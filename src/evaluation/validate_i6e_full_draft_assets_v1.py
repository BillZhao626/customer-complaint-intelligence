"""Validate I-6E dissertation full draft assembly assets.

Standard-library-only validator. It checks documentation/package files and does
not call DeepSeek, rerun inference/evaluation, or modify protected assets.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_FILES = [
    PROJECT_ROOT / "docs" / "dissertation" / "full_dissertation_draft_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "full_dissertation_figure_table_placeholder_map_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "reference_placeholder_mapping_v1.md",
    PROJECT_ROOT / "docs" / "dissertation" / "word_template_migration_checklist_v1.md",
    PROJECT_ROOT / "configs" / "dissertation" / "dissertation_full_draft_assembly_profile_v1.json",
]

FULL_DRAFT = PROJECT_ROOT / "docs" / "dissertation" / "full_dissertation_draft_v1.md"
PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "dissertation_full_draft_assembly_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i6e_full_draft_asset_validation_report_v1.md"

REQUIRED_FULL_DRAFT_STRINGS = [
    "Chapter 1",
    "Chapter 2",
    "Chapter 3",
    "Chapter 4",
    "Chapter 5",
    "Chapter 6",
    "88.21%",
    "80-case reviewed golden test set",
    "400-row full pool",
    "400/400",
    "product_category normalization caveat",
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

    if FULL_DRAFT.exists():
        draft_text = read_text(FULL_DRAFT)
        for required in REQUIRED_FULL_DRAFT_STRINGS:
            if required not in draft_text:
                failures.append(f"Full draft missing required string: {required}")
    else:
        failures.append("Full dissertation draft missing; cannot check required strings.")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-6E":
            failures.append("Profile stage is not I-6E.")
        if profile.get("no_api_call") is not True:
            failures.append("Profile no_api_call is not true.")
        if profile.get("no_model_inference_rerun") is not True:
            failures.append("Profile no_model_inference_rerun is not true.")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-6E Full Draft Asset Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Expected I-6E full draft files exist.",
        "- Full dissertation draft contains Chapter 1 through Chapter 6.",
        "- Full dissertation draft contains required evaluation boundary strings.",
        "- JSON profile is valid and records stage I-6E.",
        "- Validation performs no API call and no model inference.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-6E full draft asset validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-6E full draft asset validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-6E full draft asset validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
