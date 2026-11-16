"""Validate I-7E figure/table material pack assets."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "docs/dissertation/figures_tables/figure_3_1_system_architecture_mermaid_v1.md",
    "docs/dissertation/figures_tables/figure_3_2_dataset_pipeline_mermaid_v1.md",
    "docs/dissertation/figures_tables/figure_3_3_structured_extraction_workflow_mermaid_v1.md",
    "docs/dissertation/figures_tables/figure_5_1_evaluation_pipeline_mermaid_v1.md",
    "docs/dissertation/figures_tables/table_5_1_formal_evaluation_result_v1.md",
    "docs/dissertation/figures_tables/table_5_2_field_level_performance_v1.md",
    "docs/dissertation/figures_tables/table_5_3_product_category_normalization_v1.md",
    "docs/dissertation/figures_tables/table_5_4_batch_stability_v1.md",
    "docs/dissertation/figures_tables/table_5_5_dashboard_mode_boundary_v1.md",
    "docs/dissertation/figures_tables/ui_screenshot_caption_list_v1.md",
    "docs/dissertation/figures_tables/figure_table_material_pack_index_v1.md",
    "configs/dissertation/figure_table_material_pack_profile_v1.json",
    "src/evaluation/validate_i7e_figure_table_materials_v1.py",
]

CONTENT_CHECKS = {
    "docs/dissertation/figures_tables/table_5_1_formal_evaluation_result_v1.md": [
        "88.21%",
        "80-case reviewed golden test set",
        "560",
        "494",
        "66",
    ],
    "docs/dissertation/figures_tables/table_5_3_product_category_normalization_v1.md": [
        "secondary interpretation layer",
        "50.00%",
        "77.50%",
        "92.14%",
        "不替代",
    ],
    "docs/dissertation/figures_tables/table_5_4_batch_stability_v1.md": [
        "400",
        "2515.43",
        "6.29",
        "formal accuracy",
    ],
    "docs/dissertation/figures_tables/ui_screenshot_caption_list_v1.md": [
        "I-5E UI Screenshot Evidence Package v3 HD",
        "Dashboard",
        "Evaluation",
    ],
}

REPORT_PATH = ROOT / "outputs/i7e_figure_table_materials_validation_report_v1.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        checks.append((f"exists: {relative_path}", path.exists(), str(path)))

    profile_path = ROOT / "configs/dissertation/figure_table_material_pack_profile_v1.json"
    profile = None
    try:
        profile = json.loads(read_text(profile_path))
        checks.append(("profile JSON is valid", True, profile_path.as_posix()))
    except Exception as exc:  # noqa: BLE001 - validation report should capture all failures
        checks.append(("profile JSON is valid", False, f"{profile_path}: {exc}"))

    if profile is not None:
        checks.append(("profile stage == I-7E", profile.get("stage") == "I-7E", str(profile.get("stage"))))
        checks.append(
            (
                "evaluation boundary preserved",
                profile.get("evaluation_boundary_preserved") is True,
                str(profile.get("evaluation_boundary_preserved")),
            )
        )
        checks.append(("no_api_call == true", profile.get("no_api_call") is True, str(profile.get("no_api_call"))))
        checks.append(("no_model_rerun == true", profile.get("no_model_rerun") is True, str(profile.get("no_model_rerun"))))

    for relative_path, phrases in CONTENT_CHECKS.items():
        path = ROOT / relative_path
        text = read_text(path) if path.exists() else ""
        for phrase in phrases:
            checks.append((f"{relative_path} contains: {phrase}", phrase in text, phrase))

    index_path = ROOT / "docs/dissertation/figures_tables/figure_table_material_pack_index_v1.md"
    index_text = read_text(index_path) if index_path.exists() else ""
    for phrase in [
        "formal model evaluation",
        "secondary interpretation layer",
        "batch-processing stability evidence",
        "I-5E UI Screenshot Evidence Package v3 HD",
    ]:
        checks.append((f"index contains: {phrase}", phrase in index_text, phrase))

    original_thesis = ROOT / "docs/dissertation/thesis_full_draft_academic_rewrite_v1.md"
    checks.append(("original thesis draft still exists", original_thesis.exists(), original_thesis.as_posix()))

    protected_paths = [
        "data/synthetic/customer_emails_full_v1.csv",
        "data/golden/golden_labels_full_auto_v1.csv",
        "data/golden/golden_labels_review_sample_v1_reviewed.csv",
        "app.py",
        "src/chains/langchain_complaint_chain.py",
        "src/chains/mock_complaint_chain.py",
    ]
    for relative_path in protected_paths:
        path = ROOT / relative_path
        checks.append((f"protected file still exists: {relative_path}", path.exists(), str(path)))

    passed = all(result for _, result, _ in checks)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# I-7E Figure/Table Material Validation Report v1",
        "",
        f"Result: {'PASS' if passed else 'FAIL'}",
        "",
        "This validation checks I-7E figure/table material assets only. It does not call DeepSeek API, run inference, rerun evaluation, modify datasets, modify golden labels, edit Streamlit app code, or touch chain/prompt/taxonomy/parser/schema/API configuration files.",
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
            "## Boundary Confirmation",
            "",
            "- Table 5-1 preserves the formal 80-case reviewed golden test set result: 88.21%.",
            "- Table 5-3 frames product_category normalization as a secondary interpretation layer, not a replacement for formal results.",
            "- Table 5-4 frames the 400-row full-pool run as batch stability evidence, not formal accuracy.",
            "- UI screenshot captions point to the I-5E UI Screenshot Evidence Package v3 HD for later manual insertion.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if passed:
        print("PASS: I-7E figure/table material validation passed.")
        return 0
    print("FAIL: I-7E figure/table material validation failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
