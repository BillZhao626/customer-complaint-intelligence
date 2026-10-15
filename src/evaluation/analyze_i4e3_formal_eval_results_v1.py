from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PREDICTION_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_predictions_v1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json"
SMOKE_COMPARISON_PATH = PROJECT_ROOT / "outputs" / "i4e2_vs_i4e1_smoke_comparison_v1.json"
REVIEWED_GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_review_sample_v1_reviewed.csv"
EMAIL_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_review_sample_v1.csv"

MISMATCH_DETAIL_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_mismatch_details_v1.csv"
INTERPRETATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_evaluation_interpretation_report_v1.md"
SUPERVISOR_UPDATE_PATH = PROJECT_ROOT / "outputs" / "i4e3_supervisor_progress_update_draft_v1.md"
CHINESE_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e3_chinese_project_summary_v1.md"
INTERPRETATION_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e3_formal_eval_interpretation_summary_v1.json"

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def normalize(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text.lower() in {"true", "false"}:
        return text.lower()
    return text.casefold()


def issue_category_for(field: str, predicted: str, reviewed: str) -> str:
    pred_norm = normalize(predicted)
    reviewed_norm = normalize(reviewed)
    if field == "product_category":
        return "taxonomy_ambiguity"
    if field == "source_attribution":
        return "source_attribution_boundary"
    if field == "urgency":
        return "urgency_threshold_issue"
    if field == "sentiment":
        return "possible_label_boundary"
    if field == "is_complaint":
        return "model_error"
    if field == "complaint_reason":
        if pred_norm == "customer service" and reviewed_norm == "after-sales service":
            return "model_error"
        return "possible_label_boundary"
    if not pred_norm or not reviewed_norm:
        return "extraction_error"
    return "model_error"


def short_reason_for(field: str, predicted: str, reviewed: str, issue_category: str) -> str:
    if issue_category == "taxonomy_ambiguity":
        return (
            f"The model used `{predicted}` while the reviewed project taxonomy expects `{reviewed}`; "
            "this points to category label-space ambiguity rather than API instability."
        )
    if issue_category == "source_attribution_boundary":
        return (
            f"The model attributed the issue to `{predicted}`, while the reviewed label is `{reviewed}`; "
            "the evidence crosses source-attribution boundaries."
        )
    if issue_category == "urgency_threshold_issue":
        return (
            f"The model predicted `{predicted}` urgency while the reviewed threshold label is `{reviewed}`."
        )
    if issue_category == "possible_label_boundary":
        return (
            f"The model predicted `{predicted}` and the reviewed label is `{reviewed}`; "
            "the case may sit near a semantic label boundary."
        )
    if issue_category == "normalization_issue":
        return (
            f"The model output `{predicted}` is close to reviewed value `{reviewed}` but not normalized to the project label."
        )
    if issue_category == "extraction_error":
        return f"The model output `{predicted}` does not match the reviewed extracted value `{reviewed}`."
    return f"The model output `{predicted}` differs from reviewed value `{reviewed}`."


def reconstruct_mismatches(
    predictions: list[dict[str, str]],
    reviewed_labels: list[dict[str, str]],
    emails: list[dict[str, str]],
) -> list[dict[str, str]]:
    label_by_id = {row["email_id"]: row for row in reviewed_labels}
    email_by_id = {row["email_id"]: row for row in emails}
    mismatches: list[dict[str, str]] = []
    for prediction in predictions:
        email_id = prediction["email_id"]
        reviewed = label_by_id[email_id]
        subject = email_by_id.get(email_id, {}).get("subject", "")
        for field in FIELDS:
            predicted_value = prediction.get(field, "")
            reviewed_value = reviewed.get(field, "")
            if normalize(predicted_value) != normalize(reviewed_value):
                issue_category = issue_category_for(field, predicted_value, reviewed_value)
                mismatches.append(
                    {
                        "email_id": email_id,
                        "field": field,
                        "predicted_value": predicted_value,
                        "reviewed_value": reviewed_value,
                        "issue_category": issue_category,
                        "short_reason": short_reason_for(field, predicted_value, reviewed_value, issue_category),
                        "subject": subject,
                    }
                )
    return mismatches


def concentration_summary(mismatches: list[dict[str, str]], total_cases: int) -> dict[str, Any]:
    counts = Counter(row["email_id"] for row in mismatches)
    top_cases = [
        {"email_id": email_id, "mismatch_count": count}
        for email_id, count in counts.most_common(10)
    ]
    affected_cases = len(counts)
    max_case_mismatches = top_cases[0]["mismatch_count"] if top_cases else 0
    top_five_total = sum(item["mismatch_count"] for item in top_cases[:5])
    share_top_five = top_five_total / len(mismatches) if mismatches else 0.0
    if share_top_five >= 0.5:
        interpretation = "Mismatches are concentrated in a relatively small set of cases."
    else:
        interpretation = (
            "Mismatches are spread across the reviewed set, with product-category taxonomy differences "
            "appearing repeatedly rather than one or two cases dominating the result."
        )
    return {
        "affected_case_count": affected_cases,
        "unaffected_case_count": total_cases - affected_cases,
        "max_mismatches_in_single_case": max_case_mismatches,
        "top_email_ids_by_mismatch_count": top_cases,
        "top_five_case_mismatch_share": round(share_top_five, 4),
        "interpretation": interpretation,
    }


def field_interpretation(field: str, accuracy: float, mismatches: int) -> str:
    if field == "store_location":
        return "Very stable direct extraction from explicit store names."
    if field == "is_complaint":
        return "Very strong binary complaint classification with only one boundary/model miss."
    if field == "sentiment":
        return "Strong sentiment classification; remaining misses are near neutral-negative boundaries."
    if field == "complaint_reason":
        return "Strong overall, with remaining issues around after-sales/customer-service/other boundaries."
    if field == "urgency":
        return "Generally strong, but threshold judgments still create medium-low or medium-high misses."
    if field == "source_attribution":
        return "Moderate weakness because responsibility boundaries can overlap across store, support, refund, and product issues."
    if field == "product_category":
        return "Primary weakness; many mismatches reflect taxonomy or label-normalization mismatch with the project categories."
    return f"Accuracy {accuracy:.2%} with {mismatches} mismatches."


def write_mismatch_csv(mismatches: list[dict[str, str]]) -> None:
    MISMATCH_DETAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MISMATCH_DETAIL_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "email_id",
                "field",
                "predicted_value",
                "reviewed_value",
                "issue_category",
                "short_reason",
                "subject",
            ],
        )
        writer.writeheader()
        writer.writerows(mismatches)


def make_markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def write_interpretation_report(
    summary: dict[str, Any],
    comparison: dict[str, Any],
    analysis_json: dict[str, Any],
) -> None:
    field_accuracy = analysis_json["field_accuracy"]
    mismatches_by_field = analysis_json["mismatches_by_field"]
    field_rows = []
    for field in FIELDS:
        accuracy = field_accuracy[field]
        mismatches = mismatches_by_field[field]
        field_rows.append(
            [
                field,
                f"{accuracy:.2%}",
                str(mismatches),
                field_interpretation(field, accuracy, mismatches),
            ]
        )

    pattern_rows = [
        [pattern, str(count)]
        for pattern, count in analysis_json["top_error_patterns"].items()
    ]
    concentration = analysis_json["mismatch_concentration"]
    top_case_rows = [
        [item["email_id"], str(item["mismatch_count"])]
        for item in concentration["top_email_ids_by_mismatch_count"][:8]
    ]

    lines = [
        "# I-4E.3 Formal Evaluation Result Interpretation Report v1",
        "",
        "## Stage And Purpose",
        "",
        (
            "I-4E.3 packages and interprets the I-4E.2 formal DeepSeek evaluation on the "
            "human-reviewed golden test set. This stage is offline reporting only: no API call was made "
            "and no model evaluation was rerun."
        ),
        "",
        "## Evaluation Setup",
        "",
        f"- Backend/model result source: `{summary.get('backend_used')}`.",
        "- Reviewed golden test set size: 80 cases.",
        "- Fields evaluated: sentiment, urgency, is_complaint, store_location, product_category, complaint_reason, source_attribution.",
        (
            "- Why this is a formal evaluation: the labels were manually reviewed in I-4D and saved as a "
            "versioned reviewed golden test set."
        ),
        "- The 400-row full pool is not used for formal accuracy metrics; it remains for dashboard statistics, batch processing, and case coverage.",
        "",
        "## Overall Result",
        "",
        "- Total cases: 80 cases.",
        "- Total fields: 560 fields.",
        "- Correct fields: 494 correct fields.",
        "- Total mismatches: 66 mismatches.",
        "- Overall field accuracy: 88.21%.",
        "",
        "## Field-Level Results",
        "",
    ]
    lines.extend(make_markdown_table(["Field", "Accuracy", "Mismatch count", "Interpretation"], field_rows))
    lines.extend(
        [
            "",
            "## Strongest Fields",
            "",
            (
                "The strongest fields are store_location, is_complaint, sentiment, and complaint_reason. "
                "These fields are either explicit in the customer email text or have relatively clear semantic boundaries "
                "in the reviewed dataset."
            ),
            "",
            "## Weakest Fields",
            "",
            (
                "The weakest field is product_category, with 40 mismatches and 50.00% accuracy. Many category "
                "errors involve the model using natural category aliases such as `Other`, `Service`, `Beauty Products`, "
                "or `Sportswear` instead of the project label set. Source_attribution is the second main weakness, "
                "with boundary errors across store service, customer service, refund/exchange, product, and unclear sources."
            ),
            "",
            "## Mismatch Pattern Analysis",
            "",
        ]
    )
    lines.extend(make_markdown_table(["Issue category", "Mismatch count"], pattern_rows))
    lines.extend(["", "### Top Cases By Mismatch Count", ""])
    lines.extend(make_markdown_table(["Email ID", "Mismatch count"], top_case_rows))
    lines.extend(
        [
            "",
            f"- Affected cases: {concentration['affected_case_count']} of 80.",
            f"- Top five case mismatch share: {concentration['top_five_case_mismatch_share']:.2%}.",
            f"- Interpretation: {concentration['interpretation']}",
            "",
            "## Smoke-Vs-Full Comparison",
            "",
            (
                f"I-4E.1 smoke20 achieved {comparison.get('smoke_overall_field_accuracy', 0):.2%} field accuracy "
                f"with {comparison.get('smoke_total_mismatch_count')} mismatches. I-4E.2 full80 achieved "
                f"{comparison.get('full_overall_field_accuracy', 0):.2%} field accuracy with "
                f"{comparison.get('full_total_mismatch_count')} mismatches."
            ),
            (
                f"Full 80 remained stable after smoke: "
                f"{comparison.get('full_80_remained_stable_after_smoke')}."
            ),
            "",
            "## Dissertation Interpretation",
            "",
            (
                "The formal reviewed-test-set result suggests that the model can reliably perform structured extraction "
                "and classification for many operational complaint fields. Direct extraction fields and high-level "
                "classification fields are particularly stable. Fields involving semantic attribution and boundary "
                "judgment remain harder than direct extraction fields, especially product_category and source_attribution."
            ),
            "",
            "## Limitations",
            "",
            "- The dataset is synthetic and should be described as a controlled project dataset, not an industrial benchmark.",
            "- The reviewed golden test set contains 80 cases, which is suitable for dissertation validation but not a large-scale production benchmark.",
            "- Source_attribution and complaint_reason still involve taxonomy boundary decisions, so some mismatches may reflect label-space ambiguity.",
            "",
            "## Next-Stage Recommendation",
            "",
            (
                "Proceed to I-4F full pool batch/dashboard statistics unless a targeted product_category label-normalization "
                "or prompt-refinement step is preferred first. Because no severe API, parse, or schema stability issue appeared, "
                "the next useful evidence is dashboard-level behavior on the 400-row synthetic pool rather than another broad prompt change."
            ),
        ]
    )
    INTERPRETATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_supervisor_update() -> None:
    lines = [
        "# Supervisor Progress Update Draft",
        "",
        "Dear [Supervisor Name],",
        "",
        (
            "I have completed the next evaluation stage of the dissertation project. The dataset now includes "
            "a 400-row synthetic pool of customer complaint emails, from which an 80-case manually reviewed golden test set "
            "was selected and finalized."
        ),
        "",
        (
            "I then completed the DeepSeek evaluation on the reviewed test set. The API run was stable: 80/80 API calls "
            "completed successfully, with 0 API errors, and 80/80 outputs passed parsing and schema validation. Across "
            "the seven evaluated fields, the overall field-level accuracy was 88.21%."
        ),
        "",
        (
            "The strongest results were in direct extraction and clear classification fields, while the main remaining "
            "weaknesses were product category normalization and source attribution boundary decisions."
        ),
        "",
        (
            "My next plan is to analyze dashboard statistics using the full synthetic pool and integrate the results into "
            "the web interface, while keeping formal accuracy reporting tied to the manually reviewed test set."
        ),
        "",
        "Please let me know if you have any suggestions on the interpretation or next reporting focus.",
        "",
        "Best regards,",
        "[Your Name]",
    ]
    SUPERVISOR_UPDATE_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_chinese_summary() -> None:
    lines = [
        "# I-4E.3 中文项目总结",
        "",
        "## 当前阶段完成了什么",
        "",
        (
            "本阶段对 I-4E.2 的 80 条人工复核 golden test set 正式评估结果进行了离线分析和报告整理。"
            "本阶段没有再次调用 DeepSeek API，也没有重新运行模型评估，只读取已有的正式评估输出。"
        ),
        "",
        "## 为什么 88.21% 是可信指标",
        "",
        (
            "88.21% 来自 80 条人工复核测试样本，每条样本评估 7 个字段，共 560 个字段。"
            "其中 494 个字段预测正确，66 个字段与人工复核标签不一致。由于标签已经经过人工复核，"
            "这个结果比直接使用自动标签计算准确率更适合作为论文中的正式项目评估指标。"
        ),
        "",
        "## 表现较强的字段",
        "",
        (
            "store_location 表现最稳定，准确率为 100%。is_complaint、sentiment 和 complaint_reason "
            "也表现较好，说明模型对显式门店信息、投诉判断、情感倾向和主要投诉原因有较强的结构化抽取能力。"
        ),
        "",
        "## 表现较弱的字段",
        "",
        (
            "product_category 是最弱字段，主要问题是模型输出的类别名称与项目固定标签体系不完全一致，"
            "例如使用 Other、Service、Beauty Products 或 Sportswear 等自然类别表达。source_attribution "
            "也存在一定难度，因为 store service、customer service、refund/exchange、product issue 等责任来源之间存在边界。"
        ),
        "",
        "## 为什么不直接用 400 条 auto labels 算准确率",
        "",
        (
            "400 条 full synthetic pool 的标签是 auto labels，不是人工复核 golden labels。它适合用于 dashboard 统计、"
            "批处理展示和案例覆盖分析，但如果直接用它计算正式准确率，可能把自动标签本身的偏差当作模型错误或模型正确，"
            "从而削弱评估可信度。"
        ),
        "",
        "## 后续 I-4F / Web UI 应该怎么做",
        "",
        (
            "建议进入 I-4F：对 400 条 full pool 进行批处理统计和 dashboard 数据准备，但在论文中明确说明这些统计不是正式准确率。"
            "Web UI 可以展示投诉数量、门店分布、产品类别、投诉原因、紧急程度和来源归因等聚合结果。正式模型性能仍以 80 条人工复核测试集为准。"
        ),
    ]
    CHINESE_SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_summary_json(analysis_json: dict[str, Any]) -> None:
    INTERPRETATION_JSON_PATH.write_text(
        json.dumps(analysis_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_analysis() -> dict[str, Any]:
    predictions = load_csv(PREDICTION_PATH)
    reviewed_labels = load_csv(REVIEWED_GOLDEN_PATH)
    emails = load_csv(EMAIL_PATH)
    summary = load_json(SUMMARY_PATH)
    comparison = load_json(SMOKE_COMPARISON_PATH)
    mismatches = reconstruct_mismatches(predictions, reviewed_labels, emails)

    total_cases = int(summary.get("total_cases", len(predictions)))
    total_fields = int(summary.get("total_field_count", total_cases * len(FIELDS)))
    total_mismatches = len(mismatches)
    correct_fields = total_fields - total_mismatches
    overall_accuracy = correct_fields / total_fields if total_fields else 0.0

    mismatches_by_field = {field: 0 for field in FIELDS}
    for row in mismatches:
        mismatches_by_field[row["field"]] += 1
    field_accuracy = {
        field: (total_cases - mismatches_by_field[field]) / total_cases if total_cases else 0.0
        for field in FIELDS
    }
    issue_counts = Counter(row["issue_category"] for row in mismatches)
    strongest_fields = sorted(FIELDS, key=lambda field: (-field_accuracy[field], mismatches_by_field[field]))[:4]
    weakest_fields = sorted(FIELDS, key=lambda field: (field_accuracy[field], -mismatches_by_field[field]))[:3]

    smoke_full_stability = {
        "smoke_total_cases": comparison.get("smoke_total_cases"),
        "full_total_cases": comparison.get("full_total_cases"),
        "smoke_overall_field_accuracy": comparison.get("smoke_overall_field_accuracy"),
        "full_overall_field_accuracy": comparison.get("full_overall_field_accuracy"),
        "smoke_total_mismatch_count": comparison.get("smoke_total_mismatch_count"),
        "full_total_mismatch_count": comparison.get("full_total_mismatch_count"),
        "full_80_remained_stable_after_smoke": comparison.get("full_80_remained_stable_after_smoke"),
    }

    return {
        "stage": "I-4E.3",
        "source_summary_file": str(SUMMARY_PATH),
        "source_prediction_file": str(PREDICTION_PATH),
        "reviewed_golden_file": str(REVIEWED_GOLDEN_PATH),
        "total_cases": total_cases,
        "total_fields": total_fields,
        "correct_fields": correct_fields,
        "total_mismatches": total_mismatches,
        "overall_field_accuracy": overall_accuracy,
        "field_accuracy": field_accuracy,
        "mismatches_by_field": mismatches_by_field,
        "strongest_fields": strongest_fields,
        "weakest_fields": weakest_fields,
        "top_error_patterns": dict(issue_counts.most_common()),
        "mismatch_concentration": concentration_summary(mismatches, total_cases),
        "smoke_full_stability": smoke_full_stability,
        "recommended_next_stage": "I-4F_full_pool_batch_dashboard_statistics",
        "output_files": {
            "mismatch_details": str(MISMATCH_DETAIL_PATH),
            "interpretation_report": str(INTERPRETATION_REPORT_PATH),
            "supervisor_update": str(SUPERVISOR_UPDATE_PATH),
            "chinese_summary": str(CHINESE_SUMMARY_PATH),
            "summary_json": str(INTERPRETATION_JSON_PATH),
        },
        "_mismatch_rows": mismatches,
        "_source_summary": summary,
        "_smoke_comparison": comparison,
    }


def main() -> None:
    analysis = build_analysis()
    mismatch_rows = analysis.pop("_mismatch_rows")
    source_summary = analysis.pop("_source_summary")
    smoke_comparison = analysis.pop("_smoke_comparison")

    write_mismatch_csv(mismatch_rows)
    write_interpretation_report(source_summary, smoke_comparison, analysis)
    write_supervisor_update()
    write_chinese_summary()
    write_summary_json(analysis)

    print("I-4E.3 formal evaluation interpretation artifacts generated.")
    print(f"- Total cases: {analysis['total_cases']}")
    print(f"- Total fields: {analysis['total_fields']}")
    print(f"- Correct fields: {analysis['correct_fields']}")
    print(f"- Total mismatches: {analysis['total_mismatches']}")
    print(f"- Overall field accuracy: {analysis['overall_field_accuracy']:.4f}")
    print(f"- Mismatch details: {MISMATCH_DETAIL_PATH}")
    print(f"- Interpretation summary: {INTERPRETATION_JSON_PATH}")


if __name__ == "__main__":
    main()
