"""Candidate annotation contract. Predictions never become Gold automatically."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class GoldCaseV1(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version: Literal['gold-case-v1']='gold-case-v1'
    case_id: str
    family_id: str
    thread_id: str
    turn_index: int = Field(ge=1)
    input_email: dict
    prior_turns: dict
    customer_claims: list[str]
    verified_facts: list[dict]
    unverified_facts: list[str]
    fixture_state: dict
    expected_issue_set: list[dict] | None
    required_points: list[dict]
    permitted_actions: list[str]
    forbidden_actions: list[str]
    expected_language: str
    severity: Literal['HIGH_RISK_CANDIDATE','ORDINARY_CANDIDATE']
    rubric_version: str
    source_evidence: list[dict]
    author: str
    reviewer: str | None = None
    review_state: Literal['GOLD_CANDIDATE']='GOLD_CANDIDATE'
    human_fields: dict
    raw_outputs: dict
