"""Study-plan parsing, the generated dataset, prerequisite wording and track answers."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.academic import parse_academic_data
from app.services.chat_router import detect_track, format_prerequisites
from app.services.plan_parser import (
    build_plan, parse_course_blocks, parse_memberships, parse_prereq_text,
)

DATASET = Path(__file__).parent.parent / "datasets" / "gju" / "cs_study_plan_2023_2024.json"

# ---------- parser logic on a small synthetic document with the same layout ----------

SYNTHETIC = """\
3.1.A. Common Compulsory Courses (6 credit hours):
  Course ID               Course Name                 Credit   ECTS   Lect. Prac.  Type  Prerequisites
TS201          Algorithms                              3              3       -     F2F   TS101, TS102co
TS301          Capstone                                3              3       -     F2F   Dept. Approval
3.1.D. Special Compulsory Courses for the Cybersecurity Track (3 credit hours):
TS410          Secure Systems                          3              3       -     F2F   TS201 c o
Study Plan Guide for a B.Sc. Degree in Testing
"""
SYNTHETIC_BLOCKS = """\
TS201: Algorithms                                   3 Cr Hr (3,0)           - ECTS
Some description.

                                           Prerequisites: TS101, TS102co


TS301: Capstone                                     3 Cr Hr (3,0)           - ECTS
Description.
                                                       Prerequisites: Dept. Approval
\x0cTS410: Secure Systems And A Very Long Name That
                                                    3 Cr Hr (3,0) - ECTS
Wrapping
Text.
                                           Prerequisites: TS201 c o
"""


def test_prerequisite_text_covers_corequisites_alternatives_and_conditions():
    rows, conditions = parse_prereq_text("CS116, CS1160co, GERL102B1 or GERL102B2, MATH 101, Placement test, BSC001")
    assert [(r["code"], r["corequisite"], r["alt_group"]) for r in rows] == [
        ("CS116", False, None), ("CS1160", True, None),
        ("GERL102B1", False, 1), ("GERL102B2", False, 1), ("MATH101", False, None),
    ]
    assert conditions == ["Placement test", "BSC001"]  # not courses: kept as plain-text conditions


def test_bsc001_is_a_condition_not_a_course_row():
    rows, conditions = parse_prereq_text("BSC001")
    assert rows == [] and conditions == ["BSC001"]


def test_split_co_artefact_is_joined():
    rows, _ = parse_prereq_text("CE352 c o")
    assert [(r["code"], r["corequisite"]) for r in rows] == [("CE352", True)]


def test_dash_means_no_prerequisite():
    assert parse_prereq_text("-") == ([], [])


def test_blocks_handle_form_feed_and_wrapped_names():
    blocks = parse_course_blocks(SYNTHETIC_BLOCKS)
    assert set(blocks) == {"TS201", "TS301", "TS410"}
    assert blocks["TS201"]["credit_hours"] == 3 and blocks["TS201"]["prereq_text"] == "TS101, TS102co"
    assert blocks["TS301"]["prereq_text"] == "Dept. Approval"
    assert blocks["TS410"]["name"].startswith("Secure Systems And A Very Long Name")


def test_memberships_follow_the_section_headings():
    groups = parse_memberships(SYNTHETIC)
    assert groups == {"program-common": ["TS201", "TS301"], "track-cybersecurity": ["TS410"]}


def test_build_plan_reports_missing_blocks_instead_of_guessing():
    plan = build_plan(SYNTHETIC + SYNTHETIC_BLOCKS)
    assert {c["code"] for c in plan["courses"]} == {"TS201", "TS301", "TS410"}
    # TS101 and TS102 are not courses of this tiny plan: reported, not invented
    assert any("TS101" in w for w in plan["warnings"])
    capstone = next(c for c in plan["courses"] if c["code"] == "TS301")
    assert capstone["prerequisite_note"] == "Dept. Approval"


# ---------- the real, generated dataset ----------

@pytest.fixture(scope="module")
def plan():
    return json.loads(DATASET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_code(plan):
    return {c["code"]: c for c in plan["courses"]}


def test_dataset_is_accepted_by_the_importer_parser(plan):
    parsed, problems = parse_academic_data(plan)
    assert problems == []
    assert len(parsed["courses"]) == len(plan["courses"]) == 103
    assert parsed["replace_prerequisites"] is True
    assert len(parsed["prerequisites"]) == len(plan["prerequisites"]) == 106


def _credits(by_code, group):
    """Credit hours of one table, counting each alternative (B2 tracks, NEE101) once."""
    return sum(
        c["hours"] for c in by_code.values()
        if group in c["plan_groups"] and not c["code"].endswith("B2") and c["code"] != "NEE101"
    )


@pytest.mark.parametrize("group,printed_total", [
    ("remedial", 12), ("university-compulsory", 21), ("school", 27), ("program-common", 67),
    ("track-general", 12), ("track-data-science", 12), ("track-cybersecurity", 12),
])
def test_credit_hours_match_the_totals_printed_in_the_pdf(by_code, group, printed_total):
    assert _credits(by_code, group) == printed_total


def test_cybersecurity_track_courses(by_code):
    names = {c: by_code[c]["name"] for c in by_code if "track-cybersecurity" in by_code[c]["plan_groups"]}
    assert names == {
        "CE354": "Computer Security", "CS470": "Cryptography",
        "CS4713": "Ethical Hacking", "CS4714": "Digital Forensics",
    }


def test_every_prerequisite_refers_to_a_course_of_the_plan(plan, by_code):
    for row in plan["prerequisites"]:
        assert row["course"] in by_code and row["prereq"] in by_code, row
        assert row["course"] != row["prereq"]


def test_known_prerequisites_read_from_the_tables(plan):
    def reqs(code):
        return {(p["prereq"], p["corequisite"], p["alt_group"]) for p in plan["prerequisites"] if p["course"] == code}

    assert reqs("CS4714") == {("CE352", False, None)}
    assert reqs("CS470") == {("CS222", False, None)}
    assert reqs("CS222") == {(c, False, None) for c in ("CS116", "CS201", "ARB0099", "ENGL0099", "MATH0099")}
    assert reqs("EE570") == {("CE352", True, None)}
    assert reqs("GERL201B1") == {("GERL102B1", False, 1), ("GERL102B2", False, 1)}
    assert reqs("GERL201B2") == {("GERL102B2", False, None)}
    assert reqs("CS264") >= {("CS117", False, None), ("CS263", False, None), ("MATH0099", False, None)}


def test_notes_for_conditions_that_are_not_courses(by_code):
    assert by_code["CS391"]["prerequisite_note"] == "Dept. Approval"
    assert by_code["MATH0099"]["prerequisite_note"] == "Placement test"
    assert by_code["CS4714"]["prerequisite_note"] is None


def test_wrapped_course_names_are_complete(by_code):
    assert by_code["CS4811"]["name"] == "Special Topics in Data Science Technologies and Applications"


# ---------- wording of answers ----------

def course(code, name, note=None):
    return SimpleNamespace(code=code, name=name, prerequisite_note=note)


def test_format_lists_required_alternatives_and_corequisites():
    target = course("CS117", "OOP", note="Placement test")
    details = [
        (course("CS116", "Fundamentals"), False, None),
        (course("GA", "German A"), False, 1),
        (course("GB", "German B"), False, 1),
        (course("CS1160", "Lab"), True, None),
    ]
    text = format_prerequisites(target, details)
    assert "CS116 (Fundamentals)" in text and "either GA (German A) or GB (German B)" in text
    assert "Corequisite (can be taken at the same time): CS1160 (Lab)" in text
    assert "Other conditions listed: Placement test" in text


def test_format_without_requirements():
    assert format_prerequisites(course("X1", "Nothing"), []) == "X1 (Nothing) has no prerequisites listed in my data."
    assert "no prerequisite courses" in format_prerequisites(course("X2", "Gate", "Dept. Approval"), [])


def test_detect_track():
    assert detect_track({"cybersecurity", "track"}) == "cybersecurity"
    assert detect_track({"data", "science", "track"}) == "data-science"
    assert detect_track({"general"}) == "general"
    assert detect_track({"track"}) is None


# ---------- database + API (opt-in) ----------

URL = os.environ.get("WAJAHNI_TEST_DB_URL")
needs_db = pytest.mark.skipif(not URL, reason="set WAJAHNI_TEST_DB_URL to run against a real database")


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
            db.add(uni)
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


def ask(client, message):
    return client.post("/api/v1/chat/example.edu", json={"message": message}).json()


@needs_db
def test_api_cybersecurity_track(client):
    body = ask(client, "What courses are in the cybersecurity track?")
    assert body["status"] == "answered" and body["data_verified"] is True
    for fragment in ("CE354", "CS470", "CS4713 Ethical Hacking", "CS4714 Digital Forensics", "12 credit hours"):
        assert fragment in body["answer"]
    assert "CS333" not in body["answer"]  # an elective of the general track


@needs_db
def test_api_electives_and_unknown_track(client):
    body = ask(client, "cybersecurity track electives")
    assert "CS370 Web Security" in body["answer"] and "CE354" not in body["answer"]
    assert ask(client, "which courses are in the track?")["status"] == "needs_clarification"


@needs_db
def test_api_prerequisites_with_alternatives_and_corequisites(client):
    german = ask(client, "prerequisites of GERL201B1")["answer"]
    assert "either GERL102B1" in german and " or GERL102B2" in german
    lab = ask(client, "prerequisites of CS1170")["answer"]
    assert "CS116" in lab and "Corequisite (can be taken at the same time)" in lab and "CS117" in lab
    remedial = ask(client, "prerequisite of MATH0099")["answer"]
    assert "Placement test" in remedial


@needs_db
def test_api_forensics_chain_does_not_follow_corequisites(client):
    chain = ask(client, "full chain of prerequisites for CS4714")["answer"]
    for code in ("CE352", "CE201", "CE212", "CS116", "MATH0099"):
        assert code in chain
    assert "CS1160" not in chain  # only a corequisite of CS116, not a prerequisite


@needs_db
def test_replace_removes_old_pairs_but_never_from_verified_rows():
    from sqlalchemy import select

    from app.models.academic import CoursePrerequisite
    from app.models.university import University
    from app.services.academic import import_academic_data
    from db_helpers import run_in_schema, scratch_schema

    base = {"courses": [{"code": "AA101", "name": "A", "hours": 3}, {"code": "BB101", "name": "B", "hours": 3},
                        {"code": "CC101", "name": "C", "hours": 3}],
            "prerequisites": [{"course": "CC101", "prereq": "AA101"}]}
    newer = {**base, "replace_prerequisites": True, "prerequisites": [{"course": "CC101", "prereq": "BB101"}]}

    async def count(db, uni_id):
        rows = (await db.execute(select(CoursePrerequisite).where(CoursePrerequisite.university_id == uni_id))).scalars()
        return sorted((r.prerequisite_id for r in rows))

    with scratch_schema(URL) as schema:
        async def run(db):
            uni = University(name="U", domain="u.edu")
            db.add(uni)
            await db.commit()
            await import_academic_data(db, uni.id, base, source="old", verified=False)
            first = await import_academic_data(db, uni.id, newer, source="official", verified=False)
            assert first["prerequisites_created"] == 1 and first["prerequisites_removed"] == 1
            assert len(await count(db, uni.id)) == 1
            # now verified: an unverified replace must not touch the verified pair
            await import_academic_data(db, uni.id, newer, source="official", verified=True)
            again = await import_academic_data(
                db, uni.id, {**base, "replace_prerequisites": True, "prerequisites": []}, source="x", verified=False
            )
            assert again["prerequisites_removed"] == 0 and again["skipped_already_verified"] >= 1
            assert len(await count(db, uni.id)) == 1

        run_in_schema(URL, schema, run)
