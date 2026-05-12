"""
WebSocket routes.

GET /ws/discovery — realtime feed of scored tokens. The connection receives
broadcast messages fanned out from the worker via core.pubsub
(subscribe_and_fanout is started by main.lifespan).

No auth in v1 — all connections register as tier="free". Auth lands in Phase 4
billing.

TODO(phase-2): add an explicit application-level heartbeat (e.g., periodic
ping/pong). v1 relies on Starlette/browser/proxy TCP defaults; some NAT/proxy
paths drop idle connections at ~60s of silence.
"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/discovery")
async def discovery_ws(websocket: WebSocket) -> None:
    """
    Subscribe to the discovery token feed.

    Messages sent to the client are envelopes of the form
    {"type": "<event>", "data": <payload>}.
    v1 only emits {"type": "token", "data": TokenFeedItem}.

    Inbound messages from the client are accepted but ignored in v1
    (no client-to-server protocol yet).
    """
    await manager.connect(websocket, user_id=None, tier="free")
    try:
        while True:
            # Drain inbound traffic; receive_text raises WebSocketDisconnect on close.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        # Race-safe disconnect (manager.disconnect is idempotent on missing keys),
        # then re-raise so the failure surfaces in logs.
        try:
            manager.disconnect(websocket)
        except Exception:
            pass
        raise
