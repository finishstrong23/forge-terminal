"""
Helius webhook self-registration (M0 pipeline resurrection).

The ingest endpoint (POST /api/v1/webhooks/helius) only works while a
webhook on the Helius account points at it. That registration was manual
and silently lapsed (Helius disables webhooks after repeated delivery
failures — e.g. while this API was down). This module makes the app own
its registration:

  - ensure_webhook_registered() finds the account webhook aimed at this
    deployment's public URL, updates it if present, creates it if not.
  - main.py runs it on every web-process startup, so registration
    self-heals on each deploy without dashboard access.
  - The outcome is cached in Redis under REGISTRATION_CACHE_KEY and
    exposed by GET /api/v1/webhooks/helius/registration.

The public URL comes from RAILWAY_PUBLIC_DOMAIN (injected by Railway into
services with a public domain) or the PUBLIC_API_URL setting as an
explicit override.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from core.config import settings
from core.redis_cache import cache

logger = logging.getLogger(__name__)

HELIUS_API_BASE = "https://api.helius.xyz/v0"
WEBHOOK_TRANSACTION_TYPES = ["SWAP", "TOKEN_MINT", "TRANSFER"]
REGISTRATION_CACHE_KEY = "helius:webhook_registration"
REGISTRATION_CACHE_TTL = 7 * 24 * 3600


def target_webhook_url() -> Optional[str]:
    """Public ingest URL this deployment should be registered under."""
    if settings.PUBLIC_API_URL:
        base = settings.PUBLIC_API_URL.rstrip("/")
        return f"{base}/api/v1/webhooks/helius"
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if domain:
        return f"https://{domain}/api/v1/webhooks/helius"
    return None


def _desired_payload(target_url: str) -> dict:
    payload = {
        "webhookURL": target_url,
        "transactionTypes": WEBHOOK_TRANSACTION_TYPES,
        "accountAddresses": [settings.PUMP_FUN_PROGRAM_ID],
        "webhookType": "enhanced",
    }
    if settings.HELIUS_WEBHOOK_SECRET:
        # Helius echoes this in the Authorization header; the ingest
        # endpoint verifies it (see webhook_handler.helius_webhook).
        payload["authHeader"] = settings.HELIUS_WEBHOOK_SECRET
    return payload


def _record(report: dict) -> dict:
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    try:
        cache.set(REGISTRATION_CACHE_KEY, report, ttl=REGISTRATION_CACHE_TTL)
    except Exception:
        pass
    return report


async def ensure_webhook_registered() -> dict:
    """
    Create-or-update the Helius webhook for this deployment. Never raises;
    returns (and caches) a status report either way.
    """
    api_key = settings.HELIUS_API_KEY
    if not api_key:
        return _record({"status": "skipped", "reason": "HELIUS_API_KEY not set"})

    target_url = target_webhook_url()
    if not target_url:
        return _record({
            "status": "skipped",
            "reason": "no public domain known (set PUBLIC_API_URL or run on Railway)",
        })

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            listing = await client.get(
                f"{HELIUS_API_BASE}/webhooks", params={"api-key": api_key}
            )
            if listing.status_code != 200:
                return _record({
                    "status": "error",
                    "step": "list",
                    "http_status": listing.status_code,
                    "detail": listing.text[:300],
                })

            webhooks = listing.json() or []
            existing = next(
                (w for w in webhooks if w.get("webhookURL") == target_url), None
            )

            payload = _desired_payload(target_url)
            if existing:
                webhook_id = existing.get("webhookID")
                response = await client.put(
                    f"{HELIUS_API_BASE}/webhooks/{webhook_id}",
                    params={"api-key": api_key},
                    json=payload,
                )
                action = "updated"
            else:
                response = await client.post(
                    f"{HELIUS_API_BASE}/webhooks",
                    params={"api-key": api_key},
                    json=payload,
                )
                action = "created"

            if response.status_code not in (200, 201):
                return _record({
                    "status": "error",
                    "step": action,
                    "http_status": response.status_code,
                    "detail": response.text[:300],
                })

            body = response.json() if response.content else {}
            webhook_id = body.get("webhookID") or (
                existing.get("webhookID") if existing else None
            )
            logger.info("helius webhook %s (%s) -> %s", action, webhook_id, target_url)
            return _record({
                "status": "registered",
                "action": action,
                "webhook_id": webhook_id,
                "target_url": target_url,
                "transaction_types": WEBHOOK_TRANSACTION_TYPES,
                "auth_header_set": bool(settings.HELIUS_WEBHOOK_SECRET),
                "account_webhook_count": len(webhooks) if not existing else len(webhooks),
            })

    except Exception as exc:
        return _record({
            "status": "error",
            "step": "request",
            "detail": f"{type(exc).__name__}: {exc}",
        })


def registration_status() -> dict:
    """Read-only view for the status endpoint: config + last attempt."""
    return {
        "helius_api_key_set": bool(settings.HELIUS_API_KEY),
        "webhook_auth_secret_set": bool(settings.HELIUS_WEBHOOK_SECRET),
        "target_url": target_webhook_url(),
        "last_attempt": cache.get(REGISTRATION_CACHE_KEY),
    }
