from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "outputs" / "dashboard_i4f"

STORE_RANKING_PATH = DASHBOARD_DIR / "store_complaint_ranking_v1.csv"
PRODUCT_RANKING_PATH = DASHBOARD_DIR / "product_negative_sentiment_ranking_v1.csv"
COMPLAINT_REASON_PATH = DASHBOARD_DIR / "complaint_reason_distribution_v1.csv"
SOURCE_ATTRIBUTION_PATH = DASHBOARD_DIR / "source_attribution_distribution_v1.csv"
URGENCY_PATH = DASHBOARD_DIR / "urgency_distribution_v1.csv"
SENTIMENT_PATH = DASHBOARD_DIR / "sentiment_distribution_v1.csv"
STORE_PRODUCT_MATRIX_PATH = DASHBOARD_DIR / "store_by_product_matrix_v1.csv"
DEMO_CASES_PATH = DASHBOARD_DIR / "negative_complaint_cases_for_demo_v1.csv"
DASHBOARD_JSON_PATH = DASHBOARD_DIR / "dashboard_stats_v1.json"
REPORT_PATH = DASHBOARD_DIR / "i4f_full_pool_dashboard_statistics_report_v1.md"
PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "dashboard_i4f_profile_v1.json"
VALIDATION_REPORT_PATH = DASHBOARD_DIR / "i4f_dashboard_stats_validation_report_v1.md"

REQUIRED_FILES = [
    STORE_RANKING_PATH,
    PRODUCT_RANKING_PATH,
    COMPLAINT_REASON_PATH,
    SOURCE_ATTRIBUTION_PATH,
    URGENCY_PATH,
    SENTIMENT_PATH,
    STORE_PRODUCT_MATRIX_PATH,
    DEMO_CASES_PATH,
    DASHBOARD_JSON_PATH,
    REPORT_PATH,
    PROFILE_PATH,
]


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object."
    return data, None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def count_sum(path: Path) -> int:
    return sum(int(row["count"]) for row in read_csv(path))


def contains_all(text: str, phrases: list[str]) -> list[str]:
    lower = text.lower()
    return [phrase for phrase in phrases if phrase.lower() not in lower]


def validate_assets() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"Missing required I-4F artifact: {path}")

    dashboard: dict[str, Any] | None = None
    if DASHBOARD_JSON_PATH.exists():
        dashboard, error = load_json(DASHBOARD_JSON_PATH)
        if error:
            errors.append(f"Invalid dashboard JSON: {error}")
        elif dashboard:
            if dashboard.get("stage") != "I-4F":
                errors.append('Dashboard JSON stage must be "I-4F".')
            if dashboard.get("total_rows") != 400:
                errors.append(f"Dashboard JSON total_rows must be 400, found {dashboard.get('total_rows')}.")
            warning = str(dashboard.get("warning", "")).lower()
            if "not formal model accuracy" not in warning:
                errors.append("Dashboard JSON warning must state that the full pool is not formal model accuracy.")

    if PROFILE_PATH.exists():
        profile, error = load_json(PROFILE_PATH)
        if error:
            errors.append(f"Invalid dashboard profile JSON: {error}")
        elif profile and profile.get("stage") != "I-4F":
            errors.append('Dashboard profile JSON stage must be "I-4F".')

    for path in [COMPLAINT_REASON_PATH, SOURCE_ATTRIBUTION_PATH, URGENCY_PATH, SENTIMENT_PATH]:
        if path.exists():
            total = count_sum(path)
            if total != 400:
                errors.append(f"Distribution totals in {path} must sum to 400, found {total}.")

    if DEMO_CASES_PATH.exists():
        demo_rows = read_csv(DEMO_CASES_PATH)
        if len(demo_rows) != 20:
            errors.append(f"Demo negative complaint cases row count must be 20, found {len(demo_rows)}.")
        non_negative = [row.get("email_id", "") for row in demo_rows if row.get("sentiment") != "negative"]
        if non_negative:
            errors.append(f"Demo cases must all be negative sentiment. Non-negative IDs: {non_negative[:5]}")

    if REPORT_PATH.exists():
        report_text = REPORT_PATH.read_text(encoding="utf-8")
        missing = contains_all(
            report_text,
            [
                "400-row full synthetic pool",
                "auto labels",
                "dashboard statistics",
                "not formal accuracy",
                "80-case reviewed golden test set",
                "88.21%",
                "product_category normalization caveat",
            ],
        )
        for phrase in missing:
            errors.append(f"Dashboard report must mention: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-4F Dashboard Stats Validation Report v1",
        "",
        f"- Validation status: {status}",
        "- Stage: I-4F",
        "- Validation scope: dashboard statistics artifacts only.",
        "",
        "## Required Artifacts",
        "",
    ]
    for path in REQUIRED_FILES:
        lines.append(f"- `{path}` exists: {'yes' if path.exists() else 'no'}")
    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. I-4F dashboard statistics artifacts are present and structurally valid.")
        lines.append("")
        lines.append("No API call is made by this validation script, and no model evaluation is rerun.")
    VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_assets()
    write_report(errors)
    if errors:
        print("FAIL: I-4F dashboard stats validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: I-4F dashboard stats validation passed.")
    print(f"Validation report saved to: {VALIDATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
