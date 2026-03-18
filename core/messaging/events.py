from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator


def _now():
    return datetime.now(timezone.utc)


class PersonData(BaseModel):
    name: str
    email: str = ""
    title: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def coerce_none_email(cls, v):
        return v if v is not None else ""
    company: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None


class CompanyData(BaseModel):
    name: str
    industry: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None


class LeadCreatedEvent(BaseModel):
    event_type: str = "lead.created"
    source_app: str
    source_product: str
    person: PersonData
    company: CompanyData
    trigger: str
    score_hints: dict = Field(default_factory=dict)
    raw_context: str = ""
    timestamp: datetime = Field(default_factory=_now)


class LeadSavedEvent(BaseModel):
    event_type: str = "lead.saved"
    person_id: str
    source_app: str
    trigger: str
    raw_context: str = ""
    timestamp: datetime = Field(default_factory=_now)


class ActionLoggedEvent(BaseModel):
    event_type: str = "action.logged"
    person_id: Optional[str] = None
    person_email: Optional[str] = None
    action_type: str
    note: str = ""
    channel: str = ""
    source_app: str = ""
    timestamp: datetime = Field(default_factory=_now)


class CompanyUpdatedEvent(BaseModel):
    event_type: str = "company.updated"
    company_name: str
    updates: dict = Field(default_factory=dict)
    source_app: str = ""
    timestamp: datetime = Field(default_factory=_now)


class AITagRequestEvent(BaseModel):
    event_type: str = "lead.tag_requested"
    person_id: str
    requested_by: str
    timestamp: datetime = Field(default_factory=_now)
