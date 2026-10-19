# Decisions

- D-001 (2026-10-20): Keep the existing FastAPI/PostgreSQL/pgvector stack; no rewrite. Reason: it matches the owner's plan and nothing in the audit shows the stack itself is wrong.
- D-002: Pin `bcrypt==4.0.1` with `passlib==1.7.4` because bcrypt 5 breaks passlib hashing (reproduced). Revisit by replacing passlib with direct `bcrypt`.
- D-003: JWT secret, algorithm and expiry come only from validated settings; no literal fallback.
- D-004: No Gemini calls until exact model + free quota are confirmed in AI Studio (see COST_POLICY).
