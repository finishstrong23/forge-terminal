"""
Copy Intelligence — wallet score persistence (Phase 2, v1).

Periodically materializes the live leaderboard aggregation into the Wallet
(rolling aggregates) and WalletScore (scored_at snapshots) tables, so score
history accumulates for copy-trading decisions and the leaderboard formula
stays consistent between the live endpoint and persisted rows: total_score
IS the same v1 sustainability score computed by services.copy.leaderboard.

Component columns on WalletScore:
- persistence_score   0-100: active days / window days
- win_rate_score      0-100: win rate over closed positions (None if none closed)
- hold_pattern_score  0-100: avg first-buy -> first-sell hold time, saturating
                      at HOLD_SATURATION_MINUTES (None if no closed positions).
                      Stored for analysis; NOT part of total_score in v1.
- insider_penalty     points deducted from total_score by the cluster penalty
- total_score/grade   exactly what the live leaderboard shows

Called from tasks.score_wallets on the Celery beat schedule. Uses the 30d
window because the Wallet columns are 30d-denominated (win_rate_30d,
trade_count_30d, pnl_30d).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from models.wallet import Wallet, WalletActivity, WalletScore
from services.copy.leaderboard import (
    WINDOW_HOURS,
    compute_leaderboard,
    compute_sustainability,
)

logger = logging.getLogger(__name__)

# Avg hold time at which hold_pattern_score saturates to 100. Sub-minute
# holds (snipers/bots) score near 0.
HOLD_SATURATION_MINUTES = 60.0

# Extra net-SOL windows persisted onto Wallet.pnl_60d / pnl_90d.
PNL_WINDOWS_HOURS = {"pnl_60d": 1440, "pnl_90d": 2160}


def _as_utc(ts: Optional[datetime]) -> Optional[datetime]:
    if ts is not None and ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def compute_avg_hold_minutes(
    db: Session, wallets: List[str], cutoff: datetime
) -> Dict[str, float]:
    """
    Mean (first buy -> first sell) duration per wallet over in-window tokens
    where a round trip exists. Wallets with no closed positions are absent.
    """
    if not wallets:
        return {}
    rows = (
        db.query(
            WalletActivity.wallet_address,
            WalletActivity.token_address,
            func.min(
                case((WalletActivity.activity_type == "buy", WalletActivity.timestamp))
            ).label("first_buy"),
            func.min(
                case((WalletActivity.activity_type == "sell", WalletActivity.timestamp))
            ).label("first_sell"),
        )
        .filter(
            WalletActivity.wallet_address.in_(wallets),
            WalletActivity.timestamp >= cutoff,
        )
        .group_by(WalletActivity.wallet_address, WalletActivity.token_address)
        .all()
    )
    holds: Dict[str, List[float]] = {}
    for wallet, _token, first_buy, first_sell in rows:
        first_buy, first_sell = _as_utc(first_buy), _as_utc(first_sell)
        if first_buy is None or first_sell is None or first_sell <= first_buy:
            continue
        holds.setdefault(wallet, []).append(
            (first_sell - first_buy).total_seconds() / 60.0
        )
    return {w: sum(v) / len(v) for w, v in holds.items()}


def hold_pattern_score(avg_hold_minutes: Optional[float]) -> Optional[float]:
    if avg_hold_minutes is None:
        return None
    return round(min(avg_hold_minutes / HOLD_SATURATION_MINUTES, 1.0) * 100.0, 1)


def _net_sol_by_wallet(
    db: Session, wallets: List[str], cutoff: datetime
) -> Dict[str, float]:
    if not wallets:
        return {}
    rows = (
        db.query(
            WalletActivity.wallet_address,
            (
                func.coalesce(
                    func.sum(
                        case(
                            (WalletActivity.activity_type == "sell", WalletActivity.sol_amount),
                            else_=0.0,
                        )
                    ),
                    0.0,
                )
                - func.coalesce(
                    func.sum(
                        case(
                            (WalletActivity.activity_type == "buy", WalletActivity.sol_amount),
                            else_=0.0,
                        )
                    ),
                    0.0,
                )
            ).label("net_sol"),
        )
        .filter(
            WalletActivity.wallet_address.in_(wallets),
            WalletActivity.timestamp >= cutoff,
        )
        .group_by(WalletActivity.wallet_address)
        .all()
    )
    return {wallet: float(net or 0.0) for wallet, net in rows}


def _first_seen_by_wallet(db: Session, wallets: List[str]) -> Dict[str, datetime]:
    if not wallets:
        return {}
    rows = (
        db.query(WalletActivity.wallet_address, func.min(WalletActivity.timestamp))
        .filter(WalletActivity.wallet_address.in_(wallets))
        .group_by(WalletActivity.wallet_address)
        .all()
    )
    return {wallet: _as_utc(ts) for wallet, ts in rows if ts is not None}


def score_and_persist_wallets(
    db: Session,
    window: str = "30d",
    min_trades: int = 3,
    max_wallets: int = 200,
) -> Dict[str, Any]:
    """
    Materialize leaderboard stats for the top `max_wallets` qualifying wallets:
    upsert Wallet aggregates and append one WalletScore snapshot per wallet.

    Caller owns the transaction (commit/rollback), matching the tasks.py
    session convention.
    """
    now = datetime.now(timezone.utc)
    window_hours = WINDOW_HOURS[window]
    window_days = window_hours / 24.0
    cutoff = now - timedelta(hours=window_hours)

    entries = compute_leaderboard(
        db, window=window, limit=max_wallets, offset=0, min_trades=min_trades
    )["entries"]
    addresses = [e["wallet_address"] for e in entries]

    avg_holds = compute_avg_hold_minutes(db, addresses, cutoff)
    first_seen = _first_seen_by_wallet(db, addresses)
    pnl_extra = {
        field: _net_sol_by_wallet(db, addresses, now - timedelta(hours=hours))
        for field, hours in PNL_WINDOWS_HOURS.items()
    }

    existing = {
        w.address: w
        for w in db.query(Wallet).filter(Wallet.address.in_(addresses)).all()
    }

    for entry in entries:
        addr = entry["wallet_address"]
        avg_hold = avg_holds.get(addr)
        last_active = (
            datetime.fromisoformat(entry["last_active"]) if entry["last_active"] else None
        )

        wallet = existing.get(addr)
        if wallet is None:
            wallet = Wallet(address=addr)
            db.add(wallet)
            existing[addr] = wallet
        wallet.pnl_30d = entry["net_sol"]
        wallet.pnl_60d = pnl_extra["pnl_60d"].get(addr)
        wallet.pnl_90d = pnl_extra["pnl_90d"].get(addr)
        wallet.win_rate_30d = entry["win_rate"]
        wallet.trade_count_30d = entry["total_trades"]
        wallet.avg_hold_minutes = avg_hold
        wallet.sustainability_score = entry["sustainability_score"]
        wallet.sustainability_grade = entry["sustainability_grade"]
        wallet.first_seen = first_seen.get(addr)
        wallet.last_active = last_active

        # Penalty in points = score without the cluster multiplier minus the
        # actual score (0 for unclustered wallets).
        unpenalized = compute_sustainability(
            win_rate=entry["win_rate"],
            active_days=entry["active_days"],
            window_days=window_days,
            net_sol=entry["net_sol"],
            is_clustered=False,
        )
        db.add(
            WalletScore(
                wallet_address=addr,
                scored_at=now,
                persistence_score=round(
                    min(entry["active_days"] / window_days, 1.0) * 100.0, 1
                ),
                win_rate_score=(
                    round(entry["win_rate"] * 100.0, 1)
                    if entry["win_rate"] is not None
                    else None
                ),
                hold_pattern_score=hold_pattern_score(avg_hold),
                insider_penalty=round(unpenalized - entry["sustainability_score"], 1),
                total_score=entry["sustainability_score"],
                grade=entry["sustainability_grade"],
                details={
                    "window": window,
                    "net_sol": entry["net_sol"],
                    "sol_in": entry["sol_in"],
                    "sol_out": entry["sol_out"],
                    "total_trades": entry["total_trades"],
                    "tokens_traded": entry["tokens_traded"],
                    "closed_positions": entry["closed_positions"],
                    "wins": entry["wins"],
                    "active_days": entry["active_days"],
                    "avg_hold_minutes": round(avg_hold, 1) if avg_hold is not None else None,
                    "is_clustered": entry["is_clustered"],
                },
            )
        )

    db.flush()
    logger.info(
        "score_wallets: persisted %d wallets (window=%s min_trades=%d)",
        len(entries), window, min_trades,
    )
    return {"wallets_scored": len(entries), "window": window}
