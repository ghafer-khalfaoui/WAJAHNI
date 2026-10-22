# Next Session — resume point

1. Read `CLAUDE.md`, `PROJECT_STATE.md`, `ISSUES.md`; run `git status`.
2. Check whether the owner supplied the ZIP; diff it against the repo before editing (WJ-016).
3. Verify: `python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest && .venv/bin/pytest tests -q`
   (tests set dummy env vars themselves; no network, no DB, no API calls).
4. Next actions in order:
   - Confirm owner ran `alembic upgrade head` (two new migrations) and the tests with `WAJAHNI_TEST_DB_URL` set, then imported the data with `python -m scripts.import_academic_data data\gju_data.json` (WJ-007 final check; WJ-020 verification).
   - Owner: `git pull`, run tests with `WAJAHNI_TEST_DB_URL`, start `uvicorn app.main:app --reload`, POST `/api/v1/chat/gju.edu.jo` from `/docs` (rule-based chat is done).
   - WJ-006/WJ-008: add document retrieval (RAG) behind the same endpoint for questions the rules cannot answer; needs a confirmed free model/embedding first.
   - Add a minimal chat UI over the endpoint.
   - WJ-005: restrict tenant registration.
   - WJ-011: cost guard module + config allowlist from `COST_POLICY.md`.
5. GJU data candidate: old repo `ghafer-khalfaoui/ai-chatbot` has `gju_data.json` (33 instructors with office/phone/email, 40 courses, 69 prerequisites) and `intents.json` (21 intents). Provenance and currency are UNVERIFIED: ask the owner where it came from before treating it as official. Import it as a seed with source/date metadata; do not reuse the old Flask/BERT/MySQL code.
6. Owner's machine: Python must be 3.11-3.13 (WJ-018). Owner's AI Studio project `GJU-Chatbot-Project` is on the no-cost tier with no billing configured (screenshot 2026-10-20); the key was exposed in a screenshot and must be deleted and recreated. Rate-limit page not yet seen.
7. Do not call any Gemini endpoint until the free model and quota are confirmed in AI Studio.

## Update 2026-10-22 (GJU data source)
- Owner confirmed chat endpoint reaches the DB layer; the 500 seen was Postgres not running (port 5432 refused), not a code bug. Should return a clean 503 instead (todo).
- Official GJU pages (public): Faculty Directory https://www.gju.edu.jo/content/faculty-directory-2798 (name, title, school, office, phone ext, email; 9 pages via `?field_school_groups_target_id=All&page=N`), Staff Directory .../staff-directory-2882, Academic Calendar https://www.gju.edu.jo/academic-event (+ 2026-2027 PDF), Schools under /content/school-*. robots.txt: Crawl-delay 10s; /search/, /admin/, /user/ disallowed.
- Plan: local script run by the owner (shell here cannot reach the site) with 10s delay, identifying User-Agent, saving to `data/` (git-ignored), importing with `verified=false` and `source=<official URL>`. Study plans still need a source page.
- Added `scripts/fetch_gju.py` (polite 10s-delay downloader to `data/raw/gju/`). Parser NOT written yet: needs the real HTML (ask owner to send `faculty_p0.html` and `academic_event.html`), then write `scripts/parse_gju.py` + tests on a trimmed fixture, import with verified=false.
- Chat endpoint now returns 503 (not 500) when the DB is unreachable.
- AI Studio rate-limit screenshot (project "wajahni"): free tier, only model row visible so far is "Antigravity" (agents) 60 RPM / 100K TPM / 100 RPD; Gemini text/embedding rows not yet seen (toggle "Tous les modèles").

## Update 2026-10-22 (parser)
- Owner downloaded 15 faculty + 15 staff pages + calendar page + calendar PDF into `data/raw/gju/`. The fetcher did not stop early (every page contains a mailto), so pages past the real end may be duplicates; the parser de-duplicates by email and prints counts.
- Next: owner runs `python -m scripts.parse_gju`, sends the printed counts; compare 5 random people with the website; then `python -m scripts.import_academic_data data\gju_official.json --source "https://www.gju.edu.jo/content/faculty-directory-2798 and staff-directory-2882, fetched 2026-10-22"` (add `--verified` only after the spot check).
- The HTML calendar page for October 2026 has no events. The real source is `academic_calendar_2026-2027.pdf`: owner must attach it; then add an `academic_events` table + chat answers for dates.
- Study plans / course lists still have no official source file. Look under each school page.

## Update 2026-10-23
- Owner ran `parse_gju` (333 people). First import failed with ConnectionRefused (Postgres/Docker was off). Owner had passed `--verified` before any spot check: advise import WITHOUT `--verified`, spot-check 5 people, then re-run with `--verified`.
- Still needed: calendar PDF, study-plan source, confirm AI Studio project id.

## Update 2026-10-23 (calendar done)
- Owner: `git pull`, `alembic upgrade head` (new revision d9e1b3c5a728), then `python -m scripts.import_academic_data datasets\gju\calendar_2026_2027.json --source "GJU academic calendar 2026/2027 PDF"`; glance at the PDF vs a few chat answers; then re-run with `--verified`.
- AI Studio project confirmed: `893403538057` = `gen-lang-client-0113469613` ("wajahni"), free tier.
- Next: study plans. Owner says each school page has its study plans. Find them (School of Computing first), get an official source, extend courses/prerequisites import with source URLs.

## Study plans (found 2026-10-23)
- Official CS study-plan PDFs are linked from https://www.gju.edu.jo/content/computer-science-7419 (versions 2018, 2020, 2022/23 updated, 2023/24 updated; all tracks incl. Cybersecurity and Data Science; also dual-study versions). Tables have: Course ID, Course Name, Credit Hours, ECTS, Contact Hours, Type (F2F/BLD/OL), Prerequisites/Corequisites. Only a summary was seen via WebFetch; do NOT trust it for data: parse the real PDF.
- `scripts/fetch_gju.py` now also downloads the 2022/23 and 2023/24 plans. Owner must say which admission year applies (plans differ).
- Limitation to design for: `courses` is unique per (university, code), so only ONE plan version can be loaded at a time unless a `plan_version`/program column is added (new issue WJ-024).
- Other schools (SATS, SABE, SSSE, BS, SAMS, SAHSS, SN) have their own plans; do CS first.
