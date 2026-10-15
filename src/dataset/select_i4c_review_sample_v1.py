from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FULL_DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv"
FULL_AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_full_auto_v1.csv"
SELECTED_EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_v1.csv"
SELECTED_AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_auto_v1.csv"
MANUAL_TEMPLATE_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_manual_template_v1.csv"
PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "review_sample_profile_v1.json"

TARGET_SAMPLE_SIZE = 80

DATASET_COLUMNS = [
    "email_id",
    "subject",
    "email_body",
    "customer_name",
    "store_location",
    "purchase_channel",
    "purchase_timeframe",
    "product_name",
    "product_category",
    "expected_sentiment",
    "expected_urgency",
    "expected_is_complaint",
    "expected_complaint_reason",
    "expected_source_attribution",
    "expected_summary_hint",
    "expected_reply_tone",
    "scenario_type",
    "edge_case_type",
    "generation_template_id",
]

AUTO_LABEL_COLUMNS = [
    "email_id",
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "summary_hint",
    "reply_tone",
    "scenario_type",
    "edge_case_type",
    "label_source",
]

MANUAL_TEMPLATE_COLUMNS = [
    "email_id",
    "subject",
    "email_body",
    "auto_sentiment",
    "reviewed_sentiment",
    "auto_urgency",
    "reviewed_urgency",
    "auto_is_complaint",
    "reviewed_is_complaint",
    "auto_store_location",
    "reviewed_store_location",
    "auto_product_category",
    "reviewed_product_category",
    "auto_complaint_reason",
    "reviewed_complaint_reason",
    "auto_source_attribution",
    "reviewed_source_attribution",
    "reviewer_notes",
    "review_status",
]

BALANCING_FIELDS = [
    "sentiment",
    "urgency",
    "product_category",
    "source_attribution",
    "complaint_reason",
    "store_location",
    "edge_case_type",
    "scenario_type",
]

TARGET_COUNTS = {
    "sentiment": {"negative": 52, "neutral": 14, "positive": 14},
    "urgency": {"high": 13, "medium": 43, "low": 24},
    "product_category": {
        "Electronics": 10,
        "Home Appliances": 10,
        "Furniture": 10,
        "Clothing": 10,
        "Beauty/Personal Care": 10,
        "Sports/Outdoor": 10,
        "Food/Beverage": 10,
        "Service/Other": 10,
    },
    "source_attribution": {
        "product issue": 13,
        "delivery/logistics issue": 9,
        "customer service response issue": 9,
        "store service issue": 6,
        "refund/exchange process issue": 13,
        "none": 28,
        "unclear": 2,
    },
    "complaint_reason": {
        "product quality": 10,
        "delivery delay": 9,
        "customer service": 9,
        "refund request": 7,
        "after-sales service": 7,
        "wrong item": 5,
        "health or safety issue": 3,
        "other": 2,
        "none": 28,
    },
    "store_location": {
        "Hangzhou West Lake Store": 8,
        "Hangzhou Binjiang Store": 8,
        "Shanghai Pudong Store": 8,
        "Shanghai Xujiahui Store": 8,
        "Nanjing Xinjiekou Store": 8,
        "Suzhou Industrial Park Store": 8,
        "Ningbo Tianyi Store": 8,
        "Wenzhou Lucheng Store": 8,
        "Beijing Chaoyang Store": 8,
        "Shenzhen Nanshan Store": 8,
    },
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def joined_records() -> list[dict[str, str]]:
    email_rows, _ = read_csv(FULL_DATASET_PATH)
    label_rows, _ = read_csv(FULL_AUTO_LABEL_PATH)
    labels_by_id = {row["email_id"]: row for row in label_rows}
    joined: list[dict[str, str]] = []
    for email in email_rows:
        email_id = email["email_id"]
        if email_id not in labels_by_id:
            raise ValueError(f"Missing auto label for {email_id}")
        combined = dict(email)
        for key, value in labels_by_id[email_id].items():
            combined[f"label_{key}" if key in combined else key] = value
        joined.append(combined)
    return sorted(joined, key=lambda row: row["email_id"])


def current_counts(selected: list[dict[str, str]]) -> dict[str, Counter[str]]:
    return {field: Counter(row[field] for row in selected) for field in BALANCING_FIELDS}


def score_candidate(row: dict[str, str], selected: list[dict[str, str]], selected_bodies: set[str]) -> tuple[float, str]:
    if row["email_body"] in selected_bodies:
        return (-10_000.0, row["email_id"])

    counts = current_counts(selected)
    score = 0.0
    for field, targets in TARGET_COUNTS.items():
        value = row[field]
        target = targets.get(value)
        if target is None:
            continue
        deficit = target - counts[field].get(value, 0)
        if deficit > 0:
            score += deficit
        else:
            score -= 1.5

    for field in ["edge_case_type", "scenario_type"]:
        value = row[field]
        if counts[field].get(value, 0) == 0:
            score += 12.0
        elif counts[field].get(value, 0) < 3:
            score += 2.0

    if row["source_attribution"] == "unclear" and counts["source_attribution"].get("unclear", 0) >= 2:
        score -= 20.0

    return (score, row["email_id"])


def select_best(candidates: list[dict[str, str]], selected: list[dict[str, str]], selected_ids: set[str], selected_bodies: set[str]) -> None:
    available = [row for row in candidates if row["email_id"] not in selected_ids]
    if not available:
        raise ValueError("No available candidates left to select.")
    best = max(available, key=lambda row: score_candidate(row, selected, selected_bodies))
    selected.append(best)
    selected_ids.add(best["email_id"])
    selected_bodies.add(best["email_body"])


def select_review_sample(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()
    selected_bodies: set[str] = set()

    # Guarantee every observed value in the main review dimensions appears at least once.
    guarantee_fields = [
        "sentiment",
        "urgency",
        "product_category",
        "source_attribution",
        "complaint_reason",
        "edge_case_type",
        "store_location",
    ]
    for field in guarantee_fields:
        for value in sorted({row[field] for row in rows}):
            matching = [row for row in rows if row[field] == value and row["email_id"] not in selected_ids]
            select_best(matching, selected, selected_ids, selected_bodies)

    while len(selected) < TARGET_SAMPLE_SIZE:
        select_best(rows, selected, selected_ids, selected_bodies)

    return sorted(selected, key=lambda row: row["email_id"])


def selected_email_rows(selected: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{column: row[column] for column in DATASET_COLUMNS} for row in selected]


def selected_label_rows(selected: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{column: row[column] for column in AUTO_LABEL_COLUMNS} for row in selected]


def manual_template_rows(selected: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in selected:
        rows.append(
            {
                "email_id": row["email_id"],
                "subject": row["subject"],
                "email_body": row["email_body"],
                "auto_sentiment": row["sentiment"],
                "reviewed_sentiment": "",
                "auto_urgency": row["urgency"],
                "reviewed_urgency": "",
                "auto_is_complaint": row["is_complaint"],
                "reviewed_is_complaint": "",
                "auto_store_location": row["store_location"],
                "reviewed_store_location": "",
                "auto_product_category": row["product_category"],
                "reviewed_product_category": "",
                "auto_complaint_reason": row["complaint_reason"],
                "reviewed_complaint_reason": "",
                "auto_source_attribution": row["source_attribution"],
                "reviewed_source_attribution": "",
                "reviewer_notes": "",
                "review_status": "needs_review",
            }
        )
    return rows


def write_profile(selected: list[dict[str, str]]) -> None:
    profile = {
        "version": "v1",
        "stage": "I-4C",
        "source_dataset_file": str(FULL_DATASET_PATH),
        "source_auto_label_file": str(FULL_AUTO_LABEL_PATH),
        "selected_email_file": str(SELECTED_EMAIL_PATH),
        "selected_auto_label_file": str(SELECTED_AUTO_LABEL_PATH),
        "manual_review_template_file": str(MANUAL_TEMPLATE_PATH),
        "review_batch_dir": str(PROJECT_ROOT / "outputs" / "review_batches_i4c"),
        "review_batch_index": str(PROJECT_ROOT / "outputs" / "review_batches_i4c" / "review_batch_index_v1.md"),
        "target_sample_size": TARGET_SAMPLE_SIZE,
        "actual_sample_size": len(selected),
        "selection_policy": [
            "deterministic selection by email_id and label deficits",
            "guarantee coverage for observed sentiment, urgency, product_category, source_attribution, complaint_reason, edge_case_type, and store_location values",
            "fill remaining slots using stratified deficit scoring",
            "avoid duplicate email bodies",
        ],
        "balancing_dimensions": BALANCING_FIELDS,
        "coverage_report": str(PROJECT_ROOT / "outputs" / "i4c_review_sample_coverage_report_v1.md"),
        "annotation_guidelines": str(PROJECT_ROOT / "docs" / "reviewed_golden_test_set_annotation_guidelines_v1.md"),
        "label_status": "selected_auto_labels_not_human_reviewed",
        "next_stage_recommendation": "manual_review_selected_sample_and_create_reviewed_golden_test_set",
    }
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    rows = joined_records()
    selected = select_review_sample(rows)
    if len(selected) != TARGET_SAMPLE_SIZE:
        raise ValueError(f"Expected {TARGET_SAMPLE_SIZE} selected rows, found {len(selected)}.")

    write_csv(SELECTED_EMAIL_PATH, selected_email_rows(selected), DATASET_COLUMNS)
    write_csv(SELECTED_AUTO_LABEL_PATH, selected_label_rows(selected), AUTO_LABEL_COLUMNS)
    write_csv(MANUAL_TEMPLATE_PATH, manual_template_rows(selected), MANUAL_TEMPLATE_COLUMNS)
    write_profile(selected)

    print("I-4C review sample selection completed.")
    print(f"Selected rows: {len(selected)}")
    print(f"Selected email file saved to: {SELECTED_EMAIL_PATH}")
    print(f"Selected auto label file saved to: {SELECTED_AUTO_LABEL_PATH}")
    print(f"Manual review template saved to: {MANUAL_TEMPLATE_PATH}")
    print(f"Review sample profile saved to: {PROFILE_PATH}")


if __name__ == "__main__":
    main()
