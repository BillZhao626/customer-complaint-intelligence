"""Validate I-6F.1 verified reference candidate assets.

This validator is standard-library only. It checks the reference candidate
package and writes a validation report. It does not modify protected project
files, replace dissertation citation placeholders, call DeepSeek, or run model
inference/evaluation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REFERENCE_DOC = PROJECT_ROOT / "docs" / "dissertation" / "reference_candidates_verified_v1.md"
BIB_DRAFT = PROJECT_ROOT / "docs" / "dissertation" / "reference_candidates_bib_draft_v1.md"
PROFILE_FILE = PROJECT_ROOT / "configs" / "dissertation" / "reference_candidates_verified_profile_v1.json"
REPORT_FILE = PROJECT_ROOT / "outputs" / "i6f1_reference_candidates_validation_report_v1.md"

EXPECTED_FILES = [
    REFERENCE_DOC,
    BIB_DRAFT,
    PROFILE_FILE,
]

REQUIRED_REFERENCE_DOC_STRINGS = [
    "I-6F.1",
    "LangChain",
    "Pydantic",
    "Streamlit",
    "scikit-learn",
    "DeepSeek",
    "OpenAI",
    "Amazon",
    "CFPB",
    "Bitext",
    "Synthetic",
    "80-case reviewed golden test set",
    "400-row full pool",
    "I-4E.4 product_category normalization",
]

PROTECTED_FILES = [
    PROJECT_ROOT / "docs" / "dissertation" / "full_dissertation_draft_v1.md",
    PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv",
    PROJECT_ROOT / "data" / "golden" / "golden_labels_full_auto_v1.csv",
    PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv",
    PROJECT_ROOT / "app.py",
    PROJECT_ROOT / "src" / "chains" / "langchain_complaint_chain.py",
    PROJECT_ROOT / "src" / "chains" / "mock_complaint_chain.py",
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

    if REFERENCE_DOC.exists():
        reference_text = read_text(REFERENCE_DOC)
        for required in REQUIRED_REFERENCE_DOC_STRINGS:
            if required not in reference_text:
                failures.append(f"Reference candidates doc missing required string: {required}")
    else:
        failures.append("Reference candidates doc missing; cannot inspect content.")

    if BIB_DRAFT.exists():
        bib_text = read_text(BIB_DRAFT)
        if "metadata to verify before final formatting" not in bib_text:
            failures.append("Bibliography draft does not mark incomplete metadata for verification.")
    else:
        failures.append("Bibliography draft missing; cannot inspect metadata boundary.")

    profile_ok, profile, profile_error = load_json(PROFILE_FILE)
    if not profile_ok:
        failures.append(f"Invalid JSON profile: {profile_error}")
    elif profile:
        if profile.get("stage") != "I-6F.1":
            failures.append("Profile stage is not I-6F.1.")
        if profile.get("source_inventory_count") != 13:
            failures.append("Profile source_inventory_count is not 13.")
        if profile.get("no_placeholder_replacement") is not True:
            failures.append("Profile no_placeholder_replacement is not true.")
        if profile.get("no_api_call") is not True:
            failures.append("Profile no_api_call is not true.")

    missing_protected = [path for path in PROTECTED_FILES if not path.exists()]
    for path in missing_protected:
        failures.append(f"Protected file missing during validation: {path.relative_to(PROJECT_ROOT)}")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# I-6F.1 Reference Candidates Validation Report v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Status: {status}",
        "",
        "## Checks",
        "",
        "- Expected reference candidate files exist.",
        "- JSON profile is valid and records stage I-6F.1.",
        "- Reference candidates document contains required source names and project boundary phrases.",
        "- Bibliography draft marks incomplete metadata as `metadata to verify before final formatting`.",
        "- Protected project files were not modified by this validator; it only reads their existence and writes this report.",
        "- No placeholder replacement is performed in this stage.",
        "",
    ]

    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Result", "", "PASS: I-6F.1 reference candidates validation passed."])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL: I-6F.1 reference candidates validation failed.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: I-6F.1 reference candidates validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
