# Test Strategy

- Unit/regression tests in `tests/`, run with pytest, no network, no DB, dummy env set in `tests/conftest.py`.
- Planned: model-vs-migration drift test; migration test on Postgres+pgvector; tenant-isolation tests; mocked-provider tests for quota exhaustion; AI evaluation set (answerable, missing-evidence, conflicting sources, prompt injection).
- Live Gemini tests are opt-in only and only after the free quota is verified. Never in default runs.
