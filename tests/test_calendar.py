"""Tests for the calendar data file and the calendar question matcher (offline, no database)."""
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.academic import parse_academic_data
from app.services.calendar_answers import describe_event, select_events

DATA_FILE = Path(__file__).parent.parent / "datasets" / "gju" / "calendar_2026_2027.json"
TODAY = dt.date(2026, 10, 23)


def load_events():
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    parsed, problems = parse_academic_data({"events": raw["events"]})
    assert problems == []
    return [
        SimpleNamespace(semester=e["semester"], start_date=e["start_date"], end_date=e["end_date"],
                        title=e["title"], source="test", verified=False)
        for e in parsed["events"]
    ]


EVENTS = load_events()


def ask(message, today=TODAY):
    shown, more, past = select_events(message, EVENTS, today)
    return [(e.title, e.start_date.isoformat()) for e in shown], more, past


def test_calendar_file_is_complete_and_valid():
    assert len(EVENTS) == 84
    assert {e.semester for e in EVENTS} == {"first", "second", "summer"}
    assert all(e.end_date >= e.start_date for e in EVENTS)


def test_weekdays_in_the_pdf_match_the_dates():
    """The PDF prints a weekday next to every date. A typo in a date would break this."""
    rows = [l.split("|") for l in Path(__file__).with_name("fixtures").joinpath("gju_calendar_weekdays.txt")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    by_key = {(e.semester, e.start_date.isoformat(), e.title): e for e in EVENTS}
    assert len(rows) == len(by_key) == 84
    for semester, start, end, first_day, last_day, title in rows:
        event = by_key[(semester, start, title)]
        assert event.start_date.strftime("%a") == first_day, title
        assert event.end_date.isoformat() == end and event.end_date.strftime("%a") == last_day, title


def test_next_midterm_is_the_november_one():
    shown, more, past = ask("When are the midterm exams?")
    assert shown[0] == ("Midterm exams", "2026-11-21") and not past


def test_final_exams_prefers_the_exact_title():
    shown, _, _ = ask("when are final exams")
    assert shown[0] == ("Final exams", "2027-01-16")


def test_withdraw_deadline_and_semester_filter():
    assert ask("last day to withdraw courses")[0][0] == ("Last day to withdraw courses", "2027-01-07")
    assert ask("last day to withdraw in the second semester")[0][0] == ("Last day to withdraw courses", "2027-06-03")
    assert ask("when do I register for the summer semester")[0][0][1] == "2027-06-25"


def test_registration_prefers_online_registration():
    shown, _, _ = ask("when is registration")
    assert shown[0][0] == "Online registration"


def test_classes_start_and_add_drop():
    assert ask("when do classes start in the second semester")[0][0] == ("First day of classes", "2027-02-21")
    assert ask("add and drop period")[0][0][0] == "Add & drop"


def test_holidays_include_eids_and_christmas():
    titles = [t for t, _ in ask("when is the next holiday")[0]]
    assert titles[0] == "Christmas holiday"
    assert any("Eid" in t for t, _ in ask("when is eid")[0])


def test_past_event_is_reported_as_past():
    shown, _, past = ask("when is the first day of classes", today=dt.date(2027, 8, 1))
    assert past is True and shown == [("First day of classes", "2027-07-11")]
    shown, _, past = ask("when is the first day of classes", today=TODAY)
    assert past is False and shown[0] == ("First day of classes", "2027-02-21")  # 4 Oct 2026 has already passed


@pytest.mark.parametrize("message", ["what is the capital of france", "hello", "who is the president of gju", "tell me a joke"])
def test_unrelated_questions_match_nothing(message):
    assert ask(message)[0] == []


def test_generic_upcoming_question_lists_next_entries():
    shown, more, _ = ask("what are the upcoming deadlines")
    assert shown and shown[0][1] >= TODAY.isoformat() and more > 0


def test_description_shows_range_and_weekday():
    event = next(e for e in EVENTS if e.title == "Midterm exams" and e.semester == "first")
    assert describe_event(event) == "Midterm exams (first semester): Sat 21 Nov 2026 to Sat 28 Nov 2026"
