from __future__ import annotations

import hashlib
import py_compile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

APP_PATH = PROJECT_ROOT / "app.py"
VALIDATION_REPORT_PATH = PROJECT_ROOT / "outputs" / "i5a_dashboard_integration_validation_report_v1.md"

DASHBOARD_DIR = PROJECT_ROOT / "outputs" / "dashboard_i4f"
I4F_FILES = [
    DASHBOARD_DIR / "store_complaint_ranking_v1.csv",
    DASHBOARD_DIR / "product_negative_sentiment_ranking_v1.csv",
    DASHBOARD_DIR / "complaint_reason_distribution_v1.csv",
    DASHBOARD_DIR / "source_attribution_distribution_v1.csv",
    DASHBOARD_DIR / "urgency_distribution_v1.csv",
    DASHBOARD_DIR / "sentiment_distribution_v1.csv",
    DASHBOARD_DIR / "store_by_product_matrix_v1.csv",
    DASHBOARD_DIR / "negative_complaint_cases_for_demo_v1.csv",
    DASHBOARD_DIR / "dashboard_stats_v1.json",
    DASHBOARD_DIR / "i4f_full_pool_dashboard_statistics_report_v1.md",
]

REQUIRED_APP_REFERENCES = [
    "dashboard_stats_v1.json",
    "Customer Complaint Dashboard",
    "400-row full pool",
    "auto labels",
    "reviewed golden test set",
    "88.21%",
    "product_category normalization",
    "negative_complaint_cases_for_demo_v1.csv",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_assets() -> list[str]:
    errors: list[str] = []

    if not APP_PATH.exists():
        errors.append(f"Missing app.py: {APP_PATH}")
        app_text = ""
    else:
        app_text = APP_PATH.read_text(encoding="utf-8")

    for reference in REQUIRED_APP_REFERENCES:
        if reference not in app_text:
            errors.append(f"app.py missing required dashboard reference: {reference}")

    if APP_PATH.exists():
        try:
            py_compile.compile(str(APP_PATH), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"app.py failed py_compile: {exc}")

    for path in I4F_FILES:
        if not path.exists():
            errors.append(f"Missing required I-4F dashboard artifact: {path}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-5A Dashboard Integration Validation Report v1",
        "",
        f"- Validation status: {status}",
        "- Stage: I-5A",
        "",
        "## App Checks",
        "",
        f"- app.py exists: {'yes' if APP_PATH.exists() else 'no'}",
        "- app.py contains I-4F dashboard file references, evaluation boundary text, 88.21% formal accuracy text, and product_category normalization caveat.",
        "- app.py compiles with py_compile.",
        "",
        "## I-4F Dashboard Artifact Preservation Check",
        "",
        "This validation script reads I-4F files and writes only this validation report. It does not overwrite I-4F dashboard statistics.",
        "",
    ]
    for path in I4F_FILES:
        if path.exists():
            lines.append(f"- `{path}` exists: yes; sha256: `{sha256(path)}`")
        else:
            lines.append(f"- `{path}` exists: no")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-5A Streamlit dashboard integration is present and structurally valid.")
        lines.append("")
        lines.append("No API call is made by this validation script, and no model evaluation is rerun.")

    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-5A dashboard integration validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-5A dashboard integration validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
