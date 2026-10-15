from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Sentiment = Literal["positive", "neutral", "negative"]
Urgency = Literal["low", "medium", "high"]


class ComplaintAnalysis(BaseModel):
    """Structured output for one customer email analysis."""

    email_id: str = Field(..., description="Unique email identifier.")
    store_location: str = Field(..., description="Store, city, region, or channel mentioned in the email.")
    product_name: str = Field(..., description="Specific product name mentioned or inferred from the email.")
    product_category: str = Field(..., description="High-level product or service category.")
    sentiment: Sentiment = Field(..., description="Overall customer sentiment.")
    urgency: Urgency = Field(..., description="Estimated response urgency.")
    is_complaint: bool = Field(..., description="Whether the email contains a customer complaint.")
    complaint_reason: str = Field(..., description="Primary reason for the complaint.")
    key_information: list[str] = Field(default_factory=list, description="Important facts extracted from the email.")
    summary: str = Field(..., description="Concise summary of the email.")
    suggested_reply: str = Field(..., description="Draft customer service reply.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Mock analyzer confidence score.")
