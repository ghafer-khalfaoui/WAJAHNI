# Architecture (as found, not as planned)

Client -> FastAPI (`/api`) -> async SQLAlchemy -> PostgreSQL (+pgvector).
Ingestion (service only, no endpoint): text -> 300-word chunks -> Gemini embedding (768-d) -> `document_chunks`.
Retrieval (scripts only): cosine distance over all chunks, top 1, no tenant filter. Generation (script only): one prompt with the top chunk.
Auth: admin JWT (HS256) with `sub`, `role`, `university_id`. Students have a model but no auth flow.
Planned structure and decisions: `ROADMAP.md`, `DECISIONS.md`.
