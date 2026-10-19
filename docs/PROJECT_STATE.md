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
