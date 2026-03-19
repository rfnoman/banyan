import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings

from core.db.queries import get_analytics_summary

logger = logging.getLogger(__name__)


class AnalyticsSummaryView(APIView):
    def get(self, request):
        summary = get_analytics_summary()
        return Response(summary)


class AnalyticsEventsView(APIView):
    def get(self, request):
        limit = int(request.query_params.get("limit", 50))
        events = _query_recent_events(limit)
        return Response(events)


def _query_recent_events(limit: int) -> list:
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
    #     rows = client.execute(
    #         f"""
    #         SELECT person_id, event_type, source_app, score, stage, timestamp
    #         FROM lead_events
    #         ORDER BY timestamp DESC
    #         LIMIT {limit}
    #         """
    #     )
    #     return [
    #         {
    #             "person_id": r[0],
    #             "event_type": r[1],
    #             "source_app": r[2],
    #             "score": r[3],
    #             "stage": r[4],
    #             "timestamp": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
    #         }
    #         for r in rows
    #     ]
    # except Exception as exc:
    #     logger.warning("ClickHouse events query failed: %s", exc)
    #     return []
    logger.debug("ClickHouse disabled — returning empty events list")
    return []
