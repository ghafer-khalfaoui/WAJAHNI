# Decisions

- D-001 (2026-10-20): Keep the existing FastAPI/PostgreSQL/pgvector stack; no rewrite. Reason: it matches the owner's plan and nothing in the audit shows the stack itself is wrong.
- D-002: Pin `bcrypt==4.0.1` with `passlib==1.7.4` because bcrypt 5 breaks passlib hashing (reproduced). Revisit by replacing passlib with direct `bcrypt`.
- D-003: JWT secret, algorithm and expiry come only from validated settings; no literal fallback.
- D-004: No Gemini calls until exact model + free quota are confirmed in AI Studio (see COST_POLICY).
- D-005 (2026-10-25): The chatbot serves all students, so no per-student admission-year question. While only one plan version can be stored, always load the NEWEST official study plan of a program (CS: 2023/2024) and ignore versions older than two years. Owner decision. Revisit when `plan_version` support is added (WJ-024).
- D-006 (2026-10-25): Priority order set by the owner: all GJU study plans first, German universities later (API or own data layer, see ROADMAP). GJU plans: undergraduate regular plans first, dual-study variants second; graduate programs later; newest version per program (D-005).
