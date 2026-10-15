from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv"
AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_full_auto_v1.csv"
GENERATION_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "full_dataset_generation_summary_v1.json"
DATASET_PROFILE_PATH = PROJECT_ROOT / "outputs" / "dataset_profile_full_v1.md"
QUALITY_REPORT_PATH = PROJECT_ROOT / "outputs" / "full_dataset_quality_audit_v1.md"
QUALITY_JSON_PATH = PROJECT_ROOT / "outputs" / "full_dataset_quality_audit_v1.json"
DISTRIBUTION_REPORT_PATH = PROJECT_ROOT / "outputs" / "full_dataset_distribution_report_v1.md"
DISTRIBUTION_JSON_PATH = PROJECT_ROOT / "outputs" / "full_dataset_distribution_summary_v1.json"
RESULT_PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "full_dataset_generation_result_v1.json"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4b_asset_validation_report_v1.md"

REQUIRED_PATHS = [
    DATASET_PATH,
    AUTO_LABEL_PATH,
    GENERATION_SUMMARY_PATH,
    DATASET_PROFILE_PATH,
    QUALITY_REPORT_PATH,
    QUALITY_JSON_PATH,
    DISTRIBUTION_REPORT_PATH,
    DISTRIBUTION_JSON_PATH,
    RESULT_PROFILE_PATH,
]

PROFILE_REQUIRED_PHRASES = [
    "synthetic dataset pool",
    "not reviewed golden benchmark",
    "dashboard",
    "batch processing",
    "reviewed golden test set",
]


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object."
    return data, None


def row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def validate_assets() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required asset: {path}")

    if DATASET_PATH.exists():
        count = row_count(DATASET_PATH)
        if count != 400:
            errors.append(f"Dataset row count must be 400, found {count}.")
    if AUTO_LABEL_PATH.exists():
        count = row_count(AUTO_LABEL_PATH)
        if count != 400:
            errors.append(f"Auto label row count must be 400, found {count}.")

    generation_summary: dict[str, Any] | None = None
    if GENERATION_SUMMARY_PATH.exists():
        generation_summary, error = load_json(GENERATION_SUMMARY_PATH)
        if error:
            errors.append(f"Invalid generation summary JSON: {error}")
        elif generation_summary and generation_summary.get("stage") != "I-4B":
            errors.append('Generation summary stage must be "I-4B".')

    if QUALITY_JSON_PATH.exists():
        quality, error = load_json(QUALITY_JSON_PATH)
        if error:
            errors.append(f"Invalid quality audit JSON: {error}")
        elif quality and quality.get("pass") is not True:
            errors.append("Quality audit JSON must have pass == true.")

    if DISTRIBUTION_JSON_PATH.exists():
        distribution, error = load_json(DISTRIBUTION_JSON_PATH)
        if error:
            errors.append(f"Invalid distribution summary JSON: {error}")
        elif distribution and distribution.get("total_rows") != 400:
            errors.append("Distribution summary JSON must have total_rows == 400.")

    if RESULT_PROFILE_PATH.exists():
        result_profile, error = load_json(RESULT_PROFILE_PATH)
        if error:
            errors.append(f"Invalid generation result JSON: {error}")
        elif result_profile and result_profile.get("stage") != "I-4B":
            errors.append('Generation result JSON stage must be "I-4B".')

    for path in [DATASET_PROFILE_PATH, DISTRIBUTION_REPORT_PATH]:
        if path.exists():
            text = path.read_text(encoding="utf-8").lower()
            for phrase in PROFILE_REQUIRED_PHRASES:
                if phrase.lower() not in text:
                    errors.append(f"{path.name} missing required phrase: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4B Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        "",
        "## Required Assets",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4B dataset, auto labels, audit reports, and profiles are present and structurally valid.")
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-4B asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4B asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
