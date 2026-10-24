"""Parse a GJU study-plan PDF (text from `pdftotext -layout`) into courses and prerequisites.

Pure functions, no network or database. Two parts of the same document are used:
  * the requirement tables decide WHICH courses belong to the plan and to which group
    (university, school, program, track, elective);
  * the course blocks near the end give each course's name, credit hours and prerequisite line.
`build_plan` returns the data plus a list of warnings so a person can review anything odd
instead of the parser guessing.
"""
from __future__ import annotations

import re

CODE = r"[A-Z]{2,6}\d{2,4}[A-Z0-9]*"
CODE_RE = re.compile(rf"\b({CODE})(co)?\b")
BLOCK_START_RE = re.compile(rf"^[\s\x0c]{{0,6}}({CODE}):\s+(\S.*)$")
CREDITS_RE = re.compile(r"(\d+)\s+Cr Hr")
ROW_RE = re.compile(rf"^[\s\x0c]*({CODE})\s{{2,}}\S")
PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*$")

# Headings of the requirement tables, in document order -> group names stored on each course.
GROUP_HEADINGS = [
    (re.compile(r"^\s*III\.\s+Admission Requirements"), "remedial"),
    (re.compile(r"^\s*1\.1\.\s+Compulsory"), "university-compulsory"),
    (re.compile(r"^\s*1\.2\.\s+Elective"), "university-elective"),
    (re.compile(r"^\s*2\.\s+School Requirements"), "school"),
    (re.compile(r"^\s*3\.1\.A\."), "program-common"),
    (re.compile(r"^\s*3\.1\.B\."), "track-general"),
    (re.compile(r"^\s*3\.1\.C\."), "track-data-science"),
    (re.compile(r"^\s*3\.1\.D\."), "track-cybersecurity"),
    (re.compile(r"^\s*3\.2\.A\."), "elective-general"),
    (re.compile(r"^\s*3\.2\.B\."), "elective-data-science"),
    (re.compile(r"^\s*3\.2\.C\."), "elective-cybersecurity"),
]
TABLES_END_RE = re.compile(r"Study Plan\w* Guide for a B\.Sc\.")
# Appears in the prerequisite column but is not a course: kept as a plain-text condition.
NON_COURSE_CODES = {"BSC001"}

# Courses that have a row in the requirement tables but no course block. Values were read from
# the 2023-2024 plan tables: (name, credit hours, prerequisite text).
TABLE_ONLY_COURSES = {
    "MATH0099": ("Pre-Math", 3, "Placement test"),
    "CS354": ("Computer and Networks Security", 3, "BSC001"),
    "EI101": ("Leadership and Emotional Intelligence", 3, "ENGL0098"),
    "GERL302B1": ("German VI B1-Track", 3, "GERL301B1 or GERL301B2"),
    "NEE101": ("National Education in English", 3, "ARB0099, ENGL0099"),
    "PE101": ("Sports and Health", 3, "ARB0099"),
    "TW303": ("Technical and Workplace Writing", 3, "ENGL0098"),
}

# The requirement tables are richer than the course blocks for these courses (the blocks list one
# German track only, or leave out the remedial courses). Read from the 2023-2024 plan tables.
PREREQ_OVERRIDES = {
    "GERL102B1": "GERL101B1",
    "GERL102B2": "GERL101B1",
    "GERL201B1": "GERL102B1 or GERL102B2",
    "GERL201B2": "GERL102B2",
    "GERL202B1": "GERL201B1 or GERL201B2",
    "GERL202B2": "GERL201B2",
    "GERL301B1": "GERL202B1 or GERL202B2",
    "GERL301B2": "GERL202B2",
    "GERL302B1": "GERL301B1 or GERL301B2",
    "GERL302B2": "GERL301B2",
    "CS264": "CS117, CS263, ARB0099, ENGL0099, MATH0099",
}


def parse_prereq_text(text: str) -> tuple[list[dict], list[str]]:
    """'CS116, CS1160co, GERL102B1 or GERL102B2' -> rows plus plain-text conditions.

    Each row: {"code", "corequisite", "alt_group"}. Codes joined with "or" share an alt_group
    number (any ONE of them satisfies the requirement); everything else is required.
    """
    text = re.sub(r"(?<=\d)\s+c\s*o\b", "co", text)  # PDF artefact: "CE352 c o" means "CE352co"
    text = re.sub(r"\b([A-Z]{2,6})\s+(\d{2,4})\b", r"\1\2", text)  # "MATH 101" -> "MATH101"
    rows: list[dict] = []
    conditions: list[str] = []
    next_group = 1
    for item in (part.strip() for part in text.split(",")):
        if not item or item == "-":
            continue
        pieces = [p.strip() for p in re.split(r"\s+or\s+", item)]
        codes = [m for p in pieces for m in CODE_RE.finditer(p) if m.group(1) not in NON_COURSE_CODES]
        if not codes:
            conditions.append(item)
            continue
        group = None
        if len(codes) > 1:
            group, next_group = next_group, next_group + 1
        for match in codes:
            rows.append({"code": match.group(1), "corequisite": bool(match.group(2)), "alt_group": group})
    return rows, conditions


def parse_course_blocks(text: str) -> dict[str, dict]:
    """Course blocks near the end of the document: name, credit hours, prerequisite text."""
    lines = text.split("\n")
    starts = []
    for i, line in enumerate(lines):
        match = BLOCK_START_RE.match(line)
        if match and (CREDITS_RE.search(line) or CREDITS_RE.search(" ".join(lines[i + 1:i + 3]))):
            starts.append(i)
    blocks: dict[str, dict] = {}
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = lines[i:end]
        match = BLOCK_START_RE.match(body[0])
        code = match.group(1)
        header_rest = match.group(2)
        credit_line = 0
        if not CREDITS_RE.search(header_rest):  # name wraps; credits sit on a later line
            credit_line = 1 if CREDITS_RE.search(body[1]) else 2
            header_rest += " " + re.sub(r"\s*\d+\s*$", "", body[credit_line].split("Cr Hr")[0])
            tail = body[credit_line + 1].strip() if credit_line + 1 < len(body) else ""
            if tail and len(tail) < 40 and not tail.endswith("."):
                header_rest += " " + tail
        name_part = re.split(r"\s{2,}\d+\s+Cr Hr|\s+\d+\s+Cr Hr", header_rest)[0]
        name = re.sub(r"\s+", " ", name_part).strip(" :")
        credits = CREDITS_RE.search(" ".join(body[:4]))
        prereq_at = [k for k, l in enumerate(body) if "Prerequisites:" in l]
        prereq_text = ""
        if prereq_at:
            k = prereq_at[-1]
            parts = [body[k].split("Prerequisites:", 1)[1].strip()]
            for extra in body[k + 1:]:
                stripped = extra.strip()
                if not stripped or PAGE_NUMBER_RE.match(extra) or re.match(r"^[IVX]+\.\s", stripped):
                    break
                parts.append(stripped)
            prereq_text = " ".join(p for p in parts if p)
        blocks.setdefault(code, {
            "name": name,
            "credit_hours": int(credits.group(1)) if credits else None,
            "prereq_text": prereq_text,
            "has_prereq_line": bool(prereq_at),
        })
    return blocks


def parse_memberships(text: str) -> dict[str, list[str]]:
    """Which course codes appear in which requirement table (document order, no repeats)."""
    groups: dict[str, list[str]] = {}
    current = None
    for line in text.split("\n"):
        if TABLES_END_RE.search(line):
            break
        for pattern, name in GROUP_HEADINGS:
            if pattern.match(line):
                current = name
                groups.setdefault(name, [])
                break
        if current is None:
            continue
        match = ROW_RE.match(line)
        if match and match.group(1) not in groups[current]:
            groups[current].append(match.group(1))
    return groups


def build_plan(text: str) -> dict:
    blocks = parse_course_blocks(text)
    memberships = parse_memberships(text)
    warnings: list[str] = []
    plan_groups: dict[str, list[str]] = {}
    for group, codes in memberships.items():
        for code in codes:
            plan_groups.setdefault(code, []).append(group)

    details: dict[str, tuple[str, int, str]] = {}
    for code in sorted(plan_groups):
        block = blocks.get(code)
        if block is not None and block["credit_hours"] is not None:
            details[code] = (block["name"], block["credit_hours"], block["prereq_text"])
            if not block["has_prereq_line"]:
                warnings.append(f"{code}: no 'Prerequisites:' line found")
        elif code in TABLE_ONLY_COURSES:
            details[code] = TABLE_ONLY_COURSES[code]
        else:
            warnings.append(f"{code}: listed in the requirement tables but no course block found")

    courses, prerequisites = [], []
    known = set(details)
    for code in sorted(details):
        name, credits, prereq_text = details[code]
        prereq_text = PREREQ_OVERRIDES.get(code, prereq_text)
        rows, conditions = parse_prereq_text(prereq_text)
        for row in rows:
            if row["code"] not in known:
                warnings.append(f"{code}: prerequisite {row['code']} is not a course of this plan, skipped")
                continue
            prerequisites.append({"course": code, "prereq": row["code"],
                                  "corequisite": row["corequisite"], "alt_group": row["alt_group"]})
        courses.append({
            "code": code, "name": name, "credit_hours": credits,
            "plan_groups": plan_groups[code],
            "prerequisite_note": "; ".join(conditions) or None,
        })
    return {"courses": courses, "prerequisites": prerequisites, "warnings": warnings,
            "blocks_not_in_plan": sorted(set(blocks) - known), "memberships": memberships}


# ---------------------------------------------------------------------------------------------
# "Study Plan Guide" tables: which course sits in which year and semester of each track.
# ---------------------------------------------------------------------------------------------
TRACK_HEADING_RE = re.compile(r"^\s*[A-C]\.\s+Study Plan Guide for the (General|Data Science|Cybersecurity) Track")
YEAR_RE = re.compile(r"^\s*(First|Second|Third|Fourth|Fifth) Year\s*$")
SEMESTER_RE = re.compile(r"^\s*(First|Second|Summer) Semester\s*$")
PLACEHOLDER_RE = re.compile(r"^\s*(University Elective|elective course)\s+(\d+)\s*$", re.IGNORECASE)
TOTAL_RE = re.compile(r"^\s*Total\s+(\d+)")
GUIDE_END_RE = re.compile(r"^\s*[IVX]+\.\s+\S")
YEAR_NUMBERS = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5}
TRACK_NAMES = {"General": "general", "Data Science": "data-science", "Cybersecurity": "cybersecurity"}


def parse_guide(text: str, credits_by_code: dict[str, int]) -> tuple[list[dict], list[str]]:
    """Read the year/semester tables of every track.

    Returns (entries, warnings). Each entry: track, year, semester, position, code (or None),
    label (text for elective placeholders, else None), credit_hours. Credit hours of real courses come
    from `credits_by_code` (the course data), not from the table row, because wrapped rows are unreliable.
    German courses are listed as two alternatives (B1/B2 track) that fill ONE slot, so they count once
    in the semester total. Every semester's credit sum is compared with the PDF's own "Total" line.
    """
    entries: list[dict] = []
    warnings: list[str] = []
    started = False
    track = year = semester = None
    position = 0
    credit_sum = 0
    german_counted = False
    seen_in_track: dict[tuple[str, str], str] = {}

    def check_total(total: int) -> None:
        if (track, year, semester) != (None, None, None) and credit_sum != total:
            warnings.append(f"{track} year {year} {semester}: credits add up to {credit_sum}, the PDF says {total}")

    for line in text.split("\n"):
        if TABLES_END_RE.search(line):
            started = True
            continue
        if not started:
            continue
        if GUIDE_END_RE.match(line) and track is not None:
            break
        m = TRACK_HEADING_RE.match(line)
        if m:
            track, year, semester = TRACK_NAMES[m.group(1)], None, None
            continue
        m = YEAR_RE.match(line)
        if m:
            year = YEAR_NUMBERS[m.group(1)]
            continue
        m = SEMESTER_RE.match(line)
        if m:
            semester = m.group(1).lower()
            position, credit_sum, german_counted = 0, 0, False
            continue
        if track is None or year is None or semester is None:
            continue
        m = TOTAL_RE.match(line)
        if m:
            check_total(int(m.group(1)))
            continue
        m = PLACEHOLDER_RE.match(line)
        if m:
            position += 1
            credit_sum += int(m.group(2))
            entries.append({"track": track, "year": year, "semester": semester, "position": position,
                            "code": None, "label": m.group(1).title() if m.group(1).islower() else m.group(1),
                            "credit_hours": int(m.group(2))})
            continue
        m = ROW_RE.match(line)
        if m:
            code = m.group(1)
            if code not in credits_by_code:
                warnings.append(f"{track} year {year} {semester}: {code} is not in the plan's course list")
                continue
            hours = credits_by_code[code]
            if code.startswith("GERL"):
                if german_counted:  # second alternative of the same German slot
                    hours_for_sum = 0
                else:
                    hours_for_sum, german_counted = hours, True
            else:
                hours_for_sum = hours
            position += 1
            credit_sum += hours_for_sum
            key = (track, code)
            if key in seen_in_track:
                warnings.append(f"{track}: {code} appears in more than one semester ({seen_in_track[key]} and "
                                f"year {year} {semester}); both kept, check the PDF")
            seen_in_track.setdefault(key, f"year {year} {semester}")
            entries.append({"track": track, "year": year, "semester": semester, "position": position,
                            "code": code, "label": None, "credit_hours": hours})
    return entries, warnings
