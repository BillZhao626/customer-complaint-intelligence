from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
CANDIDATE_PATCH_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1_candidate_patch.csv"
PATCHED_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_i35_prompt_patch_v1.csv"
PREVIEW_REPORT_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_metric_preview_v1.md"
PREVIEW_JSON_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_metric_preview_v1.json"

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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def normalize(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def golden_value(row: dict[str, str], field: str) -> str:
    return row.get(f"{field}_label", "")


def prediction_value(row: dict[str, str], field: str) -> str:
    return row.get(field, "")


def apply_candidate_patch_in_memory(golden: dict[str, dict[str, str]], patch_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    patched_golden = deepcopy(golden)
    for row in patch_rows:
        if normalize(row.get("should_apply_now")) != "false":
            raise ValueError("Candidate patch preview requires should_apply_now=false for every row.")
        if row.get("decision_status") != "needs_human_confirmation":
            raise ValueError("Candidate patch preview requires decision_status=needs_human_confirmation for every row.")
        email_id = row["email_id"]
        field = row["field"]
        if email_id not in patched_golden:
            raise ValueError(f"Patch email_id not found in golden labels: {email_id}")
        label_column = f"{field}_label"
        if label_column not in patched_golden[email_id]:
            raise ValueError(f"Patch field not found in golden labels: {email_id} {field}")
        patched_golden[email_id][label_column] = row["candidate_golden_value"]
    return patched_golden


def compute_metrics(predictions: dict[str, dict[str, str]], golden: dict[str, dict[str, str]]) -> dict[str, Any]:
    common_ids = sorted(set(predictions) & set(golden))
    field_accuracy: dict[str, float] = {}
    field_mismatch_counts: dict[str, int] = {}
    mismatches: list[dict[str, str]] = []

    for field in FIELDS:
        correct = 0
        for email_id in common_ids:
            prediction = prediction_value(predictions[email_id], field)
            expected = golden_value(golden[email_id], field)
            if normalize(prediction) == normalize(expected):
                correct += 1
            else:
                mismatches.append(
                    {
                        "email_id": email_id,
                        "field": field,
                        "prediction": prediction,
                        "golden_label": expected,
                    }
                )
        support = len(common_ids)
        field_accuracy[field] = correct / support if support else 0.0
        field_mismatch_counts[field] = support - correct

    return {
        "field_accuracy": field_accuracy,
        "field_mismatch_counts": field_mismatch_counts,
        "total_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "support": len(common_ids),
    }


def compute_deltas(original_metrics: dict[str, Any], candidate_metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_accuracy_delta": {
            field: candidate_metrics["field_accuracy"][field] - original_metrics["field_accuracy"][field]
            for field in FIELDS
        },
        "field_mismatch_count_delta": {
            field: candidate_metrics["field_mismatch_counts"][field] - original_metrics["field_mismatch_counts"][field]
            for field in FIELDS
        },
        "total_mismatch_delta": candidate_metrics["total_mismatch_count"] - original_metrics["total_mismatch_count"],
    }


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:300]


def write_report(
    patch_rows: list[dict[str, str]],
    original_metrics: dict[str, Any],
    candidate_metrics: dict[str, Any],
    deltas: dict[str, Any],
) -> None:
    lines = [
        "# I-3.6 Candidate Patch Metric Preview v1",
        "",
        "## Warning",
        "",
        "This is a preview, not official final evaluation. Candidate labels are applied only in memory and the original golden labels are not overwritten.",
        "",
        "## Inputs",
        "",
        f"- Original golden labels: `{GOLDEN_PATH}`",
        f"- Candidate patch file: `{CANDIDATE_PATCH_PATH}`",
        f"- I-3.5 patched predictions: `{PATCHED_PREDICTION_PATH}`",
        "",
        "## Candidate Label Changes",
        "",
        f"- Number of candidate label changes: {len(patch_rows)}",
        "- Affected email_id / field pairs:",
    ]
    for row in patch_rows:
        lines.append(f"  - {row['email_id']} `{row['field']}`: `{row['original_golden_value']}` -> `{row['candidate_golden_value']}`")

    lines.extend(
        [
            "",
            "## Field-level Accuracy",
            "",
            "| Field | Original golden labels | Candidate-patched labels | Delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for field in FIELDS:
        lines.append(
            f"| {field} | {original_metrics['field_accuracy'][field]:.4f} | "
            f"{candidate_metrics['field_accuracy'][field]:.4f} | {deltas['field_accuracy_delta'][field]:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Mismatch Count",
            "",
            "| Field | Original golden labels | Candidate-patched labels | Delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for field in FIELDS:
        lines.append(
            f"| {field} | {original_metrics['field_mismatch_counts'][field]} | "
            f"{candidate_metrics['field_mismatch_counts'][field]} | {deltas['field_mismatch_count_delta'][field]} |"
        )

    lines.extend(
        [
            "",
            "## Total Mismatch Preview",
            "",
            f"- Total mismatch count under original golden labels: {original_metrics['total_mismatch_count']}",
            f"- Total mismatch count under candidate-patched labels: {candidate_metrics['total_mismatch_count']}",
            f"- Mismatch delta: {deltas['total_mismatch_delta']}",
            "",
            "## Affected Pairs",
            "",
            "| Email ID | Field | Original golden value | Candidate golden value | Patched prediction |",
            "|---|---|---|---|---|",
        ]
    )
    for row in patch_rows:
        lines.append(
            f"| {md_cell(row['email_id'])} | {md_cell(row['field'])} | {md_cell(row['original_golden_value'])} | "
            f"{md_cell(row['candidate_golden_value'])} | {md_cell(row['patched_prediction'])} |"
        )

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Use this preview only as a secondary metric view after human review. Keep the original golden labels as the baseline reference until candidate labels are explicitly accepted.",
            "",
        ]
    )
    PREVIEW_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    golden = read_csv_by_id(GOLDEN_PATH)
    patch_rows = read_csv_rows(CANDIDATE_PATCH_PATH)
    predictions = read_csv_by_id(PATCHED_PREDICTION_PATH)

    candidate_golden = apply_candidate_patch_in_memory(golden, patch_rows)
    original_metrics = compute_metrics(predictions, golden)
    candidate_metrics = compute_metrics(predictions, candidate_golden)
    deltas = compute_deltas(original_metrics, candidate_metrics)

    affected_fields = [{"email_id": row["email_id"], "field": row["field"]} for row in patch_rows]
    preview = {
        "stage": "I-3.6",
        "original_golden_file": str(GOLDEN_PATH),
        "candidate_patch_file": str(CANDIDATE_PATCH_PATH),
        "prediction_file": str(PATCHED_PREDICTION_PATH),
        "fields_compared": FIELDS,
        "candidate_patch_rows_count": len(patch_rows),
        "affected_fields": affected_fields,
        "original_metrics": {
            "field_accuracy": original_metrics["field_accuracy"],
            "field_mismatch_counts": original_metrics["field_mismatch_counts"],
            "total_mismatch_count": original_metrics["total_mismatch_count"],
            "support": original_metrics["support"],
        },
        "candidate_patched_metrics": {
            "field_accuracy": candidate_metrics["field_accuracy"],
            "field_mismatch_counts": candidate_metrics["field_mismatch_counts"],
            "total_mismatch_count": candidate_metrics["total_mismatch_count"],
            "support": candidate_metrics["support"],
        },
        "metric_deltas": deltas,
        "warning": "Preview only; candidate labels are not official final evaluation labels and are applied only in memory.",
        "recommendation": "Keep original labels as baseline reference until human review accepts candidate labels.",
    }

    PREVIEW_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_JSON_PATH.write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(patch_rows, original_metrics, candidate_metrics, deltas)

    print("I-3.6 candidate patch metric preview completed.")
    print(f"Original mismatch count: {original_metrics['total_mismatch_count']}")
    print(f"Candidate-patched mismatch count: {candidate_metrics['total_mismatch_count']}")
    print(f"Mismatch delta: {deltas['total_mismatch_delta']}")
    print(f"Preview report saved to: {PREVIEW_REPORT_PATH}")
    print(f"Preview JSON saved to: {PREVIEW_JSON_PATH}")


if __name__ == "__main__":
    main()
