# Changelog

## 2026-10-22
- Added: rule-based chat endpoint `POST /api/v1/chat/{domain}` (no AI model, $0). Answers course info, direct/full-chain prerequisites and staff office/phone/email from the structured tables, scoped to one university taken from the URL. Replaces the earlier mock stub (response schema changed: `answer`, `status`, `sources`, `data_verified`).
- Behaviour: returns only the contact detail asked for; says when data is unverified; asks which person when a name is ambiguous; year-like text ("deadlines in 2026") is not treated as a course code.
- Added: `tests/test_chat.py`, `tests/db_helpers.py` (temporary-schema helpers). Sandbox: 28 pass; the drift test fails only on an unmigrated sandbox DB.

## 2026-10-21 (b)
- Added: tenant-scoped `courses`, `course_prerequisites`, `instructors` (migration `c7d2f4a8b516`), each row with `source` and `verified`.
- Added: `app/services/academic.py` (validated, repeatable importer; exact lookups for courses, prerequisites incl. transitive, staff search) and `scripts/import_academic_data.py` (prints counts only).
- Added: `data/` is git-ignored for real university data; synthetic fixture in `tests/fixtures`.
- Fixed (WJ-022): all models imported in `app/models/__init__.py`.

## 2026-10-21
- Fixed (WJ-007): models rebuilt to match migrations; new migration `a3c5e7f91b24` (admin_users, chunk university_id NOT NULL + FK, data backfilled).
- Added (WJ-008): tenant-restricted `VectorStoreService.search`; ingest now writes chunk `university_id`.
- Added: `tests/test_models.py`, opt-in `tests/test_schema_drift.py` (set `WAJAHNI_TEST_DB_URL`).
- Changed: `docker-compose.yml` reads password from `.env`, port bound to 127.0.0.1.

## 2026-10-20
- Fixed: requirements encoding and missing packages; bcrypt/passlib incompatibility (WJ-003).
- Fixed: removed hard-coded JWT fallback secret; algorithm/expiry from settings (WJ-004).
- Added: `.gitignore`, `.env.example`, `tests/`, audit and policy docs.
- Changed (index only): stopped tracking `.env`, `venv/`, `__pycache__`.
