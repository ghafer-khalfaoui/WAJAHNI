# Changelog

## 2026-10-20
- Fixed: requirements encoding and missing packages; bcrypt/passlib incompatibility (WJ-003).
- Fixed: removed hard-coded JWT fallback secret; algorithm/expiry from settings (WJ-004).
- Added: `.gitignore`, `.env.example`, `tests/`, audit and policy docs.
- Changed (index only): stopped tracking `.env`, `venv/`, `__pycache__`.
