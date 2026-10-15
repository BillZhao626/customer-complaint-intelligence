from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASELINE_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_v1.csv"
PATCHED_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_i35_prompt_patch_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
BASELINE_EVAL_REPORT_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_eval_report_v1.md"
PATCHED_EVAL_REPORT_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_eval_report_i35_prompt_patch_v1.md"
PATCHED_ERROR_ANALYSIS_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_error_analysis_i35_prompt_patch_v1.md"
COMPARISON_REPORT_PATH = PROJECT_ROOT / "outputs" / "deepseek_i35_prompt_patch_comparison_report_v1.md"
COMPARISON_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "deepseek_i35_prompt_patch_comparison_summary_v1.json"

COMPARED_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]

MANUAL_REVIEW_CASES = ["P007", "P015", "P028", "P046", "P050"]


def read_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return {str(row["email_id"]): dict(row) for row in reader}


def normalize(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def label_for(golden_row: dict[str, str], field: str) -> str:
    return golden_row.get(f"{field}_label", "")


def prediction_for(prediction_row: dict[str, str], field: str) -> str:
    return prediction_row.get(field, "")


def compute_field_metrics(predictions: dict[str, dict[str, str]], golden: dict[str, dict[str, str]]) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    common_ids = sorted(set(predictions) & set(golden))

    for field in COMPARED_FIELDS:
        y_true = [normalize(label_for(golden[email_id], field)) for email_id in common_ids]
        y_pred = [normalize(prediction_for(predictions[email_id], field)) for email_id in common_ids]
        support = len(y_true)
        correct = sum(1 for true, pred in zip(y_true, y_pred) if true == pred)
        labels = sorted(set(y_true) | set(y_pred))
        true_counts = Counter(y_true)

        weighted_precision = 0.0
        weighted_recall = 0.0
        weighted_f1 = 0.0
        for label in labels:
            tp = sum(1 for true, pred in zip(y_true, y_pred) if true == label and pred == label)
            fp = sum(1 for true, pred in zip(y_true, y_pred) if true != label and pred == label)
            fn = sum(1 for true, pred in zip(y_true, y_pred) if true == label and pred != label)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            weight = true_counts[label] / support if support else 0.0
            weighted_precision += weight * precision
            weighted_recall += weight * recall
            weighted_f1 += weight * f1

        metrics[field] = {
            "accuracy": correct / support if support else 0.0,
            "precision_weighted": weighted_precision,
            "recall_weighted": weighted_recall,
            "f1_weighted": weighted_f1,
            "support": float(support),
            "mismatches": float(support - correct),
        }

    return metrics


def build_mismatch_map(predictions: dict[str, dict[str, str]], golden: dict[str, dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    mismatches: dict[tuple[str, str], dict[str, str]] = {}
    for email_id in sorted(set(predictions) & set(golden)):
        for field in COMPARED_FIELDS:
            prediction = prediction_for(predictions[email_id], field)
            golden_label = label_for(golden[email_id], field)
            if normalize(prediction) != normalize(golden_label):
                mismatches[(email_id, field)] = {
                    "email_id": email_id,
                    "field": field,
                    "prediction": prediction,
                    "golden_label": golden_label,
                }
    return mismatches


def summarize_case_changes(
    baseline_predictions: dict[str, dict[str, str]],
    patched_predictions: dict[str, dict[str, str]],
    golden: dict[str, dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    changes = {"improved": [], "regressed": [], "unchanged_mismatch": [], "unchanged_correct": []}
    common_ids = sorted(set(baseline_predictions) & set(patched_predictions) & set(golden))
    for email_id in common_ids:
        for field in COMPARED_FIELDS:
            golden_label = label_for(golden[email_id], field)
            baseline_prediction = prediction_for(baseline_predictions[email_id], field)
            patched_prediction = prediction_for(patched_predictions[email_id], field)
            baseline_correct = normalize(baseline_prediction) == normalize(golden_label)
            patched_correct = normalize(patched_prediction) == normalize(golden_label)
            item = {
                "email_id": email_id,
                "field": field,
                "baseline_prediction": baseline_prediction,
                "patched_prediction": patched_prediction,
                "golden_label": golden_label,
            }
            if not baseline_correct and patched_correct:
                changes["improved"].append(item)
            elif baseline_correct and not patched_correct:
                changes["regressed"].append(item)
            elif not baseline_correct and not patched_correct:
                changes["unchanged_mismatch"].append(item)
            else:
                changes["unchanged_correct"].append(item)
    return changes


def manual_review_case_summary(
    baseline_predictions: dict[str, dict[str, str]],
    patched_predictions: dict[str, dict[str, str]],
    golden: dict[str, dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for email_id in MANUAL_REVIEW_CASES:
        rows = []
        if email_id not in baseline_predictions or email_id not in patched_predictions or email_id not in golden:
            result[email_id] = [
                {
                    "field": "missing",
                    "baseline_prediction": "missing",
                    "patched_prediction": "missing",
                    "golden_label": "missing",
                    "change": "not_comparable",
                }
            ]
            continue
        for field in COMPARED_FIELDS:
            baseline_prediction = prediction_for(baseline_predictions[email_id], field)
            patched_prediction = prediction_for(patched_predictions[email_id], field)
            golden_label = label_for(golden[email_id], field)
            baseline_correct = normalize(baseline_prediction) == normalize(golden_label)
            patched_correct = normalize(patched_prediction) == normalize(golden_label)
            if not baseline_correct and patched_correct:
                change = "improved"
            elif baseline_correct and not patched_correct:
                change = "regressed"
            elif not baseline_correct and not patched_correct:
                change = "unchanged_mismatch"
            else:
                change = "unchanged_correct"
            rows.append(
                {
                    "field": field,
                    "baseline_prediction": baseline_prediction,
                    "patched_prediction": patched_prediction,
                    "golden_label": golden_label,
                    "change": change,
                }
            )
        result[email_id] = rows
    return result


def metric_deltas(
    baseline_metrics: dict[str, dict[str, float]], patched_metrics: dict[str, dict[str, float]]
) -> dict[str, dict[str, float]]:
    deltas: dict[str, dict[str, float]] = {}
    for field in COMPARED_FIELDS:
        deltas[field] = {}
        for metric in ["accuracy", "precision_weighted", "recall_weighted", "f1_weighted", "mismatches"]:
            deltas[field][metric] = patched_metrics[field][metric] - baseline_metrics[field][metric]
    return deltas


def make_recommendation(total_baseline_mismatches: int, total_patched_mismatches: int, regressions: int) -> str:
    if total_patched_mismatches < total_baseline_mismatches and regressions <= 5:
        return "keep_prompt_patch"
    if total_patched_mismatches > total_baseline_mismatches:
        return "revise_prompt_patch"
    if regressions:
        return "needs_more_analysis"
    return "review_golden_labels"


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:300]


def write_patched_error_analysis(patched_mismatches: dict[tuple[str, str], dict[str, str]]) -> None:
    field_counts = Counter(item["field"] for item in patched_mismatches.values())
    lines = [
        "# DeepSeek Full Pilot Error Analysis I-3.5 Prompt Patch v1",
        "",
        "- Stage: I-3.5 Prompt Patch Rerun and Baseline Comparison",
        f"- Patched prediction file: `{PATCHED_PREDICTION_PATH}`",
        f"- Golden label file: `{GOLDEN_PATH}`",
        f"- Total mismatches: {len(patched_mismatches)}",
        "",
        "## Mismatch Count By Field",
        "",
        "| Field | Mismatches |",
        "|---|---:|",
    ]
    for field in COMPARED_FIELDS:
        lines.append(f"| {field} | {field_counts.get(field, 0)} |")
    lines.extend(["", "## Mismatch Table", "", "| Email ID | Field | Prediction | Golden label |", "|---|---|---|---|"])
    for item in patched_mismatches.values():
        lines.append(
            f"| {md_cell(item['email_id'])} | {md_cell(item['field'])} | {md_cell(item['prediction'])} | {md_cell(item['golden_label'])} |"
        )
    if not patched_mismatches:
        lines.append("| none | none | none | none |")
    PATCHED_ERROR_ANALYSIS_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    baseline_metrics: dict[str, dict[str, float]],
    patched_metrics: dict[str, dict[str, float]],
    deltas: dict[str, dict[str, float]],
    baseline_mismatches: dict[tuple[str, str], dict[str, str]],
    patched_mismatches: dict[tuple[str, str], dict[str, str]],
    changes: dict[str, list[dict[str, str]]],
    manual_cases: dict[str, list[dict[str, str]]],
    recommendation: str,
) -> None:
    lines = [
        "# DeepSeek I-3.5 Prompt Patch Comparison Report v1",
        "",
        "## Stage And Purpose",
        "",
        "I-3.5 reruns the 50-case DeepSeek full pilot using the I-3.4B taxonomy-aware prompt patch and compares it against the I-3.1.1 baseline.",
        "",
        "## Dataset Used",
        "",
        f"- Pilot dataset: `data/synthetic/customer_emails_pilot_v1.csv`",
        f"- Golden labels: `{GOLDEN_PATH}`",
        "",
        "## Baseline Files Used",
        "",
        f"- Baseline prediction file: `{BASELINE_PREDICTION_PATH}`",
        f"- Baseline eval report: `{BASELINE_EVAL_REPORT_PATH}`",
        "",
        "## I-3.5 Files Generated",
        "",
        f"- Patched prediction file: `{PATCHED_PREDICTION_PATH}`",
        f"- Patched eval report: `{PATCHED_EVAL_REPORT_PATH}`",
        f"- Patched error analysis report: `{PATCHED_ERROR_ANALYSIS_PATH}`",
        f"- Comparison report: `{COMPARISON_REPORT_PATH}`",
        f"- Comparison summary JSON: `{COMPARISON_SUMMARY_PATH}`",
        "",
        "## Overall Metrics Comparison",
        "",
        f"- Baseline mismatches: {len(baseline_mismatches)}",
        f"- I-3.5 patched mismatches: {len(patched_mismatches)}",
        f"- Mismatch delta: {len(patched_mismatches) - len(baseline_mismatches)}",
        "",
        "## Field-level Metric Comparison",
        "",
        "| Field | Baseline accuracy | Patched accuracy | Accuracy delta | Baseline precision | Patched precision | Precision delta | Baseline recall | Patched recall | Recall delta | Baseline F1 | Patched F1 | F1 delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for field in COMPARED_FIELDS:
        lines.append(
            "| {field} | {ba:.4f} | {pa:.4f} | {da:.4f} | {bp:.4f} | {pp:.4f} | {dp:.4f} | {br:.4f} | {pr:.4f} | {dr:.4f} | {bf:.4f} | {pf:.4f} | {df:.4f} |".format(
                field=field,
                ba=baseline_metrics[field]["accuracy"],
                pa=patched_metrics[field]["accuracy"],
                da=deltas[field]["accuracy"],
                bp=baseline_metrics[field]["precision_weighted"],
                pp=patched_metrics[field]["precision_weighted"],
                dp=deltas[field]["precision_weighted"],
                br=baseline_metrics[field]["recall_weighted"],
                pr=patched_metrics[field]["recall_weighted"],
                dr=deltas[field]["recall_weighted"],
                bf=baseline_metrics[field]["f1_weighted"],
                pf=patched_metrics[field]["f1_weighted"],
                df=deltas[field]["f1_weighted"],
            )
        )

    lines.extend(
        [
            "",
            "## Mismatch Count Comparison",
            "",
            "| Field | Baseline mismatches | Patched mismatches | Delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for field in COMPARED_FIELDS:
        baseline_count = int(baseline_metrics[field]["mismatches"])
        patched_count = int(patched_metrics[field]["mismatches"])
        lines.append(f"| {field} | {baseline_count} | {patched_count} | {patched_count - baseline_count} |")

    for title, key in [
        ("Key Improved Cases", "improved"),
        ("Key Regressed Cases", "regressed"),
        ("Key Unchanged Mismatch Cases", "unchanged_mismatch"),
    ]:
        lines.extend(["", f"## {title}", ""])
        items = changes[key][:20]
        if not items:
            lines.append("No cases in this category.")
            continue
        lines.extend(["| Email ID | Field | Baseline prediction | Patched prediction | Golden label |", "|---|---|---|---|---|"])
        for item in items:
            lines.append(
                f"| {md_cell(item['email_id'])} | {md_cell(item['field'])} | {md_cell(item['baseline_prediction'])} | {md_cell(item['patched_prediction'])} | {md_cell(item['golden_label'])} |"
            )

    lines.extend(["", "## Specific Manual Review Cases", ""])
    for email_id in MANUAL_REVIEW_CASES:
        lines.extend([f"### {email_id}", ""])
        lines.extend(["| Field | Baseline prediction | Patched prediction | Golden label | Change |", "|---|---|---|---|---|"])
        for item in manual_cases[email_id]:
            lines.append(
                f"| {md_cell(item['field'])} | {md_cell(item['baseline_prediction'])} | {md_cell(item['patched_prediction'])} | {md_cell(item['golden_label'])} | {md_cell(item['change'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "- Improvements suggest that I-3.4B prompt rules helped fields where baseline predictions disagreed with the current golden labels.",
            "- Regressions should be reviewed before deciding whether to keep or revise the prompt patch.",
            "- Source attribution and mixed sentiment may still need taxonomy or golden-label review because exact-match metrics can over-count boundary disagreements.",
            "",
            f"Recommendation: `{recommendation}`",
            "",
            "## Next Step Recommendation",
            "",
            "- If improvements outweigh regressions, keep the prompt patch and proceed to I-3.5.1 post-rerun error analysis.",
            "- If regressions are concentrated in taxonomy-boundary cases, proceed to I-3.6 golden label candidate review.",
            "- Do not expand to 300-500 synthetic emails until the rerun mismatch deltas are understood.",
            "",
        ]
    )
    COMPARISON_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    baseline_predictions = read_csv_by_id(BASELINE_PREDICTION_PATH)
    patched_predictions = read_csv_by_id(PATCHED_PREDICTION_PATH)
    golden = read_csv_by_id(GOLDEN_PATH)

    baseline_metrics = compute_field_metrics(baseline_predictions, golden)
    patched_metrics = compute_field_metrics(patched_predictions, golden)
    deltas = metric_deltas(baseline_metrics, patched_metrics)
    baseline_mismatches = build_mismatch_map(baseline_predictions, golden)
    patched_mismatches = build_mismatch_map(patched_predictions, golden)
    changes = summarize_case_changes(baseline_predictions, patched_predictions, golden)
    manual_cases = manual_review_case_summary(baseline_predictions, patched_predictions, golden)
    recommendation = make_recommendation(len(baseline_mismatches), len(patched_mismatches), len(changes["regressed"]))

    write_patched_error_analysis(patched_mismatches)
    write_report(
        baseline_metrics,
        patched_metrics,
        deltas,
        baseline_mismatches,
        patched_mismatches,
        changes,
        manual_cases,
        recommendation,
    )

    summary = {
        "stage": "I-3.5",
        "baseline_prediction_file": str(BASELINE_PREDICTION_PATH),
        "patched_prediction_file": str(PATCHED_PREDICTION_PATH),
        "baseline_eval_report": str(BASELINE_EVAL_REPORT_PATH),
        "patched_eval_report": str(PATCHED_EVAL_REPORT_PATH),
        "comparison_report": str(COMPARISON_REPORT_PATH),
        "compared_fields": COMPARED_FIELDS,
        "baseline_metrics": baseline_metrics,
        "patched_metrics": patched_metrics,
        "metric_deltas": deltas,
        "baseline_mismatch_count": len(baseline_mismatches),
        "patched_mismatch_count": len(patched_mismatches),
        "mismatch_delta": len(patched_mismatches) - len(baseline_mismatches),
        "improved_case_count": len(changes["improved"]),
        "regressed_case_count": len(changes["regressed"]),
        "unchanged_mismatch_count": len(changes["unchanged_mismatch"]),
        "manual_review_cases": manual_cases,
        "recommendation": recommendation,
    }
    COMPARISON_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("I-3.5 prompt patch comparison completed.")
    print(f"Baseline mismatches: {len(baseline_mismatches)}")
    print(f"Patched mismatches: {len(patched_mismatches)}")
    print(f"Mismatch delta: {len(patched_mismatches) - len(baseline_mismatches)}")
    print(f"Improved field-level cases: {len(changes['improved'])}")
    print(f"Regressed field-level cases: {len(changes['regressed'])}")
    print(f"Recommendation: {recommendation}")
    print(f"Comparison report saved to: {COMPARISON_REPORT_PATH}")
    print(f"Comparison summary saved to: {COMPARISON_SUMMARY_PATH}")


if __name__ == "__main__":
    main()
