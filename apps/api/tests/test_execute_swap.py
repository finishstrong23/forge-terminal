"""M3b: swap-transaction proxy + manual trade recording."""
import pytest


@pytest.fixture()
def auth(client, db):
    r = client.post("/api/v1/auth/register",
                    json={"email": "swapper@example.com", "password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


PUBKEY = "UserPubkey111111111111111111111111111111111"
SIG = "5sigSigSigSigSigSigSigSigSigSigSigSigSigSigSigSig"


def test_quote_include_raw_carries_full_payload(client, db, monkeypatch):
    from routes import execute as execute_routes

    full_quote = {"inAmount": "1000000000", "outAmount": "42", "routePlan": [],
                  "extraJupiterField": {"deep": True}}
    monkeypatch.setattr(execute_routes, "get_quote", lambda **kw: full_quote)

    r = client.get("/api/v1/execute/quote", params={
        "token_mint": "TokenMint111111111111111111111111111111111",
        "amount_sol": 1})
    assert "quote_response" not in r.json()

    r = client.get("/api/v1/execute/quote", params={
        "token_mint": "TokenMint111111111111111111111111111111111",
        "amount_sol": 1, "include_raw": True})
    assert r.json()["quote_response"] == full_quote


def test_swap_transaction_proxy(client, db, monkeypatch):
    from routes import execute as execute_routes

    captured = {}

    def fake_build(quote_response, user_public_key, priority_fee_lamports):
        captured.update(quote=quote_response, pubkey=user_public_key,
                        fee=priority_fee_lamports)
        return {"swapTransaction": "base64tx==", "lastValidBlockHeight": 12345}

    monkeypatch.setattr(execute_routes, "get_swap_transaction", fake_build)
    r = client.post("/api/v1/execute/swap-transaction", json={
        "quote_response": {"outAmount": "42"},
        "user_public_key": PUBKEY,
        "priority_fee_lamports": 5000,
    })
    assert r.status_code == 200, r.text
    assert r.json() == {"swap_transaction": "base64tx==", "last_valid_block_height": 12345}
    assert captured["pubkey"] == PUBKEY and captured["fee"] == 5000


def test_swap_transaction_503_when_jupiter_down(client, db, monkeypatch):
    from routes import execute as execute_routes
    from services.execution.jupiter import JupiterUnavailable

    def boom(**kwargs):
        raise JupiterUnavailable("down")

    monkeypatch.setattr(execute_routes, "get_swap_transaction", boom)
    r = client.post("/api/v1/execute/swap-transaction", json={
        "quote_response": {}, "user_public_key": PUBKEY})
    assert r.status_code == 503


def test_record_and_list_manual_trades(client, db, auth, monkeypatch):
    import routes.execute as execute_routes

    monkeypatch.setattr(execute_routes.price_feed, "get_sol_price_usd", lambda: 150.0)

    assert client.post("/api/v1/execute/trades", json={}).status_code in (401, 422)
    assert client.get("/api/v1/execute/trades").status_code == 401

    r = client.post("/api/v1/execute/trades", json={
        "token_address": "MintTok1111111111111111111111111111111111111", "trade_type": "buy",
        "sol_amount": 2.0, "signature": SIG, "slippage_bps": 150,
    }, headers=auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source"] == "manual" and body["status"] == "submitted"
    assert body["usd_value"] == pytest.approx(300.0)
    assert body["slippage_pct"] == pytest.approx(1.5)

    # Duplicate signature -> 409.
    r = client.post("/api/v1/execute/trades", json={
        "token_address": "MintTok1111111111111111111111111111111111111", "trade_type": "buy",
        "sol_amount": 2.0, "signature": SIG,
    }, headers=auth)
    assert r.status_code == 409

    r = client.get("/api/v1/execute/trades", headers=auth)
    assert r.status_code == 200 and r.json()["count"] == 1

    # Manual trades don't leak into the copy-shadow ledger.
    r = client.get("/api/v1/copy/trades", headers=auth)
    assert r.json()["count"] == 0


# ---------- token metadata (M3 follow-up: real decimals) ----------

def test_token_meta_null_when_lookup_unavailable(client, db):
    # conftest stubs the RPC fetch to None.
    r = client.get("/api/v1/execute/token-meta",
                   params={"mint": "TokenMint111111111111111111111111111111111"})
    assert r.status_code == 200
    assert r.json() == {"mint": "TokenMint111111111111111111111111111111111",
                        "decimals": None}


def test_token_meta_returns_decimals(client, db, monkeypatch):
    monkeypatch.setattr(
        "services.execution.token_meta.fetch_token_decimals", lambda mint: 9
    )
    r = client.get("/api/v1/execute/token-meta",
                   params={"mint": "TokenMint111111111111111111111111111111111"})
    assert r.status_code == 200 and r.json()["decimals"] == 9


def test_token_meta_validates_mint(client, db):
    assert client.get("/api/v1/execute/token-meta",
                      params={"mint": "short"}).status_code == 422
