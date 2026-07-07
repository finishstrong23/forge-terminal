"""
WebSocket routes.

GET /ws/discovery — realtime feed of scored tokens. The connection receives
broadcast messages fanned out from the worker via core.pubsub
(subscribe_and_fanout is started by main.lifespan).

No auth in v1 — all connections register as tier="free". Auth lands in Phase 4
billing.
"""
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Application-level heartbeat cadence. Some NAT/proxy paths drop idle
# connections at ~60s of silence; 25s keeps two pings inside that budget.
HEARTBEAT_INTERVAL_S = 25


async def _heartbeat(websocket: WebSocket) -> None:
    """Send {"type": "ping"} envelopes until the socket errors or is cancelled.

    Clients ignore non-"token" envelopes; the ping exists purely to generate
    traffic so intermediaries keep the connection alive.
    """
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            await websocket.send_json({"type": "ping"})
    except asyncio.CancelledError:
        raise
    except Exception:
        # Socket closed or transport error — the receive loop handles the
        # disconnect; the heartbeat just stops.
        return


@router.websocket("/ws/discovery")
async def discovery_ws(websocket: WebSocket) -> None:
    """
    Subscribe to the discovery token feed.

    Messages sent to the client are envelopes of the form
    {"type": "<event>", "data": <payload>}.
    Emits {"type": "token", "data": TokenFeedItem} broadcasts and periodic
    {"type": "ping"} heartbeats.

    Inbound messages from the client are accepted but ignored in v1
    (no client-to-server protocol yet).
    """
    await manager.connect(websocket, user_id=None, tier="free")
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
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
    finally:
        heartbeat_task.cancel()
