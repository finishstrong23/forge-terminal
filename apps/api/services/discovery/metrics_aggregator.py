"""
Metrics Aggregator
===================

Computes time-windowed metrics from WalletActivity data, replacing the
running-counter approach that never reset.

Supports:
- Real 5m / 15m / 1h windows (buys, sells, SOL flow, retention)
- Periodic snapshots for charting (MetricSnapshot)
- Live rolling-window queries for current signal scoring
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, and_

from models.wallet import WalletActivity
from models.token import MetricSnapshot, TokenSignal


# Window durations in minutes
WINDOW_DURATIONS = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
}


def get_current_metrics(db: Session, token_address: str) -> Dict:
    """
    Compute live rolling-window metrics for a token from WalletActivity data.

    Returns a dict compatible with TokenSignal fields:
        buys_5m, sells_5m, buy_ratio_5m, retention_5m,
        net_sol_flow_15m, entity_adjusted_buyers, total_holders, holder_growth_rate
    """
    now = datetime.now(timezone.utc)
    cutoff_5m = now - timedelta(minutes=5)
    cutoff_15m = now - timedelta(minutes=15)

    # 5-minute window: buys + sells
    buys_5m = db.query(func.count(WalletActivity.id)).filter(
        WalletActivity.token_address == token_address,
        WalletActivity.activity_type == "buy",
        WalletActivity.timestamp >= cutoff_5m,
    ).scalar() or 0

    sells_5m = db.query(func.count(WalletActivity.id)).filter(
        WalletActivity.token_address == token_address,
        WalletActivity.activity_type == "sell",
        WalletActivity.timestamp >= cutoff_5m,
    ).scalar() or 0

    total_txs_5m = buys_5m + sells_5m
    buy_ratio_5m = (buys_5m / total_txs_5m * 100) if total_txs_5m > 0 else 50.0

    # 15-minute window: net SOL flow
    sol_inflow = db.query(func.coalesce(func.sum(WalletActivity.sol_amount), 0)).filter(
        WalletActivity.token_address == token_address,
        WalletActivity.activity_type == "buy",
        WalletActivity.timestamp >= cutoff_15m,
        WalletActivity.sol_amount.isnot(None),
    ).scalar() or 0

    sol_outflow = db.query(func.coalesce(func.sum(WalletActivity.sol_amount), 0)).filter(
        WalletActivity.token_address == token_address,
        WalletActivity.activity_type == "sell",
        WalletActivity.timestamp >= cutoff_15m,
        WalletActivity.sol_amount.isnot(None),
    ).scalar() or 0

    net_sol_flow_15m = float(sol_inflow) - float(sol_outflow)

    # All-time: unique buyers (entities) and retention
    all_buyers = set(
        row[0] for row in db.query(distinct(WalletActivity.wallet_address)).filter(
            WalletActivity.token_address == token_address,
            WalletActivity.activity_type == "buy",
        ).all()
    )

    all_sellers = set(
        row[0] for row in db.query(distinct(WalletActivity.wallet_address)).filter(
            WalletActivity.token_address == token_address,
            WalletActivity.activity_type == "sell",
        ).all()
    )

    total_unique_buyers = len(all_buyers)
    holders = all_buyers - all_sellers
    net_holders = len(holders)

    retention_5m = (net_holders / total_unique_buyers * 100) if total_unique_buyers > 0 else 100.0

    return {
        "buys_5m": buys_5m,
        "sells_5m": sells_5m,
        "buy_ratio_5m": round(buy_ratio_5m, 2),
        "net_sol_flow_15m": round(net_sol_flow_15m, 4),
        "retention_5m": round(retention_5m, 2),
        "total_holders": net_holders,
        "total_unique_buyers": total_unique_buyers,
    }


def aggregate_window(
    db: Session,
    token_address: str,
    window_type: str,
    window_end: Optional[datetime] = None,
) -> Optional[MetricSnapshot]:
    """
    Create a MetricSnapshot for a specific time window.

    Args:
        db: Database session
        token_address: Token mint address
        window_type: "5m", "15m", or "1h"
        window_end: End of the window (defaults to now)

    Returns:
        The created MetricSnapshot or None if no data
    """
    duration = WINDOW_DURATIONS.get(window_type)
    if not duration:
        return None

    if window_end is None:
        window_end = datetime.now(timezone.utc)

    window_start = window_end - timedelta(minutes=duration)

    # Check for existing snapshot (idempotent)
    existing = db.query(MetricSnapshot).filter(
        MetricSnapshot.token_address == token_address,
        MetricSnapshot.window_type == window_type,
        MetricSnapshot.window_start == window_start,
    ).first()

    if existing:
        return existing

    # Aggregate from WalletActivity
    activities = db.query(WalletActivity).filter(
        WalletActivity.token_address == token_address,
        WalletActivity.timestamp >= window_start,
        WalletActivity.timestamp < window_end,
    ).all()

    if not activities:
        return None

    buys = sum(1 for a in activities if a.activity_type == "buy")
    sells = sum(1 for a in activities if a.activity_type == "sell")
    unique_buyers = len(set(a.wallet_address for a in activities if a.activity_type == "buy"))
    unique_sellers = len(set(a.wallet_address for a in activities if a.activity_type == "sell"))

    sol_inflow = sum(a.sol_amount or 0 for a in activities if a.activity_type == "buy")
    sol_outflow = sum(a.sol_amount or 0 for a in activities if a.activity_type == "sell")
    net_sol_flow = sol_inflow - sol_outflow

    buy_ratio = (buys / (buys + sells) * 100) if (buys + sells) > 0 else 0

    # Retention: buyers who didn't sell in this window
    buyer_wallets = set(a.wallet_address for a in activities if a.activity_type == "buy")
    seller_wallets = set(a.wallet_address for a in activities if a.activity_type == "sell")
    retained = buyer_wallets - seller_wallets
    retention_pct = (len(retained) / len(buyer_wallets) * 100) if buyer_wallets else 0

    snapshot = MetricSnapshot(
        token_address=token_address,
        window_type=window_type,
        window_start=window_start,
        window_end=window_end,
        buys=buys,
        sells=sells,
        unique_buyers=unique_buyers,
        unique_sellers=unique_sellers,
        sol_inflow=round(sol_inflow, 6),
        sol_outflow=round(sol_outflow, 6),
        net_sol_flow=round(net_sol_flow, 6),
        retention_pct=round(retention_pct, 2),
        buy_ratio=round(buy_ratio, 2),
    )

    db.add(snapshot)
    db.flush()
    return snapshot


def build_chart_data(
    db: Session,
    token_address: str,
    window_type: str = "5m",
    periods: int = 12,
) -> List[Dict]:
    """
    Return the last N snapshots for frontend charting.
    """
    snapshots = db.query(MetricSnapshot).filter(
        MetricSnapshot.token_address == token_address,
        MetricSnapshot.window_type == window_type,
    ).order_by(MetricSnapshot.window_start.desc()).limit(periods).all()

    # Reverse to chronological order
    snapshots.reverse()

    return [
        {
            "window_start": s.window_start.isoformat(),
            "window_end": s.window_end.isoformat(),
            "buys": s.buys,
            "sells": s.sells,
            "unique_buyers": s.unique_buyers,
            "sol_inflow": s.sol_inflow,
            "sol_outflow": s.sol_outflow,
            "net_sol_flow": s.net_sol_flow,
            "retention_pct": s.retention_pct,
            "buy_ratio": s.buy_ratio,
        }
        for s in snapshots
    ]


def aggregate_active_tokens(db: Session):
    """
    Aggregate metric snapshots for all tokens with recent activity.
    Called by the periodic Celery task.
    """
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # Find tokens with activity in the last hour
    active_tokens = db.query(distinct(WalletActivity.token_address)).filter(
        WalletActivity.timestamp >= one_hour_ago,
    ).all()

    aggregated = 0
    for (token_address,) in active_tokens:
        for window_type in ["5m", "15m"]:
            snapshot = aggregate_window(db, token_address, window_type, window_end=now)
            if snapshot:
                aggregated += 1

    db.commit()
    return aggregated
