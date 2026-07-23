"""Regression tests for the security-audit fixes."""
from datetime import datetime, timezone

import pytest

from core.config import settings


# ---------- webhook ingest hardening ----------

def test_webhook_rejects_nan_infinity(client, monkeypatch):
    monkeypatch.setattr(settings, "HELIUS_WEBHOOK_SECRET", "s3cret")
    # NaN/Infinity survive json.loads by default; the ingest must reject them
    # so they can't poison persisted float columns.
    r = client.post(
        "/api/v1/webhooks/helius",
        headers={"Authorization": "s3cret", "Content-Type": "application/json"},
        content='[{"type":"SWAP","nativeTransfers":[{"amount":Infinity}]}]',
    )
    assert r.status_code == 400


def test_webhook_truncates_oversized_batches_without_rejecting_delivery(
    client, monkeypatch
):
    """A too-large batch must be truncated and still return 200 — an error
    status here reads to Helius as a failed delivery, and repeated failures
    are what got the webhook auto-disabled once already (ROADMAP M0)."""
    from services.discovery import webhook_handler as wh

    monkeypatch.setattr(settings, "HELIUS_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setattr(wh, "MAX_WEBHOOK_EVENTS", 100)
    r = client.post(
        "/api/v1/webhooks/helius",
        headers={"Authorization": "s3cret"},
        json=[{"type": "SWAP", "signature": f"s{i}"} for i in range(150)],
    )
    assert r.status_code == 200
    assert r.json()["events_received"] == 100


def test_webhook_ops_endpoints_require_owner(client):
    for path in (
        "/api/v1/webhooks/helius/reprocess",
        "/api/v1/webhooks/helius/refresh-metadata",
        "/api/v1/webhooks/helius/recalculate-scores",
    ):
        assert client.post(path).status_code == 401, path
    assert client.get("/api/v1/webhooks/helius/stats").status_code == 401


# ---------- financial extraction hardening ----------

def test_price_ignores_bundled_self_transfer(db, monkeypatch):
    """A large self-transfer bundled into a swap must not set the price —
    the bonding-curve leg is authoritative."""
    from models.token import TokenSignal
    from services.discovery.webhook_handler import HeliusWebhookProcessor

    monkeypatch.setattr(
        "services.execution.price_feed.get_sol_price_usd", lambda: 100.0
    )
    mint = "MintTokZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
    bonding = "BondCurveAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    signal = TokenSignal(
        id="ts-self", token_address=mint, symbol="Z", scan_timestamp=datetime.now(timezone.utc),
        momentum_score=0.0, rug_risk_score=50.0,
    )
    db.add(signal)
    db.commit()
    event = {
        "accounts": ["user", bonding],  # _extract_bonding_curve picks index 1
        "nativeTransfers": [
            {"amount": 900_000_000_000, "fromUserAccount": "atk", "toUserAccount": "atk"},  # self-transfer, huge
            {"amount": 2_000_000_000, "fromUserAccount": "user", "toUserAccount": bonding},  # real 2 SOL leg
        ],
        "tokenTransfers": [{"mint": mint, "tokenAmount": 50_000}],
    }
    HeliusWebhookProcessor(db)._update_metrics_from_event(signal, event, "SWAP")
    # 2 SOL / 50k tokens * $100 = $0.004 — NOT the 900-SOL self-transfer.
    assert signal.price_usd == pytest.approx(0.004)


# ---------- trade recording: per-user signature scope ----------

def test_signature_dedup_is_per_user(client, db):
    """One user pre-claiming a public signature must not block another user
    from recording the same on-chain trade."""
    mint = "MintTokQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ"
    sig = "Sig" + "1" * 60

    def register(email):
        r = client.post("/api/v1/auth/register",
                        json={"email": email, "password": "password123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    a, b = register("a@example.com"), register("b@example.com")
    body = {"token_address": mint, "trade_type": "buy", "sol_amount": 1.0, "signature": sig}

    assert client.post("/api/v1/execute/trades", json=body, headers=a).status_code == 201
    # Same user, same signature -> dup.
    assert client.post("/api/v1/execute/trades", json=body, headers=a).status_code == 409
    # Different user, same on-chain signature -> allowed (not suppressed).
    assert client.post("/api/v1/execute/trades", json=body, headers=b).status_code == 201


def test_trade_rejects_non_base58_mint(client, db):
    r = client.post("/api/v1/auth/register",
                    json={"email": "mint@example.com", "password": "password123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post(
        "/api/v1/execute/trades",
        json={"token_address": "not a mint!", "trade_type": "buy",
              "sol_amount": 1.0, "signature": "s" * 40},
        headers=auth,
    )
    assert r.status_code == 422


# ---------- auth hardening ----------

def test_owner_email_cannot_be_registered(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": settings.OWNER_EMAILS[0], "password": "password123"},
    )
    assert r.status_code == 403


def test_owner_seed_creates_account_when_configured(db, monkeypatch):
    """The startup seed recreates the owner after a DB reset so the
    non-registerable owner email isn't permanently locked out."""
    import main
    from models.user import User

    email = settings.OWNER_EMAILS[0].lower()
    assert db.query(User).filter(User.email == email).first() is None

    # No password -> no-op.
    monkeypatch.setattr(settings, "OWNER_INITIAL_PASSWORD", None)
    main._seed_owner_account()
    assert db.query(User).filter(User.email == email).first() is None

    # Password set -> owner seeded, and it can log in.
    monkeypatch.setattr(settings, "OWNER_INITIAL_PASSWORD", "seededpass123")
    main._seed_owner_account()
    owner = db.query(User).filter(User.email == email).first()
    assert owner is not None
    # Idempotent second call.
    main._seed_owner_account()
    assert db.query(User).filter(User.email == email).count() == 1


def test_purposeless_token_is_rejected(client, db):
    """A signed token without a purpose claim must not authenticate."""
    from jose import jwt
    from models.user import User
    from core.security import hash_password

    user = User(email="pt@example.com", password_hash=hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    forged = jwt.encode(
        {"sub": user.id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_production_config_rejects_default_secret_key():
    """Constructing prod settings with the default key must fail closed."""
    from core.config import Settings, INSECURE_SECRET_KEY

    with pytest.raises(Exception):
        Settings(ENVIRONMENT="production", SECRET_KEY=INSECURE_SECRET_KEY,
                  HELIUS_WEBHOOK_SECRET="x")
    # A strong key still needs the webhook secret in prod.
    with pytest.raises(Exception):
        Settings(ENVIRONMENT="production", SECRET_KEY="k" * 40,
                 HELIUS_WEBHOOK_SECRET=None)
    # Both present -> ok.
    ok = Settings(ENVIRONMENT="production", SECRET_KEY="k" * 40,
                  HELIUS_WEBHOOK_SECRET="whsec")
    assert ok.is_production


# ---------- celery exception redaction ----------

def test_task_failure_redaction_strips_secrets():
    from services.discovery.celery_app import _redact

    msg = "ConnError: https://mainnet.helius-rpc.com/?api-key=SECRET123 failed"
    assert "SECRET123" not in _redact(msg)
    assert "redis://default:hunter2@host:6379" not in _redact(
        "err redis://default:hunter2@host:6379 down"
    )
