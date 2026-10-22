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
