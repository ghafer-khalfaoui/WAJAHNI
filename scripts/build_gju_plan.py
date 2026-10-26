"""Build an import-ready study-plan JSON from the text of a GJU study-plan PDF.

Step 1 (needs the `pdftotext` tool, part of poppler):
    pdftotext -layout cs_study_plan_2023-2024_updated.pdf plan.txt
Step 2:
    python -m scripts.build_gju_plan plan.txt datasets/gju/cs_study_plan_2023_2024.json

Prints counts and any warnings. A warning means a person should look at that course.
"""
import json
import sys
from pathlib import Path

from app.services.plan_parser import build_plan, parse_guide

PLAN_NAME = "B.Sc. Computer Science study plan 2023-2024 (all tracks)"
SOURCE_URL = (
    "https://www.gju.edu.jo/sites/default/files/Computer%20Science/programs/"
    "study_plan_all_tracks_2023-2024_updated.pdf"
)


# Old group name -> (title shown to students, scope, kind, track)
GROUP_INFO = {
    "remedial": ("Admission requirements (remedial courses)", "university", "remedial", None),
    "university-compulsory": ("University requirements - compulsory", "university", "compulsory", None),
    "university-elective": ("University requirements - elective", "university", "elective", None),
    "school": ("School requirements", "school", "compulsory", None),
    "program-common": ("Program requirements - common to all tracks", "program", "compulsory", None),
    "track-general": ("Program requirements - General track", "program", "compulsory", "general"),
    "track-data-science": ("Program requirements - Data Science track", "program", "compulsory", "data-science"),
    "track-cybersecurity": ("Program requirements - Cybersecurity track", "program", "compulsory", "cybersecurity"),
    "elective-general": ("Program electives - General track", "program", "elective", "general"),
    "elective-data-science": ("Program electives - Data Science track", "program", "elective", "data-science"),
    "elective-cybersecurity": ("Program electives - Cybersecurity track", "program", "elective", "cybersecurity"),
}


def add_program(data: dict) -> dict:
    """Add the `program` and `program_courses` parts (new format) derived from each course's plan_groups."""
    data["program"] = {
        "code": "cs", "name": "B.Sc. Computer Science", "school": "School of Computing",
        "degree": "B.Sc.", "plan_version": "2023-2024", "kind": "regular",
    }
    data["program_courses"] = [
        {"course": c["code"], "group": GROUP_INFO[g][0], "scope": GROUP_INFO[g][1],
         "kind": GROUP_INFO[g][2], "track": GROUP_INFO[g][3]}
        for c in data["courses"] for g in (c.get("plan_groups") or [])
    ]
    return data


def main(text_path: Path, out_path: Path) -> int:
    text = text_path.read_text(encoding="utf-8")
    plan = build_plan(text)
    entries, guide_warnings = parse_guide(text, {c["code"]: c["credit_hours"] for c in plan["courses"]})
    plan["warnings"] = plan["warnings"] + guide_warnings
    data = {
        "plan": PLAN_NAME,
        "source_url": SOURCE_URL,
        "replace_prerequisites": True,
        "courses": [
            {
                "code": c["code"], "name": c["name"], "hours": c["credit_hours"],
                "plan_groups": c["plan_groups"], "prerequisite_note": c["prerequisite_note"],
            }
            for c in plan["courses"]
        ],
        "prerequisites": plan["prerequisites"],
        "plan_entries": entries,
    }
    add_program(data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"courses: {len(data['courses'])}, prerequisite rows: {len(data['prerequisites'])}, "
          f"year/semester slots: {len(entries)}")
    print(f"course blocks not part of this plan (ignored): {', '.join(plan['blocks_not_in_plan']) or 'none'}")
    for warning in plan["warnings"]:
        print("WARNING:", warning)
    return 1 if plan["warnings"] else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
