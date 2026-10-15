from __future__ import annotations

import csv
import json
import py_compile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

APP_PATH = PROJECT_ROOT / "app.py"
I4G_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json"
I4G_PREDICTIONS_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_predictions_v1.csv"
I4G_VALIDATION_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_output_validation_report_v1.md"
I5C_DASHBOARD_JSON_PATH = PROJECT_ROOT / "outputs" / "dashboard_i5c_deepseek" / "deepseek_dashboard_stats_v1.json"
I5C_VALIDATION_PATH = PROJECT_ROOT / "outputs" / "dashboard_i5c_deepseek" / "i5c_deepseek_dashboard_stats_validation_report_v1.md"
COMBINED_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4g_i5c_full_pool_deepseek_dashboard_update_report_v1.md"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4g_i5c_dashboard_modes_validation_report_v1.md"

APP_REQUIRED_REFERENCES = [
    "Synthetic Reference Statistics",
    "DeepSeek Prediction Statistics",
    "Formal Reviewed Golden Evaluation",
    "400-row full pool",
    "80-case reviewed golden test set",
    "88.21%",
    "product_category normalization",
    "deepseek_dashboard_stats_v1.json",
    "dashboard_stats_v1.json",
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

    if not APP_PATH.exists():
        errors.append(f"Missing app.py: {APP_PATH}")
    else:
        try:
            py_compile.compile(str(APP_PATH), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"app.py failed py_compile: {exc}")
        app_text = APP_PATH.read_text(encoding="utf-8")
        for reference in APP_REQUIRED_REFERENCES:
            if reference not in app_text:
                errors.append(f"app.py missing required dashboard mode reference: {reference}")

    for path in [I4G_SUMMARY_PATH, I4G_PREDICTIONS_PATH, I4G_VALIDATION_PATH, I5C_DASHBOARD_JSON_PATH, I5C_VALIDATION_PATH, COMBINED_REPORT_PATH]:
        if not path.exists():
            errors.append(f"Missing required I-4G/I-5C artifact: {path}")

    if I4G_SUMMARY_PATH.exists():
        summary, error = load_json(I4G_SUMMARY_PATH)
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
            for key, value in expected.items():
                if summary.get(key) != value:
                    errors.append(f"I-4G summary {key} must be {value!r}, found {summary.get(key)!r}.")

    if I4G_PREDICTIONS_PATH.exists() and row_count(I4G_PREDICTIONS_PATH) != 400:
        errors.append(f"I-4G prediction row count must be 400, found {row_count(I4G_PREDICTIONS_PATH)}.")

    if I5C_DASHBOARD_JSON_PATH.exists():
        dashboard, error = load_json(I5C_DASHBOARD_JSON_PATH)
        if error:
            errors.append(f"Invalid I-5C dashboard JSON: {error}")
        elif dashboard:
            if dashboard.get("stage") != "I-5C":
                errors.append('I-5C dashboard JSON stage must be "I-5C".')
            if dashboard.get("total_rows") != 400:
                errors.append(f"I-5C dashboard total_rows must be 400, found {dashboard.get('total_rows')}.")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4G / I-5C Dashboard Modes Validation Report v1",
        "",
        f"- Validation status: {status}",
        "",
        "## Checks",
        "",
        "- app.py compiles and contains all three dashboard mode labels.",
        "- I-4G outputs exist and are accepted real DeepSeek outputs.",
        "- I-5C DeepSeek dashboard outputs exist.",
        "- Combined report exists.",
        "",
        "## Result",
        "",
    ]
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. Streamlit dashboard multi-mode integration is present and backed by accepted I-4G/I-5C outputs.")
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-4G / I-5C dashboard modes validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4G / I-5C dashboard modes validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
