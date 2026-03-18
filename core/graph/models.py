from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Person:
    id: str
    name: str
    email: str
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    score: float = 0.0
    ai_tags: Optional[list] = None
    ai_persona: Optional[str] = None
    ai_product_fit: Optional[str] = None
    ai_urgency: Optional[str] = None
    ai_reasoning: Optional[str] = None
    ai_tagged_at: Optional[str] = None
    ai_tag_status: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Business:
    id: str
    name: str
    industry: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Product:
    id: str
    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Lead:
    id: str
    stage: str
    product_id: Optional[str] = None
    score: float = 0.0
    source: Optional[str] = None
    tags: Optional[list] = None
    created_at: Optional[str] = None


@dataclass
class Action:
    id: str
    type: str
    note: Optional[str] = None
    channel: Optional[str] = None
    timestamp: Optional[str] = None
