"""
Cross-process pub/sub for discovery broadcasts.

The web service holds WebSocket clients in memory (websocket_manager.manager).
The worker process scores tokens but has no in-memory access to those clients.
Redis pub/sub bridges the gap:

    Worker:  publish_token_update(signal)  ->  redis PUBLISH discovery:tokens <json>
    Web:     subscribe_and_fanout()        ->  redis SUBSCRIBE discovery:tokens
                                              -> manager.broadcast({"type": "token", "data": ...})

Worker uses the sync redis client (matches Celery's sync execution model).
Web uses redis.asyncio so the subscribe loop integrates with the FastAPI event loop.
"""
import asyncio
import json
import logging
import os
from typing import Optional

import redis  # sync client (for worker publish)
import redis.asyncio as aioredis  # async client (for web subscribe)

from core.websocket_manager import manager
from schemas.discovery import TokenFeedItem

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DISCOVERY_CHANNEL = "discovery:tokens"


def publish_token_update(signal) -> None:
    """
    Worker-side publish: serialize a TokenSignal into a TokenFeedItem and
    publish to the discovery channel for fan-out by the web service.

    Per-call client open/close — simplest pattern for Celery's prefork workers
    where module-level connections don't survive fork cleanly.
    TODO(scaling): cache Redis publisher at module level if connection overhead becomes measurable.
    """
    payload = TokenFeedItem.from_signal(signal).model_dump_json()
    client = redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
    try:
        client.publish(DISCOVERY_CHANNEL, payload)
    finally:
        try:
            client.close()
        except Exception:
            pass


async def subscribe_and_fanout() -> None:
    """
    Web-side subscribe loop: subscribe to the discovery channel and broadcast
    each received message (wrapped in the typed envelope) to all WebSocket
    clients via the in-memory ConnectionManager.

    Resilient to Redis disconnects: reconnects with exponential backoff
    (1s -> 30s cap). Backoff resets to 1s after a successfully received
    message.

    Cancellation: when FastAPI shuts down the lifespan task,
    asyncio.CancelledError propagates from inside `pubsub.listen()` and we
    clean up the client before re-raising.
    """
    backoff = 1.0
    max_backoff = 30.0
    while True:
        client: Optional[aioredis.Redis] = None
        pubsub = None
        try:
            client = aioredis.from_url(
                REDIS_URL,
                socket_connect_timeout=3,
                # No socket_timeout: pubsub.listen() blocks indefinitely waiting for messages.
            )
            pubsub = client.pubsub()
            await pubsub.subscribe(DISCOVERY_CHANNEL)
            logger.info("pubsub: subscribed to %s", DISCOVERY_CHANNEL)

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    # Skip subscribe-confirmation and other non-payload frames.
                    continue
                raw = message.get("data")
                if raw is None:
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    data = json.loads(raw)
                except Exception as parse_err:
                    logger.warning(
                        "pubsub: malformed message dropped (%s): %r",
                        parse_err, raw[:200],
                    )
                    continue
                envelope = {"type": "token", "data": data}
                try:
                    await manager.broadcast(envelope)
                except Exception as send_err:
                    logger.warning("pubsub: ws broadcast failed: %s", send_err)
                # Reset backoff after each successful receive+fanout.
                backoff = 1.0

        except asyncio.CancelledError:
            logger.info("pubsub: subscriber cancelled, shutting down")
            raise
        except Exception as e:
            logger.warning(
                "pubsub: subscriber loop error, reconnecting in %.1fs: %s",
                backoff, e,
            )
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                raise
            backoff = min(backoff * 2, max_backoff)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(DISCOVERY_CHANNEL)
                except Exception:
                    pass
                try:
                    await pubsub.aclose()
                except Exception:
                    pass
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass
