from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHAIN_PATH = PROJECT_ROOT / "src" / "chains" / "langchain_complaint_chain.py"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "i34b_prompt_patch_summary_v1.md"
REPORT_PATH = PROJECT_ROOT / "outputs" / "i34b_prompt_patch_validation_report_v1.md"

REQUIRED_PHRASES = [
    "I-3.4B taxonomy-aware prompt revision",
    "store_location",
    "source_attribution",
    "complaint_reason",
    "refund/exchange process issue",
    "customer service response issue",
    "store service issue",
    "delivery/logistics issue",
    "mixed",
    "urgency",
    "valid JSON",
]


def validate_prompt_patch() -> list[str]:
    errors: list[str] = []

    if not CHAIN_PATH.exists():
        errors.append(f"Missing chain file: {CHAIN_PATH}")
        chain_text = ""
    else:
        chain_text = CHAIN_PATH.read_text(encoding="utf-8")

    if not SUMMARY_PATH.exists():
        errors.append(f"Missing prompt patch summary: {SUMMARY_PATH}")

    lower_chain_text = chain_text.lower()
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() not in lower_chain_text:
            errors.append(f"Missing required prompt marker or phrase: {phrase}")

    return errors


def write_report(errors: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# I-3.4B Prompt Patch Validation Report v1",
        "",
        f"- Validation status: {status}",
        f"- Chain file: `{CHAIN_PATH}`",
        f"- Summary file: `{SUMMARY_PATH}`",
        "",
        "## Required Prompt Markers",
        "",
    ]
    for phrase in REQUIRED_PHRASES:
        lines.append(f"- `{phrase}`")

    lines.extend(["", "## Result", ""])
    if errors:
        lines.append("Validation failed:")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("Validation passed. The active prompt contains the expected I-3.4B taxonomy-aware instructions.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    errors = validate_prompt_patch()
    write_report(errors)
    if errors:
        print("FAIL: I-3.4B prompt patch validation failed.")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("PASS: I-3.4B prompt patch validation passed.")
    print(f"Validation report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
