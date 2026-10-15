from __future__ import annotations

import csv
import hashlib
import json
import py_compile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RULES_PATH = PROJECT_ROOT / "configs" / "evaluation" / "product_category_normalization_rules_v1.json"
ANALYZER_PATH = PROJECT_ROOT / "src" / "evaluation" / "analyze_i4e4_product_category_normalization_v1.py"
VALIDATOR_PATH = PROJECT_ROOT / "src" / "evaluation" / "validate_i4e4_assets_v1.py"
PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_predictions_v1.csv"
REVIEWED_GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv"
I4E2_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json"
I4E3_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_interpretation_summary_v1.json"

DETAILS_PATH = PROJECT_ROOT / "outputs" / "i4e4_product_category_normalization_details_v1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e4_post_normalized_eval_summary_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e4_product_category_normalization_report_v1.md"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e4_asset_validation_report_v1.md"

REQUIRED_PATHS = [
    RULES_PATH,
    ANALYZER_PATH,
    DETAILS_PATH,
    SUMMARY_PATH,
    REPORT_PATH,
]

INPUT_PATHS = [
    PREDICTION_PATH,
    REVIEWED_GOLDEN_PATH,
    I4E2_SUMMARY_PATH,
    I4E3_SUMMARY_PATH,
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    for path in REQUIRED_PATHS + INPUT_PATHS:
        if not path.exists():
            errors.append(f"Missing required file: {path}")

    if ANALYZER_PATH.exists():
        try:
            py_compile.compile(str(ANALYZER_PATH), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"Analyzer script failed py_compile: {exc}")

    if VALIDATOR_PATH.exists():
        try:
            py_compile.compile(str(VALIDATOR_PATH), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"Validator script failed py_compile: {exc}")

    rules: dict[str, Any] | None = None
    if RULES_PATH.exists():
        rules, error = load_json(RULES_PATH)
        if error:
            errors.append(f"Invalid normalization rules JSON: {error}")
        elif rules and rules.get("stage") != "I-4E.4":
            errors.append('Normalization rules stage must be "I-4E.4".')

    summary: dict[str, Any] | None = None
    if SUMMARY_PATH.exists():
        summary, error = load_json(SUMMARY_PATH)
        if error:
            errors.append(f"Invalid I-4E.4 summary JSON: {error}")
        elif summary:
            if summary.get("stage") != "I-4E.4":
                errors.append('Summary JSON stage must be "I-4E.4".')
            if summary.get("no_api_call") is not True:
                errors.append("Summary must include no_api_call == true.")
            if summary.get("model_evaluation_rerun") is not False:
                errors.append("Summary must include model_evaluation_rerun == false.")
            if "original_metrics" not in summary or "post_normalized_metrics" not in summary:
                errors.append("Summary must contain original_metrics and post_normalized_metrics.")
            else:
                original = summary["original_metrics"]
                normalized = summary["post_normalized_metrics"]
                original_pc_accuracy = original.get("field_accuracy", {}).get("product_category")
                if not isinstance(original_pc_accuracy, (int, float)) or abs(float(original_pc_accuracy) - 0.5) > 0.001:
                    errors.append(f"Original product_category accuracy must be close to 0.5000; found {original_pc_accuracy}.")
                post_pc_accuracy = normalized.get("field_accuracy", {}).get("product_category")
                if not isinstance(post_pc_accuracy, (int, float)):
                    errors.append("Post-normalized product_category accuracy is missing.")
                if "overall_field_accuracy" not in normalized:
                    errors.append("Post-normalized overall field accuracy is missing.")

            input_hashes = summary.get("input_sha256", {})
            expected_hashes = {
                "predictions": PREDICTION_PATH,
                "reviewed_golden_labels": REVIEWED_GOLDEN_PATH,
                "i4e2_summary": I4E2_SUMMARY_PATH,
                "i4e3_summary": I4E3_SUMMARY_PATH,
            }
            for key, path in expected_hashes.items():
                if path.exists() and input_hashes.get(key) != sha256(path):
                    errors.append(f"Input file hash mismatch for {key}; file may have changed since analysis output.")

    if DETAILS_PATH.exists() and row_count(DETAILS_PATH) != 80:
        errors.append(f"Product category detail CSV must contain 80 rows, found {row_count(DETAILS_PATH)}.")

    if REPORT_PATH.exists():
        text = REPORT_PATH.read_text(encoding="utf-8").lower()
        for phrase in [
            "no deepseek api call",
            "no model evaluation was rerun",
            "post-evaluation normalization",
            "product_category",
            "original i-4e.2 formal metrics remain",
        ]:
            if phrase not in text:
                errors.append(f"Report missing required phrase: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4E.4 Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        "- Stage: I-4E.4",
        "- Validation scope: offline product_category normalization analysis only.",
        "",
        "## Required Assets",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    lines.extend(["", "## Input Preservation Hashes", ""])
    for path in INPUT_PATHS:
        if path.exists():
            lines.append(f"- `{path}` sha256: `{sha256(path)}`")
        else:
            lines.append(f"- `{path}` sha256: missing")
    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4E.4 artifacts are present, JSON files are valid, and input hashes match the analysis summary.")
        lines.append("")
        lines.append("No API call is made by this validation script, and no model evaluation is rerun.")
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-4E.4 asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4E.4 asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
