import logging
import threading

import pika
from django.conf import settings

from core.messaging.consumer import BaseConsumer
from core.messaging.routing import QUEUE_LEADS_LLM_TAGGING, QUEUE_AI_TAG_REQUESTED

logger = logging.getLogger(__name__)


class LLMTaggingConsumer(BaseConsumer):
    queue_name = QUEUE_LEADS_LLM_TAGGING

    def handle(self, payload: dict):
        from core.llm.tasks import tag_lead_with_llm
        person_id = payload.get("person_id")
        if not person_id:
            logger.warning("LLMTaggingConsumer: missing person_id in payload")
            return
        logger.info("Dispatching LLM tag task for person_id=%s", person_id)
        tag_lead_with_llm.delay(
            person_id=person_id,
            raw_context=payload.get("raw_context", ""),
            trigger=payload.get("trigger", ""),
            source_app=payload.get("source_app", ""),
        )


class AITagRequestConsumer(BaseConsumer):
    queue_name = QUEUE_AI_TAG_REQUESTED

    def handle(self, payload: dict):
        from core.llm.tasks import tag_lead_with_llm
        person_id = payload.get("person_id")
        requested_by = payload.get("requested_by", "unknown")
        if not person_id:
            logger.warning("AITagRequestConsumer: missing person_id in payload")
            return
        logger.info("Dispatching on-demand LLM retag for person_id=%s by=%s", person_id, requested_by)
        tag_lead_with_llm.delay(
            person_id=person_id,
            requested_by=requested_by,
        )


class LLMConsumer:
    """Runs both LLM consumers in separate threads."""

    def run(self):
        t1 = threading.Thread(target=LLMTaggingConsumer().run, daemon=True)
        t2 = threading.Thread(target=AITagRequestConsumer().run, daemon=True)
        t1.start()
        t2.start()
        logger.info("LLM consumers started on queues: %s, %s", QUEUE_LEADS_LLM_TAGGING, QUEUE_AI_TAG_REQUESTED)
        t1.join()
        t2.join()
