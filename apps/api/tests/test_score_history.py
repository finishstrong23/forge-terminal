"""GET /api/v1/copy/wallets/{address}/score-history."""

WALLET_A = "walletA"


def _seed_and_score(db, seed_activity, runs: int):
    from services.copy.wallet_scoring import score_and_persist_wallets

    seed_activity(WALLET_A, "TOK1", "buy", 2.0, "sig1", mins_ago=120)
    seed_activity(WALLET_A, "TOK1", "sell", 5.0, "sig2", mins_ago=60)
    seed_activity(WALLET_A, "TOK2", "buy", 1.0, "sig3", mins_ago=30)
    db.commit()
    for _ in range(runs):
        score_and_persist_wallets(db)
        db.commit()


def test_history_ordering_and_limit(client, db, seed_activity):
    _seed_and_score(db, seed_activity, runs=3)

    r = client.get(f"/api/v1/copy/wallets/{WALLET_A}/score-history")
    assert r.status_code == 200
    body = r.json()
    assert body["wallet_address"] == WALLET_A and body["count"] == 3
    timestamps = [s["scored_at"] for s in body["snapshots"]]
    assert timestamps == sorted(timestamps), "snapshots must be oldest-first"
    assert all(s["total_score"] is not None and s["grade"] for s in body["snapshots"])

    r = client.get(f"/api/v1/copy/wallets/{WALLET_A}/score-history", params={"limit": 2})
    assert r.json()["count"] == 2


def test_unscored_wallet_returns_empty_not_404(client, db):
    r = client.get("/api/v1/copy/wallets/nobody/score-history")
    assert r.status_code == 200 and r.json()["count"] == 0
