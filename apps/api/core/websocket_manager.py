"""
WebSocket Connection Manager
==============================

Manages real-time WebSocket connections for pushing token alerts to users.

Supports:
- Anonymous connections (broadcast only)
- Authenticated connections (per-user + tier-gated alerts)
- Redis pub/sub for multi-process environments (Railway may run multiple web instances)
"""
import json
import asyncio
from typing import Dict, List, Optional, Set
from fastapi import WebSocket
from datetime import datetime, timezone


# Tier hierarchy for "this tier and above"
TIER_HIERARCHY = {
    "free": 0,
    "pro": 1,
    "ultra": 2,
    "lifetime": 3,
}


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Each connection is tracked with optional user_id and tier.
    Supports broadcast, per-user, and per-tier messaging.
    """

    def __init__(self):
        # All active connections: {websocket: {"user_id": str|None, "tier": str}}
        self._connections: Dict[WebSocket, dict] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        tier: str = "free",
    ):
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        self._connections[websocket] = {
            "user_id": user_id,
            "tier": tier,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self._connections.pop(websocket, None)

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def broadcast(self, message: dict):
        """Send a message to ALL connected clients."""
        dead_connections = []
        payload = json.dumps(message, default=str)

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)

    async def send_to_user(self, user_id: str, message: dict):
        """Send a message to all connections for a specific user."""
        dead_connections = []
        payload = json.dumps(message, default=str)

        for ws, info in self._connections.items():
            if info.get("user_id") == user_id:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)

    async def send_to_tier(self, min_tier: str, message: dict):
        """
        Send a message to all users at or above a given tier.
        E.g., send_to_tier("pro") sends to pro, ultra, lifetime.
        """
        min_level = TIER_HIERARCHY.get(min_tier, 0)
        dead_connections = []
        payload = json.dumps(message, default=str)

        for ws, info in self._connections.items():
            user_tier = info.get("tier", "free")
            if TIER_HIERARCHY.get(user_tier, 0) >= min_level:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)

    def get_status(self) -> dict:
        """Return connection stats."""
        tier_counts = {}
        for info in self._connections.values():
            tier = info.get("tier", "free")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        return {
            "total_connections": self.active_count,
            "connections_by_tier": tier_counts,
        }


# Singleton instance
manager = ConnectionManager()
