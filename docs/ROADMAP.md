# Roadmap (adapted from the audit)

| Phase | Goal | Exit criteria |
|---|---|---|
| 1 Audit | Done | Audit, issues, cost policy, state saved |
| 2 Stabilize | Fix WJ-001 (owner action), WJ-005, WJ-007, WJ-009, WJ-014 | Clean DB from `alembic upgrade head`; models match migrations (test); secrets rotated |
| 3 AI core | Chat endpoint, provider abstraction, cost guard, local-model evaluation | Mocked-provider tests pass; quota exhaustion handled; no paid fallback |
| 4 Knowledge | Ingestion (txt/PDF), versioning, per-tenant retrieval, citations | Cross-tenant leakage test passes; "no evidence" path tested |
| 5 GJU | Verified GJU data (calendar, courses, contacts) | Every answer cites a stored source |
| 6 Study tools | Summaries, flashcards, quizzes from course content | Generated from stored content only |
| 7 Guidance | Source-backed university comparison | Official sources with dates |
| 8 UI | Frontend (none exists yet) | Real, connected flows; accessibility checks |
| 9 Security | AuthZ, privacy, dependency review | Tests for unauthorized access |
| 10 Release | Reproducible local install, backups | Fresh-machine install verified |
