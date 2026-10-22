"""Parse the public GJU faculty and staff directory pages (saved HTML) into import-ready rows.

Pure functions, no network. The markup was inspected on 2026-10-22; if GJU changes its site the
parsers return fewer rows and `summarize` reports it, instead of guessing.
"""
from __future__ import annotations

import html
import re
from urllib.parse import unquote

TAG_RE = re.compile(r"<[^>]+>")
MAILTO_RE = re.compile(r"""href=['"]mailto:([^'"]+)['"]""", re.I)


def _text(fragment: str | None) -> str:
    if not fragment:
        return ""
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", fragment))).strip()


def _email(block: str) -> str | None:
    match = MAILTO_RE.search(block)
    if not match:
        return None
    address = unquote(match.group(1)).split("?")[0].strip().lower()
    return address if "@" in address else None


def _phone(value: str) -> str | None:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s*Ext\.?\s*$", "", value, flags=re.I).strip()  # "…4294444 Ext." with no number
    return value or None


def _field(block: str, css_class: str) -> str:
    """Text of <div class="css_class">…</div> without the bold label (OFFICE:, TELEPHONE:)."""
    match = re.search(rf'<div class="{css_class}"[^>]*>(.*?)</div>', block, re.S)
    if not match:
        return ""
    inner = re.sub(r'<span class="prof-bold">.*?</span>', "", match.group(1), flags=re.S)
    return _text(inner)


def _person(name: str, title: str | None, office: str, phone: str, email: str | None) -> dict | None:
    if not name or not email:
        return None
    return {
        "name": name,
        "title": title or None,
        "office_location": office or None,
        "phone": _phone(phone),
        "email": email,
    }


def parse_faculty_page(page: str) -> tuple[list[dict], int]:
    """Returns (people with an email, number of listing rows seen)."""
    rows = re.split(r'<div class="views-row views-row-\d+', page)[1:]
    people, seen = [], 0
    for row in rows:
        if "faculty-info" not in row:
            continue
        seen += 1
        name = _text((re.search(r'views-field-title-field-et.*?<a [^>]*>(.*?)</a>', row, re.S) or [None, ""])[1])
        job = _field(row, "faculty-job")
        school = _text((re.search(r'<div class="faculty-school">(.*?)</div>', row, re.S) or [None, ""])[1])
        title = ", ".join(part for part in (job, school) if part)
        person = _person(name, title, _field(row, "faculty-office"), _field(row, "faculty-telphone"), _email(row))
        if person:
            people.append(person)
    return people, seen


def parse_staff_page(page: str) -> tuple[list[dict], int]:
    rows = re.split(r'<tr class="(?:odd|even)[^"]*">', page)[1:]
    people, seen = [], 0
    for row in rows:
        if "staff-title" not in row:
            continue
        seen += 1
        match = re.search(r'<span class="staff-title">(.*?)<span class="staff-job">(.*?)</span>', row, re.S)
        if not match:
            continue
        name = _text(match.group(1))
        job = _text(match.group(2)).lstrip("|").strip()
        person = _person(name, job, _field(row, "staff-office"), _field(row, "staff-tel"), _email(row))
        if person:
            people.append(person)
    return people, seen


def merge_people(*groups: list[dict]) -> list[dict]:
    """Merge lists, keeping the first entry per email (faculty pages are passed first)."""
    merged: dict[str, dict] = {}
    for group in groups:
        for person in group:
            merged.setdefault(person["email"], person)
    return list(merged.values())
