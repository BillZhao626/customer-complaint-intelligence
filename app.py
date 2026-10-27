from __future__ import annotations

import json
import os
from uuid import uuid4
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# P3.11–P4 authorization: existing environment keys must not enable paid UI paths.
os.environ.update(COMPLAINT_ENABLE_LIVE='false', LLM_ENABLE_API='false',
                  LANGSMITH_TRACING='false', LANGCHAIN_TRACING='false', LANGCHAIN_TRACING_V2='false')

from src.chains.mock_complaint_chain import analyze_email
from src.dataset.generate_sample_dataset import generate_sample_files
from src.evaluation.evaluate_results import evaluate_predictions, LEGACY_LABEL_COLUMNS
from src.evaluation.core import validate_summary
from src.app.offline_slice import render_offline_slice
from src.app.csv_input import CSVInputError, read_csv_input


ROOT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = ROOT_DIR / "outputs"
GOLDEN_DIR = ROOT_DIR / "data" / "golden"
SYNTHETIC_DIR = ROOT_DIR / "data" / "synthetic"
DASHBOARD_I4F_DIR = OUTPUTS_DIR / "dashboard_i4f"
DASHBOARD_STATS_PATH = DASHBOARD_I4F_DIR / "dashboard_stats_v1.json"
STORE_COMPLAINT_RANKING_PATH = DASHBOARD_I4F_DIR / "store_complaint_ranking_v1.csv"
PRODUCT_NEGATIVE_RANKING_PATH = DASHBOARD_I4F_DIR / "product_negative_sentiment_ranking_v1.csv"
COMPLAINT_REASON_DISTRIBUTION_PATH = DASHBOARD_I4F_DIR / "complaint_reason_distribution_v1.csv"
SOURCE_ATTRIBUTION_DISTRIBUTION_PATH = DASHBOARD_I4F_DIR / "source_attribution_distribution_v1.csv"
URGENCY_DISTRIBUTION_PATH = DASHBOARD_I4F_DIR / "urgency_distribution_v1.csv"
SENTIMENT_DISTRIBUTION_PATH = DASHBOARD_I4F_DIR / "sentiment_distribution_v1.csv"
NEGATIVE_DEMO_CASES_PATH = DASHBOARD_I4F_DIR / "negative_complaint_cases_for_demo_v1.csv"
DASHBOARD_I5C_DIR = OUTPUTS_DIR / "dashboard_i5c_deepseek"
DEEPSEEK_DASHBOARD_STATS_PATH = DASHBOARD_I5C_DIR / "deepseek_dashboard_stats_v1.json"
DEEPSEEK_STORE_COMPLAINT_RANKING_PATH = DASHBOARD_I5C_DIR / "deepseek_store_complaint_ranking_v1.csv"
DEEPSEEK_PRODUCT_NEGATIVE_RANKING_PATH = DASHBOARD_I5C_DIR / "deepseek_product_negative_sentiment_ranking_v1.csv"
DEEPSEEK_COMPLAINT_REASON_DISTRIBUTION_PATH = DASHBOARD_I5C_DIR / "deepseek_complaint_reason_distribution_v1.csv"
DEEPSEEK_SOURCE_ATTRIBUTION_DISTRIBUTION_PATH = DASHBOARD_I5C_DIR / "deepseek_source_attribution_distribution_v1.csv"
DEEPSEEK_URGENCY_DISTRIBUTION_PATH = DASHBOARD_I5C_DIR / "deepseek_urgency_distribution_v1.csv"
DEEPSEEK_SENTIMENT_DISTRIBUTION_PATH = DASHBOARD_I5C_DIR / "deepseek_sentiment_distribution_v1.csv"
DEEPSEEK_NEGATIVE_DEMO_CASES_PATH = DASHBOARD_I5C_DIR / "deepseek_negative_complaint_cases_for_demo_v1.csv"
I4E2_SUMMARY_PATH = OUTPUTS_DIR / "i4e2_reviewed_80_summary_v1.json"
I4E3_SUMMARY_PATH = OUTPUTS_DIR / "i4e3_formal_eval_interpretation_summary_v1.json"
I4F_REPORT_PATH = DASHBOARD_I4F_DIR / "i4f_full_pool_dashboard_statistics_report_v1.md"
I5C_REPORT_PATH = DASHBOARD_I5C_DIR / "i5c_deepseek_dashboard_statistics_report_v1.md"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


st.set_page_config(
    page_title="Complaint LLM System MVP",
    layout="wide",
)


def analysis_to_dataframe(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


TEXT_COLUMN_CANDIDATES = [
    "email_text",
    "email_body",
    "text",
    "email",
    "message",
    "body",
    "content",
    "customer_email",
    "customer_message",
    "complaint_text",
]


def text_column_options(df: pd.DataFrame) -> tuple[list[str], str | None, str]:
    lower_map = {col.lower(): col for col in df.columns}
    matched_candidates = []
    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in lower_map:
            matched_candidates.append(lower_map[candidate])

    if matched_candidates:
        options = list(dict.fromkeys(matched_candidates + list(df.columns)))
        return options, matched_candidates[0], "candidate"

    text_like_columns = [
        col
        for col in df.columns
        if pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])
    ]
    if text_like_columns:
        return text_like_columns, text_like_columns[0], "text_like"

    return [], None, "none"


def detect_text_column(df: pd.DataFrame) -> str | None:
    lower_map = {col.lower(): col for col in df.columns}
    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


def run_batch_analysis(df: pd.DataFrame, text_column: str) -> pd.DataFrame:
    results = []
    for index, row in df.iterrows():
        email_id = row.get("email_id", None)
        if pd.isna(email_id) or email_id in (None, ""):
            email_id = f"uploaded-{index + 1:03d}"
        analysis = analyze_email(str(row[text_column]), email_id=str(email_id))
        results.append(analysis.model_dump())
    return pd.DataFrame(results)


def get_active_results() -> pd.DataFrame:
    session_df = st.session_state.get("latest_results")
    if isinstance(session_df, pd.DataFrame) and not session_df.empty:
        return session_df

    saved_path = OUTPUTS_DIR / "batch_results.csv"
    if saved_path.exists():
        return pd.read_csv(saved_path)

    return pd.DataFrame()


def save_results(df: pd.DataFrame, filename: str = "batch_results.csv") -> Path:
    path = ROOT_DIR / ".local" / "exports" / f"{uuid4()}-{Path(filename).name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def load_json_file(path: Path) -> dict:
    if not path.exists():
        st.warning(f"Expected dashboard file is missing: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        st.warning(f"Could not read JSON file {path}: {exc}")
        return {}


def load_dashboard_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.warning(f"Expected dashboard table is missing: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.warning(f"Could not read dashboard table {path}: {exc}")
        return pd.DataFrame()


def render_metric_row(df: pd.DataFrame) -> None:
    total = len(df)
    complaints = (
        int(df["is_complaint"].astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        if "is_complaint" in df
        else 0
    )
    negative = int((df["sentiment"].astype(str).str.lower() == "negative").sum()) if "sentiment" in df else 0
    high_urgency = int((df["urgency"].astype(str).str.lower() == "high").sum()) if "urgency" in df else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Emails", total)
    col2.metric("Complaints", complaints)
    col3.metric("Negative", negative)
    col4.metric("High urgency", high_urgency)


def render_bar_chart(df: pd.DataFrame, column: str, title: str) -> None:
    if column not in df.columns or df.empty:
        st.info(f"No data available for {title.lower()}.")
        return
    counts = df[column].fillna("unknown").value_counts().reset_index()
    counts.columns = [column, "count"]
    fig = px.bar(counts, x=column, y="count", title=title, text_auto=True)
    fig.update_layout(xaxis_title="", yaxis_title="Count")
    st.plotly_chart(fig, width="stretch")


def render_distribution_section(title: str, df: pd.DataFrame, label_column: str) -> None:
    st.markdown(f"### {title}")
    if df.empty or label_column not in df.columns or "count" not in df.columns:
        st.info(f"No {title.lower()} data is available.")
        return
    display_df = df.copy()
    if "percentage" in display_df.columns:
        display_df["percentage"] = display_df["percentage"].map(lambda value: f"{float(value):.2f}%")
    st.dataframe(display_df, width="stretch", hide_index=True)
    chart_df = df.set_index(label_column)[["count"]]
    st.bar_chart(chart_df)


def render_formal_evaluation_summary(i4e2_summary: dict, i4e3_summary: dict) -> None:
    st.markdown("### Formal Reviewed Golden Evaluation")
    report = validate_summary(i4e2_summary)
    if not report['available']:
        st.warning(report['reason'])
        return
    st.info("Historical project reference evaluation; assisted review, not an independent blind holdout. Runtime flags are historical records.")
    cols = st.columns(5)
    for col,label,key in zip(cols,['Reviewed test cases','Total fields','Correct fields','Mismatches','Accuracy'],['cases','total','correct','mismatches','accuracy']):
        col.metric(label, f"{report[key]:.2%}" if key=='accuracy' else str(report[key]))
    st.caption(f"Historical API flags: {report['attempted']} attempted, {report['errors']} errors. No new API calls.")
    st.caption("Raw historical taxonomy is preserved; v2 normalization does not change this score.")


def dashboard_paths_for_mode(mode: str) -> dict[str, Path]:
    if mode == "DeepSeek Prediction Statistics":
        return {
            "dashboard_stats": DEEPSEEK_DASHBOARD_STATS_PATH,
            "dashboard_dir": DASHBOARD_I5C_DIR,
            "store": DEEPSEEK_STORE_COMPLAINT_RANKING_PATH,
            "product": DEEPSEEK_PRODUCT_NEGATIVE_RANKING_PATH,
            "reason": DEEPSEEK_COMPLAINT_REASON_DISTRIBUTION_PATH,
            "source": DEEPSEEK_SOURCE_ATTRIBUTION_DISTRIBUTION_PATH,
            "urgency": DEEPSEEK_URGENCY_DISTRIBUTION_PATH,
            "sentiment": DEEPSEEK_SENTIMENT_DISTRIBUTION_PATH,
            "demo": DEEPSEEK_NEGATIVE_DEMO_CASES_PATH,
            "report": I5C_REPORT_PATH,
        }
    return {
        "dashboard_stats": DASHBOARD_STATS_PATH,
        "dashboard_dir": DASHBOARD_I4F_DIR,
        "store": STORE_COMPLAINT_RANKING_PATH,
        "product": PRODUCT_NEGATIVE_RANKING_PATH,
        "reason": COMPLAINT_REASON_DISTRIBUTION_PATH,
        "source": SOURCE_ATTRIBUTION_DISTRIBUTION_PATH,
        "urgency": URGENCY_DISTRIBUTION_PATH,
        "sentiment": SENTIMENT_DISTRIBUTION_PATH,
        "demo": NEGATIVE_DEMO_CASES_PATH,
        "report": I4F_REPORT_PATH,
    }


def render_i4f_dashboard() -> None:
    st.header("Customer Complaint Dashboard")
    mode = st.radio(
        "Dashboard Data Mode",
        [
            "Synthetic Reference Statistics",
            "DeepSeek Prediction Statistics",
            "Formal Reviewed Golden Evaluation",
        ],
        horizontal=True,
    )

    i4e2_summary = load_json_file(I4E2_SUMMARY_PATH)
    i4e3_summary = load_json_file(I4E3_SUMMARY_PATH)

    if mode == "Formal Reviewed Golden Evaluation":
        render_formal_evaluation_summary(i4e2_summary, i4e3_summary)
        with st.expander("Advanced / Debug: files used"):
            st.write(
                {
                    "i4e2_summary_file": str(I4E2_SUMMARY_PATH),
                    "i4e3_summary_file": str(I4E3_SUMMARY_PATH),
                }
            )
        return

    paths = dashboard_paths_for_mode(mode)
    if mode == "Synthetic Reference Statistics":
        st.caption("Synthetic full-pool dashboard statistics")
        st.info(
            "This mode uses 400-row full pool auto labels for dataset/dashboard reference statistics. "
            "It is not model accuracy. Historical reference metrics are shown only when a valid report is available."
        )
    else:
        st.caption("DeepSeek full-pool prediction dashboard statistics")
        st.info(
            "This mode uses real DeepSeek predictions on the 400-row full pool for model-output dashboard statistics. "
            "It is not formal model accuracy because the 400-row pool is not manually reviewed as a golden benchmark. "
            "Historical reference metrics require a valid report."
        )
        if not paths["dashboard_stats"].exists():
            st.warning(
                "DeepSeek prediction dashboard files are not available yet. Run I-4G and I-5C locally after the accepted "
                "400-case DeepSeek batch completes."
            )

    dashboard_stats = load_json_file(paths["dashboard_stats"])
    sentiment_df = load_dashboard_table(paths["sentiment"])
    urgency_df = load_dashboard_table(paths["urgency"])
    store_df = load_dashboard_table(paths["store"])
    product_df = load_dashboard_table(paths["product"])
    reason_df = load_dashboard_table(paths["reason"])
    source_df = load_dashboard_table(paths["source"])
    demo_df = load_dashboard_table(paths["demo"])

    total_rows = int(dashboard_stats.get("total_rows", 0))
    complaint_count = int(store_df["complaint_count"].sum()) if "complaint_count" in store_df.columns else 0
    negative_count = (
        int(sentiment_df.loc[sentiment_df["sentiment"].astype(str) == "negative", "count"].sum())
        if {"sentiment", "count"}.issubset(sentiment_df.columns)
        else 0
    )
    formal = validate_summary(i4e2_summary)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Total emails", f"{total_rows:,}")
    metric_cols[1].metric("Complaints", f"{complaint_count:,}")
    metric_cols[2].metric("Negative sentiment", f"{negative_count:,}")
    metric_cols[3].metric("历史七字段参考一致率", f"{formal['accuracy']:.2%}" if formal['available'] else 'unavailable')
    metric_cols[4].metric("Historical API errors", str(formal['errors']) if formal['available'] else 'unavailable')
    st.caption('历史80封 × 7字段：494/560 = 88.21%；参考来源为项目开发参考标签，非独立人工Gold。与400封模板数据统计及当前产品结果分开。报告不可用时不显示分数。')
    if not formal['available']:
        st.warning(formal['reason'])

    left_col, right_col = st.columns(2)
    with left_col:
        render_distribution_section("Sentiment Distribution", sentiment_df, "sentiment")
    with right_col:
        render_distribution_section("Urgency Distribution", urgency_df, "urgency")

    st.markdown("### Store Complaint Ranking")
    if mode == "Synthetic Reference Statistics":
        st.caption(
            "Synthetic demo statistics; store distribution is intentionally balanced. "
            "This ranking should not be interpreted as a real-world business ranking."
        )
    else:
        st.caption("DeepSeek prediction statistics over the same 400-row synthetic pool; this is model-output dashboard data, not formal accuracy.")
    if store_df.empty:
        st.info("No store complaint ranking data is available.")
    else:
        store_display = store_df[
            ["store_location", "complaint_count", "negative_count", "high_urgency_count", "complaint_rate"]
        ].copy()
        store_display["complaint_rate"] = store_display["complaint_rate"].map(lambda value: f"{float(value):.2%}")
        st.dataframe(store_display, width="stretch", hide_index=True)
        st.bar_chart(store_df.set_index("store_location")[["complaint_count", "negative_count", "high_urgency_count"]])

    st.markdown("### Product Negative Sentiment Ranking")
    st.caption("Product category normalization is a known follow-up issue from I-4E.3 and I-4E.4.")
    st.warning(
        "Product_category normalization / taxonomy alignment was the main weak point in formal evaluation. "
        "I-4G / I-5C displays current dashboard statistics and does not patch active product_category normalization."
    )
    if product_df.empty:
        st.info("No product negative sentiment ranking data is available.")
    else:
        product_display = product_df[
            ["product_category", "negative_count", "complaint_count", "high_urgency_count", "negative_rate"]
        ].copy()
        product_display["negative_rate"] = product_display["negative_rate"].map(lambda value: f"{float(value):.2%}")
        st.dataframe(product_display, width="stretch", hide_index=True)
        st.bar_chart(product_df.set_index("product_category")[["negative_count", "complaint_count", "high_urgency_count"]])

    left_col, right_col = st.columns(2)
    with left_col:
        render_distribution_section("Complaint Reason Distribution", reason_df, "complaint_reason")
    with right_col:
        render_distribution_section("Source Attribution Distribution", source_df, "source_attribution")

    st.markdown("### Representative Negative Complaint Cases")
    if demo_df.empty:
        st.info("No representative negative complaint demo cases are available.")
    else:
        for _, row in demo_df.iterrows():
            with st.expander(f"{row.get('email_id', 'unknown')} - {row.get('subject', 'No subject')}"):
                st.write(row.get("email_body", row.get("email_body_excerpt", "")))
                case_cols = st.columns(4)
                case_cols[0].metric("Sentiment", row.get("sentiment", ""))
                case_cols[1].metric("Urgency", row.get("urgency", ""))
                case_cols[2].metric("Store", row.get("store_location", ""))
                case_cols[3].metric("Product", row.get("product_category", ""))
                st.write(
                    {
                        "complaint_reason": row.get("complaint_reason", ""),
                        "source_attribution": row.get("source_attribution", ""),
                    }
                )

    render_formal_evaluation_summary(i4e2_summary, i4e3_summary)

    with st.expander("Advanced / Debug: files used"):
        st.write(
            {
                "dashboard_mode": mode,
                "dashboard_stats_v1.json": str(DASHBOARD_STATS_PATH),
                "deepseek_dashboard_stats_v1.json": str(DEEPSEEK_DASHBOARD_STATS_PATH),
                "dashboard_csv_directory": str(paths["dashboard_dir"]),
                "i4e2_summary_file": str(I4E2_SUMMARY_PATH),
                "i4e3_summary_file": str(I4E3_SUMMARY_PATH),
                "dashboard_report_path": str(paths["report"]),
            }
        )


def render_single_analysis_tab() -> None:
    from src.app.product_workspace import render
    render(ROOT_DIR)
    with st.expander('研究与旧版分析工具（历史兼容，付费禁用）'):
        render_offline_slice(ROOT_DIR)


def render_batch_analysis_tab() -> None:
    st.subheader("批量CSV · 旧规则演示")
    st.info("来源：legacy_mock 确定性规则；不调用DeepSeek。导出结果不进入P4审核库，不代表新邮件的LLM理解或已审核回复。")
    st.caption("Upload a CSV with an email text column. Recommended column names: email_text or email_body.")

    uploaded = st.file_uploader("Upload customer email CSV", type=["csv"])
    if uploaded is None:
        st.info("Upload a CSV file or generate sample data from the Evaluation page.")
        return

    df = load_input_csv(uploaded, '客户邮件')
    if df is None:
        return
    st.write("Preview")
    st.dataframe(df.head(20), width="stretch")

    options, detected, detection_mode = text_column_options(df)
    if detected is None:
        st.error(
            "Could not find an email text column. Please include email_text, email_body, text, email, message, body, "
            "content, customer_email, customer_message, or complaint_text."
        )
        return

    if detection_mode == "text_like":
        st.info("No standard email text column name was detected. Select the text column to analyze.")

    text_column = st.selectbox("Email text column", options=options, index=options.index(detected))
    if st.button("Run batch analysis", type="primary"):
        with st.spinner("Analyzing emails with offline mock chain..."):
            results_df = run_batch_analysis(df, text_column)
            output_path = save_results(results_df)
            st.session_state["latest_results"] = results_df

        st.success(f"Analyzed {len(results_df)} emails. Results saved to {output_path}.")
        st.dataframe(results_df, width="stretch")
        st.download_button(
            "Download results CSV",
            data=results_df.to_csv(index=False).encode("utf-8"),
            file_name="complaint_analysis_results.csv",
            mime="text/csv",
        )


def render_dashboard_tab() -> None:
    st.subheader("Dashboard")
    view = st.radio('Dashboard view', ['Historical dashboards', 'P3 versioned attribution', 'P4 review workflow'], key='dashboard_view')
    if view == 'P4 review workflow':
        from src.app.product_workspace import store, show_dashboard
        try:
            show_dashboard(store(ROOT_DIR), key='dashboard')
        except Exception as exc:
            st.error(f'Product dashboard unavailable ({type(exc).__name__}); no inferred statistics.')
        return
    elif view == 'P3 versioned attribution':
        from src.app.attribution_dashboard import render_attribution_dashboard
        st.info('P3读取 COMPLAINT_DB_PATH 分析库；默认单条工作台写入独立P4产品库。查看本轮案例请选择 P4 review workflow。P3不是P4的空数据替代来源。')
        render_attribution_dashboard(ROOT_DIR)
        return
    else:
        st.caption('Historical-only: original 400-row synthetic data and definitions; not real market rankings.')
        render_i4f_dashboard()

    st.divider()
    st.subheader("Current Session Analysis Results")
    df = get_active_results()
    if df.empty:
        st.info("No current session analysis results yet. Run single or batch analysis to populate this section.")
        return

    render_metric_row(df)
    col1, col2 = st.columns(2)
    with col1:
        render_bar_chart(df, "sentiment", "Sentiment Distribution")
        render_bar_chart(df, "product_category", "Product Categories")
    with col2:
        render_bar_chart(df, "urgency", "Urgency Distribution")
        render_bar_chart(df, "complaint_reason", "Complaint Reasons")

    render_bar_chart(df, "store_location", "Store Locations")
    st.dataframe(df, width="stretch")


def load_input_csv(source, label):
    try:
        return read_csv_input(source)
    except CSVInputError as exc:
        st.error(f'{label}：{exc}')
        return None


def render_evaluation_tab() -> None:
    st.subheader("Evaluation")
    st.caption("Compare prediction CSV output with golden labels by email_id.")
    st.info(
        "For smoke testing, use outputs/smoke_test_predictions_v1.csv as Prediction CSV "
        "and data/golden/golden_labels_smoke_v1.csv as Golden label CSV."
    )

    if st.button("Generate sample dataset"):
        sample_root = ROOT_DIR / ".local" / "samples" / str(uuid4())
        paths = generate_sample_files(sample_root)
        st.success("Sample dataset generated.")
        for name, path in paths.items():
            st.write(f"{name}: {path}")

    default_predictions = OUTPUTS_DIR / "batch_results.csv"
    default_test_golden = GOLDEN_DIR / "golden_labels_test_batch.csv"
    default_golden = default_test_golden if default_test_golden.exists() else GOLDEN_DIR / "golden_labels.csv"

    pred_file = st.file_uploader("Prediction CSV", type=["csv"], key="predictions")
    golden_file = st.file_uploader("Golden label CSV", type=["csv"], key="golden")

    predictions_df = None
    golden_df = None

    if pred_file is not None:
        predictions_df = load_input_csv(pred_file, '预测文件')
        if predictions_df is None:
            return
    elif default_predictions.exists():
        predictions_df = load_input_csv(default_predictions, '历史预测文件')
        if predictions_df is None:
            return
        st.info(f"Using saved predictions: {default_predictions}")

    if golden_file is not None:
        golden_df = load_input_csv(golden_file, '参考标签文件')
        if golden_df is None:
            return
    elif default_golden.exists():
        golden_df = load_input_csv(default_golden, '历史参考标签文件')
        if golden_df is None:
            return
        st.info(f"Using sample golden labels: {default_golden}")

    if predictions_df is None or golden_df is None:
        st.info("Provide both prediction and golden CSV files, or generate sample data and run batch analysis.")
        return

    evaluation_mode = st.selectbox("Evaluation fields", ["Core seven-field raw", "Legacy six-field compatibility"])
    if st.button("Evaluate", type="primary"):
        fields = LEGACY_LABEL_COLUMNS if evaluation_mode == 'Legacy six-field compatibility' else None
        try:
            report = evaluate_predictions(predictions_df, golden_df, fields)
        except ValueError as exc:
            st.error(f"Evaluation unavailable: {exc}")
            return
        if report['status'] != 'valid':
            st.error('; '.join(report['warnings']))
            st.write({k:report[k] for k in ('expected','matched','coverage','missing_prediction_ids','extra_prediction_ids')})
            return
        summary_df = pd.DataFrame(report["metrics"])
        if report["row_count"] == 0:
            st.error("Evaluation could not run because the prediction and golden CSV files have no matching email_id values.")
            st.info("Use data/golden/golden_labels_test_batch.csv with data/raw/test_batch_emails.csv for the smoke test batch.")
        st.write("Summary metrics")
        st.dataframe(summary_df, width="stretch")

        if report["confusion_matrices"]:
            st.write("Confusion matrices")
            for column, matrix_df in report["confusion_matrices"].items():
                st.markdown(f"**{column}**")
                st.dataframe(matrix_df, width="stretch")

        if report["warnings"]:
            for warning in report["warnings"]:
                st.warning(warning)


def main() -> None:
    st.title("客户投诉情绪分析与业务来源归因")
    st.caption("离线演示与历史真实结果重放 · 人工审核 · 仅模拟发送 · P4 Final候选")

    tabs = st.tabs(["单条处理 / Single Analysis", "批量分析 / Batch Analysis", "统计看板 / Dashboard", "评测 / Evaluation"])
    with tabs[0]:
        render_single_analysis_tab()
    with tabs[1]:
        render_batch_analysis_tab()
    with tabs[2]:
        render_dashboard_tab()
    with tabs[3]:
        render_evaluation_tab()


if __name__ == "__main__":
    main()
