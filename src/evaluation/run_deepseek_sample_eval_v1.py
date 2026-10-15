from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chains.langchain_complaint_chain import analyze_email_with_langchain
from src.config.llm_config import get_llm_config
from src.evaluation.evaluate_results import evaluate_predictions


DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_pilot_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
REVIEW_SAMPLE_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_review_sample_v1.csv"

EVALUATED_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run controlled DeepSeek/LangChain pilot evaluation.")
    parser.add_argument("--limit", type=int, default=10, help="Number of cases to run when not using --full-pilot.")
    parser.add_argument("--full-pilot", action="store_true", help="Run all 50 pilot dataset rows.")
    parser.add_argument("--output-prefix", default="deepseek_sample", help="Output filename prefix under outputs/.")
    return parser.parse_args()


def _normalize(value: object) -> str:
    return str(value).strip().lower()


def output_paths(prefix: str) -> tuple[Path, Path]:
    output_dir = PROJECT_ROOT / "outputs"
    return (
        output_dir / f"{prefix}_predictions_v1.csv",
        output_dir / f"{prefix}_eval_report_v1.md",
    )


def select_dataset_rows(dataset_df: pd.DataFrame, limit: int, full_pilot: bool) -> pd.DataFrame:
    if full_pilot:
        return dataset_df.copy()

    if REVIEW_SAMPLE_PATH.exists():
        sample_df = pd.read_csv(REVIEW_SAMPLE_PATH)
        sample_ids = sample_df["email_id"].astype(str).head(limit).tolist()
        selected = dataset_df[dataset_df["email_id"].astype(str).isin(sample_ids)].copy()
        selected["_order"] = selected["email_id"].astype(str).map({email_id: i for i, email_id in enumerate(sample_ids)})
        return selected.sort_values("_order").drop(columns=["_order"])

    return dataset_df.head(limit).copy()


def run_predictions(dataset_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for row in dataset_df.itertuples(index=False):
        records.append(analyze_email_with_langchain(str(row.email_id), str(row.email_body)))
    return pd.DataFrame(records)


def find_mismatches(predictions_df: pd.DataFrame, golden_df: pd.DataFrame) -> list[dict[str, str]]:
    merged = golden_df.merge(predictions_df, on="email_id", how="inner")
    mismatches = []
    for _, row in merged.iterrows():
        for field in EVALUATED_FIELDS:
            golden_col = f"{field}_label"
            if golden_col not in row or field not in row:
                continue
            prediction = row[field]
            golden_label = row[golden_col]
            if _normalize(prediction) != _normalize(golden_label):
                mismatches.append(
                    {
                        "email_id": str(row["email_id"]),
                        "field": field,
                        "prediction": str(prediction),
                        "golden_label": str(golden_label),
                    }
                )
    return mismatches


def _md_cell(value: object) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "\\|")
    return text[:300]


def build_report(
    report: dict,
    mismatches: list[dict[str, str]],
    predictions_df: pd.DataFrame,
    prediction_path: Path,
    report_path: Path,
    runtime_seconds: float,
) -> str:
    config = get_llm_config()
    summary = config.safe_summary()
    backend_counts = Counter(predictions_df["analyzer_backend"].fillna("unknown"))
    primary_backend = backend_counts.most_common(1)[0][0] if backend_counts else "unknown"
    total_comparisons = report["row_count"] * len(EVALUATED_FIELDS)
    parse_success_count = int(predictions_df.get("parse_success", pd.Series(dtype=bool)).astype(str).str.lower().eq("true").sum())
    schema_success_count = int(
        predictions_df.get("schema_validation_success", pd.Series(dtype=bool)).astype(str).str.lower().eq("true").sum()
    )
    api_attempted_count = int(
        predictions_df.get("api_attempted", pd.Series(dtype=bool)).astype(str).str.lower().eq("true").sum()
    )
    retry_series = predictions_df.get("api_retry_count", pd.Series(dtype=int)).fillna(0).astype(int)
    retry_count_total = int(retry_series.sum())
    retried_case_count = int(retry_series.gt(0).sum())
    api_error_series = predictions_df.get("api_error_message", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    api_error_count = int(api_error_series.ne("").sum())
    parse_failure_mask = ~predictions_df.get("parse_success", pd.Series(dtype=bool)).astype(str).str.lower().eq("true")
    schema_failure_mask = ~predictions_df.get("schema_validation_success", pd.Series(dtype=bool)).astype(str).str.lower().eq("true")
    failed_predictions_df = predictions_df[parse_failure_mask | schema_failure_mask | api_error_series.ne("")].copy()
    failed_email_ids = failed_predictions_df["email_id"].astype(str).tolist() if "email_id" in failed_predictions_df else []

    lines = [
        "# DeepSeek Sample Evaluation Report v1",
        "",
        "- Project stage: I-3.1.1 DeepSeek JSON Parse Robustness Patch",
        f"- Backend used: {primary_backend}",
        f"- Provider: {summary['provider']}",
        f"- Model name: {summary['model_name']}",
        f"- API enabled: {summary['enabled']}",
        f"- Input dataset path: `{DATASET_PATH}`",
        f"- Golden label path: `{GOLDEN_PATH}`",
        f"- Prediction path: `{prediction_path}`",
        f"- Report path: `{report_path}`",
        f"- Total cases: {report['row_count']}",
        f"- Runtime seconds: {runtime_seconds:.2f}",
        "",
    ]

    if primary_backend == "mock_fallback":
        lines.extend(
            [
                "> This run used mock_fallback, so it validates the DeepSeek integration path and evaluation runner structure rather than real LLM performance.",
                "",
            ]
        )
    elif primary_backend in {"deepseek_api", "langchain_llm"}:
        lines.extend(["> This run used the configured DeepSeek API backend.", ""])

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
            "`Mismatched fields` means incorrect field-level predictions across all evaluated fields and all selected cases. "
            f"With {report['row_count']} cases and {len(EVALUATED_FIELDS)} fields, there are {total_comparisons} comparisons. "
            f"This run has {len(mismatches)} mismatched field comparisons.",
            "",
            "## Runtime and Parsing Summary",
            "",
            f"- api_attempted count: {api_attempted_count}",
            f"- api_retry_count total: {retry_count_total}",
            f"- retried case count: {retried_case_count}",
            f"- parse_success count: {parse_success_count}",
            f"- schema_validation_success count: {schema_success_count}",
            f"- API error count after retry: {api_error_count}",
            f"- failed email IDs: {', '.join(failed_email_ids) if failed_email_ids else 'none'}",
            "- Cost note: token/cost is not precisely calculated in this version unless usage metadata is available.",
            "",
            "## Parse and Schema Failure Table",
            "",
        ]
    )
    if failed_predictions_df.empty:
        lines.append("No parse/schema/API diagnostic failures found.")
    else:
        lines.extend(
            [
                "| Email ID | Backend | Parse success | Schema validation success | API retry count | API error message | Raw response preview |",
                "|---|---|---:|---:|---:|---|---|",
            ]
        )
        for _, row in failed_predictions_df.iterrows():
            lines.append(
                "| {email_id} | {backend} | {parse_success} | {schema_success} | {retry_count} | {error} | {preview} |".format(
                    email_id=_md_cell(row.get("email_id")),
                    backend=_md_cell(row.get("analyzer_backend")),
                    parse_success=_md_cell(row.get("parse_success")),
                    schema_success=_md_cell(row.get("schema_validation_success")),
                    retry_count=_md_cell(row.get("api_retry_count")),
                    error=_md_cell(row.get("api_error_message") or row.get("error_message")),
                    preview=_md_cell(row.get("raw_response_preview")),
                )
            )

    lines.extend(
        [
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
            "## Limitations",
            "",
            "- Fallback mode validates code structure and evaluation flow, not final LLM performance.",
            "- Real API evaluation should start with 10 cases before running the full pilot.",
            "- Exact-match metrics can mark reasonable near-equivalent labels as mismatches.",
            "- Token usage and cost tracking are not implemented in this version.",
            "",
            "## Next Step Recommendation",
            "",
            "First run the 10-case fallback evaluation locally. When ready, copy `.env.example` to `.env`, set `LLM_ENABLE_API=true`, "
            "add a local API key, and run the 10-case API evaluation before any full-pilot API run.",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return primary_backend


def main() -> None:
    args = parse_args()
    prediction_path, report_path = output_paths(args.output_prefix)

    dataset_df = pd.read_csv(DATASET_PATH)
    selected_df = select_dataset_rows(dataset_df, limit=args.limit, full_pilot=args.full_pilot)
    selected_ids = set(selected_df["email_id"].astype(str))
    golden_df = pd.read_csv(GOLDEN_PATH)
    selected_golden_df = golden_df[golden_df["email_id"].astype(str).isin(selected_ids)].copy()

    start = time.perf_counter()
    predictions_df = run_predictions(selected_df)
    runtime_seconds = time.perf_counter() - start

    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    predictions_df.to_csv(prediction_path, index=False)

    report = evaluate_predictions(predictions_df, selected_golden_df, label_columns=EVALUATED_FIELDS)
    mismatches = find_mismatches(predictions_df, selected_golden_df)
    backend = build_report(report, mismatches, predictions_df, prediction_path, report_path, runtime_seconds)

    print("DeepSeek sample evaluation completed.")
    print(f"Backend used: {backend}")
    api_attempted_count = int(
        predictions_df.get("api_attempted", pd.Series(dtype=bool)).astype(str).str.lower().eq("true").sum()
    )
    api_retry_count_total = int(predictions_df.get("api_retry_count", pd.Series(dtype=int)).fillna(0).astype(int).sum())
    api_error_count = int(
        predictions_df.get("api_error_message", pd.Series(dtype=str)).fillna("").astype(str).str.strip().ne("").sum()
    )
    print(f"API attempted count: {api_attempted_count}")
    print(f"API retry count total: {api_retry_count_total}")
    print(f"API error count: {api_error_count}")
    print(f"Predictions saved to: {prediction_path}")
    print(f"Report saved to: {report_path}")
    for metric in report["metrics"]:
        print(f"{metric['label']}: accuracy={metric['accuracy']:.4f}")
    print(f"Mismatched fields: {len(mismatches)}")


if __name__ == "__main__":
    main()
