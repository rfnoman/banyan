from typing import Literal
from pydantic import BaseModel, field_validator

VALID_TAGS = {
    "decision-maker", "influencer", "champion", "end-user", "blocker",
    "high-intent", "evaluating", "early-research", "not-ready",
    "technical-buyer", "economic-buyer", "executive-sponsor",
    "hot", "warm", "cold",
    "inbound", "outbound", "referral", "scraped",
}

STAGES = ["New Lead", "Contacted", "Qualified", "Demo", "Proposal"]


class AITagResult(BaseModel):
    tags: list[str]
    persona: str
    product_fit: str
    urgency: Literal["high", "medium", "low"]
    reasoning: str
    suggested_stage: str
    confidence: float

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        invalid = set(v) - VALID_TAGS
        if invalid:
            raise ValueError(f"Invalid tags: {invalid}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v
