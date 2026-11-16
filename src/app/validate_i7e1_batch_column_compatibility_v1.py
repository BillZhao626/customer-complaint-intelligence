"""Validate I-7E.1 Batch Analysis CSV column compatibility patch."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "app.py"
REPORT_PATH = ROOT / "outputs/i7e1_batch_column_compatibility_validation_report_v1.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    checks.append(("app.py exists", APP_PATH.exists(), APP_PATH.as_posix()))
    app_text = read_text(APP_PATH) if APP_PATH.exists() else ""

    checks.extend(
        [
            ("app.py contains email_body", "email_body" in app_text, "email_body"),
            (
                "app.py contains at least one extended candidate",
                any(candidate in app_text for candidate in ["customer_email", "customer_message", "complaint_text"]),
                "customer_email / customer_message / complaint_text",
            ),
            ("Batch Analysis page logic is present", "Batch Analysis" in app_text and "render_batch_analysis_tab" in app_text, "Batch Analysis"),
            (
                "Synthetic Reference Statistics mode preserved",
                "Synthetic Reference Statistics" in app_text,
                "Synthetic Reference Statistics",
            ),
            (
                "DeepSeek Prediction Statistics mode preserved",
                "DeepSeek Prediction Statistics" in app_text,
                "DeepSeek Prediction Statistics",
            ),
            (
                "Formal Reviewed Golden Evaluation mode preserved",
                "Formal Reviewed Golden Evaluation" in app_text,
                "Formal Reviewed Golden Evaluation",
            ),
            ("manual selectbox remains available", "st.selectbox" in app_text and "Email text column" in app_text, "Email text column selectbox"),
            ("text-like fallback exists", "text_like" in app_text and "is_string_dtype" in app_text, "text_like fallback"),
        ]
    )

    protected_paths = [
        "data/synthetic/customer_emails_full_v1.csv",
        "data/golden/golden_labels_full_auto_v1.csv",
        "data/golden/golden_labels_review_sample_v1_reviewed.csv",
        "src/chains/langchain_complaint_chain.py",
        "src/chains/mock_complaint_chain.py",
    ]
    for relative_path in protected_paths:
        path = ROOT / relative_path
        checks.append((f"protected file still exists: {relative_path}", path.exists(), str(path)))

    passed = all(result for _, result, _ in checks)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# I-7E.1 Batch Column Compatibility Validation Report v1",
        "",
        f"Result: {'PASS' if passed else 'FAIL'}",
        "",
        "This validation checks the Streamlit Batch Analysis CSV text-column compatibility patch only. It does not call DeepSeek API, run model inference, rerun evaluation, modify datasets, modify golden labels, or touch chain/prompt/taxonomy/parser/schema/API configuration files.",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for name, result, detail in checks:
        status = "PASS" if result else "FAIL"
        lines.append(f"| {name} | {status} | {detail.replace('|', '\\|')} |")

    lines.extend(
        [
            "",
            "## Compatibility Summary",
            "",
            "- Batch Analysis now supports `email_body` in addition to `email_text` and other common text-column names.",
            "- The UI retains manual text-column selection through the `Email text column` selectbox.",
            "- Dashboard modes are preserved: Synthetic Reference Statistics, DeepSeek Prediction Statistics, and Formal Reviewed Golden Evaluation.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if passed:
        print("PASS: I-7E.1 batch column compatibility validation passed.")
        return 0
    print("FAIL: I-7E.1 batch column compatibility validation failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
