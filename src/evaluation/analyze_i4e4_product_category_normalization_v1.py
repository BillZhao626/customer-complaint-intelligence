from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_predictions_v1.csv"
REVIEWED_GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv"
I4E2_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json"
I4E3_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_interpretation_summary_v1.json"
I4E3_MISMATCH_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_mismatch_details_v1.csv"
RULES_PATH = PROJECT_ROOT / "configs" / "evaluation" / "product_category_normalization_rules_v1.json"

DETAILS_PATH = PROJECT_ROOT / "outputs" / "i4e4_product_category_normalization_details_v1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e4_post_normalized_eval_summary_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e4_product_category_normalization_report_v1.md"

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text.lower() in {"true", "false"}:
        return text.lower()
    return text.casefold()


def load_subject_context() -> dict[str, str]:
    if not I4E3_MISMATCH_PATH.exists():
        return {}
    rows = read_csv(I4E3_MISMATCH_PATH)
    return {row["email_id"]: row.get("subject", "") for row in rows if row.get("field") == "product_category"}


def normalize_product_category(value: str, context: str, rules: dict[str, Any]) -> tuple[str, str]:
    raw = (value or "").strip()
    if not raw:
        return "unknown", "blank_or_missing_to_unknown"

    direct_mappings = {key.casefold(): mapped for key, mapped in rules.get("direct_mappings", {}).items()}
    raw_key = raw.casefold()
    if raw_key in direct_mappings:
        return direct_mappings[raw_key], "direct_mapping"

    canonical_by_key = {label.casefold(): label for label in rules.get("canonical_labels", [])}
    if raw_key in canonical_by_key:
        return canonical_by_key[raw_key], "already_canonical"

    for rule in rules.get("conditional_mappings", []):
        source_value = str(rule.get("source_value", "")).casefold()
        if raw_key != source_value:
            continue
        context_lower = context.casefold()
        keywords = [str(keyword).casefold() for keyword in rule.get("context_keywords", [])]
        if any(keyword in context_lower for keyword in keywords):
            return str(rule.get("target_value", raw)), "conditional_context_mapping"

    return raw, "unchanged"


def compute_metrics(
    predictions: list[dict[str, str]],
    reviewed: list[dict[str, str]],
    rules: dict[str, Any] | None = None,
    subject_context: dict[str, str] | None = None,
) -> dict[str, Any]:
    reviewed_by_id = {row["email_id"]: row for row in reviewed}
    total_cases = len(predictions)
    mismatches_by_field = {field: 0 for field in FIELDS}

    for prediction in predictions:
        email_id = prediction["email_id"]
        reviewed_row = reviewed_by_id[email_id]
        for field in FIELDS:
            predicted_value = prediction.get(field, "")
            reviewed_value = reviewed_row.get(field, "")
            if rules is not None and field == "product_category":
                context = (subject_context or {}).get(email_id, "")
                predicted_value, _ = normalize_product_category(predicted_value, context, rules)
                reviewed_value, _ = normalize_product_category(reviewed_value, context, rules)
            if normalize_text(predicted_value) != normalize_text(reviewed_value):
                mismatches_by_field[field] += 1

    total_field_count = total_cases * len(FIELDS)
    total_mismatch_count = sum(mismatches_by_field.values())
    correct_fields = total_field_count - total_mismatch_count
    return {
        "total_cases": total_cases,
        "total_field_count": total_field_count,
        "correct_fields": correct_fields,
        "total_mismatch_count": total_mismatch_count,
        "overall_field_accuracy": correct_fields / total_field_count if total_field_count else 0.0,
        "field_accuracy": {
            field: (total_cases - mismatches_by_field[field]) / total_cases if total_cases else 0.0
            for field in FIELDS
        },
        "mismatches_by_field": mismatches_by_field,
    }


def build_product_details(
    predictions: list[dict[str, str]],
    reviewed: list[dict[str, str]],
    rules: dict[str, Any],
    subject_context: dict[str, str],
) -> list[dict[str, Any]]:
    reviewed_by_id = {row["email_id"]: row for row in reviewed}
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        email_id = prediction["email_id"]
        reviewed_row = reviewed_by_id[email_id]
        original_predicted = prediction.get("product_category", "")
        original_reviewed = reviewed_row.get("product_category", "")
        context = subject_context.get(email_id, "")
        normalized_predicted, predicted_rule = normalize_product_category(original_predicted, context, rules)
        normalized_reviewed, reviewed_rule = normalize_product_category(original_reviewed, context, rules)
        before_match = normalize_text(original_predicted) == normalize_text(original_reviewed)
        after_match = normalize_text(normalized_predicted) == normalize_text(normalized_reviewed)

        if before_match and after_match:
            resolution_status = "already_matched"
        elif not before_match and after_match:
            resolution_status = "resolved_by_normalization"
        elif not before_match and not after_match:
            resolution_status = "remaining_mismatch_after_normalization"
        else:
            resolution_status = "changed_to_mismatch_after_normalization"

        rows.append(
            {
                "email_id": email_id,
                "original_predicted_product_category": original_predicted,
                "original_reviewed_product_category": original_reviewed,
                "normalized_predicted_product_category": normalized_predicted,
                "normalized_reviewed_product_category": normalized_reviewed,
                "before_match": str(before_match).lower(),
                "after_match": str(after_match).lower(),
                "resolution_status": resolution_status,
                "predicted_normalization_rule": predicted_rule,
                "reviewed_normalization_rule": reviewed_rule,
                "context_used": context,
            }
        )
    return rows


def write_details(rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "email_id",
        "original_predicted_product_category",
        "original_reviewed_product_category",
        "normalized_predicted_product_category",
        "normalized_reviewed_product_category",
        "before_match",
        "after_match",
        "resolution_status",
        "predicted_normalization_rule",
        "reviewed_normalization_rule",
        "context_used",
    ]
    DETAILS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DETAILS_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_report(summary: dict[str, Any], detail_rows: list[dict[str, Any]]) -> None:
    original = summary["original_metrics"]
    normalized = summary["post_normalized_metrics"]
    status_counts = Counter(row["resolution_status"] for row in detail_rows)
    remaining_rows = [
        row
        for row in detail_rows
        if row["resolution_status"] == "remaining_mismatch_after_normalization"
    ]

    lines = [
        "# I-4E.4 Product Category Normalization and Post-evaluation Analysis v1",
        "",
        "## Stage And Purpose",
        "",
        (
            "I-4E.4 performs an offline post-evaluation normalization analysis for product_category only. "
            "It does not change model outputs, reviewed golden labels, prompts, chains, parser, schema, API settings, or datasets."
        ),
        "",
        "## Evaluation Boundary",
        "",
        "- No DeepSeek API call was made.",
        "- No model evaluation was rerun.",
        "- Original I-4E.2 formal metrics remain the primary formal evaluation record.",
        "- This analysis tests whether product_category weakness is mainly caused by category naming inconsistency.",
        "",
        "## Original Vs Post-normalized Metrics",
        "",
        "| Metric | Original | Post-normalized | Delta |",
        "|---|---:|---:|---:|",
        (
            f"| Overall field accuracy | {pct(original['overall_field_accuracy'])} | "
            f"{pct(normalized['overall_field_accuracy'])} | "
            f"{pct(summary['metric_deltas']['overall_field_accuracy_delta'])} |"
        ),
        (
            f"| Product category accuracy | {pct(original['field_accuracy']['product_category'])} | "
            f"{pct(normalized['field_accuracy']['product_category'])} | "
            f"{pct(summary['metric_deltas']['product_category_accuracy_delta'])} |"
        ),
        (
            f"| Total mismatches | {original['total_mismatch_count']} | "
            f"{normalized['total_mismatch_count']} | {summary['metric_deltas']['total_mismatch_delta']} |"
        ),
        (
            f"| Product category mismatches | {original['mismatches_by_field']['product_category']} | "
            f"{normalized['mismatches_by_field']['product_category']} | "
            f"{summary['metric_deltas']['product_category_mismatch_delta']} |"
        ),
        "",
        "## Product Category Resolution Summary",
        "",
        f"- Original product_category mismatches: {summary['product_category_analysis']['original_mismatch_count']}",
        f"- Resolved by normalization: {summary['product_category_analysis']['resolved_by_normalization_count']}",
        f"- Remaining after normalization: {summary['product_category_analysis']['remaining_mismatch_count']}",
        f"- Already matched before normalization: {status_counts.get('already_matched', 0)}",
        "",
        "## Remaining Product Category Mismatches",
        "",
        "| Email ID | Predicted normalized | Reviewed normalized | Context |",
        "|---|---|---|---|",
    ]
    for row in remaining_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["email_id"]),
                    str(row["normalized_predicted_product_category"]),
                    str(row["normalized_reviewed_product_category"]),
                    str(row["context_used"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "The post-normalized analysis indicates how much of the product_category weakness is caused by "
                "label naming and taxonomy alignment. Resolved cases are mainly project-category aliases such as "
                "`Beauty Products` -> `Beauty/Personal Care`, `Sportswear` -> `Sports/Outdoor`, and `Service` -> `Service/Other`."
            ),
            "",
            (
                "Remaining mismatches are not automatically fixed by a conservative normalization layer. These cases likely "
                "need either a targeted prompt/taxonomy decision or a separate product-to-category mapping policy."
            ),
            "",
            "## Recommendation",
            "",
            (
                "Keep the original I-4E.2 formal result unchanged for traceability. Use this I-4E.4 result as a secondary "
                "post-evaluation analysis. If dashboard functionality is now the priority, proceed to 400-case DeepSeek "
                "full-pool batch inference and dashboard mode update; otherwise consider a targeted product_category "
                "normalization/mapping design stage first."
            ),
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    predictions = read_csv(PREDICTION_PATH)
    reviewed = read_csv(REVIEWED_GOLDEN_PATH)
    rules = read_json(RULES_PATH)
    i4e2_summary = read_json(I4E2_SUMMARY_PATH)
    i4e3_summary = read_json(I4E3_SUMMARY_PATH)
    subject_context = load_subject_context()

    prediction_ids = {row["email_id"] for row in predictions}
    reviewed_ids = {row["email_id"] for row in reviewed}
    if prediction_ids != reviewed_ids:
        raise ValueError("Prediction and reviewed golden email_id values do not align.")

    original_metrics = compute_metrics(predictions, reviewed)
    post_metrics = compute_metrics(predictions, reviewed, rules=rules, subject_context=subject_context)
    detail_rows = build_product_details(predictions, reviewed, rules, subject_context)
    write_details(detail_rows)

    resolution_counts = Counter(row["resolution_status"] for row in detail_rows)
    summary: dict[str, Any] = {
        "stage": "I-4E.4",
        "analysis_type": "offline_product_category_post_evaluation_normalization",
        "no_api_call": True,
        "model_evaluation_rerun": False,
        "source_prediction_file": str(PREDICTION_PATH),
        "reviewed_golden_file": str(REVIEWED_GOLDEN_PATH),
        "normalization_rules_file": str(RULES_PATH),
        "input_sha256": {
            "predictions": sha256(PREDICTION_PATH),
            "reviewed_golden_labels": sha256(REVIEWED_GOLDEN_PATH),
            "i4e2_summary": sha256(I4E2_SUMMARY_PATH),
            "i4e3_summary": sha256(I4E3_SUMMARY_PATH),
        },
        "i4e2_reference": {
            "backend_used": i4e2_summary.get("backend_used"),
            "api_attempted_count": i4e2_summary.get("api_attempted_count"),
            "api_error_count": i4e2_summary.get("api_error_count"),
            "parse_success_count": i4e2_summary.get("parse_success_count"),
            "schema_validation_success_count": i4e2_summary.get("schema_validation_success_count"),
            "overall_field_accuracy": i4e2_summary.get("overall_field_accuracy"),
        },
        "i4e3_reference": {
            "product_category_accuracy": i4e3_summary.get("field_accuracy", {}).get("product_category"),
            "product_category_mismatches": i4e3_summary.get("mismatches_by_field", {}).get("product_category"),
            "overall_field_accuracy": i4e3_summary.get("overall_field_accuracy"),
        },
        "fields_compared": FIELDS,
        "original_metrics": original_metrics,
        "post_normalized_metrics": post_metrics,
        "metric_deltas": {
            "overall_field_accuracy_delta": post_metrics["overall_field_accuracy"] - original_metrics["overall_field_accuracy"],
            "product_category_accuracy_delta": post_metrics["field_accuracy"]["product_category"] - original_metrics["field_accuracy"]["product_category"],
            "total_mismatch_delta": post_metrics["total_mismatch_count"] - original_metrics["total_mismatch_count"],
            "product_category_mismatch_delta": post_metrics["mismatches_by_field"]["product_category"] - original_metrics["mismatches_by_field"]["product_category"],
        },
        "product_category_analysis": {
            "total_cases": len(detail_rows),
            "original_mismatch_count": sum(row["before_match"] == "false" for row in detail_rows),
            "post_normalized_mismatch_count": sum(row["after_match"] == "false" for row in detail_rows),
            "resolved_by_normalization_count": resolution_counts.get("resolved_by_normalization", 0),
            "remaining_mismatch_count": resolution_counts.get("remaining_mismatch_after_normalization", 0),
            "resolution_status_counts": dict(resolution_counts),
        },
        "output_files": {
            "details_csv": str(DETAILS_PATH),
            "summary_json": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "recommendation": "Use I-4E.4 as secondary post-evaluation analysis; proceed to 400-case DeepSeek full-pool batch inference and dashboard mode update if dashboard demonstration is the next priority.",
    }

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(summary, detail_rows)

    print("I-4E.4 product_category normalization analysis completed.")
    print(f"Original product_category accuracy: {original_metrics['field_accuracy']['product_category']:.4f}")
    print(f"Post-normalized product_category accuracy: {post_metrics['field_accuracy']['product_category']:.4f}")
    print(f"Original overall field accuracy: {original_metrics['overall_field_accuracy']:.4f}")
    print(f"Post-normalized overall field accuracy: {post_metrics['overall_field_accuracy']:.4f}")
    print(f"Resolved product_category mismatches: {summary['product_category_analysis']['resolved_by_normalization_count']}")
    print(f"Remaining product_category mismatches: {summary['product_category_analysis']['remaining_mismatch_count']}")


if __name__ == "__main__":
    main()
