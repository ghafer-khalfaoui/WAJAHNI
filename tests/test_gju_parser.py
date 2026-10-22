"""Offline tests for the GJU directory parsers (synthetic fixtures with the real markup shape)."""
from pathlib import Path

from app.services.gju_parser import merge_people, parse_faculty_page, parse_staff_page

FIX = Path(__file__).parent / "fixtures"


def test_faculty_rows_are_parsed():
    people, seen = parse_faculty_page((FIX / "gju_faculty_sample.html").read_text(encoding="utf-8"))
    assert seen == 3 and len(people) == 2  # the row without an email is not importable
    first = people[0]
    assert first["name"] == "Dr. Test O'Neil-Al Sample"
    assert first["email"] == "test.person@example.edu"  # decoded, trimmed, lower-cased
    assert first["office_location"] == "Z 101" and first["phone"] == "+000 6 111 Ext. 4100"
    assert first["title"] == "Dean, Associate Professor, School of Testing (SOT)"


def test_empty_office_and_dangling_extension_become_none():
    people, _ = parse_faculty_page((FIX / "gju_faculty_sample.html").read_text(encoding="utf-8"))
    second = people[1]
    assert second["office_location"] is None
    assert second["phone"] == "+000 6 111"


def test_staff_rows_are_parsed():
    people, seen = parse_staff_page((FIX / "gju_staff_sample.html").read_text(encoding="utf-8"))
    assert seen == 2 and len(people) == 2
    assert people[0]["name"] == "Prof. Dr. Sample Dean" and people[0]["title"] == "Dean of Testing"
    assert people[0]["office_location"] == "Building K - 2nd Floor, Office 202"
    assert people[1]["title"] == "Director" and people[1]["email"] == "test.director@example.edu"


def test_unknown_markup_gives_no_rows_instead_of_guesses():
    assert parse_faculty_page("<html><body>nothing here</body></html>") == ([], 0)
    assert parse_staff_page("<html><body>nothing here</body></html>") == ([], 0)


def test_merge_keeps_first_entry_per_email():
    a = [{"name": "A", "email": "x@e.edu"}]
    b = [{"name": "B", "email": "x@e.edu"}, {"name": "C", "email": "y@e.edu"}]
    assert [p["name"] for p in merge_people(a, b)] == ["A", "C"]
