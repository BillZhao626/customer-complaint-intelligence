from __future__ import annotations

import re
from collections.abc import Mapping
from hashlib import sha1

try:
    from langchain_core.runnables import RunnableLambda
except ModuleNotFoundError:
    class RunnableLambda:  # type: ignore[no-redef]
        """Small fallback so utility scripts work before requirements are installed."""

        def __init__(self, func):
            self.func = func

        def invoke(self, inputs):
            return self.func(inputs)

        def __call__(self, inputs):
            return self.invoke(inputs)

from src.schemas.complaint_schema import ComplaintAnalysis


NEGATIVE_KEYWORDS = {
    "angry",
    "bad",
    "broken",
    "cancel",
    "complain",
    "complaint",
    "defect",
    "defective",
    "delay",
    "disappointed",
    "failed",
    "faulty",
    "irritation",
    "late",
    "no response",
    "not replied",
    "poor",
    "refund",
    "replacement",
    "return",
    "rude",
    "skin irritation",
    "stopped",
    "stopped working",
    "terrible",
    "unacceptable",
    "wrong",
    "wrong size",
}

POSITIVE_KEYWORDS = {
    "appreciate",
    "excellent",
    "good",
    "great",
    "happy",
    "helpful",
    "love",
    "resolved",
    "satisfied",
    "thanks",
}

HIGH_URGENCY_KEYWORDS = {
    "as soon as possible",
    "asap",
    "emergency",
    "health issue",
    "immediately",
    "legal",
    "no response from customer service",
    "refund as soon as possible",
    "right now",
    "safety issue",
    "skin irritation",
    "urgent",
    "customer service has not replied",
    "has not replied",
}

MEDIUM_URGENCY_KEYWORDS = {
    "broken",
    "delayed",
    "delayed delivery",
    "delayed for more than one week",
    "delivery delay",
    "defect",
    "exchange",
    "not delivered",
    "refund",
    "replacement",
    "shipping delay",
    "soon",
    "stopped working",
    "today",
    "tomorrow",
    "this week",
    "follow up",
    "wrong size",
}

PRODUCT_RULES = {
    "Home Appliances": ["coffee machine", "blender", "microwave", "refrigerator", "washer", "kettle", "toaster"],
    "Electronics": ["wireless headphone", "headphones", "headphone", "earbud", "phone", "laptop", "tablet", "charger", "camera"],
    "Clothing": ["jacket", "shirt", "coat", "dress", "shoes", "jeans"],
    "Furniture": ["desk lamp"],
    "Beauty Products": ["skincare product"],
    "Food": ["coffee", "meal", "sandwich", "milk", "snack", "cake"],
}

NON_PRODUCT_TERMS = {
    "customer service",
    "delivery",
    "refund",
    "replacement",
    "exchange",
    "staff",
    "support",
    "service team",
    "store service",
}

PURCHASE_PRODUCT_PATTERNS = [
    re.compile(
        r"\b(?:bought|purchased|ordered)\s+(?:a|an|the)?\s*(?P<product>[a-z][a-z\s-]{1,60}?)\s+from\s+",
        re.IGNORECASE,
    ),
]

PRODUCT_FAILURE_TERMS = {
    "broken",
    "defect",
    "defective",
    "faulty",
    "stopped working",
    "damaged",
    "failed",
}

CUSTOMER_SERVICE_TERMS = {
    "customer service",
    "has not replied",
    "not replied",
    "no response",
    "not received any response",
    "ignored",
    "support",
}

REASON_RULES = {
    "customer service": ["no response from customer service", "not received any response", "no response", "ignored", "customer service"],
    "health or skin irritation": ["skin irritation", "irritation"],
    "product quality": ["broken", "defect", "defective", "faulty", "stopped working", "damaged", "failed"],
    "delivery delay": ["delay", "late", "not arrived", "delivery", "shipment", "shipping"],
    "refund request": ["refund", "return", "money back", "cancel"],
    "after-sales service": ["wrong size", "exchange", "replacement", "staff did not help", "support"],
    "wrong item": ["wrong", "incorrect", "different item", "missing"],
    "pricing issue": ["overcharged", "price", "charged twice", "billing", "invoice"],
}

KNOWN_STORE_LOCATIONS = [
    "Hangzhou West Lake Store",
    "Shanghai Pudong Store",
    "Beijing Chaoyang Store",
    "Shenzhen Nanshan Store",
    "Guangzhou Tianhe Store",
]

STORE_PATTERNS = [
    re.compile(r"\b(?:from|at|in|visited)\s+(?:the\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+Store)\b"),
    re.compile(r"\b(online store|website|mobile app)\b", re.IGNORECASE),
]


def _stable_email_id(email_text: str) -> str:
    digest = sha1(email_text.encode("utf-8")).hexdigest()[:10]
    return f"email-{digest}"


def _contains_any(text: str, keywords: set[str] | list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _body_without_subject(email_text: str) -> str:
    lines = email_text.splitlines()
    non_subject_lines = [
        line for line in lines if not line.strip().lower().startswith(("subject:", "re:", "fw:", "fwd:"))
    ]
    return "\n".join(non_subject_lines).strip() or email_text


def _extract_store_location(email_text: str) -> str:
    body_text = _body_without_subject(email_text)
    body_lower = body_text.lower()

    for store in KNOWN_STORE_LOCATIONS:
        if store.lower() in body_lower:
            return store

    for pattern in STORE_PATTERNS:
        match = pattern.search(body_text)
        if match:
            location = match.group(1).strip()
            if location.lower() in {"online store", "website", "mobile app"}:
                return location.lower()
            return location

    city_keywords = ["Shanghai", "Beijing", "Guangzhou", "Shenzhen", "Chengdu", "Hangzhou", "Pudong"]
    for city in city_keywords:
        if city.lower() in body_lower:
            return city
    return "unknown"


def _product_lookup() -> dict[str, str]:
    return {
        product: category
        for category, products in PRODUCT_RULES.items()
        for product in products
        if product not in NON_PRODUCT_TERMS
    }


def _match_known_product(text: str) -> tuple[str, str] | None:
    matches = []
    for product, category in _product_lookup().items():
        if re.search(rf"\b{re.escape(product)}s?\b", text):
            matches.append((product, category))
    if matches:
        return max(matches, key=lambda item: len(item[0]))
    return None


def _clean_candidate_product(candidate: str) -> str:
    candidate = re.sub(r"\b(?:the|a|an)\b", " ", candidate.lower())
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,!?:;-")
    return candidate


def _extract_product(email_text_lower: str) -> tuple[str, str]:
    for pattern in PURCHASE_PRODUCT_PATTERNS:
        match = pattern.search(email_text_lower)
        if not match:
            continue
        candidate = _clean_candidate_product(match.group("product"))
        known_product = _match_known_product(candidate)
        if known_product:
            return known_product
        if candidate and candidate not in NON_PRODUCT_TERMS:
            return candidate, "other"

    known_product = _match_known_product(email_text_lower)
    if known_product:
        return known_product

    product_matches = []
    for category, products in PRODUCT_RULES.items():
        for product in products:
            if product not in NON_PRODUCT_TERMS and re.search(rf"\b{re.escape(product)}s?\b", email_text_lower):
                product_matches.append((product, category))
    if product_matches:
        return max(product_matches, key=lambda item: len(item[0]))
    return "unknown", "other"


def _infer_sentiment(email_text_lower: str) -> str:
    negative_hits = sum(keyword in email_text_lower for keyword in NEGATIVE_KEYWORDS)
    positive_hits = sum(keyword in email_text_lower for keyword in POSITIVE_KEYWORDS)
    if negative_hits > positive_hits:
        return "negative"
    if positive_hits > negative_hits:
        return "positive"
    return "neutral"


def _infer_urgency(email_text_lower: str, sentiment: str) -> str:
    if sentiment == "positive" and not _contains_any(email_text_lower, NEGATIVE_KEYWORDS):
        return "low"
    if _contains_any(email_text_lower, HIGH_URGENCY_KEYWORDS):
        return "high"
    if _contains_any(email_text_lower, MEDIUM_URGENCY_KEYWORDS):
        return "medium"
    if sentiment == "negative" and _contains_any(email_text_lower, {"refund", "broken", "failed", "defect", "no response"}):
        return "medium"
    return "low"


def _infer_reason(email_text_lower: str, is_complaint: bool) -> str:
    if not is_complaint:
        return "none"

    has_product_failure = _contains_any(email_text_lower, PRODUCT_FAILURE_TERMS)
    has_customer_service_issue = _contains_any(email_text_lower, CUSTOMER_SERVICE_TERMS)
    if has_product_failure and has_customer_service_issue:
        return "product defect and customer service"
    if has_product_failure:
        return "product quality"

    for reason, keywords in REASON_RULES.items():
        if _contains_any(email_text_lower, keywords):
            return reason
    return "general dissatisfaction"


def _extract_key_information(email_text: str, product_name: str, store_location: str, complaint_reason: str) -> list[str]:
    facts = []
    if product_name != "unknown":
        facts.append(f"Product mentioned: {product_name}")
    if store_location != "unknown":
        facts.append(f"Store/location mentioned: {store_location}")
    if complaint_reason != "none":
        facts.append(f"Complaint reason: {complaint_reason}")

    time_matches = re.findall(r"\b(?:today|yesterday|last week|two days|three days|this week|tomorrow)\b", email_text, re.IGNORECASE)
    for item in sorted(set(match.lower() for match in time_matches)):
        facts.append(f"Time reference: {item}")

    return facts[:6]


def _summarize(email_text: str, product_name: str, complaint_reason: str, sentiment: str) -> str:
    product_phrase = "the product" if product_name == "unknown" else product_name
    reason = complaint_reason.lower()

    if reason == "product defect and customer service":
        return (
            f"Customer reports both a product issue with {product_phrase} "
            "and a customer service response issue."
        )
    if reason == "customer service":
        return f"Customer reports a customer service response issue regarding {product_phrase}."
    if reason == "delivery delay":
        return f"Customer reports a delivery delay for {product_phrase}."
    if reason in {"product defect", "product quality"}:
        return f"Customer reports a product issue with {product_phrase}."
    if reason == "none":
        return f"Customer message about {product_phrase}; sentiment is {sentiment}."
    return f"Customer reports {complaint_reason} regarding {product_phrase}; sentiment is {sentiment}."


def _suggest_reply(product_name: str, complaint_reason: str, urgency: str, is_complaint: bool) -> str:
    if not is_complaint:
        return (
            "Dear customer, thank you for contacting us. We appreciate your message and will be happy to help "
            "if you need any further assistance."
        )

    urgency_sentence = {
        "high": "We will prioritize this case and arrange a follow-up as soon as possible.",
        "medium": "We will review the case promptly and update you with the next steps.",
        "low": "We will review the details and respond with an appropriate solution.",
    }[urgency]

    product_phrase = "the product" if product_name == "unknown" else f"your {product_name}"
    reason = complaint_reason.lower()

    if reason == "product defect and customer service":
        opening = (
            f"Dear customer, we are sorry that {product_phrase} has experienced a product issue "
            "and that our customer service response has not met your expectations."
        )
    elif reason == "customer service":
        opening = (
            "Dear customer, we are sorry for the delay in our customer service response "
            f"regarding {product_phrase}."
        )
    elif reason == "delivery delay":
        opening = f"Dear customer, we are sorry for the delivery delay of {product_phrase}."
    elif reason in {"product defect", "product quality"}:
        opening = f"Dear customer, we are sorry for the product issue with {product_phrase}."
    else:
        opening = f"Dear customer, we are sorry for the issue regarding {product_phrase}."

    return (
        f"{opening} We understand your concern regarding {complaint_reason}. {urgency_sentence} "
        "Please share any order number, photos, or receipts if available so our service team can verify the issue."
    )


def _confidence_score(email_text_lower: str, product_name: str, store_location: str, complaint_reason: str) -> float:
    score = 0.55
    if product_name != "unknown":
        score += 0.12
    if store_location != "unknown":
        score += 0.1
    if complaint_reason not in {"general dissatisfaction", "none"}:
        score += 0.15
    if len(email_text_lower.split()) >= 20:
        score += 0.08
    return round(min(score, 0.95), 2)


def analyze_email(email_text: str, email_id: str | None = None) -> ComplaintAnalysis:
    """Analyze one email using deterministic rules instead of an external LLM."""

    raw_email = str(email_text)
    clean_email = " ".join(raw_email.split())
    email_text_lower = clean_email.lower()

    product_name, product_category = _extract_product(email_text_lower)
    store_location = _extract_store_location(raw_email)
    sentiment = _infer_sentiment(email_text_lower)
    is_complaint = sentiment == "negative" or _contains_any(email_text_lower, NEGATIVE_KEYWORDS)
    urgency = _infer_urgency(email_text_lower, sentiment)
    complaint_reason = _infer_reason(email_text_lower, is_complaint)
    key_information = _extract_key_information(clean_email, product_name, store_location, complaint_reason)
    summary = _summarize(clean_email, product_name, complaint_reason, sentiment)
    suggested_reply = _suggest_reply(product_name, complaint_reason, urgency, is_complaint)
    confidence = _confidence_score(email_text_lower, product_name, store_location, complaint_reason)

    return ComplaintAnalysis(
        email_id=email_id or _stable_email_id(clean_email),
        store_location=store_location,
        product_name=product_name,
        product_category=product_category,
        sentiment=sentiment,
        urgency=urgency,
        is_complaint=is_complaint,
        complaint_reason=complaint_reason,
        key_information=key_information,
        summary=summary,
        suggested_reply=suggested_reply,
        confidence=confidence,
    )


def _chain_callable(inputs: Mapping[str, str] | str) -> ComplaintAnalysis:
    if isinstance(inputs, str):
        return analyze_email(inputs)
    return analyze_email(inputs.get("email_text", ""), email_id=inputs.get("email_id"))


def build_mock_complaint_chain() -> RunnableLambda:
    """Return a LangChain Runnable that emits the Pydantic structured output."""

    return RunnableLambda(_chain_callable)


mock_complaint_chain = build_mock_complaint_chain()
