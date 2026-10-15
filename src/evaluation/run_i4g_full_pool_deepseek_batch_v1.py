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


FULL_POOL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv"
PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_predictions_v1.csv"
RAW_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_raw_predictions_v1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_report_v1.md"
FAILED_CASES_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_failed_cases_v1.csv"

PREDICTION_COLUMNS = [
    "email_id",
    "subject",
    "email_body_excerpt",
    "backend_used",
    "api_attempted",
    "api_error",
    "parse_success",
    "schema_validation_success",
    "retry_count",
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_name",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "key_information",
    "summary",
    "suggested_reply",
    "confidence",
    "model_name",
    "error_message",
    "api_error_message",
    "raw_response_excerpt",
]

FAILED_CASE_COLUMNS = [
    "email_id",
    "subject",
    "backend_used",
    "api_attempted",
    "api_error",
    "parse_success",
    "schema_validation_success",
    "retry_count",
    "error_message",
    "api_error_message",
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


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def prediction_text(email_row: dict[str, str]) -> str:
    return f"Subject: {email_row.get('subject', '')}\n\n{email_row.get('email_body', '')}"


def excerpt(text: str, length: int = 500) -> str:
    return str(text or "").replace("\r", " ").replace("\n", " ").strip()[:length]


def serialize_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def serialize_result(email_row: dict[str, str], result: dict[str, Any]) -> dict[str, Any]:
    api_error_message = str(result.get("api_error_message", "") or "")
    row: dict[str, Any] = {
        "email_id": email_row["email_id"],
        "subject": email_row.get("subject", ""),
        "email_body_excerpt": excerpt(email_row.get("email_body", "")),
        "backend_used": result.get("analyzer_backend", ""),
        "api_attempted": result.get("api_attempted", False),
        "api_error": bool(api_error_message.strip()),
        "parse_success": result.get("parse_success", False),
        "schema_validation_success": result.get("schema_validation_success", False),
        "retry_count": result.get("api_retry_count", 0),
        "sentiment": result.get("sentiment", ""),
        "urgency": result.get("urgency", ""),
        "is_complaint": result.get("is_complaint", ""),
        "store_location": result.get("store_location", ""),
        "product_name": result.get("product_name", ""),
        "product_category": result.get("product_category", ""),
        "complaint_reason": result.get("complaint_reason", ""),
        "source_attribution": result.get("source_attribution", ""),
        "key_information": serialize_value(result.get("key_information", [])),
        "summary": result.get("summary", ""),
        "suggested_reply": result.get("suggested_reply", ""),
        "confidence": result.get("confidence", ""),
        "model_name": result.get("model_name", ""),
        "error_message": result.get("error_message", ""),
        "api_error_message": api_error_message,
        "raw_response_excerpt": result.get("raw_response_preview", ""),
    }
    return row


def is_successful_prediction(row: dict[str, Any]) -> bool:
    return (
        truthy(row.get("parse_success"))
        and truthy(row.get("schema_validation_success"))
        and truthy(row.get("api_attempted"))
        and str(row.get("api_error", "")).strip().lower() in {"false", "0", "no"}
        and row.get("status", "succeeded") in {"succeeded", "success"}
        and not str(row.get("error_message", "") or "").strip()
        and not str(row.get("api_error_message", "") or "").strip()
        and str(row.get("backend_used", "")).strip() == "deepseek_api"
    )


def load_existing_successes() -> dict[str, dict[str, Any]]:
    if not PREDICTION_PATH.exists():
        return {}
    rows = read_csv(PREDICTION_PATH)
    from src.evaluation.core import index_rows
    index_rows(rows)
    return {row["email_id"]: row for row in rows if is_successful_prediction(row)}


def summarize(predictions: list[dict[str, Any]], runtime_seconds: float) -> dict[str, Any]:
    backend_counts = Counter(str(row.get("backend_used", "unknown")) for row in predictions)
    backend_used = backend_counts.most_common(1)[0][0] if backend_counts else "unknown"
    api_attempted_count = sum(1 for row in predictions if truthy(row.get("api_attempted")))
    api_error_count = sum(1 for row in predictions if truthy(row.get("api_error")))
    parse_success_count = sum(1 for row in predictions if truthy(row.get("parse_success")))
    schema_validation_success_count = sum(1 for row in predictions if truthy(row.get("schema_validation_success")))
    retry_total = sum(int(row.get("retry_count") or 0) for row in predictions)
    from src.evaluation.core import index_rows
    failed_cases = [row for row in predictions if not is_successful_prediction(row)]
    integrity_error = ""
    try:
        indexed = index_rows(predictions)
        expected = index_rows(read_csv(FULL_POOL_PATH))
        if indexed.keys() != expected.keys():
            integrity_error = 'Prediction IDs do not match the fixed historical input pool'
    except ValueError as exc:
        integrity_error = str(exc)
    accepted = len(predictions) == 400 and not failed_cases and not integrity_error
    return {
        "stage": "I-4G",
        "integrity_error": integrity_error,
        "provenance": "historical_flags_only; no reconstructed request metadata",
        "source_dataset_file": str(FULL_POOL_PATH),
        "total_rows": len(predictions),
        "backend_used": backend_used,
        "backend_counts": dict(backend_counts),
        "api_attempted_count": api_attempted_count,
        "api_error_count": api_error_count,
        "parse_success_count": parse_success_count,
        "schema_validation_success_count": schema_validation_success_count,
        "failed_count": len(failed_cases),
        "failed_email_ids": [str(row.get("email_id", "")) for row in failed_cases],
        "retry_total": retry_total,
        "runtime_seconds": round(runtime_seconds, 2),
        "accepted_for_dashboard_prediction_mode": accepted,
        "warning": "" if accepted else "I-4G is not accepted unless backend_used == deepseek_api and all 400 rows pass API, parse, and schema checks.",
        "output_files": {
            "predictions": str(PREDICTION_PATH),
            "raw_predictions": str(RAW_PREDICTION_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "failed_cases": str(FAILED_CASES_PATH),
        },
    }


def write_outputs(predictions: list[dict[str, Any]], runtime_seconds: float) -> dict[str, Any]:
    predictions = sorted(predictions, key=lambda row: str(row.get("email_id", "")))
    write_csv(PREDICTION_PATH, predictions, PREDICTION_COLUMNS)
    write_csv(RAW_PREDICTION_PATH, predictions, PREDICTION_COLUMNS)
    failed_rows = [row for row in predictions if not is_successful_prediction(row)]
    write_csv(FAILED_CASES_PATH, failed_rows, FAILED_CASE_COLUMNS)

    summary = summarize(predictions, runtime_seconds)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    config_summary = get_llm_config().safe_summary()
    lines = [
        "# I-4G Full Pool DeepSeek Batch Inference Report v1",
        "",
        "## Stage And Purpose",
        "",
        "I-4G runs DeepSeek inference on the 400-row full synthetic pool to create model-output dashboard statistics.",
        "",
        "## Evaluation Boundary",
        "",
        "- This is batch inference for dashboard/statistics mode, not formal model accuracy.",
        "- Formal accuracy remains the I-4E.2 80-case reviewed golden test set result: 88.21%.",
        "- The 400-row full pool is not manually reviewed as a golden benchmark.",
        "",
        "## Runtime Summary",
        "",
        f"- Backend used: {summary['backend_used']}",
        f"- API enabled in config: {config_summary['enabled']}",
        f"- API key configured: {config_summary['api_key_configured']}",
        f"- Model name: {config_summary['model_name']}",
        f"- Total rows: {summary['total_rows']}",
        f"- API attempted count: {summary['api_attempted_count']}",
        f"- API error count: {summary['api_error_count']}",
        f"- Parse success count: {summary['parse_success_count']}",
        f"- Schema validation success count: {summary['schema_validation_success_count']}",
        f"- Failed count: {summary['failed_count']}",
        f"- Retry total: {summary['retry_total']}",
        f"- Runtime seconds: {summary['runtime_seconds']}",
        f"- Accepted for dashboard prediction mode: {summary['accepted_for_dashboard_prediction_mode']}",
    ]
    if summary["warning"]:
        lines.extend(["", "## Warning", "", str(summary["warning"])])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    email_rows = sorted(read_csv(FULL_POOL_PATH), key=lambda row: row["email_id"])
    if len(email_rows) != 400:
        raise ValueError(f"I-4G requires exactly 400 full-pool rows; found {len(email_rows)}.")

    predictions_by_id = load_existing_successes()
    if predictions_by_id:
        print(f"Resuming from {len(predictions_by_id)} existing successful deepseek_api rows.")

    start = time.perf_counter()
    for index, email_row in enumerate(email_rows, start=1):
        email_id = email_row["email_id"]
        if email_id in predictions_by_id:
            print(f"[{index}/400] {email_id}: existing successful row kept.")
            continue
        print(f"[{index}/400] {email_id}: running DeepSeek/LangChain analyzer...")
        result = analyze_email_with_langchain(email_id, prediction_text(email_row))
        serialized = serialize_result(email_row, result)
        predictions_by_id[email_id] = serialized
        print(
            f"[{index}/400] {email_id}: backend={serialized['backend_used']} "
            f"parse={serialized['parse_success']} schema={serialized['schema_validation_success']} "
            f"api_error={serialized['api_error']} retry={serialized['retry_count']}"
        )
        write_outputs(list(predictions_by_id.values()), time.perf_counter() - start)

    summary = write_outputs(list(predictions_by_id.values()), time.perf_counter() - start)
    print("I-4G full pool DeepSeek batch inference finished.")
    print(f"Backend used: {summary['backend_used']}")
    print(f"API attempted count: {summary['api_attempted_count']}")
    print(f"API error count: {summary['api_error_count']}")
    print(f"Parse success count: {summary['parse_success_count']}")
    print(f"Schema validation success count: {summary['schema_validation_success_count']}")
    print(f"Accepted for dashboard prediction mode: {summary['accepted_for_dashboard_prediction_mode']}")
    print(f"Summary saved to: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
