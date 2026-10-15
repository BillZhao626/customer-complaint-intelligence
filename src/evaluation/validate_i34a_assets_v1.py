from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_ASSETS = [
    PROJECT_ROOT / "outputs" / "deepseek_manual_review_decision_summary_v1.md",
    PROJECT_ROOT / "docs" / "prompt_revision_draft_v1.md",
    PROJECT_ROOT / "docs" / "golden_label_candidate_patch_plan_v1.md",
    PROJECT_ROOT / "configs" / "prompt" / "deepseek_prompt_revision_profile_v1.json",
]

PROFILE_PATH = PROJECT_ROOT / "configs" / "prompt" / "deepseek_prompt_revision_profile_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "i34a_asset_validation_report_v1.md"

REQUIRED_PROFILE_KEYS = [
    "version",
    "stage",
    "active",
    "purpose",
    "based_on",
    "field_instruction_summary",
    "prompt_patch_status",
    "recommended_next_stage",
    "evaluation_after_patch",
    "safety_notes",
]


def load_profile() -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not PROFILE_PATH.exists():
        return None, [f"Missing JSON profile: {PROFILE_PATH}"]
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as file:
            profile = json.load(file)
    except Exception as exc:
        return None, [f"JSON profile could not be loaded: {type(exc).__name__}: {exc}"]
    if not isinstance(profile, dict):
        errors.append("JSON profile must be an object.")
        return None, errors
    return profile, errors


def validate_assets() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_ASSETS:
        if not path.exists():
            errors.append(f"Missing required asset: {path}")

    profile, profile_errors = load_profile()
    errors.extend(profile_errors)
    if profile is None:
        return errors

    for key in REQUIRED_PROFILE_KEYS:
        if key not in profile:
            errors.append(f"Missing required profile key: {key}")

    if profile.get("active") is not False:
        errors.append("Profile key active must be false for I-3.4A.")

    if profile.get("prompt_patch_status") != "draft_only_not_applied":
        errors.append("prompt_patch_status must be draft_only_not_applied.")

    if profile.get("stage") != "I-3.4A":
        errors.append("stage must be I-3.4A.")

    based_on = profile.get("based_on")
    if not isinstance(based_on, list) or not based_on:
        errors.append("based_on must be a non-empty list.")

    field_summary = profile.get("field_instruction_summary")
    if not isinstance(field_summary, dict) or not field_summary:
        errors.append("field_instruction_summary must be a non-empty object.")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-3.4A Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        f"- Profile path: `{PROFILE_PATH}`",
        "",
        "## Required Assets",
        "",
    ]

    for path in REQUIRED_ASSETS:
        exists = "yes" if path.exists() else "no"
        lines.append(f"- `{path}` exists: {exists}")

    lines.extend(["", "## Checks", ""])
    lines.append("- Required markdown and JSON assets exist")
    lines.append("- JSON profile is valid JSON")
    lines.append("- Required profile keys exist")
    lines.append("- `active` is false")
    lines.append("- `prompt_patch_status` is `draft_only_not_applied`")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-3.4A assets are present and remain draft-only.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-3.4A asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-3.4A asset validation passed.")
    print(f"Validation report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
