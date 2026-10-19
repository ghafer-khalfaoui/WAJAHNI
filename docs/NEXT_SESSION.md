# Next Session — resume point

1. Read `CLAUDE.md`, `PROJECT_STATE.md`, `ISSUES.md`; run `git status`.
2. Check whether the owner supplied the ZIP; diff it against the repo before editing (WJ-016).
3. Verify: `python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest && .venv/bin/pytest tests -q`
   (tests set dummy env vars themselves; no network, no DB, no API calls).
4. Next actions in order:
   - WJ-007: one reconciled model set and a new Alembic migration (admin_users, chunk table name, `university_id` on chunks, nullable/default fixes). Test on a Postgres with pgvector (`docker compose up db` on the owner's machine).
   - WJ-006/WJ-008: implement `/api/chat/ask` with retrieval filtered by the authenticated/selected university, citations, no-evidence answer path.
   - WJ-005: restrict tenant registration.
   - WJ-011: cost guard module + config allowlist from `COST_POLICY.md`.
5. Do not call any Gemini endpoint until the free model and quota are confirmed in AI Studio.
