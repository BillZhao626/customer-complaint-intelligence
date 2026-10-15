from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_i35_prompt_patch_v1.csv"
EVAL_REPORT_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_eval_report_i35_prompt_patch_v1.md"
COMPARISON_REPORT_PATH = PROJECT_ROOT / "outputs" / "deepseek_i35_prompt_patch_comparison_report_v1.md"
COMPARISON_JSON_PATH = PROJECT_ROOT / "outputs" / "deepseek_i35_prompt_patch_comparison_summary_v1.json"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i35_output_validation_report_v1.md"

REQUIRED_REPORT_PHRASES = [
    "I-3.1.1",
    "I-3.5",
    "P007",
    "P015",
    "P028",
    "P046",
    "P050",
    "store_location",
    "source_attribution",
    "complaint_reason",
    "urgency",
    "sentiment",
]


def validate_outputs() -> list[str]:
    errors: list[str] = []

    for path in [PREDICTION_PATH, EVAL_REPORT_PATH, COMPARISON_REPORT_PATH, COMPARISON_JSON_PATH]:
        if not path.exists():
            errors.append(f"Missing required output: {path}")

    summary = None
    if COMPARISON_JSON_PATH.exists():
        try:
            summary = json.loads(COMPARISON_JSON_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Comparison JSON is invalid: {type(exc).__name__}: {exc}")

    if isinstance(summary, dict):
        if summary.get("stage") != "I-3.5":
            errors.append('Comparison JSON field "stage" must be "I-3.5".')
    elif summary is not None:
        errors.append("Comparison JSON must contain an object.")

    if COMPARISON_REPORT_PATH.exists():
        report_text = COMPARISON_REPORT_PATH.read_text(encoding="utf-8")
        lower_report_text = report_text.lower()
        for phrase in REQUIRED_REPORT_PHRASES:
            if phrase.lower() not in lower_report_text:
                errors.append(f"Comparison report missing required phrase: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-3.5 Output Validation Report v1",
        "",
        f"- Validation status: {status}",
        "",
        "## Required Outputs",
        "",
        f"- Prediction CSV: `{PREDICTION_PATH}`",
        f"- Evaluation report: `{EVAL_REPORT_PATH}`",
        f"- Comparison report: `{COMPARISON_REPORT_PATH}`",
        f"- Comparison JSON: `{COMPARISON_JSON_PATH}`",
        "",
        "## Required Report Phrases",
        "",
    ]
    for phrase in REQUIRED_REPORT_PHRASES:
        lines.append(f"- `{phrase}`")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-3.5 rerun and comparison outputs are present and structurally valid.")

    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_outputs()
    write_report(errors)
    if errors:
        print("FAIL: I-3.5 output validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-3.5 output validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
