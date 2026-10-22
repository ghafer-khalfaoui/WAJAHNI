"""Turn the saved GJU directory pages in data/raw/gju/ into data/gju_official.json.

Usage:  .\\.venv\\Scripts\\python.exe -m scripts.parse_gju
Prints counts only (no names or contact details). The JSON stays on your computer.
"""
import json
from pathlib import Path

from app.services.gju_parser import merge_people, parse_faculty_page, parse_staff_page

RAW = Path("data/raw/gju")
OUT = Path("data/gju_official.json")


def main() -> None:
    groups, report = [], []
    for kind, parser in (("faculty", parse_faculty_page), ("staff", parse_staff_page)):
        people, seen, files = [], 0, sorted(RAW.glob(f"{kind}_p*.html"), key=lambda p: int(p.stem.split("_p")[1]))
        for path in files:
            found, rows = parser(path.read_text(encoding="utf-8", errors="replace"))
            people += found
            seen += rows
        unique = len(merge_people(people))
        report.append(f"{kind}: {len(files)} files, {seen} rows seen, {len(people)} with email, {unique} unique emails")
        groups.append(people)
    merged = merge_people(*groups)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps({"courses": [], "prerequisites": [], "instructors": merged}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("\n".join(report))
    print(f"total unique people written: {len(merged)}  ->  {OUT}")


if __name__ == "__main__":
    main()
