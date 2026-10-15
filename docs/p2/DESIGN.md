# P2 implementation decision — 2026-10-15

Before implementation: P1 52/52 passed in an isolated report destination; 262 frozen hashes match. Git initial commit was attempted after reviewing 28 staged engineering files, but author identity is absent. No identity invented; no commit/push performed. Recovery snapshot: `D:/TEMP/complaint_p2_baseline_0hxiqtuk`; baseline staged diff and initial manifest are there. Research assets, .env, databases, .local and uncertain historical documents were excluded from staging.

## Authorized minimal extension

- Keep AnalysisResult and taxonomy unchanged; extend runtime DTOs with optional evidence fields. P1 config hashes remain unchanged when new optional fields are absent.
- SQLite v2 keeps the four tables. Add execution_state and metadata_json to runs. The original terminal status constraint remains; running rows internally use failed with execution_state=running. All public reads use execution_state. This avoids rebuilding foreign-key tables. Back up v1 using SQLite backup before transactional migration. Refuse unknown versions. Restore, if needed, only by explicitly selecting the backup as a different database; never overwrite a newer run database.
- Live claims are committed before HTTP. A unique live idempotency index includes failures and uncertain runs; repeated submissions reuse the record, never automatically replay an uncertain paid operation. Started attempt is committed before each request. No exactly-once claim.
- SDK retries=0, at most two attempts per logical run; JSON repair and explicit 429/5xx retries share that budget. Timeout/connection loss are uncertain and stop without automatic replay. A 45-second transport timeout and a 90-second logical async deadline are separate.
- Live adapter uses existing ChatOpenAI, a new frozen v2 system prompt, separate untrusted user input, strict JSON/Pydantic and identity normalization. No default-filled results or fallback.
- A separate durable pilot budget ledger permits only pre-frozen synthetic input hashes, 12 distinct inputs, 20 reservations (including ambiguous dispatch), CNY20, and one logical live run at a time. Reservations are never refunded. A crash leaves the global lease blocked for manual inspection. UI and CLI share the same ledger.
- Original .env and historical chain remain unchanged. P2 requires COMPLAINT_ENABLE_LIVE=true plus explicit UI selection. Offline runner overrides this and blocks sockets/tracing. Live tests are standalone scripts, never ordinary test discovery.

## Acceptance

Fake HTTP/provider tests: params, hash binding, strict JSON, metadata unknowns, 429/5xx/auth/timeout/network/empty/schema errors, shared retry limit, durable pre-call records, storage failure, concurrent duplicates, uncertain restart, budget persistence, v1 preservation, UI reload. Then historical 52 tests and frozen hashes. Only after this gate run frozen developer fixtures, smoke then semantic then actual app.py AppTest live path. Reports distinguish structure, semantics, warnings, latency, usage, estimated cost, unknown billing, and browser limitations.
