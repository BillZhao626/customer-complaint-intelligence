from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chains.langchain_complaint_chain import analyze_email_with_langchain
from src.config.llm_config import get_llm_config


REVIEWED_EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_v1.csv"
REVIEWED_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv"
PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_predictions_v1.csv"
RAW_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_raw_predictions_v1.csv"
EVAL_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_eval_report_v1.md"
ERROR_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_error_analysis_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json"

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]

PREDICTION_COLUMNS = [
    "email_id",
    "store_location",
    "product_name",
    "product_category",
    "sentiment",
    "urgency",
    "is_complaint",
    "complaint_reason",
    "source_attribution",
    "key_information",
    "summary",
    "suggested_reply",
    "confidence",
    "analyzer_backend",
    "model_name",
    "parse_success",
    "schema_validation_success",
    "error_message",
    "api_attempted",
    "api_error_message",
    "api_retry_count",
    "raw_response_preview",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize(value: Any) -> str:
    text = str(value if value is not None else "").strip().lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    return text


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def prediction_text(email_row: dict[str, str]) -> str:
    return f"Subject: {email_row.get('subject', '')}\n\n{email_row.get('email_body', '')}"


def run_predictions(email_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    predictions = []
    for row in email_rows:
        result = analyze_email_with_langchain(row["email_id"], prediction_text(row))
        serialized = {}
        for key, value in result.items():
            if isinstance(value, (list, dict)):
                serialized[key] = json.dumps(value, ensure_ascii=False)
            else:
                serialized[key] = value
        predictions.append(serialized)
    return predictions


def compute_weighted_metrics(predictions: list[dict[str, Any]], labels: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    from src.evaluation.core import evaluate
    report = evaluate(predictions, labels, FIELDS)
    if report['status'] != 'valid':
        raise ValueError('; '.join(report['warnings']))
    mismatches = [dict(row, issue_type=classify_issue(row['field'], row['prediction'], row['golden_label'])) for row in report['mismatches']]
    return report['field_metrics'], mismatches


def classify_issue(field: str, prediction: str, expected: str) -> str:
    prediction_norm = normalize(prediction)
    expected_norm = normalize(expected)
    if field == "store_location":
        return "normalization_issue"
    if field == "urgency":
        return "urgency_threshold_issue"
    if field == "source_attribution":
        if any(term in f"{prediction_norm} {expected_norm}" for term in ["customer service", "store service", "refund", "delivery"]):
            return "source_attribution_boundary"
        return "model_error"
    if field == "product_category":
        if expected_norm in {"beauty/personal care", "sports/outdoor", "food/beverage", "service/other"}:
            return "taxonomy_ambiguity"
        return "model_error"
    if field == "complaint_reason":
        if expected_norm == "other" or prediction_norm == "other":
            return "possible_label_boundary"
        return "model_error"
    if field == "is_complaint":
        return "model_error"
    if field == "sentiment":
        return "possible_label_boundary" if {prediction_norm, expected_norm} <= {"neutral", "negative"} else "model_error"
    return "model_error"


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:300]


def summarize_runtime(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    backend_counts = Counter(str(row.get("analyzer_backend", "unknown")) for row in predictions)
    backend_used = backend_counts.most_common(1)[0][0] if backend_counts else "unknown"
    api_attempted_count = sum(1 for row in predictions if truthy(row.get("api_attempted")))
    api_error_count = sum(
        1 for row in predictions if truthy(row.get("api_attempted")) and str(row.get("api_error_message", "")).strip()
    )
    retry_count_total = sum(int(row.get("api_retry_count") or 0) for row in predictions)
    parse_success_count = sum(1 for row in predictions if truthy(row.get("parse_success")))
    schema_validation_success_count = sum(1 for row in predictions if truthy(row.get("schema_validation_success")))
    failed_email_ids = [
        str(row.get("email_id"))
        for row in predictions
        if not truthy(row.get("parse_success"))
        or not truthy(row.get("schema_validation_success"))
        or (truthy(row.get("api_attempted")) and str(row.get("api_error_message", "")).strip())
    ]
    return {
        "backend_used": backend_used,
        "api_attempted_count": api_attempted_count,
        "api_error_count": api_error_count,
        "retry_count_total": retry_count_total,
        "parse_success_count": parse_success_count,
        "schema_validation_success_count": schema_validation_success_count,
        "failed_email_ids": failed_email_ids,
    }


def write_reports(
    predictions: list[dict[str, Any]],
    labels: list[dict[str, str]],
    field_metrics: dict[str, Any],
    mismatches: list[dict[str, str]],
    runtime_seconds: float,
) -> dict[str, Any]:
    runtime = summarize_runtime(predictions)
    total_cases = len(predictions)
    total_field_count = total_cases * len(FIELDS)
    total_mismatch_count = len(mismatches)
    overall_field_accuracy = (total_field_count - total_mismatch_count) / total_field_count if total_field_count else 0.0
    mismatches_by_field = {field: int(field_metrics[field]["mismatches"]) for field in FIELDS}
    field_accuracy = {field: float(field_metrics[field]["accuracy"]) for field in FIELDS}
    issue_counts = Counter(row["issue_type"] for row in mismatches)
    config_summary = get_llm_config().safe_summary()

    eval_lines = [
        "# I-4E.2 Reviewed Golden Test Set 80-case Formal Evaluation",
        "",
        "## Stage And Purpose",
        "",
        "I-4E.2 runs the full 80-case DeepSeek evaluation against the human-reviewed golden test set.",
        "",
        "## Dataset",
        "",
        f"- Reviewed email file: `{REVIEWED_EMAIL_PATH}`",
        f"- Reviewed golden label file: `{REVIEWED_LABEL_PATH}`",
        "- Dataset role: reviewed golden test set, 80 cases.",
        "",
        "## Why This Is Formal Evaluation",
        "",
        "The labels are human-reviewed and versioned as the reviewed golden test set. The 400-row full dataset pool is not used here for formal accuracy metrics.",
        "",
        "## API Summary",
        "",
        f"- Backend used: {runtime['backend_used']}",
        f"- API enabled in config: {config_summary['enabled']}",
        f"- API key configured: {config_summary['api_key_configured']}",
        f"- Model name: {config_summary['model_name']}",
        f"- Runtime seconds: {runtime_seconds:.2f}",
        f"- API attempted count: {runtime['api_attempted_count']}",
        f"- API error count: {runtime['api_error_count']}",
        f"- Retry count total: {runtime['retry_count_total']}",
        "",
        "## Parse / Schema Summary",
        "",
        f"- Parse success count: {runtime['parse_success_count']}",
        f"- Schema validation success count: {runtime['schema_validation_success_count']}",
        f"- Failed email IDs: {', '.join(runtime['failed_email_ids']) if runtime['failed_email_ids'] else 'none'}",
        "",
        "## Field-level Metrics",
        "",
        "| Field | Accuracy | Precision weighted | Recall weighted | F1 weighted | Support | Mismatches |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for field in FIELDS:
        metric = field_metrics[field]
        eval_lines.append(
            f"| {field} | {metric['accuracy']:.4f} | {metric['precision_weighted']:.4f} | "
            f"{metric['recall_weighted']:.4f} | {metric['f1_weighted']:.4f} | {metric['support']} | {metric['mismatches']} |"
        )
    strongest = sorted(FIELDS, key=lambda field: field_accuracy[field], reverse=True)[:2]
    weakest = sorted(FIELDS, key=lambda field: field_accuracy[field])[:2]
    eval_lines.extend(
        [
            "",
            "## Overall Result",
            "",
            f"- Total cases: {total_cases}",
            f"- Total field count: {total_field_count}",
            f"- Total mismatch count: {total_mismatch_count}",
            f"- Overall field accuracy: {overall_field_accuracy:.4f}",
            "",
            "## Mismatch By Field",
            "",
            "| Field | Mismatches |",
            "|---|---:|",
        ]
    )
    for field in FIELDS:
        eval_lines.append(f"| {field} | {mismatches_by_field[field]} |")
    eval_lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Strongest fields: {', '.join(strongest)}.",
            f"- Weakest fields: {', '.join(weakest)}.",
            "- The 400-row full dataset pool remains for dashboard, batch processing, and case coverage, not formal accuracy metrics.",
            "",
        ]
    )
    EVAL_REPORT_PATH.write_text("\n".join(eval_lines), encoding="utf-8")

    error_lines = [
        "# I-4E.2 Reviewed 80-case Error Analysis v1",
        "",
        f"- Total mismatches: {total_mismatch_count}",
        "",
        "## Grouped Summary By Field",
        "",
        "| Field | Mismatches |",
        "|---|---:|",
    ]
    for field in FIELDS:
        error_lines.append(f"| {field} | {mismatches_by_field[field]} |")
    error_lines.extend(
        [
            "",
            "## Top Recurring Error Patterns",
            "",
            "| Issue type | Count |",
            "|---|---:|",
        ]
    )
    for issue_type, count in issue_counts.most_common():
        error_lines.append(f"| {issue_type} | {count} |")
    error_lines.extend(["", "## Mismatch Table", ""])
    if mismatches:
        error_lines.extend(["| Email ID | Field | Predicted value | Reviewed golden value | Issue type |", "|---|---|---|---|---|"])
        for row in mismatches:
            error_lines.append(
                f"| {md_cell(row['email_id'])} | {md_cell(row['field'])} | {md_cell(row['prediction'])} | "
                f"{md_cell(row['golden_label'])} | {md_cell(row['issue_type'])} |"
            )
    else:
        error_lines.append("No mismatches found.")
    error_lines.extend(
        [
            "",
            "## Recommended Next Action",
            "",
            "Prompt refinement is recommended only if recurring model errors are clear. Otherwise, preserve the current prompt and move to dashboard / full batch statistics.",
            "",
        ]
    )
    ERROR_REPORT_PATH.write_text("\n".join(error_lines), encoding="utf-8")

    summary = {
        "stage": "I-4E.2",
        "backend_used": runtime["backend_used"],
        "api_attempted_count": runtime["api_attempted_count"],
        "api_error_count": runtime["api_error_count"],
        "retry_count_total": runtime["retry_count_total"],
        "parse_success_count": runtime["parse_success_count"],
        "schema_validation_success_count": runtime["schema_validation_success_count"],
        "total_cases": total_cases,
        "fields_compared": FIELDS,
        "total_field_count": total_field_count,
        "total_mismatch_count": total_mismatch_count,
        "overall_field_accuracy": overall_field_accuracy,
        "field_accuracy": field_accuracy,
        "field_metrics": field_metrics,
        "mismatches_by_field": mismatches_by_field,
        "failed_email_ids": runtime["failed_email_ids"],
        "top_recurring_error_patterns": dict(issue_counts.most_common()),
        "output_files": {
            "predictions": str(PREDICTION_PATH),
            "raw_predictions": str(RAW_PREDICTION_PATH),
            "eval_report": str(EVAL_REPORT_PATH),
            "error_analysis": str(ERROR_REPORT_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
        },
        "recommendation": "proceed_to_i4e3_result_interpretation_or_i4f_full_pool_dashboard_statistics",
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    email_rows = sorted(read_csv(REVIEWED_EMAIL_PATH), key=lambda row: row["email_id"])
    label_rows = sorted(read_csv(REVIEWED_LABEL_PATH), key=lambda row: row["email_id"])
    if len(email_rows) != 80 or len(label_rows) != 80:
        raise ValueError(f"I-4E.2 requires 80 emails and 80 reviewed labels; found {len(email_rows)} and {len(label_rows)}.")
    if {row["email_id"] for row in email_rows} != {row["email_id"] for row in label_rows}:
        raise ValueError("Reviewed email IDs and reviewed label IDs do not match.")

    start = time.perf_counter()
    predictions = run_predictions(email_rows)
    runtime_seconds = time.perf_counter() - start

    write_csv(PREDICTION_PATH, predictions, PREDICTION_COLUMNS)
    write_csv(RAW_PREDICTION_PATH, predictions, PREDICTION_COLUMNS)
    field_metrics, mismatches = compute_weighted_metrics(predictions, label_rows)
    summary = write_reports(predictions, label_rows, field_metrics, mismatches, runtime_seconds)

    print("I-4E.2 reviewed 80-case evaluation completed.")
    print(f"Backend used: {summary['backend_used']}")
    print(f"Total cases: {summary['total_cases']}")
    print(f"API attempted count: {summary['api_attempted_count']}")
    print(f"API error count: {summary['api_error_count']}")
    print(f"Parse success count: {summary['parse_success_count']}")
    print(f"Schema validation success count: {summary['schema_validation_success_count']}")
    print(f"Total mismatches: {summary['total_mismatch_count']}")
    print(f"Overall field accuracy: {summary['overall_field_accuracy']:.4f}")
    print(f"Predictions saved to: {PREDICTION_PATH}")
    print(f"Summary saved to: {SUMMARY_JSON_PATH}")


if __name__ == "__main__":
    main()
