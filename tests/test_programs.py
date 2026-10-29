"""Two programs that share a course: each keeps its own requirement tables, the course stays single."""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
URL = os.environ.get("WAJAHNI_TEST_DB_URL")
needs_db = pytest.mark.skipif(not URL, reason="set WAJAHNI_TEST_DB_URL to run database tests")

BASE = {
    "plan": "test", "source_url": "x",
    "courses": [
        {"code": "MATH101", "name": "Calculus I", "hours": 3},
        {"code": "PHYS101", "name": "Physics I", "hours": 3},
    ],
    "prerequisites": [{"course": "PHYS101", "prereq": "MATH101", "corequisite": False, "alt_group": None}],
    "program": {"code": "aaa", "name": "Program A", "kind": "regular", "plan_version": "2024"},
    "program_courses": [
        {"course": "MATH101", "group": "Program - Compulsory", "scope": "program", "kind": "compulsory", "track": None},
        {"course": "PHYS101", "group": "Program - Compulsory", "scope": "program", "kind": "compulsory", "track": None},
    ],
    "plan_entries": [
        {"track": "all", "year": 1, "semester": "first", "position": 1, "code": "MATH101", "label": None, "credit_hours": 3},
    ],
}


@needs_db
def test_shared_course_is_stored_once_and_disagreements_are_reported_not_applied():
    from sqlalchemy import func, select

    from app.models.academic import Course, PlanEntry, Program, ProgramCourse
    from app.models.university import University
    from app.services.academic import import_academic_data
    from db_helpers import run_in_schema, scratch_schema

    other = copy.deepcopy(BASE)
    other["program"] = {"code": "bbb", "name": "Program B", "kind": "regular", "plan_version": "2024"}
    other["courses"][0]["name"] = "Calculus 1"  # same course, written differently by another file
    other["plan_entries"][0]["position"] = 2

    with scratch_schema(URL) as schema:
        async def run(db):
            uni = University(name="U", domain="u.edu")
            db.add(uni)
            await db.commit()
            first = await import_academic_data(db, uni.id, BASE, source="file-a")
            assert first["programs_created"] == 1 and first["program_courses_created"] == 2
            second = await import_academic_data(db, uni.id, other, source="file-b")
            assert second["programs_created"] == 1
            assert second["conflicts_kept"] == 1 and "Calculus 1" in second["conflicts"][0]
            count = lambda model: db.execute(select(func.count()).select_from(model))
            assert (await count(Course)).scalar_one() == 2  # shared, not duplicated
            assert (await count(Program)).scalar_one() == 2
            assert (await count(ProgramCourse)).scalar_one() == 4  # each program has its own rows
            assert (await count(PlanEntry)).scalar_one() == 2
            name = (await db.execute(select(Course.name).where(Course.code == "MATH101"))).scalar_one()
            assert name == "Calculus I"  # the first source is kept
            forced = await import_academic_data(db, uni.id, other, source="file-b", overwrite_conflicts=True)
            name = (await db.execute(select(Course.name).where(Course.code == "MATH101"))).scalar_one()
            assert name == "Calculus 1" and forced["conflicts_kept"] == 0

        run_in_schema(URL, schema, run)
