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

## Update 2026-10-24 (study plan done)
- Owner steps: `git pull`; `docker start wajahni_db`; `alembic upgrade head` (applies d9e1b3c5a728 and f3a9c1d7e054); import calendar, then plan (`datasets\gju\cs_study_plan_2023_2024.json`, source "GJU CS study plan 2023-2024 PDF"); read the "NOT in this plan" list; spot-check against the PDF; re-run with `--verified`. Import staff after a 5-person spot check.
- Old 2022/23 plan is ignored (owner decision). Ask owner before deleting old unverified courses (WJ-025).
- Next: owner's admission year; other schools' plans; Study Plan Guide tables (WJ-026); chat UI; RAG once a free model/embedding quota is confirmed.

## Update 2026-10-25
- Owner ran the migration and imported calendar (84 rows were already verified, kept) and the CS plan (63 created, 40 updated, no leftover list printed), then re-ran with `--verified` WITHOUT the 5-course spot check. Data is flagged verified but not independently compared with the PDF: do that check when convenient.
- Decision D-005: never ask the admission year; always use the newest plan.
- Chat smoke test: 4 requests OK, 1 returned 422 (empty or >500-char message, not investigated).

## Update 2026-10-25 (year/semester guide done)
- Owner: `git pull`, `alembic upgrade head` (new revision b4e8d2a6c913), re-import `datasets\gju\cs_study_plan_2023_2024.json` (same source text; add `--verified` only after the spot-check of WJ-027). Expect `plan_entries_created: 162`.
- Try: "what do I take in third year first semester cybersecurity", "first year first semester".
- Next: other schools' plans (list in docs), simple chat UI, RAG when a free model/embedding quota is confirmed. WJ-028 (CS451 duplicate) is a question for the department.

## Update 2026-10-25 (other schools)
- Owner: `git pull`, then `python -m scripts.fetch_gju_plans --zip` (about 40 files, 10 s apart = roughly 7 minutes), attach `data\raw\gju\plans.zip` and the printed FAILED lines.
- Then, per program: read the real PDF layout, extend/generalise `plan_parser.py` (CS layout may differ), generate `datasets/gju/<program>.json`, import, spot-check. Start with Computer Engineering (same school layout as CS), then the other engineering plans.
- Long-term (ROADMAP): German universities after all GJU plans.

## Update 2026-10-29 (multi-program backend + datasets built, chat not yet program-aware)
- Done and tested (106 tests pass, DB tests included): Program/ProgramCourse models, migration c5f1a7d3e826 (verified up/down/up on a scratch DB), importer with per-program slots and conflict report (shared courses are never silently overwritten; `--overwrite` replaces), table parser `app/services/plan_template.py`, `scripts/build_gju_program.py` (dev tool, needs `pip install pdfplumber`).
- 30 program datasets generated in `datasets/gju/programs/` (regular + dual). Each file lists its parser doubts in `review_warnings`. Importing all of them into a scratch DB worked: 269 distinct real disagreements between plans (names written differently, prerequisites one plan does not list). They were kept, not applied.
- NOT done: chat still answers from the CS data only (`answer_plan`/`_answer_track` ignore programs). Next code task: detect the program in the question, pick the newest `plan_version`, ask which program when ambiguous, regular before dual.
- Not done: gebc dual (scan PDF), gebc guide supplement, Energy Engineering (.docx 404), Management Sciences (no link). Warnings in arch, arch-dual, cee, translation, bida, gdmi need reading against the PDFs before these are called reliable. Everything imports as UNVERIFIED.
- Owner (when ready): `git pull`, `alembic upgrade head` (b4e8d2a6c913 then c5f1a7d3e826), re-import the CS file, then the files in `datasets\gju\programs\` one by one. Read the "DIFFERENCES" lines the importer prints.
