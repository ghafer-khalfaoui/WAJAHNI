"""Rule-based answers from structured university data (no AI model, no cost).

Handles: course info, prerequisites (direct or full chain), and staff directory lookups.
Everything is scoped to one university_id. Only the contact detail that was asked for is
returned, and every answer says when the underlying data is not yet verified.
"""
from __future__ import annotations

import datetime as dt
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Course, Instructor
from app.schemas.chat import ChatResponse, SourceRef
from app.services.academic import (
    get_course,
    list_courses,
    list_instructors,
    list_prerequisite_details,
    list_prerequisites,
)
from app.services.calendar_answers import answer_calendar
from app.services.plan_answers import answer_plan

COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,5})\s?(\d{3,4}(?:[A-Za-z]\d)?)\b")  # CS223, CS 223, GERL201B1
WORD_RE = re.compile(r"[A-Za-zÀ-ɏ؀-ۿ'’\-]+")

PREREQ_WORDS = {"prerequisite", "prerequisites", "prereq", "prereqs", "pre-requisite", "pre-requisites", "before"}
CHAIN_WORDS = {"all", "chain", "every", "full", "entire", "complete", "whole", "everything"}
EMAIL_CUES = {"email", "emails", "e-mail", "mail"}
PHONE_CUES = {"phone", "telephone", "number", "extension", "ext", "call"}
OFFICE_CUES = {"office", "room", "located", "location", "where"}
PERSON_CUES = {"who", "dr", "prof", "professor", "doctor", "instructor", "teacher", "contact", "reach"}
STOPWORDS = (
    EMAIL_CUES | PHONE_CUES | OFFICE_CUES | PERSON_CUES | PREREQ_WORDS | CHAIN_WORDS
    | {"the", "of", "is", "are", "what", "whats", "s", "and", "for", "at", "in", "on", "to", "a", "an", "me",
       "tell", "about", "please", "how", "can", "i", "find", "give", "show", "does", "do", "his", "her", "their",
       "my", "mr", "mrs", "ms", "course", "courses", "hours", "credit", "name", "ignore", "previous"}
)
COURSE_CUES = {"course", "courses", "credit", "credits", "hours", "class", "subject"}
DIRECTORY_WORDS = {"dr", "prof", "professor", "doctor", "instructor", "teacher", "email", "emails", "mail", "phone", "telephone", "extension"}
MAX_CODES = 3
MAX_NAME_MATCHES = 5
HELP_TEXT = (
    "I don't have information about that yet. Right now I can answer questions about GJU courses "
    "(name, credit hours, prerequisites), what to take in each year and semester of the study plan, the staff directory and the academic calendar, for example "
    "\"What are the prerequisites of CS223?\", \"What is the office of Dr. Khalifeh?\" or "
    "\"When are the midterm exams?\"."
)
UNVERIFIED_NOTE = "Note: this data has not been verified against the official source yet."


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9؀-ۿ]", "", word.lower().replace("’", "'"))


def extract_course_codes(message: str) -> list[str]:
    seen: list[str] = []
    for prefix, digits in COURSE_CODE_RE.findall(message):
        code = f"{prefix}{digits}".upper()
        if code not in seen:
            seen.append(code)
    return seen[:MAX_CODES]


def _words(message: str) -> set[str]:
    return {_norm(w) for w in WORD_RE.findall(message)} - {""}


def extract_name_tokens(message: str) -> list[str]:
    tokens = []
    for raw in WORD_RE.findall(message):
        token = _norm(re.sub(r"['’]s$", "", raw))  # "Khalifeh's" -> "khalifeh"
        if len(token) >= 2 and token not in STOPWORDS and token not in tokens:
            tokens.append(token)
    return tokens[:4]


def _finish(text: str, status: str, sources: list[SourceRef]) -> ChatResponse:
    verified = all(s.verified for s in sources) if sources else True
    if sources and not verified:
        text = f"{text}\n\n{UNVERIFIED_NOTE}"
    return ChatResponse(answer=text, status=status, sources=sources, data_verified=verified)


def _course_source(course: Course) -> SourceRef:
    return SourceRef(type="course", label=course.code, source=course.source, verified=bool(course.verified))


def _instructor_source(person: Instructor) -> SourceRef:
    return SourceRef(type="instructor", label=person.name, source=person.source, verified=bool(person.verified))


def _label(course: Course) -> str:
    return f"{course.code} ({course.name})"


def format_prerequisites(course: Course, details: list[tuple[Course, bool, int | None]]) -> str:
    """Direct requirements of one course: required courses, "A or B" alternatives, corequisites, notes."""
    required = [c for c, co, group in details if not co and group is None]
    alternatives: dict[int, list[Course]] = {}
    for c, co, group in details:
        if not co and group is not None:
            alternatives.setdefault(group, []).append(c)
    corequisites = [c for c, co, _ in details if co]
    parts = [_label(c) for c in required] + [
        "either " + " or ".join(_label(c) for c in group) for group in alternatives.values()
    ]
    head = _label(course)
    if parts:
        text = f"{head} has these direct prerequisites: {', '.join(parts)}."
    elif corequisites or course.prerequisite_note:
        text = f"{head} has no prerequisite courses."
    else:
        return f"{head} has no prerequisites listed in my data."
    if corequisites:
        text += f" Corequisite (can be taken at the same time): {', '.join(_label(c) for c in corequisites)}."
    if course.prerequisite_note:
        text += f" Other conditions listed: {course.prerequisite_note}."
    return text


TRACK_NAMES = {"cybersecurity": "cybersecurity", "cyber": "cybersecurity", "datascience": "data-science",
               "general": "general"}
TRACK_TITLES = {"cybersecurity": "Cybersecurity", "data-science": "Data Science", "general": "General"}
ELECTIVE_WORDS = {"elective", "electives", "optional"}


def detect_track(words: set[str]) -> str | None:
    for word, track in TRACK_NAMES.items():
        if word in words:
            return track
    if "data" in words and "science" in words:
        return "data-science"
    return None


async def _answer_track(db: AsyncSession, university_id: int, message: str) -> ChatResponse | None:
    words = _words(message)
    track = detect_track(words)
    if track is None:
        return _finish(
            "Which track do you mean: General, Data Science or Cybersecurity?", "needs_clarification", []
        )
    wants_electives = bool(words & ELECTIVE_WORDS)
    group = f"{'elective' if wants_electives else 'track'}-{track}"
    courses = [c for c in await list_courses(db, university_id) if group in (c.plan_groups or [])]
    if not courses:
        return None
    title = TRACK_TITLES[track]
    listing = "; ".join(f"{c.code} {c.name} ({c.credit_hours} cr.)" for c in courses)
    if wants_electives:
        text = (
            f"Elective courses listed for the {title} track (the plan asks for 12 credit hours of electives, "
            f"and the plan notes electives are taken at a partner university in Germany): {listing}."
        )
    else:
        total = sum(c.credit_hours for c in courses)
        text = (
            f"The {title} track has {len(courses)} special compulsory courses ({total} credit hours): {listing}. "
            "You also take the common program, school and university courses that every Computer Science "
            f"student takes. Ask for \"{title.lower()} electives\" to see the elective list."
        )
    return _finish(text, "answered", [_course_source(c) for c in courses][:24])


async def _answer_courses(db: AsyncSession, university_id: int, message: str, codes: list[str]) -> ChatResponse:
    words = _words(message)
    wants_prereqs = bool(words & PREREQ_WORDS)
    wants_chain = bool(words & CHAIN_WORDS)
    lines: list[str] = []
    sources: list[SourceRef] = []
    missing: list[str] = []
    for code in codes:
        course = await get_course(db, university_id, code)
        if course is None:
            missing.append(code)
            continue
        sources.append(_course_source(course))
        if wants_prereqs:
            if wants_chain:
                prereqs = await list_prerequisites(db, university_id, code, transitive=True)
                if prereqs:
                    listing = ", ".join(f"{p.code} ({p.name})" for p in prereqs)
                    lines.append(
                        f"{course.code} ({course.name}) has this full chain of prerequisites: {listing}. "
                        "Where the plan says \"A or B\", both are listed; you need only one."
                    )
                else:
                    lines.append(f"{course.code} ({course.name}) has no prerequisites listed in my data.")
            else:
                details = await list_prerequisite_details(db, university_id, code)
                lines.append(format_prerequisites(course, details))
        else:
            text = f"{course.code} - {course.name}: {course.credit_hours} credit hours."
            if course.description:
                desc = course.description if len(course.description) <= 300 else course.description[:297] + "..."
                text += f" {desc}"
            lines.append(text)
    if missing:
        lines.append("I couldn't find " + ", ".join(missing) + " in the course data I have.")
    status = "answered" if sources else "not_found"
    return _finish("\n".join(lines), status, sources)


def _describe_instructor(person: Instructor, words: set[str]) -> str:
    parts: list[str] = []
    asked = False
    if words & EMAIL_CUES:
        asked = True
        parts.append(f"email: {person.email}")
    if words & PHONE_CUES:
        asked = True
        parts.append(f"phone: {person.phone}" if person.phone else "no phone listed")
    if words & OFFICE_CUES:
        asked = True
        parts.append(f"office: {person.office_location}" if person.office_location else "no office listed")
    if not asked:
        parts.append(f"title: {person.title or 'not listed'}")
        parts.append(f"office: {person.office_location}" if person.office_location else "no office listed")
    text = f"{person.name} - " + "; ".join(parts) + "."
    if person.status:
        text += f" The directory lists this person as: {person.status}."
    return text


def _name_words(name: str) -> set[str]:
    """'Prof. Feras Al-Hawari' -> {'prof', 'feras', 'alhawari', 'al', 'hawari'}."""
    words: set[str] = set()
    for chunk in name.split():
        words.add(_norm(chunk))
        words.update(_norm(part) for part in chunk.split("-"))
    words.discard("")
    return words


def _name_matches(name: str, tokens: list[str]) -> bool:
    """Every typed token must be the START of some word of the name (so 'ali' does not match 'Khalifeh')."""
    words = _name_words(name)
    return all(any(w.startswith(t) for w in words) for t in tokens)


async def _answer_instructor(db: AsyncSession, university_id: int, message: str) -> ChatResponse | None:
    tokens = extract_name_tokens(message)
    if not tokens:
        return None
    candidates = await list_instructors(db, university_id)
    matches = [p for p in candidates if _name_matches(p.name, tokens)]
    if not matches:
        return _finish(f"I couldn't find anyone matching \"{' '.join(tokens)}\" in the staff directory I have.", "not_found", [])
    if len(matches) > MAX_NAME_MATCHES:
        return _finish("Several people match. Could you give me a fuller name?", "needs_clarification", [])
    if len(matches) > 1:
        names = "; ".join(p.name for p in matches)
        return _finish(f"More than one person matches: {names}. Which one do you mean?", "needs_clarification", [])
    person = matches[0]
    return _finish(_describe_instructor(person, _words(message)), "answered", [_instructor_source(person)])


async def answer_question(
    db: AsyncSession, university_id: int, message: str, today: dt.date | None = None
) -> ChatResponse:
    message = message.strip()[:500]
    codes = extract_course_codes(message)
    words = _words(message)
    if codes:
        response = await _answer_courses(db, university_id, message, codes)
        # "deadlines in 2026" looks like a code (IN2026): only report "not found" when the
        # question really is about a course; otherwise let the other handlers try.
        if response.status == "answered" or words & (PREREQ_WORDS | COURSE_CUES):
            return response
    if "year" in words:
        plan_answer = await answer_plan(db, university_id, message, detect_track(words))
        if plan_answer is not None:
            return plan_answer
    if words & {"track", "tracks"}:
        track_answer = await _answer_track(db, university_id, message)
        if track_answer is not None:
            return track_answer
    if not words & DIRECTORY_WORDS:
        calendar = await answer_calendar(db, university_id, message, today)
        if calendar is not None:
            return calendar
    if words & (PERSON_CUES | EMAIL_CUES | PHONE_CUES | OFFICE_CUES):
        answer = await _answer_instructor(db, university_id, message)
        if answer is not None:
            return answer
    return ChatResponse(answer=HELP_TEXT, status="unsupported", sources=[], data_verified=True)
