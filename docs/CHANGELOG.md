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

## 2026-10-22 (later)
- Added: `app/services/gju_parser.py`, `scripts/parse_gju.py` (saved GJU directory pages -> `data/gju_official.json`), `--verified` flag on the importer, fixtures and `tests/test_gju_parser.py`. Checked on real pages: 10/10 faculty rows and 15/15 staff rows parsed.

## 2026-10-23
- Changed: importer now also updates a row when only its source or verified flag changes (so importing unverified first and re-running with `--verified` works), and an unverified import never overwrites verified rows (`skipped_already_verified` count). Test added.
- Real parse result on owner's 30 saved pages: faculty 150 rows / 144 with email / 141 unique; staff 225 / 218 / 207; 333 unique people. 13 listing rows have no email and are not importable.

## 2026-10-23 (calendar)
- Added: `academic_events` table + migration `d9e1b3c5a728` (verified equal to the model in a scratch DB), `AcademicEvent` model, `events` support in the importer, `app/services/calendar_answers.py` (word-matching answers, no AI), chat now answers calendar questions ("When are the midterm exams?").
- Added: `datasets/gju/calendar_2026_2027.json` (84 entries read from the official PDF; every weekday in the PDF matches its date), `tests/test_calendar.py`, API tests.
- Changed: the "not verified" note no longer claims the data came from a student (it was wrong for official data).
- Not independently verified: the wording of the entries was read from page images by hand (OCR could not read the scan). Rows stay `verified=false` until the owner compares them with the PDF.
