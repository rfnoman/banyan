import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


@shared_task(
    queue="llm",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def tag_lead_with_llm(self, person_id: str, raw_context: str = "",
                      trigger: str = "", source_app: str = "",
                      requested_by: str = None):
    from core.llm.tagger import LeadTagger

    tagger = LeadTagger()
    if requested_by:
        result = tagger.retag_person(person_id, requested_by)
    else:
        result = tagger.tag_person(person_id, raw_context, trigger, source_app)

    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "crm_live_feed",
            {
                "type": "ai_tags_ready",
                "person_id": person_id,
                "tags": result.tags,
                "persona": result.persona,
                "product_fit": result.product_fit,
                "urgency": result.urgency,
                "reasoning": result.reasoning,
                "confidence": result.confidence,
                "suggested_stage": result.suggested_stage,
            },
        )
    except Exception as exc:
        logger.warning("Could not broadcast ai_tags_ready: %s", exc)

    return result.model_dump()
