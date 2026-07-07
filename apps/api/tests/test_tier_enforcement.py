"""Tier enforcement: free-tier feed delay + follow limits."""
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def tokens(db):
    """One fresh token (inside the 15-min free delay) and one older token."""
    from models.token import TokenSignal

    now = datetime.now(timezone.utc)
    db.add(TokenSignal(id="fresh", token_address="FRESH", symbol="FRESH",
                       scan_timestamp=now - timedelta(minutes=1),
                       momentum_score=80.0, rug_risk_score=20.0))
    db.add(TokenSignal(id="older", token_address="OLDER", symbol="OLDER",
                       scan_timestamp=now - timedelta(minutes=30),
                       momentum_score=70.0, rug_risk_score=30.0))
    db.commit()
    return db


def _register(client, email, tier=None, db=None):
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": "password123"})
    assert r.status_code == 201
    body = r.json()
    if tier and db is not None:
        from models.user import User
        user = db.query(User).filter(User.id == body["user"]["id"]).first()
        user.subscription_tier = tier
        db.commit()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_anonymous_and_free_see_delayed_feed(client, tokens):
    auth_free = _register(client, "free@example.com")

    for headers in ({}, auth_free):
        r = client.get("/api/v1/discovery/feed", headers=headers)
        ids = {t["id"] for t in r.json()["tokens"]}
        assert ids == {"older"}, f"headers={bool(headers)}: {ids}"

    r = client.get("/api/v1/signals/latest")
    assert {s["id"] for s in r.json()["signals"]} == {"older"}


def test_pro_sees_realtime_feed(client, tokens):
    auth_pro = _register(client, "pro@example.com", tier="pro", db=tokens)

    r = client.get("/api/v1/discovery/feed", headers=auth_pro)
    assert {t["id"] for t in r.json()["tokens"]} == {"fresh", "older"}

    r = client.get("/api/v1/signals/latest", headers=auth_pro)
    assert {s["id"] for s in r.json()["signals"]} == {"fresh", "older"}


def test_follow_limit_by_tier(client, db, seed_activity):
    from core.config import settings

    for i in range(settings.FREE_TIER_MAX_ACTIVE_FOLLOWS + 1):
        seed_activity(f"wallet{i}", "TOK1", "buy", 1.0, f"sig{i}", mins_ago=5)
    db.commit()

    auth = _register(client, "limited@example.com")
    for i in range(settings.FREE_TIER_MAX_ACTIVE_FOLLOWS):
        r = client.post("/api/v1/copy/subscriptions",
                        json={"wallet_address": f"wallet{i}"}, headers=auth)
        assert r.status_code == 201, r.text

    over = settings.FREE_TIER_MAX_ACTIVE_FOLLOWS
    r = client.post("/api/v1/copy/subscriptions",
                    json={"wallet_address": f"wallet{over}"}, headers=auth)
    assert r.status_code == 403
    assert "upgrade" in r.json()["detail"]

    # Stopping one frees a slot.
    sid = client.get("/api/v1/copy/subscriptions", headers=auth).json()["subscriptions"][0]["id"]
    client.patch(f"/api/v1/copy/subscriptions/{sid}", json={"action": "stop"}, headers=auth)
    r = client.post("/api/v1/copy/subscriptions",
                    json={"wallet_address": f"wallet{over}"}, headers=auth)
    assert r.status_code == 201, r.text


def test_pro_follow_limit_is_higher(client, db, seed_activity):
    from core.config import settings

    count = settings.FREE_TIER_MAX_ACTIVE_FOLLOWS + 1
    for i in range(count):
        seed_activity(f"pw{i}", "TOK1", "buy", 1.0, f"psig{i}", mins_ago=5)
    db.commit()

    auth = _register(client, "bigshot@example.com", tier="pro", db=db)
    for i in range(count):
        r = client.post("/api/v1/copy/subscriptions",
                        json={"wallet_address": f"pw{i}"}, headers=auth)
        assert r.status_code == 201, r.text
