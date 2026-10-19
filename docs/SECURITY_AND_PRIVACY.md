# Security and Privacy (baseline)

## Findings so far
- Secrets committed to a public repo (WJ-001). Rotate JWT secret and DB password; purging history needs owner authorization and a force-push or repo recreation.
- Open tenant registration (WJ-005); no tenant filter in retrieval (WJ-008).
- Admin token carries `university_id`, which is the right mechanism, but nothing enforces it on data access yet.
- Passwords: bcrypt via passlib (works with `bcrypt==4.0.1`). No login rate limiting. Passwords over 72 bytes are not handled.

## Privacy rules
- Student data stays local. Free-tier Gemini may use submitted content to improve Google products, so only public/approved institutional text may be sent to it.
- Logs must not contain secrets or student records.
- Data inspection/deletion and retention rules: not designed yet.

## Not yet assessed
Prompt-injection tests, upload validation (no upload exists), dependency vulnerability scan.
