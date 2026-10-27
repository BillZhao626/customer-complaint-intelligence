# P3.9-R3 reproduction and recovery

Use the existing environment. The offline entry disables API/tracing, blocks sockets and prevents writes to research assets. It uses explicit temporary fixture databases. Public checkout intentionally lacks historical raw and researcher references; three private-history tests explicitly skip there.

```powershell
.\.venv\Scripts\python.exe -B tests/run_offline.py
.\.venv\Scripts\python.exe -B scripts/run_portable.py
.\.venv\Scripts\python.exe -B tests/run_offline.py test_p39_continuity.py
.\.venv\Scripts\python.exe -B tests/run_offline.py test_p39_continuity_report.py
.\.venv\Scripts\python.exe -B tests/run_offline.py test_p39_exploration.py
```

`scripts/p39_continuity.py` defaults to offline preflight. Its explicit `run` action requires the saved current-user authorization, exact frozen identities, the unique pre-existing envelope and bound offline acceptance evidence. It reconciles historical attempts and skips every previously dispatched step, including quality failures. Do not run an old API evaluation script to resume. The `status` action has no inference but installs the approved append-only continuation binding if needed; use preflight for inspection before installation.

The original three runs and database remain read-only. Continuation records go to `.local/p39/v2/r3-runtime/`; the same `.local/p39/v2/shared-envelope.sqlite3` accumulates all costs. A failed JSON/schema/safety result is not an accepted prediction or approved reply. The smoke8 engineering checkpoint includes failures and no human content signature. Later dispatch is authorized by this user's R3 instruction only.

`scripts/p39_r3_report.py --out .local/p39/r3/NEW_REPORT` creates an exclusive new report directory using read-only run connections. It performs no inference. It keeps all 64 plan positions, unknown dispatch, prepared-but-not-sent, failures, fixed historical reference denominators, token usage and unavailable invoice/human metrics separate. Raw content and the full paired report remain local and must not be included in the public Git payload.

Challenger planning/execution is a separate API in `src/application/p39_exploration.py`, after fixed completion only. The plan freezes one to six distinct approved fictional inputs, the independent Prompt and config hashes, the original B run IDs and the current authorization hash. It shares the original envelope; cumulative automatic dispatch cannot exceed 71 requests or CNY10. The final hard-cap slot is retained. Do not rebuild or clone a production allowance. The test-only budget copies are explicitly fixture-marked and cannot attach to production.

Recover by reading persisted runs, reservations, settlements, receipt hashes and global leases. A quality failure with a complete response and valid economics can continue. An engineering stop, unresolved claim, unknown send or missing durable run cannot automatically resume. Keep all evidence; never restore a budget backup over later spend or delete a claim to free capacity. Frozen Champion/earlier executables remain available as a code rollback, without reversing economic history.
