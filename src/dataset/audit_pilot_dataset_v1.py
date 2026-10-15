from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_pilot_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "synthetic_dataset_profile_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "pilot_dataset_audit_report_v1.md"
REVIEW_SAMPLE_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_review_sample_v1.csv"

REQUIRED_DATASET_COLUMNS = [
    "email_id",
    "email_subject",
    "email_body",
    "store_location",
    "purchased_product",
    "product_category",
    "customer_sentiment",
    "is_complaint",
    "complaint_reason",
    "urgency",
    "source_attribution",
    "expected_summary",
    "expected_reply_intent",
    "created_by",
    "review_status",
    "notes",
]

REQUIRED_GOLDEN_COLUMNS = [
    "email_id",
    "sentiment_label",
    "product_category_label",
    "store_location_label",
    "complaint_reason_label",
    "urgency_label",
    "is_complaint_label",
    "source_attribution_label",
]

REVIEW_SAMPLE_COLUMNS = [
    "email_id",
    "email_subject",
    "email_body",
    "store_location",
    "purchased_product",
    "product_category",
    "customer_sentiment",
    "is_complaint",
    "complaint_reason",
    "urgency",
    "source_attribution",
    "expected_summary",
    "expected_reply_intent",
    "review_status",
    "human_review_notes",
]

HIGH_URGENCY_CUES = [
    "urgent",
    "refund",
    "safety",
    "health",
    "injury",
    "irritation",
    "not replied",
    "no response",
    "as soon as possible",
    "no one followed",
    "has not received any reply",
    "support has not replied",
]

PLACEHOLDER_PATTERNS = [
    re.compile(r"lorem ipsum", re.IGNORECASE),
    re.compile(r"\bxxx\b", re.IGNORECASE),
    re.compile(r"test text", re.IGNORECASE),
    re.compile(r"\[(name|store|product|email)\]", re.IGNORECASE),
]

PRIVATE_INFO_PATTERNS = [
    re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\border\s*#?\s*\d{5,}\b", re.IGNORECASE),
    re.compile(r"\b\d{5,}\b"),
    re.compile(r"\b\d+\s+(street|avenue|lane|road)\b", re.IGNORECASE),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_integrity(rows: list[dict[str, str]], golden_rows: list[dict[str, str]], profile: dict) -> dict[str, str]:
    require(DATASET_PATH.exists(), f"Missing dataset file: {DATASET_PATH}")
    require(GOLDEN_PATH.exists(), f"Missing golden label file: {GOLDEN_PATH}")
    require(PROFILE_PATH.exists(), f"Missing profile file: {PROFILE_PATH}")
    require(len(rows) == 50, f"Expected 50 dataset rows, found {len(rows)}.")
    require(len(golden_rows) == 50, f"Expected 50 golden rows, found {len(golden_rows)}.")

    missing_dataset_columns = [column for column in REQUIRED_DATASET_COLUMNS if column not in rows[0]]
    missing_golden_columns = [column for column in REQUIRED_GOLDEN_COLUMNS if column not in golden_rows[0]]
    require(not missing_dataset_columns, f"Missing dataset columns: {missing_dataset_columns}")
    require(not missing_golden_columns, f"Missing golden columns: {missing_golden_columns}")

    ids = [row["email_id"] for row in rows]
    golden_ids = [row["email_id"] for row in golden_rows]
    require(len(ids) == len(set(ids)), "Dataset email_id values are not unique.")
    require(set(ids) == set(golden_ids), "Dataset and golden label email_id values do not match.")

    require(all(row["email_subject"].strip() for row in rows), "Found empty email_subject.")
    require(all(row["email_body"].strip() for row in rows), "Found empty email_body.")
    bodies = [row["email_body"].strip().lower() for row in rows]
    require(len(bodies) == len(set(bodies)), "Found duplicate email_body values.")

    allowed = {
        "customer_sentiment": set(profile["allowed_sentiments"]),
        "urgency": set(profile["allowed_urgency_levels"]),
        "product_category": set(profile["allowed_product_categories"]),
        "complaint_reason": set(profile["allowed_complaint_reasons"]),
        "source_attribution": set(profile["allowed_source_attribution_labels"]),
        "is_complaint": {"true", "false"},
        "review_status": {"generated", "manually_reviewed", "revised", "rejected"},
    }

    for row in rows:
        for field, allowed_values in allowed.items():
            require(row[field] in allowed_values, f"{row['email_id']} has invalid {field}: {row[field]}")

    golden_allowed = {
        "sentiment_label": set(profile["allowed_sentiments"]),
        "urgency_label": set(profile["allowed_urgency_levels"]),
        "product_category_label": set(profile["allowed_product_categories"]),
        "complaint_reason_label": set(profile["allowed_complaint_reasons"]),
        "source_attribution_label": set(profile["allowed_source_attribution_labels"]),
        "is_complaint_label": {"true", "false"},
    }
    for row in golden_rows:
        for field, allowed_values in golden_allowed.items():
            require(row[field] in allowed_values, f"{row['email_id']} has invalid {field}: {row[field]}")

    return {
        "dataset_file_exists": "passed",
        "golden_label_file_exists": "passed",
        "row_count_is_50": "passed",
        "email_id_unique": "passed",
        "required_columns_exist": "passed",
        "no_empty_subject": "passed",
        "no_empty_body": "passed",
        "no_duplicate_body": "passed",
        "allowed_labels": "passed",
    }


def distribution(rows: list[dict[str, str]], field: str) -> Counter:
    return Counter(row[field] for row in rows)


def distribution_warnings(rows: list[dict[str, str]], profile: dict) -> list[dict[str, str]]:
    warnings = []
    key_fields = {
        "customer_sentiment": profile["allowed_sentiments"],
        "urgency": profile["allowed_urgency_levels"],
        "product_category": profile["allowed_product_categories"],
        "complaint_reason": profile["allowed_complaint_reasons"],
        "source_attribution": profile["allowed_source_attribution_labels"],
    }

    for field, allowed_values in key_fields.items():
        counts = distribution(rows, field)
        for value in allowed_values:
            if counts.get(value, 0) == 0:
                warnings.append({"scope": "distribution", "item": field, "reason": f"zero examples for `{value}`"})

    sentiment_counts = distribution(rows, "customer_sentiment")
    total = len(rows)
    if sentiment_counts.get("negative", 0) / total > 0.75:
        warnings.append({"scope": "distribution", "item": "customer_sentiment", "reason": "negative cases may be too dominant"})
    if sentiment_counts.get("positive", 0) / total < 0.1 or sentiment_counts.get("neutral", 0) / total < 0.1:
        warnings.append({"scope": "distribution", "item": "customer_sentiment", "reason": "positive or neutral cases may be underrepresented"})

    for field in ["product_category", "store_location"]:
        counts = distribution(rows, field)
        label, count = counts.most_common(1)[0]
        if count / total > 0.4:
            warnings.append({"scope": "distribution", "item": field, "reason": f"`{label}` dominates with {count} rows"})

    return warnings


def consistency_warnings(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    warnings = []
    source_expectations = {
        "delivery delay": {"delivery/logistics issue"},
        "customer service": {"customer service response issue"},
        "product quality": {"product issue"},
        "health or safety issue": {"product issue"},
        "refund request": {"refund/exchange process issue"},
        "none": {"none"},
        "wrong item": {"store service issue", "refund/exchange process issue"},
        "after-sales service": {"store service issue", "refund/exchange process issue"},
        "other": {"unclear"},
    }

    for row in rows:
        email_id = row["email_id"]
        reason = row["complaint_reason"]
        source = row["source_attribution"]
        body_lower = row["email_body"].lower()

        if row["customer_sentiment"] == "positive" and row["is_complaint"] != "false":
            warnings.append({"email_id": email_id, "reason": "positive sentiment should usually have is_complaint=false"})
        if row["customer_sentiment"] == "neutral" and reason not in {"none", "other"}:
            warnings.append({"email_id": email_id, "reason": "neutral sentiment should usually have complaint_reason none or other"})
        if reason == "none" and source != "none":
            warnings.append({"email_id": email_id, "reason": "complaint_reason none should usually have source_attribution none"})
        if row["is_complaint"] == "false" and reason != "none":
            warnings.append({"email_id": email_id, "reason": "non-complaint row should usually have complaint_reason none"})
        if source not in source_expectations.get(reason, {source}):
            warnings.append({"email_id": email_id, "reason": f"{reason} should usually map to {sorted(source_expectations.get(reason, []))}"})
        if row["urgency"] == "high" and not any(cue in body_lower for cue in HIGH_URGENCY_CUES):
            warnings.append({"email_id": email_id, "reason": "high urgency row may lack strong urgency cues in email_body"})

    return warnings


def text_quality_warnings(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    warnings = []
    seen_templates = Counter()
    for row in rows:
        email_id = row["email_id"]
        body = row["email_body"].strip()
        body_lower = body.lower()
        first_words = " ".join(body_lower.split()[:5])
        seen_templates[first_words] += 1

        if len(body.split()) < 12:
            warnings.append({"email_id": email_id, "reason": "email_body may be too short"})
        if row["store_location"].lower() not in body_lower:
            warnings.append({"email_id": email_id, "reason": "store_location is not mentioned in email_body"})
        if row["purchased_product"].lower() not in body_lower:
            warnings.append({"email_id": email_id, "reason": "purchased_product is not mentioned in email_body"})
        if any(pattern.search(body) for pattern in PRIVATE_INFO_PATTERNS):
            warnings.append({"email_id": email_id, "reason": "possible private information pattern found"})
        if any(pattern.search(body) for pattern in PLACEHOLDER_PATTERNS):
            warnings.append({"email_id": email_id, "reason": "placeholder text found"})

    for prefix, count in seen_templates.items():
        if count >= 10:
            warnings.append({"email_id": "dataset", "reason": f"overly repetitive opening template: `{prefix}` appears {count} times"})

    return warnings


def select_review_sample(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()

    def add_first(predicate) -> None:
        for row in rows:
            if row["email_id"] not in selected_ids and predicate(row):
                selected.append(row)
                selected_ids.add(row["email_id"])
                return

    for reason in [
        "product quality",
        "delivery delay",
        "customer service",
        "wrong item",
        "after-sales service",
        "health or safety issue",
        "refund request",
        "other",
    ]:
        add_first(lambda row, reason=reason: row["complaint_reason"] == reason)

    add_first(lambda row: row["customer_sentiment"] == "positive")
    add_first(lambda row: row["customer_sentiment"] == "neutral")

    for category in ["Electronics", "Home Appliances", "Clothing", "Furniture", "Beauty Products", "Sportswear"]:
        if len(selected) >= 15:
            break
        add_first(lambda row, category=category: row["product_category"] == category)

    sample = selected[:15]
    return [
        {
            "email_id": row["email_id"],
            "email_subject": row["email_subject"],
            "email_body": row["email_body"],
            "store_location": row["store_location"],
            "purchased_product": row["purchased_product"],
            "product_category": row["product_category"],
            "customer_sentiment": row["customer_sentiment"],
            "is_complaint": row["is_complaint"],
            "complaint_reason": row["complaint_reason"],
            "urgency": row["urgency"],
            "source_attribution": row["source_attribution"],
            "expected_summary": row["expected_summary"],
            "expected_reply_intent": row["expected_reply_intent"],
            "review_status": row["review_status"],
            "human_review_notes": "",
        }
        for row in sample
    ]


def add_distribution(lines: list[str], title: str, counts: Counter) -> None:
    lines.extend(["", f"### {title}", "", "| Label | Count |", "|---|---:|"])
    for label, count in sorted(counts.items()):
        lines.append(f"| {label} | {count} |")


def add_warning_table(lines: list[str], title: str, warnings: list[dict[str, str]], columns: list[str]) -> None:
    lines.extend(["", f"## {title}", ""])
    if not warnings:
        lines.append("No warnings found.")
        return
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "|".join("---" for _ in columns) + "|")
    for warning in warnings:
        lines.append("| " + " | ".join(warning.get(column, "") for column in columns) + " |")


def build_report(
    rows: list[dict[str, str]],
    integrity: dict[str, str],
    dist_warnings: list[dict[str, str]],
    consistency: list[dict[str, str]],
    text_quality: list[dict[str, str]],
    review_sample: list[dict[str, str]],
) -> str:
    lines = [
        "# Pilot Dataset Audit Report v1",
        "",
        "- Project stage: I-2C Pilot Dataset Review and Consistency Audit",
        f"- Pilot dataset path: `{DATASET_PATH}`",
        f"- Golden label path: `{GOLDEN_PATH}`",
        f"- Audit report path: `{REPORT_PATH}`",
        f"- Review sample path: `{REVIEW_SAMPLE_PATH}`",
        "",
        "## Dataset Integrity Summary",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for check, result in integrity.items():
        lines.append(f"| {check} | {result} |")

    lines.extend(["", "## Distribution Summary"])
    add_distribution(lines, "Sentiment Distribution", distribution(rows, "customer_sentiment"))
    add_distribution(lines, "Complaint Reason Distribution", distribution(rows, "complaint_reason"))
    add_distribution(lines, "Source Attribution Distribution", distribution(rows, "source_attribution"))
    add_distribution(lines, "Urgency Distribution", distribution(rows, "urgency"))
    add_distribution(lines, "Product Category Distribution", distribution(rows, "product_category"))
    add_distribution(lines, "Store Location Distribution", distribution(rows, "store_location"))
    add_distribution(lines, "Purchased Product Distribution", distribution(rows, "purchased_product"))

    add_warning_table(lines, "Distribution Warnings", dist_warnings, ["scope", "item", "reason"])
    add_warning_table(lines, "Consistency Warnings", consistency, ["email_id", "reason"])
    add_warning_table(lines, "Text Quality Warnings", text_quality, ["email_id", "reason"])

    covered_reasons = sorted({row["complaint_reason"] for row in review_sample})
    covered_categories = sorted({row["product_category"] for row in review_sample})
    covered_stores = sorted({row["store_location"] for row in review_sample})
    lines.extend(
        [
            "",
            "## Human Review Sample Summary",
            "",
            f"- Selected rows: {len(review_sample)}",
            f"- Covered complaint reasons: {', '.join(covered_reasons)}",
            f"- Covered product categories: {', '.join(covered_categories)}",
            f"- Covered store locations: {', '.join(covered_stores)}",
            "",
            "The review sample is intended for manual checking. It includes an empty `human_review_notes` column.",
            "",
            "## Interpretation",
            "",
            "The pilot dataset is suitable for schema validation and early evaluation preparation. "
            "It should be manually reviewed before being treated as a reliable golden test set.",
            "",
            "## Next Step Recommendation",
            "",
            "Manually review the selected sample, revise labels or templates if needed, then decide whether "
            "to expand to 300-500 synthetic emails or start the LangChain + LLM structured output analyzer.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    rows = read_csv(DATASET_PATH)
    golden_rows = read_csv(GOLDEN_PATH)
    profile = load_profile()

    integrity = validate_integrity(rows, golden_rows, profile)
    dist_warnings = distribution_warnings(rows, profile)
    consistency = consistency_warnings(rows)
    text_quality = text_quality_warnings(rows)
    review_sample = select_review_sample(rows)

    write_csv(REVIEW_SAMPLE_PATH, review_sample, REVIEW_SAMPLE_COLUMNS)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        build_report(rows, integrity, dist_warnings, consistency, text_quality, review_sample),
        encoding="utf-8",
    )

    print("Pilot dataset audit completed.")
    print(f"Rows audited: {len(rows)}")
    print(f"Audit report saved to: {REPORT_PATH}")
    print(f"Review sample saved to: {REVIEW_SAMPLE_PATH}")
    print(f"Distribution warnings: {len(dist_warnings)}")
    print(f"Consistency warnings: {len(consistency)}")
    print(f"Text quality warnings: {len(text_quality)}")
    print(f"Review sample size: {len(review_sample)}")


if __name__ == "__main__":
    main()
