"""Answers to "what do I take in year 2, semester 1?" from the study-plan guide (no AI model)."""
from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatResponse, SourceRef
from app.services.academic import list_plan_entries

ORDINALS = {"first": 1, "1st": 1, "one": 1, "1": 1, "second": 2, "2nd": 2, "two": 2, "2": 2,
            "third": 3, "3rd": 3, "three": 3, "3": 3, "fourth": 4, "4th": 4, "four": 4, "4": 4,
            "fifth": 5, "5th": 5, "five": 5, "5": 5}
SEMESTER_NUMBERS = {1: "first", 2: "second"}
TRACK_TITLES = {"cybersecurity": "Cybersecurity", "data-science": "Data Science", "general": "General"}
UNVERIFIED_NOTE = "Note: this data has not been verified against the official source yet."
GUIDE_NOTE = ("This is the suggested order from the official study-plan guide; it does not include remedial "
              "courses and the real order can depend on your situation.")
TOKEN_RE = re.compile(r"[a-z0-9]+")


def extract_year_semester(message: str) -> tuple[int | None, str | None]:
    """'second year first semester' / 'year 2 semester 1' / 'summer semester' -> (2, 'first')."""
    tokens = TOKEN_RE.findall(message.lower())

    used: set[int] = set()  # a number belongs to one word only ("year 2 semester 1")

    def number_near(word: str) -> int | None:
        for i, token in enumerate(tokens):
            if token == word:
                for j in (i - 1, i + 1):  # "second year" or "year 2"
                    if 0 <= j < len(tokens) and j not in used and tokens[j] in ORDINALS:
                        used.add(j)
                        return ORDINALS[tokens[j]]
        return None

    year = number_near("year")
    number = number_near("semester") or number_near("sem")
    semester = SEMESTER_NUMBERS.get(number) if number else None
    if "summer" in tokens:
        semester = "summer"
    return year, semester


def _line(entry, course) -> str:
    if course is None:
        return f"{entry.label} ({entry.credit_hours} cr.)"
    return f"{course.code} {course.name} ({entry.credit_hours} cr.)"


def _describe_semester(rows) -> tuple[str, int]:
    """One line per slot; the two German alternatives (B1/B2 track) are one slot."""
    parts: list[str] = []
    german: list[str] = []
    total = 0
    german_credit = 0
    for entry, course in rows:
        if course is not None and course.code.startswith("GERL"):
            german.append(course.code)
            if not german_credit:
                german_credit = entry.credit_hours
                total += german_credit
            continue
        parts.append(_line(entry, course))
        total += entry.credit_hours
    if german:
        parts.insert(0, f"German course: {' or '.join(german)} ({german_credit} cr.; B1 or B2 track)")
    return "; ".join(parts), total


async def answer_plan(db: AsyncSession, university_id: int, message: str, track: str | None) -> ChatResponse | None:
    year, semester = extract_year_semester(message)
    if year is None:
        return None
    rows = await list_plan_entries(db, university_id, year, semester, track)
    if not rows:
        return None
    by_track: dict[str, dict[str, list]] = {}
    for entry, course in rows:
        by_track.setdefault(entry.track, {}).setdefault(entry.semester, []).append((entry, course))

    def signature(semesters):  # what the student would see, to compare tracks
        return {s: sorted((e.course_id or 0, e.label or "") for e, _ in r) for s, r in semesters.items()}

    if track is None and len(by_track) > 1:
        first = signature(next(iter(by_track.values())))
        if any(signature(v) != first for v in by_track.values()):
            return ChatResponse(
                answer=f"Year {year} is different in each track. Which track do you mean: General, Data Science "
                       "or Cybersecurity?",
                status="needs_clarification", sources=[], data_verified=True)
        shown = {"all tracks": next(iter(by_track.values()))}
    else:
        shown = {TRACK_TITLES.get(t, t) + " track": v for t, v in by_track.items()}

    lines = []
    for title, semesters in shown.items():
        for sem in ("first", "second", "summer"):
            if sem in semesters:
                text, total = _describe_semester(semesters[sem])
                lines.append(f"{title.capitalize() if title == 'all tracks' else title}, year {year}, "
                             f"{sem} semester ({total} credit hours): {text}.")
    entries = [e for e, _ in rows]
    verified = all(e.verified for e in entries)
    sources = [SourceRef(type="plan", label=f"Study plan guide, year {year}", source=entries[0].source,
                         verified=verified)]
    seen = set()
    for _, course in rows:
        if course is not None and course.code not in seen and len(seen) < 23:
            seen.add(course.code)
            sources.append(SourceRef(type="course", label=course.code, source=course.source,
                                     verified=bool(course.verified)))
    text = "\n".join(lines) + "\n\n" + GUIDE_NOTE
    if not all(s.verified for s in sources):
        text += "\n\n" + UNVERIFIED_NOTE
    return ChatResponse(answer=text, status="answered", sources=sources,
                        data_verified=all(s.verified for s in sources))
