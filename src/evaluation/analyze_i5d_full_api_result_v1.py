from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

I4G_PREDICTIONS_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_predictions_v1.csv"
I4G_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json"
I4G_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_report_v1.md"
I5D_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i5d_full_api_result_summary_v1.json"
I5D_REPORT_PATH = PROJECT_ROOT / "outputs" / "i5d_full_api_result_interpretation_report_v1.md"
SUPERVISOR_UPDATE_PATH = PROJECT_ROOT / "outputs" / "i5d_supervisor_progress_update_draft_v1.md"

DISTRIBUTION_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "store_location",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def validate_i4g_acceptance(summary: dict[str, Any], prediction_count: int) -> None:
    expected = {
        "stage": "I-4G",
        "total_rows": 400,
        "backend_used": "deepseek_api",
        "api_attempted_count": 400,
        "api_error_count": 0,
        "parse_success_count": 400,
        "schema_validation_success_count": 400,
        "accepted_for_dashboard_prediction_mode": True,
    }
    errors = []
    for key, expected_value in expected.items():
        if summary.get(key) != expected_value:
            errors.append(f"{key} must be {expected_value!r}, found {summary.get(key)!r}")
    if prediction_count != 400:
        errors.append(f"prediction row count must be 400, found {prediction_count}")
    if errors:
        raise ValueError("I-4G accepted result validation failed: " + "; ".join(errors))


def distribution(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter((row.get(field, "") or "unknown") for row in rows).items()))


def top_negative_high_urgency_cases(rows: list[dict[str, str]], limit: int = 20) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if str(row.get("sentiment", "")).lower() == "negative"
        and str(row.get("urgency", "")).lower() == "high"
    ]
    if len(selected) < limit:
        selected.extend(
            row
            for row in rows
            if row not in selected
            and str(row.get("sentiment", "")).lower() == "negative"
            and is_true(row.get("is_complaint"))
        )
    selected.sort(key=lambda row: ({"high": 0, "medium": 1, "low": 2}.get(str(row.get("urgency", "")).lower(), 9), row.get("email_id", "")))
    return [
        {
            "email_id": row.get("email_id", ""),
            "subject": row.get("subject", ""),
            "sentiment": row.get("sentiment", ""),
            "urgency": row.get("urgency", ""),
            "store_location": row.get("store_location", ""),
            "product_category": row.get("product_category", ""),
            "complaint_reason": row.get("complaint_reason", ""),
            "source_attribution": row.get("source_attribution", ""),
            "summary": row.get("summary", ""),
        }
        for row in selected[:limit]
    ]


def markdown_distribution_table(title: str, counts: dict[str, int], total: int) -> list[str]:
    lines = [f"### {title}", "", "| Label | Count | Percentage |", "|---|---:|---:|"]
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        percentage = count / total * 100 if total else 0.0
        lines.append(f"| {label} | {count} | {percentage:.2f}% |")
    return lines


def write_interpretation_report(summary: dict[str, Any]) -> None:
    lines = [
        "# I-5D Full API Result Interpretation Report v1",
        "",
        "## Stage And Purpose",
        "",
        (
            "I-5D interprets the accepted I-4G full-pool DeepSeek batch result. This is analysis-only: "
            "no DeepSeek API call is made and no model inference is rerun."
        ),
        "",
        "## I-4G Acceptance Status",
        "",
        f"- Backend used: {summary['backend_used']}",
        f"- Total rows: {summary['total_rows']}",
        f"- API attempted count: {summary['api_attempted_count']}",
        f"- API error count: {summary['api_error_count']}",
        f"- Parse success count: {summary['parse_success_count']}",
        f"- Schema validation success count: {summary['schema_validation_success_count']}",
        f"- Failed count: {summary['failed_count']}",
        f"- Retry total: {summary['retry_total']}",
        f"- Runtime seconds: {summary['runtime_seconds']}",
        f"- Average seconds per case: {summary['average_seconds_per_case']:.2f}",
        "",
        "## Interpretation",
        "",
        (
            "The 400-row batch demonstrates stable real API batch processing: all 400 rows were attempted with "
            "DeepSeek, no API errors occurred, and all outputs passed parse and schema validation. These statistics "
            "support system-level dashboard and batch-processing evidence, not formal model accuracy."
        ),
        "",
        "## Formal Evaluation Boundary",
        "",
        (
            "Formal Reviewed Golden Evaluation remains the I-4E.2 80-case reviewed golden test set result: 88.21% "
            "field accuracy. The 400-row full pool is not formal accuracy."
        ),
        "",
        "## Prediction Distributions",
        "",
    ]
    for field in DISTRIBUTION_FIELDS:
        lines.extend(markdown_distribution_table(field, summary["distributions"][field], summary["total_rows"]))
        lines.append("")
    lines.extend(
        [
            "## Representative Negative / High-Urgency Cases",
            "",
            "| Email ID | Sentiment | Urgency | Product | Reason | Source |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in summary["representative_negative_high_urgency_cases"][:10]:
        lines.append(
            f"| {row['email_id']} | {row['sentiment']} | {row['urgency']} | "
            f"{row['product_category']} | {row['complaint_reason']} | {row['source_attribution']} |"
        )
    I5D_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_supervisor_update(summary: dict[str, Any]) -> None:
    lines = [
        "# Supervisor Progress Update Draft v1",
        "",
        "Dear [Supervisor Name],",
        "",
        (
            "I have completed the full-pool DeepSeek batch-processing stage and the dashboard evidence update. "
            "The 400-row synthetic customer email pool was processed with the real DeepSeek API."
        ),
        "",
        (
            "The API run was stable: 400/400 API calls were successful, with 0 API errors, and 400/400 outputs "
            "passed parsing and schema validation. The runtime was 2515.43 seconds."
        ),
        "",
        (
            "The Streamlit dashboard now supports three modes: Synthetic Reference Statistics, DeepSeek Prediction "
            "Statistics, and Formal Reviewed Golden Evaluation. The formal model accuracy remains based on the "
            "80-case manually reviewed golden test set, with 88.21% field accuracy."
        ),
        "",
        (
            "The 400-row prediction dashboard is used for system demonstration and model-output statistics, not formal "
            "accuracy. Product_category normalization remains a known caveat and possible follow-up optimization."
        ),
        "",
        (
            "My next plan is to capture UI screenshots, finalize the evidence package, and then decide whether to polish "
            "the Streamlit interface further or add a FastAPI service layer."
        ),
        "",
        "Best regards,",
        "[Your Name]",
    ]
    SUPERVISOR_UPDATE_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    i4g_summary = read_json(I4G_SUMMARY_PATH)
    predictions = read_csv(I4G_PREDICTIONS_PATH)
    validate_i4g_acceptance(i4g_summary, len(predictions))

    runtime_seconds = float(i4g_summary.get("runtime_seconds", 0.0))
    total_rows = int(i4g_summary.get("total_rows", len(predictions)))
    result_summary = {
        "stage": "I-5D",
        "source_i4g_summary_file": str(I4G_SUMMARY_PATH),
        "source_prediction_file": str(I4G_PREDICTIONS_PATH),
        "source_i4g_report_file": str(I4G_REPORT_PATH),
        "total_rows": total_rows,
        "runtime_seconds": runtime_seconds,
        "average_seconds_per_case": runtime_seconds / total_rows if total_rows else 0.0,
        "backend_used": i4g_summary["backend_used"],
        "backend_counts": i4g_summary.get("backend_counts", {}),
        "api_attempted_count": i4g_summary["api_attempted_count"],
        "api_error_count": i4g_summary["api_error_count"],
        "retry_total": i4g_summary.get("retry_total", 0),
        "failed_count": i4g_summary["failed_count"],
        "parse_success_count": i4g_summary["parse_success_count"],
        "schema_validation_success_count": i4g_summary["schema_validation_success_count"],
        "parse_schema_stability": {
            "parse_success_rate": i4g_summary["parse_success_count"] / total_rows if total_rows else 0.0,
            "schema_validation_success_rate": i4g_summary["schema_validation_success_count"] / total_rows if total_rows else 0.0,
        },
        "accepted_for_dashboard_prediction_mode": i4g_summary.get("accepted_for_dashboard_prediction_mode") is True,
        "distributions": {field: distribution(predictions, field) for field in DISTRIBUTION_FIELDS},
        "representative_negative_high_urgency_cases": top_negative_high_urgency_cases(predictions),
        "evaluation_boundary": "400-row DeepSeek prediction statistics are dashboard/model-output statistics, not formal accuracy. Formal accuracy remains 88.21% on the 80-case reviewed golden test set.",
    }

    I5D_SUMMARY_PATH.write_text(json.dumps(result_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_interpretation_report(result_summary)
    write_supervisor_update(result_summary)

    print("I-5D full API result interpretation completed.")
    print(f"Total rows: {total_rows}")
    print(f"Runtime seconds: {runtime_seconds:.2f}")
    print(f"Average seconds per case: {result_summary['average_seconds_per_case']:.2f}")
    print(f"API errors: {result_summary['api_error_count']}")
    print(f"Parse/schema success: {result_summary['parse_success_count']}/{result_summary['schema_validation_success_count']}")


if __name__ == "__main__":
    main()
