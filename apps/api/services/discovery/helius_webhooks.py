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


async def _disable_webhook(api_key: str, target_url: str) -> dict:
    """Delete this deployment's webhook(s) on Helius so events (and their
    credit cost) stop. Idempotent — no-op if none are registered."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            listing = await client.get(
                f"{HELIUS_API_BASE}/webhooks", params={"api-key": api_key}
            )
            if listing.status_code != 200:
                return {
                    "status": "error",
                    "step": "list",
                    "http_status": listing.status_code,
                    "detail": listing.text[:300],
                }
            ours = [
                w for w in (listing.json() or [])
                if w.get("webhookURL") == target_url
            ]
            deleted = []
            for w in ours:
                webhook_id = w.get("webhookID")
                resp = await client.delete(
                    f"{HELIUS_API_BASE}/webhooks/{webhook_id}",
                    params={"api-key": api_key},
                )
                deleted.append({"webhook_id": webhook_id, "http_status": resp.status_code})
            logger.info("helius webhook disabled (deleted %d) — poll-only mode", len(deleted))
            return {
                "status": "disabled",
                "reason": "WEBHOOK_ENABLED=false — poll-only mode to save Helius credits",
                "deleted": deleted,
            }
    except Exception as exc:
        return {"status": "error", "step": "disable", "detail": f"{type(exc).__name__}: {exc}"}


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

    # Credit control: when the webhook is disabled, delete it on Helius so it
    # stops sending (and thus stops billing) — not re-registering is not
    # enough; an already-registered webhook keeps firing until deleted.
    if not settings.WEBHOOK_ENABLED:
        return _record(await _disable_webhook(api_key, target_url))

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

            # Read-after-write: Helius can accept a write yet silently drop
            # accountAddresses (seen in prod: webhook "registered" but
            # watching nothing → zero deliveries). Fetch the stored config
            # and compare.
            stored = {}
            if webhook_id:
                verify = await client.get(
                    f"{HELIUS_API_BASE}/webhooks/{webhook_id}",
                    params={"api-key": api_key},
                )
                if verify.status_code == 200 and verify.content:
                    stored = verify.json() or {}
            stored_addresses = stored.get("accountAddresses")
            if stored_addresses is None:
                stored_addresses = body.get("accountAddresses") or []

            watching = len(stored_addresses) > 0
            status = "registered" if watching else "registered_but_not_watching"
            logger.info(
                "helius webhook %s (%s) -> %s [stored addresses: %d]",
                action, webhook_id, target_url, len(stored_addresses),
            )
            report = {
                "status": status,
                "action": action,
                "webhook_id": webhook_id,
                "target_url": target_url,
                "sent_account_addresses": [settings.PUMP_FUN_PROGRAM_ID],
                "stored_account_addresses_count": len(stored_addresses),
                "stored_transaction_types": stored.get("transactionTypes")
                or body.get("transactionTypes"),
                "write_response_addresses_count": len(body.get("accountAddresses") or []),
                "auth_header_set": bool(settings.HELIUS_WEBHOOK_SECRET),
                "account_webhook_count": len(webhooks),
            }
            if not watching:
                report["hint"] = (
                    "Helius accepted the write but kept an empty accountAddresses "
                    "list — the webhook watches nothing, so no events will ever "
                    "arrive. Usual causes: plan/credit limits on the Helius "
                    "account, or program-address monitoring not allowed on the "
                    "current tier. Check the webhook and plan usage at "
                    "https://dashboard.helius.dev"
                )
            return _record(report)

    except Exception as exc:
        return _record({
            "status": "error",
            "step": "request",
            "detail": f"{type(exc).__name__}: {exc}",
        })


def registration_status() -> dict:
    """Read-only view for the status endpoint: config + last attempt."""
    return {
        "webhook_enabled": settings.WEBHOOK_ENABLED,
        "helius_api_key_set": bool(settings.HELIUS_API_KEY),
        "webhook_auth_secret_set": bool(settings.HELIUS_WEBHOOK_SECRET),
        "target_url": target_webhook_url(),
        "last_attempt": cache.get(REGISTRATION_CACHE_KEY),
        # Deliveries rejected by the ingest endpoint's auth check —
        # non-zero means Helius IS sending but the secret doesn't match.
        "rejected_deliveries": cache.get("helius:webhook_auth_failures"),
    }


def _summarize_webhook(webhook: dict, ours: bool) -> dict:
    """Webhook config as Helius stores it, safe for display: authHeader is
    reduced to a length, and foreign webhook URLs to their host."""
    addresses = webhook.get("accountAddresses") or []
    url = webhook.get("webhookURL", "")
    if not ours:
        # Foreign URLs can embed tokens in path/query — host is enough.
        url = url.split("//", 1)[-1].split("/", 1)[0] if url else ""
    return {
        "webhook_id": webhook.get("webhookID"),
        "webhook_url" if ours else "webhook_host": url,
        "webhook_type": webhook.get("webhookType"),
        "transaction_types": webhook.get("transactionTypes"),
        "account_addresses_count": len(addresses),
        "account_addresses_sample": addresses[:3],
        "auth_header_length": len(webhook.get("authHeader") or ""),
        "txn_status": webhook.get("txnStatus"),
    }


async def live_account_view() -> dict:
    """
    Fetch the account's webhooks from Helius RIGHT NOW — what Helius has
    actually stored, not what we last sent. For diagnosing 'registered but
    silent' deliveries.
    """
    api_key = settings.HELIUS_API_KEY
    if not api_key:
        return {"error": "HELIUS_API_KEY not set"}
    target_url = target_webhook_url()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            listing = await client.get(
                f"{HELIUS_API_BASE}/webhooks", params={"api-key": api_key}
            )
            if listing.status_code != 200:
                return {
                    "error": f"Helius list returned {listing.status_code}",
                    "detail": listing.text[:300],
                }
            webhooks = listing.json() or []
            ours = [w for w in webhooks if w.get("webhookURL") == target_url]
            others = [w for w in webhooks if w.get("webhookURL") != target_url]
            return {
                "total_webhooks": len(webhooks),
                "our_webhook": _summarize_webhook(ours[0], ours=True) if ours else None,
                "other_webhooks": [_summarize_webhook(w, ours=False) for w in others],
            }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
