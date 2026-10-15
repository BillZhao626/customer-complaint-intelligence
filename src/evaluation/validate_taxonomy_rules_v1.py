from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "taxonomy" / "label_taxonomy_rules_v1.json"
REPORT_PATH = PROJECT_ROOT / "outputs" / "taxonomy_rules_validation_report_v1.md"

REQUIRED_TOP_LEVEL_KEYS = [
    "version",
    "stage",
    "purpose",
    "allowed_values",
    "field_level_decision_rules",
    "source_attribution_priority_rules",
    "complaint_reason_priority_rules",
    "sentiment_mixed_feedback_rule",
    "urgency_threshold_rule",
    "store_location_extraction_rule",
    "examples",
    "implementation_notes",
]

REQUIRED_FIELDS = [
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
]


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Taxonomy config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in config:
            errors.append(f"Missing top-level key: {key}")

    allowed_values = config.get("allowed_values", {})
    if not isinstance(allowed_values, dict):
        errors.append("allowed_values must be an object.")
        allowed_values = {}

    for field in REQUIRED_FIELDS:
        values = allowed_values.get(field)
        if values is None:
            errors.append(f"Missing allowed values for field: {field}")
        elif not isinstance(values, list) or not values:
            errors.append(f"Allowed values for {field} must be a non-empty list.")

    field_rules = config.get("field_level_decision_rules", {})
    if not isinstance(field_rules, dict):
        errors.append("field_level_decision_rules must be an object.")
        field_rules = {}

    for field in REQUIRED_FIELDS:
        if field not in field_rules and field not in {"is_complaint", "product_category"}:
            errors.append(f"Missing field-level decision rules for: {field}")

    source_rules = config.get("source_attribution_priority_rules")
    if not isinstance(source_rules, list) or not source_rules:
        errors.append("source_attribution_priority_rules must be a non-empty list.")
    else:
        source_labels = {rule.get("label") for rule in source_rules if isinstance(rule, dict)}
        expected_source_labels = set(allowed_values.get("source_attribution", []))
        missing = expected_source_labels - source_labels
        if missing:
            errors.append(f"Source attribution priority rules missing labels: {', '.join(sorted(missing))}")

    complaint_rules = config.get("complaint_reason_priority_rules")
    if not isinstance(complaint_rules, list) or not complaint_rules:
        errors.append("complaint_reason_priority_rules must be a non-empty list.")
    else:
        complaint_labels = {rule.get("label") for rule in complaint_rules if isinstance(rule, dict)}
        expected_complaint_labels = set(allowed_values.get("complaint_reason", []))
        missing = expected_complaint_labels - complaint_labels
        if missing:
            errors.append(f"Complaint reason priority rules missing labels: {', '.join(sorted(missing))}")

    examples = config.get("examples")
    if not isinstance(examples, list) or not examples:
        errors.append("examples must be a non-empty list.")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# Taxonomy Rules Validation Report v1",
        "",
        f"- Config path: `{CONFIG_PATH}`",
        f"- Validation status: {status}",
        "",
        "## Checks",
        "",
        "- Required top-level keys",
        "- Required output fields",
        "- Non-empty allowed label lists",
        "- Source attribution priority rules",
        "- Complaint reason priority rules",
        "- Example cases",
        "",
        "## Result",
        "",
    ]

    if errors:
        lines.append("Validation failed with the following issues:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. The taxonomy rules config is structurally complete for I-3.3 planning use.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    try:
        config = load_config()
        errors = validate_config(config)
    except Exception as exc:
        errors = [f"{type(exc).__name__}: {exc}"]

    write_report(errors)
    if errors:
        print("FAIL: taxonomy rules validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("PASS: taxonomy rules validation passed.")
    print(f"Validation report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
