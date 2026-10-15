from __future__ import annotations

import json
import py_compile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ANALYZE_SCRIPT = PROJECT_ROOT / "src" / "evaluation" / "analyze_i5d_full_api_result_v1.py"
COMPARE_SCRIPT = PROJECT_ROOT / "src" / "evaluation" / "compare_i5d_synthetic_vs_deepseek_dashboard_v1.py"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i5d_asset_validation_report_v1.md"

EXPECTED_FILES = [
    PROJECT_ROOT / "outputs" / "i5d_full_api_result_summary_v1.json",
    PROJECT_ROOT / "outputs" / "i5d_full_api_result_interpretation_report_v1.md",
    PROJECT_ROOT / "outputs" / "i5d_synthetic_vs_deepseek_dashboard_comparison_v1.json",
    PROJECT_ROOT / "outputs" / "i5d_synthetic_vs_deepseek_dashboard_comparison_v1.md",
    PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_sentiment_v1.csv",
    PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_urgency_v1.csv",
    PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_complaint_reason_v1.csv",
    PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_source_attribution_v1.csv",
    PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_product_ranking_v1.csv",
    PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_store_ranking_v1.csv",
    PROJECT_ROOT / "docs" / "i5d_dashboard_screenshot_and_figure_plan_v1.md",
    PROJECT_ROOT / "outputs" / "i5d_supervisor_progress_update_draft_v1.md",
    PROJECT_ROOT / "outputs" / "i5d_full_api_and_dashboard_evidence_report_v1.md",
]

I4G_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json"
I5C_DASHBOARD_PATH = PROJECT_ROOT / "outputs" / "dashboard_i5c_deepseek" / "deepseek_dashboard_stats_v1.json"
APP_PATH = PROJECT_ROOT / "app.py"

BOUNDARY_PHRASES = [
    "400-row full pool",
    "DeepSeek Prediction Statistics",
    "Synthetic Reference Statistics",
    "Formal Reviewed Golden Evaluation",
    "80-case reviewed golden test set",
    "88.21%",
    "not formal accuracy",
    "product_category normalization",
]


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object."
    return data, None


def validate_i4g_summary(errors: list[str]) -> None:
    if not I4G_SUMMARY_PATH.exists():
        errors.append(f"Missing I-4G summary: {I4G_SUMMARY_PATH}")
        return
    summary, error = load_json(I4G_SUMMARY_PATH)
    if error:
        errors.append(f"Invalid I-4G summary JSON: {error}")
        return
    assert summary is not None
    required = {
        "stage": "I-4G",
        "total_rows": 400,
        "backend_used": "deepseek_api",
        "api_attempted_count": 400,
        "api_error_count": 0,
        "parse_success_count": 400,
        "schema_validation_success_count": 400,
        "accepted_for_dashboard_prediction_mode": True,
    }
    for key, expected in required.items():
        if summary.get(key) != expected:
            errors.append(f"I-4G summary {key} must be {expected!r}, found {summary.get(key)!r}.")


def validate_reports(errors: list[str]) -> None:
    report_paths = [
        PROJECT_ROOT / "outputs" / "i5d_full_api_result_interpretation_report_v1.md",
        PROJECT_ROOT / "outputs" / "i5d_synthetic_vs_deepseek_dashboard_comparison_v1.md",
        PROJECT_ROOT / "docs" / "i5d_dashboard_screenshot_and_figure_plan_v1.md",
        PROJECT_ROOT / "outputs" / "i5d_supervisor_progress_update_draft_v1.md",
        PROJECT_ROOT / "outputs" / "i5d_full_api_and_dashboard_evidence_report_v1.md",
    ]
    combined_text = ""
    for path in report_paths:
        if path.exists():
            combined_text += "\n" + path.read_text(encoding="utf-8")
    lower_text = combined_text.lower()
    for phrase in BOUNDARY_PHRASES:
        if phrase.lower() not in lower_text:
            errors.append(f"I-5D reports must mention required boundary phrase: {phrase}")


def validate_assets() -> list[str]:
    errors: list[str] = []

    for script in [ANALYZE_SCRIPT, COMPARE_SCRIPT]:
        if not script.exists():
            errors.append(f"Missing script: {script}")
        else:
            try:
                py_compile.compile(str(script), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(f"Script failed py_compile: {script}: {exc}")

    for path in EXPECTED_FILES:
        if not path.exists():
            errors.append(f"Missing expected I-5D file: {path}")

    for path in [
        PROJECT_ROOT / "outputs" / "i5d_full_api_result_summary_v1.json",
        PROJECT_ROOT / "outputs" / "i5d_synthetic_vs_deepseek_dashboard_comparison_v1.json",
        I5C_DASHBOARD_PATH,
    ]:
        if path.exists():
            data, error = load_json(path)
            if error:
                errors.append(f"Invalid JSON file: {path}: {error}")
            elif path.name.startswith("i5d_") and data and data.get("stage") != "I-5D":
                errors.append(f"{path} stage must be I-5D.")
        else:
            errors.append(f"Missing JSON file: {path}")

    validate_i4g_summary(errors)

    if I5C_DASHBOARD_PATH.exists():
        dashboard, error = load_json(I5C_DASHBOARD_PATH)
        if not error and dashboard:
            if dashboard.get("stage") != "I-5C":
                errors.append('I-5C dashboard stage must be "I-5C".')
            if dashboard.get("total_rows") != 400:
                errors.append("I-5C dashboard total_rows must be 400.")

    if APP_PATH.exists():
        app_text = APP_PATH.read_text(encoding="utf-8")
        for phrase in ["Synthetic Reference Statistics", "DeepSeek Prediction Statistics", "Formal Reviewed Golden Evaluation"]:
            if phrase not in app_text:
                errors.append(f"app.py missing dashboard mode string: {phrase}")

    validate_reports(errors)
    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-5D Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        "- Stage: I-5D",
        "- This stage is analysis-only: no API call, no model inference rerun, and no dataset/golden label overwrite.",
        "",
        "## Expected Files",
        "",
    ]
    for path in EXPECTED_FILES:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-5D interpretation, comparison, screenshot plan, supervisor draft, and evidence report are complete.")
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-5D asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-5D asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
