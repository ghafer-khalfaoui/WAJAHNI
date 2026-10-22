"""Tests for the structured academic data importer and lookups.

Offline tests always run. The database test only runs when WAJAHNI_TEST_DB_URL is set,
and it works ONLY inside a temporary schema that it creates and drops itself, so it never
touches your real tables.
"""
import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest

from app.services.academic import normalize_code, parse_academic_data

FIXTURE = Path(__file__).parent / "fixtures" / "sample_academic.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_normalize_code():
    assert normalize_code(" cs 223 ") == "CS223"


def test_parse_normalizes_and_skips_bad_rows():
    parsed, problems = parse_academic_data(DATA)
    assert [c["code"] for c in parsed["courses"]] == ["T101", "T201", "T301"]
    assert [i["email"] for i in parsed["instructors"]] == ["ada.example@example.edu", "bob.sample@example.edu"]
    assert parsed["instructors"][1]["status"] == "on leave"
    assert parsed["prerequisites"] == [("T201", "T101"), ("T301", "T201")]
    assert len(problems) == 6


def test_problem_messages_never_contain_personal_data():
    _, problems = parse_academic_data(DATA)
    assert all("@" not in p and "example" not in p.lower() for p in problems)


def test_parse_rejects_non_object():
    parsed, problems = parse_academic_data(["not", "an", "object"])
    assert problems and not parsed["courses"]


URL = os.environ.get("WAJAHNI_TEST_DB_URL")


@pytest.mark.skipif(not URL, reason="set WAJAHNI_TEST_DB_URL to run against a real database")
def test_import_and_lookups_in_a_temporary_schema():
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.models.document  # noqa: F401
    from app.core.database import Base
    from app.models.academic import Course, CoursePrerequisite, Instructor
    from app.models.university import University
    from app.services.academic import (
        find_instructors, get_course, import_academic_data, list_prerequisites,
    )

    async def run():
        schema = f"wajahni_test_{uuid.uuid4().hex[:10]}"
        admin = create_async_engine(URL)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(URL, connect_args={"server_settings": {"search_path": schema}})
        try:
            tables = [University.__table__, Course.__table__, CoursePrerequisite.__table__, Instructor.__table__]
            async with engine.begin() as conn:
                await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                uni = University(name="Example U", domain="example.edu")
                other = University(name="Other U", domain="other.edu")
                db.add_all([uni, other])
                await db.commit()

                first = await import_academic_data(db, uni.id, DATA, source="test")
                assert (first["courses_created"], first["instructors_created"], first["prerequisites_created"]) == (3, 2, 2)
                assert len(first["problems"]) == 6

                again = await import_academic_data(db, uni.id, DATA, source="test")
                assert again["courses_created"] == again["courses_updated"] == 0
                assert again["instructors_created"] == again["instructors_updated"] == 0
                assert again["prerequisites_created"] == 0

                assert (await get_course(db, uni.id, " t 101")).code == "T101"
                assert (await get_course(db, uni.id, "T101")).verified is False
                assert [c.code for c in await list_prerequisites(db, uni.id, "T301")] == ["T201"]
                assert [c.code for c in await list_prerequisites(db, uni.id, "T301", transitive=True)] == ["T101", "T201"]
                assert await list_prerequisites(db, uni.id, "T101", transitive=True) == []

                # another university sees nothing
                assert await get_course(db, other.id, "T101") is None
                assert await list_prerequisites(db, other.id, "T301", transitive=True) == []
                assert await find_instructors(db, other.id, "ada") == []

                assert [i.name for i in await find_instructors(db, uni.id, "ADA")] == ["Dr. Ada Example"]
                assert await find_instructors(db, uni.id, "%") == []
                assert (await find_instructors(db, uni.id, "bob"))[0].status == "on leave"

                # re-importing the same data as verified flips the flag even though the data is unchanged
                promoted = await import_academic_data(db, uni.id, DATA, source="official", verified=True)
                assert promoted["courses_updated"] == 3 and promoted["instructors_updated"] == 2
                assert (await get_course(db, uni.id, "T101")).verified is True
                # a later unverified import must not downgrade or overwrite verified rows
                kept = await import_academic_data(db, uni.id, DATA, source="old file", verified=False)
                assert kept["courses_updated"] == kept["instructors_updated"] == 0
                assert kept["skipped_already_verified"] == 5
                assert (await get_course(db, uni.id, "T101")).source == "official"

                t101 = await get_course(db, uni.id, "T101")
                db.add(CoursePrerequisite(university_id=uni.id, course_id=t101.id, prerequisite_id=t101.id))
                with pytest.raises(IntegrityError):
                    await db.commit()
                await db.rollback()
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(run())
