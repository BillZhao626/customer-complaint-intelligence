from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_predictions_v1.csv"
I4G_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json"
DASHBOARD_DIR = PROJECT_ROOT / "outputs" / "dashboard_i5c_deepseek"

STORE_RANKING_PATH = DASHBOARD_DIR / "deepseek_store_complaint_ranking_v1.csv"
PRODUCT_RANKING_PATH = DASHBOARD_DIR / "deepseek_product_negative_sentiment_ranking_v1.csv"
COMPLAINT_REASON_PATH = DASHBOARD_DIR / "deepseek_complaint_reason_distribution_v1.csv"
SOURCE_ATTRIBUTION_PATH = DASHBOARD_DIR / "deepseek_source_attribution_distribution_v1.csv"
URGENCY_PATH = DASHBOARD_DIR / "deepseek_urgency_distribution_v1.csv"
SENTIMENT_PATH = DASHBOARD_DIR / "deepseek_sentiment_distribution_v1.csv"
STORE_PRODUCT_MATRIX_PATH = DASHBOARD_DIR / "deepseek_store_by_product_matrix_v1.csv"
DEMO_CASES_PATH = DASHBOARD_DIR / "deepseek_negative_complaint_cases_for_demo_v1.csv"
DASHBOARD_JSON_PATH = DASHBOARD_DIR / "deepseek_dashboard_stats_v1.json"
REPORT_PATH = DASHBOARD_DIR / "i5c_deepseek_dashboard_statistics_report_v1.md"
PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "dashboard_i5c_deepseek_profile_v1.json"
COMBINED_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4g_i5c_full_pool_deepseek_dashboard_update_report_v1.md"


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


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def percentage(count: int, total: int) -> float:
    return round(count / total * 100, 2) if total else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def require_accepted_i4g() -> dict[str, Any]:
    summary = read_json(I4G_SUMMARY_PATH)
    if summary.get("stage") != "I-4G" or summary.get("accepted_for_dashboard_prediction_mode") is not True:
        raise RuntimeError("I-5C requires accepted I-4G output before building DeepSeek prediction dashboard statistics.")
    if summary.get("backend_used") != "deepseek_api":
        raise RuntimeError("I-5C requires I-4G backend_used == deepseek_api.")
    return summary


def store_ranking(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("store_location", "unknown") or "unknown"].append(row)
    output: list[dict[str, Any]] = []
    for store, group_rows in grouped.items():
        total = len(group_rows)
        complaint_count = sum(is_true(row.get("is_complaint")) for row in group_rows)
        negative_count = sum(str(row.get("sentiment", "")).strip().lower() == "negative" for row in group_rows)
        high_urgency_count = sum(str(row.get("urgency", "")).strip().lower() == "high" for row in group_rows)
        output.append(
            {
                "store_location": store,
                "total_emails": total,
                "complaint_count": complaint_count,
                "negative_count": negative_count,
                "high_urgency_count": high_urgency_count,
                "complaint_rate": rate(complaint_count, total),
                "negative_rate": rate(negative_count, total),
            }
        )
    return sorted(output, key=lambda row: (-row["complaint_count"], -row["negative_count"], row["store_location"]))


def product_ranking(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("product_category", "unknown") or "unknown"].append(row)
    output: list[dict[str, Any]] = []
    for product_category, group_rows in grouped.items():
        total = len(group_rows)
        negative_count = sum(str(row.get("sentiment", "")).strip().lower() == "negative" for row in group_rows)
        complaint_count = sum(is_true(row.get("is_complaint")) for row in group_rows)
        high_urgency_count = sum(str(row.get("urgency", "")).strip().lower() == "high" for row in group_rows)
        output.append(
            {
                "product_category": product_category,
                "total_emails": total,
                "negative_count": negative_count,
                "complaint_count": complaint_count,
                "high_urgency_count": high_urgency_count,
                "negative_rate": rate(negative_count, total),
                "complaint_rate": rate(complaint_count, total),
            }
        )
    return sorted(output, key=lambda row: (-row["negative_count"], -row["complaint_count"], row["product_category"]))


def distribution(rows: list[dict[str, str]], source_field: str, label_name: str) -> list[dict[str, Any]]:
    counts = Counter((row.get(source_field, "") or "unknown") for row in rows)
    total = len(rows)
    output = [
        {label_name: label, "count": count, "percentage": percentage(count, total)}
        for label, count in sorted(counts.items())
    ]
    return sorted(output, key=lambda row: (-row["count"], str(row[label_name])))


def store_product_matrix(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        store = row.get("store_location", "unknown") or "unknown"
        product = row.get("product_category", "unknown") or "unknown"
        grouped[(store, product)].append(row)
    output: list[dict[str, Any]] = []
    for (store, product), group_rows in grouped.items():
        output.append(
            {
                "store_location": store,
                "product_category": product,
                "email_count": len(group_rows),
                "complaint_count": sum(is_true(row.get("is_complaint")) for row in group_rows),
                "negative_count": sum(str(row.get("sentiment", "")).strip().lower() == "negative" for row in group_rows),
            }
        )
    return sorted(output, key=lambda row: (row["store_location"], row["product_category"]))


def select_demo_cases(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if str(row.get("sentiment", "")).strip().lower() == "negative" and is_true(row.get("is_complaint"))
    ]
    candidates.sort(key=lambda row: ({"high": 0, "medium": 1, "low": 2}.get(str(row.get("urgency", "")).lower(), 9), row["email_id"]))
    return [
        {
            "email_id": row.get("email_id", ""),
            "subject": row.get("subject", ""),
            "email_body_excerpt": row.get("email_body_excerpt", ""),
            "sentiment": row.get("sentiment", ""),
            "urgency": row.get("urgency", ""),
            "store_location": row.get("store_location", ""),
            "product_category": row.get("product_category", ""),
            "complaint_reason": row.get("complaint_reason", ""),
            "source_attribution": row.get("source_attribution", ""),
            "summary": row.get("summary", ""),
            "suggested_reply": row.get("suggested_reply", ""),
        }
        for row in candidates[:20]
    ]


def build_dashboard_json(
    rows: list[dict[str, str]],
    store_rows: list[dict[str, Any]],
    product_rows: list[dict[str, Any]],
    reason_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    urgency_rows: list[dict[str, Any]],
    sentiment_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    top_store = store_rows[0] if store_rows else {}
    top_product = product_rows[0] if product_rows else {}
    top_reason = reason_rows[0] if reason_rows else {}
    top_source = source_rows[0] if source_rows else {}
    return {
        "stage": "I-5C",
        "source_prediction_file": str(PREDICTION_PATH),
        "total_rows": len(rows),
        "label_status": "deepseek_predictions_for_dashboard_statistics_not_formal_accuracy",
        "store_complaint_ranking": store_rows,
        "product_negative_sentiment_ranking": product_rows,
        "complaint_reason_distribution": reason_rows,
        "source_attribution_distribution": source_rows,
        "urgency_distribution": urgency_rows,
        "sentiment_distribution": sentiment_rows,
        "top_insights": [
            f"Top predicted store by complaint count: {top_store.get('store_location')} with {top_store.get('complaint_count')} complaints.",
            f"Top predicted product category by negative sentiment count: {top_product.get('product_category')} with {top_product.get('negative_count')} negative cases.",
            f"Most common predicted complaint reason: {top_reason.get('complaint_reason')} with {top_reason.get('count')} cases.",
            f"Most common predicted source attribution: {top_source.get('source_attribution')} with {top_source.get('count')} cases.",
        ],
        "warning": "400-row DeepSeek prediction statistics are model-output dashboard statistics, not formal accuracy. Formal accuracy remains the 80-case reviewed golden test set result: 88.21%.",
    }


def write_report(rows: list[dict[str, str]], dashboard_json: dict[str, Any], i4g_summary: dict[str, Any]) -> None:
    lines = [
        "# I-5C DeepSeek Prediction Dashboard Statistics Report v1",
        "",
        "## Stage And Purpose",
        "",
        "I-5C builds dashboard statistics from real DeepSeek predictions on the 400-row full synthetic pool.",
        "",
        "## Data Source",
        "",
        f"- Prediction file: `{PREDICTION_PATH}`",
        f"- I-4G backend: {i4g_summary.get('backend_used')}",
        f"- Rows: {len(rows)}",
        "",
        "## Evaluation Boundary",
        "",
        "These are DeepSeek prediction statistics, not formal accuracy. Formal accuracy remains 88.21% on the 80-case reviewed golden test set.",
        "",
        "## Top Insights",
        "",
    ]
    for insight in dashboard_json["top_insights"]:
        lines.append(f"- {insight}")
    lines.extend(
        [
            "",
            "## Product Category Caveat",
            "",
            "Product_category normalization remains a known post-processing / taxonomy alignment caveat. This stage does not patch active chain normalization.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_profile() -> None:
    profile = {
        "version": "v1",
        "stage": "I-5C",
        "source_prediction_file": str(PREDICTION_PATH),
        "source_i4g_summary_file": str(I4G_SUMMARY_PATH),
        "dashboard_output_dir": str(DASHBOARD_DIR),
        "generated_json": str(DASHBOARD_JSON_PATH),
        "generated_tables": [
            str(STORE_RANKING_PATH),
            str(PRODUCT_RANKING_PATH),
            str(COMPLAINT_REASON_PATH),
            str(SOURCE_ATTRIBUTION_PATH),
            str(URGENCY_PATH),
            str(SENTIMENT_PATH),
            str(STORE_PRODUCT_MATRIX_PATH),
            str(DEMO_CASES_PATH),
        ],
        "label_status": "deepseek_predictions_for_dashboard_statistics_not_formal_accuracy",
        "formal_evaluation_reference": "I-4E.2 80-case reviewed golden test set",
        "formal_accuracy": 0.8821,
        "recommended_next_stage": "Streamlit_dashboard_screenshot_packaging_or_dissertation_results_writeup",
    }
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def write_combined_report(rows: list[dict[str, str]], dashboard_json: dict[str, Any], i4g_summary: dict[str, Any]) -> None:
    sentiment_counts = {row["sentiment"]: row["count"] for row in dashboard_json["sentiment_distribution"]}
    urgency_counts = {row["urgency"]: row["count"] for row in dashboard_json["urgency_distribution"]}
    lines = [
        "# I-4G / I-5C Full Pool DeepSeek Dashboard Update Report v1",
        "",
        "## Stage And Purpose",
        "",
        (
            "I-4G / I-5C runs real DeepSeek batch inference over the 400-row full synthetic pool, "
            "builds DeepSeek prediction dashboard statistics, and updates the Streamlit dashboard to support multiple data modes."
        ),
        "",
        "## Why Run 400-row DeepSeek Batch Inference",
        "",
        (
            "The 80-case reviewed golden test set provides formal accuracy. The 400-row full pool provides a larger "
            "system demonstration for batch processing, model-output dashboard statistics, and UI aggregation behavior."
        ),
        "",
        "## Dashboard Modes",
        "",
        "- Synthetic Reference Statistics: 400-row full pool auto labels for dataset/dashboard reference statistics, not formal model accuracy.",
        "- DeepSeek Prediction Statistics: real DeepSeek model predictions on the 400-row full pool for model-output dashboard statistics, not formal model accuracy.",
        "- Formal Reviewed Golden Evaluation: 80-case manually reviewed golden test set for formal accuracy; field accuracy remains 88.21%.",
        "",
        "## I-4G Batch Summary",
        "",
        f"- Backend: {i4g_summary.get('backend_used')}",
        f"- API attempted: {i4g_summary.get('api_attempted_count')}",
        f"- API errors: {i4g_summary.get('api_error_count')}",
        f"- Parse success: {i4g_summary.get('parse_success_count')}",
        f"- Schema validation success: {i4g_summary.get('schema_validation_success_count')}",
        f"- Failed cases: {i4g_summary.get('failed_count')}",
        f"- Accepted for dashboard prediction mode: {i4g_summary.get('accepted_for_dashboard_prediction_mode')}",
        "",
        "## I-5C Dashboard Statistics Summary",
        "",
        f"- Total prediction rows: {len(rows)}",
        f"- Sentiment distribution: {sentiment_counts}",
        f"- Urgency distribution: {urgency_counts}",
        "",
        "## Dashboard Mode Update Summary",
        "",
        (
            "The Streamlit Dashboard page now supports Synthetic Reference Statistics, DeepSeek Prediction Statistics, "
            "and Formal Reviewed Golden Evaluation modes. Missing DeepSeek dashboard files are handled with warnings so "
            "the synthetic reference mode remains usable before the 400-case API run is completed."
        ),
        "",
        "## Important Caveat",
        "",
        (
            "The 400-row prediction dashboard is not formal accuracy. Formal accuracy remains the I-4E.2 80-case reviewed "
            "golden test set result: 88.21%."
        ),
        "",
        "## Product Category Normalization Caveat",
        "",
        (
            "I-4E.4 showed that post-normalized interpretation improved product_category from 50.00% to 77.50%, but this "
            "stage does not patch active chain normalization."
        ),
        "",
        "## Suggested Screenshots",
        "",
        "- Dashboard mode selector.",
        "- Synthetic Reference Statistics overview.",
        "- DeepSeek Prediction Statistics overview.",
        "- DeepSeek product negative sentiment ranking.",
        "- DeepSeek complaint reason and source attribution distributions.",
        "- Formal Reviewed Golden Evaluation summary.",
    ]
    COMBINED_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    i4g_summary = require_accepted_i4g()
    rows = read_csv(PREDICTION_PATH)
    if len(rows) != 400:
        raise ValueError(f"I-5C requires 400 DeepSeek prediction rows; found {len(rows)}.")
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    store_rows = store_ranking(rows)
    product_rows = product_ranking(rows)
    reason_rows = distribution(rows, "complaint_reason", "complaint_reason")
    source_rows = distribution(rows, "source_attribution", "source_attribution")
    urgency_rows = distribution(rows, "urgency", "urgency")
    sentiment_rows = distribution(rows, "sentiment", "sentiment")
    matrix_rows = store_product_matrix(rows)
    demo_rows = select_demo_cases(rows)

    write_csv(STORE_RANKING_PATH, store_rows, ["store_location", "total_emails", "complaint_count", "negative_count", "high_urgency_count", "complaint_rate", "negative_rate"])
    write_csv(PRODUCT_RANKING_PATH, product_rows, ["product_category", "total_emails", "negative_count", "complaint_count", "high_urgency_count", "negative_rate", "complaint_rate"])
    write_csv(COMPLAINT_REASON_PATH, reason_rows, ["complaint_reason", "count", "percentage"])
    write_csv(SOURCE_ATTRIBUTION_PATH, source_rows, ["source_attribution", "count", "percentage"])
    write_csv(URGENCY_PATH, urgency_rows, ["urgency", "count", "percentage"])
    write_csv(SENTIMENT_PATH, sentiment_rows, ["sentiment", "count", "percentage"])
    write_csv(STORE_PRODUCT_MATRIX_PATH, matrix_rows, ["store_location", "product_category", "email_count", "complaint_count", "negative_count"])
    write_csv(DEMO_CASES_PATH, demo_rows, ["email_id", "subject", "email_body_excerpt", "sentiment", "urgency", "store_location", "product_category", "complaint_reason", "source_attribution", "summary", "suggested_reply"])

    dashboard_json = build_dashboard_json(rows, store_rows, product_rows, reason_rows, source_rows, urgency_rows, sentiment_rows)
    DASHBOARD_JSON_PATH.write_text(json.dumps(dashboard_json, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(rows, dashboard_json, i4g_summary)
    write_profile()
    write_combined_report(rows, dashboard_json, i4g_summary)

    print("I-5C DeepSeek prediction dashboard statistics generated.")
    print(f"Rows: {len(rows)}")
    print(f"Dashboard JSON: {DASHBOARD_JSON_PATH}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
