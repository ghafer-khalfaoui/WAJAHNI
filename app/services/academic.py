"""Exact (non-AI) lookups and a safe, repeatable importer for structured academic data.

Everything here is scoped to ONE university_id. Imported rows are marked
`verified=False` until someone checks them against an official source.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicEvent, Course, CoursePrerequisite, Instructor, PlanEntry, Program, ProgramCourse,
)

MAX_RESULTS = 20
SEMESTERS = ("first", "second", "summer")
PROGRAM_KINDS = ("regular", "dual")
GROUP_KINDS = ("compulsory", "elective", "remedial")
MAX_CONFLICTS = 60


def normalize_code(code: str) -> str:
    """'cs 223' -> 'CS223'."""
    return "".join(str(code).split()).upper()


def parse_academic_data(data: Any) -> tuple[dict, list[str]]:
    """Validate and normalize raw data. Never raises; bad rows are skipped and reported.

    Problem messages mention row numbers or course codes only, never personal data.
    """
    problems: list[str] = []
    parsed: dict = {"courses": [], "instructors": [], "prerequisites": [], "events": [], "plan_entries": [],
              "program": None, "program_courses": [], "replace_prerequisites": False}
    if not isinstance(data, dict):
        return parsed, ["top level must be an object with courses/instructors/prerequisites"]

    parsed["replace_prerequisites"] = bool(data.get("replace_prerequisites"))
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
        groups = row.get("plan_groups")
        if groups is not None and not (isinstance(groups, list) and all(isinstance(g, str) for g in groups)):
            problems.append(f"course {code}: plan_groups must be a list of text, ignored")
            groups = None
        note = row.get("prerequisite_note")
        parsed["courses"].append(
            {
                "code": code, "name": name, "credit_hours": hours,
                "description": str(desc).strip() if desc else None,
                "plan_groups": list(groups) if groups else None,
                "prerequisite_note": str(note).strip() if note else None,
            }
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
            group = row.get("alt_group")
            group = group if isinstance(group, int) and not isinstance(group, bool) else None
            parsed["prerequisites"].append((course, prereq, bool(row.get("corequisite")), group))

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

    program = data.get("program")
    if program is not None:
        try:
            code = re.sub(r"[^a-z0-9-]+", "-", str(program["code"]).strip().lower()).strip("-")
            name = str(program["name"]).strip()
            kind = str(program.get("kind") or "regular").strip().lower()
            if not code or not name or kind not in PROGRAM_KINDS:
                raise ValueError("needs a code, a name and kind regular/dual")
            parsed["program"] = {
                "code": code, "name": name, "kind": kind,
                "school": str(program["school"]).strip() if program.get("school") else None,
                "degree": str(program["degree"]).strip() if program.get("degree") else None,
                "plan_version": str(program["plan_version"]).strip() if program.get("plan_version") else None,
            }
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            problems.append(f"program: ignored ({exc})")
    if parsed["program"] is None and (data.get("program_courses") or data.get("plan_entries")):
        problems.append("program_courses/plan_entries need a valid 'program' object, they were ignored")
        data = {**data, "program_courses": [], "plan_entries": []}

    seen_groups: set[tuple[str, str]] = set()
    for i, row in enumerate(data.get("program_courses") or []):
        try:
            code = normalize_code(row["course"])
            group = str(row["group"]).strip()
            kind = str(row["kind"]).strip().lower()
            track = str(row["track"]).strip().lower() if row.get("track") else None
            scope = str(row["scope"]).strip().lower() if row.get("scope") else None
            if not group or kind not in GROUP_KINDS or code not in seen_codes:
                raise ValueError("needs a known course, a group title and a kind (compulsory/elective/remedial)")
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            problems.append(f"program course row {i}: skipped ({exc})")
            continue
        if (code, group) in seen_groups:
            problems.append(f"program course row {i}: duplicate, skipped")
            continue
        seen_groups.add((code, group))
        parsed["program_courses"].append({"course": code, "group_title": group, "scope": scope, "kind": kind,
                                          "track": track})

    seen_slots: set[tuple[str, int, str, int]] = set()
    for i, row in enumerate(data.get("plan_entries") or []):
        try:
            track = str(row["track"]).strip().lower()
            year, position, hours = row["year"], row["position"], row["credit_hours"]
            semester = str(row["semester"]).strip().lower()
            code = normalize_code(row["code"]) if row.get("code") else None
            label = str(row["label"]).strip() if row.get("label") else None
            for number in (year, position, hours):
                if isinstance(number, bool) or not isinstance(number, int) or number < 0:
                    raise ValueError("year, position and credit_hours must be whole numbers")
            if not track or semester not in SEMESTERS or year < 1 or position < 1:
                raise ValueError("bad track, semester, year or position")
            if code is None and label is None:
                raise ValueError("needs a course code or a label")
            if code is not None and code not in seen_codes:
                raise ValueError(f"unknown course code {code}")
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"plan entry row {i}: skipped ({exc})")
            continue
        slot = (track, year, semester, position)
        if slot in seen_slots:
            problems.append(f"plan entry row {i}: duplicate slot, skipped")
            continue
        seen_slots.add(slot)
        parsed["plan_entries"].append(
            {"track": track, "year": year, "semester": semester, "position": position,
             "code": code, "label": label, "credit_hours": hours}
        )
    return parsed, problems


def _differs(current, row: dict, source: str, verified: bool) -> bool:
    """True when the data, its source, or its verified flag would change."""
    return (
        any(getattr(current, k) != v for k, v in row.items())
        or current.source != source
        or bool(current.verified) != verified
    )


async def import_academic_data(
    db: AsyncSession, university_id: int, data: Any, source: str, verified: bool = False,
    overwrite_conflicts: bool = False,
) -> dict:
    """Insert or update rows for one university. Safe to run repeatedly (idempotent).

    Courses and prerequisites are shared by every program of the university. When a row already exists
    from a DIFFERENT source with different data, the importer reports a conflict and keeps the existing
    data unless `overwrite_conflicts` is true. Program-specific rows (requirement tables, year/semester
    slots) belong to one program and are replaced for that program only.
    """
    parsed, problems = parse_academic_data(data)
    counts = {
        "courses_created": 0, "courses_updated": 0,
        "instructors_created": 0, "instructors_updated": 0,
        "prerequisites_created": 0, "prerequisites_updated": 0, "prerequisites_removed": 0,
        "events_created": 0, "events_updated": 0,
        "programs_created": 0, "programs_updated": 0,
        "program_courses_created": 0, "program_courses_updated": 0, "program_courses_removed": 0,
        "plan_entries_created": 0, "plan_entries_updated": 0, "plan_entries_removed": 0,
        "skipped_already_verified": 0, "conflicts_kept": 0,
    }
    conflicts: list[str] = []

    def note_conflict(text: str) -> None:
        counts["conflicts_kept"] += 1
        if len(conflicts) < MAX_CONFLICTS:
            conflicts.append(text)

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
        elif current.source != source and not overwrite_conflicts and not (verified and not current.verified):
            # Shared course already stored from another file: keep it, report real disagreements only.
            changed = {k: (getattr(current, k), v) for k, v in row.items()
                       if k in ("name", "credit_hours") and getattr(current, k) != v}
            if changed:
                note_conflict(f"course {row['code']}: kept " + "; ".join(
                    f"{k} '{o}' (file says '{n}')" for k, (o, n) in changed.items()))
            elif not current.prerequisite_note and row.get("prerequisite_note"):
                current.prerequisite_note = row["prerequisite_note"]  # fill a gap, change nothing else
                counts["courses_updated"] += 1
        elif _differs(current, row, source, verified):
            for k, v in row.items():
                if k == "plan_groups" and v is None:
                    continue  # plan groups now live in program_courses; never wipe the old column
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

    # ---- prerequisites (shared by all programs) ----
    existing = {
        (p.course_id, p.prerequisite_id): p
        for p in (
            await db.execute(select(CoursePrerequisite).where(CoursePrerequisite.university_id == university_id))
        ).scalars()
    }
    file_pairs: dict[int, set[tuple[int, bool, int | None]]] = {}
    for course_code, prereq_code, corequisite, alt_group in parsed["prerequisites"]:
        file_pairs.setdefault(existing_courses[course_code].id, set()).add(
            (existing_courses[prereq_code].id, corequisite, alt_group))
    db_pairs: dict[int, set[tuple[int, bool, int | None]]] = {}
    for (course_id, prereq_id), p in existing.items():
        db_pairs.setdefault(course_id, set()).add((prereq_id, bool(p.corequisite), p.alt_group))
    id_to_code = {c.id: code for code, c in existing_courses.items()}
    blocked: set[int] = set()  # courses whose prerequisites differ from another source: left untouched
    if not overwrite_conflicts:
        for course_id in {existing_courses[row["code"]].id for row in parsed["courses"]}:
            old, new = db_pairs.get(course_id, set()), file_pairs.get(course_id, set())
            others = [p for (c, _), p in existing.items() if c == course_id and p.source != source]
            if old and others and old != new and not parsed["replace_prerequisites"]:
                blocked.add(course_id)
                names = lambda pairs: ", ".join(sorted(id_to_code[pid] + ("(co)" if co else "") for pid, co, _ in pairs)) or "none"
                note_conflict(f"prerequisites of {id_to_code[course_id]}: kept [{names(old)}] (file says [{names(new)}])")

    wanted: set[tuple[int, int]] = set()
    for course_code, prereq_code, corequisite, alt_group in parsed["prerequisites"]:
        pair = (existing_courses[course_code].id, existing_courses[prereq_code].id)
        wanted.add(pair)
        if pair[0] in blocked:
            continue
        current = existing.get(pair)
        flags = {"corequisite": corequisite, "alt_group": alt_group}
        if current is None:
            db.add(
                CoursePrerequisite(
                    university_id=university_id, course_id=pair[0], prerequisite_id=pair[1],
                    source=source, verified=verified, **flags,
                )
            )
            counts["prerequisites_created"] += 1
        elif current.verified and not verified:
            counts["skipped_already_verified"] += 1
        elif _differs(current, flags, source, verified):
            for k, v in flags.items():
                setattr(current, k, v)
            current.source, current.verified = source, verified
            counts["prerequisites_updated"] += 1

    if parsed["replace_prerequisites"]:
        # This file lists the complete prerequisites of every course it contains: remove older pairs
        # for those courses that it no longer lists (never touching verified rows from an unverified file).
        in_file = {existing_courses[row["code"]].id for row in parsed["courses"]}
        for pair, current in existing.items():
            if pair[0] in in_file and pair not in wanted:
                if current.verified and not verified:
                    counts["skipped_already_verified"] += 1
                else:
                    await db.delete(current)
                    counts["prerequisites_removed"] += 1

    # ---- one program: requirement tables and year/semester slots ----
    if parsed["program"] is not None:
        row = parsed["program"]
        program = (await db.execute(
            select(Program).where(Program.university_id == university_id, Program.code == row["code"])
        )).scalar_one_or_none()
        if program is None:
            program = Program(university_id=university_id, source=source, verified=verified, **row)
            db.add(program)
            counts["programs_created"] += 1
        elif program.verified and not verified:
            counts["skipped_already_verified"] += 1
        elif _differs(program, row, source, verified):
            for k, v in row.items():
                setattr(program, k, v)
            program.source, program.verified = source, verified
            counts["programs_updated"] += 1
        await db.flush()

        existing_groups = {
            (g.course_id, g.group_title): g
            for g in (await db.execute(select(ProgramCourse).where(ProgramCourse.program_id == program.id))).scalars()
        }
        wanted_groups: set[tuple[int, str]] = set()
        for g in parsed["program_courses"]:
            key = (existing_courses[g["course"]].id, g["group_title"])
            wanted_groups.add(key)
            fields = {"scope": g["scope"], "kind": g["kind"], "track": g["track"]}
            current = existing_groups.get(key)
            if current is None:
                db.add(ProgramCourse(university_id=university_id, program_id=program.id, course_id=key[0],
                                     group_title=key[1], source=source, verified=verified, **fields))
                counts["program_courses_created"] += 1
            elif current.verified and not verified:
                counts["skipped_already_verified"] += 1
            elif _differs(current, fields, source, verified):
                for k, v in fields.items():
                    setattr(current, k, v)
                current.source, current.verified = source, verified
                counts["program_courses_updated"] += 1
        for key, current in existing_groups.items():
            if key not in wanted_groups:
                if current.verified and not verified:
                    counts["skipped_already_verified"] += 1
                else:
                    await db.delete(current)
                    counts["program_courses_removed"] += 1

        existing_slots = {
            (e.track, e.year, e.semester, e.position): e
            for e in (await db.execute(
                select(PlanEntry).where(PlanEntry.university_id == university_id, PlanEntry.program_id == program.id)
            )).scalars()
        }
        wanted_slots: set[tuple[str, int, str, int]] = set()
        for e in parsed["plan_entries"]:
            slot = (e["track"], e["year"], e["semester"], e["position"])
            wanted_slots.add(slot)
            fields = {"course_id": existing_courses[e["code"]].id if e["code"] else None,
                      "label": e["label"], "credit_hours": e["credit_hours"]}
            current = existing_slots.get(slot)
            if current is None:
                db.add(PlanEntry(university_id=university_id, program_id=program.id, track=slot[0], year=slot[1],
                                 semester=slot[2], position=slot[3], source=source, verified=verified, **fields))
                counts["plan_entries_created"] += 1
            elif current.verified and not verified:
                counts["skipped_already_verified"] += 1
            elif _differs(current, fields, source, verified):
                for k, v in fields.items():
                    setattr(current, k, v)
                current.source, current.verified = source, verified
                counts["plan_entries_updated"] += 1
        listed_tracks = {slot[0] for slot in wanted_slots}  # a file never touches tracks it does not list
        for slot, current in existing_slots.items():
            if slot not in wanted_slots and slot[0] in listed_tracks:
                if current.verified and not verified:
                    counts["skipped_already_verified"] += 1
                else:
                    await db.delete(current)
                    counts["plan_entries_removed"] += 1
        if parsed["plan_entries"]:  # slots saved before programs existed are superseded by this file
            legacy = (await db.execute(
                select(PlanEntry).where(PlanEntry.university_id == university_id, PlanEntry.program_id.is_(None))
            )).scalars().all()
            for current in legacy:
                await db.delete(current)
                counts["plan_entries_removed"] += 1

    await db.commit()
    return {**counts, "problems": problems, "conflicts": conflicts}


async def get_course(db: AsyncSession, university_id: int, code: str) -> Course | None:
    result = await db.execute(
        select(Course).where(Course.university_id == university_id, Course.code == normalize_code(code))
    )
    return result.scalars().first()


async def list_prerequisites(
    db: AsyncSession, university_id: int, code: str, transitive: bool = False, max_depth: int = 10
) -> list[Course]:
    """Direct prerequisites, or the full chain when transitive=True. Cycle-safe. Corequisites are not followed."""
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
                CoursePrerequisite.corequisite.is_(False),
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


async def list_prerequisite_details(
    db: AsyncSession, university_id: int, code: str
) -> list[tuple[Course, bool, int | None]]:
    """Direct requirements of one course as (course, is_corequisite, alt_group), ordered by code."""
    start = await get_course(db, university_id, code)
    if start is None:
        return []
    rows = await db.execute(
        select(Course, CoursePrerequisite.corequisite, CoursePrerequisite.alt_group)
        .join(CoursePrerequisite, CoursePrerequisite.prerequisite_id == Course.id)
        .where(CoursePrerequisite.university_id == university_id, CoursePrerequisite.course_id == start.id)
        .order_by(Course.code)
    )
    return [(course, bool(co), group) for course, co, group in rows.all()]


async def list_courses(db: AsyncSession, university_id: int, limit: int = 1000) -> list[Course]:
    """All courses of ONE university (bounded), ordered by code."""
    result = await db.execute(
        select(Course).where(Course.university_id == university_id).order_by(Course.code).limit(limit)
    )
    return list(result.scalars().all())


async def list_plan_entries(
    db: AsyncSession, university_id: int, year: int, semester: str | None = None, track: str | None = None
) -> list[tuple[PlanEntry, Course | None]]:
    """Slots of the study-plan guide for one year (and optionally one semester / track), in table order."""
    query = (
        select(PlanEntry, Course)
        .outerjoin(Course, Course.id == PlanEntry.course_id)
        .where(PlanEntry.university_id == university_id, PlanEntry.year == year)
        .order_by(PlanEntry.track, PlanEntry.position)
    )
    if semester:
        query = query.where(PlanEntry.semester == semester)
    if track:
        query = query.where(PlanEntry.track == track)
    rows = (await db.execute(query)).all()
    order = {name: i for i, name in enumerate(SEMESTERS)}
    return sorted(((e, c) for e, c in rows), key=lambda r: (r[0].track, order.get(r[0].semester, 9), r[0].position))
