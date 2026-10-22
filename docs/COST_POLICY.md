# WAJAHNI — Cost Policy ($0 hard constraint)

No paid APIs, no billing activation, no credits, no paid hosting. Verified against official Google pages on 2026-10-20 (pricing page: first 100,000 of 132,274 characters read; billing, rate-limits and embeddings pages read).

## External dependency inventory
| Service | Used for | Verified status | Risk | Local fallback | Disable |
|---|---|---|---|---|---|
| Gemini API, text (`gemini-3.5-flash` in `test_generation.py`) | Answer generation | **Model name not on pricing page.** Free tier is listed for `gemini-3.8-flash`, `3.6-flash`, `3.5-flash-lite`, `3.1-flash-lite`. | Unknown model may be paid or retired | Local open-weight model (not yet evaluated) | Leave `GEMINI_API_KEY` empty |
| Gemini API, embeddings (`gemini-embedding-2`) | Vector search | Model exists in docs. **Free-tier status not stated** on pages read. Batch discount mentioned, no prices. | Unverified, so treat as not authorized | Local open-source embedding model (to evaluate) | Leave key empty |
| PostgreSQL + pgvector (Docker) | Storage, search | Open source, local, $0 | None | — | — |
| Python packages in `requirements.txt` | Runtime | Open source | Licences not yet reviewed | — | — |

## Facts that shape the design
1. **Free-tier content is used to improve Google products** (pricing page, every free-tier model). Therefore **never send student records, private documents or private conversations to a free-tier key.** Only public or owner-approved university text may go to Gemini free tier.
2. **Projects without a linked billing account stay on the free tier.** Linking billing is the step that enables charges (Tier 1 needs a billing account; prepay minimum $5). Never link billing to the project that owns the key.
3. Free-tier rate limits are per **project**, not per key, and vary by model; read the live values in Google AI Studio before relying on them. Do not create extra projects/accounts to get around limits.
4. The billing page does not say a Google AI Pro / Gemini-app subscription includes API access or credits. **Assume it does not.**
5. Search grounding is paid beyond 5,000 requests/month: do not enable.

## Required guards (not yet implemented, tracked as WJ-011)
Paid/unknown models rejected by a config allowlist; daily request counter and hard cap; bounded retries and timeouts; on quota exhaustion stop remote calls and use the local fallback or an "unavailable" message; never fall back to a paid model.

## Rule
If free status of an exact model/feature cannot be established from official pages, it is not used.

## Rate limits (checked 2026-10-22, official docs)
- Limits are per **project**, not per key, measured as requests/min, input tokens/min and requests/day; exceeding any gives a rate-limit error. Daily quota resets at midnight Pacific.
- Docs do not list per-model numbers; they must be read from the AI Studio "Rate limit" page for the project (owner screenshot still needed, key hidden). Until then no Gemini call is made.
- Owner deleted the exposed keys? Owner reports a new key was created and placed only in `.env`; the repo `ai-chatbot` was made private.
