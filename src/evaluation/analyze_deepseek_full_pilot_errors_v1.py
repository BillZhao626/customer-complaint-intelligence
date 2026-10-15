from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


PREDICTION_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_predictions_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_pilot_v1.csv"

ERROR_ANALYSIS_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_error_analysis_v1.csv"
REPORT_PATH = PROJECT_ROOT / "outputs" / "deepseek_full_pilot_error_analysis_report_v1.md"
MANUAL_REVIEW_SAMPLE_PATH = PROJECT_ROOT / "data" / "golden" / "deepseek_full_pilot_manual_review_sample_v1.csv"

FIELD_PAIRS = {
    "sentiment": "sentiment_label",
    "urgency": "urgency_label",
    "is_complaint": "is_complaint_label",
    "store_location": "store_location_label",
    "product_category": "product_category_label",
    "complaint_reason": "complaint_reason_label",
    "source_attribution": "source_attribution_label",
}

REVIEW_PRIORITY = {
    "source_attribution": 0,
    "store_location": 1,
    "urgency": 2,
    "complaint_reason": 3,
    "product_category": 4,
    "sentiment": 5,
    "is_complaint": 6,
}


def _normalize(value: object) -> str:
    return str(value or "").strip().lower()


def _compact_label(value: object) -> str:
    text = _normalize(value)
    for token in [" store", " issue", " response", " process", "/", "-", "_"]:
        text = text.replace(token, " ")
    return " ".join(text.split())


def _md_cell(value: object, max_len: int = 300) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "\\|")
    return text[:max_len]


def _is_store_format_mismatch(prediction: str, golden_label: str) -> bool:
    pred = _compact_label(prediction)
    gold = _compact_label(golden_label)
    if not pred or not gold:
        return False
    return pred in gold or gold in pred


def _is_semantic_equivalent(field: str, prediction: str, golden_label: str) -> bool:
    pred = _compact_label(prediction)
    gold = _compact_label(golden_label)
    if pred == gold:
        return True
    if field == "complaint_reason":
        close_pairs = {
            ("after sales service", "customer service"),
            ("refund request", "after sales service"),
            ("refund request", "customer service"),
            ("product quality", "health or safety"),
            ("other", "none"),
        }
        return (pred, gold) in close_pairs or (gold, pred) in close_pairs
    if field == "source_attribution":
        close_pairs = {
            ("store service", "customer service"),
            ("refund exchange", "customer service"),
            ("refund exchange", "store service"),
            ("product", "unclear"),
        }
        return any(a in pred and b in gold or b in pred and a in gold for a, b in close_pairs)
    return False


def classify_mismatch(field: str, prediction: object, golden_label: object) -> tuple[str, str, str]:
    pred = _normalize(prediction)
    gold = _normalize(golden_label)

    if field == "store_location":
        if _is_store_format_mismatch(pred, gold):
            return (
                "store_location_format_issue",
                "The predicted store location is a partial or differently formatted version of the golden label.",
                "Consider output normalization for store names before exact-match evaluation.",
            )
        return (
            "normalization_needed",
            "The store location mismatch may need normalization or manual checking.",
            "Review whether city-only, branch-only, or casing differences should be normalized.",
        )

    if field == "source_attribution":
        service_terms = ["customer service", "refund", "exchange", "store service", "after-sales", "after sales"]
        if any(term in pred or term in gold for term in service_terms):
            return (
                "source_attribution_boundary",
                "The mismatch is near the boundary between service, store, and refund/exchange attribution.",
                "Clarify the source attribution taxonomy and add examples in the prompt or label guide.",
            )
        if _is_semantic_equivalent(field, pred, gold):
            return (
                "acceptable_semantic_equivalent",
                "The two source attribution labels are semantically close but not exact string matches.",
                "Review whether these labels should be merged, normalized, or kept distinct.",
            )
        return (
            "needs_manual_review",
            "The source attribution mismatch does not match a simple heuristic pattern.",
            "Manually inspect the email and decide whether the prediction or golden label is more appropriate.",
        )

    if field == "urgency":
        if {pred, gold} == {"medium", "high"}:
            return (
                "urgency_threshold_issue",
                "The mismatch is between medium and high urgency, which depends on threshold interpretation.",
                "Define clearer urgency thresholds for health, safety, refund, and no-response cases.",
            )
        return (
            "model_error",
            "The urgency label differs outside the common medium/high boundary case.",
            "Review the prompt examples and golden label consistency for urgency.",
        )

    if field == "complaint_reason":
        taxonomy_terms = ["customer service", "after-sales", "after sales", "refund", "exchange", "other"]
        if any(term in pred or term in gold for term in taxonomy_terms):
            return (
                "taxonomy_ambiguity",
                "The complaint reason mismatch is likely caused by overlap between service, after-sales, and refund labels.",
                "Clarify the complaint_reason taxonomy and add representative examples.",
            )
        if _is_semantic_equivalent(field, pred, gold):
            return (
                "acceptable_semantic_equivalent",
                "The complaint reason labels are semantically close but fail exact-match evaluation.",
                "Consider label normalization or manual golden label review.",
            )
        return (
            "needs_manual_review",
            "The complaint reason mismatch needs manual inspection.",
            "Review whether this is a model error or a golden label boundary issue.",
        )

    if field == "product_category":
        if pred in gold or gold in pred:
            return (
                "normalization_needed",
                "The product category appears close but differs in exact label format.",
                "Consider category normalization before scoring.",
            )
        return (
            "model_error",
            "The product category prediction does not match the golden label.",
            "Review product-category examples in the prompt or dataset notes.",
        )

    if field == "sentiment":
        return (
            "golden_label_too_strict" if {pred, gold} == {"positive", "neutral"} else "model_error",
            "The sentiment mismatch may reflect ambiguity in praise, inquiry, or mixed-feedback wording.",
            "Manually review ambiguous sentiment cases before changing the prompt.",
        )

    if field == "is_complaint":
        return (
            "model_error",
            "The complaint flag differs from the golden label.",
            "Check whether the email contains an explicit complaint, request, or only neutral/positive feedback.",
        )

    return (
        "needs_manual_review",
        "The mismatch does not match a known heuristic category.",
        "Manually review this case.",
    )


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in [PREDICTION_PATH, GOLDEN_PATH, DATASET_PATH]:
        if not path.exists():
            raise FileNotFoundError(f"Required input file not found: {path}")
    return pd.read_csv(PREDICTION_PATH), pd.read_csv(GOLDEN_PATH), pd.read_csv(DATASET_PATH)


def build_joined_frame(predictions_df: pd.DataFrame, golden_df: pd.DataFrame, dataset_df: pd.DataFrame) -> pd.DataFrame:
    dataset_context = dataset_df[["email_id", "email_subject", "email_body"]].copy()
    joined = predictions_df.merge(golden_df, on="email_id", how="inner")
    joined = joined.merge(dataset_context, on="email_id", how="left")
    return joined


def build_mismatch_rows(joined_df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in joined_df.iterrows():
        for field, golden_field in FIELD_PAIRS.items():
            prediction = row.get(field, "")
            golden_label = row.get(golden_field, "")
            if _normalize(prediction) == _normalize(golden_label):
                continue
            error_category, diagnosis_note, recommended_action = classify_mismatch(field, prediction, golden_label)
            rows.append(
                {
                    "email_id": row.get("email_id", ""),
                    "field": field,
                    "prediction": prediction,
                    "golden_label": golden_label,
                    "email_subject": row.get("email_subject", ""),
                    "email_body": row.get("email_body", ""),
                    "predicted_summary": row.get("summary", ""),
                    "predicted_reply": row.get("suggested_reply", ""),
                    "error_category": error_category,
                    "diagnosis_note": diagnosis_note,
                    "recommended_action": recommended_action,
                }
            )
    return rows


def select_manual_review_sample(mismatch_df: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    if mismatch_df.empty:
        sample = mismatch_df.copy()
        sample["human_decision"] = ""
        sample["human_review_notes"] = ""
        return sample

    work_df = mismatch_df.copy()
    email_mismatch_counts = work_df.groupby("email_id")["field"].transform("count")
    work_df["_email_mismatch_count"] = email_mismatch_counts
    work_df["_field_priority"] = work_df["field"].map(REVIEW_PRIORITY).fillna(99)
    work_df["_category_priority"] = work_df["error_category"].map(
        {
            "source_attribution_boundary": 0,
            "store_location_format_issue": 1,
            "urgency_threshold_issue": 2,
            "taxonomy_ambiguity": 3,
            "normalization_needed": 4,
        }
    ).fillna(9)
    work_df = work_df.sort_values(
        by=["_email_mismatch_count", "_field_priority", "_category_priority", "email_id"],
        ascending=[False, True, True, True],
    )
    sample = work_df.head(limit).drop(columns=["_email_mismatch_count", "_field_priority", "_category_priority"])
    sample["human_decision"] = ""
    sample["human_review_notes"] = ""
    return sample


def representative_examples(mismatch_df: pd.DataFrame, field: str, limit: int = 3) -> list[dict[str, object]]:
    examples_df = mismatch_df[mismatch_df["field"] == field].head(limit)
    return examples_df.to_dict(orient="records")


def write_report(joined_df: pd.DataFrame, mismatch_df: pd.DataFrame) -> None:
    total_cases = len(joined_df)
    total_comparisons = total_cases * len(FIELD_PAIRS)
    field_counts = Counter(mismatch_df["field"]) if not mismatch_df.empty else Counter()
    category_counts = Counter(mismatch_df["error_category"]) if not mismatch_df.empty else Counter()
    top_fields = field_counts.most_common()

    lines = [
        "# DeepSeek Full Pilot Error Analysis Report v1",
        "",
        "- Stage name: I-3.2 DeepSeek 50-case Error Analysis",
        f"- Prediction file: `{PREDICTION_PATH}`",
        f"- Golden label file: `{GOLDEN_PATH}`",
        f"- Pilot dataset file: `{DATASET_PATH}`",
        f"- Error analysis CSV: `{ERROR_ANALYSIS_PATH}`",
        f"- Manual review sample: `{MANUAL_REVIEW_SAMPLE_PATH}`",
        f"- Total cases: {total_cases}",
        f"- Total field-level comparisons: {total_comparisons}",
        f"- Total mismatches: {len(mismatch_df)}",
        "",
        "## Mismatch Count By Field",
        "",
        "| Field | Mismatches |",
        "|---|---:|",
    ]
    for field in FIELD_PAIRS:
        lines.append(f"| {field} | {field_counts.get(field, 0)} |")

    lines.extend(["", "## Mismatch Count By Error Category", "", "| Error category | Mismatches |", "|---|---:|"])
    for category, count in category_counts.most_common():
        lines.append(f"| {category} | {count} |")

    lines.extend(["", "## Top Problematic Fields", ""])
    if top_fields:
        for field, count in top_fields:
            lines.append(f"- `{field}`: {count} mismatches")
    else:
        lines.append("No mismatches found.")

    lines.extend(["", "## Representative Examples", ""])
    for field in ["source_attribution", "store_location", "urgency", "complaint_reason"]:
        lines.extend([f"### {field}", ""])
        examples = representative_examples(mismatch_df, field)
        if not examples:
            lines.append("No mismatch examples for this field.")
            lines.append("")
            continue
        lines.extend(["| Email ID | Prediction | Golden label | Error category | Diagnosis |", "|---|---|---|---|---|"])
        for item in examples:
            lines.append(
                "| {email_id} | {prediction} | {golden_label} | {error_category} | {diagnosis_note} |".format(
                    email_id=_md_cell(item.get("email_id")),
                    prediction=_md_cell(item.get("prediction")),
                    golden_label=_md_cell(item.get("golden_label")),
                    error_category=_md_cell(item.get("error_category")),
                    diagnosis_note=_md_cell(item.get("diagnosis_note")),
                )
            )
        lines.append("")

    source_boundary = category_counts.get("source_attribution_boundary", 0)
    normalization = category_counts.get("normalization_needed", 0) + category_counts.get("store_location_format_issue", 0)
    taxonomy = category_counts.get("taxonomy_ambiguity", 0)
    model_error = category_counts.get("model_error", 0)
    interpretation = (
        "The mismatch set should be interpreted before any prompt change. "
        "A large share of source attribution, taxonomy, and normalization categories suggests that exact-match scoring may be "
        "over-counting some boundary or formatting issues. Model errors should still be reviewed, but the next change should be "
        "guided by manual review rather than score-chasing."
    )
    lines.extend(
        [
            "## Interpretation",
            "",
            interpretation,
            "",
            f"- Source attribution boundary cases: {source_boundary}",
            f"- Normalization or store-format cases: {normalization}",
            f"- Complaint taxonomy ambiguity cases: {taxonomy}",
            f"- Initial model-error cases: {model_error}",
            "",
            "## Recommended Next Step",
            "",
            "- Review `data/golden/deepseek_full_pilot_manual_review_sample_v1.csv` manually.",
            "- Decide which mismatches are true model errors, acceptable semantic equivalents, label-boundary issues, or normalization issues.",
            "- Refine the prompt only after manual review identifies repeated model behavior.",
            "- Add output normalization for store names if format-only mismatches are common.",
            "- Clarify the source attribution taxonomy before expanding to 300-500 synthetic emails.",
            "- Do not expand to 300-500 cases until the 50-case error categories are understood.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    predictions_df, golden_df, dataset_df = load_inputs()
    joined_df = build_joined_frame(predictions_df, golden_df, dataset_df)
    mismatch_rows = build_mismatch_rows(joined_df)
    mismatch_df = pd.DataFrame(mismatch_rows)

    ERROR_ANALYSIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_REVIEW_SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)

    mismatch_df.to_csv(ERROR_ANALYSIS_PATH, index=False)
    manual_review_sample_df = select_manual_review_sample(mismatch_df)
    manual_review_sample_df.to_csv(MANUAL_REVIEW_SAMPLE_PATH, index=False)
    write_report(joined_df, mismatch_df)

    field_counts = Counter(mismatch_df["field"]) if not mismatch_df.empty else Counter()
    category_counts = Counter(mismatch_df["error_category"]) if not mismatch_df.empty else Counter()

    print("DeepSeek full pilot error analysis completed.")
    print(f"Rows joined: {len(joined_df)}")
    print(f"Total field-level comparisons: {len(joined_df) * len(FIELD_PAIRS)}")
    print(f"Total mismatches: {len(mismatch_df)}")
    print(f"Error analysis CSV saved to: {ERROR_ANALYSIS_PATH}")
    print(f"Report saved to: {REPORT_PATH}")
    print(f"Manual review sample saved to: {MANUAL_REVIEW_SAMPLE_PATH}")
    print("Mismatch count by field:")
    for field in FIELD_PAIRS:
        print(f"- {field}: {field_counts.get(field, 0)}")
    print("Mismatch count by error category:")
    for category, count in category_counts.most_common():
        print(f"- {category}: {count}")


if __name__ == "__main__":
    main()
