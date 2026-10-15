from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv"
AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_full_auto_v1.csv"
AUDIT_REPORT_PATH = PROJECT_ROOT / "outputs" / "full_dataset_quality_audit_v1.md"
AUDIT_JSON_PATH = PROJECT_ROOT / "outputs" / "full_dataset_quality_audit_v1.json"

REQUIRED_DATASET_COLUMNS = [
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

REQUIRED_LABEL_COLUMNS = [
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

ALLOWED = {
    "sentiment": {"negative", "positive", "neutral"},
    "urgency": {"high", "medium", "low"},
    "is_complaint": {"true", "false"},
    "complaint_reason": {
        "product quality",
        "delivery delay",
        "customer service",
        "refund request",
        "after-sales service",
        "wrong item",
        "health or safety issue",
        "other",
        "none",
    },
    "source_attribution": {
        "product issue",
        "delivery/logistics issue",
        "customer service response issue",
        "store service issue",
        "refund/exchange process issue",
        "none",
        "unclear",
    },
    "product_category": {
        "Electronics",
        "Home Appliances",
        "Furniture",
        "Clothing",
        "Beauty/Personal Care",
        "Sports/Outdoor",
        "Food/Beverage",
        "Service/Other",
    },
}

REQUIRED_EDGE_CASES = {
    "mixed praise plus complaint",
    "refund plus no response",
    "store staff issue vs customer support issue",
    "delivery update confusion",
    "safety/health issue",
    "neutral inquiry",
    "positive praise",
    "wrong item",
    "after-sales warranty/repair/exchange",
}

PRIVATE_PATTERNS = {
    "phone_number": re.compile(r"\b(?:\d{3}[-.\s]?\d{3}[-.\s]?\d{4}|1[3-9]\d{9})\b"),
    "full_street_address": re.compile(r"\b\d{1,5}\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,3}\s+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln)\b"),
    "order_number": re.compile(r"\b(?:ORD\d{6,}|order\s*#?\s*\d{6,}|#\d{9,})\b", re.IGNORECASE),
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def count_values(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row.get(field, "") for row in rows).items()))


def validate() -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    dataset_rows, dataset_columns = read_csv(DATASET_PATH)
    label_rows, label_columns = read_csv(AUTO_LABEL_PATH)

    if len(dataset_rows) != 400:
        errors.append(f"Dataset row count must be 400, found {len(dataset_rows)}.")
    if len(label_rows) != 400:
        errors.append(f"Auto label row count must be 400, found {len(label_rows)}.")

    missing_dataset_columns = [column for column in REQUIRED_DATASET_COLUMNS if column not in dataset_columns]
    missing_label_columns = [column for column in REQUIRED_LABEL_COLUMNS if column not in label_columns]
    if missing_dataset_columns:
        errors.append(f"Dataset missing required columns: {missing_dataset_columns}")
    if missing_label_columns:
        errors.append(f"Auto labels missing required columns: {missing_label_columns}")

    dataset_ids = [row.get("email_id", "") for row in dataset_rows]
    label_ids = [row.get("email_id", "") for row in label_rows]
    if len(dataset_ids) != len(set(dataset_ids)):
        errors.append("Dataset email_id values are not unique.")
    if len(label_ids) != len(set(label_ids)):
        errors.append("Auto label email_id values are not unique.")
    if set(dataset_ids) != set(label_ids):
        errors.append("Dataset and auto label email_id values are not aligned.")

    for row in dataset_rows:
        if not row.get("subject", "").strip():
            errors.append(f"{row.get('email_id', 'unknown')} has empty subject.")
        if not row.get("email_body", "").strip():
            errors.append(f"{row.get('email_id', 'unknown')} has empty email_body.")

    for row in label_rows:
        for field in ["sentiment", "urgency", "is_complaint", "complaint_reason", "source_attribution", "product_category"]:
            value = row.get(field, "").strip()
            if not value:
                errors.append(f"{row.get('email_id', 'unknown')} has empty required label field: {field}")
            elif value not in ALLOWED[field]:
                errors.append(f"{row.get('email_id', 'unknown')} has invalid {field}: {value}")

    bodies = [row.get("email_body", "").strip() for row in dataset_rows]
    duplicate_body_count = len(bodies) - len(set(bodies))
    if duplicate_body_count:
        errors.append(f"Duplicate email_body count must be 0, found {duplicate_body_count}.")

    privacy_hits: list[dict[str, str]] = []
    for row in dataset_rows:
        text = f"{row.get('subject', '')} {row.get('email_body', '')}"
        for name, pattern in PRIVATE_PATTERNS.items():
            if pattern.search(text):
                privacy_hits.append({"email_id": row.get("email_id", ""), "pattern": name})
    if privacy_hits:
        errors.append(f"Potential private information patterns found: {privacy_hits[:10]}")

    distribution_fields = ["sentiment", "urgency", "complaint_reason", "source_attribution", "product_category", "edge_case_type"]
    distributions = {field: count_values(label_rows, field) for field in distribution_fields}
    for field in ["sentiment", "urgency", "complaint_reason", "source_attribution", "product_category"]:
        missing_values = sorted(ALLOWED[field] - set(distributions[field]))
        if missing_values:
            errors.append(f"Missing coverage for {field}: {missing_values}")

    missing_edges = sorted(REQUIRED_EDGE_CASES - set(distributions["edge_case_type"]))
    if missing_edges:
        errors.append(f"Missing required edge case coverage: {missing_edges}")

    unclear_count = distributions["source_attribution"].get("unclear", 0)
    if unclear_count > 40:
        errors.append(f"unclear source_attribution is too dominant: {unclear_count} rows.")

    total = len(label_rows) or 1
    negative_share = distributions["sentiment"].get("negative", 0) / total
    positive_share = distributions["sentiment"].get("positive", 0) / total
    neutral_share = distributions["sentiment"].get("neutral", 0) / total
    high_share = distributions["urgency"].get("high", 0) / total
    medium_share = distributions["urgency"].get("medium", 0) / total
    low_share = distributions["urgency"].get("low", 0) / total

    if not 0.60 <= negative_share <= 0.70:
        errors.append(f"Negative sentiment share outside target range: {negative_share:.3f}")
    if not 0.15 <= positive_share <= 0.20:
        errors.append(f"Positive sentiment share outside target range: {positive_share:.3f}")
    if not 0.10 <= neutral_share <= 0.20:
        errors.append(f"Neutral sentiment share outside target range: {neutral_share:.3f}")
    if not 0.10 <= high_share <= 0.20:
        errors.append(f"High urgency share outside target range: {high_share:.3f}")
    if not 0.45 <= medium_share <= 0.60:
        errors.append(f"Medium urgency share outside target range: {medium_share:.3f}")
    if not 0.25 <= low_share <= 0.35:
        errors.append(f"Low urgency share outside target range: {low_share:.3f}")

    audit = {
        "stage": "I-4B",
        "pass": not errors,
        "dataset_file": str(DATASET_PATH),
        "auto_label_file": str(AUTO_LABEL_PATH),
        "dataset_row_count": len(dataset_rows),
        "auto_label_row_count": len(label_rows),
        "email_id_unique": len(dataset_ids) == len(set(dataset_ids)) and len(label_ids) == len(set(label_ids)),
        "email_id_aligned": set(dataset_ids) == set(label_ids),
        "duplicate_email_body_count": duplicate_body_count,
        "privacy_hits": privacy_hits,
        "distributions": distributions,
        "unclear_source_attribution_count": unclear_count,
        "label_status": "auto_generated_not_human_reviewed",
        "errors": errors,
    }
    return errors, audit


def write_report(audit: dict[str, Any]) -> None:
    status = "PASS" if audit["pass"] else "FAIL"
    lines = [
        "# Full Dataset Quality Audit v1",
        "",
        "- Stage: I-4B Full Synthetic Customer Email Dataset Pool Generation",
        f"- Audit status: {status}",
        f"- Dataset file: `{DATASET_PATH}`",
        f"- Auto label file: `{AUTO_LABEL_PATH}`",
        f"- Dataset rows: {audit['dataset_row_count']}",
        f"- Auto label rows: {audit['auto_label_row_count']}",
        "",
        "## Dataset Role",
        "",
        "This file audits the synthetic dataset pool. Auto labels are not human-reviewed golden labels.",
        "",
        "## Structural Checks",
        "",
        f"- email_id unique: {'yes' if audit['email_id_unique'] else 'no'}",
        f"- email_id aligned: {'yes' if audit['email_id_aligned'] else 'no'}",
        f"- duplicate email_body count: {audit['duplicate_email_body_count']}",
        f"- privacy pattern hits: {len(audit['privacy_hits'])}",
        "",
        "## Distribution Coverage",
        "",
    ]
    for field, counts in audit["distributions"].items():
        lines.extend([f"### {field}", "", "| Label | Count |", "|---|---:|"])
        for label, count in counts.items():
            lines.append(f"| {label} | {count} |")
        lines.append("")

    lines.extend(["## Result", ""])
    if audit["errors"]:
        lines.append("Validation failed:")
        lines.append("")
        for error in audit["errors"]:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. The full synthetic dataset pool satisfies I-4B structural, coverage, and privacy checks.")
    lines.append("")
    AUDIT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    AUDIT_JSON_PATH.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    errors, audit = validate()
    write_report(audit)
    if errors:
        print("FAIL: I-4B full dataset quality audit failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4B full dataset quality audit passed.")
    print(f"Quality audit report saved to: {AUDIT_REPORT_PATH}")
    print(f"Quality audit JSON saved to: {AUDIT_JSON_PATH}")


if __name__ == "__main__":
    main()
