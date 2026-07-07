"""Shadow-trade recorder + /api/v1/copy/trades ledger."""
from datetime import datetime, timedelta, timezone

import pytest

WALLET = "walletA"


@pytest.fixture()
def followed(client, db, seed_activity):
    """Two users following walletA with different risk filters, plus fresh
    post-follow activity across three tokens (one honeypot, one blacklisted)."""
    from models.token import TokenSignal
    from models.wallet import Wallet

    now = datetime.now(timezone.utc)
    seed_activity(WALLET, "TOK1", "buy", 1.0, "preexisting", mins_ago=30)
    db.add(Wallet(address=WALLET, sustainability_score=50.0, sustainability_grade="C"))
    db.add(TokenSignal(id="ts1", token_address="TOK1", symbol="TOK1", scan_timestamp=now,
                       price_usd=0.01, rug_risk_score=20.0, momentum_score=80.0,
                       is_honeypot=False))
    db.add(TokenSignal(id="ts2", token_address="TOKHONEY", symbol="HONEY", scan_timestamp=now,
                       rug_risk_score=95.0, momentum_score=10.0, is_honeypot=True))
    db.commit()

    def register_and_follow(email, **params):
        r = client.post("/api/v1/auth/register",
                        json={"email": email, "password": "password123"})
        auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.post("/api/v1/copy/subscriptions",
                        json={"wallet_address": WALLET, **params}, headers=auth)
        assert r.status_code == 201, r.text
        return auth, r.json()["id"]

    # u1 passes the threshold (40 <= 50); u2 does not (90 > 50).
    auth1, sub1 = register_and_follow(
        "u1@example.com", token_blacklist=["TOKBAD"], min_sustainability_score=40
    )
    auth2, _sub2 = register_and_follow("u2@example.com", min_sustainability_score=90)

    fresh = datetime.now(timezone.utc) + timedelta(seconds=1)  # after started_at
    for token, side, sol, sig in [
        ("TOK1", "buy", 2.0, "sigN1"),
        ("TOK1", "sell", 3.0, "sigN2"),
        ("TOKHONEY", "buy", 1.0, "sigN3"),
        ("TOKBAD", "buy", 5.0, "sigN4"),
    ]:
        seed_activity(WALLET, token, side, sol, sig, ts=fresh)
    db.commit()

    return {"db": db, "client": client, "auth1": auth1, "auth2": auth2, "sub1": sub1}


def test_recorder_filters_and_idempotency(followed):
    from services.copy.shadow_recorder import record_shadow_trades

    db = followed["db"]
    # u1: TOK1 buy+sell simulated, HONEY + TOKBAD skipped.
    # u2: all four skipped (threshold; HONEY via honeypot rule).
    result = record_shadow_trades(db)
    db.commit()
    assert result == {"subscriptions": 2, "recorded": 2, "skipped": 6}

    rerun = record_shadow_trades(db)
    db.commit()
    assert rerun == {"subscriptions": 2, "recorded": 0, "skipped": 0}


def test_ledger_contents_and_reasons(followed):
    from services.copy.shadow_recorder import record_shadow_trades

    db, client = followed["db"], followed["client"]
    record_shadow_trades(db)
    db.commit()

    # u1: the pre-follow activity was never copied → exactly 4 rows.
    r = client.get("/api/v1/copy/trades", headers=followed["auth1"])
    assert r.status_code == 200 and r.json()["count"] == 4
    trades = r.json()["trades"]
    simulated = [t for t in trades if t["status"] == "simulated"]
    skipped = [t for t in trades if t["status"] == "skipped"]
    assert {t["trade_type"] for t in simulated} == {"buy", "sell"}
    assert all(t["token_address"] == "TOK1" for t in simulated)
    assert all(t["rug_risk_at_trade"] == 20.0 and t["price_at_trade"] == 0.01
               for t in simulated)
    reasons = {t["token_address"]: t["error_message"] for t in skipped}
    assert reasons["TOKBAD"] == "token blacklisted by subscription"
    assert reasons["TOKHONEY"] == "token flagged as honeypot"

    # u2: everything skipped; TOK1 rows cite the sustainability threshold.
    r = client.get("/api/v1/copy/trades", headers=followed["auth2"])
    assert r.json()["count"] == 4
    assert all(t["status"] == "skipped" for t in r.json()["trades"])
    tok1_reason = next(t["error_message"] for t in r.json()["trades"]
                       if t["token_address"] == "TOK1")
    assert "below" in tok1_reason and "90" in tok1_reason


def test_ledger_filters_and_auth(followed):
    from services.copy.shadow_recorder import record_shadow_trades

    db, client = followed["db"], followed["client"]
    record_shadow_trades(db)
    db.commit()

    r = client.get("/api/v1/copy/trades", params={"status": "simulated"},
                   headers=followed["auth1"])
    assert r.json()["count"] == 2
    r = client.get("/api/v1/copy/trades",
                   params={"subscription_id": followed["sub1"]},
                   headers=followed["auth1"])
    assert r.json()["count"] == 4
    assert client.get("/api/v1/copy/trades").status_code == 401


def test_celery_task_eager(followed):
    from services.discovery.celery_app import celery_app
    import services.discovery.tasks as tasks

    assert "tasks.record_shadow_trades" in celery_app.tasks
    assert "record-shadow-trades" in celery_app.conf.beat_schedule
    result = tasks.record_shadow_trades.delay().get()
    assert result["status"] == "completed"
    assert result["recorded"] == 2 and result["skipped"] == 6
