from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ORIGINAL_GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
CANDIDATE_PATCH_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1_candidate_patch.csv"
REVIEWED_GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v2_reviewed.csv"
DECISION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i361_candidate_patch_human_review_decision_v1.md"
DECISION_PROFILE_PATH = PROJECT_ROOT / "configs" / "evaluation" / "golden_label_review_decision_v1.json"
METRIC_PREVIEW_REPORT_PATH = PROJECT_ROOT / "outputs" / "i361_reviewed_golden_v2_metric_preview_v1.md"
METRIC_PREVIEW_JSON_PATH = PROJECT_ROOT / "outputs" / "i361_reviewed_golden_v2_metric_preview_v1.json"
EVALUATION_PROTOCOL_DOC_PATH = PROJECT_ROOT / "docs" / "evaluation_protocol_v1.md"
EVALUATION_PROTOCOL_JSON_PATH = PROJECT_ROOT / "configs" / "evaluation" / "evaluation_protocol_v1.json"
FULL_DATASET_PLAN_PATH = PROJECT_ROOT / "docs" / "full_dataset_expansion_plan_v1.md"
FULL_DATASET_PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "full_synthetic_dataset_profile_v1.json"
REVIEW_AND_SMOKE_PLAN_PATH = PROJECT_ROOT / "docs" / "full_dataset_review_and_smoke_plan_v1.md"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i361_i37_i4a_asset_validation_report_v1.md"

REQUIRED_PATHS = [
    REVIEWED_GOLDEN_PATH,
    DECISION_REPORT_PATH,
    DECISION_PROFILE_PATH,
    METRIC_PREVIEW_REPORT_PATH,
    METRIC_PREVIEW_JSON_PATH,
    EVALUATION_PROTOCOL_DOC_PATH,
    EVALUATION_PROTOCOL_JSON_PATH,
    FULL_DATASET_PLAN_PATH,
    FULL_DATASET_PROFILE_PATH,
    REVIEW_AND_SMOKE_PLAN_PATH,
]

PROTOCOL_REQUIRED_PHRASES = [
    "mismatch",
    "reviewed golden test set",
    "full synthetic dataset pool",
    "300-500",
    "50-100",
    "external datasets",
    "not direct golden answers",
]

FULL_PLAN_REQUIRED_PHRASES = [
    "20-case smoke",
    "dashboard",
    "batch processing",
    "case coverage",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object."
    return data, None


def read_csv_ids(path: Path) -> tuple[list[str], int, str | None]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = [dict(row) for row in csv.DictReader(file)]
    except Exception as exc:
        return [], 0, f"{type(exc).__name__}: {exc}"
    return [row.get("email_id", "") for row in rows], len(rows), None


def validate_assets() -> tuple[list[str], str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required asset: {path}")

    if not ORIGINAL_GOLDEN_PATH.exists():
        errors.append(f"Missing original golden label file: {ORIGINAL_GOLDEN_PATH}")
        original_sha256 = "missing"
    else:
        original_sha256 = sha256_file(ORIGINAL_GOLDEN_PATH)

    if not CANDIDATE_PATCH_PATH.exists():
        errors.append(f"Missing candidate patch file: {CANDIDATE_PATCH_PATH}")

    decision_profile: dict[str, Any] | None = None
    if DECISION_PROFILE_PATH.exists():
        decision_profile, error = load_json(DECISION_PROFILE_PATH)
        if error:
            errors.append(f"Invalid golden label review decision JSON: {error}")
        elif decision_profile and decision_profile.get("stage") != "I-3.6.1":
            errors.append('golden_label_review_decision_v1.json stage must be "I-3.6.1".')

    if METRIC_PREVIEW_JSON_PATH.exists():
        metric_preview, error = load_json(METRIC_PREVIEW_JSON_PATH)
        if error:
            errors.append(f"Invalid reviewed golden v2 metric preview JSON: {error}")
        elif metric_preview and metric_preview.get("stage") != "I-3.6.1":
            errors.append('i361_reviewed_golden_v2_metric_preview_v1.json stage must be "I-3.6.1".')

    if EVALUATION_PROTOCOL_JSON_PATH.exists():
        protocol, error = load_json(EVALUATION_PROTOCOL_JSON_PATH)
        if error:
            errors.append(f"Invalid evaluation protocol JSON: {error}")
        elif protocol and protocol.get("stage") != "I-3.7":
            errors.append('evaluation_protocol_v1.json stage must be "I-3.7".')

    if FULL_DATASET_PROFILE_PATH.exists():
        profile, error = load_json(FULL_DATASET_PROFILE_PATH)
        if error:
            errors.append(f"Invalid full synthetic dataset profile JSON: {error}")
        elif profile and profile.get("stage") != "I-4A":
            errors.append('full_synthetic_dataset_profile_v1.json stage must be "I-4A".')

    if decision_profile and original_sha256 != "missing":
        if decision_profile.get("original_sha256") != original_sha256:
            errors.append("Decision profile original_sha256 does not match current v1 golden label SHA256.")
        if not decision_profile.get("reviewed_sha256"):
            errors.append("Decision profile missing reviewed_sha256.")

    if DECISION_REPORT_PATH.exists() and original_sha256 != "missing":
        decision_text = DECISION_REPORT_PATH.read_text(encoding="utf-8").lower()
        if original_sha256.lower() not in decision_text:
            errors.append("Decision report missing original golden label SHA256.")

    if EVALUATION_PROTOCOL_DOC_PATH.exists():
        protocol_text = EVALUATION_PROTOCOL_DOC_PATH.read_text(encoding="utf-8").lower()
        for phrase in PROTOCOL_REQUIRED_PHRASES:
            if phrase.lower() not in protocol_text:
                errors.append(f"Evaluation protocol missing required phrase: {phrase}")

    if FULL_DATASET_PLAN_PATH.exists():
        full_plan_text = FULL_DATASET_PLAN_PATH.read_text(encoding="utf-8").lower()
        for phrase in FULL_PLAN_REQUIRED_PHRASES:
            if phrase.lower() not in full_plan_text:
                errors.append(f"Full dataset plan missing required phrase: {phrase}")

    if ORIGINAL_GOLDEN_PATH.exists() and REVIEWED_GOLDEN_PATH.exists():
        v1_ids, v1_count, v1_error = read_csv_ids(ORIGINAL_GOLDEN_PATH)
        v2_ids, v2_count, v2_error = read_csv_ids(REVIEWED_GOLDEN_PATH)
        if v1_error:
            errors.append(f"Could not read v1 golden labels: {v1_error}")
        if v2_error:
            errors.append(f"Could not read v2 reviewed golden labels: {v2_error}")
        if not v1_error and not v2_error:
            if v1_count != v2_count:
                errors.append(f"Reviewed golden v2 row count differs from v1: {v1_count} vs {v2_count}")
            if set(v1_ids) != set(v2_ids):
                errors.append("Reviewed golden v2 email_ids differ from v1.")

    return errors, original_sha256


def write_report(errors: list[str], original_sha256: str) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-3.6.1 / I-3.7 / I-4A Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        f"- Original golden label file: `{ORIGINAL_GOLDEN_PATH}`",
        f"- Original golden label SHA256: `{original_sha256}`",
        "",
        "## Required Assets",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")

    lines.extend(
        [
            "",
            "## Preservation Checks",
            "",
            f"- v1 original file exists: {'yes' if ORIGINAL_GOLDEN_PATH.exists() else 'no'}",
            f"- candidate patch file exists: {'yes' if CANDIDATE_PATCH_PATH.exists() else 'no'}",
            "- reviewed golden v2 must have same row count and email_ids as v1.",
            "",
            "## Result",
            "",
        ]
    )
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-3.6.1 / I-3.7 / I-4A assets are present and structurally valid.")

    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors, original_sha256 = validate_assets()
    write_report(errors, original_sha256)
    if errors:
        print("FAIL: I-3.6.1 / I-3.7 / I-4A asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-3.6.1 / I-3.7 / I-4A asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")
    print(f"Original golden label SHA256: {original_sha256}")


if __name__ == "__main__":
    main()
