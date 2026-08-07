"""
RabbitMQ Publisher/Consumer assíncrono usando aio-pika.
Também expõe helper para publicar mensagens de sync do Elasticsearch.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger("collector.queue")


class RabbitMQPublisher:
    """Publica mensagens JSON em exchanges/routing keys do RabbitMQ."""

    EXCHANGE = "licitaim"

    def __init__(self, url: str):
        self._url = url
        self._connection = None
        self._channel = None
        self._exchange = None

    async def connect(self) -> None:
        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self.EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            logger.info("RabbitMQ publisher conectado: %s", self._url)
        except Exception as exc:
            logger.warning("RabbitMQ publisher: não foi possível conectar (%s). "
                           "Mensagens serão descartadas.", exc)

    async def publish(self, routing_key: str, payload: dict) -> bool:
        if self._exchange is None:
            logger.debug("RabbitMQ offline — descartando mensagem: %s", routing_key)
            return False
        try:
            import aio_pika
            body = json.dumps(payload, ensure_ascii=False, default=str).encode()
            msg = aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await self._exchange.publish(msg, routing_key=routing_key)
            logger.debug("RabbitMQ publicado: %s", routing_key)
            return True
        except Exception as exc:
            logger.warning("RabbitMQ publish(%s): %s", routing_key, exc)
            return False

    async def close(self) -> None:
        try:
            if self._connection:
                await self._connection.close()
        except Exception:
            pass


class RabbitMQConsumer:
    """Consome mensagens de uma queue do RabbitMQ e delega ao handler."""

    EXCHANGE = "licitaim"

    def __init__(self, url: str, queue_name: str, routing_key: str):
        self._url = url
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._connection = None
        self._channel = None

    async def consume(
        self,
        handler: Callable[[dict], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Conecta ao RabbitMQ e processa mensagens indefinidamente.
        handler(payload: dict) é chamado para cada mensagem.
        """
        import aio_pika

        try:
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=10)

            exchange = await self._channel.declare_exchange(
                self.EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            queue = await self._channel.declare_queue(
                self._queue_name,
                durable=True,
            )
            await queue.bind(exchange, routing_key=self._routing_key)

            logger.info(
                "RabbitMQ consumer ouvindo '%s' (routing: %s)",
                self._queue_name, self._routing_key,
            )

            async with queue.iterator() as q_iter:
                async for message in q_iter:
                    async with message.process(requeue_on_timeout=True):
                        try:
                            payload = json.loads(message.body)
                            await handler(payload)
                        except Exception as exc:
                            logger.error("Consumer handler error: %s", exc)

        except Exception as exc:
            logger.error("RabbitMQ consumer falhou: %s", exc)
            await asyncio.sleep(5)

    async def close(self) -> None:
        try:
            if self._connection:
                await self._connection.close()
        except Exception:
            pass


# ── ES Sync consumer handler ──────────────────────────────────────────────────

async def es_sync_handler(payload: dict) -> None:
    """
    Handler RabbitMQ para eventos 'tender.upserted'.
    Indexa o tender no Elasticsearch via SyncService do backend.
    """
    import sys
    import os
    # Tenta importar o SyncService do backend (se no mesmo PYTHONPATH)
    backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "artifacts", "api-server")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    tender_id = payload.get("tender_id") or payload.get("external_id", "")
    if not tender_id:
        return

    try:
        from app.services.sync_service import get_sync_service
        svc = get_sync_service()
        await svc.sync_tender(tender_id)
        logger.info("ES sync via RabbitMQ: %s", tender_id)
    except Exception as exc:
        logger.warning("ES sync handler(%s): %s", tender_id, exc)


# ── Singleton publisher ────────────────────────────────────────────────────────

_publisher: Optional[RabbitMQPublisher] = None


def get_publisher() -> RabbitMQPublisher:
    global _publisher
    if _publisher is None:
        from .config import get_settings
        _publisher = RabbitMQPublisher(get_settings().get_broker_url())
    return _publisher


async def start_es_consumer() -> None:
    """Inicia consumer que processa eventos de sync do ES."""
    from .config import get_settings
    settings = get_settings()
    consumer = RabbitMQConsumer(
        url=settings.get_broker_url(),
        queue_name="licitaim.es.sync",
        routing_key="tender.sync",
    )
    await consumer.consume(es_sync_handler)
