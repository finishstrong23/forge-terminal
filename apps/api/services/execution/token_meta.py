"""
Token metadata lookup (M3 follow-up: real decimals for the swap ticket).

Mint decimals are immutable, so a successful lookup is cached for a day.
Uses the same RPC endpoint precedence as the confirmation checker. None on
failure — callers fall back to the documented 6-decimals assumption.
"""
import logging
from typing import Optional

import httpx

from core.redis_cache import cache
from services.execution.confirmations import _rpc_url

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_S = 5.0
DECIMALS_TTL_SECONDS = 24 * 3600


def fetch_token_decimals(mint: str) -> Optional[int]:
    """Live getTokenSupply lookup. None on RPC failure or unknown mint."""
    try:
        response = httpx.post(
            _rpc_url(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenSupply",
                "params": [mint],
            },
            timeout=HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        decimals = response.json()["result"]["value"]["decimals"]
        return int(decimals)
    except Exception as exc:
        logger.warning("token_meta: decimals lookup failed for %s: %s", mint, exc)
        return None


def get_token_decimals(mint: str) -> Optional[int]:
    """Cached decimals; fetch + cache on a miss. None when unavailable."""
    key = f"token:decimals:{mint}"
    cached = cache.get(key)
    if isinstance(cached, int):
        return cached
    decimals = fetch_token_decimals(mint)
    if decimals is not None:
        cache.set(key, decimals, ttl=DECIMALS_TTL_SECONDS)
    return decimals
