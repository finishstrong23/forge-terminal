"""
Copy Intelligence — wallet leaderboard aggregation (Phase 2, v1).

Computes wallet performance stats from WalletActivity rows recorded by the
discovery webhook pipeline (services/discovery/wallet_clustering.py). No new
ingestion is required: every Helius swap event already lands here with
wallet, token, side, SOL amount, cluster id, and timestamp.

Metric definitions (v1 — SOL-flow realized PnL proxy):
- A wallet's per-token "net SOL" = SOL received from sells - SOL spent on buys
  within the window. This understates PnL for positions still held (unsold
  inventory is valued at 0) and is therefore conservative.
- A token position is "closed" if the wallet has >= 1 sell of it in-window.
- A "win" is a closed position with positive net SOL.
- win_rate = wins / closed_positions (None when nothing closed yet).

Sustainability score (v1 heuristic — replace with the WalletScore model
pipeline when persistent scoring lands):
    45 pts * win_rate            (0.4 neutral default when no closed positions)
  + 25 pts * persistence         (active days / window days, capped at 1)
  + 30 pts * flow factor         (net SOL soft-clamped at +/- FLOW_SCALE_SOL)
  * 0.6 cluster penalty          (wallet funded from a known cluster = insider risk)
Grades: A >= 75, B >= 60, C >= 45, else D.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, distinct, func
from sqlalchemy.orm import Session

from models.token import TokenSignal
from models.wallet import WalletActivity

logger = logging.getLogger(__name__)

WINDOW_HOURS = {"24h": 24, "7d": 168, "30d": 720}

# Net SOL at which the flow component of the sustainability score saturates.
FLOW_SCALE_SOL = 50.0


def _per_token_subquery(db: Session, cutoff: datetime, wallet_address: Optional[str] = None):
    """Per (wallet, token) aggregates within the window — the inner rollup."""
    filters = [
        WalletActivity.timestamp >= cutoff,
        WalletActivity.activity_type.in_(["buy", "sell"]),
    ]
    if wallet_address:
        filters.append(WalletActivity.wallet_address == wallet_address)

    return (
        db.query(
            WalletActivity.wallet_address.label("wallet"),
            WalletActivity.token_address.label("token"),
            func.count(WalletActivity.id).label("trades"),
            func.sum(case((WalletActivity.activity_type == "buy", 1), else_=0)).label("buys"),
            func.sum(case((WalletActivity.activity_type == "sell", 1), else_=0)).label("sells"),
            func.coalesce(
                func.sum(case((WalletActivity.activity_type == "buy", WalletActivity.sol_amount), else_=0.0)),
                0.0,
            ).label("sol_in"),
            func.coalesce(
                func.sum(case((WalletActivity.activity_type == "sell", WalletActivity.sol_amount), else_=0.0)),
                0.0,
            ).label("sol_out"),
            func.max(WalletActivity.timestamp).label("last_ts"),
            func.max(WalletActivity.cluster_id).label("cluster_id"),
        )
        .filter(*filters)
        .group_by(WalletActivity.wallet_address, WalletActivity.token_address)
        .subquery()
    )


def _active_days_by_wallet(db: Session, wallets: List[str], cutoff: datetime) -> Dict[str, int]:
    """Distinct UTC days with activity per wallet, for the persistence component."""
    if not wallets:
        return {}
    rows = (
        db.query(
            WalletActivity.wallet_address,
            func.count(distinct(func.date(WalletActivity.timestamp))),
        )
        .filter(
            WalletActivity.wallet_address.in_(wallets),
            WalletActivity.timestamp >= cutoff,
        )
        .group_by(WalletActivity.wallet_address)
        .all()
    )
    return {addr: int(days) for addr, days in rows}


def compute_sustainability(
    win_rate: Optional[float],
    active_days: int,
    window_days: float,
    net_sol: float,
    is_clustered: bool,
) -> float:
    win_component = 45.0 * (win_rate if win_rate is not None else 0.4)
    persistence = min(active_days / max(window_days, 1.0), 1.0)
    persistence_component = 25.0 * persistence
    flow = max(-1.0, min(1.0, net_sol / FLOW_SCALE_SOL))
    flow_component = 30.0 * (0.5 + flow / 2.0)
    score = win_component + persistence_component + flow_component
    if is_clustered:
        score *= 0.6
    return round(min(score, 100.0), 1)


def grade_for_score(score: float) -> str:
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def _row_to_entry(row, active_days: int, window_hours: int) -> Dict[str, Any]:
    sol_in = float(row.sol_in or 0.0)
    sol_out = float(row.sol_out or 0.0)
    net_sol = sol_out - sol_in
    closed = int(row.closed_positions or 0)
    wins = int(row.wins or 0)
    win_rate = round(wins / closed, 4) if closed > 0 else None
    is_clustered = row.cluster_id is not None
    score = compute_sustainability(
        win_rate=win_rate,
        active_days=active_days,
        window_days=window_hours / 24.0,
        net_sol=net_sol,
        is_clustered=is_clustered,
    )
    last_active = row.last_active
    if last_active is not None and last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)
    return {
        "wallet_address": row.wallet_address,
        "total_trades": int(row.total_trades or 0),
        "buy_count": int(row.buy_count or 0),
        "sell_count": int(row.sell_count or 0),
        "tokens_traded": int(row.tokens_traded or 0),
        "closed_positions": closed,
        "wins": wins,
        "win_rate": win_rate,
        "sol_in": round(sol_in, 4),
        "sol_out": round(sol_out, 4),
        "net_sol": round(net_sol, 4),
        "active_days": active_days,
        "sustainability_score": score,
        "sustainability_grade": grade_for_score(score),
        "is_clustered": is_clustered,
        "last_active": last_active.isoformat() if last_active else None,
    }


def compute_leaderboard(
    db: Session,
    window: str = "24h",
    limit: int = 25,
    offset: int = 0,
    min_trades: int = 3,
    exclude_clustered: bool = False,
) -> Dict[str, Any]:
    """
    Ranked wallet leaderboard for the window, ordered by net SOL descending.

    Returns {"entries": [...], "has_more": bool} with plain-dict entries
    (ISO timestamps) so the result is JSON-cacheable as-is.
    """
    window_hours = WINDOW_HOURS[window]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    per_token = _per_token_subquery(db, cutoff)

    sol_in_sum = func.coalesce(func.sum(per_token.c.sol_in), 0.0)
    sol_out_sum = func.coalesce(func.sum(per_token.c.sol_out), 0.0)

    query = (
        db.query(
            per_token.c.wallet.label("wallet_address"),
            func.count().label("tokens_traded"),
            func.sum(per_token.c.trades).label("total_trades"),
            func.sum(per_token.c.buys).label("buy_count"),
            func.sum(per_token.c.sells).label("sell_count"),
            sol_in_sum.label("sol_in"),
            sol_out_sum.label("sol_out"),
            func.sum(case((per_token.c.sells > 0, 1), else_=0)).label("closed_positions"),
            func.sum(
                case(
                    (and_(per_token.c.sells > 0, per_token.c.sol_out > per_token.c.sol_in), 1),
                    else_=0,
                )
            ).label("wins"),
            func.max(per_token.c.last_ts).label("last_active"),
            func.max(per_token.c.cluster_id).label("cluster_id"),
        )
        .group_by(per_token.c.wallet)
        .having(func.sum(per_token.c.trades) >= min_trades)
    )
    if exclude_clustered:
        query = query.having(func.max(per_token.c.cluster_id).is_(None))

    # Fetch limit+1 so has_more needs no separate COUNT (same trick as the
    # discovery feed endpoint).
    rows = (
        query.order_by((sol_out_sum - sol_in_sum).desc())
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    days_map = _active_days_by_wallet(db, [r.wallet_address for r in rows], cutoff)
    entries = []
    for i, row in enumerate(rows):
        entry = _row_to_entry(row, days_map.get(row.wallet_address, 0), window_hours)
        entry["rank"] = offset + i + 1
        entries.append(entry)

    logger.info(
        "copy/leaderboard: window=%s returned=%d has_more=%s min_trades=%d exclude_clustered=%s",
        window, len(entries), has_more, min_trades, exclude_clustered,
    )
    return {"entries": entries, "has_more": has_more}


def _symbol_map(db: Session, token_addresses: List[str]) -> Dict[str, str]:
    """Best-effort token_address -> symbol lookup from discovery scans."""
    if not token_addresses:
        return {}
    rows = (
        db.query(TokenSignal.token_address, TokenSignal.symbol)
        .filter(
            TokenSignal.token_address.in_(token_addresses),
            TokenSignal.symbol.isnot(None),
        )
        .all()
    )
    result: Dict[str, str] = {}
    for addr, symbol in rows:
        if addr and addr not in result:
            result[addr] = symbol
    return result


def compute_wallet_detail(
    db: Session,
    wallet_address: str,
    window: str = "24h",
    activity_limit: int = 50,
) -> Optional[Dict[str, Any]]:
    """
    Windowed stats + recent trade history for one wallet.

    Stats use the leaderboard window; the recent-activity list is all-time
    (last `activity_limit` events) so the panel isn't empty for a wallet
    that was active just outside the window. Returns None if the wallet has
    never recorded any activity.
    """
    has_any = (
        db.query(WalletActivity.id)
        .filter(WalletActivity.wallet_address == wallet_address)
        .first()
    )
    if not has_any:
        return None

    window_hours = WINDOW_HOURS[window]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    per_token = _per_token_subquery(db, cutoff, wallet_address=wallet_address)

    sol_in_sum = func.coalesce(func.sum(per_token.c.sol_in), 0.0)
    sol_out_sum = func.coalesce(func.sum(per_token.c.sol_out), 0.0)
    row = (
        db.query(
            per_token.c.wallet.label("wallet_address"),
            func.count().label("tokens_traded"),
            func.sum(per_token.c.trades).label("total_trades"),
            func.sum(per_token.c.buys).label("buy_count"),
            func.sum(per_token.c.sells).label("sell_count"),
            sol_in_sum.label("sol_in"),
            sol_out_sum.label("sol_out"),
            func.sum(case((per_token.c.sells > 0, 1), else_=0)).label("closed_positions"),
            func.sum(
                case(
                    (and_(per_token.c.sells > 0, per_token.c.sol_out > per_token.c.sol_in), 1),
                    else_=0,
                )
            ).label("wins"),
            func.max(per_token.c.last_ts).label("last_active"),
            func.max(per_token.c.cluster_id).label("cluster_id"),
        )
        .group_by(per_token.c.wallet)
        .first()
    )

    if row is not None:
        days_map = _active_days_by_wallet(db, [wallet_address], cutoff)
        stats = _row_to_entry(row, days_map.get(wallet_address, 0), window_hours)
    else:
        # Wallet exists but has no in-window activity: zeroed stats.
        stats = {
            "wallet_address": wallet_address,
            "total_trades": 0,
            "buy_count": 0,
            "sell_count": 0,
            "tokens_traded": 0,
            "closed_positions": 0,
            "wins": 0,
            "win_rate": None,
            "sol_in": 0.0,
            "sol_out": 0.0,
            "net_sol": 0.0,
            "active_days": 0,
            "sustainability_score": compute_sustainability(None, 0, window_hours / 24.0, 0.0, False),
            "sustainability_grade": None,
            "is_clustered": False,
            "last_active": None,
        }
        stats["sustainability_grade"] = grade_for_score(stats["sustainability_score"])

    activities = (
        db.query(WalletActivity)
        .filter(WalletActivity.wallet_address == wallet_address)
        .order_by(WalletActivity.timestamp.desc())
        .limit(activity_limit)
        .all()
    )
    symbols = _symbol_map(db, list({a.token_address for a in activities}))
    recent = []
    for a in activities:
        ts = a.timestamp
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        recent.append(
            {
                "token_address": a.token_address,
                "symbol": symbols.get(a.token_address),
                "activity_type": a.activity_type,
                "sol_amount": a.sol_amount,
                "signature": a.event_signature,
                "timestamp": ts.isoformat() if ts else None,
            }
        )

    return {"wallet": stats, "recent_activity": recent}
