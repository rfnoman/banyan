import logging
from core.messaging.events import LeadCreatedEvent, PersonData, CompanyData
from core.messaging.publisher import CRMPublisher

logger = logging.getLogger(__name__)


def on_contact_updated(contact: dict):
    raw_context = (
        f"{contact['name']} is a {contact.get('title', 'professional')} at {contact.get('company', 'an organization')}. "
        f"They updated their profile. Industry: {contact.get('industry', 'Unknown')}. "
        f"Note from app: {contact.get('notes', '')}"
    )
    event = LeadCreatedEvent(
        source_app="bookkeeper",
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
        trigger="contact_updated",
        score_hints={"is_paid": contact.get("is_paid", False)},
        raw_context=raw_context,
    )
    _publish(event)


def on_business_signup(business: dict):
    raw_context = (
        f"New business signup: {business['name']}, "
        f"industry: {business.get('industry', 'Unknown')}, "
        f"plan: {business.get('plan', 'Unknown')}, "
        f"size: {business.get('size', 'Unknown')} employees."
    )
    event = LeadCreatedEvent(
        source_app="bookkeeper",
        source_product=business.get("product", "ProductA"),
        person=PersonData(
            name=business.get("contact_name", business["name"]),
            email=business.get("contact_email", f"signup@{business['name'].lower().replace(' ', '')}.com"),
            title=business.get("contact_title"),
            company=business["name"],
        ),
        company=CompanyData(
            name=business["name"],
            industry=business.get("industry"),
            size=business.get("size"),
            website=business.get("website"),
        ),
        trigger="business_signup",
        score_hints={"is_paid": business.get("plan") not in (None, "free")},
        raw_context=raw_context,
    )
    _publish(event)


def on_invoice_sent(invoice: dict):
    raw_context = (
        f"{invoice.get('contact_name', 'A contact')} received an invoice of {invoice.get('amount', '?')} "
        f"from {invoice.get('company_name', 'Unknown')}. "
        f"Invoice status: {invoice.get('status', 'sent')}. "
        f"Product: {invoice.get('product_line', 'Unknown')}."
    )
    event = LeadCreatedEvent(
        source_app="bookkeeper",
        source_product=invoice.get("product", "ProductA"),
        person=PersonData(
            name=invoice.get("contact_name", "Unknown"),
            email=invoice.get("contact_email", "unknown@example.com"),
            company=invoice.get("company_name"),
        ),
        company=CompanyData(
            name=invoice.get("company_name", "Unknown"),
        ),
        trigger="invoice_sent",
        score_hints={"is_paid": invoice.get("status") == "paid"},
        raw_context=raw_context,
    )
    _publish(event)


def _publish(event: LeadCreatedEvent):
    try:
        with CRMPublisher() as pub:
            pub.publish_lead(event)
        logger.info("Bookkeeper event published: %s for %s", event.trigger, event.person.email)
    except Exception as exc:
        logger.error("Failed to publish Bookkeeper event: %s", exc)
