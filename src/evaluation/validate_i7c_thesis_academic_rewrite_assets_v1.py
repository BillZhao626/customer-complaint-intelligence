"""Validate I-7C thesis academic rewrite assets.

Standard-library-only validation. This script does not call APIs, rerun model
inference/evaluation, or modify protected project files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REWRITE_DRAFT = PROJECT_ROOT / "docs" / "dissertation" / "thesis_full_draft_academic_rewrite_v1.md"
CHANGE_LOG = PROJECT_ROOT / "docs" / "dissertation" / "thesis_academic_rewrite_change_log_v1.md"
RISK_CHECK = PROJECT_ROOT / "docs" / "dissertation" / "thesis_academic_rewrite_risk_check_v1.md"
SUPERVISOR_NOTES = PROJECT_ROOT / "docs" / "dissertation" / "thesis_supervisor_reading_version_notes_v1.md"
PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "thesis_academic_rewrite_profile_v1.json"
ORIGINAL_DRAFT = PROJECT_ROOT / "docs" / "dissertation" / "thesis_full_draft_v1.md"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i7c_thesis_academic_rewrite_validation_report_v1.md"

EXPECTED_FILES = [
    REWRITE_DRAFT,
    CHANGE_LOG,
    RISK_CHECK,
    SUPERVISOR_NOTES,
    PROFILE_FILE,
]

REQUIRED_REWRITE_STRINGS = [
    "中文摘要",
    "Abstract",
    "第1章",
    "第3章",
    "第5章",
    "第6章",
    "88.21%",
    "80-case reviewed golden test set",
    "400-row full pool",
    "400/400",
    "2515.43",
    "6.29",
    "I-4E.4",
    "[R1]",
    "[R4]",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> tuple[bool, dict | None, str]:
    try:
        data = json.loads(read_text(path))
    except Exception as exc:  # pragma: no cover
        return False, None, str(exc)
    if not isinstance(data, dict):
        return False, None, "JSON root is not an object"
    return True, data, ""


def main() -> int:
    failures: list[str] = []

    for path in EXPECTED_FILES:
        if not path.exists():
            failures.append(f"Missing expected file: {path.relative_to(PROJECT_ROOT)}")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-7C":
            failures.append("Profile stage is not I-7C.")
        if profile.get("no_api_call") is not True:
            failures.append("Profile no_api_call is not true.")
        if profile.get("no_model_rerun") is not True:
            failures.append("Profile no_model_rerun is not true.")

    if REWRITE_DRAFT.exists():
        text = read_text(REWRITE_DRAFT)
        for required in REQUIRED_REWRITE_STRINGS:
            if required not in text:
                failures.append(f"Academic rewrite draft missing required string: {required}")
        if not ("secondary interpretation layer" in text or "解释性分析" in text):
            failures.append("Academic rewrite draft missing secondary interpretation layer wording.")

    if RISK_CHECK.exists():
        text = read_text(RISK_CHECK)
        for required in ["formal accuracy", "batch stability", "secondary interpretation layer"]:
            if required not in text:
                failures.append(f"Risk check missing required string: {required}")

    if not ORIGINAL_DRAFT.exists():
        failures.append("Original thesis_full_draft_v1.md is missing.")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-7C Thesis Academic Rewrite Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Required I-7C files exist.",
        "- JSON profile is valid.",
        "- Academic rewrite draft contains required chapters, metrics, boundaries, and references.",
        "- Risk check contains formal accuracy, batch stability, and secondary interpretation layer wording.",
        "- Original thesis_full_draft_v1.md still exists.",
        "- Validation performs no API call and no model rerun.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-7C thesis academic rewrite validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-7C thesis academic rewrite validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-7C thesis academic rewrite validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
