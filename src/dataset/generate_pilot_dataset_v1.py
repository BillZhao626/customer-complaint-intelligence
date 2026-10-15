from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = PROJECT_ROOT / "configs" / "dataset" / "synthetic_dataset_profile_v1.json"
DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "customer_emails_pilot_v1.csv"
GOLDEN_PATH = PROJECT_ROOT / "data" / "golden" / "golden_labels_pilot_v1.csv"
REPORT_PATH = PROJECT_ROOT / "outputs" / "dataset_profile_pilot_v1.md"

DATASET_COLUMNS = [
    "email_id",
    "email_subject",
    "email_body",
    "store_location",
    "purchased_product",
    "product_category",
    "customer_sentiment",
    "is_complaint",
    "complaint_reason",
    "urgency",
    "source_attribution",
    "expected_summary",
    "expected_reply_intent",
    "created_by",
    "review_status",
    "notes",
]

GOLDEN_COLUMNS = [
    "email_id",
    "sentiment_label",
    "product_category_label",
    "store_location_label",
    "complaint_reason_label",
    "urgency_label",
    "is_complaint_label",
    "source_attribution_label",
]

PRODUCT_CATEGORIES = {
    "wireless headphone": "Electronics",
    "coffee machine": "Home Appliances",
    "jacket": "Clothing",
    "desk lamp": "Furniture",
    "skincare product": "Beauty Products",
    "blender": "Home Appliances",
    "laptop": "Electronics",
    "rice cooker": "Home Appliances",
    "running shoes": "Sportswear",
    "air purifier": "Home Appliances",
    "smartphone": "Electronics",
    "office chair": "Furniture",
}

STORES = [
    "Hangzhou West Lake Store",
    "Shanghai Pudong Store",
    "Beijing Chaoyang Store",
    "Shenzhen Nanshan Store",
    "Guangzhou Tianhe Store",
    "Chengdu Chunxi Road Store",
    "Nanjing Xinjiekou Store",
]

NEGATIVE_SCENARIOS = [
    ("product quality", "product issue", "medium", "stopped working after two days", "check the product issue and offer repair, replacement, or refund options"),
    ("delivery delay", "delivery/logistics issue", "medium", "has not arrived after more than one week", "check the delivery status and provide a clear update"),
    ("customer service", "customer service response issue", "high", "has not received any reply from customer service", "prioritize the case and arrange a customer service follow-up"),
    ("wrong item", "store service issue", "medium", "received a different item from what was purchased", "verify the item mismatch and arrange correction"),
    ("after-sales service", "refund/exchange process issue", "medium", "could not complete an exchange request at the store", "review the exchange request and explain the next step"),
    ("health or safety issue", "product issue", "high", "caused a safety or health concern during use", "prioritize the safety concern and advise inspection or return"),
    ("refund request", "refund/exchange process issue", "medium", "wants a refund because the issue remains unresolved", "review the refund request and provide a clear resolution path"),
    ("product quality", "product issue", "medium", "arrived with visible damage and cannot be used normally", "verify the damage and offer an appropriate solution"),
    ("delivery delay", "delivery/logistics issue", "medium", "shows a shipping delay and no updated delivery date", "investigate the shipping delay and update the customer"),
    ("customer service", "customer service response issue", "high", "sent several messages but support has not replied", "escalate the response delay and contact the customer"),
    ("wrong item", "refund/exchange process issue", "medium", "received the wrong model and needs replacement", "arrange a replacement or return process"),
    ("after-sales service", "store service issue", "medium", "was told different return policies by store staff", "clarify the after-sales policy and support the customer"),
    ("product quality", "product issue", "medium", "makes an unusual noise during normal use", "inspect the product issue and suggest service options"),
    ("delivery delay", "delivery/logistics issue", "medium", "was promised delivery this week but it is still missing", "check logistics and provide an updated delivery time"),
    ("customer service", "customer service response issue", "high", "called the store service desk twice but no one followed up", "arrange a follow-up from the service team"),
    ("health or safety issue", "product issue", "high", "smelled like burning during first use, and I am worried this may be a safety issue", "prioritize the safety issue and stop-use guidance"),
    ("refund request", "refund/exchange process issue", "medium", "asked for a refund but the process has not moved forward", "review the refund progress and explain next steps"),
    ("wrong item", "store service issue", "medium", "the package contained an accessory instead of the purchased product", "verify the package issue and send the correct product"),
    ("product quality", "product issue", "medium", "lost power repeatedly after a recent purchase", "check the product quality problem and offer support"),
    ("delivery delay", "delivery/logistics issue", "medium", "tracking has not changed for several days", "investigate tracking and provide a delivery update"),
    ("customer service", "customer service response issue", "high", "customer service closed the chat without resolving the case, and there is still no response from customer service", "reopen and prioritize the customer service case"),
    ("after-sales service", "refund/exchange process issue", "medium", "the exchange request was rejected without explanation", "review the exchange decision and explain options"),
    ("health or safety issue", "product issue", "high", "caused skin discomfort and the customer is worried this may be a health issue", "prioritize health-related review and provide safe return guidance"),
    ("product quality", "product issue", "medium", "does not match the promised quality in the store", "review the product quality concern"),
    ("refund request", "refund/exchange process issue", "medium", "requests a refund after repeated unresolved issues", "confirm eligibility and explain the refund path"),
    ("wrong item", "refund/exchange process issue", "medium", "received the wrong size and needs an exchange", "arrange exchange support for the wrong size"),
    ("delivery delay", "delivery/logistics issue", "medium", "paid for fast delivery but the order is late", "review the delivery delay and service promise"),
    ("customer service", "customer service response issue", "medium", "visited the store but staff did not record the complaint", "document the complaint and arrange follow-up"),
    ("product quality", "product issue", "medium", "failed during normal use shortly after purchase", "verify the product failure and provide a solution"),
    ("after-sales service", "refund/exchange process issue", "medium", "needs replacement but has not received clear instructions", "send clear replacement instructions"),
]

POSITIVE_TEMPLATES = [
    "works well and the staff were helpful",
    "was delivered on time and performs better than expected",
    "was easy to set up and the store team explained everything clearly",
    "has excellent quality and the purchase experience was smooth",
    "was recommended by staff and fits my needs very well",
    "arrived quickly and customer service answered my question politely",
    "looks good and works reliably after several days of use",
    "was packaged carefully and the store visit was pleasant",
    "has been useful every day and I am satisfied with the service",
    "was a good purchase and I appreciate the support from the store",
]

NEUTRAL_TEMPLATES = [
    "Could you tell me whether an extended warranty is available?",
    "I would like to know whether installation service can be arranged.",
    "Can you confirm whether this item is available in another color?",
    "Please let me know if the store offers maintenance service.",
    "Could you explain the return policy before I decide whether to buy it?",
]

MIXED_TEMPLATES = [
    ("other", "unclear", "medium", "works well overall, but the delivery update was confusing and I am not sure who should handle it", "clarify the responsible team and provide a helpful update"),
    ("customer service", "customer service response issue", "medium", "is good, but customer service took too long to answer a simple setup question", "acknowledge the delay and provide setup support"),
    ("product quality", "product issue", "medium", "looks nice, but one small part became loose after a few days", "check the minor product issue and offer support"),
    ("delivery delay", "delivery/logistics issue", "medium", "is fine, but the delivery was late and affected my plan", "apologize for the delivery delay and explain the cause"),
    ("after-sales service", "refund/exchange process issue", "medium", "fits well, but the exchange policy was explained unclearly by staff", "clarify exchange policy and assist the customer"),
]


def load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def bool_label(value: bool) -> str:
    return "true" if value else "false"


def make_record(
    index: int,
    product: str,
    store: str,
    sentiment: str,
    complaint_reason: str,
    urgency: str,
    source_attribution: str,
    subject: str,
    body: str,
    reply_intent: str,
    notes: str,
) -> dict[str, str]:
    is_complaint = complaint_reason != "none"
    category = PRODUCT_CATEGORIES.get(product, "Other")
    expected_summary = f"Customer email about {product} at {store}: {complaint_reason}."
    return {
        "email_id": f"P{index:03d}",
        "email_subject": subject,
        "email_body": body,
        "store_location": store,
        "purchased_product": product,
        "product_category": category,
        "customer_sentiment": sentiment,
        "is_complaint": bool_label(is_complaint),
        "complaint_reason": complaint_reason,
        "urgency": urgency,
        "source_attribution": source_attribution,
        "expected_summary": expected_summary,
        "expected_reply_intent": reply_intent,
        "created_by": "deterministic_template_generator_v1",
        "review_status": "generated",
        "notes": notes,
    }


def generate_records() -> list[dict[str, str]]:
    products = list(PRODUCT_CATEGORIES)
    records = []
    index = 1

    for i, (reason, source, urgency, issue_text, reply_intent) in enumerate(NEGATIVE_SCENARIOS):
        product = products[i % len(products)]
        store = STORES[i % len(STORES)]
        subject = f"Issue with {product}"
        body = (
            f"I bought a {product} from {store} recently, but it {issue_text}. "
            "Please help me resolve this case."
        )
        records.append(
            make_record(
                index,
                product,
                store,
                "negative",
                reason,
                urgency,
                source,
                subject,
                body,
                reply_intent,
                "negative_complaint_template",
            )
        )
        index += 1

    for i, praise_text in enumerate(POSITIVE_TEMPLATES):
        product = products[(i + 2) % len(products)]
        store = STORES[(i + 1) % len(STORES)]
        subject = f"Positive feedback for {product}"
        body = f"I purchased a {product} from {store}. It {praise_text}. Thank you for the good experience."
        records.append(
            make_record(
                index,
                product,
                store,
                "positive",
                "none",
                "low",
                "none",
                subject,
                body,
                "thank the customer and offer further help if needed",
                "positive_praise_template",
            )
        )
        index += 1

    for i, inquiry_text in enumerate(NEUTRAL_TEMPLATES):
        product = products[(i + 5) % len(products)]
        store = STORES[(i + 3) % len(STORES)]
        subject = f"Question about {product}"
        body = f"I am considering buying a {product} from {store}. {inquiry_text}"
        records.append(
            make_record(
                index,
                product,
                store,
                "neutral",
                "none",
                "low",
                "none",
                subject,
                body,
                "answer the customer's product or service question",
                "neutral_inquiry_template",
            )
        )
        index += 1

    for i, (reason, source, urgency, issue_text, reply_intent) in enumerate(MIXED_TEMPLATES):
        product = products[(i + 7) % len(products)]
        store = STORES[(i + 5) % len(STORES)]
        subject = f"Mixed feedback about {product}"
        body = (
            f"I bought a {product} from {store}. The product {issue_text}. "
            "I appreciate part of the experience, but I still need help."
        )
        records.append(
            make_record(
                index,
                product,
                store,
                "negative",
                reason,
                urgency,
                source,
                subject,
                body,
                reply_intent,
                "mixed_or_ambiguous_template",
            )
        )
        index += 1

    return records


def validate_records(records: list[dict[str, str]], profile: dict) -> None:
    if len(records) != 50:
        raise ValueError(f"Expected 50 rows, found {len(records)}.")

    ids = [record["email_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("email_id values must be unique.")

    bodies = [record["email_body"].strip() for record in records]
    if any(not body for body in bodies):
        raise ValueError("email_body must not be empty.")
    if len(bodies) != len(set(bodies)):
        raise ValueError("email_body values must not be duplicated.")

    for record in records:
        missing = [column for column in DATASET_COLUMNS if column not in record]
        if missing:
            raise ValueError(f"Missing required columns for {record.get('email_id', 'unknown')}: {missing}")

    allowed_checks = {
        "customer_sentiment": set(profile["allowed_sentiments"]),
        "urgency": set(profile["allowed_urgency_levels"]),
        "product_category": set(profile["allowed_product_categories"]),
        "complaint_reason": set(profile["allowed_complaint_reasons"]),
        "source_attribution": set(profile["allowed_source_attribution_labels"]),
        "review_status": {"generated", "manually_reviewed", "revised", "rejected"},
        "is_complaint": {"true", "false"},
    }

    for record in records:
        for field, allowed_values in allowed_checks.items():
            if record[field] not in allowed_values:
                raise ValueError(f"{record['email_id']} has invalid {field}: {record[field]}")

    private_patterns = [
        re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        re.compile(r"\b1[3-9]\d{9}\b"),
        re.compile(r"\border\s*#?\s*\d+", re.IGNORECASE),
        re.compile(r"\b\d+\s+(road|street|avenue|lane)\b", re.IGNORECASE),
    ]
    for record in records:
        text = f"{record['email_subject']} {record['email_body']}"
        if any(pattern.search(text) for pattern in private_patterns):
            raise ValueError(f"{record['email_id']} may contain private information: {text}")


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_golden_rows(records: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "email_id": record["email_id"],
            "sentiment_label": record["customer_sentiment"],
            "product_category_label": record["product_category"],
            "store_location_label": record["store_location"],
            "complaint_reason_label": record["complaint_reason"],
            "urgency_label": record["urgency"],
            "is_complaint_label": record["is_complaint"],
            "source_attribution_label": record["source_attribution"],
        }
        for record in records
    ]


def distribution(records: list[dict[str, str]], field: str) -> Counter:
    return Counter(record[field] for record in records)


def add_distribution(lines: list[str], title: str, counts: Counter) -> None:
    lines.extend(["", f"## {title}", "", "| Label | Count |", "|---|---:|"])
    for label, count in sorted(counts.items()):
        lines.append(f"| {label} | {count} |")


def write_profile_report(records: list[dict[str, str]]) -> None:
    lines = [
        "# Pilot Synthetic Dataset Profile v1",
        "",
        "- Project stage: I-2B Pilot Synthetic Dataset",
        f"- Dataset path: `{DATASET_PATH}`",
        f"- Golden label path: `{GOLDEN_PATH}`",
        f"- Total rows: {len(records)}",
        "",
        "This is a synthetic pilot dataset. It is not copied from private customer data. "
        "It is used to test schema, label consistency, scenario coverage, and preparation "
        "for later LangChain + LLM structured output analysis. It is not the final full dataset.",
    ]

    add_distribution(lines, "Sentiment Distribution", distribution(records, "customer_sentiment"))
    add_distribution(lines, "Complaint Flag Distribution", distribution(records, "is_complaint"))
    add_distribution(lines, "Urgency Distribution", distribution(records, "urgency"))
    add_distribution(lines, "Product Category Distribution", distribution(records, "product_category"))
    add_distribution(lines, "Complaint Reason Distribution", distribution(records, "complaint_reason"))
    add_distribution(lines, "Source Attribution Distribution", distribution(records, "source_attribution"))
    add_distribution(lines, "Store Location Distribution", distribution(records, "store_location"))

    lines.extend(
        [
            "",
            "## Quality-Control Checklist",
            "",
            "- Required columns exist: passed",
            "- `email_id` values are unique: passed",
            "- `email_body` values are non-empty: passed",
            "- Labels belong to allowed values: passed",
            "- No obvious phone numbers, addresses, or order IDs: passed",
            "- Duplicate email bodies removed or avoided: passed",
            "- Total row count is 50: passed",
            "",
            "## Privacy and Synthetic Data Notes",
            "",
            "- The dataset is template-generated synthetic data.",
            "- It does not claim to come from real customer data.",
            "- It avoids real personal information, phone numbers, addresses, and order IDs.",
            "",
            "## Known Limitations",
            "",
            "- Template wording may be repetitive.",
            "- Some labels may still need manual review.",
            "- Source attribution can be ambiguous for mixed cases.",
            "- The pilot size is useful for checking schema and coverage, not for final benchmarking.",
            "",
            "## Next Step Recommendation",
            "",
            "Manually review the pilot dataset, revise weak rows, select a 30-50 case golden subset, "
            "and then proceed toward a larger 300-500 row synthetic dataset and LangChain-based analysis.",
            "",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    profile = load_profile()
    records = generate_records()
    validate_records(records, profile)
    golden_rows = build_golden_rows(records)

    write_csv(DATASET_PATH, records, DATASET_COLUMNS)
    write_csv(GOLDEN_PATH, golden_rows, GOLDEN_COLUMNS)
    write_profile_report(records)

    print("Pilot synthetic dataset generation passed quality checks.")
    print(f"Rows generated: {len(records)}")
    print(f"Dataset saved to: {DATASET_PATH}")
    print(f"Golden labels saved to: {GOLDEN_PATH}")
    print(f"Profile report saved to: {REPORT_PATH}")
    print(f"Sentiment distribution: {dict(distribution(records, 'customer_sentiment'))}")
    print(f"Complaint reason distribution: {dict(distribution(records, 'complaint_reason'))}")
    print(f"Source attribution distribution: {dict(distribution(records, 'source_attribution'))}")


if __name__ == "__main__":
    main()
