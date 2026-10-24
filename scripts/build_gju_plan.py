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

from app.services.plan_parser import build_plan

PLAN_NAME = "B.Sc. Computer Science study plan 2023-2024 (all tracks)"
SOURCE_URL = (
    "https://www.gju.edu.jo/sites/default/files/Computer%20Science/programs/"
    "study_plan_all_tracks_2023-2024_updated.pdf"
)


def main(text_path: Path, out_path: Path) -> int:
    plan = build_plan(text_path.read_text(encoding="utf-8"))
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
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"courses: {len(data['courses'])}, prerequisite rows: {len(data['prerequisites'])}")
    print(f"course blocks not part of this plan (ignored): {', '.join(plan['blocks_not_in_plan']) or 'none'}")
    for warning in plan["warnings"]:
        print("WARNING:", warning)
    return 1 if plan["warnings"] else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
