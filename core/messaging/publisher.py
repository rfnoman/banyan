import json
import logging
import time
from datetime import datetime, timezone

import pika
from django.conf import settings

from .routing import EXCHANGE_NAME, EXCHANGE_TYPE, QUEUES_CONFIG
from .events import LeadCreatedEvent, LeadSavedEvent, ActionLoggedEvent, CompanyUpdatedEvent, AITagRequestEvent

logger = logging.getLogger(__name__)


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class CRMPublisher:
    def __init__(self):
        self.rabbitmq_url = settings.RABBITMQ_URL
        self._connection = None
        self._channel = None

    def _connect(self, attempt: int = 1, max_attempts: int = 3):
        try:
            params = pika.URLParameters(self.rabbitmq_url)
            params.heartbeat = 60
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            self._declare_topology()
        except Exception as exc:
            if attempt >= max_attempts:
                raise
            wait = 2 ** attempt
            logger.warning("RabbitMQ connect attempt %d failed (%s). Retrying in %ds.", attempt, exc, wait)
            time.sleep(wait)
            self._connect(attempt + 1, max_attempts)

    def _declare_topology(self):
        self._channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type=EXCHANGE_TYPE,
            durable=True,
        )
        for queue_name, config in QUEUES_CONFIG.items():
            self._channel.queue_declare(queue=queue_name, durable=config["durable"])
            for routing_key in config["routing_keys"]:
                self._channel.queue_bind(
                    exchange=EXCHANGE_NAME,
                    queue=queue_name,
                    routing_key=routing_key,
                )

    def _get_channel(self):
        if self._connection is None or self._connection.is_closed:
            self._connect()
        return self._channel

    def _publish(self, routing_key: str, payload: dict):
        channel = self._get_channel()
        body = json.dumps(payload, default=_json_default)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=body.encode(),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        logger.info("Published to %s: %s", routing_key, routing_key)

    def publish_lead(self, event: LeadCreatedEvent):
        routing_key = f"lead.created.{event.source_app}"
        self._publish(routing_key, event.model_dump())

    def publish_lead_saved(self, event: LeadSavedEvent):
        routing_key = f"lead.saved.{event.source_app}"
        self._publish(routing_key, event.model_dump())

    def publish_action(self, event: ActionLoggedEvent):
        routing_key = f"action.logged.{event.source_app or 'crm'}"
        self._publish(routing_key, event.model_dump())

    def publish_company(self, event: CompanyUpdatedEvent):
        routing_key = f"company.updated.{event.source_app or 'crm'}"
        self._publish(routing_key, event.model_dump())

    def publish_ai_tag_request(self, event: AITagRequestEvent):
        self._publish("lead.tag_requested", event.model_dump())

    def close(self):
        if self._connection and not self._connection.is_closed:
            self._connection.close()

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *args):
        self.close()
