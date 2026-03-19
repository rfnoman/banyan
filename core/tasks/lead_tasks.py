import logging
from datetime import datetime, timezone

from celery import shared_task
from django.conf import settings

from core.messaging.events import LeadCreatedEvent, LeadSavedEvent
from django.db import transaction
from core.db.queries import (
    add_referral_source,
    create_contact,
    create_or_merge_person,
    create_or_merge_business,
    link_person_to_business,
    create_lead_relationship,
    update_person_score,
    get_person_with_connections,
)

logger = logging.getLogger(__name__)


def _compute_initial_score(event: LeadCreatedEvent) -> float:
    score = 40.0
    title = (event.person.title or "").lower()
    senior_titles = ("vp", "vice president", "director", "head of", "chief", "cto", "ceo", "coo", "cfo", "founder")
    if any(t in title for t in senior_titles):
        score += 20

    score_hints = event.score_hints or {}
    if score_hints.get("is_paid"):
        score += 15

    size_str = event.company.size or ""
    try:
        size = int("".join(filter(str.isdigit, size_str)))
        if size >= 100:
            score += 10
    except (ValueError, TypeError):
        pass

    if event.source_app and "linkedin" in event.source_app.lower():
        score += 10

    if event.person.linkedin_url:
        score += 5

    return min(score, 100.0)


def _write_to_clickhouse(person_id: str, event_type: str, source_app: str, score: float, stage: str):
    """Stub — ClickHouse integration disabled. Uncomment to re-enable."""
    # TODO: re-enable ClickHouse integration
    # try:
    #     from clickhouse_driver import Client
    #     client = Client(
    #         host=settings.CLICKHOUSE_HOST,
    #         port=settings.CLICKHOUSE_PORT,
    #         database=settings.CLICKHOUSE_DB,
    #         user=settings.CLICKHOUSE_USER,
    #         password=settings.CLICKHOUSE_PASSWORD,
    #     )
    #     client.execute(
    #         "INSERT INTO lead_events (person_id, event_type, source_app, score, stage, timestamp) VALUES",
    #         [{
    #             "person_id": person_id,
    #             "event_type": event_type,
    #             "source_app": source_app,
    #             "score": score,
    #             "stage": stage,
    #             "timestamp": datetime.now(timezone.utc),
    #         }],
    #     )
    # except Exception as exc:
    #     logger.warning("ClickHouse write failed (non-fatal): %s", exc)
    logger.debug("ClickHouse disabled — skipping write for person_id=%s", person_id)


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def process_incoming_lead(self, event_data: dict):
    """Stage an incoming lead as a Contact for manual classification."""
    logger.info("Staging contact: %s", event_data.get("person", {}).get("email"))

    event = LeadCreatedEvent(**event_data)

    contact_data = {
        "name": event.person.name,
        "email": event.person.email,
        "title": event.person.title,
        "linkedin_url": event.person.linkedin_url,
        "location": event.person.location,
        "company_name": event.company.name,
        "company_industry": event.company.industry,
        "company_size": event.company.size,
        "company_website": event.company.website,
        "source_app": event.source_app,
        "source_product": event.source_product,
        "trigger": event.trigger,
        "score_hints": event.score_hints or {},
        "raw_context": event.raw_context,
    }
    contact_id = create_contact(contact_data)

    logger.info("Contact staged: contact_id=%s", contact_id)
    return {"contact_id": contact_id, "status": "pending"}


def _publish_lead_saved(person_id: str, event: LeadCreatedEvent):
    try:
        from core.messaging.publisher import CRMPublisher
        saved_event = LeadSavedEvent(
            person_id=person_id,
            source_app=event.source_app,
            trigger=event.trigger,
            raw_context=event.raw_context,
        )
        with CRMPublisher() as pub:
            pub.publish_lead_saved(saved_event)
    except Exception as exc:
        logger.warning("Could not publish LeadSavedEvent: %s", exc)


def _publish_high_score_lead(person_id: str, score: float, event: LeadCreatedEvent):
    logger.info("High-score lead (%.1f) for person_id=%s", score, person_id)
