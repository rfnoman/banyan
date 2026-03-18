import logging

from core.messaging.events import LeadCreatedEvent, PersonData, CompanyData
from core.messaging.publisher import CRMPublisher

logger = logging.getLogger(__name__)


def on_contact_created(contact: dict, source_app: str):
    """Handle a new contact from any external app."""
    raw_context = (
        f"{contact['name']} is a {contact.get('title', 'professional')} at "
        f"{contact.get('company', 'an organization')}. "
        f"New contact created via {source_app}. "
        f"Industry: {contact.get('industry', 'Unknown')}. "
        f"Note: {contact.get('notes', '')}"
    )
    event = _build_event(contact, source_app, "contact_created", raw_context)
    _publish(event, source_app)


def on_contact_updated(contact: dict, source_app: str):
    """Handle a contact update from any external app."""
    raw_context = (
        f"{contact['name']} is a {contact.get('title', 'professional')} at "
        f"{contact.get('company', 'an organization')}. "
        f"Contact updated via {source_app}. "
        f"Industry: {contact.get('industry', 'Unknown')}. "
        f"Note: {contact.get('notes', '')}"
    )
    event = _build_event(contact, source_app, "contact_updated", raw_context)
    _publish(event, source_app)


def _build_event(contact: dict, source_app: str, trigger: str, raw_context: str) -> LeadCreatedEvent:
    return LeadCreatedEvent(
        source_app=source_app,
        source_product=contact.get("product", "ProductA"),
        person=PersonData(
            name=contact["name"],
            email=contact["email"],
            title=contact.get("title"),
            company=contact.get("company"),
            linkedin_url=contact.get("linkedin_url"),
            location=contact.get("location"),
        ),
        company=CompanyData(
            name=contact.get("company", "Unknown"),
            industry=contact.get("industry"),
            size=contact.get("company_size"),
            website=contact.get("website"),
        ),
        trigger=trigger,
        score_hints={"is_paid": contact.get("is_paid", False)},
        raw_context=raw_context,
    )


def _publish(event: LeadCreatedEvent, source_app: str):
    try:
        with CRMPublisher() as pub:
            pub.publish_lead(event)
        logger.info("%s event published: %s for %s", source_app, event.trigger, event.person.email)
    except Exception as exc:
        logger.error("Failed to publish %s event: %s", source_app, exc)
