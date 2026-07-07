"""Leaderboard aggregation + /api/v1/copy read endpoints."""
from datetime import datetime, timezone

import pytest

WALLET_A, WALLET_B, WALLET_C = "walletA", "walletB", "walletC"


@pytest.fixture()
def seeded(db, seed_activity):
    from models.token import TokenSignal

    # Wallet A: profitable round trip on TOK1 (buy 2, sell 5) + open buy on
    # TOK2 — 3 trades, 1 win / 1 closed. Plus one buy outside the 24h window.
    seed_activity(WALLET_A, "TOK1", "buy", 2.0, "sigA1", mins_ago=300)
    seed_activity(WALLET_A, "TOK1", "sell", 5.0, "sigA2", mins_ago=200)
    seed_activity(WALLET_A, "TOK2", "buy", 1.0, "sigA3", mins_ago=100)
    seed_activity(WALLET_A, "TOK1", "buy", 99.0, "sigOld", mins_ago=60 * 48)
    # Wallet B: clustered, losing round trip — 3 trades, 0 wins / 1 closed.
    seed_activity(WALLET_B, "TOK1", "buy", 4.0, "sigB1", mins_ago=280, cluster="cl-1")
    seed_activity(WALLET_B, "TOK1", "sell", 1.0, "sigB2", mins_ago=180, cluster="cl-1")
    seed_activity(WALLET_B, "TOK2", "buy", 0.5, "sigB3", mins_ago=90, cluster="cl-1")
    # Wallet C: single trade — filtered by min_trades >= 2.
    seed_activity(WALLET_C, "TOK2", "buy", 9.0, "sigC1", mins_ago=50)

    db.add(TokenSignal(id="ts1", token_address="TOK1", symbol="TOK1SYM",
                       scan_timestamp=datetime.now(timezone.utc)))
    db.commit()
    return db


def test_ranking_and_stats(seeded):
    from services.copy.leaderboard import compute_leaderboard

    lb = compute_leaderboard(seeded, window="24h", limit=10, offset=0, min_trades=2)
    entries = lb["entries"]
    assert [e["wallet_address"] for e in entries] == [WALLET_A, WALLET_B]
    a, b = entries
    assert (a["rank"], b["rank"]) == (1, 2)
    assert a["total_trades"] == 3 and a["tokens_traded"] == 2
    assert a["net_sol"] == pytest.approx(2.0)  # 5 out - (2 + 1) in
    assert (a["closed_positions"], a["wins"], a["win_rate"]) == (1, 1, 1.0)
    assert a["is_clustered"] is False
    assert b["net_sol"] == pytest.approx(-3.5)
    assert b["win_rate"] == 0.0 and b["is_clustered"] is True
    assert a["sustainability_score"] > b["sustainability_score"]
    assert lb["has_more"] is False


def test_min_trades_and_cluster_filters(seeded):
    from services.copy.leaderboard import compute_leaderboard

    all_wallets = compute_leaderboard(seeded, window="24h", limit=10, offset=0, min_trades=1)
    assert {e["wallet_address"] for e in all_wallets["entries"]} == {WALLET_A, WALLET_B, WALLET_C}

    unclustered = compute_leaderboard(
        seeded, window="24h", limit=10, offset=0, min_trades=1, exclude_clustered=True
    )
    assert {e["wallet_address"] for e in unclustered["entries"]} == {WALLET_A, WALLET_C}


def test_pagination(seeded):
    from services.copy.leaderboard import compute_leaderboard

    page1 = compute_leaderboard(seeded, window="24h", limit=1, offset=0, min_trades=2)
    assert page1["has_more"] is True
    assert page1["entries"][0]["wallet_address"] == WALLET_A
    page2 = compute_leaderboard(seeded, window="24h", limit=1, offset=1, min_trades=2)
    assert page2["entries"][0]["wallet_address"] == WALLET_B
    assert page2["entries"][0]["rank"] == 2


def test_window_includes_older_activity(seeded):
    from services.copy.leaderboard import compute_leaderboard

    lb = compute_leaderboard(seeded, window="7d", limit=10, offset=0, min_trades=2)
    a = next(e for e in lb["entries"] if e["wallet_address"] == WALLET_A)
    assert a["net_sol"] == pytest.approx(2.0 - 99.0)


def test_wallet_detail(seeded):
    from services.copy.leaderboard import compute_wallet_detail

    detail = compute_wallet_detail(seeded, WALLET_A, window="24h")
    assert detail["wallet"]["net_sol"] == pytest.approx(2.0)
    # History is all-time: includes the 48h-old buy; symbols enriched.
    assert len(detail["recent_activity"]) == 4
    assert any(r["symbol"] == "TOK1SYM" for r in detail["recent_activity"])
    assert compute_wallet_detail(seeded, "nobody", window="24h") is None


def test_read_endpoints(client, seeded):
    r = client.get("/api/v1/copy/leaderboard", params={"window": "24h", "min_trades": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2 and body["window"] == "24h"
    assert body["entries"][0]["wallet_address"] == WALLET_A

    assert client.get(f"/api/v1/copy/wallets/{WALLET_A}").status_code == 200
    assert client.get("/api/v1/copy/wallets/nobody").status_code == 404
    assert client.get("/api/v1/copy/leaderboard", params={"window": "99h"}).status_code == 422
