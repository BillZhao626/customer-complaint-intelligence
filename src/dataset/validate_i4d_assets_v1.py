from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_auto_v1.csv"
REVIEWED_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv"
AUDIT_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4d_manual_review_audit_report_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4d_reviewed_golden_test_set_summary_v1.json"
PROFILE_PATH = PROJECT_ROOT / "configs" / "evaluation" / "reviewed_golden_test_set_profile_v1.json"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4d_asset_validation_report_v1.md"

REQUIRED_COLUMNS = [
    "email_id",
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "review_status",
    "reviewer_notes",
    "review_source",
]

CORRECTIONS = {
    "F031": ("high", "medium"),
    "F041": ("high", "medium"),
    "F081": ("high", "medium"),
    "F086": ("high", "medium"),
    "F201": ("high", "medium"),
    "F206": ("high", "medium"),
    "F391": ("medium", "low"),
    "F396": ("medium", "low"),
    "F399": ("medium", "low"),
    "F400": ("medium", "low"),
}

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]

AUDIT_PHRASES = [
    "80",
    "accepted: 70",
    "corrected: 10",
    "needs_discussion: 0",
    "reviewed golden test set",
    "no api call",
    "no model evaluation",
    "high urgency threshold",
]


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
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

    for path in [REVIEWED_LABEL_PATH, AUDIT_REPORT_PATH, SUMMARY_JSON_PATH, PROFILE_PATH]:
        if not path.exists():
            errors.append(f"Missing required asset: {path}")

    if REVIEWED_LABEL_PATH.exists() and AUTO_LABEL_PATH.exists():
        auto_rows, _ = read_csv(AUTO_LABEL_PATH)
        reviewed_rows, reviewed_columns = read_csv(REVIEWED_LABEL_PATH)
        auto_by_id = {row["email_id"]: row for row in auto_rows}
        reviewed_by_id = {row["email_id"]: row for row in reviewed_rows}

        if len(reviewed_rows) != 80:
            errors.append(f"Reviewed row count must be 80, found {len(reviewed_rows)}.")
        if len(auto_rows) != 80:
            errors.append(f"Source auto label row count must be 80, found {len(auto_rows)}.")
        if set(auto_by_id) != set(reviewed_by_id):
            errors.append("email_id values do not match between source auto labels and reviewed labels.")

        missing_columns = [column for column in REQUIRED_COLUMNS if column not in reviewed_columns]
        if missing_columns:
            errors.append(f"Reviewed CSV missing required columns: {missing_columns}")

        status_counts = Counter(row.get("review_status", "") for row in reviewed_rows)
        expected_status_counts = {"accepted": 70, "corrected": 10, "needs_discussion": 0, "needs_review": 0}
        for status, expected_count in expected_status_counts.items():
            if status_counts.get(status, 0) != expected_count:
                errors.append(f"review_status count for {status} must be {expected_count}, found {status_counts.get(status, 0)}.")

        for email_id, (original, corrected) in CORRECTIONS.items():
            auto_row = auto_by_id.get(email_id)
            reviewed_row = reviewed_by_id.get(email_id)
            if not auto_row or not reviewed_row:
                errors.append(f"Correction case missing from auto or reviewed labels: {email_id}")
                continue
            if auto_row.get("urgency") != original or reviewed_row.get("urgency") != corrected:
                errors.append(
                    f"{email_id} urgency correction not applied exactly: expected {original} -> {corrected}, "
                    f"found {auto_row.get('urgency')} -> {reviewed_row.get('urgency')}"
                )
            if reviewed_row.get("review_status") != "corrected":
                errors.append(f"{email_id} must have review_status=corrected.")

        for email_id, auto_row in auto_by_id.items():
            reviewed_row = reviewed_by_id.get(email_id)
            if not reviewed_row:
                continue
            for field in FIELDS:
                if field == "urgency" and email_id in CORRECTIONS:
                    continue
                if auto_row.get(field) != reviewed_row.get(field):
                    errors.append(f"Unexpected non-urgency field change for {email_id} {field}: {auto_row.get(field)} -> {reviewed_row.get(field)}")

    if SUMMARY_JSON_PATH.exists():
        summary, error = load_json(SUMMARY_JSON_PATH)
        if error:
            errors.append(f"Invalid summary JSON: {error}")
        elif summary and summary.get("stage") != "I-4D":
            errors.append('Summary JSON stage must be "I-4D".')

    if PROFILE_PATH.exists():
        profile, error = load_json(PROFILE_PATH)
        if error:
            errors.append(f"Invalid profile JSON: {error}")
        elif profile and profile.get("stage") != "I-4D":
            errors.append('Profile JSON stage must be "I-4D".')

    if AUDIT_REPORT_PATH.exists():
        audit_text = AUDIT_REPORT_PATH.read_text(encoding="utf-8").lower()
        for phrase in AUDIT_PHRASES:
            if phrase.lower() not in audit_text:
                errors.append(f"Audit report missing required phrase: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4D Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        "",
        "## Required Assets",
        "",
    ]
    for path in [REVIEWED_LABEL_PATH, AUDIT_REPORT_PATH, SUMMARY_JSON_PATH, PROFILE_PATH]:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4D reviewed golden test set artifacts are present and structurally valid.")
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-4D asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4D asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
