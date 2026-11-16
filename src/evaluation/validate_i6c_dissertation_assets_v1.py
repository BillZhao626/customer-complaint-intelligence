"""Validate I-6C dissertation draft chapter package assets.

This script is standard-library only and performs documentation/package checks.
It does not call DeepSeek, rerun inference, or modify datasets/golden labels.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_FILES = [
    PROJECT_ROOT / "docs" / "dissertation" / "chapter_1_introduction_draft_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "chapter_2_related_work_draft_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "chapter_3_requirement_and_design_draft_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "chapter_4_system_implementation_draft_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "chapter_5_evaluation_and_result_analysis_draft_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "chapter_6_conclusion_and_future_work_draft_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "figure_and_table_plan_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "thesis_writing_todo_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "dissertation_chapter_package_index_v1.md",
    PROJECT_ROOT / "configs" / "dissertation" / "dissertation_chapter_package_profile_v1.json",
]

CHAPTER_5 = PROJECT_ROOT / "docs" / "dissertation" / "chapter_5_evaluation_and_result_analysis_draft_v1.md"
INDEX_FILE = PROJECT_ROOT / "docs" / "dissertation" / "dissertation_chapter_package_index_v1.md"
PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "dissertation_chapter_package_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i6c_dissertation_asset_validation_report_v1.md"

REQUIRED_CHAPTER_5_STRINGS = [
    "88.21%",
    "400",
    "2515.43",
    "6.29",
    "92.14%",
    "77.50%",
    "80 cases",
    "560",
    "494",
    "66",
    "0 API errors",
]

REQUIRED_INDEX_STRINGS = [
    "I-6C",
    "I-6AB",
    "I-5E UI screenshot evidence package",
    "80-case reviewed golden test set",
    "400-row full pool",
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

    if CHAPTER_5.exists():
        chapter_5_text = read_text(CHAPTER_5)
        for value in REQUIRED_CHAPTER_5_STRINGS:
            if value not in chapter_5_text:
                failures.append(f"Chapter 5 missing required metric string: {value}")
    else:
        failures.append("Chapter 5 file is missing, cannot check metric strings.")

    if INDEX_FILE.exists():
        index_text = read_text(INDEX_FILE)
        for value in REQUIRED_INDEX_STRINGS:
            if value not in index_text:
                failures.append(f"Package index missing required string: {value}")
    else:
        failures.append("Chapter package index file is missing.")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-6C":
            failures.append("Profile stage is not I-6C.")
        constraints = profile.get("stage_constraints", {})
        expected_true_flags = [
            "no_deepseek_api_call",
            "no_model_evaluation_rerun",
            "no_dataset_modification",
            "no_golden_label_modification",
            "no_app_or_chain_modification",
        ]
        for flag in expected_true_flags:
            if constraints.get(flag) is not True:
                failures.append(f"Profile constraint {flag} is not true.")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-6C Dissertation Asset Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Expected dissertation chapter/package files exist.",
        "- Chapter 5 contains required metric strings, including 88.21%, 400, 2515.43, 6.29, 92.14%, and 77.50%.",
        "- Chapter package index exists and describes I-6C, I-6AB, I-5E, the 80-case reviewed golden test set, and the 400-row full pool.",
        "- Dissertation profile JSON is valid and records stage I-6C.",
        "- This validation is documentation-only and performs no API call or model inference.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-6C dissertation chapter package validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-6C dissertation chapter package validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-6C dissertation chapter package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
