import json
import logging
import time

import pika
from django.conf import settings

from .routing import EXCHANGE_NAME, EXCHANGE_TYPE, QUEUES_CONFIG, QUEUE_DEADLETTER

logger = logging.getLogger(__name__)


class BaseConsumer:
    queue_name: str = None
    prefetch_count: int = 1

    def __init__(self):
        if not self.queue_name:
            raise ValueError("queue_name must be set on the consumer subclass")
        self.rabbitmq_url = settings.RABBITMQ_URL
        self._connection = None
        self._channel = None

    def _connect(self):
        params = pika.URLParameters(self.rabbitmq_url)
        params.heartbeat = 60
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()

        self._channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type=EXCHANGE_TYPE,
            durable=True,
        )
        for q_name, config in QUEUES_CONFIG.items():
            self._channel.queue_declare(queue=q_name, durable=config["durable"])
            for routing_key in config["routing_keys"]:
                self._channel.queue_bind(
                    exchange=EXCHANGE_NAME,
                    queue=q_name,
                    routing_key=routing_key,
                )

        self._channel.basic_qos(prefetch_count=self.prefetch_count)
        self._channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self._on_message,
        )

    def _on_message(self, channel, method, properties, body):
        try:
            payload = json.loads(body)
            self.handle(payload)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            logger.exception("Error handling message from %s: %s", self.queue_name, exc)
            self._send_to_dlq(body, str(exc))
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _send_to_dlq(self, body: bytes, error: str):
        try:
            self._channel.queue_declare(queue=QUEUE_DEADLETTER, durable=True)
            self._channel.basic_publish(
                exchange="",
                routing_key=QUEUE_DEADLETTER,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers={"x-error": error[:500]},
                ),
            )
        except Exception:
            logger.exception("Failed to send to DLQ")

    def handle(self, payload: dict):
        raise NotImplementedError("Subclasses must implement handle()")

    def run(self):
        while True:
            try:
                logger.info("Connecting to RabbitMQ, queue=%s", self.queue_name)
                self._connect()
                logger.info("Waiting for messages on %s...", self.queue_name)
                self._channel.start_consuming()
            except pika.exceptions.AMQPConnectionError as exc:
                logger.warning("Connection lost: %s. Reconnecting in 5s...", exc)
                time.sleep(5)
            except KeyboardInterrupt:
                logger.info("Consumer stopped.")
                if self._connection and not self._connection.is_closed:
                    self._connection.close()
                break
