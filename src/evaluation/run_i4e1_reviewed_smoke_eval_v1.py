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
SMOKE_EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_smoke20_v1.csv"
SMOKE_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_smoke20_v1.csv"

PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_predictions_v1.csv"
RAW_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_raw_predictions_v1.csv"
EVAL_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_eval_report_v1.md"
ERROR_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_error_analysis_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_summary_v1.json"

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


def select_smoke_cases(email_rows: list[dict[str, str]], label_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    labels_by_id = {row["email_id"]: row for row in label_rows}
    joined = [{**row, **{f"label_{key}": value for key, value in labels_by_id[row["email_id"]].items()}} for row in email_rows]
    joined.sort(key=lambda row: row["email_id"])

    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()

    guarantee_pairs = [
        ("label_sentiment", "negative"),
        ("label_sentiment", "neutral"),
        ("label_sentiment", "positive"),
        ("label_urgency", "high"),
        ("label_urgency", "medium"),
        ("label_urgency", "low"),
        ("label_source_attribution", "product issue"),
        ("label_source_attribution", "delivery/logistics issue"),
        ("label_source_attribution", "customer service response issue"),
        ("label_source_attribution", "store service issue"),
        ("label_source_attribution", "refund/exchange process issue"),
        ("label_source_attribution", "none"),
        ("label_source_attribution", "unclear"),
        ("label_complaint_reason", "health or safety issue"),
        ("label_complaint_reason", "wrong item"),
        ("label_complaint_reason", "refund request"),
    ]
    for field, value in guarantee_pairs:
        match = next((row for row in joined if row[field] == value and row["email_id"] not in selected_ids), None)
        if match:
            selected.append(match)
            selected_ids.add(match["email_id"])

    target_sentiment = {"negative": 13, "neutral": 4, "positive": 3}
    target_urgency = {"high": 3, "medium": 11, "low": 6}
    target_category_min = 2

    def score(row: dict[str, str]) -> tuple[float, str]:
        labels = [labels_by_id[item["email_id"]] for item in selected]
        sentiment_counts = Counter(item["sentiment"] for item in labels)
        urgency_counts = Counter(item["urgency"] for item in labels)
        category_counts = Counter(item["product_category"] for item in labels)
        reason_counts = Counter(item["complaint_reason"] for item in labels)
        source_counts = Counter(item["source_attribution"] for item in labels)
        store_counts = Counter(item["store_location"] for item in labels)

        label = labels_by_id[row["email_id"]]
        value = 0.0
        value += max(0, target_sentiment.get(label["sentiment"], 0) - sentiment_counts[label["sentiment"]]) * 3
        value += max(0, target_urgency.get(label["urgency"], 0) - urgency_counts[label["urgency"]]) * 3
        value += max(0, target_category_min - category_counts[label["product_category"]]) * 2
        if reason_counts[label["complaint_reason"]] == 0:
            value += 4
        if source_counts[label["source_attribution"]] == 0:
            value += 4
        if store_counts[label["store_location"]] == 0:
            value += 2
        return (value, row["email_id"])

    while len(selected) < 20:
        remaining = [row for row in joined if row["email_id"] not in selected_ids]
        best = max(remaining, key=score)
        selected.append(best)
        selected_ids.add(best["email_id"])

    selected.sort(key=lambda row: row["email_id"])
    selected_emails = [{key: value for key, value in row.items() if not key.startswith("label_")} for row in selected]
    selected_labels = [labels_by_id[row["email_id"]] for row in selected]
    return selected_emails, selected_labels


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


def compute_metrics(predictions: list[dict[str, Any]], labels: list[dict[str, str]]) -> tuple[dict[str, float], list[dict[str, str]], dict[str, int]]:
    predictions_by_id = {str(row["email_id"]): row for row in predictions}
    labels_by_id = {row["email_id"]: row for row in labels}
    field_accuracy: dict[str, float] = {}
    mismatches: list[dict[str, str]] = []
    mismatches_by_field: dict[str, int] = {}
    common_ids = sorted(set(predictions_by_id) & set(labels_by_id))

    for field in FIELDS:
        correct = 0
        for email_id in common_ids:
            prediction = predictions_by_id[email_id].get(field, "")
            expected = labels_by_id[email_id].get(field, "")
            if normalize(prediction) == normalize(expected):
                correct += 1
            else:
                mismatches.append(
                    {
                        "email_id": email_id,
                        "field": field,
                        "prediction": str(prediction),
                        "golden_label": str(expected),
                    }
                )
        total = len(common_ids)
        field_accuracy[field] = correct / total if total else 0.0
        mismatches_by_field[field] = total - correct
    return field_accuracy, mismatches, mismatches_by_field


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:300]


def write_reports(
    predictions: list[dict[str, Any]],
    labels: list[dict[str, str]],
    field_accuracy: dict[str, float],
    mismatches: list[dict[str, str]],
    mismatches_by_field: dict[str, int],
    runtime_seconds: float,
) -> dict[str, Any]:
    backend_counts = Counter(str(row.get("analyzer_backend", "unknown")) for row in predictions)
    backend_used = backend_counts.most_common(1)[0][0] if backend_counts else "unknown"
    api_attempted_count = sum(1 for row in predictions if truthy(row.get("api_attempted")))
    api_error_count = sum(
        1 for row in predictions if truthy(row.get("api_attempted")) and str(row.get("api_error_message", "")).strip()
    )
    parse_success_count = sum(1 for row in predictions if truthy(row.get("parse_success")))
    schema_success_count = sum(1 for row in predictions if truthy(row.get("schema_validation_success")))
    failed_email_ids = [
        str(row.get("email_id"))
        for row in predictions
        if not truthy(row.get("parse_success"))
        or not truthy(row.get("schema_validation_success"))
        or (truthy(row.get("api_attempted")) and str(row.get("api_error_message", "")).strip())
    ]
    config = get_llm_config()
    config_summary = config.safe_summary()

    eval_lines = [
        "# I-4E.1 Reviewed Golden Test Set 20-case Smoke Evaluation",
        "",
        "## Stage And Purpose",
        "",
        "I-4E.1 runs a 20-case smoke evaluation against the reviewed golden test set before the full 80-case evaluation.",
        "",
        "## Inputs And Outputs",
        "",
        f"- Smoke email file: `{SMOKE_EMAIL_PATH}`",
        f"- Smoke reviewed label file: `{SMOKE_LABEL_PATH}`",
        f"- Prediction file: `{PREDICTION_PATH}`",
        f"- Raw prediction file: `{RAW_PREDICTION_PATH}`",
        "",
        "## Runtime Summary",
        "",
        f"- Backend used: {backend_used}",
        f"- API enabled in config: {config_summary['enabled']}",
        f"- API key configured: {config_summary['api_key_configured']}",
        f"- Model name: {config_summary['model_name']}",
        f"- Runtime seconds: {runtime_seconds:.2f}",
        f"- Total cases: {len(predictions)}",
        f"- API attempted count: {api_attempted_count}",
        f"- API error count: {api_error_count}",
        f"- Parse success count: {parse_success_count}",
        f"- Schema validation success count: {schema_success_count}",
        "",
        "## Field-level Accuracy",
        "",
        "| Field | Accuracy | Mismatches |",
        "|---|---:|---:|",
    ]
    for field in FIELDS:
        eval_lines.append(f"| {field} | {field_accuracy[field]:.4f} | {mismatches_by_field[field]} |")
    eval_lines.extend(
        [
            "",
            f"- Total mismatch count: {len(mismatches)}",
            "",
            "## Recommendation",
            "",
            "Proceed to I-4E.2 full 80-case evaluation if smoke is stable: API attempts, parsing, and schema validation should all succeed for the 20 smoke cases.",
            "",
        ]
    )
    EVAL_REPORT_PATH.write_text("\n".join(eval_lines), encoding="utf-8")

    error_lines = [
        "# I-4E.1 Reviewed Smoke Error Analysis v1",
        "",
        f"- Total mismatches: {len(mismatches)}",
        "",
        "## Mismatches By Field",
        "",
        "| Field | Mismatches |",
        "|---|---:|",
    ]
    for field in FIELDS:
        error_lines.append(f"| {field} | {mismatches_by_field[field]} |")
    error_lines.extend(["", "## Mismatch Table", ""])
    if mismatches:
        error_lines.extend(["| Email ID | Field | Prediction | Reviewed label |", "|---|---|---|---|"])
        for item in mismatches:
            error_lines.append(
                f"| {md_cell(item['email_id'])} | {md_cell(item['field'])} | {md_cell(item['prediction'])} | {md_cell(item['golden_label'])} |"
            )
    else:
        error_lines.append("No mismatches found.")
    error_lines.extend(["", "## Failed Email IDs", "", ", ".join(failed_email_ids) if failed_email_ids else "none", ""])
    ERROR_REPORT_PATH.write_text("\n".join(error_lines), encoding="utf-8")

    summary = {
        "stage": "I-4E.1",
        "backend_used": backend_used,
        "api_attempted_count": api_attempted_count,
        "api_error_count": api_error_count,
        "parse_success_count": parse_success_count,
        "schema_validation_success_count": schema_success_count,
        "total_cases": len(predictions),
        "fields_compared": FIELDS,
        "field_accuracy": field_accuracy,
        "total_mismatch_count": len(mismatches),
        "mismatches_by_field": mismatches_by_field,
        "failed_email_ids": failed_email_ids,
        "output_files": {
            "smoke_email_file": str(SMOKE_EMAIL_PATH),
            "smoke_reviewed_label_file": str(SMOKE_LABEL_PATH),
            "predictions": str(PREDICTION_PATH),
            "raw_predictions": str(RAW_PREDICTION_PATH),
            "eval_report": str(EVAL_REPORT_PATH),
            "error_analysis": str(ERROR_REPORT_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
        },
        "recommendation": "proceed_to_i4e2_full_80_eval if smoke is stable",
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    email_rows = read_csv(REVIEWED_EMAIL_PATH)
    label_rows = read_csv(REVIEWED_LABEL_PATH)
    selected_emails, selected_labels = select_smoke_cases(email_rows, label_rows)

    write_csv(SMOKE_EMAIL_PATH, selected_emails, list(selected_emails[0].keys()))
    write_csv(SMOKE_LABEL_PATH, selected_labels, list(selected_labels[0].keys()))

    start = time.perf_counter()
    predictions = run_predictions(selected_emails)
    runtime_seconds = time.perf_counter() - start

    write_csv(PREDICTION_PATH, predictions, PREDICTION_COLUMNS)
    write_csv(RAW_PREDICTION_PATH, predictions, PREDICTION_COLUMNS)
    field_accuracy, mismatches, mismatches_by_field = compute_metrics(predictions, selected_labels)
    summary = write_reports(predictions, selected_labels, field_accuracy, mismatches, mismatches_by_field, runtime_seconds)

    print("I-4E.1 reviewed smoke evaluation completed.")
    print(f"Backend used: {summary['backend_used']}")
    print(f"Total cases: {summary['total_cases']}")
    print(f"API attempted count: {summary['api_attempted_count']}")
    print(f"API error count: {summary['api_error_count']}")
    print(f"Parse success count: {summary['parse_success_count']}")
    print(f"Schema validation success count: {summary['schema_validation_success_count']}")
    print(f"Total mismatches: {summary['total_mismatch_count']}")
    print(f"Predictions saved to: {PREDICTION_PATH}")
    print(f"Summary saved to: {SUMMARY_JSON_PATH}")


if __name__ == "__main__":
    main()
