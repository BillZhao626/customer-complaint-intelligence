# P3.9-R3 verification and experimental outcome

2026-10-17, Asia/Shanghai. Fixed A/B collection is complete. The execution-continuity engineering fix is verified; semantic improvement of the independent Prompt candidate is **not demonstrated**.

## Frozen comparison and append-only execution

The starting HEAD was `f0a5eb71e7a46c036700f1d406cc3b34b680ff07`. The approved manifest remains `9a0e63fb494b7e926ac890438155ada2fb730953ba82b26c74a5a06eaf8b499b`, profile `urgency-context-evidence-v1`, A Prompt `872162575df43d0a81edef6c40882b7d7112e49604ee035750f2321707c2ac44`, B Prompt `a4ecfaa52c37103a5dcd1544240f55c566be0adaa433132848a9c12a90c7027a`. Frozen prediction/validation/transport modules and inputs were not changed.

New `evaluation-continuity-v1` runtime identity: `9fc19c9b371737a9602ee517382b7e3cc8ab8634242db94740ad28714adb22d9`. It keeps quality rejection as a failed result, saves a linked read-only diagnosis and continues the fixed schedule. It stops on unknown dispatch, wrong identity, invalid usage/economics, missing persistence or global locks. No retry, fallback, field repair or failed-to-success conversion is used.

The original three v2 requests were reconciled and never resent. The remaining 61 were written to a separate database. The sole existing envelope retains its original root, approvals, historical stop and spend. Appended continuity authority acknowledges the old quality stop without manufacturing human content approval. The eight-attempt checkpoint was 4 accepted / 4 rejected, safe for the authorized experiment continuation; its receipt is `780a01b2201773a44cc5136f59b4eb406278463a616b97b4f1b4d30ad90324e3`.

## Fixed A/B denominators

All 32 inputs are exposed fictional development data. The original 24 researcher-approved references remain unchanged; the other eight inputs have no independent semantic Gold.

|Measure|A|B|Combined|
|---|---:|---:|---:|
|Fixed planned requests|32|32|64|
|Actual responses / attempted requests|32|32|64|
|Formally accepted|17|17|34|
|Rejected predictions|15|15|30|
|Unknown dispatch / infrastructure-blocked / unattempted|0|0|0|
|Historical seven-field agreement, fixed 168 per arm|90/168|82/168|Different policy/projection from old v1.1 reference|
|Historical all-seven agreement, fixed 24 per arm|12/24|10/24|Development consistency, not independent accuracy|
|Provider p50, n=32 each|3.900 s|3.770 s|No production SLO claim|
|Provider p95, n=32 each|6.811 s|4.993 s|Includes original retained requests|
|Tokens|142,754|161,095|303,849|
|Peak cache-miss cost upper estimate, CNY|0.410662|0.439310|0.849972|

There are 32 complete attempted pairs: 14 both accepted, 12 both rejected, 3 A-only accepted and 3 B-only accepted. B has no observed acceptance advantage. All 64 strict JSON parses passed; 61/64 passed the published wire JSON Schema shape; only 34/64 passed the full model/source/business acceptance chain. Earliest rejection stages were Pydantic structure/cross-field validation 9 and source/semantic validation 21. JSON or Schema shape is not semantic correctness.

Failed predictions contribute zero formally available fields to the fixed historical-reference comparison. The report exposes each expected/actual field and the unchanged denominator; no accepted-only overall accuracy is claimed. Policy v2 urgency, safe uncertainty projection, mixed sentiment, billing/size projection and complaint-state changes limit comparison with old references. Issue-level and evidence semantic accuracy, human summary/reply scores and human semantic winners are null.

## Causal and semantic evidence

The same 44 historical raws were replayed read-only across explicit old/current implementations. Original states and P3.6 results (143/168 fields, 17/24 emails, 29/32 draft-v3 acceptance) remain intact. See [root cause and ownership](ROOT_CAUSE_OWNERSHIP.md).

The 64 fixed outputs have 1,152 assistant-authored 18-dimension candidate observations. The six Challenger raws have 108 separate observations. Each binds run/input/raw identity; all human scores remain null. Partition vocabularies are preserved, so descriptive candidate counts are not calibrated severity scores or inter-rater agreement. No separate paid DeepSeek Judge was called.

Observed mechanisms include incorrect general_help/repeated_failure, customer importance versus handling order, custody versus delay/responsibility, bounded evidence vocabulary, empty required fields, duplicate issue evidence, reply language, unverified future actions and resolved-versus-relaxed meaning. Some apparent repeated-failure rejections are **validator false-rejection candidates**: semantically supporting evidence can miss a finite lexical pattern. Rejection totals are acceptance outcomes, not proof that all 30 were model semantic defects. Accepted outputs also retain content risks.

## Independent Challenger, negative result

The independent candidate retains the original B validator, Schema and safety gates and adds generic fact/ownership Prompt instructions. After fixed completion, six distinct approved inputs were selected for observed mechanisms plus one correctly accepted severe-risk anchor. Its installed plan is `6b173b21d4be11b67a9f2f015f965c0b7329be167e43d7333bed7a54992bb0ef`; Prompt SHA is `080c53abf1b44181ffb1c1418bc1ba6f66a889efa553bf8f675cfb5f4490239c`.

The selected original B outputs were 1/6 accepted; Challenger was 0/6. Partial raw improvements in basis/customer-importance/channel wording did not remove rejection. Existing basis and state defects persisted, and an empty required store field rejected the severe-risk anchor although its severe/high assessment and safety advice remained intact. This is an observed exploratory regression in formal acceptance, not proof of Prompt causality or a population effect. Different call times and unavailable weight snapshots remain limitations. The candidate is not promoted and no further calls are authorized automatically.

## Shared economics and hard stop boundary

The single original envelope contains 1 historical v1 + 64 fixed A/B + 6 exploratory requests = **71**, with one hard-cap slot retained. All 71 have usage receipts and settled sends; zero unknown dispatch, retries or fallback. Conservative reservation is **CNY3.058708** against CNY10. The old summary's planned combined ceiling 65 refers to the historical-plus-fixed plan; the appended exploratory authority separately enforces automatic ceiling 71 and at most six new requests, without modifying the old root.

Observed cumulative tokens are **343,136**. Applying the verified peak cache-miss rates gives **CNY0.959884 upper estimate**; the actual account invoice remains unavailable/null. The official price page was rechecked and matched the saved receipt. Cache/time-of-day discounts mean this estimate is not the account bill. [Official pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).

## Engineering regression, asset protection and delivery

The final complete offline suite passed **329/329** with no skips. All original 290 test IDs remain. Public clean-export verification passed 230 tests with 3 explicit private-history skips (233 total before the last reporting/identity supplements); final Git/CI receipt identifies the exact delivered commit and current portable result. The final reporting supplement passed four tests after a descriptive-label handling refinement.

Fault injection covers malformed JSON, schema and reply-gate rejection continuing to B, 64 mixed-outcome attempts, eight-output checkpoint, restart with no resend, locks after uncertain sends, wrong model/usage/payload, persistence faults, shared caps and six-call exploration. New fixtures cover arbitrary JSON failure reports, prepared-not-sent denominators, exact unsigned-review binding and rehashed Challenger-plan identity rejection before any send. Offline review caught and fixed report type handling/counting and Challenger-plan binding bugs before those affected paid execution.

Baseline protection covers 4,380 files, including untracked assets. The original data, outputs, Gold/references, P3.6, v1/v2 raws and prior run databases stay unchanged; only the shared envelope appends authorized records. Row-level recovery audit retains every original envelope row. The actual `.env` remains unchanged. All replies are unreviewed and unsent.

Only engineering source, explicit synthetic fixtures and redacted documentation are eligible for Git. Full raw, semantic review packets, researcher references, recovery budget and credentials remain local. A normal branch is used; no force push, history rewrite, Tag or Release. The final local entry is `.local/p39/r3/REPORT.md`, paired review `.local/p39/r3/fixed-report-delivery/REVIEW.html`, budget receipt `.local/p39/r3/budget-receipt-final.json`, and Git/CI receipt `.local/p39/r3/git-delivery.json`.

Independent Human Gold/holdout and human content approval remain pending. See [next milestones](NEXT_PHASE.md) and [reproduction/recovery](REPRODUCE.md).
