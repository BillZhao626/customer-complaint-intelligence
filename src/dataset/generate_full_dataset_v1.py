from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "full_synthetic_dataset_profile_v1.json"
DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_full_v1.csv"
AUTO_LABEL_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_full_auto_v1.csv"
SUMMARY_JSON_PATH = PROJECT_ROOT / "outputs" / "full_dataset_generation_summary_v1.json"
PROFILE_REPORT_PATH = PROJECT_ROOT / "outputs" / "dataset_profile_full_v1.md"
RESULT_PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "full_dataset_generation_result_v1.json"

DATASET_COLUMNS = [
    "email_id",
    "subject",
    "email_body",
    "customer_name",
    "store_location",
    "purchase_channel",
    "purchase_timeframe",
    "product_name",
    "product_category",
    "expected_sentiment",
    "expected_urgency",
    "expected_is_complaint",
    "expected_complaint_reason",
    "expected_source_attribution",
    "expected_summary_hint",
    "expected_reply_tone",
    "scenario_type",
    "edge_case_type",
    "generation_template_id",
]

AUTO_LABEL_COLUMNS = [
    "email_id",
    "sentiment",
    "urgency",
    "is_complaint",
    "store_location",
    "product_category",
    "complaint_reason",
    "source_attribution",
    "summary_hint",
    "reply_tone",
    "scenario_type",
    "edge_case_type",
    "label_source",
]

STORES = [
    "Hangzhou West Lake Store",
    "Hangzhou Binjiang Store",
    "Shanghai Pudong Store",
    "Shanghai Xujiahui Store",
    "Nanjing Xinjiekou Store",
    "Suzhou Industrial Park Store",
    "Ningbo Tianyi Store",
    "Wenzhou Lucheng Store",
    "Beijing Chaoyang Store",
    "Shenzhen Nanshan Store",
]

PRODUCTS_BY_CATEGORY = {
    "Electronics": ["wireless headphones", "tablet", "smart speaker", "monitor", "keyboard"],
    "Home Appliances": ["rice cooker", "air purifier", "coffee machine", "vacuum cleaner", "blender"],
    "Furniture": ["desk lamp", "office chair", "bookshelf", "sofa table", "bedside cabinet"],
    "Clothing": ["jacket", "winter coat", "linen shirt", "jeans", "cardigan"],
    "Beauty/Personal Care": ["skincare set", "electric toothbrush", "hair dryer", "face cream", "shaver"],
    "Sports/Outdoor": ["running shoes", "fitness band", "yoga mat", "cycling jacket", "camping light"],
    "Food/Beverage": ["coffee beans", "tea gift box", "snack basket", "sparkling drink", "breakfast cereal"],
    "Service/Other": ["installation service", "membership plan", "repair appointment", "gift card", "delivery service"],
}

PURCHASE_CHANNELS = ["physical store", "official website", "mobile app", "customer service hotline"]
PURCHASE_TIMEFRAMES = ["recently", "last week", "a few days ago", "earlier this month", "during a recent visit"]

SCENARIOS = [
    {
        "count": 50,
        "sentiment": "negative",
        "urgency": "medium",
        "complaint_reason": "product quality",
        "source_attribution": "product issue",
        "scenario_type": "negative_product_quality",
        "edge_case_type": "standard product quality complaint",
        "issue_templates": [
            "stopped working during normal use",
            "arrived with a visible defect",
            "started making an unusual noise",
            "felt much lower quality than expected",
            "had a loose part after only a few uses",
        ],
        "reply_tone": "apologetic and solution-focused",
    },
    {
        "count": 45,
        "sentiment": "negative",
        "urgency": "medium",
        "complaint_reason": "delivery delay",
        "source_attribution": "delivery/logistics issue",
        "scenario_type": "negative_delivery_delay",
        "edge_case_type": "delivery update confusion",
        "issue_templates": [
            "has not arrived even though the delivery window passed",
            "shows a confusing delivery update and no clear next step",
            "was marked delayed without a new estimated arrival time",
            "has tracking that stopped updating several days ago",
            "was promised for this week but is still missing",
        ],
        "reply_tone": "clear and reassuring",
    },
    {
        "count": 45,
        "sentiment": "negative",
        "urgency": "medium",
        "complaint_reason": "customer service",
        "source_attribution": "customer service response issue",
        "scenario_type": "negative_customer_service",
        "edge_case_type": "customer support no response",
        "issue_templates": [
            "received no reply after several support messages",
            "was told someone would follow up but no one did",
            "had the chat closed before the issue was resolved",
            "called twice but still has no clear answer",
            "waited for a promised service response that never arrived",
        ],
        "reply_tone": "accountable and prompt",
    },
    {
        "count": 35,
        "sentiment": "negative",
        "urgency": "medium",
        "complaint_reason": "refund request",
        "source_attribution": "refund/exchange process issue",
        "scenario_type": "negative_refund_request",
        "edge_case_type": "refund plus no response",
        "issue_templates": [
            "asked for a refund but the process has not moved forward",
            "requested money back after the issue remained unresolved",
            "was told the refund would be checked but received no update",
            "needs a refund decision because the problem is still open",
            "cannot get a clear answer about refund eligibility",
        ],
        "reply_tone": "direct and resolution-oriented",
    },
    {
        "count": 35,
        "sentiment": "negative",
        "urgency": "medium",
        "complaint_reason": "after-sales service",
        "source_attribution": "refund/exchange process issue",
        "scenario_type": "negative_after_sales",
        "edge_case_type": "after-sales warranty/repair/exchange",
        "issue_templates": [
            "needs warranty support but the repair process is unclear",
            "could not complete an exchange request",
            "was given different repair instructions by different staff",
            "needs a replacement but has not received a clear process",
            "cannot confirm the next step for after-sales service",
        ],
        "reply_tone": "patient and procedural",
    },
    {
        "count": 25,
        "sentiment": "negative",
        "urgency": "medium",
        "complaint_reason": "wrong item",
        "source_attribution": "store service issue",
        "scenario_type": "negative_wrong_item",
        "edge_case_type": "wrong item",
        "issue_templates": [
            "received a different item from what was selected",
            "picked up the wrong size after store staff prepared the package",
            "found the package contained an accessory instead of the main product",
            "was given a different color than requested",
            "noticed the product label did not match the item inside",
        ],
        "reply_tone": "apologetic and corrective",
    },
    {
        "count": 15,
        "sentiment": "negative",
        "urgency": "high",
        "complaint_reason": "health or safety issue",
        "source_attribution": "product issue",
        "scenario_type": "negative_safety_health",
        "edge_case_type": "safety/health issue",
        "issue_templates": [
            "smelled like burning during first use",
            "became unusually hot and felt unsafe",
            "caused skin discomfort after normal use",
            "made a sharp cracking sound and the customer stopped using it",
            "created a safety concern that needs urgent attention",
        ],
        "reply_tone": "urgent and safety-first",
    },
    {
        "count": 10,
        "sentiment": "negative",
        "urgency": "medium",
        "complaint_reason": "other",
        "source_attribution": "unclear",
        "scenario_type": "negative_unclear_responsibility",
        "edge_case_type": "store staff issue vs customer support issue",
        "issue_templates": [
            "was passed between store staff and support without a clear owner",
            "cannot tell whether the store or support team should handle the issue",
            "received conflicting guidance about who is responsible",
            "was redirected several times and still does not know the right contact",
            "needs help because the responsible team is unclear",
        ],
        "reply_tone": "clarifying and ownership-focused",
    },
    {
        "count": 70,
        "sentiment": "positive",
        "urgency": "low",
        "complaint_reason": "none",
        "source_attribution": "none",
        "scenario_type": "positive_praise",
        "edge_case_type": "positive praise",
        "issue_templates": [
            "works well and the staff were helpful",
            "arrived on time and performed better than expected",
            "was easy to set up and the service felt thoughtful",
            "looked good and matched the recommendation",
            "made the customer satisfied with the purchase experience",
        ],
        "reply_tone": "warm and appreciative",
    },
    {
        "count": 50,
        "sentiment": "neutral",
        "urgency": "low",
        "complaint_reason": "none",
        "source_attribution": "none",
        "scenario_type": "neutral_inquiry",
        "edge_case_type": "neutral inquiry",
        "issue_templates": [
            "would like to know whether extended service is available",
            "needs confirmation about availability in another color",
            "is asking whether installation can be arranged",
            "wants to understand the return policy before buying",
            "would like more details about maintenance options",
        ],
        "reply_tone": "informative and polite",
    },
    {
        "count": 20,
        "sentiment": "neutral",
        "urgency": "medium",
        "complaint_reason": "none",
        "source_attribution": "none",
        "scenario_type": "neutral_service_question",
        "edge_case_type": "neutral inquiry",
        "issue_templates": [
            "is comparing service options before deciding what to buy",
            "needs help choosing between delivery and store pickup",
            "asks whether a product demonstration can be arranged",
            "wants to confirm whether membership benefits apply",
            "needs a clear explanation of service coverage",
        ],
        "reply_tone": "helpful and concise",
    },
]

HIGH_URGENCY_EXTRA_EVERY = 5
MIXED_EDGE_EVERY = 7


def load_profile() -> dict[str, Any]:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def product_for_index(index: int) -> tuple[str, str]:
    categories = list(PRODUCTS_BY_CATEGORY)
    category = categories[(index - 1) % len(categories)]
    products = PRODUCTS_BY_CATEGORY[category]
    return products[((index - 1) // len(categories)) % len(products)], category


def subject_for(scenario: dict[str, Any], product: str, index: int) -> str:
    if scenario["sentiment"] == "positive":
        return f"Positive feedback about {product} F{index:03d}"
    if scenario["sentiment"] == "neutral":
        return f"Question about {product} F{index:03d}"
    return f"Help needed with {product} F{index:03d}"


def body_for(
    scenario: dict[str, Any],
    product: str,
    store: str,
    purchase_channel: str,
    timeframe: str,
    issue_text: str,
    index: int,
) -> str:
    if scenario["sentiment"] == "positive":
        return (
            f"I bought a {product} from {store} through the {purchase_channel} {timeframe}. "
            f"It {issue_text}. I wanted to share this positive feedback with your team. "
            f"This synthetic note is case F{index:03d}."
        )
    if scenario["sentiment"] == "neutral":
        return (
            f"I am considering a {product} from {store} through the {purchase_channel}. "
            f"I {issue_text}. Please let me know the best option. "
            f"This synthetic note is case F{index:03d}."
        )
    if scenario["edge_case_type"] == "mixed praise plus complaint":
        return (
            f"I bought a {product} from {store} {timeframe}. The product has some good points, "
            f"but it {issue_text}. I appreciate part of the experience, but I still need help. "
            f"This synthetic complaint is case F{index:03d}."
        )
    return (
        f"I bought a {product} from {store} through the {purchase_channel} {timeframe}, "
        f"but it {issue_text}. Please help me resolve this synthetic customer case F{index:03d}."
    )


def make_record(index: int, scenario: dict[str, Any], local_index: int) -> dict[str, str]:
    product, category = product_for_index(index)
    store = STORES[(index - 1) % len(STORES)]
    purchase_channel = PURCHASE_CHANNELS[(index + local_index) % len(PURCHASE_CHANNELS)]
    timeframe = PURCHASE_TIMEFRAMES[(index + local_index * 2) % len(PURCHASE_TIMEFRAMES)]
    issue_text = scenario["issue_templates"][local_index % len(scenario["issue_templates"])]
    urgency = scenario["urgency"]
    edge_case_type = scenario["edge_case_type"]

    if scenario["sentiment"] == "negative" and scenario["complaint_reason"] != "health or safety issue":
        if local_index % HIGH_URGENCY_EXTRA_EVERY == 0:
            urgency = "high"
    if scenario["sentiment"] == "negative" and local_index % MIXED_EDGE_EVERY == 0:
        edge_case_type = "mixed praise plus complaint"

    subject = subject_for(scenario, product, index)
    email_body = body_for(scenario, product, store, purchase_channel, timeframe, issue_text, index)
    is_complaint = "false" if scenario["complaint_reason"] == "none" else "true"
    summary_hint = f"{scenario['scenario_type']} involving {product} at {store}"
    template_id = f"i4b_{scenario['scenario_type']}_{local_index % len(scenario['issue_templates']) + 1:02d}"

    return {
        "email_id": f"F{index:03d}",
        "subject": subject,
        "email_body": email_body,
        "customer_name": f"Synthetic Customer F{index:03d}",
        "store_location": store,
        "purchase_channel": purchase_channel,
        "purchase_timeframe": timeframe,
        "product_name": product,
        "product_category": category,
        "expected_sentiment": scenario["sentiment"],
        "expected_urgency": urgency,
        "expected_is_complaint": is_complaint,
        "expected_complaint_reason": scenario["complaint_reason"],
        "expected_source_attribution": scenario["source_attribution"],
        "expected_summary_hint": summary_hint,
        "expected_reply_tone": scenario["reply_tone"],
        "scenario_type": scenario["scenario_type"],
        "edge_case_type": edge_case_type,
        "generation_template_id": template_id,
    }


def generate_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    index = 1
    for scenario in SCENARIOS:
        for local_index in range(scenario["count"]):
            records.append(make_record(index, scenario, local_index))
            index += 1
    return records


def build_auto_labels(records: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "email_id": record["email_id"],
            "sentiment": record["expected_sentiment"],
            "urgency": record["expected_urgency"],
            "is_complaint": record["expected_is_complaint"],
            "store_location": record["store_location"],
            "product_category": record["product_category"],
            "complaint_reason": record["expected_complaint_reason"],
            "source_attribution": record["expected_source_attribution"],
            "summary_hint": record["expected_summary_hint"],
            "reply_tone": record["expected_reply_tone"],
            "scenario_type": record["scenario_type"],
            "edge_case_type": record["edge_case_type"],
            "label_source": "auto_generated_not_human_reviewed",
        }
        for record in records
    ]


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def distribution(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row[field] for row in rows).items()))


def percentage(count: int, total: int) -> str:
    return f"{count / total * 100:.1f}%" if total else "0.0%"


def add_distribution(lines: list[str], title: str, counts: dict[str, int], total: int) -> None:
    lines.extend(["", f"## {title}", "", "| Label | Count | Share |", "|---|---:|---:|"])
    for label, count in counts.items():
        lines.append(f"| {label} | {count} | {percentage(count, total)} |")


def write_summary_files(records: list[dict[str, str]], labels: list[dict[str, str]], profile: dict[str, Any]) -> None:
    total = len(records)
    distributions = {
        "sentiment": distribution(labels, "sentiment"),
        "urgency": distribution(labels, "urgency"),
        "is_complaint": distribution(labels, "is_complaint"),
        "store_location": distribution(labels, "store_location"),
        "product_category": distribution(labels, "product_category"),
        "complaint_reason": distribution(labels, "complaint_reason"),
        "source_attribution": distribution(labels, "source_attribution"),
        "scenario_type": distribution(labels, "scenario_type"),
        "edge_case_type": distribution(labels, "edge_case_type"),
    }
    summary = {
        "stage": "I-4B",
        "target_size": profile.get("target_size", 400),
        "actual_size": total,
        "generated_dataset_file": str(DATASET_PATH),
        "generated_auto_label_file": str(AUTO_LABEL_PATH),
        "label_status": "auto_generated_not_human_reviewed",
        "dataset_role": "synthetic dataset pool for dashboard statistics, batch processing, case coverage, and reviewed golden test set sampling",
        "distributions": distributions,
        "privacy_note": "Synthetic scenario data only; no real personal data, phone numbers, addresses, or order IDs intentionally included.",
        "next_stage_recommendation": "I-4C reviewed golden test set candidate selection",
    }
    SUMMARY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Full Synthetic Customer Email Dataset Profile v1",
        "",
        "- Stage: I-4B Full Synthetic Customer Email Dataset Pool Generation",
        f"- Dataset file: `{DATASET_PATH}`",
        f"- Auto label file: `{AUTO_LABEL_PATH}`",
        f"- Total rows: {total}",
        "",
        "## Dataset Role",
        "",
        "This is a synthetic dataset pool for dashboard statistics, batch processing demonstration, case coverage, and future reviewed golden test set sampling.",
        "It is not reviewed golden benchmark data. The labels are initial auto labels and are not human-reviewed golden labels.",
        "",
        "## Generation Policy",
        "",
        "- No DeepSeek API call was made.",
        "- No model evaluation was run.",
        "- No pilot dataset or pilot golden label file was modified.",
        "- Synthetic store names and generic synthetic customer identifiers are used.",
        "- Real phone numbers, exact addresses, order numbers, and private information are intentionally avoided.",
    ]
    for title, field in [
        ("Sentiment Distribution", "sentiment"),
        ("Urgency Distribution", "urgency"),
        ("Complaint Flag Distribution", "is_complaint"),
        ("Product Category Distribution", "product_category"),
        ("Complaint Reason Distribution", "complaint_reason"),
        ("Source Attribution Distribution", "source_attribution"),
        ("Store Location Distribution", "store_location"),
        ("Scenario Type Distribution", "scenario_type"),
        ("Edge Case Type Distribution", "edge_case_type"),
    ]:
        add_distribution(lines, title, distributions[field], total)

    lines.extend(
        [
            "",
            "## Coverage Observations",
            "",
            "- The pool covers complaint, praise, neutral inquiry, mixed praise plus complaint, delivery update confusion, safety/health issues, wrong item, refund, and after-sales cases.",
            "- All required source attribution and complaint reason categories are represented.",
            "- `unclear` source attribution is intentionally limited to a small proportion.",
            "",
            "## Limitations",
            "",
            "- Auto labels are not human-reviewed.",
            "- Formal metrics should not be computed on the full pool without manual review.",
            "- The pool is suitable for dashboard and batch processing workflows, not as an official benchmark.",
            "",
            "## Next Step",
            "",
            "Proceed to I-4C: select 50-100 reviewed golden test set candidates from this synthetic pool.",
            "",
        ]
    )
    PROFILE_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    result_profile = {
        "stage": "I-4B",
        "generated_dataset_file": str(DATASET_PATH),
        "generated_auto_label_file": str(AUTO_LABEL_PATH),
        "target_size": 400,
        "actual_size": total,
        "generation_script": str(PROJECT_ROOT / "src" / "dataset" / "generate_full_dataset_v1.py"),
        "validation_script": str(PROJECT_ROOT / "src" / "dataset" / "validate_full_dataset_v1.py"),
        "distribution_script": str(PROJECT_ROOT / "src" / "dataset" / "summarize_full_dataset_v1.py"),
        "profile_used": str(PROFILE_PATH),
        "quality_audit_report": str(PROJECT_ROOT / "outputs" / "full_dataset_quality_audit_v1.md"),
        "distribution_report": str(PROJECT_ROOT / "outputs" / "full_dataset_distribution_report_v1.md"),
        "dataset_role": "synthetic dataset pool for dashboard statistics, batch processing, case coverage, and reviewed golden test set sampling",
        "label_status": "auto_generated_not_human_reviewed",
        "next_stage_recommendation": "I-4C reviewed golden test set candidate selection",
    }
    RESULT_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PROFILE_PATH.write_text(json.dumps(result_profile, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    profile = load_profile()
    records = generate_records()
    labels = build_auto_labels(records)
    write_csv(DATASET_PATH, records, DATASET_COLUMNS)
    write_csv(AUTO_LABEL_PATH, labels, AUTO_LABEL_COLUMNS)
    write_summary_files(records, labels, profile)

    print("I-4B full synthetic dataset generation completed.")
    print(f"Rows generated: {len(records)}")
    print(f"Dataset saved to: {DATASET_PATH}")
    print(f"Auto labels saved to: {AUTO_LABEL_PATH}")
    print(f"Generation summary saved to: {SUMMARY_JSON_PATH}")
    print(f"Dataset profile saved to: {PROFILE_REPORT_PATH}")


if __name__ == "__main__":
    main()
