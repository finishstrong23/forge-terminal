"""
Token metadata via Helius DAS (P1 credibility).

The original metadata source — pump.fun's frontend API — blocks servers
via Cloudflare and is rate-limited here to ~3 calls/min, so at live
ingest volume most tokens rendered as "UNKNOWN". DAS (getAssetBatch) runs
on the same HELIUS_API_KEY that powers ingestion, has no Cloudflare, and
resolves up to 100 mints per call.

Sync client on purpose: callers are the Celery worker (enrich beat task)
and the webhook processor's sync path.
"""
import logging
from typing import Dict, List, Optional

import httpx

from services.discovery.token_discovery import helius_rpc_url

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


def parse_das_asset(asset: Optional[dict]) -> Optional[dict]:
    """DAS asset -> {name, symbol, image_uri}; None when unusable."""
    if not asset:
        return None
    content = asset.get("content") or {}
    meta = content.get("metadata") or {}
    links = content.get("links") or {}
    name = (meta.get("name") or "").strip()
    symbol = (meta.get("symbol") or "").strip()
    if not name and not symbol:
        return None
    return {
        "name": name or None,
        "symbol": symbol or None,
        "image_uri": links.get("image"),
    }


def fetch_das_metadata(mints: List[str]) -> Dict[str, dict]:
    """
    Resolve mints -> {name, symbol, image_uri} via DAS getAssetBatch.
    Best-effort: returns what it could resolve, never raises.
    """
    rpc = helius_rpc_url()
    if not rpc or not mints:
        return {}
    resolved: Dict[str, dict] = {}
    try:
        with httpx.Client(timeout=15.0) as client:
            for start in range(0, len(mints), BATCH_SIZE):
                batch = mints[start:start + BATCH_SIZE]
                response = client.post(rpc, json={
                    "jsonrpc": "2.0",
                    "id": "token-metadata",
                    "method": "getAssetBatch",
                    "params": {"ids": batch},
                })
                if response.status_code != 200:
                    logger.warning(
                        "DAS getAssetBatch returned %s", response.status_code
                    )
                    continue
                for asset in response.json().get("result") or []:
                    parsed = parse_das_asset(asset)
                    if parsed and asset.get("id"):
                        resolved[asset["id"]] = parsed
    except Exception as exc:
        logger.warning("DAS metadata fetch failed: %s", exc)
    return resolved
