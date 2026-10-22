"""Download public GJU pages (staff directories, academic calendar) to data/raw/gju/.

Polite by design: waits 10 seconds between requests (the site's robots.txt Crawl-delay),
identifies itself, skips files already downloaded (safe to re-run), and never touches the
paths robots.txt disallows. Raw pages stay on your computer (data/ is git-ignored).

Usage:  .\\.venv\\Scripts\\python.exe -m scripts.fetch_gju
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://www.gju.edu.jo"
OUT = Path("data/raw/gju")
DELAY_SECONDS = 10
MAX_PAGES = 15
USER_AGENT = "WAJAHNI-student-project/0.1 (educational; polite, 10s delay)"
DISALLOWED = ("/admin/", "/search/", "/user/", "/comment/reply/", "/node/add/", "/filter/tips/")

LISTINGS = {
    "faculty": "/content/faculty-directory-2798?field_school_groups_target_id=All&page={n}",
    "staff": "/content/staff-directory-2882?page={n}",
}
SINGLE = {
    "academic_event.html": "/academic-event",
    "academic_calendar_2026-2027.pdf": "/sites/default/files/announcement/academic_calendar_2026-2027.pdf",
}


def fetch(path: str) -> bytes:
    if any(path.startswith(p) for p in DISALLOWED):
        raise ValueError(f"refusing disallowed path {path}")
    request = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def polite_fetch(path: str, target: Path) -> bytes | None:
    if target.exists():
        print(f"  have {target.name}")
        return target.read_bytes()
    time.sleep(DELAY_SECONDS)
    try:
        body = fetch(path)
    except urllib.error.URLError as exc:
        print(f"  FAILED {path}: {exc}")
        return None
    target.write_bytes(body)
    print(f"  saved {target.name} ({len(body)} bytes)")
    return body


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, template in LISTINGS.items():
        print(f"{name} directory")
        for n in range(MAX_PAGES):
            body = polite_fetch(template.format(n=n), OUT / f"{name}_p{n}.html")
            if body is None or b"mailto:" not in body:
                print("  no more entries, stopping this listing")
                break
    print("academic calendar")
    for filename, path in SINGLE.items():
        polite_fetch(path, OUT / filename)
    print(f"Done. Files are in {OUT.resolve()}")


if __name__ == "__main__":
    main()
