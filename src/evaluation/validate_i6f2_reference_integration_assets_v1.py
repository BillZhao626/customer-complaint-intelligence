"""Validate I-6F.2 reference integration assets.

This standard-library-only validator checks the reference-integrated dissertation
draft and related documentation. It does not call APIs, rerun model evaluation,
replace citations, or modify protected project files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INTEGRATED_DRAFT = PROJECT_ROOT / "docs" / "dissertation" / "full_dissertation_draft_with_references_v1.md"
ORIGINAL_DRAFT = PROJECT_ROOT / "docs" / "dissertation" / "full_dissertation_draft_v1.md"
REPLACEMENT_MAP = PROJECT_ROOT / "docs" / "dissertation" / "reference_replacement_map_v1.md"
REFERENCE_LIST = PROJECT_ROOT / "docs" / "dissertation" / "reference_list_integrated_draft_v1.md"
INTEGRATION_REPORT = PROJECT_ROOT / "docs" / "dissertation" / "reference_integration_report_v1.md"
UNRESOLVED_TODO = PROJECT_ROOT / "docs" / "dissertation" / "unresolved_reference_todo_v1.md"
PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "reference_integration_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i6f2_reference_integration_validation_report_v1.md"

EXPECTED_FILES = [
    INTEGRATED_DRAFT,
    REPLACEMENT_MAP,
    REFERENCE_LIST,
    INTEGRATION_REPORT,
    UNRESOLVED_TODO,
    PROFILE_FILE,
]

REQUIRED_DRAFT_STRINGS = [
    "[R1]",
    "[R2]",
    "[R3]",
    "[R4]",
    "88.21%",
    "80-case reviewed golden test set",
    "400-row full pool",
    "I-4E.4 product_category normalization",
]

REQUIRED_REPORT_STRINGS = [
    "direct golden labels",
    "formal evaluation basis",
    "batch stability evidence",
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

    if not ORIGINAL_DRAFT.exists():
        failures.append("Original full_dissertation_draft_v1.md is missing.")

    if INTEGRATED_DRAFT.exists():
        draft_text = read_text(INTEGRATED_DRAFT)
        for required in REQUIRED_DRAFT_STRINGS:
            if required not in draft_text:
                failures.append(f"Integrated draft missing required string: {required}")
        if "[REF-" in draft_text:
            failures.append("Integrated draft still contains unresolved [REF-...] placeholders.")
    else:
        failures.append("Integrated draft missing; cannot inspect content.")

    if REFERENCE_LIST.exists():
        ref_text = read_text(REFERENCE_LIST)
        if "metadata to verify before final formatting" not in ref_text:
            failures.append("Reference list missing metadata verification warning.")
        if "Accessed: 2026-05-23" not in ref_text:
            failures.append("Reference list missing accessed date.")
    else:
        failures.append("Reference list missing; cannot inspect content.")

    if INTEGRATION_REPORT.exists():
        report_text = read_text(INTEGRATION_REPORT)
        for required in REQUIRED_REPORT_STRINGS:
            if required not in report_text:
                failures.append(f"Integration report missing required phrase: {required}")
    else:
        failures.append("Integration report missing; cannot inspect content.")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-6F.2":
            failures.append("Profile stage is not I-6F.2.")
        if profile.get("source_stage") != "I-6F.1":
            failures.append("Profile source_stage is not I-6F.1.")
        if profile.get("no_api_call") is not True:
            failures.append("Profile no_api_call is not true.")
        if profile.get("no_model_rerun") is not True:
            failures.append("Profile no_model_rerun is not true.")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-6F.2 Reference Integration Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Expected I-6F.2 output files exist.",
        "- JSON profile is valid.",
        "- Integrated draft contains [R1], [R2], [R3], [R4], formal metric strings, and product_category normalization boundary.",
        "- Original full dissertation draft still exists.",
        "- Reference list includes metadata verification warnings and access date.",
        "- Integration report states direct golden labels, formal evaluation basis, and batch stability evidence boundaries.",
        "- Validation performs no API call, no model rerun, and no protected-file modification.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-6F.2 reference integration validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-6F.2 reference integration validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-6F.2 reference integration validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
