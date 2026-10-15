from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_predictions_v1.csv"
RAW_PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_raw_predictions_v1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_report_v1.md"
FAILED_CASES_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_failed_cases_v1.csv"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_output_validation_report_v1.md"

REQUIRED_PATHS = [
    PREDICTION_PATH,
    RAW_PREDICTION_PATH,
    SUMMARY_PATH,
    REPORT_PATH,
    FAILED_CASES_PATH,
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
            errors.append(f"Missing required I-4G output: {path}")

    summary: dict[str, Any] | None = None
    if SUMMARY_PATH.exists():
        summary, error = load_json(SUMMARY_PATH)
        if error:
            errors.append(f"Invalid I-4G summary JSON: {error}")
        elif summary:
            expected = {
                "stage": "I-4G",
                "total_rows": 400,
                "backend_used": "deepseek_api",
                "api_attempted_count": 400,
                "api_error_count": 0,
                "parse_success_count": 400,
                "schema_validation_success_count": 400,
                "accepted_for_dashboard_prediction_mode": True,
            }
            for key, expected_value in expected.items():
                actual = summary.get(key)
                if actual != expected_value:
                    errors.append(f"Summary {key} must be {expected_value!r}, found {actual!r}.")
            if summary.get("backend_used") == "mock_fallback" or summary.get("api_attempted_count") == 0:
                errors.append("I-4G validation rejects mock_fallback or zero-API runs.")

    if PREDICTION_PATH.exists():
        count = row_count(PREDICTION_PATH)
        if count != 400:
            errors.append(f"Prediction row count must be 400, found {count}.")

    if RAW_PREDICTION_PATH.exists():
        count = row_count(RAW_PREDICTION_PATH)
        if count != 400:
            errors.append(f"Raw prediction row count must be 400, found {count}.")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4G Full Pool DeepSeek Output Validation Report v1",
        "",
        f"- Validation status: {status}",
        "- Stage: I-4G",
        "",
        "## Required Outputs",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    lines.extend(["", "## Acceptance Boundary", ""])
    lines.append("Accepted I-4G requires backend_used=deepseek_api, 400 API attempts, 0 API errors, 400 parse successes, and 400 schema validation successes.")
    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4G real DeepSeek full-pool batch output is accepted for dashboard prediction mode.")
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_outputs()
    write_report(errors)
    if errors:
        print("FAIL: I-4G full pool DeepSeek output validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4G full pool DeepSeek output validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
