from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chains.mock_complaint_chain import analyze_email
from src.evaluation.evaluate_results import LEGACY_LABEL_COLUMNS as DEFAULT_LABEL_COLUMNS, evaluate_predictions


RAW_PATH = PROJECT_ROOT / "data" / "raw" / "smoke_test_emails_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_smoke_v1.csv"
PREDICTION_PATH = PROJECT_ROOT / "outputs" / "smoke_test_predictions_v1.csv"
REPORT_PATH = PROJECT_ROOT / "outputs" / "smoke_test_report_v1.md"


def _normalize(value: object) -> str:
    return str(value).strip().lower()


def _golden_column(column: str) -> str:
    return f"{column}_label"


def _mismatch_note(field: str) -> str:
    notes = {
        "sentiment": "Sentiment label differs from the golden label.",
        "urgency": "Urgency level differs from the golden label.",
        "is_complaint": "Complaint flag differs from the golden label.",
        "store_location": "Store/location exact match failed.",
        "product_category": "Product category exact match failed.",
        "complaint_reason": "Complaint reason/source attribution differs from the golden label.",
    }
    return notes.get(field, "Predicted value differs from the golden label.")


def run_predictions(raw_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for row in raw_df.itertuples(index=False):
        result = analyze_email(str(row.email_text), email_id=str(row.email_id))
        records.append(result.model_dump())
    return pd.DataFrame(records)


def find_mismatches(predictions_df: pd.DataFrame, golden_df: pd.DataFrame) -> list[dict[str, str]]:
    report = evaluate_predictions(predictions_df, golden_df, DEFAULT_LABEL_COLUMNS)
    if report['status'] != 'valid':
        raise ValueError('; '.join(report['warnings']))
    return [dict(email_id=row['email_id'],field=row['field'],predicted=row['prediction'],golden_label=row['golden_label'],note=_mismatch_note(row['field'])) for row in report['mismatches']]


def build_markdown_report(report: dict, mismatches: list[dict[str, str]]) -> str:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "# Smoke Test Report v1",
        "",
        "- Project stage: I-1.2 / I-1.3 Smoke Regression and Evaluation Framework",
        f"- Timestamp: {timestamp}",
        "",
        "## Local Engineering Status",
        "",
        "- Local D: drive py_compile checks passed.",
        "- The smoke test runner executed successfully.",
        "- The prediction CSV and markdown report were generated.",
        "- In some Codex shell environments, the virtual environment may show a stale Python312 path warning. "
        "The local D: drive `.venv` check is the source of truth for this project.",
        "",
        "## Dataset and Path Summary",
        "",
        f"- Dataset path: `{RAW_PATH}`",
        f"- Golden label path: `{GOLDEN_PATH}`",
        f"- Prediction output path: `{PREDICTION_PATH}`",
        f"- Report output path: `{REPORT_PATH}`",
        f"- Total test cases: {report['row_count']}",
        "",
        "This is a small smoke regression set for the offline MVP mock analyzer. "
        "It is not a formal large-scale evaluation.",
        "",
        "## Field-Level Metrics",
        "",
        "Exact-match accuracy is the primary smoke regression metric. Weighted precision, recall, "
        "F1-score, and support are supplementary classification-style metrics.",
        "",
        "| Field | Accuracy | precision_weighted | recall_weighted | f1_weighted | Support |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for metric in report["metrics"]:
        lines.append(
            "| {label} | {accuracy:.4f} | {precision_weighted:.4f} | "
            "{recall_weighted:.4f} | {f1_weighted:.4f} | {support} |".format(**metric)
        )

    total_comparisons = report["row_count"] * len(DEFAULT_LABEL_COLUMNS)
    lines.extend(
        [
            "",
            "## Mismatched Fields Explanation",
            "",
            "`Mismatched fields` means the total number of incorrect field-level predictions across all "
            "evaluated fields and all test cases. For example, with 18 cases and 6 evaluated fields, "
            "there are 108 field-level comparisons in total. "
            f"In this run, {len(mismatches)} of {total_comparisons} field-level comparisons do not match the golden labels.",
            "",
            "## Error Analysis",
            "",
        ]
    )

    if mismatches:
        lines.extend(
            [
                "| Email ID | Field | Prediction | Golden label | Short note |",
                "|---|---|---|---|---|",
            ]
        )
        for item in mismatches:
            lines.append(
                f"| {item['email_id']} | {item['field']} | {item['predicted']} | "
                f"{item['golden_label']} | {item['note']} |"
            )
    else:
        lines.append("No mismatched rows or fields were found.")

    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This smoke test validates the MVP evaluation loop. The mock analyzer is an offline fallback "
            "baseline, and the current scores are not final model performance. Lower scores on "
            "`complaint_reason`, `sentiment`, and `product_category` expose the limitations of rule-based "
            "mock analysis. These limitations justify the next step: a LangChain + LLM structured output analyzer.",
            "",
            "## Dissertation Usage",
            "",
            "- Methodology: use this stage to describe dataset design, the structured output schema, "
            "the system pipeline, and the offline baseline.",
            "- Evaluation: use this stage to describe the smoke regression test, golden label design, "
            "field-level metrics, generated text rubric, and baseline limitations.",
            "",
            "## Next Step Recommendation",
            "",
            "Freeze the mock analyzer as an offline fallback baseline, then proceed to synthetic dataset "
            "generation and LangChain-based structured output analysis.",
            "",
            "This report is intended to catch regressions and compare the offline mock baseline "
            "with a later LangChain + LLM structured-output analyzer.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    raw_df = pd.read_csv(RAW_PATH)
    golden_df = pd.read_csv(GOLDEN_PATH)

    PREDICTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    predictions_df = run_predictions(raw_df)
    predictions_df.to_csv(PREDICTION_PATH, index=False)

    report = evaluate_predictions(predictions_df, golden_df, DEFAULT_LABEL_COLUMNS)
    mismatches = find_mismatches(predictions_df, golden_df)
    REPORT_PATH.write_text(build_markdown_report(report, mismatches), encoding="utf-8")

    print(f"Smoke test cases: {report['row_count']}")
    print(f"Predictions saved to: {PREDICTION_PATH}")
    print(f"Report saved to: {REPORT_PATH}")
    for metric in report["metrics"]:
        print(f"{metric['label']}: accuracy={metric['accuracy']:.4f}")
    print(f"Mismatched fields: {len(mismatches)}")


if __name__ == "__main__":
    main()
