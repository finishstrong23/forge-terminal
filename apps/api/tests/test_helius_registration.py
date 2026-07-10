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
    }
    assert isinstance(body["helius_api_key_set"], bool)


def test_manual_register_requires_owner_auth(client):
    r = client.post("/api/v1/webhooks/helius/register")
    assert r.status_code == 401


def test_helius_rpc_url_derived_from_api_key(monkeypatch):
    from services.discovery.token_discovery import helius_rpc_url

    monkeypatch.setattr(settings, "HELIUS_RPC_URL", None)
    monkeypatch.setattr(settings, "HELIUS_API_KEY", None)
    assert helius_rpc_url() is None

    monkeypatch.setattr(settings, "HELIUS_API_KEY", "abc123")
    assert helius_rpc_url() == "https://mainnet.helius-rpc.com/?api-key=abc123"

    monkeypatch.setattr(settings, "HELIUS_RPC_URL", "https://custom.rpc/x")
    assert helius_rpc_url() == "https://custom.rpc/x"
