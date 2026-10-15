from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SMOKE_EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_smoke20_v1.csv"
SMOKE_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_smoke20_v1.csv"
PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_predictions_v1.csv"
EVAL_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_eval_report_v1.md"
ERROR_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_error_analysis_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_summary_v1.json"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e1_smoke_output_validation_report_v1.md"

I4D_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4d_reviewed_golden_test_set_summary_v1.json"
I4D_REVIEWED_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv"

REQUIRED_PATHS = [
    SMOKE_EMAIL_PATH,
    SMOKE_LABEL_PATH,
    PREDICTION_PATH,
    EVAL_REPORT_PATH,
    ERROR_REPORT_PATH,
    SUMMARY_JSON_PATH,
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object."
    return data, None


def validate_outputs() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required output: {path}")

    summary: dict[str, Any] | None = None
    if SUMMARY_JSON_PATH.exists():
        summary, error = load_json(SUMMARY_JSON_PATH)
        if error:
            errors.append(f"Invalid summary JSON: {error}")
        elif summary:
            if summary.get("stage") != "I-4E.1":
                errors.append('Summary JSON stage must be "I-4E.1".')
            if summary.get("total_cases") != 20:
                errors.append(f"summary total_cases must be 20, found {summary.get('total_cases')}.")
            if summary.get("backend_used") == "deepseek_api" and summary.get("api_attempted_count") != 20:
                errors.append("api_attempted_count must be 20 when DeepSeek API backend is used.")
            if summary.get("parse_success_count") != 20:
                errors.append(f"parse_success_count must be 20, found {summary.get('parse_success_count')}.")
            if summary.get("schema_validation_success_count") != 20:
                errors.append(
                    f"schema_validation_success_count must be 20, found {summary.get('schema_validation_success_count')}."
                )

    if SMOKE_EMAIL_PATH.exists() and len(read_csv(SMOKE_EMAIL_PATH)) != 20:
        errors.append("Smoke email row count must be 20.")
    if SMOKE_LABEL_PATH.exists() and len(read_csv(SMOKE_LABEL_PATH)) != 20:
        errors.append("Smoke label row count must be 20.")
    if PREDICTION_PATH.exists() and len(read_csv(PREDICTION_PATH)) != 20:
        errors.append("Prediction row count must be 20.")

    if I4D_SUMMARY_PATH.exists():
        i4d_summary, error = load_json(I4D_SUMMARY_PATH)
        if error:
            errors.append(f"I-4D summary is no longer valid JSON: {error}")
        elif i4d_summary and i4d_summary.get("stage") != "I-4D":
            errors.append("I-4D summary stage changed unexpectedly.")
    else:
        errors.append(f"Missing prior I-4D summary: {I4D_SUMMARY_PATH}")
    if not I4D_REVIEWED_PATH.exists():
        errors.append(f"Missing prior I-4D reviewed labels: {I4D_REVIEWED_PATH}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4E.1 Smoke Output Validation Report v1",
        "",
        f"- Validation status: {status}",
        "",
        "## Required Outputs",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    lines.extend(
        [
            "",
            "## Prior Output Preservation Check",
            "",
            f"- I-4D summary exists: {'yes' if I4D_SUMMARY_PATH.exists() else 'no'}",
            f"- I-4D reviewed labels exist: {'yes' if I4D_REVIEWED_PATH.exists() else 'no'}",
            "",
            "## Result",
            "",
        ]
    )
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4E.1 smoke outputs are present and structurally valid.")
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_outputs()
    write_report(errors)
    if errors:
        print("FAIL: I-4E.1 smoke output validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4E.1 smoke output validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
