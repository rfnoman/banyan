"""
PostgreSQL query layer — mirrors core/graph/queries.py function signatures and return shapes.
All functions return plain dicts matching the exact structure templates and API views expect.
"""
import json
import uuid
from datetime import datetime, timezone

from django.db.models import Avg, Count, F, Q

from core.models import (
    Action,
    Business,
    Contact,
    Lead,
    Person,
    Product,
    ReferralSource,
    Source,
)

IMPORT_SOURCES = ["apify_linkedin", "csv_import", "xlsx_import", "api_external"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------- Write functions ---------------


def create_or_merge_person(data: dict) -> str:
    """Create or update a Person by email. Returns person_id."""
    person_id = data.get("id") or str(uuid.uuid4())
    email = data.get("email", "")

    defaults = {
        "name": data.get("name", ""),
        "title": data.get("title"),
        "source": data.get("source"),
        "score": float(data.get("score", 0)),
    }
    # Only update these if provided (preserve existing values)
    if data.get("linkedin_url") is not None:
        defaults["linkedin_url"] = data["linkedin_url"]
    if data.get("location") is not None:
        defaults["location"] = data["location"]

    person, created = Person.objects.update_or_create(
        email=email,
        defaults=defaults,
        create_defaults={**defaults, "id": person_id},
    )
    return person.id


def create_or_merge_business(data: dict) -> str:
    """Create or update a Business by name. Returns business_id."""
    business_id = data.get("id") or str(uuid.uuid4())
    name = data.get("name", "")

    defaults = {}
    if data.get("industry") is not None:
        defaults["industry"] = data["industry"]
    if data.get("size") is not None:
        defaults["size"] = data["size"]
    if data.get("website") is not None:
        defaults["website"] = data["website"]
    if data.get("location") is not None:
        defaults["location"] = data["location"]

    business, created = Business.objects.update_or_create(
        name=name,
        defaults=defaults,
        create_defaults={**defaults, "id": business_id},
    )
    return business.id


def create_or_merge_product(data: dict) -> str:
    """Create or update a Product by name. Returns product_id."""
    product_id = data.get("id") or str(uuid.uuid4())
    name = data.get("name", "")

    defaults = {}
    if data.get("url") is not None:
        defaults["url"] = data["url"]
    if data.get("description") is not None:
        defaults["description"] = data["description"]

    product, created = Product.objects.update_or_create(
        name=name,
        defaults=defaults,
        create_defaults={**defaults, "id": product_id},
    )
    return product.id


def link_person_to_business(person_id: str, business_id: str):
    """Set the person's company FK (WORKS_AT equivalent)."""
    Person.objects.filter(id=person_id).update(company_id=business_id)


def create_lead_relationship(person_id: str, product_name: str, stage: str, score: float):
    """Create IS_LEAD_FOR relationship via Lead model."""
    product, _ = Product.objects.get_or_create(
        name=product_name,
        defaults={"id": str(uuid.uuid4())},
    )
    Lead.objects.update_or_create(
        person_id=person_id,
        product=product,
        defaults={"stage": stage, "score": score},
    )


def log_action(person_id: str, action_type: str, note: str = "", channel: str = "") -> str:
    """Create an Action node. Returns action_id."""
    action = Action.objects.create(
        person_id=person_id,
        type=action_type,
        note=note,
        channel=channel,
    )
    return action.id


def update_ai_tags(person_id: str, ai_result: dict):
    """Update AI tagging fields on a Person."""
    tags = ai_result.get("tags", [])
    # Store as native list in JSONField (not JSON string)
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []

    Person.objects.filter(id=person_id).update(
        ai_tags=tags,
        ai_persona=ai_result.get("persona", ""),
        ai_product_fit=ai_result.get("product_fit", ""),
        ai_urgency=ai_result.get("urgency", "medium"),
        ai_reasoning=ai_result.get("reasoning", ""),
        ai_tagged_at=ai_result.get("ai_tagged_at", _now()),
        ai_tag_status=ai_result.get("ai_tag_status", "auto"),
        ai_suggested_stage=ai_result.get("suggested_stage", ""),
        ai_confidence=float(ai_result.get("confidence", 0.0)),
        ai_model_used=ai_result.get("model_used", ""),
        ai_tokens_used=int(ai_result.get("tokens_used", 0)),
    )


def update_person_score(person_id: str, score: float):
    Person.objects.filter(id=person_id).update(score=score)


def update_lead_stage(person_id: str, stage: str) -> int:
    """Update stage on all leads for a person. Returns count updated."""
    return Lead.objects.filter(person_id=person_id).update(stage=stage)


def update_product(product_id: str, data: dict):
    Product.objects.filter(id=product_id).update(
        url=data.get("url"),
        description=data.get("description"),
    )


def delete_product(product_id: str):
    Product.objects.filter(id=product_id).delete()


def bulk_link_people_to_business(person_ids: list[str], business_id: str):
    Person.objects.filter(id__in=person_ids).update(company_id=business_id)


def add_referral_source(person_id: str, source_app: str, trigger: str):
    """Track that this person was referred from a specific external app."""
    source, _ = Source.objects.get_or_create(
        name=source_app,
        defaults={"id": str(uuid.uuid4())},
    )
    ref, created = ReferralSource.objects.get_or_create(
        person_id=person_id,
        source=source,
        defaults={"trigger": trigger},
    )
    if not created:
        ReferralSource.objects.filter(pk=ref.pk).update(
            event_count=F("event_count") + 1,
            trigger=trigger,
        )


# --------------- Read functions ---------------


def get_all_people(limit: int = 100, offset: int = 0) -> list:
    qs = Person.objects.select_related("company").order_by("-created_at")[offset:offset + limit]
    people = []
    for p in qs:
        person = p.to_dict()
        if p.company:
            person["company"] = p.company.to_dict()
        people.append(person)
    return people


def get_all_businesses(limit: int = 100, offset: int = 0) -> list:
    qs = Business.objects.all().order_by("-created_at")[offset:offset + limit]
    return [b.to_dict() for b in qs]


def get_all_products(limit: int = 500, offset: int = 0) -> list:
    qs = Product.objects.all().order_by("name")[offset:offset + limit]
    return [p.to_dict() for p in qs]


def get_person_with_connections(person_id: str) -> dict:
    try:
        person = Person.objects.select_related("company").prefetch_related(
            "leads__product", "actions"
        ).get(id=person_id)
    except Person.DoesNotExist:
        return {}

    result = person.to_dict()
    result["company"] = person.company.to_dict() if person.company else {}
    result["products"] = [lead.product.to_dict() for lead in person.leads.all()]
    result["actions"] = [a.to_dict() for a in person.actions.all()]
    return result


def get_business_by_id(business_id: str) -> dict:
    try:
        return Business.objects.get(id=business_id).to_dict()
    except Business.DoesNotExist:
        return {}


def get_people_by_business(business_id: str) -> list:
    qs = Person.objects.filter(company_id=business_id).order_by("name")
    return [p.to_dict() for p in qs]


def get_leads(
    product: str = None,
    stage: str = None,
    score_min: float = None,
    ai_persona: str = None,
    limit: int = 100,
) -> list:
    qs = Lead.objects.select_related("person", "person__company", "product").order_by(
        "-person__score"
    )

    if product:
        qs = qs.filter(product__name=product)
    if stage:
        qs = qs.filter(stage=stage)
    if score_min is not None:
        qs = qs.filter(person__score__gte=score_min)
    if ai_persona:
        qs = qs.filter(person__ai_persona=ai_persona)

    qs = qs[:limit]

    leads = []
    for lead in qs:
        person = lead.person.to_dict()
        person["lead_stage"] = lead.stage
        person["product"] = lead.product.to_dict()
        person["company"] = lead.person.company.to_dict() if lead.person.company else {}
        leads.append(person)
    return leads


def get_analytics_summary() -> dict:
    people_count = Person.objects.count()
    businesses_count = Business.objects.count()
    leads_count = Lead.objects.count()

    avg_result = Person.objects.filter(score__gt=0).aggregate(avg_score=Avg("score"))
    avg_score = round(avg_result["avg_score"] or 0, 2)

    stage_dist = (
        Lead.objects.values("stage")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return {
        "people": people_count,
        "businesses": businesses_count,
        "leads": leads_count,
        "avg_score": avg_score,
        "stage_distribution": [
            {"stage": row["stage"], "count": row["count"]} for row in stage_dist
        ],
    }


def get_pending_ai_tagging(limit: int = 50) -> list:
    qs = Person.objects.filter(
        Q(ai_tag_status__isnull=True) | Q(ai_tag_status="")
    ).values("id", "name", "email")[:limit]
    return list(qs)


def get_ai_tag_history(person_id: str) -> list:
    try:
        p = Person.objects.get(id=person_id)
    except Person.DoesNotExist:
        return []

    if not p.ai_tagged_at:
        return []

    tags = p.ai_tags
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []

    return [
        {
            "tags": tags or [],
            "persona": p.ai_persona,
            "product_fit": p.ai_product_fit,
            "urgency": p.ai_urgency,
            "reasoning": p.ai_reasoning,
            "ai_tagged_at": p.ai_tagged_at.isoformat() if p.ai_tagged_at else None,
            "ai_tag_status": p.ai_tag_status,
            "suggested_stage": p.ai_suggested_stage,
            "confidence": p.ai_confidence,
            "model_used": p.ai_model_used,
            "tokens_used": p.ai_tokens_used,
        }
    ]


def get_product_by_id(product_id: str) -> dict:
    try:
        return Product.objects.get(id=product_id).to_dict()
    except Product.DoesNotExist:
        return {}


def get_product_with_leads(product_id: str) -> dict:
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return {}

    result = product.to_dict()
    leads_qs = Lead.objects.filter(product=product).select_related("person", "person__company")
    leads = []
    for lead in leads_qs:
        entry = lead.person.to_dict()
        entry["lead_stage"] = lead.stage
        entry["lead_score"] = lead.score
        entry["company"] = lead.person.company.to_dict() if lead.person.company else {}
        leads.append(entry)
    result["leads"] = leads
    return result


def get_imported_people(
    sources: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    search: str = "",
) -> list:
    sources = sources or IMPORT_SOURCES
    qs = Person.objects.filter(source__in=sources).select_related("company").order_by("-created_at")

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))

    qs = qs[offset:offset + limit]

    people = []
    for p in qs:
        person = p.to_dict()
        person["company_name"] = p.company.name if p.company else ""
        people.append(person)
    return people


def get_imported_people_count(
    sources: list[str] | None = None,
    search: str = "",
) -> int:
    sources = sources or IMPORT_SOURCES
    qs = Person.objects.filter(source__in=sources)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))
    return qs.count()


def get_person_referral_sources(person_id: str) -> list[dict]:
    """Get all apps that referred this person, with timestamps."""
    qs = ReferralSource.objects.filter(person_id=person_id).select_related("source").order_by(
        "first_seen"
    )
    return [
        {
            "source": ref.source.name,
            "first_seen": ref.first_seen.isoformat() if ref.first_seen else None,
            "last_seen": ref.last_seen.isoformat() if ref.last_seen else None,
            "event_count": ref.event_count,
            "trigger": ref.trigger,
        }
        for ref in qs
    ]


# --------------- Contact staging functions ---------------


def create_contact(data: dict) -> str:
    """Create a Contact staging record from an incoming event. Returns contact_id."""
    contact = Contact.objects.create(
        name=data.get("name", ""),
        email=data.get("email"),
        title=data.get("title"),
        linkedin_url=data.get("linkedin_url"),
        location=data.get("location"),
        company_name=data.get("company_name"),
        company_industry=data.get("company_industry"),
        company_size=data.get("company_size"),
        company_website=data.get("company_website"),
        source_app=data.get("source_app"),
        source_product=data.get("source_product"),
        trigger=data.get("trigger"),
        score_hints=data.get("score_hints") or {},
        raw_context=data.get("raw_context", ""),
    )
    return contact.id


def classify_contact(contact_id: str, contact_type: str, classified_by: str, overrides: dict | None = None) -> dict:
    """Classify a pending contact as person or business.
    Creates the corresponding Person or Business record and links back.
    Optional overrides dict allows the caller to supply missing/corrected fields."""
    contact = Contact.objects.get(id=contact_id)

    # Apply any user-provided overrides to the contact before processing
    if overrides:
        for field in ("name", "email", "title", "linkedin_url", "location",
                       "company_name", "company_industry", "company_size", "company_website"):
            if overrides.get(field):
                setattr(contact, field, overrides[field])
        contact.save(update_fields=[f for f in ("name", "email", "title", "linkedin_url", "location",
                                                 "company_name", "company_industry", "company_size", "company_website")
                                     if overrides.get(f)])

    source = contact.source_product or contact.source_app

    if contact_type == "person":
        person_data = {
            "name": contact.name,
            "email": contact.email,
            "title": contact.title,
            "linkedin_url": contact.linkedin_url,
            "location": contact.location,
            "source": source,
        }
        person_id = create_or_merge_person(person_data)

        if contact.company_name:
            biz_data = {
                "name": contact.company_name,
                "industry": contact.company_industry,
                "size": contact.company_size,
                "website": contact.company_website,
            }
            business_id = create_or_merge_business(biz_data)
            link_person_to_business(person_id, business_id)
            contact.business_id = business_id

        if contact.source_app:
            add_referral_source(person_id, contact.source_app, contact.trigger or "")

        contact.person_id = person_id

    elif contact_type == "business":
        biz_data = {
            "name": contact.company_name or contact.name,
            "industry": contact.company_industry,
            "size": contact.company_size,
            "website": contact.company_website,
            "location": contact.location,
        }
        business_id = create_or_merge_business(biz_data)
        contact.business_id = business_id

    contact.contact_type = contact_type
    contact.status = "classified"
    contact.classified_at = datetime.now(timezone.utc)
    contact.save()

    return contact.to_dict()


def convert_contact_to_lead(contact_id: str, product_name: str, stage: str, score: float) -> dict:
    """Convert a classified person-type contact to a lead."""
    contact = Contact.objects.get(id=contact_id)

    if not contact.person_id:
        raise ValueError("Contact must be classified as a person before converting to lead.")

    product_name = product_name or contact.source_product or "General"
    create_lead_relationship(contact.person_id, product_name, stage, score)
    update_person_score(contact.person_id, score)

    contact.status = "converted"
    contact.save()

    return contact.to_dict()


def dismiss_contact(contact_id: str):
    """Dismiss a contact (mark as not useful)."""
    Contact.objects.filter(id=contact_id).update(status="dismissed")


def bulk_classify_contacts(contact_ids: list[str], contact_type: str, classified_by: str) -> int:
    """Classify multiple contacts. Returns count classified."""
    count = 0
    for cid in contact_ids:
        try:
            classify_contact(cid, contact_type, classified_by)
            count += 1
        except Exception:
            pass
    return count


def bulk_dismiss_contacts(contact_ids: list[str]):
    """Dismiss multiple contacts."""
    Contact.objects.filter(id__in=contact_ids).update(status="dismissed")


def get_all_contacts(
    status: str = "",
    contact_type: str = "",
    source_app: str = "",
    search: str = "",
    limit: int = 25,
    offset: int = 0,
) -> list:
    qs = Contact.objects.all()

    if status:
        qs = qs.filter(status=status)
    if contact_type:
        qs = qs.filter(contact_type=contact_type)
    if source_app:
        qs = qs.filter(source_app=source_app)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))

    qs = qs[offset:offset + limit]
    return [c.to_dict() for c in qs]


def get_contacts_count(
    status: str = "",
    contact_type: str = "",
    source_app: str = "",
    search: str = "",
) -> int:
    qs = Contact.objects.all()

    if status:
        qs = qs.filter(status=status)
    if contact_type:
        qs = qs.filter(contact_type=contact_type)
    if source_app:
        qs = qs.filter(source_app=source_app)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))

    return qs.count()


def get_contact_source_apps() -> list[str]:
    """Get distinct source_app values for the filter dropdown."""
    return list(
        Contact.objects.exclude(source_app__isnull=True)
        .exclude(source_app="")
        .values_list("source_app", flat=True)
        .distinct()
        .order_by("source_app")
    )
