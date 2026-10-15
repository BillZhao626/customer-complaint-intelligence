from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REMAINING_CASES_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_cases_v1.csv"
REGRESSION_CASES_PATH = PROJECT_ROOT / "outputs" / "i351_regression_cases_v1.csv"
IMPROVED_CASES_PATH = PROJECT_ROOT / "outputs" / "i351_improved_cases_v1.csv"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_summary_v1.json"
ANALYSIS_REPORT_PATH = PROJECT_ROOT / "outputs" / "i351_remaining_mismatch_analysis_report_v1.md"
EXTERNAL_REVIEW_PATH = PROJECT_ROOT / "docs" / "external_dataset_reference_review_v1.md"
EXTERNAL_PROFILE_PATH = PROJECT_ROOT / "configs" / "evaluation" / "external_dataset_reference_profile_v1.json"
CREDIBILITY_PLAN_PATH = PROJECT_ROOT / "docs" / "evaluation_credibility_plan_v1.md"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i351_asset_validation_report_v1.md"

REQUIRED_PATHS = [
    REMAINING_CASES_PATH,
    REGRESSION_CASES_PATH,
    IMPROVED_CASES_PATH,
    SUMMARY_JSON_PATH,
    ANALYSIS_REPORT_PATH,
    EXTERNAL_REVIEW_PATH,
    EXTERNAL_PROFILE_PATH,
    CREDIBILITY_PLAN_PATH,
]

REPORT_PHRASES = [
    "41",
    "17",
    "P007",
    "P015",
    "P028",
    "P046",
    "P050",
    "source_attribution",
    "is_complaint",
    "golden_label_issue",
    "taxonomy_ambiguity",
]

EXTERNAL_REVIEW_PHRASES = [
    "Amazon",
    "CFPB",
    "Bitext",
    "internal golden labels",
    "not direct golden labels",
]


def load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object."
    return data, None


def validate_assets() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required asset: {path}")

    if SUMMARY_JSON_PATH.exists():
        summary, error = load_json(SUMMARY_JSON_PATH)
        if error:
            errors.append(f"Invalid summary JSON: {error}")
        elif summary and summary.get("stage") != "I-3.5.1":
            errors.append('Summary JSON stage must be "I-3.5.1".')

    if EXTERNAL_PROFILE_PATH.exists():
        profile, error = load_json(EXTERNAL_PROFILE_PATH)
        if error:
            errors.append(f"Invalid external dataset profile JSON: {error}")
        elif profile and profile.get("stage") != "I-3.5.1":
            errors.append('External dataset profile stage must be "I-3.5.1".')

    if ANALYSIS_REPORT_PATH.exists():
        report_text = ANALYSIS_REPORT_PATH.read_text(encoding="utf-8").lower()
        for phrase in REPORT_PHRASES:
            if phrase.lower() not in report_text:
                errors.append(f"Analysis report missing required phrase: {phrase}")

    if EXTERNAL_REVIEW_PATH.exists():
        external_text = EXTERNAL_REVIEW_PATH.read_text(encoding="utf-8").lower()
        for phrase in EXTERNAL_REVIEW_PHRASES:
            if phrase.lower() not in external_text:
                errors.append(f"External review missing required phrase: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-3.5.1 Asset Validation Report v1",
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
        lines.append("Validation passed. I-3.5.1 assets are present and structurally valid.")

    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-3.5.1 asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-3.5.1 asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
