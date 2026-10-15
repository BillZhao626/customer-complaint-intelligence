from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv"
AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_full_auto_v1.csv"
I4E3_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_interpretation_summary_v1.json"

DASHBOARD_DIR = PROJECT_ROOT / "outputs" / "dashboard_i4f"
STORE_RANKING_PATH = DASHBOARD_DIR / "store_complaint_ranking_v1.csv"
PRODUCT_RANKING_PATH = DASHBOARD_DIR / "product_negative_sentiment_ranking_v1.csv"
COMPLAINT_REASON_PATH = DASHBOARD_DIR / "complaint_reason_distribution_v1.csv"
SOURCE_ATTRIBUTION_PATH = DASHBOARD_DIR / "source_attribution_distribution_v1.csv"
URGENCY_PATH = DASHBOARD_DIR / "urgency_distribution_v1.csv"
SENTIMENT_PATH = DASHBOARD_DIR / "sentiment_distribution_v1.csv"
STORE_PRODUCT_MATRIX_PATH = DASHBOARD_DIR / "store_by_product_matrix_v1.csv"
DEMO_CASES_PATH = DASHBOARD_DIR / "negative_complaint_cases_for_demo_v1.csv"
DASHBOARD_JSON_PATH = DASHBOARD_DIR / "dashboard_stats_v1.json"
REPORT_PATH = DASHBOARD_DIR / "i4f_full_pool_dashboard_statistics_report_v1.md"
PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "dashboard_i4f_profile_v1.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        return {}
    return data


def is_true(value: str) -> bool:
    return str(value).strip().lower() == "true"


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


def join_rows(dataset_rows: list[dict[str, str]], label_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    dataset_by_id = {row["email_id"]: row for row in dataset_rows}
    label_by_id = {row["email_id"]: row for row in label_rows}
    if len(dataset_rows) != len(label_rows):
        raise ValueError(f"Dataset row count {len(dataset_rows)} does not match label row count {len(label_rows)}.")
    if set(dataset_by_id) != set(label_by_id):
        missing_dataset = sorted(set(label_by_id) - set(dataset_by_id))[:10]
        missing_labels = sorted(set(dataset_by_id) - set(label_by_id))[:10]
        raise ValueError(f"Email IDs do not align. Missing dataset: {missing_dataset}; missing labels: {missing_labels}")

    joined: list[dict[str, str]] = []
    for email_id in sorted(dataset_by_id):
        row = dict(dataset_by_id[email_id])
        row.update({f"label_{key}": value for key, value in label_by_id[email_id].items() if key != "email_id"})
        joined.append(row)
    return joined


def store_ranking(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["label_store_location"]].append(row)
    output: list[dict[str, Any]] = []
    for store, store_rows in grouped.items():
        total = len(store_rows)
        complaint_count = sum(is_true(row["label_is_complaint"]) for row in store_rows)
        negative_count = sum(row["label_sentiment"] == "negative" for row in store_rows)
        high_urgency_count = sum(row["label_urgency"] == "high" for row in store_rows)
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
        grouped[row["label_product_category"]].append(row)
    output: list[dict[str, Any]] = []
    for product_category, product_rows in grouped.items():
        total = len(product_rows)
        negative_count = sum(row["label_sentiment"] == "negative" for row in product_rows)
        complaint_count = sum(is_true(row["label_is_complaint"]) for row in product_rows)
        high_urgency_count = sum(row["label_urgency"] == "high" for row in product_rows)
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


def distribution(rows: list[dict[str, str]], field: str, label_name: str) -> list[dict[str, Any]]:
    counts = Counter(row[field] for row in rows)
    total = len(rows)
    output = [
        {label_name: label, "count": count, "percentage": percentage(count, total)}
        for label, count in sorted(counts.items())
    ]
    return sorted(output, key=lambda row: (-row["count"], str(row[label_name])))


def store_product_matrix(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["label_store_location"], row["label_product_category"])].append(row)
    output: list[dict[str, Any]] = []
    for (store, product), group_rows in grouped.items():
        output.append(
            {
                "store_location": store,
                "product_category": product,
                "email_count": len(group_rows),
                "complaint_count": sum(is_true(row["label_is_complaint"]) for row in group_rows),
                "negative_count": sum(row["label_sentiment"] == "negative" for row in group_rows),
            }
        )
    return sorted(output, key=lambda row: (row["store_location"], row["product_category"]))


def select_demo_cases(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if row["label_sentiment"] == "negative" and is_true(row["label_is_complaint"])
    ]
    selected: list[dict[str, str]] = []
    used_ids: set[str] = set()

    def add_best(key: str, value: str) -> None:
        for row in sorted(candidates, key=lambda item: (item["email_id"])):
            if row["email_id"] not in used_ids and row.get(key) == value:
                selected.append(row)
                used_ids.add(row["email_id"])
                return

    for urgency in ["high", "medium", "low"]:
        add_best("label_urgency", urgency)
    for reason in sorted({row["label_complaint_reason"] for row in candidates}):
        if len(selected) >= 20:
            break
        add_best("label_complaint_reason", reason)
    for source in sorted({row["label_source_attribution"] for row in candidates}):
        if len(selected) >= 20:
            break
        add_best("label_source_attribution", source)
    for product in sorted({row["label_product_category"] for row in candidates}):
        if len(selected) >= 20:
            break
        add_best("label_product_category", product)
    for row in sorted(candidates, key=lambda item: ({"high": 0, "medium": 1, "low": 2}.get(item["label_urgency"], 9), item["email_id"])):
        if len(selected) >= 20:
            break
        if row["email_id"] not in used_ids:
            selected.append(row)
            used_ids.add(row["email_id"])

    return [
        {
            "email_id": row["email_id"],
            "subject": row["subject"],
            "email_body": row["email_body"],
            "sentiment": row["label_sentiment"],
            "urgency": row["label_urgency"],
            "store_location": row["label_store_location"],
            "product_category": row["label_product_category"],
            "complaint_reason": row["label_complaint_reason"],
            "source_attribution": row["label_source_attribution"],
        }
        for row in selected[:20]
    ]


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def write_report(
    joined_rows: list[dict[str, str]],
    store_rows: list[dict[str, Any]],
    product_rows: list[dict[str, Any]],
    sentiment_rows: list[dict[str, Any]],
    urgency_rows: list[dict[str, Any]],
    reason_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    formal_accuracy: float,
) -> None:
    total = len(joined_rows)
    complaint_count = sum(is_true(row["label_is_complaint"]) for row in joined_rows)
    negative_count = sum(row["label_sentiment"] == "negative" for row in joined_rows)

    lines = [
        "# I-4F Full Pool Dashboard Statistics Report v1",
        "",
        "## Stage And Purpose",
        "",
        (
            "I-4F aggregates the existing 400-row full synthetic pool into dashboard statistics, "
            "batch-processing demonstration tables, and chart-ready data files."
        ),
        "",
        "## Input Dataset",
        "",
        f"- Dataset: `{DATASET_PATH}`",
        f"- Labels: `{AUTO_LABEL_PATH}`",
        "- Dataset size: 400-row full synthetic pool.",
        "- Label status: auto labels, not human-reviewed golden labels.",
        "",
        "## Evaluation Boundary",
        "",
        (
            "The 400-row full pool is used for dashboard statistics and batch statistics. It is not formal accuracy. "
            "Formal model accuracy remains tied to the I-4E.2 80-case reviewed golden test set result: 88.21%."
        ),
        "",
        "## Key Statistics",
        "",
        f"- Total emails: {total}",
        f"- Complaint count: {complaint_count}",
        f"- Negative sentiment count: {negative_count}",
        "",
        "### Sentiment Distribution",
        "",
    ]
    lines.extend(markdown_table(["Sentiment", "Count", "Percentage"], [[row["sentiment"], str(row["count"]), f"{row['percentage']:.2f}%"] for row in sentiment_rows]))
    lines.extend(["", "### Urgency Distribution", ""])
    lines.extend(markdown_table(["Urgency", "Count", "Percentage"], [[row["urgency"], str(row["count"]), f"{row['percentage']:.2f}%"] for row in urgency_rows]))
    lines.extend(["", "### Top Store Locations By Complaint Count", ""])
    lines.extend(
        markdown_table(
            ["Store location", "Complaints", "Negative", "High urgency", "Complaint rate"],
            [
                [
                    row["store_location"],
                    str(row["complaint_count"]),
                    str(row["negative_count"]),
                    str(row["high_urgency_count"]),
                    f"{row['complaint_rate']:.2%}",
                ]
                for row in store_rows[:5]
            ],
        )
    )
    lines.extend(["", "### Top Product Categories By Negative Sentiment", ""])
    lines.extend(
        markdown_table(
            ["Product category", "Negative", "Complaints", "High urgency", "Negative rate"],
            [
                [
                    row["product_category"],
                    str(row["negative_count"]),
                    str(row["complaint_count"]),
                    str(row["high_urgency_count"]),
                    f"{row['negative_rate']:.2%}",
                ]
                for row in product_rows[:5]
            ],
        )
    )
    lines.extend(["", "### Complaint Reason Distribution", ""])
    lines.extend(markdown_table(["Complaint reason", "Count", "Percentage"], [[row["complaint_reason"], str(row["count"]), f"{row['percentage']:.2f}%"] for row in reason_rows]))
    lines.extend(["", "### Source Attribution Distribution", ""])
    lines.extend(markdown_table(["Source attribution", "Count", "Percentage"], [[row["source_attribution"], str(row["count"]), f"{row['percentage']:.2f}%"] for row in source_rows]))
    lines.extend(
        [
            "",
            "## Dashboard Interpretation",
            "",
            (
                "These tables can support Streamlit views for product categories associated with negative sentiment, "
                "store locations with the most complaints, complaint reason distribution, urgency distribution, and "
                "source attribution distribution. They directly support the supervisor-facing requirement to show "
                "batch processing and dashboard capability."
            ),
            "",
            "## Product Category Caveat",
            "",
            (
                "Product_category normalization caveat: I-4E.3 found product_category normalization / taxonomy alignment "
                "as the main weak point in the formal reviewed evaluation. I-4F does not fix that issue and does not change "
                "the prompt, taxonomy, chain, parser, or mapping. A later optional I-4E.4 stage can handle product_category "
                "normalization / mapping."
            ),
            "",
            "## Recommended Next Stage",
            "",
            (
                "Proceed to I-5A Streamlit dashboard integration, or choose I-4E.4 product_category normalization first "
                "if the project owner wants to prioritize metric refinement before interface work."
            ),
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def build_dashboard_json(
    total_rows: int,
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
        "stage": "I-4F",
        "total_rows": total_rows,
        "label_status": "full_pool_auto_labels_for_dashboard_statistics_not_formal_accuracy",
        "store_complaint_ranking": store_rows,
        "product_negative_sentiment_ranking": product_rows,
        "complaint_reason_distribution": reason_rows,
        "source_attribution_distribution": source_rows,
        "urgency_distribution": urgency_rows,
        "sentiment_distribution": sentiment_rows,
        "top_insights": [
            f"Top store by complaint count: {top_store.get('store_location')} with {top_store.get('complaint_count')} complaints.",
            f"Top product category by negative sentiment count: {top_product.get('product_category')} with {top_product.get('negative_count')} negative cases.",
            f"Most common complaint reason label: {top_reason.get('complaint_reason')} with {top_reason.get('count')} cases.",
            f"Most common source attribution label: {top_source.get('source_attribution')} with {top_source.get('count')} cases.",
        ],
        "warning": "400-row full pool statistics are for dashboard demonstration and batch statistics, not formal model accuracy.",
    }


def write_profile(generated_tables: list[str], formal_accuracy: float) -> None:
    profile = {
        "version": "v1",
        "stage": "I-4F",
        "source_dataset_file": str(DATASET_PATH),
        "source_auto_label_file": str(AUTO_LABEL_PATH),
        "dashboard_output_dir": str(DASHBOARD_DIR),
        "generated_tables": generated_tables,
        "generated_json": str(DASHBOARD_JSON_PATH),
        "label_status": "auto_labels_for_dashboard_statistics",
        "formal_evaluation_reference": "I-4E.2 80-case reviewed golden test set",
        "formal_accuracy": round(formal_accuracy, 4),
        "caveats": [
            "full_pool_not_formal_accuracy_benchmark",
            "product_category_normalization_issue_identified_in_I4E3",
        ],
        "recommended_next_stage": "I-5A_Streamlit_dashboard_integration",
    }
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    dataset_rows = read_csv(DATASET_PATH)
    label_rows = read_csv(AUTO_LABEL_PATH)
    joined_rows = join_rows(dataset_rows, label_rows)
    formal_summary = read_json(I4E3_SUMMARY_PATH)
    formal_accuracy = float(formal_summary.get("overall_field_accuracy", 0.8821))

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    store_rows = store_ranking(joined_rows)
    product_rows = product_ranking(joined_rows)
    reason_rows = distribution(joined_rows, "label_complaint_reason", "complaint_reason")
    source_rows = distribution(joined_rows, "label_source_attribution", "source_attribution")
    urgency_rows = distribution(joined_rows, "label_urgency", "urgency")
    sentiment_rows = distribution(joined_rows, "label_sentiment", "sentiment")
    matrix_rows = store_product_matrix(joined_rows)
    demo_rows = select_demo_cases(joined_rows)

    write_csv(STORE_RANKING_PATH, store_rows, ["store_location", "total_emails", "complaint_count", "negative_count", "high_urgency_count", "complaint_rate", "negative_rate"])
    write_csv(PRODUCT_RANKING_PATH, product_rows, ["product_category", "total_emails", "negative_count", "complaint_count", "high_urgency_count", "negative_rate", "complaint_rate"])
    write_csv(COMPLAINT_REASON_PATH, reason_rows, ["complaint_reason", "count", "percentage"])
    write_csv(SOURCE_ATTRIBUTION_PATH, source_rows, ["source_attribution", "count", "percentage"])
    write_csv(URGENCY_PATH, urgency_rows, ["urgency", "count", "percentage"])
    write_csv(SENTIMENT_PATH, sentiment_rows, ["sentiment", "count", "percentage"])
    write_csv(STORE_PRODUCT_MATRIX_PATH, matrix_rows, ["store_location", "product_category", "email_count", "complaint_count", "negative_count"])
    write_csv(DEMO_CASES_PATH, demo_rows, ["email_id", "subject", "email_body", "sentiment", "urgency", "store_location", "product_category", "complaint_reason", "source_attribution"])

    dashboard_json = build_dashboard_json(
        len(joined_rows),
        store_rows,
        product_rows,
        reason_rows,
        source_rows,
        urgency_rows,
        sentiment_rows,
    )
    DASHBOARD_JSON_PATH.write_text(json.dumps(dashboard_json, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(joined_rows, store_rows, product_rows, sentiment_rows, urgency_rows, reason_rows, source_rows, formal_accuracy)
    write_profile(
        [
            str(STORE_RANKING_PATH),
            str(PRODUCT_RANKING_PATH),
            str(COMPLAINT_REASON_PATH),
            str(SOURCE_ATTRIBUTION_PATH),
            str(URGENCY_PATH),
            str(SENTIMENT_PATH),
            str(STORE_PRODUCT_MATRIX_PATH),
            str(DEMO_CASES_PATH),
        ],
        formal_accuracy,
    )

    print("I-4F full pool dashboard statistics generated.")
    print(f"Total rows: {len(joined_rows)}")
    print(f"Dashboard JSON: {DASHBOARD_JSON_PATH}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
