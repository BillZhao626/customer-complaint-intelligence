"""Validate I-7A thesis full draft assets.

This standard-library-only script validates documentation assets. It does not
call APIs, rerun model inference/evaluation, or modify datasets, labels, app
code, chain files, prompts, taxonomy, parser/schema/API config, .env, secrets,
or the I-5E screenshot package.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

THESIS_DRAFT = PROJECT_ROOT / "docs" / "dissertation" / "thesis_full_draft_v1.md"
REVISION_NOTES = PROJECT_ROOT / "docs" / "dissertation" / "thesis_full_draft_revision_notes_v1.md"
IMAGE_NOTES = PROJECT_ROOT / "docs" / "dissertation" / "thesis_image_insertion_notes_v1.md"
PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "thesis_full_draft_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i7a_thesis_full_draft_validation_report_v1.md"

EXPECTED_FILES = [
    THESIS_DRAFT,
    REVISION_NOTES,
    IMAGE_NOTES,
    PROFILE_FILE,
]

REQUIRED_THESIS_STRINGS = [
    "中文摘要",
    "Abstract",
    "第1章",
    "第2章",
    "第3章",
    "第4章",
    "第5章",
    "第6章",
    "88.21%",
    "80-case reviewed golden test set",
    "400-row full pool",
    "400/400",
    "2515.43",
    "6.29",
    "I-4E.4",
    "不替代 I-4E.2",
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

    if THESIS_DRAFT.exists():
        thesis_text = read_text(THESIS_DRAFT)
        for required in REQUIRED_THESIS_STRINGS:
            if required not in thesis_text:
                failures.append(f"Thesis draft missing required string: {required}")
    else:
        failures.append("Thesis full draft missing; cannot inspect content.")

    if IMAGE_NOTES.exists():
        image_text = read_text(IMAGE_NOTES)
        if "I-5E UI Screenshot Evidence Package v3 HD" not in image_text:
            failures.append("Image insertion notes missing I-5E UI Screenshot Evidence Package v3 HD.")
    else:
        failures.append("Image insertion notes missing; cannot inspect content.")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-7A":
            failures.append("Profile stage is not I-7A.")
        if profile.get("source_stage") != "I-6F.2":
            failures.append("Profile source_stage is not I-6F.2.")
        if profile.get("no_api_call") is not True:
            failures.append("Profile no_api_call is not true.")
        if profile.get("no_model_rerun") is not True:
            failures.append("Profile no_model_rerun is not true.")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-7A Thesis Full Draft Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Expected I-7A files exist.",
        "- JSON profile is valid.",
        "- Thesis draft contains abstracts, Chapters 1-6, core metrics, and boundary statements.",
        "- Image insertion notes mention I-5E UI Screenshot Evidence Package v3 HD.",
        "- Validation performs no API call and no model rerun.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-7A thesis full draft validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-7A thesis full draft validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-7A thesis full draft validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
