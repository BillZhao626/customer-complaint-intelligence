from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASELINE_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_v1.csv"
PATCHED_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_i35_prompt_patch_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
COMPARISON_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "deepseek_i35_prompt_patch_comparison_summary_v1.json"
MANUAL_REVIEW_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "deepseek_manual_review_decision_summary_v1.md"

REMAINING_MISMATCH_CASES_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_cases_v1.csv"
REGRESSION_CASES_PATH = PROJECT_ROOT / "outputs" / "i351_regression_cases_v1.csv"
IMPROVED_CASES_PATH = PROJECT_ROOT / "outputs" / "i351_improved_cases_v1.csv"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_summary_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_analysis_report_v1.md"

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]

MANUAL_REVIEW_CASES = ["P007", "P015", "P028", "P046", "P050"]

KNOWN_REVIEW_DECISIONS = {
    ("P015", "urgency"): ("urgency_threshold_issue", "golden_label_candidate_review"),
    ("P015", "source_attribution"): ("taxonomy_ambiguity", "taxonomy_rule_review"),
    ("P028", "source_attribution"): ("golden_label_issue", "golden_label_candidate_review"),
    ("P046", "complaint_reason"): ("golden_label_issue", "golden_label_candidate_review"),
    ("P046", "source_attribution"): ("golden_label_issue", "golden_label_candidate_review"),
    ("P050", "is_complaint"): ("model_error", "prompt_followup_needed"),
    ("P050", "source_attribution"): ("taxonomy_ambiguity", "taxonomy_rule_review"),
}


def read_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {row["email_id"]: dict(row) for row in csv.DictReader(file)}


def normalize(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def golden_value(row: dict[str, str], field: str) -> str:
    return row.get(f"{field}_label", "")


def classify_issue(email_id: str, field: str, golden_label: str, baseline_prediction: str, patched_prediction: str) -> tuple[str, str]:
    if (email_id, field) in KNOWN_REVIEW_DECISIONS:
        return KNOWN_REVIEW_DECISIONS[(email_id, field)]

    golden = normalize(golden_label)
    patched = normalize(patched_prediction)
    baseline = normalize(baseline_prediction)

    if field == "store_location":
        if patched in golden or golden in patched:
            return "normalization_issue", "no_action"
        return "normalization_issue", "prompt_followup_needed"

    if field == "urgency":
        if {golden, patched} == {"medium", "high"}:
            return "urgency_threshold_issue", "taxonomy_rule_review"
        return "model_error", "prompt_followup_needed"

    if field == "is_complaint":
        return "model_error", "prompt_followup_needed"

    if field == "sentiment":
        if {golden, patched} <= {"neutral", "negative"}:
            return "taxonomy_ambiguity", "golden_label_candidate_review"
        return "model_error", "prompt_followup_needed"

    if field == "complaint_reason":
        if golden == "other" and patched not in {"", "other", "none"}:
            return "golden_label_issue", "golden_label_candidate_review"
        overlap_terms = ["refund", "after-sales", "after sales", "customer service", "delivery"]
        if any(term in golden or term in patched or term in baseline for term in overlap_terms):
            return "taxonomy_ambiguity", "taxonomy_rule_review"
        return "needs_human_review", "golden_label_candidate_review"

    if field == "source_attribution":
        if golden == "unclear" and patched not in {"", "unclear", "none"}:
            return "golden_label_issue", "golden_label_candidate_review"
        overlap_terms = ["refund", "exchange", "store service", "customer service", "delivery", "product"]
        if any(term in golden or term in patched or term in baseline for term in overlap_terms):
            return "taxonomy_ambiguity", "taxonomy_rule_review"
        return "needs_human_review", "golden_label_candidate_review"

    if field == "product_category":
        return "model_error", "prompt_followup_needed"

    return "needs_human_review", "golden_label_candidate_review"


def classify_status(baseline_correct: bool, patched_correct: bool) -> str:
    if not baseline_correct and patched_correct:
        return "improved"
    if baseline_correct and not patched_correct:
        return "regressed"
    if not baseline_correct and not patched_correct:
        return "still_mismatch"
    return "unchanged_correct"


def build_rows() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    baseline = read_csv_by_id(BASELINE_PREDICTION_PATH)
    patched = read_csv_by_id(PATCHED_PREDICTION_PATH)
    golden = read_csv_by_id(GOLDEN_PATH)
    common_ids = sorted(set(baseline) & set(patched) & set(golden))

    remaining_rows: list[dict[str, str]] = []
    regression_rows: list[dict[str, str]] = []
    improved_rows: list[dict[str, str]] = []
    all_status_counts = Counter()
    remaining_field_counts = Counter()
    regression_field_counts = Counter()
    issue_category_counts = Counter()
    action_counts = Counter()

    for email_id in common_ids:
        for field in FIELDS:
            golden_label = golden_value(golden[email_id], field)
            baseline_prediction = baseline[email_id].get(field, "")
            patched_prediction = patched[email_id].get(field, "")
            baseline_correct = normalize(baseline_prediction) == normalize(golden_label)
            patched_correct = normalize(patched_prediction) == normalize(golden_label)
            status = classify_status(baseline_correct, patched_correct)
            all_status_counts[status] += 1

            issue_category, next_action = classify_issue(email_id, field, golden_label, baseline_prediction, patched_prediction)
            row = {
                "email_id": email_id,
                "field": field,
                "golden_label": golden_label,
                "baseline_prediction": baseline_prediction,
                "patched_prediction": patched_prediction,
                "status": status,
                "preliminary_issue_category": issue_category,
                "recommended_next_action": next_action if status != "unchanged_correct" else "no_action",
                "heuristic_note": "Preliminary heuristic classification; not final human review.",
            }

            if status in {"regressed", "still_mismatch"}:
                remaining_rows.append(row)
                remaining_field_counts[field] += 1
                issue_category_counts[issue_category] += 1
                action_counts[row["recommended_next_action"]] += 1
            if status == "regressed":
                regression_rows.append(row)
                regression_field_counts[field] += 1
            if status == "improved":
                improved_rows.append(row)

    summary = {
        "stage": "I-3.5.1",
        "baseline_prediction_file": str(BASELINE_PREDICTION_PATH),
        "patched_prediction_file": str(PATCHED_PREDICTION_PATH),
        "golden_label_file": str(GOLDEN_PATH),
        "compared_fields": FIELDS,
        "total_field_comparisons": len(common_ids) * len(FIELDS),
        "baseline_mismatch_count": all_status_counts["improved"] + all_status_counts["still_mismatch"],
        "patched_mismatch_count": len(remaining_rows),
        "improved_count": len(improved_rows),
        "regression_count": len(regression_rows),
        "unchanged_mismatch_count": all_status_counts["still_mismatch"],
        "unchanged_correct_count": all_status_counts["unchanged_correct"],
        "remaining_mismatch_count_by_field": dict(remaining_field_counts),
        "regression_count_by_field": dict(regression_field_counts),
        "remaining_mismatch_count_by_issue_category": dict(issue_category_counts),
        "recommended_next_action_counts": dict(action_counts),
        "manual_review_focus_cases": MANUAL_REVIEW_CASES,
        "candidate_cases_for_i36": sorted(
            {
                row["email_id"]
                for row in remaining_rows
                if row["recommended_next_action"] == "golden_label_candidate_review"
            }
        ),
        "recommendation": [
            "keep I-3.4B prompt patch",
            "enter I-3.6 only after reviewing candidate label cases",
            "do not expand to 300-500 until remaining mismatch categories are documented",
        ],
    }
    return remaining_rows, regression_rows, improved_rows, summary


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "email_id",
        "field",
        "golden_label",
        "baseline_prediction",
        "patched_prediction",
        "status",
        "preliminary_issue_category",
        "recommended_next_action",
        "heuristic_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:300]


def write_report(
    remaining_rows: list[dict[str, str]],
    regression_rows: list[dict[str, str]],
    improved_rows: list[dict[str, str]],
    summary: dict[str, Any],
) -> None:
    remaining_field_counts = Counter(row["field"] for row in remaining_rows)
    regression_field_counts = Counter(row["field"] for row in regression_rows)
    issue_counts = Counter(row["preliminary_issue_category"] for row in remaining_rows)
    action_counts = Counter(row["recommended_next_action"] for row in remaining_rows)

    lines = [
        "# I-3.5.1 Remaining Mismatch, Regression, and Evaluation Credibility Analysis",
        "",
        "## Stage And Purpose",
        "",
        "This analysis reviews the 17 remaining mismatches after the I-3.5 patched-prompt rerun, identifies regressions, and separates likely model errors from taxonomy and golden-label boundary issues.",
        "",
        "## Inputs Used",
        "",
        f"- Baseline predictions: `{BASELINE_PREDICTION_PATH}`",
        f"- Patched predictions: `{PATCHED_PREDICTION_PATH}`",
        f"- Golden labels: `{GOLDEN_PATH}`",
        f"- I-3.5 comparison summary: `{COMPARISON_SUMMARY_PATH}`",
        f"- Manual review summary: `{MANUAL_REVIEW_SUMMARY_PATH}`",
        "",
        "## Summary Of I-3.5 Result",
        "",
        "- Mismatches improved from 41 to 17.",
        "- Comparison recommendation: keep_prompt_patch.",
        "- This means model-reference-label consistency improved, not that the golden labels are official absolute truth.",
        "",
        "## Remaining Mismatch Overview",
        "",
        f"- Remaining mismatch count: {len(remaining_rows)}",
        f"- Regression count: {len(regression_rows)}",
        f"- Improved field-level cases: {len(improved_rows)}",
        "",
        "## Field-level Remaining Mismatch Count",
        "",
        "| Field | Remaining mismatches |",
        "|---|---:|",
    ]
    for field in FIELDS:
        lines.append(f"| {field} | {remaining_field_counts.get(field, 0)} |")

    lines.extend(["", "## Field-level Regression Count", "", "| Field | Regressions |", "|---|---:|"])
    for field in FIELDS:
        lines.append(f"| {field} | {regression_field_counts.get(field, 0)} |")

    lines.extend(["", "## Remaining Mismatch Categories", "", "| Preliminary issue category | Count |", "|---|---:|"])
    for category, count in issue_counts.most_common():
        lines.append(f"| {category} | {count} |")

    lines.extend(["", "## Recommended Next Actions", "", "| Recommended action | Count |", "|---|---:|"])
    for action, count in action_counts.most_common():
        lines.append(f"| {action} | {count} |")

    lines.extend(
        [
            "",
            "## Case-level Analysis Table",
            "",
            "| Email ID | Field | Golden label | Baseline prediction | Patched prediction | Status | Preliminary issue category | Recommended next action |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in remaining_rows:
        lines.append(
            "| {email_id} | {field} | {golden_label} | {baseline_prediction} | {patched_prediction} | {status} | {category} | {action} |".format(
                email_id=md_cell(row["email_id"]),
                field=md_cell(row["field"]),
                golden_label=md_cell(row["golden_label"]),
                baseline_prediction=md_cell(row["baseline_prediction"]),
                patched_prediction=md_cell(row["patched_prediction"]),
                status=md_cell(row["status"]),
                category=md_cell(row["preliminary_issue_category"]),
                action=md_cell(row["recommended_next_action"]),
            )
        )

    lines.extend(["", "## Manual Review Focus Cases", ""])
    for case_id in MANUAL_REVIEW_CASES:
        case_rows = [row for row in remaining_rows + improved_rows + regression_rows if row["email_id"] == case_id]
        lines.append(f"### {case_id}")
        lines.append("")
        if not case_rows:
            lines.append("No field-level change or mismatch found for this case in the analyzed outputs.")
            lines.append("")
            continue
        lines.extend(["| Field | Golden label | Baseline prediction | Patched prediction | Status | Category |", "|---|---|---|---|---|---|"])
        for row in case_rows:
            lines.append(
                f"| {md_cell(row['field'])} | {md_cell(row['golden_label'])} | {md_cell(row['baseline_prediction'])} | {md_cell(row['patched_prediction'])} | {md_cell(row['status'])} | {md_cell(row['preliminary_issue_category'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Which Cases Look Like model_error",
            "",
        ]
    )
    for row in remaining_rows:
        if row["preliminary_issue_category"] == "model_error":
            lines.append(f"- {row['email_id']} `{row['field']}`: patched `{row['patched_prediction']}` vs golden `{row['golden_label']}`")
    if not any(row["preliminary_issue_category"] == "model_error" for row in remaining_rows):
        lines.append("- None from heuristic classification.")

    for category in ["golden_label_issue", "taxonomy_ambiguity", "urgency_threshold_issue", "normalization_issue"]:
        lines.extend(["", f"## Which Cases Look Like {category}", ""])
        matches = [row for row in remaining_rows if row["preliminary_issue_category"] == category]
        if not matches:
            lines.append("- None from heuristic classification.")
        for row in matches:
            lines.append(f"- {row['email_id']} `{row['field']}`: patched `{row['patched_prediction']}` vs golden `{row['golden_label']}`")

    candidate_rows = [row for row in remaining_rows if row["recommended_next_action"] == "golden_label_candidate_review"]
    lines.extend(["", "## Candidate List For I-3.6 Golden Label Candidate Patch", ""])
    if candidate_rows:
        for row in candidate_rows:
            lines.append(f"- {row['email_id']} `{row['field']}`: current golden `{row['golden_label']}`, patched prediction `{row['patched_prediction']}`")
    else:
        lines.append("- No candidate golden label review cases identified by heuristics.")

    no_patch_rows = [row for row in remaining_rows if row["recommended_next_action"] in {"taxonomy_rule_review", "prompt_followup_needed"}]
    lines.extend(["", "## Cases That Should Not Be Patched Yet", ""])
    if no_patch_rows:
        for row in no_patch_rows:
            lines.append(f"- {row['email_id']} `{row['field']}` should be reviewed before any label patch. Action: {row['recommended_next_action']}.")
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Prompt Follow-up Recommendations",
            "",
            "- Keep the I-3.4B prompt patch because overall mismatches decreased substantially.",
            "- Review `is_complaint` regressions before adding more prompt rules.",
            "- Do not overcorrect source_attribution until golden-label candidate cases are reviewed.",
            "- Treat remaining urgency mismatches as threshold review cases rather than immediate model failures.",
            "",
            "## Recommendation",
            "",
            "- Keep I-3.4B prompt patch.",
            "- Enter I-3.6 only after reviewing candidate label cases.",
            "- Do not expand to 300-500 until remaining mismatch categories are documented.",
            "",
            "## Note On Evaluation Meaning",
            "",
            "The current golden labels are project-level internal reference labels for a synthetic customer email pilot dataset. A mismatch means the model output differs from the current project reference label, not necessarily that the model is always wrong.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    remaining_rows, regression_rows, improved_rows, summary = build_rows()
    write_csv(REMAINING_MISMATCH_CASES_PATH, remaining_rows)
    write_csv(REGRESSION_CASES_PATH, regression_rows)
    write_csv(IMPROVED_CASES_PATH, improved_rows)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(remaining_rows, regression_rows, improved_rows, summary)

    print("I-3.5.1 remaining mismatch analysis completed.")
    print(f"Remaining mismatches: {len(remaining_rows)}")
    print(f"Regressions: {len(regression_rows)}")
    print(f"Improved cases: {len(improved_rows)}")
    print(f"Summary saved to: {SUMMARY_JSON_PATH}")
    print(f"Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
