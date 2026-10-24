"""Download the official GJU study-plan files listed in datasets/gju/study_plan_sources.json.

Polite: one request every 10 seconds (the site's robots.txt Crawl-delay), identifying User-Agent,
only /sites/default/files/ paths, skips files you already have (safe to re-run). Regular plans are
fetched first, dual-study plans after. Every download is checked to really be a PDF or Word file.

Usage (project folder):
    .\\.venv\\Scripts\\python.exe -m scripts.fetch_gju_plans            # download everything missing
    .\\.venv\\Scripts\\python.exe -m scripts.fetch_gju_plans --zip      # also make data\\raw\\gju\\plans.zip to attach

Files go to data/raw/gju/plans/ (git-ignored). A report is written to plans/_report.txt.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www.gju.edu.jo"
MANIFEST = Path("datasets/gju/study_plan_sources.json")
OUT = Path("data/raw/gju/plans")
DELAY_SECONDS = 10
USER_AGENT = "WAJAHNI-student-project/0.1 (educational; polite, 10s delay)"
ALLOWED_PREFIX = "/sites/default/files/"


def looks_right(body: bytes, suffix: str) -> bool:
    return body.startswith(b"%PDF") if suffix == ".pdf" else body.startswith(b"PK")  # .docx is a zip


def candidates(path: str) -> list[str]:
    # The site sometimes writes "&amp;" into file URLs; try the odd form first, then a plain "&".
    return [path] + ([path.replace("%26amp%3B", "%26")] if "%26amp%3B" in path else [])


def download(path: str, suffix: str) -> tuple[bytes | None, str]:
    last_error = ""
    for attempt, candidate in enumerate(candidates(path)):
        if not candidate.startswith(ALLOWED_PREFIX):
            return None, "refused: path outside /sites/default/files/"
        if attempt:
            time.sleep(DELAY_SECONDS)
        request = urllib.request.Request(BASE + candidate, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read()
        except urllib.error.URLError as exc:
            last_error = f"{exc}"
            continue
        if looks_right(body, suffix):
            return body, "ok"
        last_error = "downloaded, but it is not a real PDF/Word file (maybe an error page)"
    return None, last_error


def main(make_zip: bool) -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    plans = [p for p in data["plans"] if p["status"] != "loaded"]
    plans.sort(key=lambda p: p["kind"] != "regular")  # regular first (stable)
    lines, failed = [], 0
    for plan in plans:
        suffix = Path(plan["path"]).suffix.lower()
        target = OUT / f"{plan['id']}{suffix}"
        if target.exists():
            lines.append(f"have    {target.name}")
            continue
        time.sleep(DELAY_SECONDS)
        body, message = download(plan["path"], suffix)
        if body is None:
            failed += 1
            lines.append(f"FAILED  {target.name}: {message}")
        else:
            target.write_bytes(body)
            lines.append(f"saved   {target.name} ({len(body)} bytes)")
        print(lines[-1])
    (OUT / "_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nDone: {len(plans) - failed} of {len(plans)} files available in {OUT.resolve()}")
    if make_zip:
        archive = OUT.parent / "plans.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for file in sorted(OUT.iterdir()):
                z.write(file, file.name)
        print(f"Zip to attach to the chat: {archive.resolve()} ({archive.stat().st_size // 1024} KB)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main("--zip" in sys.argv[1:]))
