"""Validate I-6D dissertation template assembly assets.

This script is documentation-only. It does not call DeepSeek, rerun model
inference, or modify datasets, labels, app code, chain code, prompts, taxonomy,
schema, API configuration, .env, or secret files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOC_FILES = [
    PROJECT_ROOT / "docs" / "dissertation" / "dissertation_template_assembly_plan_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "figure_table_insertion_plan_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "reference_requirement_plan_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "dissertation_gap_checklist_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "supervisor_update_after_i6c_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "defense_storyline_v1.md",
]

PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "dissertation_template_assembly_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i6d_dissertation_template_asset_validation_report_v1.md"

EXPECTED_FILES = DOC_FILES + [PROFILE_FILE]

REQUIRED_KEYWORDS = [
    "88.21%",
    "80-case reviewed golden test set",
    "400-row full pool",
    "400/400",
    "0 API errors",
    "I-5E",
]

BOUNDARY_PHRASES = [
    "not formal accuracy",
    "不是 formal accuracy",
    "不作为 formal accuracy",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> tuple[bool, dict | None, str]:
    try:
        data = json.loads(read_text(path))
    except Exception as exc:  # pragma: no cover - report path
        return False, None, str(exc)
    if not isinstance(data, dict):
        return False, None, "JSON root is not an object"
    return True, data, ""


def main() -> int:
    failures: list[str] = []

    for path in EXPECTED_FILES:
        if not path.exists():
            failures.append(f"Missing expected file: {path.relative_to(PROJECT_ROOT)}")

    existing_doc_texts = []
    for path in DOC_FILES:
        if path.exists():
            existing_doc_texts.append(read_text(path))

    combined_docs = "\n".join(existing_doc_texts)
    for keyword in REQUIRED_KEYWORDS:
        if keyword not in combined_docs:
            failures.append(f"Required keyword missing from I-6D docs: {keyword}")

    if not any(phrase in combined_docs for phrase in BOUNDARY_PHRASES):
        failures.append("I-6D docs do not clearly state that 400-row full pool is not formal accuracy.")

    risky_phrases = [
        "400-row full pool formal accuracy",
        "400-row full pool is formal accuracy",
        "400-row full pool 是 formal accuracy",
        "400-row full pool 作为 formal accuracy",
    ]
    for phrase in risky_phrases:
        if phrase in combined_docs:
            failures.append(f"Risky formal-accuracy phrase found: {phrase}")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-6D":
            failures.append("Profile stage is not I-6D.")
        if profile.get("source_stage") != "I-6C":
            failures.append("Profile source_stage is not I-6C.")
        if profile.get("key_metric_formal_accuracy") != 0.8821:
            failures.append("Profile formal accuracy is not 0.8821.")
        if profile.get("reviewed_cases") != 80:
            failures.append("Profile reviewed_cases is not 80.")
        if profile.get("full_pool_cases") != 400:
            failures.append("Profile full_pool_cases is not 400.")
        if profile.get("i4g_api_attempted") != 400:
            failures.append("Profile i4g_api_attempted is not 400.")
        if profile.get("i4g_api_errors") != 0:
            failures.append("Profile i4g_api_errors is not 0.")
        if profile.get("no_api_call") is not True:
            failures.append("Profile no_api_call is not true.")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-6D Dissertation Template Asset Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Expected I-6D docs/config files exist.",
        "- Profile JSON is valid and records stage I-6D and source stage I-6C.",
        "- Required keywords are present: 88.21%, 80-case reviewed golden test set, 400-row full pool, 400/400, 0 API errors, and I-5E.",
        "- Documents state that 400-row full pool is not formal accuracy.",
        "- No risky phrase treating 400-row full pool as formal accuracy was found.",
        "- Validation performs no API call and no model inference.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-6D dissertation template assembly assets validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-6D dissertation template assembly assets validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-6D dissertation template assembly assets validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
