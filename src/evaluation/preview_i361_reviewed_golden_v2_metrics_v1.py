from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ORIGINAL_GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
REVIEWED_GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v2_reviewed.csv"
BASELINE_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_v1.csv"
PATCHED_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_i35_prompt_patch_v1.csv"
PREVIEW_REPORT_PATH = PROJECT_ROOT / "outputs" / "i361_reviewed_golden_v2_metric_preview_v1.md"
PREVIEW_JSON_PATH = PROJECT_ROOT / "outputs" / "i361_reviewed_golden_v2_metric_preview_v1.json"

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def read_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {row["email_id"]: dict(row) for row in csv.DictReader(file)}


def normalize(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def golden_value(row: dict[str, str], field: str) -> str:
    return row.get(f"{field}_label", "")


def prediction_value(row: dict[str, str], field: str) -> str:
    return row.get(field, "")


def compute_metrics(predictions: dict[str, dict[str, str]], golden: dict[str, dict[str, str]]) -> dict[str, Any]:
    common_ids = sorted(set(predictions) & set(golden))
    field_metrics: dict[str, dict[str, float]] = {}
    mismatch_rows: list[dict[str, str]] = []

    for field in FIELDS:
        y_true = [normalize(golden_value(golden[email_id], field)) for email_id in common_ids]
        y_pred = [normalize(prediction_value(predictions[email_id], field)) for email_id in common_ids]
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

        mismatches = support - correct
        field_metrics[field] = {
            "accuracy": correct / support if support else 0.0,
            "precision_weighted": weighted_precision,
            "recall_weighted": weighted_recall,
            "f1_weighted": weighted_f1,
            "support": support,
            "mismatches": mismatches,
        }

        for email_id in common_ids:
            expected = golden_value(golden[email_id], field)
            predicted = prediction_value(predictions[email_id], field)
            if normalize(expected) != normalize(predicted):
                mismatch_rows.append(
                    {
                        "email_id": email_id,
                        "field": field,
                        "golden_label": expected,
                        "prediction": predicted,
                    }
                )

    return {
        "field_metrics": field_metrics,
        "total_mismatch_count": len(mismatch_rows),
        "mismatch_rows": mismatch_rows,
        "support": len(common_ids),
    }


def comparison_delta(baseline_metrics: dict[str, Any], patched_metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "mismatch_delta": patched_metrics["total_mismatch_count"] - baseline_metrics["total_mismatch_count"],
        "field_accuracy_delta": {
            field: patched_metrics["field_metrics"][field]["accuracy"] - baseline_metrics["field_metrics"][field]["accuracy"]
            for field in FIELDS
        },
        "field_mismatch_delta": {
            field: patched_metrics["field_metrics"][field]["mismatches"] - baseline_metrics["field_metrics"][field]["mismatches"]
            for field in FIELDS
        },
    }


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:300]


def write_report(results: dict[str, Any]) -> None:
    v1_baseline = results["v1_original"]["baseline_prompt"]
    v1_patched = results["v1_original"]["patched_prompt"]
    v2_baseline = results["v2_reviewed"]["baseline_prompt"]
    v2_patched = results["v2_reviewed"]["patched_prompt"]
    v1_delta = results["v1_original"]["prompt_delta"]
    v2_delta = results["v2_reviewed"]["prompt_delta"]

    lines = [
        "# I-3.6.1 Reviewed Golden v2 Metric Preview v1",
        "",
        "## Warning",
        "",
        "v2_reviewed metrics are reviewed project-label metrics, not official external benchmark metrics.",
        "The original v1 labels remain the historical comparison reference.",
        "",
        "## Inputs",
        "",
        f"- Original v1 golden labels: `{ORIGINAL_GOLDEN_PATH}`",
        f"- Reviewed v2 golden labels: `{REVIEWED_GOLDEN_PATH}`",
        f"- Baseline prompt predictions: `{BASELINE_PREDICTION_PATH}`",
        f"- I-3.5 patched prompt predictions: `{PATCHED_PREDICTION_PATH}`",
        "",
        "## Main Historical Result Under v1 Labels",
        "",
        f"- v1 labels: mismatch {v1_baseline['total_mismatch_count']} -> {v1_patched['total_mismatch_count']}",
        f"- v1 mismatch delta: {v1_delta['mismatch_delta']}",
        "",
        "## Reviewed-label Preview Under v2_reviewed Labels",
        "",
        f"- v2_reviewed labels: mismatch {v2_baseline['total_mismatch_count']} -> {v2_patched['total_mismatch_count']}",
        f"- v2_reviewed mismatch delta: {v2_delta['mismatch_delta']}",
        "- The patched mismatch count aligns with the I-3.6 candidate preview around 13.",
        "",
        "## Baseline Prompt vs Patched Prompt",
        "",
        "| Label version | Baseline mismatches | Patched mismatches | Mismatch delta |",
        "|---|---:|---:|---:|",
        f"| v1_original | {v1_baseline['total_mismatch_count']} | {v1_patched['total_mismatch_count']} | {v1_delta['mismatch_delta']} |",
        f"| v2_reviewed | {v2_baseline['total_mismatch_count']} | {v2_patched['total_mismatch_count']} | {v2_delta['mismatch_delta']} |",
        "",
        "## Field-level Accuracy Under v1 Labels",
        "",
        "| Field | Baseline accuracy | Patched accuracy | Delta | Baseline mismatches | Patched mismatches | Mismatch delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for field in FIELDS:
        lines.append(
            f"| {field} | {v1_baseline['field_metrics'][field]['accuracy']:.4f} | "
            f"{v1_patched['field_metrics'][field]['accuracy']:.4f} | {v1_delta['field_accuracy_delta'][field]:.4f} | "
            f"{v1_baseline['field_metrics'][field]['mismatches']} | {v1_patched['field_metrics'][field]['mismatches']} | "
            f"{v1_delta['field_mismatch_delta'][field]} |"
        )

    lines.extend(
        [
            "",
            "## Field-level Accuracy Under v2_reviewed Labels",
            "",
            "| Field | Baseline accuracy | Patched accuracy | Delta | Baseline mismatches | Patched mismatches | Mismatch delta |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for field in FIELDS:
        lines.append(
            f"| {field} | {v2_baseline['field_metrics'][field]['accuracy']:.4f} | "
            f"{v2_patched['field_metrics'][field]['accuracy']:.4f} | {v2_delta['field_accuracy_delta'][field]:.4f} | "
            f"{v2_baseline['field_metrics'][field]['mismatches']} | {v2_patched['field_metrics'][field]['mismatches']} | "
            f"{v2_delta['field_mismatch_delta'][field]} |"
        )

    lines.extend(
        [
            "",
            "## Recommended Dissertation Wording",
            "",
            "- Main prompt revision conclusion: under original v1 project reference labels, mismatches improved from 41 to 17 after the taxonomy-aware prompt revision.",
            "- Audit-supported secondary result: after human review accepted four label changes into v2_reviewed, the patched-prompt mismatch count is 13.",
            "- Do not describe either result as an official external benchmark score.",
            "",
        ]
    )
    PREVIEW_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    v1_golden = read_csv_by_id(ORIGINAL_GOLDEN_PATH)
    v2_golden = read_csv_by_id(REVIEWED_GOLDEN_PATH)
    baseline_predictions = read_csv_by_id(BASELINE_PREDICTION_PATH)
    patched_predictions = read_csv_by_id(PATCHED_PREDICTION_PATH)

    results = {
        "stage": "I-3.6.1",
        "original_golden_file": str(ORIGINAL_GOLDEN_PATH),
        "reviewed_golden_file": str(REVIEWED_GOLDEN_PATH),
        "baseline_prediction_file": str(BASELINE_PREDICTION_PATH),
        "patched_prediction_file": str(PATCHED_PREDICTION_PATH),
        "fields_compared": FIELDS,
        "v1_original": {},
        "v2_reviewed": {},
        "warning": "v2_reviewed metrics are reviewed project-label metrics, not official external benchmark metrics.",
        "recommended_dissertation_wording": [
            "Report the v1 historical result as 41 -> 17 mismatches for traceability.",
            "Report the v2_reviewed patched mismatch count of 13 as an audit-supported secondary result.",
        ],
    }

    v1_baseline = compute_metrics(baseline_predictions, v1_golden)
    v1_patched = compute_metrics(patched_predictions, v1_golden)
    v2_baseline = compute_metrics(baseline_predictions, v2_golden)
    v2_patched = compute_metrics(patched_predictions, v2_golden)

    results["v1_original"] = {
        "baseline_prompt": {k: v for k, v in v1_baseline.items() if k != "mismatch_rows"},
        "patched_prompt": {k: v for k, v in v1_patched.items() if k != "mismatch_rows"},
        "prompt_delta": comparison_delta(v1_baseline, v1_patched),
    }
    results["v2_reviewed"] = {
        "baseline_prompt": {k: v for k, v in v2_baseline.items() if k != "mismatch_rows"},
        "patched_prompt": {k: v for k, v in v2_patched.items() if k != "mismatch_rows"},
        "prompt_delta": comparison_delta(v2_baseline, v2_patched),
    }

    PREVIEW_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_JSON_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(results)

    print("I-3.6.1 reviewed golden v2 metric preview completed.")
    print(f"v1 labels mismatch: {v1_baseline['total_mismatch_count']} -> {v1_patched['total_mismatch_count']}")
    print(f"v2_reviewed labels mismatch: {v2_baseline['total_mismatch_count']} -> {v2_patched['total_mismatch_count']}")
    print(f"Preview report saved to: {PREVIEW_REPORT_PATH}")
    print(f"Preview JSON saved to: {PREVIEW_JSON_PATH}")


if __name__ == "__main__":
    main()
