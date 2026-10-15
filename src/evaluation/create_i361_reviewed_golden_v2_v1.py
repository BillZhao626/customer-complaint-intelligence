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

ACCEPTED_PATCHES = {
    ("P015", "urgency"): ("high", "medium"),
    ("P028", "source_attribution"): ("customer service response issue", "store service issue"),
    ("P046", "complaint_reason"): ("other", "delivery delay"),
    ("P046", "source_attribution"): ("unclear", "delivery/logistics issue"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        return [dict(row) for row in reader], fieldnames


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:400]


def build_reviewed_rows() -> tuple[list[dict[str, str]], list[str], list[dict[str, str]], list[dict[str, str]]]:
    golden_rows, golden_fieldnames = read_csv_rows(ORIGINAL_GOLDEN_PATH)
    patch_rows, _ = read_csv_rows(CANDIDATE_PATCH_PATH)
    patch_by_key = {(row["email_id"], row["field"]): row for row in patch_rows}

    missing = sorted(set(ACCEPTED_PATCHES) - set(patch_by_key))
    if missing:
        raise ValueError(f"Accepted patch rows missing from candidate patch CSV: {missing}")

    accepted_rows: list[dict[str, str]] = []
    not_applied_rows: list[dict[str, str]] = []

    for row in patch_rows:
        key = (row["email_id"], row["field"])
        if key in ACCEPTED_PATCHES:
            expected_original, expected_candidate = ACCEPTED_PATCHES[key]
            if row["original_golden_value"] != expected_original or row["candidate_golden_value"] != expected_candidate:
                raise ValueError(
                    "Candidate patch row does not match accepted project-owner decision: "
                    f"{key} {row['original_golden_value']} -> {row['candidate_golden_value']}"
                )
            accepted_rows.append(row)
        else:
            not_applied_rows.append(row)

    reviewed_rows = [dict(row) for row in golden_rows]
    rows_by_id = {row["email_id"]: row for row in reviewed_rows}
    for row in accepted_rows:
        label_column = f"{row['field']}_label"
        if row["email_id"] not in rows_by_id:
            raise ValueError(f"Accepted patch email_id not found in original golden labels: {row['email_id']}")
        if label_column not in rows_by_id[row["email_id"]]:
            raise ValueError(f"Accepted patch field not found in original golden labels: {row['email_id']} {row['field']}")
        current_value = rows_by_id[row["email_id"]][label_column]
        if current_value != row["original_golden_value"]:
            raise ValueError(
                f"Original golden value mismatch for {row['email_id']} {row['field']}: "
                f"expected {row['original_golden_value']}, found {current_value}"
            )
        rows_by_id[row["email_id"]][label_column] = row["candidate_golden_value"]

    return reviewed_rows, golden_fieldnames, accepted_rows, not_applied_rows


def write_decision_report(
    accepted_rows: list[dict[str, str]],
    not_applied_rows: list[dict[str, str]],
    original_sha256: str,
    reviewed_sha256: str,
) -> None:
    lines = [
        "# I-3.6.1 Candidate Patch Human Review Decision v1",
        "",
        "## Stage",
        "",
        "I-3.6.1 Candidate Patch Human Review Confirmation.",
        "",
        "## Purpose",
        "",
        "This stage records project-owner acceptance of the four I-3.6 candidate patch rows and applies them only to a new versioned reviewed label file.",
        "",
        "## Preservation Policy",
        "",
        "The original `data/golden/golden_labels_pilot_v1.csv` is preserved for historical comparison and is not overwritten.",
        "A new `data/golden/golden_labels_pilot_v2_reviewed.csv` file is created so future reviewed pilot metrics can be reported with a clear label version.",
        "",
        f"- Original v1 SHA256: `{original_sha256}`",
        f"- v2_reviewed SHA256: `{reviewed_sha256}`",
        "",
        "## Accepted Candidate Rows",
        "",
        "| Email ID | Field | Original v1 label | Reviewed v2 label | Evidence source | Reason |",
        "|---|---|---|---|---|---|",
    ]
    for row in accepted_rows:
        lines.append(
            f"| {md_cell(row['email_id'])} | {md_cell(row['field'])} | {md_cell(row['original_golden_value'])} | "
            f"{md_cell(row['candidate_golden_value'])} | {md_cell(row['evidence_source'])} | {md_cell(row['candidate_reason'])} |"
        )

    lines.extend(["", "## Rejected / Not Applied Fields", ""])
    if not_applied_rows:
        lines.extend(["| Email ID | Field | Original label | Candidate label | Reason not applied |", "|---|---|---|---|---|"])
        for row in not_applied_rows:
            lines.append(
                f"| {md_cell(row['email_id'])} | {md_cell(row['field'])} | {md_cell(row['original_golden_value'])} | "
                f"{md_cell(row['candidate_golden_value'])} | Not included in the project-owner accepted row list for I-3.6.1. |"
            )
    else:
        lines.append("No candidate patch rows were rejected. The I-3.6 candidate patch CSV contained exactly the four project-owner accepted rows.")

    lines.extend(
        [
            "",
            "## Why v2_reviewed Was Created",
            "",
            "Versioned reviewed labels allow the project to report both historical v1 metrics and human-reviewed project-label metrics without mixing the two references.",
            "The candidate patch CSV remains the audit trail, while v2_reviewed is the concrete reviewed reference file for future pilot reporting.",
            "",
            "## Evaluation Warning",
            "",
            "`golden_labels_pilot_v2_reviewed.csv` is a reviewed project reference label version for a synthetic pilot dataset. It is not an official external benchmark.",
            "",
            "## Recommended Usage",
            "",
            "- Use v1 for historical comparison.",
            "- Use v2_reviewed for future reviewed pilot metric reporting.",
            "- Keep the candidate patch CSV as the audit trail.",
            "",
        ]
    )
    DECISION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DECISION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_decision_profile(
    accepted_rows: list[dict[str, str]],
    original_sha256: str,
    reviewed_sha256: str,
) -> None:
    profile = {
        "stage": "I-3.6.1",
        "original_golden_file": str(ORIGINAL_GOLDEN_PATH),
        "candidate_patch_file": str(CANDIDATE_PATCH_PATH),
        "reviewed_golden_file": str(REVIEWED_GOLDEN_PATH),
        "accepted_patch_rows": [
            {
                "email_id": row["email_id"],
                "field": row["field"],
                "original_golden_value": row["original_golden_value"],
                "reviewed_golden_value": row["candidate_golden_value"],
                "evidence_source": row["evidence_source"],
                "decision_status": "accepted_by_project_owner_for_v2_reviewed",
            }
            for row in accepted_rows
        ],
        "original_sha256": original_sha256,
        "reviewed_sha256": reviewed_sha256,
        "policy": {
            "preserve_v1": True,
            "create_versioned_reviewed_labels": True,
            "do_not_overwrite_original": True,
            "use_for_future_reviewed_metrics": True,
        },
    }
    DECISION_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DECISION_PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    reviewed_rows, fieldnames, accepted_rows, not_applied_rows = build_reviewed_rows()
    original_sha256 = sha256_file(ORIGINAL_GOLDEN_PATH)
    write_csv_rows(REVIEWED_GOLDEN_PATH, reviewed_rows, fieldnames)
    reviewed_sha256 = sha256_file(REVIEWED_GOLDEN_PATH)
    write_decision_report(accepted_rows, not_applied_rows, original_sha256, reviewed_sha256)
    write_decision_profile(accepted_rows, original_sha256, reviewed_sha256)

    print("I-3.6.1 reviewed golden v2 file created.")
    print(f"Accepted patch rows: {len(accepted_rows)}")
    print(f"Reviewed golden file saved to: {REVIEWED_GOLDEN_PATH}")
    print(f"Decision report saved to: {DECISION_REPORT_PATH}")
    print(f"Decision profile saved to: {DECISION_PROFILE_PATH}")
    print(f"Original v1 SHA256: {original_sha256}")
    print(f"v2_reviewed SHA256: {reviewed_sha256}")


if __name__ == "__main__":
    main()
