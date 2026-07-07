"""
WebSocket routes.

GET /ws/discovery — realtime feed of scored tokens. The connection receives
broadcast messages fanned out from the worker via core.pubsub
(subscribe_and_fanout is started by main.lifespan).

Tier gating (M2): realtime "token" envelopes are sent to paid tiers only
(core/pubsub uses manager.send_to_tier("pro", ...)). Clients pass their JWT
as a `?token=` query param — browsers can't set an Authorization header on
a WebSocket handshake. Anonymous / free / invalid-token connections are
accepted (they still get pings) but receive no realtime tokens; the
frontend's polling fallback serves them the delayed REST feed.
"""
import asyncio
import logging
from typing import Optional, Tuple

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from core.database import SessionLocal
from core.security import decode_access_token
from core.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Application-level heartbeat cadence. Some NAT/proxy paths drop idle
# connections at ~60s of silence; 25s keeps two pings inside that budget.
HEARTBEAT_INTERVAL_S = 25


def _resolve_tier(token: Optional[str]) -> Tuple[Optional[str], str]:
    """Resolve a JWT to (user_id, tier); anonymous/invalid -> (None, "free")."""
    if not token:
        return None, "free"
    user_id = decode_access_token(token)
    if user_id is None:
        return None, "free"
    db = SessionLocal()
    try:
        from models.user import User

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None, "free"
        return user.id, user.subscription_tier or "free"
    finally:
        db.close()


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
async def discovery_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT for tier-gated realtime."),
) -> None:
    """
    Subscribe to the discovery token feed.

    Messages sent to the client are envelopes of the form
    {"type": "<event>", "data": <payload>}.
    Paid tiers receive {"type": "token", ...} broadcasts; everyone receives
    periodic {"type": "ping"} heartbeats.

    Inbound messages from the client are accepted but ignored in v1
    (no client-to-server protocol yet).
    """
    user_id, tier = _resolve_tier(token)
    await manager.connect(websocket, user_id=user_id, tier=tier)
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
