"""Wallet score persistence (Wallet upserts + WalletScore snapshots)."""
import pytest

WALLET_A, WALLET_B, WALLET_C = "walletA", "walletB", "walletC"


@pytest.fixture()
def seeded(db, seed_activity):
    # walletA: old big buy (48h) + round trip + open position → 4 trades in 30d.
    seed_activity(WALLET_A, "TOK1", "buy", 99.0, "sigOld", mins_ago=60 * 48)
    seed_activity(WALLET_A, "TOK1", "buy", 2.0, "sigA1", mins_ago=300)
    seed_activity(WALLET_A, "TOK1", "sell", 5.0, "sigA2", mins_ago=200)
    seed_activity(WALLET_A, "TOK2", "buy", 1.0, "sigA3", mins_ago=100)
    # walletB: clustered, losing round trip.
    seed_activity(WALLET_B, "TOK1", "buy", 4.0, "sigB1", mins_ago=280, cluster="cl-1")
    seed_activity(WALLET_B, "TOK1", "sell", 1.0, "sigB2", mins_ago=180, cluster="cl-1")
    seed_activity(WALLET_B, "TOK2", "buy", 0.5, "sigB3", mins_ago=90, cluster="cl-1")
    # walletC: single trade — below min_trades.
    seed_activity(WALLET_C, "TOK2", "buy", 9.0, "sigC1", mins_ago=50)
    db.commit()
    return db


def test_persist_aggregates_and_snapshots(seeded):
    from models.wallet import Wallet, WalletScore
    from services.copy.wallet_scoring import score_and_persist_wallets

    result = score_and_persist_wallets(seeded)
    seeded.commit()
    assert result["wallets_scored"] == 2

    wallets = {w.address: w for w in seeded.query(Wallet).all()}
    assert set(wallets) == {WALLET_A, WALLET_B}
    a, b = wallets[WALLET_A], wallets[WALLET_B]
    assert a.pnl_30d == pytest.approx(5.0 - 102.0)
    assert b.pnl_30d == pytest.approx(-3.5)
    assert a.win_rate_30d == 0.0  # TOK1 closed at a loss inside the 30d window
    assert (a.trade_count_30d, b.trade_count_30d) == (4, 3)
    # First buy 48h ago → first sell 200m ago = 2680m; TOK2 never sold.
    assert a.avg_hold_minutes == pytest.approx(2680.0, abs=1.0)
    assert b.avg_hold_minutes == pytest.approx(100.0, abs=1.0)
    assert a.first_seen is not None and a.last_active is not None
    assert a.sustainability_grade in {"A", "B", "C", "D"}
    assert a.pnl_60d == pytest.approx(5.0 - 102.0)
    assert a.pnl_90d == pytest.approx(5.0 - 102.0)

    scores = {s.wallet_address: s for s in seeded.query(WalletScore).all()}
    assert len(scores) == 2
    sa, sb = scores[WALLET_A], scores[WALLET_B]
    assert sa.total_score == a.sustainability_score and sa.grade == a.sustainability_grade
    assert sa.insider_penalty == 0.0
    assert sb.insider_penalty > 0.0  # clustered wallet loses points
    assert sa.hold_pattern_score == 100.0  # 2680m saturates at 60m
    assert sa.win_rate_score == 0.0 and sa.persistence_score > 0
    assert sa.details["window"] == "30d" and sa.details["is_clustered"] is False
    assert sb.details["is_clustered"] is True


def test_rerun_upserts_wallets_appends_scores(seeded):
    from models.wallet import Wallet, WalletScore
    from services.copy.wallet_scoring import score_and_persist_wallets

    for _ in range(2):
        score_and_persist_wallets(seeded)
        seeded.commit()
    assert seeded.query(Wallet).count() == 2
    assert seeded.query(WalletScore).count() == 4


def test_celery_task_eager(seeded):
    from models.wallet import WalletScore
    from services.discovery.celery_app import celery_app
    import services.discovery.tasks as tasks

    assert "tasks.score_wallets" in celery_app.tasks
    assert "score-wallets-15m" in celery_app.conf.beat_schedule
    result = tasks.score_wallets.delay().get()
    assert result["status"] == "completed" and result["wallets_scored"] == 2
    assert seeded.query(WalletScore).count() == 2
