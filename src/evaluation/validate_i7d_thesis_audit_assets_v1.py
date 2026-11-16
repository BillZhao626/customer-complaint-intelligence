"""Validate I-7D thesis full-scope audit assets.

This validator is intentionally read-only except for writing its validation
report. It does not call APIs, run model inference, or touch datasets.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "docs/dissertation/thesis_full_scope_audit_report_v1.md",
    "docs/dissertation/thesis_claim_evidence_trace_v1.md",
    "docs/dissertation/thesis_figure_table_gap_check_v1.md",
    "docs/dissertation/thesis_reference_verification_todo_v1.md",
    "docs/dissertation/thesis_revision_action_list_v1.md",
    "docs/dissertation/thesis_supervisor_review_readiness_summary_v1.md",
    "configs/dissertation/thesis_full_scope_audit_profile_v1.json",
    "src/evaluation/validate_i7d_thesis_audit_assets_v1.py",
]

AUDIT_REQUIRED_PHRASES = [
    "80-case reviewed golden test set",
    "formal field accuracy",
    "88.21%",
    "400-row full pool",
    "dashboard/batch/system evidence",
    "I-4G 400/400",
    "I-4E.4 secondary interpretation",
    "product_category",
]

REPORT_PATH = ROOT / "outputs/i7d_thesis_full_scope_audit_validation_report_v1.md"
ORIGINAL_DRAFT = ROOT / "docs/dissertation/thesis_full_draft_academic_rewrite_v1.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        checks.append((f"exists: {relative_path}", path.exists(), str(path)))

    profile_path = ROOT / "configs/dissertation/thesis_full_scope_audit_profile_v1.json"
    profile = None
    try:
        profile = json.loads(read_text(profile_path))
        checks.append(("profile JSON is valid", True, profile_path.as_posix()))
    except Exception as exc:  # noqa: BLE001 - report validation failure clearly
        checks.append(("profile JSON is valid", False, f"{profile_path}: {exc}"))

    if profile is not None:
        checks.append(("profile stage == I-7D", profile.get("stage") == "I-7D", str(profile.get("stage"))))

    audit_report = ROOT / "docs/dissertation/thesis_full_scope_audit_report_v1.md"
    if audit_report.exists():
        audit_text = read_text(audit_report)
        for phrase in AUDIT_REQUIRED_PHRASES:
            checks.append((f"audit report contains: {phrase}", phrase in audit_text, phrase))
    else:
        audit_text = ""

    i7d_docs = [
        ROOT / "docs/dissertation/thesis_full_scope_audit_report_v1.md",
        ROOT / "docs/dissertation/thesis_claim_evidence_trace_v1.md",
        ROOT / "docs/dissertation/thesis_figure_table_gap_check_v1.md",
        ROOT / "docs/dissertation/thesis_reference_verification_todo_v1.md",
        ROOT / "docs/dissertation/thesis_revision_action_list_v1.md",
        ROOT / "docs/dissertation/thesis_supervisor_review_readiness_summary_v1.md",
    ]
    ref_hits: list[str] = []
    for path in i7d_docs:
        if path.exists() and "[REF-" in read_text(path):
            ref_hits.append(path.as_posix())
    checks.append(("no [REF-...] placeholders introduced in I-7D docs", not ref_hits, ", ".join(ref_hits)))

    checks.append(("original academic rewrite draft still exists", ORIGINAL_DRAFT.exists(), ORIGINAL_DRAFT.as_posix()))

    protected_paths = [
        "data/synthetic/customer_emails_full_v1.csv",
        "data/golden/golden_labels_full_auto_v1.csv",
        "data/golden/golden_labels_review_sample_v1_reviewed.csv",
        "app.py",
        "src/chains/langchain_complaint_chain.py",
        "src/chains/mock_complaint_chain.py",
    ]
    for relative_path in protected_paths:
        path = ROOT / relative_path
        checks.append((f"protected file still exists: {relative_path}", path.exists(), str(path)))

    passed = all(result for _, result, _ in checks)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# I-7D Thesis Full-Scope Audit Validation Report v1",
        "",
        f"Result: {'PASS' if passed else 'FAIL'}",
        "",
        "This validation checks only I-7D documentation assets. It does not call DeepSeek API, run inference, rerun evaluation, or modify datasets, golden labels, app code, chain files, prompt files, taxonomy files, parser/schema/API configuration, .env, or secrets.",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for name, result, detail in checks:
        status = "PASS" if result else "FAIL"
        detail = detail.replace("|", "\\|")
        lines.append(f"| {name} | {status} | {detail} |")

    lines.extend(
        [
            "",
            "## Boundary Confirmation",
            "",
            "- The 80-case reviewed golden test set remains the formal model evaluation source.",
            "- The formal field accuracy remains 88.21% from I-4E.2.",
            "- The 400-row full pool remains dashboard/batch/system evidence, not formal accuracy.",
            "- I-4G 400/400 DeepSeek API success remains batch stability evidence, not accuracy.",
            "- I-4E.4 secondary interpretation for product_category normalization does not replace I-4E.2.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if passed:
        print("PASS: I-7D thesis full-scope audit validation passed.")
        return 0
    print("FAIL: I-7D thesis full-scope audit validation failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
