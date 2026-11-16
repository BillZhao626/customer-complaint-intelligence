"""Validate I-7B thesis quality review assets.

Documentation-only validator. It checks required review artifacts and does not
call APIs, rerun inference/evaluation, or modify protected files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

QUALITY_REPORT = PROJECT_ROOT / "docs" / "dissertation" / "thesis_quality_review_report_v1.md"
REWRITE_GUIDELINES = PROJECT_ROOT / "docs" / "dissertation" / "thesis_academic_rewrite_guidelines_v1.md"
FIGURE_TABLE_PLAN = PROJECT_ROOT / "docs" / "dissertation" / "thesis_figure_table_integration_plan_v2.md"
REFERENCE_REVIEW = PROJECT_ROOT / "docs" / "dissertation" / "thesis_reference_format_review_v1.md"
PRODUCT_GUARDRAIL = PROJECT_ROOT / "docs" / "dissertation" / "product_category_result_writing_guardrail_v1.md"
ACTION_LIST = PROJECT_ROOT / "docs" / "dissertation" / "thesis_revision_action_list_v1.md"
POLISH_SAMPLE = PROJECT_ROOT / "docs" / "dissertation" / "thesis_full_draft_academic_polish_sample_v1.md"
PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "thesis_quality_review_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i7b_thesis_quality_validation_report_v1.md"

EXPECTED_FILES = [
    QUALITY_REPORT,
    REWRITE_GUIDELINES,
    FIGURE_TABLE_PLAN,
    REFERENCE_REVIEW,
    PRODUCT_GUARDRAIL,
    ACTION_LIST,
    POLISH_SAMPLE,
    PROFILE_FILE,
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


def contains_any(text: str, values: list[str]) -> bool:
    return any(value in text for value in values)


def main() -> int:
    failures: list[str] = []

    for path in EXPECTED_FILES:
        if not path.exists():
            failures.append(f"Missing expected file: {path.relative_to(PROJECT_ROOT)}")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-7B":
            failures.append("Profile stage is not I-7B.")
        if profile.get("no_api_call") is not True:
            failures.append("Profile no_api_call is not true.")

    if QUALITY_REPORT.exists():
        text = read_text(QUALITY_REPORT)
        if "88.21%" not in text:
            failures.append("Quality report missing 88.21%.")
        if not contains_any(text, ["80-case reviewed golden test set", "80 个字段", "80-case"]):
            failures.append("Quality report missing reviewed golden test set phrase.")
        if not contains_any(text, ["400-row full pool", "400-row"]):
            failures.append("Quality report missing 400-row full pool phrase.")

    if PRODUCT_GUARDRAIL.exists():
        text = read_text(PRODUCT_GUARDRAIL)
        if not contains_any(text, ["secondary interpretation layer", "解释性分析"]):
            failures.append("Product category guardrail missing secondary interpretation layer wording.")

    if REFERENCE_REVIEW.exists():
        text = read_text(REFERENCE_REVIEW)
        if "GB/T 7714" not in text:
            failures.append("Reference format review missing GB/T 7714.")

    if FIGURE_TABLE_PLAN.exists():
        text = read_text(FIGURE_TABLE_PLAN)
        for phrase in ["formal evaluation", "Dashboard three-mode", "batch stability"]:
            if phrase not in text:
                failures.append(f"Figure/table plan missing required entry phrase: {phrase}")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-7B Thesis Quality Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Required I-7B files exist.",
        "- JSON profile is valid.",
        "- Quality report contains formal evaluation metrics and dataset boundary phrases.",
        "- Product category guardrail contains secondary interpretation layer wording.",
        "- Reference format review mentions GB/T 7714.",
        "- Figure/table plan contains formal evaluation, dashboard screenshots, and batch stability entries.",
        "- No protected files were required to be modified.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-7B thesis quality validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-7B thesis quality validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-7B thesis quality validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
