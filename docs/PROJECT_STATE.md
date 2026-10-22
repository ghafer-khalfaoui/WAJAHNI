# Project State (2026-10-20)

Last inspected commit: `0369882` (only commit). Nothing committed or pushed by this session; changes are in the working tree/index.

## Works (verified)
- App boots from a clean install of the repaired `requirements.txt`; `GET /` = 200.
- Password hashing; JWT settings now read from validated config.
- Alembic migration 1 applies on Postgres 16.

## Does not work / missing
See `ISSUES.md`. Biggest gaps: chat and ingest endpoints, schema drift, tenant isolation, open tenant registration, no tests beyond the new `tests/`, no frontend, no GJU data.

## Changes made this session
- `app/core/security.py`: settings-only secret, algorithm, expiry.
- `requirements.txt`: re-encoded UTF-8, added 6 missing packages, pinned `bcrypt==4.0.1`.
- Added `.gitignore`, `.env.example`, `tests/`, `docs/*`.
- Untracked (index only) `.env`, `venv/`, all `__pycache__`. Files remain on disk.

## Tests
`pytest tests/` (see NEXT_SESSION). DB-backed and live-API tests: none, blocked by WJ-017 and unverified free API access.

## Blockers needing the owner
1. Provide the ZIP (WJ-016).
2. Authorize secret rotation and history purge / repo recreation (WJ-001).
3. Confirm which Gemini model and project to use after checking free limits in AI Studio.

## Update 2026-10-21
- Owner machine (Windows, Python 3.11, folder `wajahni2`): install OK, 5 tests passed, `alembic upgrade head` connected; DB at revision 8770692a9cc5 with tables documentchunks, documents, students, universities.
- New migration a3c5e7f91b24 written and verified in sandbox; NOT yet applied to the owner's DB.
- Tests: 10 pass + 1 opt-in drift test (passed against sandbox DB).
- Owner's Docker container `wajahni_db` belongs to Compose project `wajahni1` (old folder); running Compose from `wajahni2` creates a separate empty volume. Do not remove the old container/volume.
- Later 2026-10-21: migrations a3c5e7f91b24 and c7d2f4a8b516 written; sandbox result: 17 tests pass (incl. opt-in drift and temp-schema integration), real `gju_data.json` imported in sandbox (40 courses, 33 instructors, 69 prerequisites; second run created nothing). NOT yet run on the owner's DB. Owner created a new Gemini key twice-exposed in screenshots; must delete and recreate; billing level of the new project (893403538057) not yet confirmed.

## Update 2026-10-22
- Owner DB verified: migrations applied to c7d2f4a8b516, 17 tests passed (incl. drift), GJU seed imported (40/33/69, all `verified=false`).
- New: rule-based chat endpoint `POST /api/v1/chat/{domain}`; 12 new tests (offline + temp-schema) pass in sandbox. Not yet run on owner's machine.
- Still open: no DB backup exists; Gemini keys exposed in screenshots (delete/recreate); WJ-001/005/011/020/021.
