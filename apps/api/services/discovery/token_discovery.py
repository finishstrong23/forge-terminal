"""
Token Discovery Service
========================

Proactively discovers new Pump.fun token launches instead of waiting for
webhook events. Uses two strategies:

1. Helius DAS API (preferred) -- search for recently created SPL tokens
   from the Pump.fun program. No Cloudflare issues.
2. Pump.fun API fallback -- call /coins/latest with rate limiting.
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
import httpx

from core.config import settings
from core.rate_limiter import rate_limiter
from core.database import SessionLocal
from models.token import TokenSignal


PUMP_FUN_API = "https://frontend-api.pump.fun"


def helius_rpc_url() -> Optional[str]:
    """Explicit HELIUS_RPC_URL, else derived from HELIUS_API_KEY — one
    configured key is enough to power DAS discovery."""
    if settings.HELIUS_RPC_URL:
        return settings.HELIUS_RPC_URL
    if settings.HELIUS_API_KEY:
        return f"https://mainnet.helius-rpc.com/?api-key={settings.HELIUS_API_KEY}"
    return None


async def poll_new_tokens() -> List[Dict]:
    """
    Discover new Pump.fun tokens. Tries Helius DAS first, falls back to Pump.fun API.

    Returns list of discovered token dicts: [{mint_address, name, symbol, ...}]
    """
    # Strategy 1: Helius DAS API (no Cloudflare issues)
    tokens = await _discover_via_helius_das()
    if tokens:
        return tokens

    # Strategy 2: Pump.fun API (rate limited)
    return await _discover_via_pump_fun_api()


async def _discover_via_helius_das() -> List[Dict]:
    """
    Use Helius DAS API to search for recently created Pump.fun tokens.
    """
    rpc_url = helius_rpc_url()
    if not rpc_url:
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Use searchAssets to find recently minted tokens from Pump.fun program
            response = await client.post(rpc_url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "searchAssets",
                "params": {
                    "grouping": ["collection", settings.PUMP_FUN_PROGRAM_ID],
                    "sortBy": {"sortBy": "created", "sortDirection": "desc"},
                    "limit": settings.DISCOVERY_BATCH_SIZE,
                    "page": 1,
                }
            })

            if response.status_code != 200:
                return []

            data = response.json()
            items = data.get("result", {}).get("items", [])

            tokens = []
            for item in items:
                mint_address = item.get("id")
                if not mint_address:
                    continue

                content = item.get("content", {})
                metadata = content.get("metadata", {})

                tokens.append({
                    "mint_address": mint_address,
                    "name": metadata.get("name", "Unknown Token"),
                    "symbol": metadata.get("symbol", "UNKNOWN"),
                    "image_uri": content.get("links", {}).get("image"),
                    "source": "helius_das",
                })

            return tokens

    except Exception as e:
        print(f"Helius DAS discovery failed: {e}")
        return []


async def _discover_via_pump_fun_api() -> List[Dict]:
    """
    Fallback: discover tokens via Pump.fun's frontend API.
    Heavily rate limited to avoid Cloudflare bans.
    """
    if not rate_limiter.can_call():
        return []

    try:
        rate_limiter.record_request()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{PUMP_FUN_API}/coins",
                params={"offset": 0, "limit": settings.DISCOVERY_BATCH_SIZE, "sort": "created_timestamp"},
            )

            if response.status_code in (429, 403):
                rate_limiter.disable()
                return []

            if response.status_code != 200:
                return []

            text = response.text
            if "cloudflare" in text.lower() or "error code" in text.lower():
                rate_limiter.disable_cloudflare()
                return []

            data = response.json()
            tokens = []

            # Pump.fun API returns a list of coin objects
            items = data if isinstance(data, list) else data.get("coins", data.get("items", []))

            for item in items:
                mint_address = item.get("mint")
                if not mint_address:
                    continue

                tokens.append({
                    "mint_address": mint_address,
                    "name": item.get("name", "Unknown Token"),
                    "symbol": item.get("symbol", "UNKNOWN"),
                    "image_uri": item.get("image_uri"),
                    "description": item.get("description"),
                    "creator": item.get("creator"),
                    "market_cap": item.get("usd_market_cap"),
                    "complete": item.get("complete", False),
                    "source": "pump_fun_api",
                })

            return tokens

    except Exception as e:
        print(f"Pump.fun API discovery failed: {e}")
        return []


def process_discovered_tokens(tokens: List[Dict]) -> dict:
    """
    Process discovered tokens: create TokenSignal records for new ones.
    Returns stats about what was created vs. skipped.
    """
    db = SessionLocal()
    try:
        created = 0
        skipped = 0

        for token_data in tokens:
            mint_address = token_data.get("mint_address")
            if not mint_address:
                continue

            # Check if already tracked
            existing = db.query(TokenSignal).filter(
                TokenSignal.token_address == mint_address
            ).first()

            if existing:
                skipped += 1
                continue

            # Create new token signal
            signal = TokenSignal(
                token_address=mint_address,
                chain_id="solana",
                symbol=token_data.get("symbol", "UNKNOWN"),
                name=token_data.get("name", "Unknown Token"),
                dev_wallet=token_data.get("creator"),
                has_graduated=token_data.get("complete", False),
                market_cap=token_data.get("market_cap"),
                token_metadata=token_data,
                tier_level="ultra",
                scan_timestamp=datetime.now(timezone.utc),
                pair_created_at=datetime.now(timezone.utc),
                age_minutes=0.0,
                pump_fun_url=f"https://pump.fun/{mint_address}",
                total_holders=1,
                entity_adjusted_buyers=1,
                buys_5m=0,
                sells_5m=0,
                holder_concentration=0,
                retention_5m=100,
                # Initial scores -- will be recalculated when events arrive
                momentum_score=0,
                rug_risk_score=50,
                confidence_score=0,
            )

            db.add(signal)
            created += 1

            print(f"Discovered: {token_data.get('symbol', 'UNKNOWN')} ({mint_address[:8]}...)")

        db.commit()
        return {"created": created, "skipped": skipped, "total": len(tokens)}

    except Exception as e:
        db.rollback()
        print(f"Error processing discovered tokens: {e}")
        return {"created": 0, "skipped": 0, "error": str(e)}
    finally:
        db.close()


async def register_token_for_webhook(mint_address: str) -> bool:
    """
    Optionally register a discovered token with the Helius webhook
    so future events arrive via webhook.

    Requires HELIUS_WEBHOOK_ID to be set.
    """
    webhook_id = settings.HELIUS_WEBHOOK_ID
    api_key = settings.HELIUS_API_KEY

    if not webhook_id or not api_key:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"https://api.helius.xyz/v0/webhooks/{webhook_id}?api-key={api_key}",
                json={
                    "accountAddresses": [mint_address],
                    "accountAddressOwners": [settings.PUMP_FUN_PROGRAM_ID],
                },
            )
            return response.status_code == 200

    except Exception as e:
        print(f"Failed to register {mint_address[:8]}... for webhook: {e}")
        return False
