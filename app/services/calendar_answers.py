"""Answer academic-calendar questions by matching words against event titles (no AI model).

`select_events` is a pure function (easy to test); `answer_calendar` adds the database lookup.
Matching is deliberately simple and conservative: at least one meaningful word of the question
must appear in the event title, otherwise nothing is returned and the caller falls through.
"""
from __future__ import annotations

import datetime as dt
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicEvent
from app.schemas.chat import ChatResponse, SourceRef
from app.services.academic import list_events

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "be", "will", "when", "what", "whens", "whats", "s", "of", "to", "for",
    "in", "on", "at", "by", "do", "does", "did", "i", "my", "me", "we", "our", "can", "you", "tell", "about",
    "please", "date", "dates", "deadline", "deadlines", "time", "there", "any", "next", "upcoming", "it", "this",
    "that", "and", "or", "how", "long", "until", "which", "give", "show", "gju", "university", "have", "has",
    "get", "need", "from", "with", "as", "if", "are", "year", "academic", "calendar", "schedule", "term",
}
WEAK = {"day", "last", "first", "semester", "period", "week", "1st", "2nd", "summer"}
SYNONYMS = {
    "register": "registration", "registering": "registration", "registered": "registration",
    "withdrawal": "withdraw", "withdrawing": "withdraw",
    "start": "beginning", "begin": "beginning", "starting": "beginning", "commence": "beginning",
    "mid": "midterm", "finals": "final",
}
HOLIDAY_WORDS = {"holiday", "eid", "christmas", "easter", "palm", "independence", "labor", "prophet"}
UPCOMING_CUES = {"upcoming", "next", "coming", "soon"}
SEMESTER_WORDS = {"1st": "first", "fall": "first", "2nd": "second", "spring": "second", "summer": "summer"}
MAX_SHOWN = 3


def _stem(word: str) -> str:
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _tokens(text: str) -> list[str]:
    words = [_stem(w) for w in TOKEN_RE.findall(text.lower().replace("’", "'").replace("'s", ""))]
    words = [SYNONYMS.get(w, w) for w in words]
    return [w for w in words if w not in STOPWORDS]


def _event_tokens(event: AcademicEvent) -> set[str]:
    tokens = set(_tokens(event.title))
    if tokens & HOLIDAY_WORDS:
        tokens.add("holiday")
    return tokens


def _wanted_semester(raw_words: set[str]) -> str | None:
    if "semester" in raw_words:
        if raw_words & {"first", "1st", "fall"}:
            return "first"
        if raw_words & {"second", "2nd", "spring"}:
            return "second"
    for word, semester in SEMESTER_WORDS.items():
        if word in raw_words:
            return semester
    return None


def _question_tokens(message: str) -> list[str]:
    tokens = _tokens(message)
    raw = set(TOKEN_RE.findall(message.lower()))
    if "classe" in tokens or "class" in tokens:  # "when do classes start" -> "First day of classes"
        if "beginning" in tokens:
            tokens = [t for t in tokens if t != "beginning"] + ["first", "day"]
    if "midterm" in tokens and "mid" in raw:
        tokens = [t for t in tokens if t != "term"]
    return tokens


def select_events(message: str, events: list[AcademicEvent], today: dt.date) -> tuple[list[AcademicEvent], int, bool]:
    """Returns (events to show, how many more matched, True if every match is already in the past)."""
    raw = set(TOKEN_RE.findall(message.lower()))
    wanted = _wanted_semester(raw)
    qtokens = [t for t in _question_tokens(message) if t not in {"semester"} or t in raw]
    qset = set(qtokens)
    pool = [e for e in events if wanted is None or e.semester == wanted]
    if not pool:
        return [], 0, False

    strong_query = {t for t in qset if t not in WEAK}
    if not strong_query:
        if raw & UPCOMING_CUES or "calendar" in raw or "schedule" in raw or "deadline" in raw or "deadlines" in raw:
            upcoming = [e for e in pool if e.end_date >= today]
            return upcoming[:MAX_SHOWN], max(len(upcoming) - MAX_SHOWN, 0), False
        return [], 0, False

    scored = []
    for event in pool:
        etokens = _event_tokens(event)
        matched = qset & etokens
        if matched - WEAK:
            # more matched words wins; among equals, the shorter (closer) title wins
            scored.append(((len(matched), -len(etokens)), event))
    if not scored:
        return [], 0, False
    best = max(key for key, _ in scored)
    hits = [e for key, e in scored if key == best]
    upcoming = [e for e in hits if e.end_date >= today]
    if not upcoming:
        return hits[-1:], 0, True
    return upcoming[:MAX_SHOWN], max(len(upcoming) - MAX_SHOWN, 0), False


def _fmt(date: dt.date) -> str:
    return f"{date.strftime('%a')} {date.day} {date.strftime('%b %Y')}"


def describe_event(event: AcademicEvent) -> str:
    when = _fmt(event.start_date) if event.start_date == event.end_date else f"{_fmt(event.start_date)} to {_fmt(event.end_date)}"
    return f"{event.title} ({event.semester} semester): {when}"


async def answer_calendar(
    db: AsyncSession, university_id: int, message: str, today: dt.date | None = None
) -> ChatResponse | None:
    today = today or dt.date.today()
    events = await list_events(db, university_id)
    if not events:
        return None
    shown, more, past = select_events(message, events, today)
    if not shown:
        return None
    lines = [describe_event(e) + "." for e in shown]
    text = "\n".join(lines)
    if past:
        text = f"That already happened this year. The calendar I have lists:\n{text}"
    if more:
        text += f"\n(and {more} more matching entries - ask about a specific one)"
    text += "\nDates come from the official GJU academic calendar and can change."
    sources = [
        SourceRef(type="event", label=e.title, source=e.source, verified=bool(e.verified)) for e in shown
    ]
    verified = all(s.verified for s in sources)
    if not verified:
        from app.services.chat_router import UNVERIFIED_NOTE  # local import avoids a cycle

        text += f"\n\n{UNVERIFIED_NOTE}"
    return ChatResponse(answer=text, status="answered", sources=sources, data_verified=verified)
