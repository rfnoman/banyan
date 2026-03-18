import logging

from core.messaging.consumer import BaseConsumer
from core.messaging.routing import QUEUE_LEADS_INGEST

logger = logging.getLogger(__name__)


class LeadConsumer(BaseConsumer):
    queue_name = QUEUE_LEADS_INGEST

    def handle(self, payload: dict):
        email = payload.get("person", {}).get("email")
        logger.info("Dispatching lead task for: %s", email)
        try:
            from core.tasks.lead_tasks import process_incoming_lead
            process_incoming_lead.delay(payload)
        except Exception:
            logger.warning("Celery broker unavailable, running task inline for: %s", email)
            from core.db.queries import create_contact
            from core.messaging.events import LeadCreatedEvent
            event = LeadCreatedEvent(**payload)
            contact_id = create_contact({
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
            })
            logger.info("Contact staged inline: contact_id=%s", contact_id)
