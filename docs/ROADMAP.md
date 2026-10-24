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

## Long-term: universities in Germany (owner goal, 2026-10-25)
Goal: study plans and offered courses for universities in Germany, not only GJU.
- Order of work: (1) finish ALL GJU study plans first (owner decision); (2) generalise the plan pipeline so a new university is "a manifest of sources + a parser per document layout"; (3) then Germany.
- Two routes to evaluate (nothing verified yet, no code before this research): (a) an existing API/open dataset; (b) WAJAHNI builds its own data layer and exposes it as its own API (the importer + `plan_entries` model is already tenant-based, so this is the same design).
- Research checklist for (a): who publishes it (e.g. national higher-education databases and university module catalogues), licence and terms of use, whether it is free at our volume ($0 rule), update frequency, whether it contains study plans (Studienverlauf/Modulhandbuch) and per-semester course offerings (Vorlesungsverzeichnis), not only programme names. Check robots.txt/ToS before any fetching.
- Data model gaps to expect: module handbooks use ECTS and modules rather than credit hours; course offerings change every semester (needs a term dimension); several languages (German/English).
