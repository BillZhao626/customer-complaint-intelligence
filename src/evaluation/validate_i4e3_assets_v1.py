from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MISMATCH_DETAIL_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_mismatch_details_v1.csv"
INTERPRETATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_evaluation_interpretation_report_v1.md"
SUPERVISOR_UPDATE_PATH = PROJECT_ROOT / "outputs" / "i4e3_supervisor_progress_update_draft_v1.md"
CHINESE_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e3_chinese_project_summary_v1.md"
INTERPRETATION_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_interpretation_summary_v1.json"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e3_asset_validation_report_v1.md"

REQUIRED_PATHS = [
    MISMATCH_DETAIL_PATH,
    INTERPRETATION_REPORT_PATH,
    SUPERVISOR_UPDATE_PATH,
    CHINESE_SUMMARY_PATH,
    INTERPRETATION_JSON_PATH,
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


def contains_all(text: str, terms: list[str]) -> list[str]:
    text_lower = text.lower()
    return [term for term in terms if term.lower() not in text_lower]


def validate_assets() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required I-4E.3 artifact: {path}")

    summary: dict[str, Any] | None = None
    if INTERPRETATION_JSON_PATH.exists():
        summary, error = load_json(INTERPRETATION_JSON_PATH)
        if error:
            errors.append(f"Invalid interpretation summary JSON: {error}")
        elif summary:
            if summary.get("stage") != "I-4E.3":
                errors.append('Summary JSON stage must be "I-4E.3".')
            if summary.get("total_cases") != 80:
                errors.append(f"total_cases must be 80, found {summary.get('total_cases')}.")
            if summary.get("total_fields") != 560:
                errors.append(f"total_fields must be 560, found {summary.get('total_fields')}.")
            if summary.get("total_mismatches") != 66:
                errors.append(f"total_mismatches must be 66, found {summary.get('total_mismatches')}.")
            accuracy = summary.get("overall_field_accuracy")
            if not isinstance(accuracy, (int, float)) or abs(float(accuracy) - 0.8821) > 0.0002:
                errors.append(f"overall_field_accuracy must be approximately 0.8821, found {accuracy}.")

    if MISMATCH_DETAIL_PATH.exists() and row_count(MISMATCH_DETAIL_PATH) != 66:
        errors.append(f"Mismatch detail CSV must contain 66 rows, found {row_count(MISMATCH_DETAIL_PATH)}.")

    if INTERPRETATION_REPORT_PATH.exists():
        report_text = INTERPRETATION_REPORT_PATH.read_text(encoding="utf-8")
        missing = contains_all(
            report_text,
            [
                "reviewed golden test set",
                "80 cases",
                "560 fields",
                "66 mismatches",
                "88.21%",
                "smoke",
                "400-row full pool is not used for formal accuracy metrics",
            ],
        )
        for term in missing:
            errors.append(f"Interpretation report must mention: {term}")

    if SUPERVISOR_UPDATE_PATH.exists():
        update_text = SUPERVISOR_UPDATE_PATH.read_text(encoding="utf-8")
        missing = contains_all(
            update_text,
            [
                "400-row synthetic pool",
                "80-case manually reviewed golden test set",
                "88.21%",
                "web interface",
            ],
        )
        for term in missing:
            errors.append(f"Supervisor update must mention: {term}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4E.3 Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        "- Stage: I-4E.3",
        "- Validation scope: offline interpretation artifacts only.",
        "",
        "## Required Artifacts",
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
        lines.append("Validation passed. I-4E.3 interpretation artifacts are present and structurally valid.")
        lines.append("")
        lines.append("No API call is made by this validation script, and no model evaluation is rerun.")
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-4E.3 asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4E.3 asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
