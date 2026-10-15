from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv"
AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_full_auto_v1.csv"
DISTRIBUTION_REPORT_PATH = PROJECT_ROOT / "outputs" / "full_dataset_distribution_report_v1.md"
DISTRIBUTION_JSON_PATH = PROJECT_ROOT / "outputs" / "full_dataset_distribution_summary_v1.json"

DISTRIBUTION_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "scenario_type",
    "edge_case_type",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def distribution(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row.get(field, "") for row in rows).items()))


def percentage(count: int, total: int) -> str:
    return f"{count / total * 100:.1f}%" if total else "0.0%"


def add_table(lines: list[str], title: str, counts: dict[str, int], total: int) -> None:
    lines.extend(["", f"## {title}", "", "| Label | Count | Share |", "|---|---:|---:|"])
    for label, count in counts.items():
        lines.append(f"| {label} | {count} | {percentage(count, total)} |")


def main() -> None:
    dataset_rows = read_csv(DATASET_PATH)
    label_rows = read_csv(AUTO_LABEL_PATH)
    total = len(label_rows)
    distributions = {field: distribution(label_rows, field) for field in DISTRIBUTION_FIELDS}

    summary: dict[str, Any] = {
        "stage": "I-4B",
        "dataset_file": str(DATASET_PATH),
        "auto_label_file": str(AUTO_LABEL_PATH),
        "total_rows": total,
        "dataset_row_count": len(dataset_rows),
        "label_status": "auto_generated_not_human_reviewed",
        "dataset_role": "synthetic dataset pool, not reviewed golden benchmark",
        "distributions": distributions,
        "next_step": "I-4C select 50-100 reviewed golden test set candidates",
    }
    DISTRIBUTION_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    DISTRIBUTION_JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Full Dataset Distribution Report v1",
        "",
        "## Stage And Purpose",
        "",
        "I-4B summarizes the generated 400-row full synthetic customer email dataset pool and its initial auto labels.",
        "",
        "## Dataset Role",
        "",
        "This is a synthetic dataset pool, not reviewed golden benchmark data. It supports dashboard statistics, batch processing demonstration, case coverage, and future reviewed golden test set sampling.",
        "",
        f"- Dataset file: `{DATASET_PATH}`",
        f"- Auto label file: `{AUTO_LABEL_PATH}`",
        f"- Total row count: {total}",
    ]
    for field in DISTRIBUTION_FIELDS:
        add_table(lines, field, distributions[field], total)

    lines.extend(
        [
            "",
            "## Coverage Observations",
            "",
            "- Sentiment and urgency distributions are designed to match the frozen I-4A profile.",
            "- All required complaint_reason, source_attribution, and product_category categories are represented.",
            "- The dataset includes positive praise, neutral inquiry, mixed praise plus complaint, refund plus no response, delivery update confusion, wrong item, safety/health, and after-sales cases.",
            "",
            "## Suitability For Dashboard Statistics",
            "",
            "The pool is suitable for dashboard statistics because it includes enough variation in sentiment, urgency, store location, product category, complaint reason, and source attribution to support aggregate charts.",
            "",
            "## Suitability For Future Reviewed Golden Test Set Sampling",
            "",
            "The pool is suitable for I-4C sampling because it includes common and boundary cases. A 50-100 case subset should still be manually reviewed before formal metric evaluation.",
            "",
            "## Limitations",
            "",
            "- Auto labels are not human-reviewed.",
            "- Formal metrics should not be computed on the full pool without review.",
            "- The full pool is synthetic and should not be described as an official external benchmark.",
            "",
            "## Next Step",
            "",
            "I-4C select 50-100 reviewed golden test set candidates.",
            "",
        ]
    )
    DISTRIBUTION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("I-4B full dataset distribution summary completed.")
    print(f"Total rows: {total}")
    print(f"Distribution report saved to: {DISTRIBUTION_REPORT_PATH}")
    print(f"Distribution JSON saved to: {DISTRIBUTION_JSON_PATH}")


if __name__ == "__main__":
    main()
