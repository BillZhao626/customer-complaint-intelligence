from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_predictions_v1.csv"
EVAL_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_eval_report_v1.md"
ERROR_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_error_analysis_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json"
COMPARISON_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e2_vs_i4e1_smoke_comparison_v1.md"
COMPARISON_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e2_vs_i4e1_smoke_comparison_v1.json"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_output_validation_report_v1.md"

PRIOR_REQUIRED = [
    PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_summary_v1.json",
    PROJECT_ROOT / "outputs" / "i4d_reviewed_golden_test_set_summary_v1.json",
    PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv",
]

REQUIRED_PATHS = [
    PREDICTION_PATH,
    EVAL_REPORT_PATH,
    ERROR_REPORT_PATH,
    SUMMARY_JSON_PATH,
    COMPARISON_REPORT_PATH,
    COMPARISON_JSON_PATH,
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


def validate_outputs() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required output: {path}")
    for path in PRIOR_REQUIRED:
        if not path.exists():
            errors.append(f"Missing prior output/source expected to remain available: {path}")

    summary: dict[str, Any] | None = None
    if SUMMARY_JSON_PATH.exists():
        summary, error = load_json(SUMMARY_JSON_PATH)
        if error:
            errors.append(f"Invalid I-4E.2 summary JSON: {error}")
        elif summary:
            if summary.get("stage") != "I-4E.2":
                errors.append('Summary JSON stage must be "I-4E.2".')
            if summary.get("total_cases") != 80:
                errors.append(f"total_cases must be 80, found {summary.get('total_cases')}.")
            if summary.get("backend_used") != "deepseek_api":
                errors.append("Formal I-4E.2 validation requires backend_used == deepseek_api.")
            if summary.get("api_attempted_count") != 80:
                errors.append(f"api_attempted_count must be 80, found {summary.get('api_attempted_count')}.")
            if summary.get("api_error_count") != 0:
                errors.append(f"api_error_count must be 0, found {summary.get('api_error_count')}.")
            if summary.get("parse_success_count") != 80:
                errors.append(f"parse_success_count must be 80, found {summary.get('parse_success_count')}.")
            if summary.get("schema_validation_success_count") != 80:
                errors.append(
                    f"schema_validation_success_count must be 80, found {summary.get('schema_validation_success_count')}."
                )
            if summary.get("total_field_count") != 560:
                errors.append(f"total_field_count must be 560, found {summary.get('total_field_count')}.")

    if PREDICTION_PATH.exists() and row_count(PREDICTION_PATH) != 80:
        errors.append(f"Prediction row count must be 80, found {row_count(PREDICTION_PATH)}.")

    if COMPARISON_JSON_PATH.exists():
        comparison, error = load_json(COMPARISON_JSON_PATH)
        if error:
            errors.append(f"Invalid comparison JSON: {error}")
        elif comparison and comparison.get("stage") != "I-4E.2_vs_I-4E.1":
            errors.append('Comparison JSON stage must be "I-4E.2_vs_I-4E.1".')

    for path in PRIOR_REQUIRED:
        if path.suffix == ".json" and path.exists():
            data, error = load_json(path)
            if error:
                errors.append(f"Prior JSON output is no longer valid: {path}: {error}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4E.2 Reviewed 80-case Output Validation Report v1",
        "",
        f"- Validation status: {status}",
        "",
        "## Required Outputs",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    lines.extend(["", "## Prior Output Preservation Checks", ""])
    for path in PRIOR_REQUIRED:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4E.2 formal DeepSeek reviewed 80-case outputs are present and structurally valid.")
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_outputs()
    write_report(errors)
    if errors:
        print("FAIL: I-4E.2 reviewed 80-case output validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4E.2 reviewed 80-case output validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
