from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
CANDIDATE_PATCH_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1_candidate_patch.csv"
AUDIT_REPORT_PATH = PROJECT_ROOT / "outputs" / "golden_label_candidate_patch_audit_v1.md"
METRIC_PREVIEW_REPORT_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_metric_preview_v1.md"
METRIC_PREVIEW_JSON_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_metric_preview_v1.json"
PROFILE_PATH = PROJECT_ROOT / "configs" / "evaluation" / "golden_label_candidate_patch_profile_v1.json"
CREATE_SCRIPT_PATH = PROJECT_ROOT / "src" / "evaluation" / "create_i36_golden_label_candidate_patch_v1.py"
PREVIEW_SCRIPT_PATH = PROJECT_ROOT / "src" / "evaluation" / "preview_i36_candidate_patch_metrics_v1.py"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i36_candidate_patch_validation_report_v1.md"

REQUIRED_PATHS = [
    CANDIDATE_PATCH_PATH,
    AUDIT_REPORT_PATH,
    METRIC_PREVIEW_REPORT_PATH,
    METRIC_PREVIEW_JSON_PATH,
    PROFILE_PATH,
    CREATE_SCRIPT_PATH,
    PREVIEW_SCRIPT_PATH,
]

REQUIRED_PATCH_COLUMNS = [
    "email_id",
    "field",
    "original_golden_value",
    "candidate_golden_value",
    "baseline_prediction",
    "patched_prediction",
    "candidate_reason",
    "evidence_source",
    "issue_category",
    "confidence",
    "decision_status",
    "should_apply_now",
]

REQUIRED_CASES = {"P015", "P028", "P046"}

AUDIT_REQUIRED_PHRASES = [
    "P015",
    "P028",
    "P046",
    "do not overwrite",
    "human confirmation",
    "golden_label_issue",
    "taxonomy_ambiguity",
    "urgency_threshold_issue",
]

PREVIEW_REQUIRED_PHRASES = [
    "original golden labels",
    "candidate-patched labels",
    "preview",
    "not official final evaluation",
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


def read_patch_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != REQUIRED_PATCH_COLUMNS:
                errors.append(f"Candidate patch columns must exactly match required columns. Found: {reader.fieldnames}")
            rows = [dict(row) for row in reader]
    except Exception as exc:
        return [], [f"Could not read candidate patch CSV: {type(exc).__name__}: {exc}"]
    return rows, errors


def validate_assets() -> tuple[list[str], str]:
    errors: list[str] = []

    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"Missing required asset: {path}")

    golden_sha256 = sha256_file(GOLDEN_PATH) if GOLDEN_PATH.exists() else "missing"
    if not GOLDEN_PATH.exists():
        errors.append(f"Missing original golden label file: {GOLDEN_PATH}")

    metric_preview_json: dict[str, Any] | None = None
    if METRIC_PREVIEW_JSON_PATH.exists():
        metric_preview_json, error = load_json(METRIC_PREVIEW_JSON_PATH)
        if error:
            errors.append(f"Invalid metric preview JSON: {error}")
        elif metric_preview_json and metric_preview_json.get("stage") != "I-3.6":
            errors.append('Metric preview JSON stage must be "I-3.6".')

    profile_json: dict[str, Any] | None = None
    if PROFILE_PATH.exists():
        profile_json, error = load_json(PROFILE_PATH)
        if error:
            errors.append(f"Invalid profile JSON: {error}")
        elif profile_json and profile_json.get("stage") != "I-3.6":
            errors.append('Profile JSON stage must be "I-3.6".')

    if CANDIDATE_PATCH_PATH.exists():
        rows, csv_errors = read_patch_rows(CANDIDATE_PATCH_PATH)
        errors.extend(csv_errors)
        if rows:
            cases = {row.get("email_id", "") for row in rows}
            missing_cases = REQUIRED_CASES - cases
            if missing_cases:
                errors.append(f"Candidate patch CSV missing required cases: {sorted(missing_cases)}")
            bad_apply_values = sorted({row.get("should_apply_now", "") for row in rows if row.get("should_apply_now") != "false"})
            if bad_apply_values:
                errors.append(f"Candidate patch CSV has non-false should_apply_now values: {bad_apply_values}")
            bad_statuses = sorted(
                {row.get("decision_status", "") for row in rows if row.get("decision_status") != "needs_human_confirmation"}
            )
            if bad_statuses:
                errors.append(f"Candidate patch CSV has invalid decision_status values: {bad_statuses}")
        else:
            errors.append("Candidate patch CSV must contain at least one candidate row.")

    if AUDIT_REPORT_PATH.exists():
        audit_text = AUDIT_REPORT_PATH.read_text(encoding="utf-8").lower()
        for phrase in AUDIT_REQUIRED_PHRASES:
            if phrase.lower() not in audit_text:
                errors.append(f"Audit report missing required phrase: {phrase}")
        if golden_sha256 != "missing" and golden_sha256 not in audit_text:
            errors.append("Audit report missing original golden label SHA256.")

    if METRIC_PREVIEW_REPORT_PATH.exists():
        preview_text = METRIC_PREVIEW_REPORT_PATH.read_text(encoding="utf-8").lower()
        for phrase in PREVIEW_REQUIRED_PHRASES:
            if phrase.lower() not in preview_text:
                errors.append(f"Metric preview report missing required phrase: {phrase}")

    return errors, golden_sha256


def write_report(errors: list[str], golden_sha256: str) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-3.6 Candidate Patch Asset Validation Report v1",
        "",
        f"- Validation status: {status}",
        f"- Original golden label file: `{GOLDEN_PATH}`",
        f"- Original golden label SHA256: `{golden_sha256}`",
        "",
        "## Required Assets",
        "",
    ]
    for path in REQUIRED_PATHS:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")

    lines.extend(["", "## Candidate Patch Contract", ""])
    lines.append("- Required `should_apply_now=false` for every candidate row.")
    lines.append("- Required `decision_status=needs_human_confirmation` for every candidate row.")
    lines.append("- Required cases: P015, P028, P046.")
    lines.append("- Original golden labels are not overwritten by this validation.")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-3.6 candidate patch assets are present and structurally valid.")

    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors, golden_sha256 = validate_assets()
    write_report(errors, golden_sha256)
    if errors:
        print("FAIL: I-3.6 candidate patch asset validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-3.6 candidate patch asset validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")
    print(f"Original golden label SHA256: {golden_sha256}")


if __name__ == "__main__":
    main()
