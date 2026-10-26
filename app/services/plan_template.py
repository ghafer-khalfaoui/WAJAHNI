"""Parse a GJU undergraduate study-plan PDF that follows the common GJU template.

The PDFs contain ruled tables, so rows are read from table CELLS (code, name, credit hours, type,
prerequisites) instead of guessing from text layout. Two layers:

  * `extract_items(pdf_path)` (needs `pip install pdfplumber`, dev-time only) turns a PDF into a flat,
    page-ordered list of items: ("text", "line") and ("table", [[cell, ...], ...]).
  * `parse_items(items)` is pure Python on that list (no PDF, no network, no database) and is what the
    tests exercise with small synthetic inputs.

Nothing is guessed silently: every cross-check that fails (credits vs the PDF's own Total line,
duplicates, unknown prerequisites) becomes a warning that a person must read.
"""
from __future__ import annotations

import difflib
import re
from collections import defaultdict

from app.services.plan_parser import parse_prereq_text

CODE_RE = re.compile(r"^[A-Z]{2,6}\s?\d{2,4}[A-Z0-9]*$")
FRAMEWORK_RE = re.compile(r"Framework for B\.\s?(?:Sc|A)", re.IGNORECASE)
ADMISSION_RE = re.compile(r"^\s*[IVX]+\.\s+Admission Requirements", re.IGNORECASE)
GUIDE_HEADING_RE = re.compile(r"^\s*(?:[IVX]+\.|[A-C]\.)?\s*Study\s+Plan\w*(?:\s+c)?\s+Guide\s+for\b", re.IGNORECASE)
COURSES_SECTION_RE = re.compile(
    r"^\s*[IVX]+\.\s+(?:Compulsory Courses Offered|Program and School Compulsory Courses|Compulsory Courses)",
    re.IGNORECASE)
HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*(?:\.[A-Z])?\.?)\s+(\S.*)$")
YEAR_RE = re.compile(r"^\s*(First|Second|Third|Fourth|Fifth|Sixth) Year\s*$")
SEMESTER_RE = re.compile(r"^\s*(First|Second|Summer) Semester\s*$")
TRACK_LINE_RE = re.compile(r"^\s*\(([^()]*?)\s+Tracks?\)\s*$", re.IGNORECASE)
TRACK_FOR_RE = re.compile(r"Guide for (?:the )?(.+?) Track", re.IGNORECASE)
NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
TYPE_CELLS = {"F2F", "BLD", "OL"}
YEARS = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5, "Sixth": 6}
GERMAN_PAIR_RE = re.compile(r"^(GERL\d{3})B[12]$")
# Typos found in the official PDFs' prerequisite cells -> the real course code. Reported, never silent.
CODE_TYPOS = {"ARB099": "ARB0099", "ARAB099": "ARB0099", "ARB00992": "ARB0099", "ENGL099": "ENGL0099",
              "MATH099": "MATH0099"}
SUMMARY_LABELS = {"university requirements": "university", "school requirements": "school",
                  "program requirements": "program"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def squash(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_title(text: str) -> str:
    text = re.sub(r"\(\s*\d+\s+credit\s+hours?\s*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\s*(?:two|three|one)\s+courses[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[a-z])[a-d](?=\s*\)|\s*:)", "", text)  # footnote letter glued on: "Electivesb"
    text = squash(text).strip(" :")
    return text.replace("( ", "(").replace(" )", ")").strip(" :")


def track_of(title: str) -> str | None:
    """'Program Requirements (General Track Compulsory)' -> 'general'; 'Compulsory for Track 1: X' -> 'x'."""
    m = re.search(r"Tracks?\s*\d*\s*:\s*([^):]+)", title, re.IGNORECASE)
    if m:
        return slug(m.group(1)) or None
    m = re.search(r"(?:\(|for the |for )\s*([A-Za-z][A-Za-z &/]*?)\s+Track\b", title, re.IGNORECASE)
    if m:
        name = re.sub(r"\b(Special|Compulsory|Electives?|Courses|for|the)\b", "", m.group(1), flags=re.IGNORECASE)
        return slug(name) or None
    return None


def normalize_prereq_text(text: str) -> str:
    """'ACC1002 & ENGL0099 ARB0099', 'A OR B' -> 'ACC1002, ENGL0099, ARB0099', 'A or B'."""
    text = squash(text)
    text = re.sub(r"\b([A-Z]{2,6})\s+(\d{2,4})\b", r"\1\2", text)
    text = re.sub(r"(?<=\d)\s+c\s*o\b", "co", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)Co\b", "co", text)
    text = re.sub(r"\s*&\s*|\s+and\s+|\s*;\s*", ", ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+OR\s+", " or ", text)
    code = r"[A-Z]{2,6}\d{2,4}[A-Z0-9]*"
    previous = None
    while previous != text:  # two codes only separated by a space -> comma
        previous = text
        text = re.sub(rf"\b({code}(?:co)?)\s+(?=[A-Z]{{2,6}}\d{{2,4}})", r"\1, ", text)
    return text


# ---------------------------------------------------------------------------------------------
# table rows
# ---------------------------------------------------------------------------------------------

def parse_row(raw: list) -> dict | None:
    """One table row -> {"code","name","credit","prereq"} | {"total"} | None when it is not a data row.

    Column layout is [code, name(, track label), credit, ECTS, lect, prac, type, prerequisites] with
    None cells where the PDF merged columns. The credit cell is the FIRST non-None cell after the text
    cells; if that cell is empty the credit is unknown (never mistake the ECTS number for it).
    """
    squashed = [None if c is None else squash(c) for c in raw]
    cells = [c for c in squashed if c]
    if not cells:
        return None
    first = cells[0]
    if first == "Total" or (NUMBER_RE.match(first) and len(cells) >= 2):
        numbers = [c for c in cells if NUMBER_RE.match(c)]
        return {"total": float(numbers[0])} if numbers else None
    code = re.sub(r"\s+", "", first) if CODE_RE.match(first) else None
    start = next(i for i, c in enumerate(squashed) if c) + (1 if code else 0)
    text_cells: list[str] = []
    credit: float | None = None
    i = start
    while i < len(squashed):
        c = squashed[i]
        if c is None:
            i += 1
            continue
        if c == "":  # the credit cell exists but is empty
            i += 1
            break
        if NUMBER_RE.match(c):
            credit = float(c)
            i += 1
            break
        if c in TYPE_CELLS:
            break
        text_cells.append(c)
        i += 1
    name = squash(" ".join(text_cells))
    tail = [c for c in squashed[i:] if c is not None]
    if code is None:
        if "elective" not in name.lower() or credit is None:
            return None
        return {"code": None, "name": name, "credit": credit, "prereq": ""}
    type_at = next((k for k, c in enumerate(tail) if c in TYPE_CELLS), None)
    prereq = ""
    if type_at is not None and type_at + 1 < len(tail):
        prereq = tail[type_at + 1]
    elif type_at is None and tail and re.search(r"[A-Z]{2,6}\d{2,4}", tail[-1]):
        prereq = tail[-1]
    return {"code": code, "name": name, "credit": credit, "prereq": normalize_prereq_text(prereq)}


# ---------------------------------------------------------------------------------------------
# the state machine
# ---------------------------------------------------------------------------------------------

class _Plan:
    def __init__(self) -> None:
        self.groups: list[dict] = []
        self.rows: dict[str, list[dict]] = defaultdict(list)  # code -> rows of the requirement tables
        self.guide_rows: dict[str, list[dict]] = defaultdict(list)  # code -> rows of the year/semester tables
        self.entries: list[dict] = []
        self.summary: dict[str, tuple[int, int]] = {}
        self.warnings: list[str] = []


def parse_items(items: list[tuple]) -> dict:
    """items: ("text", line) | ("table", rows). See `finish` for the result."""
    plan = _Plan()
    mode = "preamble"  # preamble -> admission -> framework -> guide -> done
    scope: str | None = None
    group: dict | None = None
    track, year, semester = "all", None, None
    position, credit_sum, pair_seen = 0, 0.0, set()
    in_summary = False
    seen_in_track: dict[tuple[str, str], str] = {}
    pending: str | None = None  # a heading whose "(N credit hours)" is on the next line

    def start_guide(new_track: str | None = None) -> None:
        nonlocal mode, group, in_summary, year, semester, track
        mode, group, in_summary = "guide", None, False
        if new_track is not None:
            track, year, semester = new_track, None, None

    for kind, payload in items:
        if kind == "text":
            line = payload.strip()
            if not line:
                continue
            if COURSES_SECTION_RE.match(line):
                mode = "done"
            if mode == "done":
                continue
            if pending is not None:  # a wrapped heading: "(N credit hours)" is on the following line
                joined = pending + " " + line
                pending = None
                if "credit hour" in joined.lower():
                    line = joined
            if ADMISSION_RE.match(line) and mode == "preamble":
                mode, scope = "admission", "admission"
                group = {"number": "III", "title": "Remedial courses (admission requirements)", "scope": "admission",
                         "kind": "remedial", "track": None, "required_credits": None, "rows": [], "total": None}
                plan.groups.append(group)
                continue
            if FRAMEWORK_RE.search(line):
                mode, group, in_summary = "framework", None, True
                continue
            if mode not in ("framework", "guide"):
                continue
            # guide structure lines
            if GUIDE_HEADING_RE.search(line):
                m = TRACK_FOR_RE.search(line)
                start_guide(slug(m.group(1)) or "all" if m else "all")
                continue
            m = TRACK_LINE_RE.match(line)
            if m and (mode == "guide" or year is None):
                start_guide(slug(m.group(1)) or "all")
                continue
            m = YEAR_RE.match(line)
            if m:
                start_guide()
                year = YEARS[m.group(1)]
                continue
            m = SEMESTER_RE.match(line)
            if m and year is not None:
                start_guide()
                semester, position, credit_sum, pair_seen = m.group(1).lower(), 0, 0.0, set()
                continue
            if mode == "framework":
                m = HEADING_RE.match(line)
                if not m:
                    continue
                text = m.group(2)
                if "credit hour" not in text.lower():
                    if re.search(r"requirements|compulsory|elective", text, re.IGNORECASE):
                        pending = line
                    continue
                title = clean_title(text)
                low = title.lower()
                hours = re.search(r"\(\s*(\d+)\s+credit\s+hours?\s*\)", text, re.IGNORECASE)
                if "university requirements" in low:
                    scope = "university"
                elif "school requirements" in low:
                    scope = "school"
                elif "requirements" in low:
                    scope = "program"
                group = {"number": m.group(1).rstrip("."), "title": title, "scope": scope,
                         "kind": "elective" if "elective" in low else "compulsory", "track": track_of(title),
                         "required_credits": int(hours.group(1)) if hours else None, "rows": [], "total": None}
                plan.groups.append(group)
                in_summary = False
            continue

        # ---- tables ----
        if mode in ("preamble", "done"):
            continue
        for raw in payload:
            first_cell = squash(raw[0]) if raw and raw[0] else ""
            label = first_cell.lower()
            m = YEAR_RE.match(first_cell)  # in these PDFs the year/semester labels are the table's first rows
            if m:
                start_guide()
                year = YEARS[m.group(1)]
                continue
            m = SEMESTER_RE.match(first_cell)
            if m and year is not None:
                start_guide()
                semester, position, credit_sum, pair_seen = m.group(1).lower(), 0, 0.0, set()
                continue
            if mode == "framework" and in_summary and label in SUMMARY_LABELS:
                numbers = [squash(c) for c in raw[1:] if c is not None and NUMBER_RE.match(squash(c))]
                if len(numbers) >= 2:
                    plan.summary[SUMMARY_LABELS[label]] = (int(float(numbers[0])), int(float(numbers[1])))
                continue
            row = parse_row(raw)
            if row is None:
                continue
            if "total" in row:
                if mode == "guide":
                    if year is not None and semester is not None and abs(credit_sum - row["total"]) > 0.01:
                        plan.warnings.append(f"guide {track} year {year} {semester}: credits add up to "
                                             f"{credit_sum:g}, the PDF says {row['total']:g}")
                elif group is not None and group["total"] is None:
                    group["total"] = row["total"]
                continue
            if mode in ("admission", "framework"):
                if group is not None and row["code"]:
                    group["rows"].append(row)
                    plan.rows[row["code"]].append(row)
                continue
            if year is None or semester is None:
                continue
            position += 1
            if row["code"] is None:
                credit_sum += row["credit"]
                plan.entries.append({"track": track, "year": year, "semester": semester, "position": position,
                                     "code": None, "label": row["name"], "credit_hours": int(row["credit"])})
                continue
            plan.guide_rows[row["code"]].append(row)
            pair = GERMAN_PAIR_RE.match(row["code"])
            # credit hours come from the requirement tables; the guide's own credit cell is a fallback
            credit = next((r["credit"] for r in plan.rows.get(row["code"], []) if r["credit"] is not None), row["credit"])
            if credit is None and pair:  # a German B2 row shares the slot (and credit) of its B1 sibling
                sibling = plan.rows.get(row["code"][:-1] + "1") or plan.guide_rows.get(row["code"][:-1] + "1") or []
                credit = next((r["credit"] for r in sibling if r["credit"] is not None), None)
            if credit is None:
                plan.warnings.append(f"guide {track} year {year} {semester}: {row['code']} has no credit hours")
                position -= 1
                continue
            counts = credit
            if pair:
                counts = 0 if pair.group(1) in pair_seen else credit
                pair_seen.add(pair.group(1))
            credit_sum += counts
            key = (track, row["code"])
            if key in seen_in_track:
                plan.warnings.append(
                    f"guide {track}: {row['code']} appears twice ({seen_in_track[key]} and year {year} {semester})")
            seen_in_track.setdefault(key, f"year {year} {semester}")
            plan.entries.append({"track": track, "year": year, "semester": semester, "position": position,
                                 "code": row["code"], "label": None, "credit_hours": int(credit)})
    return finish(plan)


def finish(plan: _Plan) -> dict:
    """Merge the rows of each course, build prerequisites, cross-check, and return the result.

    Result keys: courses[{code,name,credit_hours,prerequisite_note}], prerequisites[{course,prereq,corequisite,
    alt_group}], groups[{title,scope,kind,track,required_credits,codes}], plan_entries, summary, warnings.
    """
    warnings = plan.warnings
    courses: dict[str, dict] = {}
    track_label = re.compile(r"B[12]-?\s?track", re.IGNORECASE)

    def prereq_set(text: str) -> frozenset:
        found, _ = parse_prereq_text(text)
        return frozenset((CODE_TYPOS.get(r["code"], r["code"]), r["corequisite"]) for r in found)

    for code in sorted(set(plan.rows) | set(plan.guide_rows)):
        primary = plan.rows.get(code, [])
        guide = plan.guide_rows.get(code, [])
        pool = primary + guide
        name = next((r["name"] for r in pool if r["name"] and not track_label.fullmatch(r["name"])), None)
        credit = next((r["credit"] for r in pool if r["credit"] is not None), None)
        if (name is None or credit is None) and GERMAN_PAIR_RE.match(code):  # B2 rows borrow from their B1 sibling
            sib = plan.rows.get(code[:-1] + "1", []) + plan.guide_rows.get(code[:-1] + "1", [])
            name = name or next((r["name"].replace("B1-Track", "B2-Track") for r in sib if r["name"]), None)
            credit = credit if credit is not None else next((r["credit"] for r in sib if r["credit"] is not None), None)
        if name is None or credit is None:
            warnings.append(f"{code}: could not read {'a name' if name is None else 'credit hours'} from any table")
            continue
        if not primary:
            warnings.append(f"{code}: only in the year/semester guide, not in a requirement table")
        # real differences only: different credit hours, clearly different names, different prerequisite sets
        if len({r["credit"] for r in primary if r["credit"] is not None}) > 1:
            warnings.append(f"{code}: credit hours differ between tables: "
                            f"{sorted({r['credit'] for r in primary if r['credit'] is not None})}")
        norm = {re.sub(r"[^a-z0-9]+", " ", r["name"].lower()).strip() for r in primary if r["name"]}
        norm = {n for n in norm if not track_label.fullmatch(n)}
        if len(norm) > 1 and min(difflib.SequenceMatcher(None, x, y).ratio() for x in norm for y in norm if x < y) < 0.75:
            warnings.append(f"{code}: names differ between tables: " + " | ".join(sorted({r['name'] for r in primary})))
        texts = [r["prereq"] for r in primary if r["prereq"]]
        if len({prereq_set(t) for t in texts}) > 1:
            warnings.append(f"{code}: prerequisites differ between tables: " + " | ".join(dict.fromkeys(texts)))
        chosen = max(texts, key=lambda t: len(prereq_set(t))) if texts else next(
            (r["prereq"] for r in guide if r["prereq"]), "")
        courses[code] = {"code": code, "name": name, "credit_hours": int(credit), "prereq_text": chosen}

    out_courses, prerequisites = [], []
    for code in sorted(courses):
        info = courses[code]
        rows, conditions = parse_prereq_text(info["prereq_text"])
        for row in rows:
            target = CODE_TYPOS.get(row["code"], row["code"])
            if target != row["code"]:
                warnings.append(f"{code}: prerequisite '{row['code']}' looks like a typo for {target}; used {target}")
            if target not in courses:
                warnings.append(f"{code}: prerequisite {target} is not a course of this plan, skipped")
            elif target == code:
                warnings.append(f"{code}: lists itself as prerequisite, skipped")
            else:
                prerequisites.append({"course": code, "prereq": target,
                                      "corequisite": row["corequisite"], "alt_group": row["alt_group"]})
        out_courses.append({"code": code, "name": info["name"], "credit_hours": info["credit_hours"],
                            "prerequisite_note": "; ".join(conditions) or None})

    out_groups = []
    for g in plan.groups:
        codes = list(dict.fromkeys(r["code"] for r in g["rows"]))
        pair_seen: set[str] = set()
        total = 0
        for c in codes:
            if c not in courses:
                continue
            pair = GERMAN_PAIR_RE.match(c)
            if pair:
                if pair.group(1) in pair_seen:
                    continue
                pair_seen.add(pair.group(1))
            total += courses[c]["credit_hours"]
        if not codes:
            continue
        if g["kind"] != "elective" and g["total"] is not None and abs(total - g["total"]) > 0.01:
            warnings.append(f"table '{g['title']}': courses add up to {total}, the PDF's Total line says {g['total']:g}")
        if g["kind"] == "compulsory" and g["required_credits"] is not None and total != g["required_credits"]:
            warnings.append(f"table '{g['title']}': courses add up to {total}, the heading says {g['required_credits']}")
        if codes:
            out_groups.append({"title": g["title"], "scope": g["scope"], "kind": g["kind"], "track": g["track"],
                               "required_credits": g["required_credits"], "codes": codes})
    return {"courses": out_courses, "prerequisites": prerequisites, "groups": out_groups,
            "plan_entries": plan.entries, "summary": plan.summary, "warnings": warnings}


# ---------------------------------------------------------------------------------------------
# PDF -> items (dev-time only: needs pdfplumber)
# ---------------------------------------------------------------------------------------------

def extract_items(pdf_path: str) -> list[tuple]:
    import pdfplumber  # imported here so the rest of the module (and the app) never needs it

    items: list[tuple] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.find_tables()
            boxes = [t.bbox for t in tables]
            page_items: list[tuple] = []
            for line in page.extract_text_lines():
                middle = (line["top"] + line["bottom"]) / 2
                if any(b[1] - 1 <= middle <= b[3] + 1 and b[0] - 1 <= line["x0"] <= b[2] + 1 for b in boxes):
                    continue
                page_items.append((line["top"], "text", line["text"]))
            for table in tables:
                page_items.append((table.bbox[1], "table", table.extract()))
            page_items.sort(key=lambda item: item[0])
            items.extend((kind, payload) for _, kind, payload in page_items)
    return items


def parse_plan_pdf(pdf_path: str) -> dict:
    return parse_items(extract_items(pdf_path))
