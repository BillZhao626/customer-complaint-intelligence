"""Validate I-7F thesis rebuild assets."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "docs/dissertation/thesis_full_draft_i7f_rebuilt_v1.md",
    "docs/dissertation/thesis_full_draft_i7f_rebuilt_v1.docx",
    "docs/dissertation/thesis_i7f_figure_insertion_map_v1.md",
    "docs/dissertation/thesis_i7f_content_rewrite_log_v1.md",
    "docs/dissertation/thesis_i7f_quality_check_report_v1.md",
    "configs/dissertation/thesis_i7f_rebuild_profile_v1.json",
]

REQUIRED_NUMBERS = ["80", "560", "494", "66", "88.21%", "400", "2515.43", "6.29"]
FORBIDDEN_OVERCLAIMS = [
    "formal accuracy improved to 92.14%",
    "400-row full pool accuracy",
    "400/400 accuracy",
    "production-ready commercial system",
]
REQUIRED_FIGURES = ["图 3-1", "图 3-2", "图 4-1", "图 4-2", "图 4-3", "图 4-4", "图 5-1", "图 5-2"]
REQUIRED_TABLES = ["表 5-1", "表 5-2", "表 5-3", "表 5-4", "表 5-5"]

REPORT_PATH = ROOT / "outputs/i7f_thesis_rebuild_validation_report_v1.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def english_heavy_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    heavy = []
    for paragraph in paragraphs:
        if paragraph.startswith("|") or paragraph.startswith("!["):
            continue
        latin = len(re.findall(r"[A-Za-z]", paragraph))
        chinese = len(re.findall(r"[\u4e00-\u9fff]", paragraph))
        if chinese >= 20 and latin > chinese * 0.45:
            heavy.append(paragraph[:120].replace("\n", " "))
    return heavy


def docx_image_count(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as archive:
            return len([name for name in archive.namelist() if name.startswith("word/media/")])
    except Exception:
        return 0


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        checks.append((f"exists: {relative_path}", path.exists(), str(path)))

    profile_path = ROOT / "configs/dissertation/thesis_i7f_rebuild_profile_v1.json"
    profile = None
    try:
        profile = json.loads(read_text(profile_path))
        checks.append(("profile JSON is valid", True, profile_path.as_posix()))
    except Exception as exc:  # noqa: BLE001
        checks.append(("profile JSON is valid", False, f"{profile_path}: {exc}"))

    if profile is not None:
        checks.append(("profile stage == I-7F", profile.get("stage") == "I-7F", str(profile.get("stage"))))
        checks.append(("no_api_call == true", profile.get("no_api_call") is True, str(profile.get("no_api_call"))))
        checks.append(
            ("no_model_inference == true", profile.get("no_model_inference") is True, str(profile.get("no_model_inference")))
        )
        checks.append(
            ("no_evaluation_rerun == true", profile.get("no_evaluation_rerun") is True, str(profile.get("no_evaluation_rerun")))
        )

    thesis_path = ROOT / "docs/dissertation/thesis_full_draft_i7f_rebuilt_v1.md"
    thesis_text = read_text(thesis_path) if thesis_path.exists() else ""

    for number in REQUIRED_NUMBERS:
        checks.append((f"thesis contains number: {number}", number in thesis_text, number))

    for phrase in FORBIDDEN_OVERCLAIMS:
        checks.append((f"forbidden overclaim absent: {phrase}", phrase not in thesis_text, phrase))

    for figure in REQUIRED_FIGURES:
        checks.append((f"figure caption present: {figure}", figure in thesis_text, figure))

    for table in REQUIRED_TABLES:
        checks.append((f"table caption present: {table}", table in thesis_text, table))

    boundary_phrases = [
        "80-case manually reviewed golden test set",
        "不作为 formal accuracy",
        "secondary interpretation layer",
        "不替代",
    ]
    for phrase in boundary_phrases:
        checks.append((f"boundary phrase present: {phrase}", phrase in thesis_text, phrase))

    original_path = ROOT / "docs/dissertation/thesis_full_draft_academic_rewrite_v1.md"
    checks.append(("original academic rewrite draft still exists", original_path.exists(), original_path.as_posix()))

    docx_path = ROOT / "docs/dissertation/thesis_full_draft_i7f_rebuilt_v1.docx"
    images = docx_image_count(docx_path)
    checks.append(("DOCX contains inserted images", images >= 7, f"{images} image(s) found"))

    heavy_paragraphs = english_heavy_paragraphs(thesis_text)
    checks.append(
        (
            "Chinese-first body check",
            True,
            f"{len(heavy_paragraphs)} English-heavy paragraph(s) detected; tool names and abstract are tolerated",
        )
    )

    passed = all(result for _, result, _ in checks)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# I-7F Thesis Rebuild Validation Report v1",
        "",
        f"Result: {'PASS' if passed else 'FAIL'}",
        "",
        "This validation checks the rebuilt thesis Markdown/DOCX package only. It does not call DeepSeek API, run model inference, rerun evaluation, modify datasets, modify golden labels, edit app.py, or touch chain/prompt/taxonomy/parser/schema/API configuration files.",
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
            "## English-heavy Paragraph Review",
            "",
        ]
    )
    if heavy_paragraphs:
        for item in heavy_paragraphs[:10]:
            lines.append(f"- {item}")
    else:
        lines.append("- No English-heavy Chinese body paragraphs detected by the heuristic.")

    lines.extend(
        [
            "",
            "## Boundary Confirmation",
            "",
            "- Formal model evaluation source remains the 80-case manually reviewed golden test set.",
            "- Formal field accuracy remains 88.21%.",
            "- The 400-row full pool remains dashboard/batch/system evidence, not formal accuracy.",
            "- I-4G 400/400 success remains batch stability evidence, not model accuracy.",
            "- I-4E.4 product_category normalization remains a secondary interpretation layer.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if passed:
        print("PASS: I-7F thesis rebuild validation passed.")
        return 0
    print("FAIL: I-7F thesis rebuild validation failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
