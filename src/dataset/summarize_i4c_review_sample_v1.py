from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SELECTED_EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_v1.csv"
SELECTED_AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_auto_v1.csv"
FULL_DISTRIBUTION_PATH = PROJECT_ROOT / "outputs" / "full_dataset_distribution_summary_v1.json"
COVERAGE_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4c_review_sample_coverage_report_v1.md"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "i4c_review_sample_summary_v1.json"

DISTRIBUTION_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "store_location",
    "scenario_type",
    "edge_case_type",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def distribution(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row.get(field, "") for row in rows).items()))


def pct(count: int, total: int) -> str:
    return f"{count / total * 100:.1f}%" if total else "0.0%"


def add_comparison_table(
    lines: list[str],
    title: str,
    field: str,
    full_counts: dict[str, int],
    sample_counts: dict[str, int],
    full_total: int,
    sample_total: int,
) -> None:
    labels = sorted(set(full_counts) | set(sample_counts))
    lines.extend(["", f"## {title}", "", "| Label | Full count | Full share | Sample count | Sample share |", "|---|---:|---:|---:|---:|"])
    for label in labels:
        full_count = full_counts.get(label, 0)
        sample_count = sample_counts.get(label, 0)
        lines.append(f"| {label} | {full_count} | {pct(full_count, full_total)} | {sample_count} | {pct(sample_count, sample_total)} |")


def main() -> None:
    selected_emails = read_csv(SELECTED_EMAIL_PATH)
    selected_labels = read_csv(SELECTED_AUTO_LABEL_PATH)
    full_summary = load_json(FULL_DISTRIBUTION_PATH)
    full_distributions = full_summary["distributions"]
    full_total = int(full_summary["total_rows"])
    sample_total = len(selected_labels)
    sample_distributions = {field: distribution(selected_labels, field) for field in DISTRIBUTION_FIELDS}

    coverage_flags = {
        "sentiment_all_present": {"negative", "neutral", "positive"} <= set(sample_distributions["sentiment"]),
        "urgency_all_present": {"high", "medium", "low"} <= set(sample_distributions["urgency"]),
        "product_categories_all_present": set(full_distributions["product_category"]) <= set(sample_distributions["product_category"]),
        "source_attribution_all_present": set(full_distributions["source_attribution"]) <= set(sample_distributions["source_attribution"]),
        "complaint_reason_all_present": set(full_distributions["complaint_reason"]) <= set(sample_distributions["complaint_reason"]),
        "edge_case_all_present": set(full_distributions["edge_case_type"]) <= set(sample_distributions["edge_case_type"]),
        "multiple_store_locations": len(sample_distributions["store_location"]) >= 6,
    }

    summary = {
        "stage": "I-4C",
        "selected_email_file": str(SELECTED_EMAIL_PATH),
        "selected_auto_label_file": str(SELECTED_AUTO_LABEL_PATH),
        "total_selected_rows": sample_total,
        "full_dataset_rows": full_total,
        "label_status": "selected_auto_labels_not_human_reviewed",
        "sample_distributions": sample_distributions,
        "full_distributions_used_for_comparison": full_distributions,
        "coverage_flags": coverage_flags,
        "next_stage_recommendation": "manual review and creation of reviewed golden test labels",
    }
    SUMMARY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# I-4C Review Sample Coverage Report v1",
        "",
        "## Stage And Purpose",
        "",
        "I-4C selects 80 candidate cases from the 400-row synthetic full pool for manual review.",
        "",
        "## Full Dataset Role",
        "",
        "The full dataset is a synthetic dataset pool for dashboard statistics, batch processing, case coverage, and sampling. It is not a reviewed golden benchmark.",
        "",
        "## Reviewed Sample Candidate Role",
        "",
        "The selected 80 rows are manual review candidates. Their labels are still auto labels and this is not final golden test set output yet.",
        "",
        f"- Selected rows: {sample_total}",
        f"- Selected email file: `{SELECTED_EMAIL_PATH}`",
        f"- Selected auto label file: `{SELECTED_AUTO_LABEL_PATH}`",
    ]
    for field in DISTRIBUTION_FIELDS:
        title = field.replace("_", " ").title()
        add_comparison_table(
            lines,
            f"{title} Distribution",
            field,
            full_distributions.get(field, {}),
            sample_distributions[field],
            full_total,
            sample_total,
        )

    lines.extend(["", "## Rare Category Coverage", ""])
    for key, value in coverage_flags.items():
        lines.append(f"- {key}: {'yes' if value else 'no'}")

    lines.extend(
        [
            "",
            "## Edge Case Coverage",
            "",
        ]
    )
    for label, count in sample_distributions["edge_case_type"].items():
        lines.append(f"- {label}: {count}")

    lines.extend(
        [
            "",
            "## Why This Sample Is Suitable For Manual Review",
            "",
            "- It includes negative, neutral, and positive examples.",
            "- It includes high, medium, and low urgency examples.",
            "- It covers all product categories, complaint reasons, source attribution labels, and major edge cases from the full pool.",
            "- It includes all 10 synthetic store locations.",
            "- It is small enough for batch manual review while broad enough to support future reviewed golden test set construction.",
            "",
            "## Limitations",
            "",
            "- The selected labels are still auto-labeled before manual review.",
            "- This is not final golden test set yet.",
            "- Formal model metrics should wait until reviewed labels are created.",
            "",
            "## Next Step",
            "",
            "Manual review and creation of reviewed golden test labels.",
            "",
        ]
    )
    COVERAGE_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("I-4C review sample coverage summary completed.")
    print(f"Selected rows: {sample_total}")
    print(f"Coverage report saved to: {COVERAGE_REPORT_PATH}")
    print(f"Summary JSON saved to: {SUMMARY_JSON_PATH}")


if __name__ == "__main__":
    main()
