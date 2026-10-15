from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SMOKE_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e1_reviewed_smoke20_summary_v1.json"
FULL_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i4e2_reviewed_80_summary_v1.json"
COMPARISON_REPORT_PATH = PROJECT_ROOT / "outputs" / "i4e2_vs_i4e1_smoke_comparison_v1.md"
COMPARISON_JSON_PATH = PROJECT_ROOT / "outputs" / "i4e2_vs_i4e1_smoke_comparison_v1.json"

FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def overall_accuracy(summary: dict[str, Any]) -> float:
    if "overall_field_accuracy" in summary:
        return float(summary["overall_field_accuracy"])
    total_cases = int(summary.get("total_cases", 0))
    total_fields = total_cases * len(summary.get("fields_compared", FIELDS))
    mismatches = int(summary.get("total_mismatch_count", 0))
    return (total_fields - mismatches) / total_fields if total_fields else 0.0


def main() -> None:
    smoke = load_json(SMOKE_SUMMARY_PATH)
    full = load_json(FULL_SUMMARY_PATH)

    smoke_stable = (
        smoke.get("backend_used") == "deepseek_api"
        and smoke.get("api_error_count") == 0
        and smoke.get("parse_success_count") == smoke.get("total_cases")
        and smoke.get("schema_validation_success_count") == smoke.get("total_cases")
    )
    full_stable = (
        full.get("backend_used") == "deepseek_api"
        and full.get("api_error_count") == 0
        and full.get("parse_success_count") == full.get("total_cases")
        and full.get("schema_validation_success_count") == full.get("total_cases")
    )

    field_comparison = {}
    for field in FIELDS:
        field_comparison[field] = {
            "smoke_accuracy": float(smoke.get("field_accuracy", {}).get(field, 0.0)),
            "full_accuracy": float(full.get("field_accuracy", {}).get(field, 0.0)),
            "delta_full_minus_smoke": float(full.get("field_accuracy", {}).get(field, 0.0))
            - float(smoke.get("field_accuracy", {}).get(field, 0.0)),
            "smoke_mismatches": int(smoke.get("mismatches_by_field", {}).get(field, 0)),
            "full_mismatches": int(full.get("mismatches_by_field", {}).get(field, 0)),
        }

    comparison = {
        "stage": "I-4E.2_vs_I-4E.1",
        "smoke_summary_file": str(SMOKE_SUMMARY_PATH),
        "full_summary_file": str(FULL_SUMMARY_PATH),
        "smoke_api_status": {
            "backend_used": smoke.get("backend_used"),
            "api_attempted_count": smoke.get("api_attempted_count"),
            "api_error_count": smoke.get("api_error_count"),
        },
        "full_api_status": {
            "backend_used": full.get("backend_used"),
            "api_attempted_count": full.get("api_attempted_count"),
            "api_error_count": full.get("api_error_count"),
        },
        "smoke_parse_schema_stable": smoke_stable,
        "full_parse_schema_stable": full_stable,
        "smoke_total_cases": smoke.get("total_cases"),
        "full_total_cases": full.get("total_cases"),
        "smoke_total_mismatch_count": smoke.get("total_mismatch_count"),
        "full_total_mismatch_count": full.get("total_mismatch_count"),
        "smoke_overall_field_accuracy": overall_accuracy(smoke),
        "full_overall_field_accuracy": overall_accuracy(full),
        "field_level_accuracy_comparison": field_comparison,
        "full_80_remained_stable_after_smoke": bool(smoke_stable and full_stable),
        "recommendation": (
            "proceed_to_i4e3_result_interpretation"
            if smoke_stable and full_stable
            else "rerun_api_evaluation_until_backend_and_parse_schema_are_stable"
        ),
    }
    COMPARISON_JSON_PATH.write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# I-4E.2 vs I-4E.1 Smoke Comparison v1",
        "",
        "## API Status",
        "",
        "| Run | Backend | API attempted | API errors |",
        "|---|---|---:|---:|",
        f"| Smoke 20 | {smoke.get('backend_used')} | {smoke.get('api_attempted_count')} | {smoke.get('api_error_count')} |",
        f"| Full 80 | {full.get('backend_used')} | {full.get('api_attempted_count')} | {full.get('api_error_count')} |",
        "",
        "## Parse / Schema Stability",
        "",
        "| Run | Parse success | Schema success | Total cases | Stable |",
        "|---|---:|---:|---:|---|",
        f"| Smoke 20 | {smoke.get('parse_success_count')} | {smoke.get('schema_validation_success_count')} | {smoke.get('total_cases')} | {'yes' if smoke_stable else 'no'} |",
        f"| Full 80 | {full.get('parse_success_count')} | {full.get('schema_validation_success_count')} | {full.get('total_cases')} | {'yes' if full_stable else 'no'} |",
        "",
        "## Overall Comparison",
        "",
        "| Run | Mismatch count | Overall field accuracy |",
        "|---|---:|---:|",
        f"| Smoke 20 | {smoke.get('total_mismatch_count')} | {overall_accuracy(smoke):.4f} |",
        f"| Full 80 | {full.get('total_mismatch_count')} | {overall_accuracy(full):.4f} |",
        "",
        "## Field-level Accuracy Comparison",
        "",
        "| Field | Smoke accuracy | Full accuracy | Delta | Smoke mismatches | Full mismatches |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field in FIELDS:
        item = field_comparison[field]
        lines.append(
            f"| {field} | {item['smoke_accuracy']:.4f} | {item['full_accuracy']:.4f} | "
            f"{item['delta_full_minus_smoke']:.4f} | {item['smoke_mismatches']} | {item['full_mismatches']} |"
        )
    lines.extend(
        [
            "",
            "## Stability Decision",
            "",
            f"- Full 80 remained stable after smoke: {'yes' if comparison['full_80_remained_stable_after_smoke'] else 'no'}",
            f"- Recommendation: `{comparison['recommendation']}`",
            "",
        ]
    )
    COMPARISON_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("I-4E.2 vs I-4E.1 comparison completed.")
    print(f"Full 80 remained stable after smoke: {comparison['full_80_remained_stable_after_smoke']}")
    print(f"Comparison report saved to: {COMPARISON_REPORT_PATH}")
    print(f"Comparison JSON saved to: {COMPARISON_JSON_PATH}")


if __name__ == "__main__":
    main()
