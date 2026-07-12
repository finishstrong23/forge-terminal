"""Helius webhook self-registration (M0).

No network in CI: these cover the config-gated skip paths, the status
endpoint shape, the owner guard on the manual trigger, and RPC-URL
derivation — the Helius API calls themselves are exercised in prod by the
startup pass and reported via /webhooks/helius/registration.
"""
import asyncio

from core.config import settings


def test_ensure_registration_skips_without_api_key(monkeypatch):
    from services.discovery import helius_webhooks

    monkeypatch.setattr(settings, "HELIUS_API_KEY", None)
    report = asyncio.run(helius_webhooks.ensure_webhook_registered())
    assert report["status"] == "skipped"
    assert "HELIUS_API_KEY" in report["reason"]


def test_ensure_registration_skips_without_public_domain(monkeypatch):
    from services.discovery import helius_webhooks

    monkeypatch.setattr(settings, "HELIUS_API_KEY", "test-key")
    monkeypatch.setattr(settings, "PUBLIC_API_URL", None)
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    report = asyncio.run(helius_webhooks.ensure_webhook_registered())
    assert report["status"] == "skipped"
    assert "public domain" in report["reason"]


def test_target_url_prefers_explicit_setting(monkeypatch):
    from services.discovery import helius_webhooks

    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com/")
    assert (
        helius_webhooks.target_webhook_url()
        == "https://api.example.com/api/v1/webhooks/helius"
    )

    monkeypatch.setattr(settings, "PUBLIC_API_URL", None)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "myapp.up.railway.app")
    assert (
        helius_webhooks.target_webhook_url()
        == "https://myapp.up.railway.app/api/v1/webhooks/helius"
    )


def test_registration_status_endpoint_is_public_and_masked(client):
    r = client.get("/api/v1/webhooks/helius/registration")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "helius_api_key_set",
        "webhook_auth_secret_set",
        "target_url",
        "last_attempt",
        "rejected_deliveries",
    }
    assert isinstance(body["helius_api_key_set"], bool)


def test_registration_live_view_reports_missing_key(client, monkeypatch):
    monkeypatch.setattr(settings, "HELIUS_API_KEY", None)
    r = client.get("/api/v1/webhooks/helius/registration?live=true")
    assert r.status_code == 200
    assert r.json()["live"] == {"error": "HELIUS_API_KEY not set"}


def test_manual_register_requires_owner_auth(client):
    r = client.post("/api/v1/webhooks/helius/register")
    assert r.status_code == 401


def test_ingest_accepts_raw_and_bearer_auth_headers(client, monkeypatch):
    monkeypatch.setattr(settings, "HELIUS_WEBHOOK_SECRET", "s3cret")

    ok_raw = client.post(
        "/api/v1/webhooks/helius", json=[], headers={"Authorization": "s3cret"}
    )
    assert ok_raw.status_code == 200 and ok_raw.json()["events_received"] == 0

    ok_bearer = client.post(
        "/api/v1/webhooks/helius", json=[], headers={"Authorization": "Bearer s3cret"}
    )
    assert ok_bearer.status_code == 200

    rejected = client.post(
        "/api/v1/webhooks/helius", json=[], headers={"Authorization": "wrong"}
    )
    assert rejected.status_code == 401


def test_archive_stale_marks_only_pre_cutoff_events(client, db):
    from datetime import datetime, timedelta, timezone

    from models.token import HeliusEvent

    now = datetime.now(timezone.utc)
    db.add(HeliusEvent(event_type="SWAP", signature="stale-1", raw_data={},
                       event_timestamp=now - timedelta(days=60),
                       received_at=now - timedelta(days=60), processed=False))
    db.add(HeliusEvent(event_type="SWAP", signature="fresh-1", raw_data={},
                       event_timestamp=now, received_at=now, processed=False))
    db.commit()

    # Unauthenticated → rejected.
    assert client.post(
        "/api/v1/webhooks/helius/archive-stale?before=2026-01-01"
    ).status_code == 401

    # Owner account (finishstrong23@gmail.com is in OWNER_EMAILS).
    token = client.post(
        "/api/v1/auth/register",
        json={"email": "finishstrong23@gmail.com", "password": "ownerpass123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    cutoff = (now - timedelta(days=1)).date().isoformat()
    r = client.post(
        f"/api/v1/webhooks/helius/archive-stale?before={cutoff}", headers=headers
    )
    assert r.status_code == 200 and r.json()["archived"] == 1

    stale = db.query(HeliusEvent).filter_by(signature="stale-1").one()
    fresh = db.query(HeliusEvent).filter_by(signature="fresh-1").one()
    assert stale.processed is True and "archived" in stale.processing_error
    assert fresh.processed is False


def test_helius_rpc_url_derived_from_api_key(monkeypatch):
    from services.discovery.token_discovery import helius_rpc_url

    monkeypatch.setattr(settings, "HELIUS_RPC_URL", None)
    monkeypatch.setattr(settings, "HELIUS_API_KEY", None)
    assert helius_rpc_url() is None

    monkeypatch.setattr(settings, "HELIUS_API_KEY", "abc123")
    assert helius_rpc_url() == "https://mainnet.helius-rpc.com/?api-key=abc123"

    monkeypatch.setattr(settings, "HELIUS_RPC_URL", "https://custom.rpc/x")
    assert helius_rpc_url() == "https://custom.rpc/x"
