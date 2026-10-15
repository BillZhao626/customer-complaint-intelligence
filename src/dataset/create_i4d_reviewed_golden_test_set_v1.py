from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_auto_v1.csv"
EMAIL_SAMPLE_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_v1.csv"
REVIEWED_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv"
AUDIT_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4d_manual_review_audit_report_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4d_reviewed_golden_test_set_summary_v1.json"
PROFILE_PATH = PROJECT_ROOT / "configs" / "evaluation" / "reviewed_golden_test_set_profile_v1.json"

REVIEW_SOURCE = "manual_review_chatgpt_assisted_v1"
URGENCY_RATIONALE = (
    "Urgency corrected after manual review: high urgency should require safety/health risk, "
    "explicit urgent/ASAP wording, severe disruption, escalation, or repeated long-term no response; "
    "ordinary broken product, delivery not arrived, unclear repair process, normal after-sales issue, "
    "or neutral pre-sales inquiry should use medium or low as appropriate."
)

CORRECTIONS = {
    "F031": ("high", "medium"),
    "F041": ("high", "medium"),
    "F081": ("high", "medium"),
    "F086": ("high", "medium"),
    "F201": ("high", "medium"),
    "F206": ("high", "medium"),
    "F391": ("medium", "low"),
    "F396": ("medium", "low"),
    "F399": ("medium", "low"),
    "F400": ("medium", "low"),
}

REVIEWED_COLUMNS = [
    "email_id",
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "review_status",
    "reviewer_notes",
    "review_source",
]

EVALUATION_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("|", "\\|")[:400]


def build_reviewed_rows(auto_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    auto_ids = {row["email_id"] for row in auto_rows}
    missing = sorted(set(CORRECTIONS) - auto_ids)
    if missing:
        raise ValueError(f"Correction ids missing from auto labels: {missing}")

    reviewed_rows: list[dict[str, str]] = []
    for row in auto_rows:
        email_id = row["email_id"]
        urgency = row["urgency"]
        review_status = "accepted"
        reviewer_notes = "Auto labels accepted after manual review."

        if email_id in CORRECTIONS:
            expected_original, corrected_value = CORRECTIONS[email_id]
            if urgency != expected_original:
                raise ValueError(f"{email_id} expected original urgency {expected_original}, found {urgency}.")
            urgency = corrected_value
            review_status = "corrected"
            reviewer_notes = URGENCY_RATIONALE

        reviewed_rows.append(
            {
                "email_id": email_id,
                "sentiment": row["sentiment"],
                "urgency": urgency,
                "is_complaint": row["is_complaint"],
                "store_location": row["store_location"],
                "product_category": row["product_category"],
                "complaint_reason": row["complaint_reason"],
                "source_attribution": row["source_attribution"],
                "review_status": review_status,
                "reviewer_notes": reviewer_notes,
                "review_source": REVIEW_SOURCE,
            }
        )
    return reviewed_rows


def write_audit_report(auto_sha256: str, reviewed_sha256: str) -> None:
    lines = [
        "# I-4D Manual Review Audit Report v1",
        "",
        "## Stage",
        "",
        "I-4D Create Reviewed Golden Test Set from Manual Review Decisions.",
        "",
        "## Purpose",
        "",
        "This stage converts the I-4C selected auto labels into a versioned reviewed golden test set by applying manually reviewed urgency corrections.",
        "",
        "## Inputs Used",
        "",
        f"- Selected email file: `{EMAIL_SAMPLE_PATH}`",
        f"- Source auto label file: `{AUTO_LABEL_PATH}`",
        "",
        "## Manual Review Summary",
        "",
        "- total: 80",
        "- accepted: 70",
        "- corrected: 10",
        "- needs_discussion: 0",
        "",
        "## Correction Table",
        "",
        "| Email ID | Field | Auto label | Reviewed label |",
        "|---|---|---|---|",
    ]
    for email_id, (original, corrected) in CORRECTIONS.items():
        lines.append(f"| {email_id} | urgency | {original} | {corrected} |")

    lines.extend(
        [
            "",
            "## Correction Rationale",
            "",
            "High urgency threshold: high urgency should require safety/health risk, explicit urgent/ASAP wording, severe disruption, escalation, or repeated long-term no response.",
            "Ordinary broken product, delivery not arrived, unclear repair process, or normal after-sales issue should usually be medium. Neutral pre-sales inquiry should usually be low.",
            "",
            "## Fields Accepted Without Correction",
            "",
            "- sentiment",
            "- is_complaint",
            "- store_location",
            "- product_category",
            "- complaint_reason",
            "- source_attribution",
            "",
            "## SHA256 Audit",
            "",
            f"- Auto label file SHA256: `{auto_sha256}`",
            f"- Reviewed label file SHA256: `{reviewed_sha256}`",
            "",
            "## Evaluation Meaning",
            "",
            f"`{REVIEWED_LABEL_PATH}` is now the reviewed golden test set for formal model evaluation in the next stage.",
            "The 400-row full auto label file is still not a reviewed golden benchmark.",
            "",
            "## Run Policy",
            "",
            "- No API call was made.",
            "- No model evaluation was run.",
            "",
            "## Recommended Next Stage",
            "",
            "I-4E reviewed golden test set DeepSeek evaluation.",
            "",
        ]
    )
    AUDIT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_summary_and_profile(reviewed_rows: list[dict[str, str]], auto_sha256: str, reviewed_sha256: str) -> None:
    status_counts = Counter(row["review_status"] for row in reviewed_rows)
    corrected_cases = [
        {
            "email_id": email_id,
            "field": "urgency",
            "auto_value": original,
            "reviewed_value": corrected,
            "rationale": "urgency_threshold_adjustment",
        }
        for email_id, (original, corrected) in CORRECTIONS.items()
    ]
    summary = {
        "stage": "I-4D",
        "reviewed_golden_file": str(REVIEWED_LABEL_PATH),
        "source_auto_label_file": str(AUTO_LABEL_PATH),
        "source_email_file": str(EMAIL_SAMPLE_PATH),
        "total_rows": len(reviewed_rows),
        "accepted_count": status_counts.get("accepted", 0),
        "corrected_count": status_counts.get("corrected", 0),
        "needs_discussion_count": status_counts.get("needs_discussion", 0),
        "corrected_cases": corrected_cases,
        "correction_fields_summary": {"urgency": len(corrected_cases)},
        "auto_label_sha256": auto_sha256,
        "reviewed_label_sha256": reviewed_sha256,
        "label_status": "human_reviewed_golden_test_set",
        "next_stage_recommendation": "I-4E_reviewed_golden_test_set_evaluation",
    }
    SUMMARY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    profile = {
        "version": "v1",
        "stage": "I-4D",
        "reviewed_golden_file": str(REVIEWED_LABEL_PATH),
        "reviewed_email_file": str(EMAIL_SAMPLE_PATH),
        "source_auto_label_file": str(AUTO_LABEL_PATH),
        "manual_review_method": REVIEW_SOURCE,
        "review_status_counts": dict(status_counts),
        "fields_for_evaluation": EVALUATION_FIELDS,
        "metric_policy": {
            "formal_metrics_should_use_reviewed_golden_test_set": True,
        },
        "full_pool_policy": {
            "400_row_full_pool_is_for_dashboard_batch_statistics_and_case_coverage": True,
        },
        "next_stage_recommendation": "I-4E",
    }
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    auto_rows = read_csv(AUTO_LABEL_PATH)
    email_rows = read_csv(EMAIL_SAMPLE_PATH)
    if len(auto_rows) != 80:
        raise ValueError(f"Expected 80 auto label rows, found {len(auto_rows)}.")
    if len(email_rows) != 80:
        raise ValueError(f"Expected 80 selected email rows, found {len(email_rows)}.")
    if {row["email_id"] for row in auto_rows} != {row["email_id"] for row in email_rows}:
        raise ValueError("Selected email ids and auto label ids do not match.")

    reviewed_rows = build_reviewed_rows(auto_rows)
    write_csv(REVIEWED_LABEL_PATH, reviewed_rows, REVIEWED_COLUMNS)
    auto_sha256 = sha256_file(AUTO_LABEL_PATH)
    reviewed_sha256 = sha256_file(REVIEWED_LABEL_PATH)
    write_audit_report(auto_sha256, reviewed_sha256)
    write_summary_and_profile(reviewed_rows, auto_sha256, reviewed_sha256)

    counts = Counter(row["review_status"] for row in reviewed_rows)
    print("I-4D reviewed golden test set created.")
    print(f"Reviewed rows: {len(reviewed_rows)}")
    print(f"Accepted: {counts.get('accepted', 0)}")
    print(f"Corrected: {counts.get('corrected', 0)}")
    print(f"Needs discussion: {counts.get('needs_discussion', 0)}")
    print(f"Reviewed golden file saved to: {REVIEWED_LABEL_PATH}")
    print(f"Auto label SHA256: {auto_sha256}")
    print(f"Reviewed label SHA256: {reviewed_sha256}")


if __name__ == "__main__":
    main()
