"""M3c: manual-trade confirmation checker + sell-side quoting."""
from datetime import datetime, timedelta, timezone

import pytest


def _record_trade(client, auth, signature):
    r = client.post("/api/v1/execute/trades", json={
        "token_address": "MintTok1111111111111111111111111111111111111", "trade_type": "buy",
        "sol_amount": 1.0, "signature": signature,
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture()
def auth(client, db):
    r = client.post("/api/v1/auth/register",
                    json={"email": "confirm@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


SIG_OK = "okSignature11111111111111111111111111111111"
SIG_ERR = "errSignature1111111111111111111111111111111"
SIG_PENDING = "pendingSignature111111111111111111111111111"


def test_confirmations_resolve_statuses(client, db, auth, monkeypatch):
    import services.execution.confirmations as confirmations

    for sig in (SIG_OK, SIG_ERR, SIG_PENDING):
        _record_trade(client, auth, sig)

    def fake_statuses(signatures):
        by_sig = {
            SIG_OK: {"confirmationStatus": "finalized", "err": None},
            SIG_ERR: {"confirmationStatus": "finalized",
                      "err": {"InstructionError": [0, "Custom"]}},
            SIG_PENDING: None,
        }
        return [by_sig[s] for s in signatures]

    monkeypatch.setattr(confirmations, "fetch_signature_statuses", fake_statuses)
    result = confirmations.check_pending_trades(db)
    db.commit()
    assert result == {"pending": 3, "confirmed": 1, "failed": 1}

    trades = {t["signature"]: t for t in
              client.get("/api/v1/execute/trades", headers=auth).json()["trades"]}
    assert trades[SIG_OK]["status"] == "confirmed"
    assert trades[SIG_ERR]["status"] == "failed"
    assert "on-chain error" in trades[SIG_ERR]["error_message"]
    assert trades[SIG_PENDING]["status"] == "submitted"  # young unknown stays


def test_old_unknown_trades_expire(client, db, auth, monkeypatch):
    import services.execution.confirmations as confirmations
    from models.trade import ExecutedTrade

    trade_id = _record_trade(client, auth, SIG_PENDING)
    trade = db.query(ExecutedTrade).filter(ExecutedTrade.id == trade_id).first()
    trade.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.commit()

    monkeypatch.setattr(confirmations, "fetch_signature_statuses",
                        lambda sigs: [None for _ in sigs])
    result = confirmations.check_pending_trades(db)
    db.commit()
    assert result["failed"] == 1
    db.refresh(trade)
    assert trade.status == "failed" and "blockhash expired" in trade.error_message


def test_rpc_failure_leaves_everything_submitted(client, db, auth, monkeypatch):
    import services.execution.confirmations as confirmations

    _record_trade(client, auth, SIG_PENDING)
    monkeypatch.setattr(confirmations, "fetch_signature_statuses", lambda sigs: None)
    result = confirmations.check_pending_trades(db)
    assert result == {"pending": 1, "confirmed": 0, "failed": 0}


def test_confirmation_task_registered(db):
    from services.discovery.celery_app import celery_app
    import services.discovery.tasks as tasks  # noqa: F401

    assert "tasks.check_trade_confirmations" in celery_app.tasks
    assert "check-trade-confirmations" in celery_app.conf.beat_schedule


# ---------- sell-side quoting ----------

def test_sell_quote_swaps_direction_and_converts_decimals(client, db, monkeypatch):
    from routes import execute as execute_routes
    from services.execution.price_feed import SOL_MINT

    captured = {}

    def fake_quote(input_mint, output_mint, amount_raw, slippage_bps):
        captured.update(input_mint=input_mint, output_mint=output_mint,
                        amount_raw=amount_raw)
        return {"inAmount": str(amount_raw), "outAmount": "990000000",
                "routePlan": []}

    monkeypatch.setattr(execute_routes, "get_quote", fake_quote)
    r = client.get("/api/v1/execute/quote", params={
        "token_mint": "TokenMint111111111111111111111111111111111",
        "side": "sell",
        "amount_tokens": 1500,
        "token_decimals": 6,
    })
    assert r.status_code == 200, r.text
    assert captured["input_mint"] == "TokenMint111111111111111111111111111111111"
    assert captured["output_mint"] == SOL_MINT
    assert captured["amount_raw"] == 1_500_000_000
    assert r.json()["side"] == "sell"


def test_quote_side_amount_requirements(client, db):
    mint = "TokenMint111111111111111111111111111111111"
    # Buy without amount_sol / sell without amount_tokens -> 422.
    assert client.get("/api/v1/execute/quote",
                      params={"token_mint": mint}).status_code == 422
    assert client.get("/api/v1/execute/quote",
                      params={"token_mint": mint, "side": "sell"}).status_code == 422
