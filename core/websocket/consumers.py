import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

GROUP_NAME = "crm_live_feed"


class CRMConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()
        logger.info("WS connected: %s", self.channel_name)
        # Send last 10 lead events on connect
        recent = await self._get_recent_events()
        if recent:
            await self.send(text_data=json.dumps({"type": "recent_events", "events": recent}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)
        logger.info("WS disconnected: %s (code=%s)", self.channel_name, close_code)

    async def receive(self, text_data):
        pass

    # ── Group message handlers ────────────────────────────────────────────────

    async def new_lead(self, event):
        await self.send(text_data=json.dumps(event))

    async def ai_tags_ready(self, event):
        await self.send(text_data=json.dumps(event))

    async def ai_tags_overridden(self, event):
        await self.send(text_data=json.dumps(event))

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_recent_events(self) -> list:
        try:
            from asgiref.sync import sync_to_async
            from django.conf import settings
            from clickhouse_driver import Client

            def _fetch():
                client = Client(
                    host=settings.CLICKHOUSE_HOST,
                    port=settings.CLICKHOUSE_PORT,
                    database=settings.CLICKHOUSE_DB,
                    user=settings.CLICKHOUSE_USER,
                    password=settings.CLICKHOUSE_PASSWORD,
                )
                rows = client.execute(
                    "SELECT person_id, event_type, source_app, score, stage, timestamp "
                    "FROM lead_events ORDER BY timestamp DESC LIMIT 10"
                )
                return [
                    {
                        "type": "new_lead",
                        "person_id": r[0],
                        "event_type": r[1],
                        "source_app": r[2],
                        "score": r[3],
                        "stage": r[4],
                        "timestamp": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
                    }
                    for r in rows
                ]

            return await sync_to_async(_fetch)()
        except Exception as exc:
            logger.warning("Could not fetch recent events for WS: %s", exc)
            return []
