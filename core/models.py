import uuid
import secrets

from django.db import models


def _uuid():
    return str(uuid.uuid4())


class ExternalApp(models.Model):
    """An external application authorized to send contact events to the CRM."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, unique=True, help_text="App identifier (e.g., 'greenforest')"
    )
    display_name = models.CharField(max_length=200, help_text="Human-readable name")
    api_key = models.CharField(max_length=64, unique=True, default=secrets.token_hex)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name


class Business(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=_uuid)
    name = models.CharField(max_length=255, unique=True)
    industry = models.CharField(max_length=255, blank=True, null=True)
    size = models.CharField(max_length=100, blank=True, null=True)
    website = models.CharField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "businesses"

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "size": self.size,
            "website": self.website,
            "location": self.location,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Product(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=_uuid)
    name = models.CharField(max_length=255, unique=True)
    url = models.CharField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Source(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=_uuid)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Person(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=_uuid)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    linkedin_url = models.CharField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    source = models.CharField(max_length=100, blank=True, null=True)
    score = models.FloatField(default=0.0)
    company = models.ForeignKey(
        Business, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees"
    )

    # AI tagging fields
    ai_tags = models.JSONField(default=list, blank=True)
    ai_persona = models.CharField(max_length=255, blank=True, null=True)
    ai_product_fit = models.CharField(max_length=255, blank=True, null=True)
    ai_urgency = models.CharField(max_length=50, blank=True, null=True)
    ai_reasoning = models.TextField(blank=True, null=True)
    ai_tagged_at = models.DateTimeField(blank=True, null=True)
    ai_tag_status = models.CharField(max_length=50, blank=True, null=True)
    ai_suggested_stage = models.CharField(max_length=100, blank=True, null=True)
    ai_confidence = models.FloatField(default=0.0)
    ai_model_used = models.CharField(max_length=100, blank=True, null=True)
    ai_tokens_used = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["score"]),
            models.Index(fields=["ai_tag_status"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.email})"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "title": self.title,
            "linkedin_url": self.linkedin_url,
            "location": self.location,
            "source": self.source,
            "score": self.score,
            "ai_tags": self.ai_tags,
            "ai_persona": self.ai_persona,
            "ai_product_fit": self.ai_product_fit,
            "ai_urgency": self.ai_urgency,
            "ai_reasoning": self.ai_reasoning,
            "ai_tagged_at": self.ai_tagged_at.isoformat() if self.ai_tagged_at else None,
            "ai_tag_status": self.ai_tag_status,
            "ai_suggested_stage": self.ai_suggested_stage,
            "ai_confidence": self.ai_confidence,
            "ai_model_used": self.ai_model_used,
            "ai_tokens_used": self.ai_tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Lead(models.Model):
    """Through-model for Person <-> Product (IS_LEAD_FOR relationship)."""

    id = models.CharField(max_length=36, primary_key=True, default=_uuid)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="leads")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="leads")
    stage = models.CharField(max_length=100, default="New Lead")
    score = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("person", "product")]
        indexes = [
            models.Index(fields=["stage"]),
        ]

    def __str__(self):
        return f"{self.person.name} -> {self.product.name} ({self.stage})"


class Action(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=_uuid)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="actions")
    type = models.CharField(max_length=100)
    note = models.TextField(blank=True, default="")
    channel = models.CharField(max_length=100, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "note": self.note,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class ReferralSource(models.Model):
    """Through-model for Person <-> Source (REFERRED_FROM relationship)."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="referral_sources")
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="referrals")
    trigger = models.CharField(max_length=100, blank=True, default="")
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    event_count = models.IntegerField(default=1)

    class Meta:
        unique_together = [("person", "source")]


class Contact(models.Model):
    """Staging inbox for raw incoming contacts from RabbitMQ / external apps.
    Admin users classify these as person or business, then convert to leads."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("classified", "Classified"),
        ("converted", "Converted"),
        ("dismissed", "Dismissed"),
    ]
    TYPE_CHOICES = [
        ("", "Unclassified"),
        ("person", "Person"),
        ("business", "Business"),
    ]

    id = models.CharField(max_length=36, primary_key=True, default=_uuid)

    # Core contact fields
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    linkedin_url = models.CharField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    # Company info from event
    company_name = models.CharField(max_length=255, blank=True, null=True)
    company_industry = models.CharField(max_length=255, blank=True, null=True)
    company_size = models.CharField(max_length=100, blank=True, null=True)
    company_website = models.CharField(max_length=500, blank=True, null=True)

    # Event metadata
    source_app = models.CharField(max_length=100, blank=True, null=True)
    source_product = models.CharField(max_length=255, blank=True, null=True)
    trigger = models.CharField(max_length=100, blank=True, null=True)
    score_hints = models.JSONField(default=dict, blank=True)
    raw_context = models.TextField(blank=True, default="")

    # Classification & status
    contact_type = models.CharField(max_length=10, choices=TYPE_CHOICES, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Link to created records (set after classify/convert)
    person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="source_contacts"
    )
    business = models.ForeignKey(
        Business, on_delete=models.SET_NULL, null=True, blank=True, related_name="source_contacts"
    )

    classified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["contact_type"]),
            models.Index(fields=["source_app"]),
            models.Index(fields=["source_product"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.email or 'no email'}) [{self.status}]"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "title": self.title,
            "linkedin_url": self.linkedin_url,
            "location": self.location,
            "company_name": self.company_name,
            "company_industry": self.company_industry,
            "company_size": self.company_size,
            "company_website": self.company_website,
            "source_app": self.source_app,
            "source_product": self.source_product,
            "trigger": self.trigger,
            "raw_context": self.raw_context,
            "contact_type": self.contact_type,
            "status": self.status,
            "person_id": self.person_id,
            "business_id": self.business_id,
            "classified_at": self.classified_at.isoformat() if self.classified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
