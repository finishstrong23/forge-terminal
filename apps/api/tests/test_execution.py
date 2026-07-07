"""M3a execution foundation: price feed, USD caps in shadow mode, quote proxy."""
from datetime import datetime, timedelta, timezone

import pytest


# ---------- price feed ----------

def test_price_endpoint_503_when_sources_down(client, db):
    # conftest stubs the live fetch to None and test Redis is unreachable.
    r = client.get("/api/v1/execute/price")
    assert r.status_code == 503


def test_price_endpoint_returns_price(client, db, monkeypatch):
    from services.execution import price_feed

    monkeypatch.setattr(price_feed, "fetch_sol_price_usd", lambda: 142.5)
    r = client.get("/api/v1/execute/price")
    assert r.status_code == 200 and r.json() == {"sol_usd": 142.5}


def test_refresh_task_reports_no_price(db):
    import services.discovery.tasks as tasks
    from services.discovery.celery_app import celery_app

    assert "tasks.refresh_sol_price" in celery_app.tasks
    assert "refresh-sol-price" in celery_app.conf.beat_schedule
    result = tasks.refresh_sol_price.delay().get()
    assert result["status"] == "no_price"  # sources stubbed to None


# ---------- USD cap enforcement in shadow mode ----------

def test_shadow_recorder_enforces_max_position_usd(client, db, seed_activity, monkeypatch):
    import services.copy.shadow_recorder as recorder

    seed_activity("walletA", "TOK1", "buy", 1.0, "pre", mins_ago=30)
    db.commit()

    r = client.post("/api/v1/auth/register",
                    json={"email": "cap@example.com", "password": "password123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/v1/copy/subscriptions",
                    json={"wallet_address": "walletA", "max_position_usd": 100},
                    headers=auth)
    assert r.status_code == 201

    fresh = datetime.now(timezone.utc) + timedelta(seconds=1)
    seed_activity("walletA", "TOK1", "buy", 0.5, "small", ts=fresh)  # $50 @ $100/SOL
    seed_activity("walletA", "TOK1", "buy", 2.0, "large", ts=fresh)  # $200 @ $100/SOL
    db.commit()

    monkeypatch.setattr(recorder, "get_sol_price_usd", lambda: 100.0)
    result = recorder.record_shadow_trades(db)
    db.commit()
    assert result == {"subscriptions": 1, "recorded": 1, "skipped": 1}

    trades = client.get("/api/v1/copy/trades", headers=auth).json()["trades"]
    by_status = {t["status"]: t for t in trades}
    assert by_status["simulated"]["usd_value"] == pytest.approx(50.0)
    assert by_status["skipped"]["usd_value"] == pytest.approx(200.0)
    assert "exceeds cap $100.00" in by_status["skipped"]["error_message"]


def test_shadow_recorder_skips_usd_cap_without_price(client, db, seed_activity, monkeypatch):
    import services.copy.shadow_recorder as recorder

    seed_activity("walletB", "TOK1", "buy", 1.0, "preB", mins_ago=30)
    db.commit()
    r = client.post("/api/v1/auth/register",
                    json={"email": "noprice@example.com", "password": "password123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/api/v1/copy/subscriptions",
                json={"wallet_address": "walletB", "max_position_usd": 1},
                headers=auth)

    fresh = datetime.now(timezone.utc) + timedelta(seconds=1)
    seed_activity("walletB", "TOK1", "buy", 50.0, "big", ts=fresh)
    db.commit()

    monkeypatch.setattr(recorder, "get_sol_price_usd", lambda: None)
    result = recorder.record_shadow_trades(db)
    db.commit()
    # No price -> cap unenforceable -> recorded as simulated with NULL usd.
    assert result["recorded"] == 1 and result["skipped"] == 0
    trades = client.get("/api/v1/copy/trades", headers=auth).json()["trades"]
    assert trades[0]["usd_value"] is None


# ---------- quote proxy ----------

def test_quote_endpoint_trims_jupiter_payload(client, db, monkeypatch):
    from routes import execute as execute_routes

    captured = {}

    def fake_quote(input_mint, output_mint, amount_raw, slippage_bps):
        captured.update(input_mint=input_mint, output_mint=output_mint,
                        amount_raw=amount_raw, slippage_bps=slippage_bps)
        return {
            "inAmount": str(amount_raw),
            "outAmount": "123456789",
            "otherAmountThreshold": "122222222",
            "priceImpactPct": "0.0042",
            "slippageBps": slippage_bps,
            "routePlan": [{"swapInfo": {"label": "Raydium"}},
                          {"swapInfo": {"label": "Orca"}}],
        }

    monkeypatch.setattr(execute_routes, "get_quote", fake_quote)
    r = client.get("/api/v1/execute/quote", params={
        "token_mint": "TokenMint111111111111111111111111111111111",
        "amount_sol": 1.5,
        "slippage_bps": 150,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert captured["amount_raw"] == 1_500_000_000
    assert captured["slippage_bps"] == 150
    assert body["out_amount"] == "123456789"
    assert body["route_labels"] == ["Raydium", "Orca"]


def test_quote_endpoint_503_when_jupiter_down(client, db, monkeypatch):
    from routes import execute as execute_routes
    from services.execution.jupiter import JupiterUnavailable

    def boom(**kwargs):
        raise JupiterUnavailable("Jupiter quote unavailable: connect timeout")

    monkeypatch.setattr(execute_routes, "get_quote", boom)
    r = client.get("/api/v1/execute/quote", params={
        "token_mint": "TokenMint111111111111111111111111111111111",
        "amount_sol": 1,
    })
    assert r.status_code == 503


def test_quote_endpoint_validates_params(client, db):
    assert client.get("/api/v1/execute/quote", params={
        "token_mint": "short", "amount_sol": 1}).status_code == 422
    assert client.get("/api/v1/execute/quote", params={
        "token_mint": "TokenMint111111111111111111111111111111111",
        "amount_sol": -1}).status_code == 422
