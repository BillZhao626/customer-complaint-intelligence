"""Validate I-6AB closeout and dissertation material assets.

This validator is intentionally documentation-focused. It does not call any
model API, run inference, regenerate data, or modify protected project assets.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_FILES = [
    PROJECT_ROOT / "docs" / "project_closeout_index_v1.md",
    PROJECT_ROOT / "docs" / "dissertation_material_package_v1.md",
    PROJECT_ROOT / "docs" / "evaluation_result_writeup_v1.md",
    PROJECT_ROOT / "docs" / "supervisor_report_summary_v1.md",
    PROJECT_ROOT / "docs" / "defense_demo_script_v1.md",
    PROJECT_ROOT / "configs" / "project_closeout_profile_v1.json",
    PROJECT_ROOT / "src" / "evaluation" / "validate_i6ab_closeout_assets_v1.py",
]

TEXT_FILES_TO_SCAN = [
    PROJECT_ROOT / "docs" / "project_closeout_index_v1.md",
    PROJECT_ROOT / "docs" / "dissertation_material_package_v1.md",
    PROJECT_ROOT / "docs" / "evaluation_result_writeup_v1.md",
    PROJECT_ROOT / "docs" / "supervisor_report_summary_v1.md",
    PROJECT_ROOT / "docs" / "defense_demo_script_v1.md",
]

PROFILE_FILE = PROJECT_ROOT / "configs" / "project_closeout_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i6ab_project_closeout_validation_report_v1.md"

REQUIRED_PHRASES = [
    "88.21%",
    "80-case reviewed golden test set",
    "400-row full pool",
    "not formal accuracy",
    "DeepSeek",
    "product_category",
    "source_attribution",
    "0 API errors",
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-.]{20,}"),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_json(path: Path) -> tuple[bool, object | None, str]:
    try:
        return True, json.loads(read_text(path)), ""
    except Exception as exc:  # pragma: no cover - report-only path
        return False, None, str(exc)


def main() -> int:
    failures: list[str] = []
    notes: list[str] = []

    for path in EXPECTED_FILES:
        if not path.exists():
            failures.append(f"Missing expected file: {path.relative_to(PROJECT_ROOT)}")

    profile_ok, profile, profile_error = validate_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif isinstance(profile, dict):
        if profile.get("stage") != "I-6AB":
            failures.append("project_closeout_profile_v1.json stage is not I-6AB")
        if profile.get("formal_accuracy_percent") != "88.21%":
            failures.append("project_closeout_profile_v1.json does not record 88.21% formal accuracy")
        constraints = profile.get("stage_constraints", {})
        if constraints.get("no_api_call") is not True:
            failures.append("profile does not mark no_api_call=true")

    existing_texts = []
    for path in TEXT_FILES_TO_SCAN:
        if path.exists():
            existing_texts.append((path, read_text(path)))

    combined_text = "\n".join(text for _, text in existing_texts)
    for phrase in REQUIRED_PHRASES:
        if phrase not in combined_text:
            failures.append(f"Required phrase missing from I-6AB docs: {phrase}")

    forbidden_old_copy = str(Path.home() / 'Documents' / 'complaint_llm_system')
    for path, text in existing_texts:
        if forbidden_old_copy in text:
            failures.append(f"Forbidden old project path appears in {path.relative_to(PROJECT_ROOT)}")

    for path, text in existing_texts:
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"Secret-like string detected in {path.relative_to(PROJECT_ROOT)}")

    # Guard evidence from prior stages without modifying it.
    important_existing_assets = [
        PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json",
        PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json",
        PROJECT_ROOT / "outputs" / "i5d_full_api_and_dashboard_evidence_report_v1.md",
        PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv",
    ]
    for path in important_existing_assets:
        if not path.exists():
            failures.append(f"Prior-stage evidence missing: {path.relative_to(PROJECT_ROOT)}")

    notes.append("I-6AB is documentation and packaging only.")
    notes.append("No DeepSeek API call is made by this validator.")
    notes.append("No model inference, dataset regeneration, or golden-label overwrite is performed.")

    status = "PASS" if not failures else "FAIL"

    lines = [
        "# I-6AB Project Closeout Asset Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- All expected I-6AB files exist.",
        "- `project_closeout_profile_v1.json` is valid JSON and records stage `I-6AB`.",
        "- Required boundary phrases are present across the I-6AB documentation corpus.",
        "- The old project copy path is absent from newly generated I-6AB docs.",
        "- No secret-like strings were detected in newly generated I-6AB docs.",
        "- Prior-stage evidence files remain present.",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)

    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["", "## Result", "", "PASS: I-6AB closeout asset validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-6AB closeout asset validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-6AB closeout asset validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
