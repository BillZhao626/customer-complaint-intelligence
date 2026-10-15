from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from src.chains.mock_complaint_chain import analyze_email as analyze_email_with_mock
from src.config.llm_config import LLMConfig, get_llm_config


Sentiment = Literal["positive", "neutral", "negative"]
Urgency = Literal["low", "medium", "high"]
ProductCategory = Literal[
    "Electronics",
    "Home Appliances",
    "Clothing",
    "Furniture",
    "Beauty Products",
    "Sportswear",
    "Service",
    "Other",
]
ComplaintReason = Literal[
    "product quality",
    "delivery delay",
    "customer service",
    "wrong item",
    "after-sales service",
    "health or safety issue",
    "refund request",
    "none",
    "other",
]
SourceAttribution = Literal[
    "product issue",
    "store service issue",
    "delivery/logistics issue",
    "customer service response issue",
    "refund/exchange process issue",
    "unclear",
    "none",
]
AnalyzerBackend = Literal["deepseek_api", "langchain_llm", "mock_fallback"]


class LangChainComplaintAnalysis(BaseModel):
    email_id: str
    store_location: str
    product_name: str
    product_category: ProductCategory
    sentiment: Sentiment
    urgency: Urgency
    is_complaint: bool
    complaint_reason: ComplaintReason
    source_attribution: SourceAttribution
    key_information: list[str] = Field(default_factory=list)
    summary: str
    suggested_reply: str
    confidence: float = Field(ge=0.0, le=1.0)
    analyzer_backend: AnalyzerBackend
    model_name: str = ""
    parse_success: bool = True
    schema_validation_success: bool = True
    error_message: str = ""
    api_attempted: bool = False
    api_error_message: str = ""
    api_retry_count: int = 0
    raw_response_preview: str = ""


# I-3.4B taxonomy-aware prompt revision.
# Based on I-3.3 taxonomy rules and I-3.4A manual review summary.
CUSTOMER_EMAIL_ANALYSIS_PROMPT = """You are analyzing a customer email for a complaint analysis system.

Read the customer email and return structured JSON only.

Tasks:
- identify store location or channel
- identify purchased product
- classify product category
- classify sentiment
- decide whether it is a complaint
- identify complaint reason
- identify source attribution
- assign urgency
- extract key information
- write a short summary
- write a polite and practical suggested reply

Allowed values:
- sentiment: positive, neutral, negative
- urgency: low, medium, high
- product_category: Electronics, Home Appliances, Clothing, Furniture, Beauty Products, Sportswear, Service, Other
- complaint_reason: product quality, delivery delay, customer service, wrong item, after-sales service, health or safety issue, refund request, none, other
- source_attribution: product issue, store service issue, delivery/logistics issue, customer service response issue, refund/exchange process issue, unclear, none

Rules:
- Return only valid JSON as one JSON object, with no markdown wrapper.
- Output JSON must match the schema.
- Do not include markdown fences, comments, or extra commentary outside JSON.
- Use exactly the expected schema fields and do not add extra fields.
- Do not invent unsupported information.
- If there is no complaint, use complaint_reason "none" and source_attribution "none".
- Source attribution means business-source attribution, not legal liability.
- Suggested reply should be polite, action-oriented, and consistent with the detected complaint reason.

Field decision rules:

store_location:
- Extract the full store name from the email subject or email body whenever it appears.
- Use the complete branch name, for example "Hangzhou West Lake Store" or "Nanjing Xinjiekou Store".
- Use "unknown" only when no store location is explicitly present or reasonably inferable.
- Do not drop a visible store name and replace it with "unknown".

product_category:
- Follow the allowed taxonomy exactly.
- Useful examples: wireless headphone, laptop, smartphone -> Electronics; coffee machine, blender, rice cooker, air purifier -> Home Appliances; jacket -> Clothing; desk lamp, office chair -> Furniture; skincare product -> Beauty Products; running shoes -> Sportswear.
- Avoid over-generalizing desk lamp as Electronics if the project taxonomy treats it as Furniture or Home Appliances.
- If uncertain, choose the closest allowed category and keep the summary clear.

sentiment:
- positive: praise or satisfaction without unresolved problem.
- neutral: information request, general inquiry, or mixed wording without a clear complaint or unresolved issue.
- negative: explicit complaint, unresolved issue, refund/exchange request caused by a problem, product defect, service failure, delivery failure, or safety/health concern.
- If the email contains praise but also asks for help with an unresolved issue, default to negative unless the issue is only a minor neutral inquiry.

urgency:
- high requires strong cues such as safety/health concern, urgent/ASAP/immediately wording, repeated long-term no response, severe disruption, escalation, or serious business/customer impact.
- medium is for unresolved refund/exchange request, delivery delay, repeated contact without severe urgency cues, or standard complaint needing follow-up.
- low is for praise, neutral inquiry, or minor issue without time pressure.
- Do not assign high urgency only because an email is negative.

complaint_reason:
- Use "refund request" when the customer explicitly asks for a refund, money back, reimbursement, or refund processing.
- Use "after-sales service" for exchange, warranty, return policy, replacement, repair, or post-purchase handling without explicit refund wording.
- Use "customer service" for no support response, poor support communication, or call/email/chat not followed up.
- Use "delivery delay" for late delivery, confusing delivery update, delayed shipment, wrong delivery status, or logistics update problem when no more specific category exists.
- Use "product quality" for defect, malfunction, damaged product, missing part, or quality issue.
- Use "health or safety issue" for irritation, injury, safety risk, burning smell, smoke, overheating, or other health/safety concerns.
- Use "wrong item" when the received item is different from what was ordered.
- Use "none" for positive praise or neutral inquiry without complaint.
- Use "other" only when no defined category reasonably applies.

source_attribution:
- Choose one primary source_attribution as the business source of the issue.
- Use "refund/exchange process issue" when the core issue is refund, exchange, return, warranty, replacement, repair, or policy/process handling.
- Use "customer service response issue" when the issue is no reply, no follow-up, delayed support response, or phone/email/chat support failure.
- Use "store service issue" when the issue happened in a physical store or with in-store staff handling.
- Use "delivery/logistics issue" when the issue is late delivery, confusing delivery update, missing shipment, wrong delivery status, or logistics handling.
- Use "product issue" when the root cause is product quality, defect, missing part, malfunction, damaged product, or product-related safety issue.
- Use "none" when there is no complaint.
- Use "unclear" only when the source cannot be identified from the email.

Summary and suggested_reply:
- The summary should match the structured fields and should not add unsupported facts.
- The suggested_reply should acknowledge the correct reason and be practical.
- Do not blame the product when the issue is customer service response, store service, delivery, or refund/exchange process.
- Do not promise unsupported actions such as guaranteed refund approval.

Email ID: {email_id}
Customer email:
{email_text}
"""


STRICT_JSON_RETRY_REMINDER = """

Retry instruction:
Return only valid JSON. Do not include markdown fences or explanatory text.
"""


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        stripped = fenced_match.group(1).strip()
    elif stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"\s*```$", "", stripped).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as first_error:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise first_error
        return json.loads(stripped[start : end + 1])


def _safe_error_message(exc: Exception | str, config: LLMConfig | None = None) -> str:
    message = str(exc)
    active_config = config or get_llm_config()
    if active_config.api_key:
        message = message.replace(active_config.api_key, "[redacted_api_key]")
    message = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted_api_key]", message)
    return message[:800]


def _safe_response_preview(text: object, config: LLMConfig | None = None) -> str:
    preview = str(text or "")
    active_config = config or get_llm_config()
    if active_config.api_key:
        preview = preview.replace(active_config.api_key, "[redacted_api_key]")
    preview = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted_api_key]", preview)
    return preview[:300]


def _normalize_product_category(value: str) -> ProductCategory:
    aliases = {
        "electronics": "Electronics",
        "home appliances": "Home Appliances",
        "appliance": "Home Appliances",
        "clothing": "Clothing",
        "furniture": "Furniture",
        "beauty products": "Beauty Products",
        "sportswear": "Sportswear",
        "service": "Service",
        "other": "Other",
    }
    return aliases.get(str(value).strip().lower(), "Other")  # type: ignore[return-value]


def _normalize_complaint_reason(value: str) -> ComplaintReason:
    value_lower = str(value).strip().lower()
    aliases = {
        "product defect": "product quality",
        "product quality": "product quality",
        "delivery delay": "delivery delay",
        "customer service": "customer service",
        "staff service": "customer service",
        "wrong item": "wrong item",
        "after-sales service": "after-sales service",
        "health or skin irritation": "health or safety issue",
        "health or safety issue": "health or safety issue",
        "refund request": "refund request",
        "none": "none",
        "not a complaint": "none",
    }
    if "product" in value_lower and "customer service" in value_lower:
        return "other"
    return aliases.get(value_lower, "other")  # type: ignore[return-value]


def _normalize_sentiment(value: str) -> Sentiment:
    value_lower = str(value).strip().lower()
    if value_lower in {"positive", "neutral", "negative"}:
        return value_lower  # type: ignore[return-value]
    return "neutral"


def _normalize_urgency(value: str) -> Urgency:
    value_lower = str(value).strip().lower()
    if value_lower in {"low", "medium", "high"}:
        return value_lower  # type: ignore[return-value]
    return "low"


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    value_lower = str(value).strip().lower()
    if value_lower in {"true", "yes", "1", "complaint"}:
        return True
    if value_lower in {"false", "no", "0", "not a complaint"}:
        return False
    raise ValueError("Invalid boolean value")


def _to_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _clamp_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.8
    return max(0.0, min(1.0, confidence))


def _normalize_source_attribution(value: str, complaint_reason: str) -> SourceAttribution:
    value_lower = str(value).strip().lower()
    aliases = {
        "product issue": "product issue",
        "store service issue": "store service issue",
        "delivery issue": "delivery/logistics issue",
        "logistics issue": "delivery/logistics issue",
        "delivery/logistics issue": "delivery/logistics issue",
        "customer service issue": "customer service response issue",
        "customer service response issue": "customer service response issue",
        "refund process issue": "refund/exchange process issue",
        "exchange process issue": "refund/exchange process issue",
        "refund/exchange process issue": "refund/exchange process issue",
        "unclear": "unclear",
        "none": "none",
    }
    return aliases.get(value_lower, _infer_source_attribution(complaint_reason))  # type: ignore[return-value]


def _infer_source_attribution(complaint_reason: str) -> SourceAttribution:
    mapping = {
        "product quality": "product issue",
        "delivery delay": "delivery/logistics issue",
        "customer service": "customer service response issue",
        "wrong item": "store service issue",
        "after-sales service": "refund/exchange process issue",
        "health or safety issue": "product issue",
        "refund request": "refund/exchange process issue",
        "none": "none",
        "other": "unclear",
    }
    return mapping.get(complaint_reason, "unclear")  # type: ignore[return-value]


def _prepare_llm_payload(data: dict, email_id: str, config_model_name: str, backend: AnalyzerBackend) -> dict:
    from src.domain.contracts import LegacyProviderResult
    data = LegacyProviderResult.model_validate(data).model_dump()
    complaint_reason = _normalize_complaint_reason(data.get("complaint_reason", "other"))
    return {
        "email_id": email_id,
        "store_location": str(data.get("store_location") or "unknown"),
        "product_name": str(data.get("product_name") or data.get("purchased_product") or "unknown"),
        "product_category": _normalize_product_category(data.get("product_category", "Other")),
        "sentiment": _normalize_sentiment(data.get("sentiment", "neutral")),
        "urgency": _normalize_urgency(data.get("urgency", "low")),
        "is_complaint": _to_bool(data.get("is_complaint", False)),
        "complaint_reason": complaint_reason,
        "source_attribution": _normalize_source_attribution(data.get("source_attribution", "unclear"), complaint_reason),
        "key_information": _to_list(data.get("key_information")),
        "summary": str(data.get("summary") or ""),
        "suggested_reply": str(data.get("suggested_reply") or ""),
        "confidence": _clamp_confidence(data.get("confidence", 0.8)),
        "analyzer_backend": backend,
        "model_name": config_model_name,
        "parse_success": True,
        "schema_validation_success": True,
        "error_message": "",
        "api_attempted": True,
        "api_error_message": "",
        "api_retry_count": 0,
        "raw_response_preview": "",
    }


def _mock_fallback(
    email_id: str,
    email_text: str,
    error_message: str = "",
    parse_success: bool = True,
    schema_validation_success: bool = True,
    api_attempted: bool = False,
    api_error_message: str = "",
    api_retry_count: int = 0,
    raw_response_preview: str = "",
) -> dict:
    config = get_llm_config()
    mock_result = analyze_email_with_mock(email_text, email_id=email_id).model_dump()
    complaint_reason = _normalize_complaint_reason(mock_result.get("complaint_reason", "other"))
    payload = {
        "email_id": email_id,
        "store_location": mock_result.get("store_location", "unknown"),
        "product_name": mock_result.get("product_name", "unknown"),
        "product_category": _normalize_product_category(mock_result.get("product_category", "Other")),
        "sentiment": mock_result.get("sentiment", "neutral"),
        "urgency": mock_result.get("urgency", "low"),
        "is_complaint": bool(mock_result.get("is_complaint", False)),
        "complaint_reason": complaint_reason,
        "source_attribution": _infer_source_attribution(complaint_reason),
        "key_information": mock_result.get("key_information", []),
        "summary": mock_result.get("summary", ""),
        "suggested_reply": mock_result.get("suggested_reply", ""),
        "confidence": float(mock_result.get("confidence", 0.0)),
        "analyzer_backend": "mock_fallback",
        "model_name": config.model_name,
        "parse_success": parse_success,
        "schema_validation_success": schema_validation_success,
        "error_message": error_message,
        "api_attempted": api_attempted,
        "api_error_message": api_error_message,
        "api_retry_count": api_retry_count,
        "raw_response_preview": raw_response_preview,
    }
    return LangChainComplaintAnalysis(**payload).model_dump()


def _invoke_llm_json(
    prompt_class,
    llm,
    email_id: str,
    email_text: str,
    config: LLMConfig,
    backend: AnalyzerBackend,
    api_retry_count: int,
) -> dict:
    prompt_text = CUSTOMER_EMAIL_ANALYSIS_PROMPT
    if api_retry_count:
        prompt_text += STRICT_JSON_RETRY_REMINDER

    prompt = prompt_class.from_template(prompt_text)
    response = (prompt | llm).invoke({"email_id": email_id, "email_text": email_text})
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = " ".join(str(item) for item in content)
    content_text = str(content)
    data = _extract_json_object(content_text)
    payload = _prepare_llm_payload(data, email_id, config.model_name, backend)
    payload["api_retry_count"] = api_retry_count
    return LangChainComplaintAnalysis(**payload).model_dump()


def _langchain_llm_analysis(email_id: str, email_text: str) -> dict:
    config = get_llm_config()
    validation_errors = config.validation_errors()
    if validation_errors:
        error = "; ".join(validation_errors)
        return _mock_fallback(email_id, email_text, error_message=error, api_error_message=error)
    if not config.is_configured:
        return _mock_fallback(email_id, email_text, error_message="LLM API mode is disabled; using mock fallback.")

    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
    except ModuleNotFoundError as exc:
        safe_error = _safe_error_message(exc, config)
        error = f"Optional LangChain OpenAI provider package is not installed; using mock fallback. {safe_error}"
        return _mock_fallback(
            email_id,
            email_text,
            error_message=error,
            api_error_message=error,
        )

    api_attempted = False
    try:
        api_attempted = True
        llm = ChatOpenAI(
            model=config.model_name,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        backend: AnalyzerBackend = "deepseek_api" if config.provider == "deepseek" else "langchain_llm"
        try:
            return _invoke_llm_json(ChatPromptTemplate, llm, email_id, email_text, config, backend, api_retry_count=0)
        except (json.JSONDecodeError, ValidationError) as first_exc:
            first_error = _safe_error_message(first_exc, config)
            raw_response_preview = ""
            if isinstance(first_exc, json.JSONDecodeError):
                raw_response_preview = _safe_response_preview(getattr(first_exc, "doc", ""), config)
            try:
                return _invoke_llm_json(ChatPromptTemplate, llm, email_id, email_text, config, backend, api_retry_count=1)
            except (json.JSONDecodeError, ValidationError) as retry_exc:
                retry_error = _safe_error_message(retry_exc, config)
                if isinstance(retry_exc, json.JSONDecodeError):
                    raw_response_preview = _safe_response_preview(getattr(retry_exc, "doc", ""), config)
                combined_error = (
                    f"Initial JSON/schema failure: {type(first_exc).__name__}: {first_error}; "
                    f"retry failure: {type(retry_exc).__name__}: {retry_error}"
                )
                return _mock_fallback(
                    email_id,
                    email_text,
                    error_message=f"LLM JSON parsing or schema validation failed after retry: {combined_error}",
                    parse_success=not isinstance(retry_exc, json.JSONDecodeError),
                    schema_validation_success=False,
                    api_attempted=api_attempted,
                    api_error_message=combined_error,
                    api_retry_count=1,
                    raw_response_preview=raw_response_preview,
                )
            except Exception as retry_exc:
                retry_error = _safe_error_message(retry_exc, config)
                combined_error = (
                    f"Initial JSON/schema failure: {type(first_exc).__name__}: {first_error}; "
                    f"retry API failure: {type(retry_exc).__name__}: {retry_error}"
                )
                return _mock_fallback(
                    email_id,
                    email_text,
                    error_message=f"LLM retry failed safely after JSON/schema failure: {combined_error}",
                    parse_success=False,
                    schema_validation_success=False,
                    api_attempted=api_attempted,
                    api_error_message=combined_error,
                    api_retry_count=1,
                    raw_response_preview=raw_response_preview,
                )
    except (json.JSONDecodeError, ValidationError) as exc:
        safe_error = _safe_error_message(exc, config)
        raw_response_preview = ""
        if isinstance(exc, json.JSONDecodeError):
            raw_response_preview = _safe_response_preview(getattr(exc, "doc", ""), config)
        return _mock_fallback(
            email_id,
            email_text,
            error_message=f"LLM JSON parsing or schema validation failed: {type(exc).__name__}: {safe_error}",
            parse_success=not isinstance(exc, json.JSONDecodeError),
            schema_validation_success=False,
            api_attempted=api_attempted,
            api_error_message=safe_error,
            raw_response_preview=raw_response_preview,
        )
    except Exception as exc:
        safe_error = _safe_error_message(exc, config)
        return _mock_fallback(
            email_id,
            email_text,
            error_message=f"LLM call failed safely: {type(exc).__name__}: {safe_error}",
            parse_success=False,
            schema_validation_success=False,
            api_attempted=api_attempted,
            api_error_message=safe_error,
            api_retry_count=0,
        )


def analyze_email_with_langchain(email_id: str, email_text: str) -> dict:
    """Analyze one email with LangChain when configured, otherwise use mock fallback."""

    return _langchain_llm_analysis(email_id=email_id, email_text=email_text)
