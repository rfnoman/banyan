import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from django.conf import settings

from core.db.queries import update_person_score

logger = logging.getLogger(__name__)

ACTION_WEIGHTS = {
    "email_sent": 3,
    "email_opened": 5,
    "email_clicked": 8,
    "meeting_booked": 15,
    "demo_attended": 20,
    "proposal_sent": 10,
    "call_completed": 12,
    "linkedin_connected": 5,
}


def _query_clickhouse_actions(person_id: str) -> list:
    """Stub — ClickHouse integration disabled. Returns empty list."""
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
    #     cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    #     rows = client.execute(
    #         """
    #         SELECT event_type, score, stage, timestamp
    #         FROM lead_events
    #         WHERE person_id = %(person_id)s AND timestamp >= %(cutoff)s
    #         ORDER BY timestamp DESC
    #         """,
    #         {"person_id": person_id, "cutoff": cutoff},
    #     )
    #     return rows
    # except Exception as exc:
    #     logger.warning("ClickHouse query failed: %s", exc)
    #     return []
    logger.debug("ClickHouse disabled — returning empty actions for person_id=%s", person_id)
    return []


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def recalculate_lead_score(self, person_id: str) -> float:
    rows = _query_clickhouse_actions(person_id)

    base_score = 40.0
    action_bonus = 0.0
    for row in rows:
        event_type = row[0] if isinstance(row, (list, tuple)) else row.get("event_type", "")
        action_bonus += ACTION_WEIGHTS.get(event_type, 1)

    new_score = min(base_score + action_bonus, 100.0)
    update_person_score(person_id, new_score)
    logger.info("Score recalculated: person_id=%s new_score=%.1f", person_id, new_score)
    return new_score
