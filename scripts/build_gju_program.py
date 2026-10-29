"""Build an import-ready program dataset from a GJU study-plan PDF that has ruled tables.

Dev-time tool (needs `pip install pdfplumber`, not a runtime dependency). One plan at a time:

  python -m scripts.build_gju_program ce_2023-2024 path/to/ce.pdf

or every downloaded plan at once (PDFs named <id>.pdf in the folder; ids come from study_plan_sources.json):

  python -m scripts.build_gju_program --all path/to/plans_folder

Output: datasets/gju/programs/<program-code>.json. The parser's warnings are stored inside the file
("review_warnings") so a person can see exactly what was uncertain. The importer ignores that key.
The Computer Science plan has no ruled tables and still uses scripts/build_gju_plan.py.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from app.services.plan_template import parse_plan_pdf

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "datasets" / "gju" / "study_plan_sources.json"
OUT_DIR = ROOT / "datasets" / "gju" / "programs"
CATALOG = ROOT / "datasets" / "gju" / "cs_study_plan_2023_2024.json"  # fills credits missing in every table
SCOPE_LABEL = {"admission": "Admission", "university": "University", "school": "School", "program": "Program"}


def program_code(plan_id: str) -> str:
    """'ce_2023-2024_dual' -> 'ce-dual'; 'translation_2024-2025' -> 'translation' (version lives in plan_version)."""
    code = re.sub(r"[_-]?20\d\d(-\d{2,4})?", "", plan_id)
    return re.sub(r"[^a-z0-9-]+", "-", code.lower()).strip("-")


def load_catalog() -> dict[str, dict]:
    if not CATALOG.exists():
        return {}
    return {c["code"]: c for c in json.loads(CATALOG.read_text(encoding="utf-8"))["courses"]}


def build(entry: dict, pdf: Path, catalog: dict[str, dict]) -> dict:
    parsed = parse_plan_pdf(str(pdf))
    warnings = list(parsed["warnings"])
    courses = []
    for c in parsed["courses"]:
        hours = c["credit_hours"]
        if hours is None and c["code"] in catalog:
            hours = catalog[c["code"]]["hours"]
            warnings.append(f"{c['code']}: credit hours ({hours}) taken from the Computer Science plan, not from this PDF")
        if hours is None:
            warnings.append(f"{c['code']}: no credit hours anywhere, course left out")
            continue
        courses.append({"code": c["code"], "name": c["name"], "hours": hours,
                        "prerequisite_note": c["prerequisite_note"]})
    known = {c["code"] for c in courses}
    program_courses = []
    for g in parsed["groups"]:
        title = f"{SCOPE_LABEL.get(g['scope'], g['scope'])} - {g['title']}"
        for code in g["codes"]:
            if code in known:
                program_courses.append({"course": code, "group": title, "scope": g["scope"],
                                        "kind": g["kind"], "track": g["track"]})
    return {
        "plan": f"{entry['program']} study plan {entry['version']} ({entry['kind']})",
        "source_url": SOURCES_BASE + entry["path"],
        "replace_prerequisites": False,  # shared courses: never wipe another program's prerequisites
        "program": {"code": program_code(entry["id"]), "name": entry["program"], "school": entry["school"],
                    "degree": "B.Sc.", "plan_version": entry["version"], "kind": entry["kind"]},
        "courses": courses,
        "prerequisites": [p for p in parsed["prerequisites"] if p["course"] in known and p["prereq"] in known],
        "program_courses": program_courses,
        "plan_entries": [e for e in parsed["plan_entries"] if e["code"] is None or e["code"] in known],
        "review_warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="plan id, or with --all the folder of PDFs")
    ap.add_argument("pdf", nargs="?", type=Path)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    manifest = json.loads(SOURCES.read_text(encoding="utf-8"))
    global SOURCES_BASE
    SOURCES_BASE = manifest["base"]
    entries = {e["id"]: e for e in manifest["plans"]}
    jobs = []
    if args.all:
        folder = Path(args.target)
        jobs = [(e, folder / f"{e['id']}.pdf") for e in entries.values()
                if e["id"] != "cs_2023-2024" and (folder / f"{e['id']}.pdf").exists()]
    else:
        if args.target not in entries or args.pdf is None:
            raise SystemExit(f"unknown plan id or missing PDF path; ids: {', '.join(entries)}")
        jobs = [(entries[args.target], args.pdf)]
    catalog = load_catalog()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for entry, pdf in jobs:
        data = build(entry, pdf, catalog)
        if not data["courses"]:
            print(f"{entry['id']:28} nothing readable (scan or supplement PDF), skipped")
            continue
        out = OUT_DIR / f"{data['program']['code']}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{entry['id']:28} courses {len(data['courses']):3}  slots {len(data['plan_entries']):3}  "
              f"warnings {len(data['review_warnings']):2}  -> {out.relative_to(ROOT)}")
    return 0


SOURCES_BASE = ""

if __name__ == "__main__":
    sys.exit(main())
