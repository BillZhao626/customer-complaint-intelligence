from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chains.langchain_complaint_chain import analyze_email_with_langchain
from src.evaluation.evaluate_results import evaluate_predictions


DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_pilot_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
PREDICTION_PATH = PROJECT_ROOT / "outputs" / "langchain_pilot_predictions_v1.csv"
REPORT_PATH = PROJECT_ROOT / "outputs" / "langchain_pilot_eval_report_v1.md"

EVALUATED_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def _normalize(value: object) -> str:
    return str(value).strip().lower()


def run_predictions(dataset_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for row in dataset_df.itertuples(index=False):
        result = analyze_email_with_langchain(str(row.email_id), str(row.email_body))
        records.append(result)
    return pd.DataFrame(records)


def find_mismatches(predictions_df: pd.DataFrame, golden_df: pd.DataFrame) -> list[dict[str, str]]:
    merged = golden_df.merge(predictions_df, on="email_id", how="inner")
    mismatches = []
    for _, row in merged.iterrows():
        for field in EVALUATED_FIELDS:
            golden_col = f"{field}_label"
            if golden_col not in row or field not in row:
                continue
            predicted = row[field]
            expected = row[golden_col]
            if _normalize(predicted) != _normalize(expected):
                mismatches.append(
                    {
                        "email_id": str(row["email_id"]),
                        "field": field,
                        "prediction": str(predicted),
                        "golden_label": str(expected),
                    }
                )
    return mismatches


def build_report(report: dict, mismatches: list[dict[str, str]], backend_counts: Counter) -> str:
    backend_label = ", ".join(f"{backend}={count}" for backend, count in sorted(backend_counts.items()))
    primary_backend = backend_counts.most_common(1)[0][0] if backend_counts else "unknown"
    total_comparisons = report["row_count"] * len(EVALUATED_FIELDS)

    lines = [
        "# LangChain Pilot Evaluation Report v1",
        "",
        "- Project stage: I-3 LangChain + LLM Structured Output Analyzer",
        f"- Backend used: {primary_backend}",
        f"- Backend counts: {backend_label}",
        f"- Input dataset path: `{DATASET_PATH}`",
        f"- Golden label path: `{GOLDEN_PATH}`",
        f"- Prediction output path: `{PREDICTION_PATH}`",
        f"- Total cases: {report['row_count']}",
        "",
    ]

    if primary_backend == "mock_fallback":
        lines.extend(
            [
                "> This run used the mock fallback backend, so it validates the LangChain pipeline structure rather than final LLM performance.",
                "",
            ]
        )

    lines.extend(
        [
            "## Field-Level Metrics",
            "",
            "| Field | Accuracy | precision_weighted | recall_weighted | f1_weighted | Support |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for metric in report["metrics"]:
        lines.append(
            "| {label} | {accuracy:.4f} | {precision_weighted:.4f} | "
            "{recall_weighted:.4f} | {f1_weighted:.4f} | {support} |".format(**metric)
        )

    lines.extend(
        [
            "",
            "## Mismatched Fields Explanation",
            "",
            "`Mismatched fields` means incorrect field-level predictions across all evaluated fields and all test cases. "
            f"With {report['row_count']} cases and {len(EVALUATED_FIELDS)} fields, there are {total_comparisons} comparisons. "
            f"This run has {len(mismatches)} mismatched field comparisons.",
            "",
            "## Mismatch Table",
            "",
        ]
    )
    if mismatches:
        lines.extend(["| Email ID | Field | Prediction | Golden label |", "|---|---|---|---|"])
        for item in mismatches:
            lines.append(f"| {item['email_id']} | {item['field']} | {item['prediction']} | {item['golden_label']} |")
    else:
        lines.append("No mismatches found.")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This evaluation checks whether the first LangChain-compatible analyzer pipeline can process the pilot dataset, "
            "save structured predictions, and reuse the existing field-level evaluation framework.",
            "",
            "## Limitations",
            "",
            "- Without LLM API configuration, the analyzer uses the mock fallback backend.",
            "- A mock fallback run is useful for pipeline validation, but it is not final LLM performance.",
            "- Exact-match field evaluation may mark near-equivalent labels as incorrect.",
            "",
            "## Next Step Recommendation",
            "",
            "Verify the pipeline locally, then configure an LLM provider through environment variables when ready. "
            "After that, compare `langchain_llm` results against the frozen mock fallback baseline.",
            "",
        ]
    )
    if report["warnings"]:
        lines.extend(["## Evaluation Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return primary_backend


def main() -> None:
    dataset_df = pd.read_csv(DATASET_PATH)
    golden_df = pd.read_csv(GOLDEN_PATH)

    PREDICTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    predictions_df = run_predictions(dataset_df)
    predictions_df.to_csv(PREDICTION_PATH, index=False)

    report = evaluate_predictions(predictions_df, golden_df, label_columns=EVALUATED_FIELDS)
    mismatches = find_mismatches(predictions_df, golden_df)
    backend_counts = Counter(predictions_df["analyzer_backend"].fillna("unknown"))
    backend = build_report(report, mismatches, backend_counts)

    print("LangChain pilot evaluation completed.")
    print(f"Backend used: {backend}")
    print(f"Predictions saved to: {PREDICTION_PATH}")
    print(f"Report saved to: {REPORT_PATH}")
    for metric in report["metrics"]:
        print(f"{metric['label']}: accuracy={metric['accuracy']:.4f}")
    print(f"Mismatched fields: {len(mismatches)}")


if __name__ == "__main__":
    main()
