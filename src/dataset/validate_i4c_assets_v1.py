from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SELECTED_EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_v1.csv"
SELECTED_AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_auto_v1.csv"
MANUAL_TEMPLATE_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_manual_template_v1.csv"
COVERAGE_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4c_review_sample_coverage_report_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4c_review_sample_summary_v1.json"
GUIDELINES_PATH = PROJECT_ROOT / "docs" / "reviewed_golden_test_set_annotation_guidelines_v1.md"
PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "review_sample_profile_v1.json"
BATCH_DIR = PROJECT_ROOT / "outputs" / "review_batches_i4c"
BATCH_INDEX_PATH = BATCH_DIR / "review_batch_index_v1.md"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4c_asset_validation_report_v1.md"

REQUIRED_PATHS = [
    SELECTED_EMAIL_PATH,
    SELECTED_AUTO_LABEL_PATH,
    MANUAL_TEMPLATE_PATH,
    COVERAGE_REPORT_PATH,
    SUMMARY_JSON_PATH,
    GUIDELINES_PATH,
    PROFILE_PATH,
    BATCH_INDEX_PATH,
]

REVIEWED_COLUMNS = [
    "reviewed_sentiment",
    "reviewed_urgency",
    "reviewed_is_complaint",
    "reviewed_store_location",
    "reviewed_product_category",
    "reviewed_complaint_reason",
    "reviewed_source_attribution",
]

REQUIRED_COVERAGE = {
    "sentiment": {"negative", "neutral", "positive"},
    "urgency": {"high", "medium", "low"},
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
    "source_attribution": {
        "product issue",
        "delivery/logistics issue",
        "customer service response issue",
        "store service issue",
        "refund/exchange process issue",
        "none",
        "unclear",
    },
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
}

COVERAGE_PHRASES = [
    "not final golden test set",
    "manual review",
    "auto labels",
    "80",
    "reviewed golden test set",
]


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object."
    return data, None


def validate_assets() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required asset: {path}")

    for index in range(1, 9):
        path = BATCH_DIR / f"review_batch_{index:02d}.md"
        if not path.exists():
            errors.append(f"Missing review batch file: {path}")

    if SELECTED_EMAIL_PATH.exists() and SELECTED_AUTO_LABEL_PATH.exists() and MANUAL_TEMPLATE_PATH.exists():
        email_rows, _ = read_csv(SELECTED_EMAIL_PATH)
        label_rows, _ = read_csv(SELECTED_AUTO_LABEL_PATH)
        template_rows, template_columns = read_csv(MANUAL_TEMPLATE_PATH)

        if len(email_rows) != 80:
            errors.append(f"Selected email row count must be 80, found {len(email_rows)}.")
        if len(label_rows) != 80:
            errors.append(f"Selected auto label row count must be 80, found {len(label_rows)}.")
        if len(template_rows) != 80:
            errors.append(f"Manual template row count must be 80, found {len(template_rows)}.")

        email_ids = [row.get("email_id", "") for row in email_rows]
        label_ids = [row.get("email_id", "") for row in label_rows]
        template_ids = [row.get("email_id", "") for row in template_rows]
        if len(email_ids) != len(set(email_ids)):
            errors.append("Selected email_id values are not unique.")
        if set(email_ids) != set(label_ids) or set(email_ids) != set(template_ids):
            errors.append("Selected email_id values do not align across selected email, auto label, and manual template files.")

        missing_reviewed = [column for column in REVIEWED_COLUMNS if column not in template_columns]
        if missing_reviewed:
            errors.append(f"Manual review template missing reviewed_* columns: {missing_reviewed}")
        bad_statuses = sorted({row.get("review_status", "") for row in template_rows if row.get("review_status") != "needs_review"})
        if bad_statuses:
            errors.append(f"Manual template review_status values must default to needs_review. Found: {bad_statuses}")

        for field, required_values in REQUIRED_COVERAGE.items():
            observed = {row.get(field, "") for row in label_rows}
            missing = sorted(required_values - observed)
            if missing:
                errors.append(f"Review sample missing {field} coverage: {missing}")
        stores = {row.get("store_location", "") for row in label_rows}
        if len(stores) < 6:
            errors.append(f"Review sample must include multiple store locations; found {len(stores)}.")

    if SUMMARY_JSON_PATH.exists():
        summary, error = load_json(SUMMARY_JSON_PATH)
        if error:
            errors.append(f"Invalid review sample summary JSON: {error}")
        elif summary and summary.get("stage") != "I-4C":
            errors.append('Review sample summary stage must be "I-4C".')

    if PROFILE_PATH.exists():
        profile, error = load_json(PROFILE_PATH)
        if error:
            errors.append(f"Invalid review sample profile JSON: {error}")
        elif profile and profile.get("stage") != "I-4C":
            errors.append('Review sample profile stage must be "I-4C".')

    if COVERAGE_REPORT_PATH.exists():
        text = COVERAGE_REPORT_PATH.read_text(encoding="utf-8").lower()
        for phrase in COVERAGE_PHRASES:
            if phrase.lower() not in text:
                errors.append(f"Coverage report missing required phrase: {phrase}")

    if BATCH_INDEX_PATH.exists():
        text = BATCH_INDEX_PATH.read_text(encoding="utf-8")
        for phrase in ["review_batch_01.md", "review_batch_08.md"]:
            if phrase not in text:
                errors.append(f"Review batch index missing required phrase: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4C Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        "",
        "## Required Assets",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    for index in range(1, 9):
        path = BATCH_DIR / f"review_batch_{index:02d}.md"
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4C review sample, manual template, review batches, and coverage artifacts are structurally valid.")
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-4C asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4C asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
