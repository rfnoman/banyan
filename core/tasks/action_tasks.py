import logging

from celery import shared_task

from core.db.queries import log_action

logger = logging.getLogger(__name__)


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def process_action_logged(self, event_data: dict):
    person_id = event_data.get("person_id")
    action_type = event_data.get("action_type", "unknown")
    note = event_data.get("note", "")
    channel = event_data.get("channel", "")

    if not person_id:
        logger.warning("process_action_logged: missing person_id in event_data")
        return {"error": "missing person_id"}

    action_id = log_action(person_id, action_type, note, channel)
    logger.info("Action logged: person_id=%s type=%s action_id=%s", person_id, action_type, action_id)
    return {"action_id": action_id, "person_id": person_id, "action_type": action_type}
