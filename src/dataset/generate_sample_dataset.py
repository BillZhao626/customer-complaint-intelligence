from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chains.mock_complaint_chain import analyze_email


SAMPLE_EMAILS = [
    {
        "email_id": "sample-001",
        "email_text": "I bought a blender from the Shanghai Pudong store last week. It stopped working after two days. Please refund me as soon as possible.",
    },
    {
        "email_id": "sample-002",
        "email_text": "The delivery of my laptop from the Beijing store is late and no one has followed up. This is very disappointing.",
    },
    {
        "email_id": "sample-003",
        "email_text": "Thank you for the helpful customer service in the Guangzhou store. My phone setup issue was resolved quickly.",
    },
    {
        "email_id": "sample-004",
        "email_text": "I received the wrong shoes from the online store. The color and size are different from my order.",
    },
    {
        "email_id": "sample-005",
        "email_text": "The coffee I bought in the Chengdu store tasted good. I wanted to ask whether you sell larger packs.",
    },
    {
        "email_id": "sample-006",
        "email_text": "Your support team ignored my repair request for the refrigerator. The service was poor and I need help today.",
    },
    {
        "email_id": "sample-007",
        "email_text": "I was charged twice for a jacket on the mobile app. Please check the billing issue and return the extra payment.",
    },
    {
        "email_id": "sample-008",
        "email_text": "The installation service for my washer was excellent. The staff arrived on time and explained everything clearly.",
    },
]


def generate_sample_files(root_dir: str | Path | None = None) -> dict[str, Path]:
    root = Path(root_dir) if root_dir is not None else Path(__file__).resolve().parents[2]
    raw_dir = root / "data" / "raw"
    synthetic_dir = root / "data" / "synthetic"
    golden_dir = root / "data" / "golden"
    outputs_dir = root / "outputs"

    for directory in (raw_dir, synthetic_dir, golden_dir, outputs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    raw_df = pd.DataFrame(SAMPLE_EMAILS)
    synthetic_path = synthetic_dir / "sample_customer_emails.csv"
    raw_path = raw_dir / "sample_customer_emails_raw.csv"
    raw_df.to_csv(raw_path, index=False)
    raw_df.to_csv(synthetic_path, index=False)

    analysis_records = [
        analyze_email(item["email_text"], email_id=item["email_id"]).model_dump()
        for item in SAMPLE_EMAILS
    ]
    golden_df = pd.DataFrame(analysis_records)
    golden_path = golden_dir / "golden_labels.csv"
    golden_df.to_csv(golden_path, index=False)

    return {
        "raw": raw_path,
        "synthetic": synthetic_path,
        "golden": golden_path,
    }


if __name__ == "__main__":
    paths = generate_sample_files()
    for name, path in paths.items():
        print(f"{name}: {path}")
