"""M3e: portfolio positions — ExecutedTrade aggregation + PnL."""
import pytest


@pytest.fixture()
def auth(client, db):
    r = client.post("/api/v1/auth/register",
                    json={"email": "holder@example.com", "password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _record(client, auth, *, token, side, sol, tokens=None, sig):
    body = {"token_address": token, "trade_type": side,
            "sol_amount": sol, "signature": sig}
    if tokens is not None:
        body["token_amount"] = tokens
    r = client.post("/api/v1/execute/trades", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_positions_requires_auth(client, db):
    assert client.get("/api/v1/execute/positions").status_code == 401


def test_positions_empty_without_trades(client, db, auth):
    r = client.get("/api/v1/execute/positions", headers=auth)
    assert r.status_code == 200
    assert r.json() == {"positions": [], "count": 0, "sol_usd": None}


def test_position_aggregates_avg_cost_and_realized_pnl(client, db, auth, monkeypatch):
    # 2 SOL -> 1000 tokens, 1 SOL -> 1000 tokens: avg cost 0.0015 SOL/token.
    _record(client, auth, token="MintTokAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", side="buy", sol=2.0, tokens=1000, sig="s" * 40)
    _record(client, auth, token="MintTokAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", side="buy", sol=1.0, tokens=1000, sig="t" * 40)
    # Sell 500 tokens for 1.5 SOL: realized = 1.5 - 500*0.0015 = 0.75 SOL.
    _record(client, auth, token="MintTokAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", side="sell", sol=1.5, tokens=500, sig="u" * 40)

    r = client.get("/api/v1/execute/positions", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    p = body["positions"][0]
    assert p["token_address"] == "MintTokAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert p["trade_count"] == 3
    assert p["bought_sol"] == pytest.approx(3.0)
    assert p["sold_sol"] == pytest.approx(1.5)
    assert p["net_tokens"] == pytest.approx(1500)
    assert p["cost_basis_sol"] == pytest.approx(1500 * 0.0015)
    assert p["realized_pnl_sol"] == pytest.approx(0.75)
    # Token price feed stubbed to None in conftest -> no mark-to-market.
    assert p["token_price_usd"] is None
    assert p["value_sol"] is None and p["unrealized_pnl_sol"] is None


def test_position_quantities_unknown_without_token_amount(client, db, auth):
    # Legacy row: no token_amount. SOL flows still aggregate; quantity math
    # degrades to None instead of guessing.
    _record(client, auth, token="MintTokBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", side="buy", sol=1.0, sig="v" * 40)
    r = client.get("/api/v1/execute/positions", headers=auth)
    p = r.json()["positions"][0]
    assert p["bought_sol"] == pytest.approx(1.0)
    assert p["net_tokens"] is None
    assert p["cost_basis_sol"] is None and p["realized_pnl_sol"] is None


def test_positions_exclude_failed_and_shadow_rows(client, db, auth):
    from models.trade import ExecutedTrade
    from models.user import User

    trade = _record(client, auth, token="MintTokCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC", side="buy", sol=1.0,
                    tokens=100, sig="w" * 40)
    user_id = db.query(User.id).filter(User.email == "holder@example.com").scalar()

    db.add(ExecutedTrade(user_id=user_id, token_address="MintTokCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC", trade_type="buy",
                         source="manual", sol_amount=9.0, token_amount=900,
                         signature="x" * 40, status="failed"))
    db.add(ExecutedTrade(user_id=user_id, token_address="MintTokCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC", trade_type="buy",
                         source="copy_shadow", sol_amount=9.0, token_amount=900,
                         status="simulated"))
    db.commit()

    r = client.get("/api/v1/execute/positions", headers=auth)
    p = r.json()["positions"][0]
    assert p["trade_count"] == 1
    assert p["bought_sol"] == pytest.approx(1.0)
    assert trade["status"] == "submitted"  # optimistic rows DO count


def test_positions_mark_to_market_with_prices(client, db, auth, monkeypatch):
    import routes.execute as execute_routes

    _record(client, auth, token="MintTokDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD", side="buy", sol=2.0, tokens=1000, sig="y" * 40)

    monkeypatch.setattr(execute_routes.price_feed, "get_sol_price_usd", lambda: 100.0)
    monkeypatch.setattr(
        execute_routes.price_feed, "get_token_prices_usd",
        lambda mints: {m: 0.5 for m in mints},
    )
    r = client.get("/api/v1/execute/positions", headers=auth)
    body = r.json()
    assert body["sol_usd"] == pytest.approx(100.0)
    p = body["positions"][0]
    # 1000 tokens * $0.5 / $100-per-SOL = 5 SOL; cost 2 SOL -> +3 SOL unrealized.
    assert p["value_sol"] == pytest.approx(5.0)
    assert p["unrealized_pnl_sol"] == pytest.approx(3.0)


def test_manual_trade_stamps_risk_context(client, db, auth):
    from datetime import datetime, timezone
    from models.token import TokenSignal

    db.add(TokenSignal(scan_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                       token_address="MintTokEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE", rug_risk_score=20.0, momentum_score=50.0))
    db.add(TokenSignal(scan_timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
                       token_address="MintTokEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE", rug_risk_score=35.0, momentum_score=80.0))
    db.commit()

    body = _record(client, auth, token="MintTokEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE", side="buy", sol=1.0,
                   tokens=10, sig="z" * 40)
    # The LATEST signal wins.
    assert body["rug_risk_at_trade"] == pytest.approx(35.0)
    assert body["momentum_at_trade"] == pytest.approx(80.0)
    assert body["token_amount"] == pytest.approx(10)
