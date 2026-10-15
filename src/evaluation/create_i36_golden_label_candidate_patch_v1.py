from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
BASELINE_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_v1.csv"
PATCHED_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_i35_prompt_patch_v1.csv"
REMAINING_MISMATCH_CASES_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_cases_v1.csv"
I351_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_summary_v1.json"
MANUAL_REVIEW_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "deepseek_manual_review_decision_summary_v1.md"
I351_ANALYSIS_REPORT_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_analysis_report_v1.md"
I35_COMPARISON_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "deepseek_i35_prompt_patch_comparison_summary_v1.json"

CANDIDATE_PATCH_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1_candidate_patch.csv"
AUDIT_REPORT_PATH = PROJECT_ROOT / "outputs" / "golden_label_candidate_patch_audit_v1.md"
PROFILE_PATH = PROJECT_ROOT / "configs" / "evaluation" / "golden_label_candidate_patch_profile_v1.json"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_validation_report_v1.md"
METRIC_PREVIEW_REPORT_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_metric_preview_v1.md"
METRIC_PREVIEW_JSON_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_metric_preview_v1.json"

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]

CANDIDATE_CASES = ["P015", "P028", "P046"]

CANDIDATE_PATCH_ROWS = [
    {
        "email_id": "P015",
        "field": "urgency",
        "candidate_golden_value": "medium",
        "candidate_reason": (
            'I-3.5.1 indicated urgency threshold ambiguity. "called twice but no one followed up" '
            "can be medium unless long-term no response, urgent wording, or severe escalation is explicit."
        ),
        "evidence_source": "i351_remaining_mismatch_analysis",
        "issue_category": "urgency_threshold_issue",
        "confidence": "medium",
    },
    {
        "email_id": "P028",
        "field": "source_attribution",
        "candidate_golden_value": "store service issue",
        "candidate_reason": (
            "Manual review indicated the issue happened through physical store staff handling: "
            "customer visited the store and staff did not record the complaint."
        ),
        "evidence_source": "manual_review_summary",
        "issue_category": "golden_label_issue",
        "confidence": "high",
    },
    {
        "email_id": "P046",
        "field": "complaint_reason",
        "candidate_golden_value": "delivery delay",
        "candidate_reason": (
            'Manual review indicated "delivery update was confusing" is more specific than other. '
            "Current taxonomy has no exact delivery update issue, so delivery delay is the closest "
            "available complaint_reason."
        ),
        "evidence_source": "manual_review_summary",
        "issue_category": "golden_label_issue",
        "confidence": "high",
    },
    {
        "email_id": "P046",
        "field": "source_attribution",
        "candidate_golden_value": "delivery/logistics issue",
        "candidate_reason": (
            "Manual review indicated delivery update confusion points to delivery/logistics issue "
            "and should not be unclear."
        ),
        "evidence_source": "manual_review_summary",
        "issue_category": "golden_label_issue",
        "confidence": "medium",
    },
]

PATCH_FIELDNAMES = [
    "email_id",
    "field",
    "original_golden_value",
    "candidate_golden_value",
    "baseline_prediction",
    "patched_prediction",
    "candidate_reason",
    "evidence_source",
    "issue_category",
    "confidence",
    "decision_status",
    "should_apply_now",
]


def read_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {row["email_id"]: dict(row) for row in csv.DictReader(file)}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def golden_value(row: dict[str, str], field: str) -> str:
    return row.get(f"{field}_label", "")


def prediction_value(row: dict[str, str], field: str) -> str:
    return row.get(field, "")


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:400]


def build_patch_rows() -> tuple[list[dict[str, str]], dict[str, Any], dict[tuple[str, str], dict[str, str]]]:
    golden = read_csv_by_id(GOLDEN_PATH)
    baseline = read_csv_by_id(BASELINE_PREDICTION_PATH)
    patched = read_csv_by_id(PATCHED_PREDICTION_PATH)
    remaining_rows = read_csv_rows(REMAINING_MISMATCH_CASES_PATH)
    i351_summary = load_json(I351_SUMMARY_PATH)

    remaining_by_pair = {(row["email_id"], row["field"]): row for row in remaining_rows}
    output_rows: list[dict[str, str]] = []

    for candidate in CANDIDATE_PATCH_ROWS:
        email_id = candidate["email_id"]
        field = candidate["field"]
        if email_id not in golden:
            raise ValueError(f"Candidate email_id not found in golden labels: {email_id}")
        if email_id not in baseline:
            raise ValueError(f"Candidate email_id not found in baseline predictions: {email_id}")
        if email_id not in patched:
            raise ValueError(f"Candidate email_id not found in patched predictions: {email_id}")

        output_rows.append(
            {
                "email_id": email_id,
                "field": field,
                "original_golden_value": golden_value(golden[email_id], field),
                "candidate_golden_value": candidate["candidate_golden_value"],
                "baseline_prediction": prediction_value(baseline[email_id], field),
                "patched_prediction": prediction_value(patched[email_id], field),
                "candidate_reason": candidate["candidate_reason"],
                "evidence_source": candidate["evidence_source"],
                "issue_category": candidate["issue_category"],
                "confidence": candidate["confidence"],
                "decision_status": "needs_human_confirmation",
                "should_apply_now": "false",
            }
        )

    return output_rows, i351_summary, remaining_by_pair


def write_candidate_patch(rows: list[dict[str, str]]) -> None:
    CANDIDATE_PATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATE_PATCH_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PATCH_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_audit_report(
    rows: list[dict[str, str]],
    i351_summary: dict[str, Any],
    remaining_by_pair: dict[tuple[str, str], dict[str, str]],
    golden_sha256: str,
) -> None:
    issue_counts = Counter(row["issue_category"] for row in rows)
    confidence_counts = Counter(row["confidence"] for row in rows)

    lines = [
        "# I-3.6 Golden Label Candidate Patch and Audit Trail",
        "",
        "## Stage And Purpose",
        "",
        "I-3.6 creates candidate-only golden label review artifacts for P015, P028, and P046 after the I-3.5.1 remaining mismatch analysis.",
        "The purpose is to preserve an audit trail from original golden labels to candidate label changes, reasons, evidence basis, and a secondary metric preview.",
        "",
        "## Baseline Preservation",
        "",
        "The original `data/golden/golden_labels_pilot_v1.csv` is not overwritten. It remains the baseline reference for the pilot evaluation.",
        "Policy: do not overwrite the original golden label file during I-3.6.",
        "Candidate labels are stored separately and every row has `should_apply_now=false` with `decision_status=needs_human_confirmation`.",
        f"- Original golden label SHA256: `{golden_sha256}`",
        "",
        "## Inputs Used",
        "",
        f"- Original golden labels: `{GOLDEN_PATH}`",
        f"- Baseline predictions: `{BASELINE_PREDICTION_PATH}`",
        f"- I-3.5 patched prompt predictions: `{PATCHED_PREDICTION_PATH}`",
        f"- I-3.5.1 remaining mismatch cases: `{REMAINING_MISMATCH_CASES_PATH}`",
        f"- I-3.5.1 summary: `{I351_SUMMARY_PATH}`",
        f"- I-3.5.1 analysis report: `{I351_ANALYSIS_REPORT_PATH}`",
        f"- Manual review summary: `{MANUAL_REVIEW_SUMMARY_PATH}`",
        f"- I-3.5 comparison summary: `{I35_COMPARISON_SUMMARY_PATH}`",
        "",
        "## I-3.5.1 Relationship",
        "",
        f"- Remaining mismatches after I-3.5: {i351_summary.get('patched_mismatch_count')}",
        f"- Regressions: {i351_summary.get('regression_count')}",
        f"- Improved field-level cases: {i351_summary.get('improved_count')}",
        "- Candidate cases for I-3.6 are P015, P028, and P046.",
        "",
        "Relationship to I-3.5.1 categories:",
        "",
        "- `golden_label_issue`: label may be too broad, conservative, or inconsistent with project taxonomy.",
        "- `taxonomy_ambiguity`: boundary is unclear and should inform taxonomy rules before label changes.",
        "- `model_error`: model or prompt behavior should be improved rather than changing the golden label.",
        "- `urgency_threshold_issue`: medium versus high urgency needs explicit threshold review.",
        "",
        "## Candidate Cases Reviewed",
        "",
        "- P015",
        "- P028",
        "- P046",
        "",
        "## Candidate Patch Table",
        "",
        "| Email ID | Field | Original golden value | Candidate golden value | Baseline prediction | Patched prediction | Issue category | Confidence | Decision status | Should apply now | Reason |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {md_cell(row['email_id'])} | {md_cell(row['field'])} | {md_cell(row['original_golden_value'])} | "
            f"{md_cell(row['candidate_golden_value'])} | {md_cell(row['baseline_prediction'])} | "
            f"{md_cell(row['patched_prediction'])} | {md_cell(row['issue_category'])} | {md_cell(row['confidence'])} | "
            f"{md_cell(row['decision_status'])} | {md_cell(row['should_apply_now'])} | {md_cell(row['candidate_reason'])} |"
        )

    lines.extend(["", "## Per-case Reasoning", ""])
    for case_id in CANDIDATE_CASES:
        case_rows = [row for row in rows if row["email_id"] == case_id]
        lines.append(f"### {case_id}")
        lines.append("")
        if not case_rows:
            lines.append("No candidate patch row was recommended for this case in I-3.6.")
            lines.append("")
            continue
        for row in case_rows:
            mismatch = remaining_by_pair.get((row["email_id"], row["field"]), {})
            lines.append(
                f"- `{row['field']}`: original `{row['original_golden_value']}` -> candidate `{row['candidate_golden_value']}`. "
                f"Baseline prediction `{row['baseline_prediction']}`, patched prediction `{row['patched_prediction']}`. "
                f"Evidence source `{row['evidence_source']}`. Reason: {row['candidate_reason']}"
            )
            if mismatch:
                lines.append(
                    f"  I-3.5.1 categorized this as `{mismatch.get('preliminary_issue_category')}` with recommended action `{mismatch.get('recommended_next_action')}`."
                )
        lines.append("")

    lines.extend(
        [
            "## Candidate Golden Label Issues",
            "",
        ]
    )
    for row in rows:
        if row["issue_category"] == "golden_label_issue":
            lines.append(f"- {row['email_id']} `{row['field']}`: candidate `{row['candidate_golden_value']}`.")
    lines.extend(["", "## Taxonomy Ambiguity / Threshold Ambiguity", ""])
    lines.append("- P015 `urgency`: recorded as `urgency_threshold_issue`; the candidate medium label still needs human confirmation.")
    lines.append("- P015 `source_attribution`: reviewed as taxonomy_ambiguity and not recommended for a label patch in I-3.6.")
    lines.append("- Source attribution boundaries remain sensitive for customer service response issue versus store service issue.")

    lines.extend(["", "## Fields Not Recommended For Label Patch", ""])
    lines.append("- P015 `source_attribution`: I-3.5.1 marked it as taxonomy_ambiguity, and earlier manual review said the original customer service response label is reasonable.")
    lines.append("- P046 `sentiment`: no I-3.6 patch row is proposed because the I-3.5 patched prediction already matches the current golden label.")
    lines.append("- P015/P028 `store_location` and P028 `product_category`: treated as model or prompt extraction/classification issues already improved by I-3.5, not golden-label changes.")

    lines.extend(["", "## Human Confirmation Required", ""])
    lines.append("Every candidate row has `decision_status=needs_human_confirmation` and `should_apply_now=false`.")
    lines.append("These candidate labels are not final and should not replace the active golden label file without explicit review approval.")

    lines.extend(["", "## Audit Trail", ""])
    lines.append("Audit trail preserved in this stage:")
    lines.append("")
    lines.append("1. Original golden labels remain in `data/golden/golden_labels_pilot_v1.csv`.")
    lines.append("2. Candidate changes are stored in `data/golden/golden_labels_pilot_v1_candidate_patch.csv`.")
    lines.append("3. Reasons and evidence sources are recorded per candidate row.")
    lines.append("4. Candidate labels are applied only in memory by the metric preview script.")
    lines.append("5. The preview is a secondary analysis and not official final evaluation.")

    lines.extend(
        [
            "",
            "## Candidate Patch Summary",
            "",
            f"- Candidate patch rows: {len(rows)}",
            f"- Issue category counts: {dict(issue_counts)}",
            f"- Confidence counts: {dict(confidence_counts)}",
            "",
            "## Risks",
            "",
            "- Overfitting to 50 pilot cases.",
            "- Weakening evaluation by changing labels too aggressively.",
            "- Source_attribution boundary ambiguity.",
            "- Urgency threshold ambiguity.",
            "",
            "## Recommendation",
            "",
            "- Keep original labels as baseline reference.",
            "- Use candidate patch only for review and optional secondary metric preview.",
            "- Do not expand to 300-500 until candidate labels are reviewed.",
            "",
        ]
    )
    AUDIT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_profile() -> None:
    profile = {
        "version": "v1",
        "stage": "I-3.6",
        "purpose": "Candidate-only golden label patch and audit trail for reviewed I-3.5.1 cases; original golden labels are not overwritten.",
        "original_golden_file": str(GOLDEN_PATH),
        "candidate_patch_file": str(CANDIDATE_PATCH_PATH),
        "audit_report": str(AUDIT_REPORT_PATH),
        "metric_preview_report": str(METRIC_PREVIEW_REPORT_PATH),
        "metric_preview_json": str(METRIC_PREVIEW_JSON_PATH),
        "validation_report": str(VALIDATION_REPORT_PATH),
        "candidate_cases": CANDIDATE_CASES,
        "candidate_patch_policy": {
            "do_not_overwrite_original": True,
            "needs_human_confirmation": True,
            "use_for_secondary_metric_preview_only": True,
            "should_apply_now_false_required": True,
        },
        "recommended_next_stage": [
            "human_review_candidate_patch",
            "decide_whether_to_accept_candidate_labels",
            "then expand_dataset_or_refine_prompt",
        ],
    }
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    rows, i351_summary, remaining_by_pair = build_patch_rows()
    golden_sha256 = sha256_file(GOLDEN_PATH)
    write_candidate_patch(rows)
    write_audit_report(rows, i351_summary, remaining_by_pair, golden_sha256)
    write_profile()

    print("I-3.6 golden label candidate patch generated.")
    print(f"Candidate patch rows: {len(rows)}")
    print(f"Candidate patch saved to: {CANDIDATE_PATCH_PATH}")
    print(f"Audit report saved to: {AUDIT_REPORT_PATH}")
    print(f"Profile saved to: {PROFILE_PATH}")
    print(f"Original golden label SHA256: {golden_sha256}")


if __name__ == "__main__":
    main()
