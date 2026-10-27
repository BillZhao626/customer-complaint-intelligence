# P3.10 reproduction and rollback

Default verification is offline. Do not rerun old API scripts or recreate a budget.

```powershell
python -B tests/run_offline.py
python -B scripts/run_portable.py
python -B tests/run_offline.py 'test_p310*.py'
python -B scripts/p310.py audit --out .local/p310/NEW_EXCLUSIVE_AUDIT
```

The first two commands block network and protected research writes. Public
checkout uses explicit fixtures; unavailable private historical tests skip with
a stated reason. A new audit directory is required, and original statuses stay
unchanged. Audit needs the private64 report and reading notes retained locally.

Local canonical evidence:

| Item | Path under `.local/p310/` |
|---|---|
| Original task / explicit180-CNY30 approval |`user-task.txt`, `authorization.json`|
| Initial assets/Git identity |`baseline-files.json`, `baseline-git.json`|
| Official price/model receipt |`official-price-model-receipt.json`|
| Full64, rejected30, accepted34, pairs |`audit-v3-final/`|
| Reverified earlier44 raw causal baselines |`historical44-causal-reverified.json`|
| Same-raw recovery diagnostics |`validator-v3-same-raw-differential-final.json`|
| D1 / D2 frozen source + plans |`development-candidate-v1-final/`, `development-candidate-v2/`|
| C3 correction source / development workflow |`development-candidate-v3-final/`, `dev-v3-workflow.json`|
| Candidate freeze before authoring |`CANDIDATE_FREEZE.json`|
| New40 source / provenance / reference separation |`new40-v1/`|
| New40 initial / corrected / combined results |`new40-initial-report/`, `new40-correction-report/`, `new40-workflow-final.json`|
| Full source and content review |`FINAL_REVIEW_V2/`|
| Lifetime economics / run receipts |`envelope.sqlite3`, `FINAL_METRICS.json`|
| Immutable experiment runtimes |`runtime-<plan_hash>/`|
| Final asset/source/Git/CI receipts |`protection-final.json`, `evidence-manifest.json`, `git-delivery.json`|

Each of the five executed plans has a unique identity. Each real request has one
run and one attempt; corrected runs bind the exact failed parent's run/raw hashes.
Development C3 explicitly reuses D1 initials; new40 uses fresh80 initial requests.
The last23 corrections are chosen by frozen input order, not retrospectively by
success.14 additional rejected initials were not corrected. All failures remain.

`scripts/p310.py preflight --plan <saved-plan>` checks current sources and payload
bounds without creating provider clients or funding. Earlier source revisions
must be inspected with their archived source/dependency identities; do not edit
their manifest hashes to force current-source verification. Current generation
is D1 plus the frozen C3 correction protocol; D2 is retained as a failed version.

The180-request ledger is halted, not resettable. The `run` CLI requires the
canonical envelope and a source-bound engineering receipt and will reject new
dispatch. Never copy this ledger to obtain more allowance or consume the old
P3.9 final request. Any later paid work needs a new explicitly approved envelope
and new experimental identity. Code rollback does not roll back economic events.
Long-term audit uses the exported JSON receipts or SQLite opened with `mode=ro`
and `PRAGMA query_only=ON`; the dispatch budget adapter also enforces current
price freshness, so do not edit an old approval to make it a report reader.

The `audit` CLI preserves v2 diagnostics for reproducibility. The tighter v3
diagnostic is `src.domain.analysis_v31_recovery_scoped.ScopedRecoveryAnalysisV31`,
with its separately identified same-raw receipt; neither is the paid acceptance
profile. Do not silently substitute v3 for a historical result.

No candidate was enabled in the default UI. Rollback means keeping Champion and
old profiles as defaults; experimental source and evidence remain reproducible.
Do not delete negative results, relabel references, sign assistant opinions as
human Gold, or present drafts as actually sent. Future work should target robust
missing-field generation and source-grounded risk/complaint status rather than
another unmeasured prompt appendix; independently annotate new data before making
thesis accuracy or generalization claims.
