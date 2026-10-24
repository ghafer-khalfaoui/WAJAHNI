"""Study-plan guide (year/semester placement): parser, dataset, import and chat answers."""
import copy
import json
import os
from pathlib import Path

import pytest

from app.services.academic import parse_academic_data
from app.services.plan_answers import extract_year_semester
from app.services.plan_parser import parse_guide

DATASET = Path(__file__).parent.parent / "datasets" / "gju" / "cs_study_plan_2023_2024.json"
CREDITS = {"TS101": 3, "TS102": 3, "GERL101B1": 3, "GERL101B2": 3}

GUIDE = """\
Study Plan Guide for a B.Sc. Degree in Testing
   A. Study Plan Guide for the General Track
                                  First Year
                                First Semester
  Course ID   Course Name               Credit   ECTS   Lect. Prac.  Type  Prerequisites
TS101          Intro                       3       3      3     -     F2F   -
GERL101B1                 B1-Track
          German I                         3       6      9     -     F2F   -
GERL101B2                 B2-Track
              University Elective          3
                                Total      9              12    0

                                  First Year
                                Second Semester
TS102          Second                      3       3      3     -     F2F   TS101
                                Total      3               3    0
   C. Study Plan Guide for the Cybersecurity Track
                                  First Year
                                First Semester
TS101          Intro                       3       3      3     -     F2F   -
                                  First Year
                                Second Semester
TS101          Intro again                 3       3      3     -     F2F   -
                                Total      3               3    0
VI. Compulsory Courses Offered by the Department
TS102          Not part of the guide       3
"""


def test_guide_slots_german_pair_counts_once_and_electives_have_a_label():
    entries, warnings = parse_guide(GUIDE.replace("Total      3               3    0\n   C.", "Total      3               3    0\n   C."), CREDITS)
    general_first = [e for e in entries if e["track"] == "general" and e["semester"] == "first"]
    assert [(e["code"], e["label"], e["position"]) for e in general_first] == [
        ("TS101", None, 1), ("GERL101B1", None, 2), ("GERL101B2", None, 3), (None, "University Elective", 4)]
    assert all(e["year"] == 1 for e in entries)
    assert not [w for w in warnings if "add up" in w]  # 3 + 3 (German once) + 3 = 9 = PDF total


def test_guide_stops_at_the_next_section_and_keeps_tracks_apart():
    entries, _ = parse_guide(GUIDE, CREDITS)
    assert {e["track"] for e in entries} == {"general", "cybersecurity"}
    assert not any(e["position"] == 1 and e["code"] == "TS102" and e["track"] == "cybersecurity" for e in entries)
    assert sum(1 for e in entries if e["code"] == "TS102") == 1  # the line after "VI." is ignored


def test_guide_warns_when_credits_do_not_match_the_pdf_total():
    _, warnings = parse_guide(GUIDE.replace("Total      9", "Total     12"), CREDITS)
    assert any("add up to 9" in w and "says 12" in w for w in warnings)


def test_guide_warns_about_unknown_codes_and_repeated_courses():
    _, warnings = parse_guide(GUIDE, {"TS101": 3, "GERL101B1": 3, "GERL101B2": 3})
    assert any("TS102 is not in the plan's course list" in w for w in warnings)
    _, warnings = parse_guide(GUIDE, CREDITS)
    assert any("cybersecurity: TS101 appears in more than one semester" in w for w in warnings)


@pytest.mark.parametrize("message,expected", [
    ("what do I take in second year first semester", (2, "first")),
    ("year 2 semester 1 cybersecurity", (2, "first")),
    ("year 2 second semester", (2, "second")),
    ("first semester of year two", (2, "first")),
    ("fourth year", (4, None)),
    ("academic year 2026", (None, None)),
    ("when does the first semester start", (None, "first")),
])
def test_year_and_semester_are_read_from_the_question(message, expected):
    assert extract_year_semester(message) == expected


# ---------- the generated dataset ----------

@pytest.fixture(scope="module")
def plan():
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _semester_credits(plan, track, year, semester):
    hours = {c["code"]: c["hours"] for c in plan["courses"]}
    total, german = 0, False
    for e in plan["plan_entries"]:
        if (e["track"], e["year"], e["semester"]) != (track, year, semester):
            continue
        if e["code"] and e["code"].startswith("GERL"):
            if german:
                continue
            german = True
        total += e["credit_hours"]
        if e["code"]:
            assert e["credit_hours"] == hours[e["code"]]
    return total


def test_dataset_has_all_semesters_of_the_three_tracks(plan):
    parsed, problems = parse_academic_data(plan)
    assert problems == [] and len(parsed["plan_entries"]) == len(plan["plan_entries"]) == 162
    slots = {(e["track"], e["year"], e["semester"]) for e in plan["plan_entries"]}
    assert len(slots) == 24
    assert {t for t, _, _ in slots} == {"general", "data-science", "cybersecurity"}


def test_semester_credits_match_the_totals_printed_in_the_pdf(plan):
    printed = [(1, "first", 19), (1, "second", 20), (2, "first", 21), (2, "second", 21),
               (3, "first", 19), (3, "second", 21), (4, "first", 12), (4, "second", 12)]
    for track in ("cybersecurity", "general"):
        for year, semester, total in printed:
            assert _semester_credits(plan, track, year, semester) == total, (track, year, semester)


def test_known_placements(plan):
    where = {(e["track"], e["code"]): (e["year"], e["semester"]) for e in plan["plan_entries"] if e["code"]}
    assert where[("cybersecurity", "CS4713")] == (3, "first")
    assert where[("cybersecurity", "CS4714")] == (3, "second")
    assert where[("cybersecurity", "CS491")] == (4, "second")
    assert where[("general", "CS116")] == (1, "first")


# ---------- database + API (opt-in) ----------

URL = os.environ.get("WAJAHNI_TEST_DB_URL")
needs_db = pytest.mark.skipif(not URL, reason="set WAJAHNI_TEST_DB_URL to run against a real database")


@needs_db
def test_import_is_repeatable_and_removes_dropped_slots_only_of_listed_tracks(plan):
    from sqlalchemy import func, select

    from app.models.academic import PlanEntry
    from app.models.university import University
    from app.services.academic import import_academic_data
    from db_helpers import run_in_schema, scratch_schema

    async def total(db):
        return (await db.execute(select(func.count()).select_from(PlanEntry))).scalar_one()

    with scratch_schema(URL) as schema:
        async def run(db):
            uni = University(name="U", domain="u.edu")
            db.add(uni)
            await db.commit()
            first = await import_academic_data(db, uni.id, plan, source="plan", verified=False)
            assert first["plan_entries_created"] == 162 and first["problems"] == []
            again = await import_academic_data(db, uni.id, plan, source="plan", verified=False)
            assert again["plan_entries_created"] == again["plan_entries_updated"] == again["plan_entries_removed"] == 0
            smaller = copy.deepcopy(plan)
            smaller["plan_entries"] = [e for e in plan["plan_entries"] if e["track"] != "general" or e["year"] < 4]
            cut = await import_academic_data(db, uni.id, smaller, source="plan", verified=False)
            assert cut["plan_entries_removed"] == sum(
                1 for e in plan["plan_entries"] if e["track"] == "general" and e["year"] >= 4)
            only_cyber = copy.deepcopy(plan)
            only_cyber["plan_entries"] = [e for e in plan["plan_entries"] if e["track"] == "cybersecurity"]
            before = await total(db)
            await import_academic_data(db, uni.id, only_cyber, source="plan", verified=False)
            assert await total(db) == before  # a file that lists only one track never touches the others
            # verified rows survive an unverified file that drops them
            await import_academic_data(db, uni.id, plan, source="plan", verified=True)
            empty_cyber = copy.deepcopy(plan)
            empty_cyber["plan_entries"] = [e for e in plan["plan_entries"] if e["track"] == "cybersecurity"][:3]
            result = await import_academic_data(db, uni.id, empty_cyber, source="plan", verified=False)
            assert result["plan_entries_removed"] == 0 and result["skipped_already_verified"] > 0

        run_in_schema(URL, schema, run)


@pytest.fixture
def client(plan):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app
    from app.models.university import University
    from app.services.academic import import_academic_data
    from db_helpers import db_override, run_in_schema, scratch_schema

    with scratch_schema(URL) as schema:
        async def seed(db):
            uni = University(name="Example U", domain="example.edu")
            other = University(name="Other U", domain="other.edu")
            db.add_all([uni, other])
            await db.commit()
            result = await import_academic_data(db, uni.id, plan, source="plan test", verified=True)
            assert result["problems"] == []

        run_in_schema(URL, schema, seed)
        app.dependency_overrides[get_db] = db_override(URL, schema)
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.pop(get_db, None)


def ask(client, message, domain="example.edu"):
    return client.post(f"/api/v1/chat/{domain}", json={"message": message}).json()


@needs_db
def test_api_year_and_semester_for_a_track(client):
    body = ask(client, "What do I take in third year first semester in cybersecurity?")
    assert body["status"] == "answered" and body["data_verified"] is True
    assert "CS4713 Ethical Hacking" in body["answer"] and "19 credit hours" in body["answer"]
    assert "German course: GERL301B1 or GERL301B2" in body["answer"]
    assert body["sources"][0]["type"] == "plan"


@needs_db
def test_api_year_without_semester_shows_both_semesters(client):
    body = ask(client, "fourth year cybersecurity track")
    assert "first semester (12 credit hours)" in body["answer"] and "CS491" in body["answer"]
    assert "University Elective" not in body["answer"] and "elective course" in body["answer"].lower()


@needs_db
def test_api_asks_for_the_track_when_tracks_differ(client):
    body = ask(client, "what courses are in year 3 semester 1?")
    assert body["status"] == "needs_clarification" and "Cybersecurity" in body["answer"]


@needs_db
def test_api_year_one_is_shared_by_all_tracks(client):
    body = ask(client, "what do I take in the first year first semester?")
    assert body["status"] == "answered" and "all tracks" in body["answer"].lower()
    assert "CS116" in body["answer"]


@needs_db
def test_api_plan_is_tenant_scoped_and_calendar_questions_still_work(client):
    assert ask(client, "third year first semester cybersecurity", domain="other.edu")["status"] == "unsupported"
    for question in ("when does the first semester start", "when does the academic year 2026 start"):
        body = ask(client, question)  # no calendar data here: the plan must not hijack the question
        assert body["status"] == "unsupported" and not body["sources"]
