from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SELECTED_EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_v1.csv"
SELECTED_AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_auto_v1.csv"
BATCH_DIR = PROJECT_ROOT / "outputs" / "review_batches_i4c"
BATCH_INDEX_PATH = BATCH_DIR / "review_batch_index_v1.md"

BATCH_SIZE = 10

ALLOWED_VALUES = {
    "reviewed_sentiment": ["negative", "neutral", "positive"],
    "reviewed_urgency": ["high", "medium", "low"],
    "reviewed_is_complaint": ["true", "false"],
    "reviewed_product_category": [
        "Electronics",
        "Home Appliances",
        "Furniture",
        "Clothing",
        "Beauty/Personal Care",
        "Sports/Outdoor",
        "Food/Beverage",
        "Service/Other",
    ],
    "reviewed_complaint_reason": [
        "product quality",
        "delivery delay",
        "customer service",
        "refund request",
        "after-sales service",
        "wrong item",
        "health or safety issue",
        "other",
        "none",
    ],
    "reviewed_source_attribution": [
        "product issue",
        "delivery/logistics issue",
        "customer service response issue",
        "store service issue",
        "refund/exchange process issue",
        "none",
        "unclear",
    ],
    "review_status": ["accepted", "corrected", "needs_discussion"],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def md(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").strip()


def write_batch(batch_number: int, rows: list[dict[str, str]]) -> Path:
    path = BATCH_DIR / f"review_batch_{batch_number:02d}.md"
    lines = [
        f"# I-4C Manual Review Batch {batch_number:02d}",
        "",
        "- Stage: I-4C manual review batch",
        f"- Batch number: {batch_number:02d}",
        f"- Row count: {len(rows)}",
        "",
        "## Instructions For ChatGPT / Human Reviewer",
        "",
        "Review each synthetic customer email and decide whether the auto labels should be accepted or corrected.",
        "Fill every reviewed_* field, write brief reviewer_notes, and set review_status to accepted, corrected, or needs_discussion.",
        "These selected labels are still auto labels until manual review is completed; do not treat them as final reviewed golden labels.",
        "",
        "## Allowed Label Values",
        "",
    ]
    for field, values in ALLOWED_VALUES.items():
        lines.append(f"- `{field}`: {', '.join(values)}")
    lines.extend(
        [
            "- `reviewed_store_location`: use the explicit full store name from the email when present.",
            "",
            "## Cases",
            "",
        ]
    )

    for row in rows:
        lines.extend(
            [
                f"### {row['email_id']}",
                "",
                f"- subject: {md(row['subject'])}",
                f"- email_body: {md(row['email_body'])}",
                "",
                "Auto labels:",
                "",
                f"- sentiment: {row['sentiment']}",
                f"- urgency: {row['urgency']}",
                f"- is_complaint: {row['is_complaint']}",
                f"- store_location: {row['store_location']}",
                f"- product_category: {row['product_category']}",
                f"- complaint_reason: {row['complaint_reason']}",
                f"- source_attribution: {row['source_attribution']}",
                "",
                "Review fields:",
                "",
                "- reviewed_sentiment:",
                "- reviewed_urgency:",
                "- reviewed_is_complaint:",
                "- reviewed_store_location:",
                "- reviewed_product_category:",
                "- reviewed_complaint_reason:",
                "- reviewed_source_attribution:",
                "- reviewer_notes:",
                "- review_status:",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    email_rows = read_csv(SELECTED_EMAIL_PATH)
    label_rows = read_csv(SELECTED_AUTO_LABEL_PATH)
    labels_by_id = {row["email_id"]: row for row in label_rows}
    combined: list[dict[str, str]] = []
    for email in email_rows:
        label = labels_by_id[email["email_id"]]
        combined.append({**email, **label})
    combined.sort(key=lambda row: row["email_id"])

    if len(combined) != 80:
        raise ValueError(f"Expected 80 selected rows, found {len(combined)}.")

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batch_rows = [combined[index : index + BATCH_SIZE] for index in range(0, len(combined), BATCH_SIZE)]
    batch_paths = []
    for index, rows in enumerate(batch_rows, start=1):
        batch_paths.append(write_batch(index, rows))

    index_lines = [
        "# I-4C Review Batch Index v1",
        "",
        "- Stage: I-4C manual review batches",
        "- Total batches: 8",
        "- Cases per batch: 10",
        "",
        "| Batch file | Row count | Included email_ids |",
        "|---|---:|---|",
    ]
    for path, rows in zip(batch_paths, batch_rows):
        ids = ", ".join(row["email_id"] for row in rows)
        index_lines.append(f"| {path.name} | {len(rows)} | {ids} |")
    BATCH_INDEX_PATH.write_text("\n".join(index_lines), encoding="utf-8")

    print("I-4C review batches exported.")
    print(f"Batch directory: {BATCH_DIR}")
    print(f"Batch index saved to: {BATCH_INDEX_PATH}")


if __name__ == "__main__":
    main()
