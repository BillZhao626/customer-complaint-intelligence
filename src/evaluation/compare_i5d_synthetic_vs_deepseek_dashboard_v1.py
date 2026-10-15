from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SYNTHETIC_DASHBOARD_PATH = PROJECT_ROOT / "outputs" / "dashboard_i4f" / "dashboard_stats_v1.json"
DEEPSEEK_DASHBOARD_PATH = PROJECT_ROOT / "outputs" / "dashboard_i5c_deepseek" / "deepseek_dashboard_stats_v1.json"
I4G_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4g_full_pool_deepseek_batch_summary_v1.json"
I4E2_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json"
I4E3_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_interpretation_summary_v1.json"
I4E4_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e4_post_normalized_eval_summary_v1.json"
I5D_API_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i5d_full_api_result_summary_v1.json"

COMPARISON_JSON_PATH = PROJECT_ROOT / "outputs" / "i5d_synthetic_vs_deepseek_dashboard_comparison_v1.json"
COMPARISON_REPORT_PATH = PROJECT_ROOT / "outputs" / "i5d_synthetic_vs_deepseek_dashboard_comparison_v1.md"
SCREENSHOT_PLAN_PATH = PROJECT_ROOT / "docs" / "i5d_dashboard_screenshot_and_figure_plan_v1.md"
CONSOLIDATED_REPORT_PATH = PROJECT_ROOT / "outputs" / "i5d_full_api_and_dashboard_evidence_report_v1.md"

SENTIMENT_CSV_PATH = PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_sentiment_v1.csv"
URGENCY_CSV_PATH = PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_urgency_v1.csv"
REASON_CSV_PATH = PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_complaint_reason_v1.csv"
SOURCE_CSV_PATH = PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_source_attribution_v1.csv"
PRODUCT_CSV_PATH = PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_product_ranking_v1.csv"
STORE_CSV_PATH = PROJECT_ROOT / "outputs" / "i5d_distribution_comparison_store_ranking_v1.csv"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_count_map(rows: list[dict[str, Any]], label_key: str, count_key: str = "count") -> dict[str, int]:
    return {str(row[label_key]): int(row[count_key]) for row in rows}


def compare_distribution(
    synthetic_rows: list[dict[str, Any]],
    deepseek_rows: list[dict[str, Any]],
    label_key: str,
    total: int = 400,
) -> list[dict[str, Any]]:
    synthetic_counts = to_count_map(synthetic_rows, label_key)
    deepseek_counts = to_count_map(deepseek_rows, label_key)
    labels = sorted(set(synthetic_counts) | set(deepseek_counts))
    output: list[dict[str, Any]] = []
    for label in labels:
        synthetic_count = synthetic_counts.get(label, 0)
        deepseek_count = deepseek_counts.get(label, 0)
        delta = deepseek_count - synthetic_count
        output.append(
            {
                label_key: label,
                "synthetic_reference_count": synthetic_count,
                "deepseek_prediction_count": deepseek_count,
                "absolute_delta": delta,
                "percentage_delta": round(delta / total * 100, 2) if total else 0.0,
            }
        )
    return sorted(output, key=lambda row: (-abs(row["absolute_delta"]), str(row[label_key])))


def compare_ranking(
    synthetic_rows: list[dict[str, Any]],
    deepseek_rows: list[dict[str, Any]],
    label_key: str,
    metric_key: str,
    rate_key: str,
    total: int = 400,
) -> list[dict[str, Any]]:
    synthetic_by_label = {str(row[label_key]): row for row in synthetic_rows}
    deepseek_by_label = {str(row[label_key]): row for row in deepseek_rows}
    labels = sorted(set(synthetic_by_label) | set(deepseek_by_label))
    output: list[dict[str, Any]] = []
    for label in labels:
        synthetic_row = synthetic_by_label.get(label, {})
        deepseek_row = deepseek_by_label.get(label, {})
        synthetic_count = int(synthetic_row.get(metric_key, 0) or 0)
        deepseek_count = int(deepseek_row.get(metric_key, 0) or 0)
        delta = deepseek_count - synthetic_count
        output.append(
            {
                label_key: label,
                "synthetic_reference_count": synthetic_count,
                "deepseek_prediction_count": deepseek_count,
                "absolute_delta": delta,
                "percentage_delta": round(delta / total * 100, 2) if total else 0.0,
                "synthetic_rate": synthetic_row.get(rate_key, 0),
                "deepseek_rate": deepseek_row.get(rate_key, 0),
            }
        )
    return sorted(output, key=lambda row: (-abs(row["absolute_delta"]), str(row[label_key])))


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def write_comparison_report(comparison: dict[str, Any]) -> None:
    lines = [
        "# I-5D Synthetic Reference vs DeepSeek Prediction Dashboard Comparison v1",
        "",
        "## Purpose",
        "",
        (
            "This report compares Synthetic Reference Statistics and DeepSeek Prediction Statistics for the 400-row full pool. "
            "It does not compute formal accuracy."
        ),
        "",
        "## Data Mode Boundary",
        "",
        "- Synthetic Reference Statistics = data design / dashboard reference / auto labels.",
        "- DeepSeek Prediction Statistics = real model output / dashboard statistics.",
        "- Formal Reviewed Golden Evaluation = 80-case reviewed test set / formal accuracy.",
        "",
        "## Key Distribution Differences",
        "",
        "### Sentiment",
        "",
    ]
    for section_key, title, label_key in [
        ("sentiment", "Sentiment", "sentiment"),
        ("urgency", "Urgency", "urgency"),
        ("complaint_reason", "Complaint Reason", "complaint_reason"),
        ("source_attribution", "Source Attribution", "source_attribution"),
    ]:
        lines.extend([f"### {title}", ""])
        rows = comparison["distribution_comparisons"][section_key]
        lines.extend(
            markdown_table(
                [label_key, "Synthetic", "DeepSeek", "Delta"],
                [[str(row[label_key]), str(row["synthetic_reference_count"]), str(row["deepseek_prediction_count"]), str(row["absolute_delta"])] for row in rows],
            )
        )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            (
                "Differences are expected because the synthetic reference source uses auto labels from the dataset design, "
                "whereas the DeepSeek prediction source reflects real model output. The comparison supports dashboard and "
                "discussion evidence, not formal accuracy."
            ),
            "",
            "## Formal Boundary",
            "",
            "Formal accuracy remains 88.21% on the 80-case reviewed golden test set. The 400-row full pool is not formal accuracy.",
        ]
    )
    COMPARISON_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_screenshot_plan() -> None:
    lines = [
        "# I-5D Dashboard Screenshot and Figure Plan v1",
        "",
        "## Screenshot Checklist",
        "",
        "1. Dashboard mode selector.",
        "2. Synthetic Reference Statistics overview.",
        "3. DeepSeek Prediction Statistics overview.",
        "4. DeepSeek Prediction sentiment / urgency distributions.",
        "5. DeepSeek Prediction store complaint ranking.",
        "6. DeepSeek Prediction product negative sentiment ranking.",
        "7. DeepSeek Prediction complaint reason distribution.",
        "8. DeepSeek Prediction source attribution distribution.",
        "9. Formal Reviewed Golden Evaluation mode.",
        "10. Formal accuracy 88.21% visible.",
        "11. 400-row prediction dashboard is not formal accuracy warning.",
        "12. product_category normalization caveat.",
        "",
        "## Recommended Figure Captions",
        "",
        "| Figure | English Caption | Chinese Caption |",
        "|---|---|---|",
        "| Dashboard modes | Streamlit dashboard showing three separated data modes for reference statistics, DeepSeek predictions, and formal evaluation. | Streamlit 仪表盘展示三种数据模式：参考统计、DeepSeek 预测统计和正式评估。 |",
        "| DeepSeek prediction overview | Dashboard overview of 400-row DeepSeek prediction statistics for system-level batch output. | 400 条 DeepSeek 预测结果的系统级批处理统计概览。 |",
        "| Formal evaluation summary | Formal reviewed golden test set evaluation summary with 88.21% field-level accuracy. | 人工复核 golden test set 的正式评估摘要，字段级准确率为 88.21%。 |",
        "| Product category caveat | Product category normalization caveat shown as a known taxonomy-alignment limitation. | product_category 标准化问题作为已知分类体系对齐限制展示。 |",
        "",
        "## Dissertation Usage",
        "",
        "- System interface chapter: use dashboard mode selector and overview screenshots.",
        "- Evaluation chapter: use Formal Reviewed Golden Evaluation screenshot and 88.21% metric.",
        "- Results and discussion chapter: use synthetic-vs-DeepSeek comparison screenshots and product_category caveat.",
    ]
    SCREENSHOT_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_PLAN_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_consolidated_report(comparison: dict[str, Any]) -> None:
    i4g = comparison["i4g_summary"]
    i4e4 = comparison.get("i4e4_summary", {})
    product_original = i4e4.get("original_metrics", {}).get("field_accuracy", {}).get("product_category", 0.5)
    product_normalized = i4e4.get("post_normalized_metrics", {}).get("field_accuracy", {}).get("product_category", 0.775)
    lines = [
        "# I-5D Full API and Dashboard Evidence Report v1",
        "",
        "## 1. Purpose of I-5D",
        "",
        "I-5D packages the accepted 400-row DeepSeek batch result and dashboard evidence for dissertation reporting.",
        "",
        "## 2. Current System Status",
        "",
        "The system now has a formal reviewed evaluation result, synthetic reference dashboard statistics, real DeepSeek prediction dashboard statistics, and a Streamlit dashboard with three data modes.",
        "",
        "## 3. I-4G 400-row DeepSeek Batch Result",
        "",
        f"- Backend: {i4g.get('backend_used')}",
        f"- API attempted: {i4g.get('api_attempted_count')}",
        f"- API errors: {i4g.get('api_error_count')}",
        f"- Parse success: {i4g.get('parse_success_count')}",
        f"- Schema validation success: {i4g.get('schema_validation_success_count')}",
        f"- Failed cases: {i4g.get('failed_count')}",
        f"- Runtime seconds: {i4g.get('runtime_seconds')}",
        "",
        "## 4. I-5C DeepSeek Prediction Dashboard Status",
        "",
        "DeepSeek prediction dashboard statistics were generated from the accepted 400-row model prediction file.",
        "",
        "## 5. Comparison Among Three Data Modes",
        "",
        "- Synthetic Reference Statistics: 400-row auto-label reference statistics for dataset design and dashboard coverage.",
        "- DeepSeek Prediction Statistics: 400-row real model-output statistics for batch-processing and dashboard demonstration.",
        "- Formal Reviewed Golden Evaluation: 80-case manually reviewed golden test set used for formal accuracy.",
        "",
        "## 6. Synthetic vs DeepSeek Distribution Comparison Summary",
        "",
        "The comparison files quantify count deltas for sentiment, urgency, complaint reason, source attribution, product ranking, and store ranking.",
        "",
        "## 7. Formal Evaluation Boundary",
        "",
        "Formal accuracy comes from the 80-case reviewed golden test set: 88.21% field accuracy. The 400-row full pool is not formal accuracy.",
        "",
        "## 8. Product_category Normalization Caveat",
        "",
        (
            f"I-4E.4 showed original product_category accuracy {product_original * 100:.2f}% and "
            f"post-normalized product_category accuracy {product_normalized * 100:.2f}%. No active patch was applied."
        ),
        "",
        "## 9. Dissertation Usage",
        "",
        "Use I-5D outputs for the system interface, evaluation, and results/discussion chapters.",
        "",
        "## 10. Recommended Next Stage",
        "",
        "Capture Streamlit screenshots, finalize the evidence package, then decide whether to polish the UI or add a FastAPI service layer.",
    ]
    CONSOLIDATED_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    synthetic = read_json(SYNTHETIC_DASHBOARD_PATH)
    deepseek = read_json(DEEPSEEK_DASHBOARD_PATH)
    i4g = read_json(I4G_SUMMARY_PATH)
    i4e2 = read_json(I4E2_SUMMARY_PATH)
    i4e3 = read_json(I4E3_SUMMARY_PATH)
    i4e4 = read_json(I4E4_SUMMARY_PATH) if I4E4_SUMMARY_PATH.exists() else {}
    i5d_api = read_json(I5D_API_SUMMARY_PATH) if I5D_API_SUMMARY_PATH.exists() else {}

    comparisons = {
        "sentiment": compare_distribution(synthetic["sentiment_distribution"], deepseek["sentiment_distribution"], "sentiment"),
        "urgency": compare_distribution(synthetic["urgency_distribution"], deepseek["urgency_distribution"], "urgency"),
        "complaint_reason": compare_distribution(synthetic["complaint_reason_distribution"], deepseek["complaint_reason_distribution"], "complaint_reason"),
        "source_attribution": compare_distribution(synthetic["source_attribution_distribution"], deepseek["source_attribution_distribution"], "source_attribution"),
    }
    product_comparison = compare_ranking(
        synthetic["product_negative_sentiment_ranking"],
        deepseek["product_negative_sentiment_ranking"],
        "product_category",
        "negative_count",
        "negative_rate",
    )
    store_comparison = compare_ranking(
        synthetic["store_complaint_ranking"],
        deepseek["store_complaint_ranking"],
        "store_location",
        "complaint_count",
        "complaint_rate",
    )

    write_csv(SENTIMENT_CSV_PATH, comparisons["sentiment"], ["sentiment", "synthetic_reference_count", "deepseek_prediction_count", "absolute_delta", "percentage_delta"])
    write_csv(URGENCY_CSV_PATH, comparisons["urgency"], ["urgency", "synthetic_reference_count", "deepseek_prediction_count", "absolute_delta", "percentage_delta"])
    write_csv(REASON_CSV_PATH, comparisons["complaint_reason"], ["complaint_reason", "synthetic_reference_count", "deepseek_prediction_count", "absolute_delta", "percentage_delta"])
    write_csv(SOURCE_CSV_PATH, comparisons["source_attribution"], ["source_attribution", "synthetic_reference_count", "deepseek_prediction_count", "absolute_delta", "percentage_delta"])
    write_csv(PRODUCT_CSV_PATH, product_comparison, ["product_category", "synthetic_reference_count", "deepseek_prediction_count", "absolute_delta", "percentage_delta", "synthetic_rate", "deepseek_rate"])
    write_csv(STORE_CSV_PATH, store_comparison, ["store_location", "synthetic_reference_count", "deepseek_prediction_count", "absolute_delta", "percentage_delta", "synthetic_rate", "deepseek_rate"])

    comparison_summary = {
        "stage": "I-5D",
        "synthetic_reference_dashboard_file": str(SYNTHETIC_DASHBOARD_PATH),
        "deepseek_prediction_dashboard_file": str(DEEPSEEK_DASHBOARD_PATH),
        "i4g_summary": i4g,
        "formal_evaluation_reference": {
            "source": "I-4E.2 80-case reviewed golden test set",
            "overall_field_accuracy": i4e2.get("overall_field_accuracy", i4e3.get("overall_field_accuracy", 0.8821)),
            "total_cases": i4e2.get("total_cases", 80),
        },
        "data_mode_definitions": {
            "Synthetic Reference Statistics": "data design / dashboard reference / auto labels",
            "DeepSeek Prediction Statistics": "real model output / dashboard statistics",
            "Formal Reviewed Golden Evaluation": "80-case reviewed test set / formal accuracy",
        },
        "distribution_comparisons": comparisons,
        "product_ranking_comparison": product_comparison,
        "store_ranking_comparison": store_comparison,
        "i4e4_summary": i4e4,
        "i5d_api_result_summary": i5d_api,
        "warning": "400-row full pool dashboard statistics and DeepSeek prediction statistics are not formal accuracy. Formal accuracy remains 88.21% on the 80-case reviewed golden test set.",
    }
    COMPARISON_JSON_PATH.write_text(json.dumps(comparison_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_comparison_report(comparison_summary)
    write_screenshot_plan()
    write_consolidated_report(comparison_summary)

    print("I-5D synthetic-vs-DeepSeek dashboard comparison completed.")
    print(f"Comparison JSON: {COMPARISON_JSON_PATH}")
    print(f"Comparison report: {COMPARISON_REPORT_PATH}")
    print(f"Screenshot plan: {SCREENSHOT_PLAN_PATH}")
    print(f"Consolidated report: {CONSOLIDATED_REPORT_PATH}")


if __name__ == "__main__":
    main()
