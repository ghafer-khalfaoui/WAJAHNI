# WAJAHNI — Project Audit (baseline)

Audit date: 2026-10-20. Source inspected: GitHub `ghafer-khalfaoui/wajahni`, single commit `0369882 first commit`, shallow clone. **The ZIP was never received**, so ZIP-vs-repo comparison was not possible.

## What exists (verified by reading and running code)
- FastAPI backend, Python (committed venv was 3.11; audit ran on 3.13). Async SQLAlchemy 2 + asyncpg, Alembic, pgvector, PyJWT + passlib/bcrypt.
- `app/main.py` mounts one router at `/api`: `POST /api/auth/register-tenant`, `POST /api/auth/login`. `GET /` returns status.
- Models: `University`, `AdminUser`, `Student`, `Document`, `DocumentChunk` (two different base classes, see WJ-007).
- `app/services/vector_store.py`: chunk (300 words) -> Gemini embedding (768-d) -> pgvector.
- Root scripts `test_vector.py`, `test_search.py`, `test_generation.py`, `check_models.py` are manual live scripts (need DB + Gemini), not automated tests.
- No frontend, no document upload/PDF parsing, no study tools, no GJU data, no Moodle, no maps, no tests, empty README.

## Baseline results (what was actually observed)
| Check | Result |
|---|---|
| Install from original `requirements.txt` | Fails to import: file is UTF-16 and omits PyJWT, passlib, bcrypt, email-validator, python-multipart, google-genai (reproduced) |
| Hash a password with original pins (bcrypt 5.0.0 + passlib 1.7.4) | Fails: `ValueError: password cannot be longer than 72 bytes` (reproduced) |
| App boot after fixes, clean venv | OK, `GET /` = 200 |
| `POST /api/v1/chat/`, `/api/chat/ask`, `/api/knowledge/ingest` | All 404 (reproduced): v1 router never mounted, other two routes do not exist |
| Alembic migration 1 on throwaway Postgres 16 | Applies; creates `universities`, `students` |
| Alembic migration 2 (pgvector) | **Not run**: sandbox Postgres has no pgvector extension; Docker daemon unavailable |
| Model-vs-migration comparison | Drift found (WJ-007) |
| DB-backed and live-Gemini behaviour | **Not tested** (no pgvector, no verified free API key) |

## Discrepancy to resolve
Saved project notes say five core tables were migrated and the next step is `app/repositories/course_repository.py`. The repo has two migrations, no `repositories/` folder, and no such file. Either local work was never pushed, or the ZIP is newer. **Provide the ZIP before further feature work.**

## Gemini and cost findings (official pages, read 2026-10-20)
See `COST_POLICY.md`. Key points: free tier exists for several text models but free-tier content is used to improve Google products; embedding free-tier status is not stated on pages read; model `gemini-3.5-flash` used in `test_generation.py` did not appear on the pricing page; a Google AI Pro subscription is not documented as including API access.

Issue details: `ISSUES.md`.
