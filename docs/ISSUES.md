# WAJAHNI — Issue Register

Status key: OPEN, MITIGATED (local change, not pushed), FIXED (verified), BLOCKED.
Evidence key: REPRODUCED = observed by running; INSPECTION = read in code, not executed; ENV = blocked by sandbox.

| ID | Sev | Issue | Evidence | Status |
|---|---|---|---|---|
| WJ-001 | Critical | `.env` committed to a **public** repo (history commit `0369882`). JWT secret (64 chars) and DB password (16 chars) are not placeholders. Treat both as compromised. `GEMINI_API_KEY` value looks like a placeholder (not confirmed real). | REPRODUCED (file in history) | MITIGATED locally: untracked, `.gitignore`, `.env.example`. **Still needs: rotate secrets, purge history or recreate repo (needs your authorization).** |
| WJ-002 | High | `venv/` (10,062 files, ~240 MB) and `__pycache__` committed; no `.gitignore`. | REPRODUCED | MITIGATED (untracked locally) |
| WJ-003 | High | `requirements.txt` UTF-16, missing 6 packages; bcrypt 5 breaks passlib 1.7.4 hashing. | REPRODUCED | FIXED, verified in clean venv |
| WJ-004 | High | Hard-coded fallback JWT secret literal; algorithm and expiry hard-coded, ignoring settings. | INSPECTION | FIXED (`app/core/security.py`), regression test added |
| WJ-005 | High | `POST /api/auth/register-tenant` is unauthenticated: anyone can create a university and its admin. | INSPECTION | OPEN |
| WJ-006 | High | Chat and ingest endpoints missing (404). `chat.py` stub is also broken: reads `request.message` (field is `user_query`) and returns fields not in `ChatResponse`. | REPRODUCED (404), INSPECTION (stub) | OPEN |
| WJ-007 | High | Schema drift between models and DB (missing `admin_users`, table-name mismatch, missing NOT NULL columns). Owner's DB confirmed at revision 8770692a9cc5 without `admin_users`. | REPRODUCED on owner's DB | FIXED in code: models rebuilt on `WajahniBaseModel`, migration a3c5e7f91b24 adds `admin_users` and backfills `documentchunks.university_id`. Verified in sandbox (old-style data kept, reversible, register/login work) using a float array instead of pgvector. **Pending: owner runs `alembic upgrade head` on the real DB** |
| WJ-008 | Medium | Retrieval had no tenant filter. | INSPECTION | PARTIAL: chunks carry `university_id` (NOT NULL, FK); `VectorStoreService.search` filters by it (tested). Still to do: chat endpoint must take the university from the user context, not the client; update root test scripts |
| WJ-009 | Medium | Duplicate `services/vector_store.py` (root) and `app/services/vector_store.py` with different embedding models. | REPRODUCED (diff) | OPEN |
| WJ-010 | Medium | Model IDs unverified: `gemini-3.5-flash` absent from pricing page; embedding free-tier status not stated. | Official pages | OPEN, see COST_POLICY |
| WJ-011 | Medium | No quota counters, rate limits, retries/timeouts, or cost guard; ingest embeds each chunk sequentially, unbounded input size. | INSPECTION | OPEN |
| WJ-012 | Medium | Two Gemini SDKs installed; `google-generativeai` is end-of-life. | REPRODUCED (warning) | OPEN |
| WJ-013 | Medium | No automated tests; `test_*.py` in root are live scripts. | INSPECTION | PARTIAL: `tests/` started |
| WJ-014 | Low | `docker-compose.yml` hard-codes the DB password; DB port exposed on all interfaces. | INSPECTION | OPEN |
| WJ-015 | Low | Pool size 20 + 10 overflow oversized for local; BOM/UTF-16 files; empty README. | INSPECTION | OPEN |
| WJ-016 | Info | Saved notes (five tables migrated, `course_repository.py` next) do not match the repo. | — | OPEN, needs ZIP |
| WJ-018 | High | `pip install -r requirements.txt` fails on the owner's Windows machine: wheel tags in the pip output show a Python 3.15 interpreter (`cp315`). `google-api-core 2.31.0` requires `grpcio-status>=1.75.1` on Python >=3.14, conflicting with the pin `1.71.2`; several packages (asyncpg, pydantic_core, numpy, grpcio) were downloading as source. Works on Python 3.13 (verified in sandbox). | REPRODUCED (owner's output) | OPEN: use Python 3.11-3.13; consider loosening gRPC pins |
| WJ-019 | High | Owner put real secrets into the tracked file `.env.example`; committing it would leak them again. `DATABASE_ASYNC_URL` there still says `CHANGE_ME`. | Owner message | OPEN: keep `.env.example` empty; real values only in `.env` |
| WJ-017 | Info | DB-backed behaviour untestable in this sandbox (no pgvector, no Docker). | ENV | BLOCKED |
| WJ-020 | Medium | GJU seed data (`gju_data.json`, from the owner's university) needs verification: all 3 preparatory courses (ARB0099, ENGL0099, MATH0099) appear as prerequisites of most CS courses (33 of 69 prerequisite rows cross departments); credit hours include 0 (CS391) and 12 (CS491). Data is partial (40 courses, 33 instructors). | INSPECTION of data | OPEN: compare with the official study plan; rows stored `verified=false` |
| WJ-021 | High | Old public repo `ghafer-khalfaoui/ai-chatbot` contains staff names, emails and phone numbers plus an old `.env` with a Flask secret. Owner no longer needs it. | REPRODUCED (public clone worked) | OPEN: owner should make it private or delete it |
| WJ-022 | Medium | `University` relationships failed to resolve when a script imported only that model (mapper error). | REPRODUCED | FIXED: `app/models/__init__.py` imports all models; regression test added |
| WJ-023 | Low | Some job titles in the official GJU faculty listing are cut off by the website itself (e.g. "Full Professor/Vice President for..."; 4 of 25 on the sample pages). Full titles exist on each profile page. | INSPECTION of real pages | OPEN: optionally fetch profile pages (10 s delay each) later |
| WJ-024 | Medium | Study plans differ by admission year, but `courses` allows one row per code per university. | DESIGN | PARTLY RESOLVED 2026-10-24: only the newest plan (CS 2023/2024, all tracks) is loaded; older versions ignored by owner decision. Still open: plan year may not match a student's admission year; other schools' plans |
| WJ-025 | Low | Old unverified seed courses stay in the DB after the official plan is imported. | DATA | OPEN: importer only REPORTS them; deleting needs owner approval |
| WJ-026 | Low | Year/semester placement per track (the 'Study Plan Guide' tables) was not parsed. | FEATURE | FIXED 2026-10-25: `plan_entries` table, `parse_guide`, chat answers; all 24 semester credit totals match the PDF |
| WJ-027 | Medium | CS plan rows are flagged verified without an independent spot-check against the PDF (parser self-checks only). | DATA | OPEN: owner to compare 5 courses |
| WJ-028 | Low | The official CS plan PDF lists CS451 twice on the Cybersecurity track (year 2 and year 3, second semester); both semester totals only add up with both. Possibly a copy error in the PDF. | DATA | OPEN: both kept; ask the department / re-read the PDF |
| WJ-029 | Medium | 30 program datasets are generated (`datasets/gju/programs/`) and import cleanly into a scratch DB, but none is imported on the real DB yet and the chat ignores programs. Warnings per plan are in each file (`review_warnings`). | DATA | IN PROGRESS: chat program support next; read warnings for arch, cee, translation, bida, gdmi |
| WJ-030 | Low | Plan sources not found: Management Sciences B.Sc. (no link on its page), architecture page 2470 (empty), newer SAHSS plans possible. | DATA | OPEN: check pages by hand or ask the school |
| WJ-031 | Low | Dual-study plans are listed but not loaded; Energy Engineering plan is a .docx (parser needs Word support). | DATA | OPEN |
