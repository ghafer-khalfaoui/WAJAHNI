"""Exact (non-AI) lookups and a safe, repeatable importer for structured academic data.

Everything here is scoped to ONE university_id. Imported rows are marked
`verified=False` until someone checks them against an official source.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicEvent, Course, CoursePrerequisite, Instructor

MAX_RESULTS = 20
SEMESTERS = ("first", "second", "summer")


def normalize_code(code: str) -> str:
    """'cs 223' -> 'CS223'."""
    return "".join(str(code).split()).upper()


def parse_academic_data(data: Any) -> tuple[dict, list[str]]:
    """Validate and normalize raw data. Never raises; bad rows are skipped and reported.

    Problem messages mention row numbers or course codes only, never personal data.
    """
    problems: list[str] = []
    parsed: dict = {"courses": [], "instructors": [], "prerequisites": [], "events": []}
    if not isinstance(data, dict):
        return parsed, ["top level must be an object with courses/instructors/prerequisites"]

    seen_codes: set[str] = set()
    for i, row in enumerate(data.get("courses") or []):
        try:
            code = normalize_code(row["code"])
            name = str(row["name"]).strip()
            hours = row["hours"]
            if not code or not name:
                raise ValueError("empty code or name")
            if isinstance(hours, bool) or not isinstance(hours, int) or hours < 0:
                raise ValueError("credit hours must be a non-negative integer")
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"course row {i}: skipped ({exc})")
            continue
        if code in seen_codes:
            problems.append(f"course {code}: duplicate code, later row skipped")
            continue
        seen_codes.add(code)
        desc = row.get("desc")
        parsed["courses"].append(
            {"code": code, "name": name, "credit_hours": hours, "description": str(desc).strip() if desc else None}
        )

    seen_emails: set[str] = set()
    for i, row in enumerate(data.get("instructors") or []):
        try:
            name = str(row["name"]).strip()
            email = str(row["email"]).strip().lower()
            if not name or "@" not in email:
                raise ValueError("missing name or valid email")
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"instructor row {i}: skipped ({exc})")
            continue
        if email in seen_emails:
            problems.append(f"instructor row {i}: duplicate email, skipped")
            continue
        seen_emails.add(email)

        def clean(key: str) -> str | None:
            value = row.get(key)
            return str(value).strip() or None if value is not None else None

        status = clean("status")
        parsed["instructors"].append(
            {
                "name": name,
                "email": email,
                "title": clean("title"),
                "office_location": clean("office_location"),
                "phone": clean("phone"),
                "status": status.lower() if status else None,
            }
        )

    pairs: set[tuple[str, str]] = set()
    for i, row in enumerate(data.get("prerequisites") or []):
        try:
            course, prereq = normalize_code(row["course"]), normalize_code(row["prereq"])
        except (KeyError, TypeError):
            problems.append(f"prerequisite row {i}: skipped (needs 'course' and 'prereq')")
            continue
        if course == prereq:
            problems.append(f"prerequisite {course}: a course cannot require itself, skipped")
        elif course not in seen_codes or prereq not in seen_codes:
            problems.append(f"prerequisite {course} <- {prereq}: unknown course code, skipped")
        elif (course, prereq) not in pairs:
            pairs.add((course, prereq))
            parsed["prerequisites"].append((course, prereq))

    seen_events: set[tuple[str, dt.date, str]] = set()
    for i, row in enumerate(data.get("events") or []):
        try:
            semester = str(row["semester"]).strip().lower()
            title = str(row["title"]).strip()
            start = dt.date.fromisoformat(str(row["start"]))
            end = dt.date.fromisoformat(str(row["end"]))
            if semester not in SEMESTERS or not title or end < start:
                raise ValueError("bad semester, title or date order")
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"event row {i}: skipped ({exc})")
            continue
        key = (semester, start, title)
        if key in seen_events:
            problems.append(f"event row {i}: duplicate, skipped")
            continue
        seen_events.add(key)
        parsed["events"].append({"semester": semester, "start_date": start, "end_date": end, "title": title})
    return parsed, problems


def _differs(current, row: dict, source: str, verified: bool) -> bool:
    """True when the data, its source, or its verified flag would change."""
    return (
        any(getattr(current, k) != v for k, v in row.items())
        or current.source != source
        or bool(current.verified) != verified
    )


async def import_academic_data(
    db: AsyncSession, university_id: int, data: Any, source: str, verified: bool = False
) -> dict:
    """Insert or update rows for one university. Safe to run repeatedly (idempotent)."""
    parsed, problems = parse_academic_data(data)
    counts = {
        "courses_created": 0, "courses_updated": 0,
        "instructors_created": 0, "instructors_updated": 0,
        "prerequisites_created": 0,
        "events_created": 0, "events_updated": 0,
        "skipped_already_verified": 0,
    }

    existing_courses = {
        c.code: c
        for c in (await db.execute(select(Course).where(Course.university_id == university_id))).scalars()
    }
    for row in parsed["courses"]:
        current = existing_courses.get(row["code"])
        if current is None:
            current = Course(university_id=university_id, source=source, verified=verified, **row)
            db.add(current)
            existing_courses[row["code"]] = current
            counts["courses_created"] += 1
        elif current.verified and not verified:
            counts["skipped_already_verified"] += 1  # an unverified import never overwrites verified rows
        elif _differs(current, row, source, verified):
            for k, v in row.items():
                setattr(current, k, v)
            current.source, current.verified = source, verified
            counts["courses_updated"] += 1

    existing_instructors = {
        i.email: i
        for i in (await db.execute(select(Instructor).where(Instructor.university_id == university_id))).scalars()
    }
    for row in parsed["instructors"]:
        current = existing_instructors.get(row["email"])
        if current is None:
            db.add(Instructor(university_id=university_id, source=source, verified=verified, **row))
            counts["instructors_created"] += 1
        elif current.verified and not verified:
            counts["skipped_already_verified"] += 1  # an unverified import never overwrites verified rows
        elif _differs(current, row, source, verified):
            for k, v in row.items():
                setattr(current, k, v)
            current.source, current.verified = source, verified
            counts["instructors_updated"] += 1

    existing_events = {
        (e.semester, e.start_date, e.title): e
        for e in (await db.execute(select(AcademicEvent).where(AcademicEvent.university_id == university_id))).scalars()
    }
    for row in parsed["events"]:
        current = existing_events.get((row["semester"], row["start_date"], row["title"]))
        if current is None:
            db.add(AcademicEvent(university_id=university_id, source=source, verified=verified, **row))
            counts["events_created"] += 1
        elif current.verified and not verified:
            counts["skipped_already_verified"] += 1
        elif _differs(current, row, source, verified):
            for k, v in row.items():
                setattr(current, k, v)
            current.source, current.verified = source, verified
            counts["events_updated"] += 1

    await db.flush()  # assigns ids to new courses

    existing_pairs = {
        (p.course_id, p.prerequisite_id)
        for p in (
            await db.execute(select(CoursePrerequisite).where(CoursePrerequisite.university_id == university_id))
        ).scalars()
    }
    for course_code, prereq_code in parsed["prerequisites"]:
        pair = (existing_courses[course_code].id, existing_courses[prereq_code].id)
        if pair not in existing_pairs:
            db.add(
                CoursePrerequisite(
                    university_id=university_id, course_id=pair[0], prerequisite_id=pair[1],
                    source=source, verified=verified,
                )
            )
            existing_pairs.add(pair)
            counts["prerequisites_created"] += 1

    await db.commit()
    return {**counts, "problems": problems}


async def get_course(db: AsyncSession, university_id: int, code: str) -> Course | None:
    result = await db.execute(
        select(Course).where(Course.university_id == university_id, Course.code == normalize_code(code))
    )
    return result.scalars().first()


async def list_prerequisites(
    db: AsyncSession, university_id: int, code: str, transitive: bool = False, max_depth: int = 10
) -> list[Course]:
    """Direct prerequisites, or the full chain when transitive=True. Cycle-safe."""
    start = await get_course(db, university_id, code)
    if start is None:
        return []
    seen: set[int] = {start.id}
    frontier = {start.id}
    found: list[int] = []
    for _ in range(max_depth if transitive else 1):
        rows = await db.execute(
            select(CoursePrerequisite.prerequisite_id).where(
                CoursePrerequisite.university_id == university_id,
                CoursePrerequisite.course_id.in_(frontier),
            )
        )
        next_ids = {r for (r,) in rows.all()} - seen
        if not next_ids:
            break
        seen |= next_ids
        found.extend(sorted(next_ids))
        frontier = next_ids
    if not found:
        return []
    courses = await db.execute(
        select(Course).where(Course.university_id == university_id, Course.id.in_(found)).order_by(Course.code)
    )
    return list(courses.scalars().all())


async def list_instructors(db: AsyncSession, university_id: int, limit: int = 500) -> list[Instructor]:
    """All staff of ONE university (bounded), for matching names in Python."""
    result = await db.execute(
        select(Instructor)
        .where(Instructor.university_id == university_id)
        .order_by(Instructor.name)
        .limit(min(max(limit, 1), 1000))
    )
    return list(result.scalars().all())


async def find_instructors(db: AsyncSession, university_id: int, query: str, limit: int = 10) -> list[Instructor]:
    """Case-insensitive name search. LIKE wildcards in the query are treated as plain text."""
    text = query.strip()
    if not text:
        return []
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    result = await db.execute(
        select(Instructor)
        .where(Instructor.university_id == university_id, Instructor.name.ilike(f"%{escaped}%", escape="\\"))
        .order_by(Instructor.name)
        .limit(min(max(limit, 1), MAX_RESULTS))
    )
    return list(result.scalars().all())


async def list_events(db: AsyncSession, university_id: int) -> list[AcademicEvent]:
    """All calendar entries of ONE university in date order (a year has about 90)."""
    result = await db.execute(
        select(AcademicEvent)
        .where(AcademicEvent.university_id == university_id)
        .order_by(AcademicEvent.start_date, AcademicEvent.title)
        .limit(1000)
    )
    return list(result.scalars().all())
