"""
Copy Intelligence — shadow-trade recorder (Phase 2, v1).

For every active shadow-mode CopySubscription, translates the followed
wallet's new WalletActivity rows into ExecutedTrade records with
source="copy_shadow" — a paper-trading ledger of what copy-execution WOULD
have done, so users can evaluate a wallet before Phase 3 live execution
exists.

Each activity produces one ExecutedTrade per subscription, either:
- status="simulated" — the trade would have been copied, or
- status="skipped" + error_message — a risk filter blocked it (token
  blacklist, honeypot flag, wallet sustainability below the subscription's
  threshold). Recording skips makes the filters visible in the ledger.

Filters applied in v1: token_blacklist, honeypot (latest TokenSignal),
min_sustainability_score (persisted Wallet score; not applied until the
wallet has been scored). max_position_usd and daily_loss_cap_usd need a
SOL/USD price source we don't ingest yet — they are stored on the
subscription and enforced at execution time (Phase 3); usd_value stays
NULL on shadow rows for the same reason.

Idempotency: signature = "shadow:{subscription_id}:{event_signature}" is
unique on executed_trades, so the beat task can rescan a lookback window
every run (no high-water-mark state) without duplicating rows.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.token import TokenSignal
from models.trade import CopySubscription, ExecutedTrade
from models.wallet import Wallet, WalletActivity

logger = logging.getLogger(__name__)

# Rescan window per run. Must comfortably exceed the beat cadence (60s) so
# webhook-processing lag can't drop trades into a gap between runs.
LOOKBACK_MINUTES = 15


def _as_utc(ts: Optional[datetime]) -> Optional[datetime]:
    if ts is not None and ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _latest_signal_by_token(db: Session, tokens: List[str]) -> Dict[str, TokenSignal]:
    if not tokens:
        return {}
    rows = (
        db.query(TokenSignal)
        .filter(TokenSignal.token_address.in_(tokens))
        .order_by(TokenSignal.scan_timestamp.desc())
        .all()
    )
    latest: Dict[str, TokenSignal] = {}
    for signal in rows:
        if signal.token_address not in latest:
            latest[signal.token_address] = signal
    return latest


def _skip_reason(
    sub: CopySubscription,
    activity: WalletActivity,
    signal: Optional[TokenSignal],
    wallet_score: Optional[float],
) -> Optional[str]:
    if sub.token_blacklist and activity.token_address in sub.token_blacklist:
        return "token blacklisted by subscription"
    if signal is not None and signal.is_honeypot:
        return "token flagged as honeypot"
    if (
        sub.min_sustainability_score is not None
        and wallet_score is not None
        and wallet_score < sub.min_sustainability_score
    ):
        return (
            f"wallet sustainability {wallet_score:.1f} below "
            f"threshold {sub.min_sustainability_score:.1f}"
        )
    return None


def record_shadow_trades(
    db: Session, lookback_minutes: int = LOOKBACK_MINUTES
) -> Dict[str, Any]:
    """
    Scan recent WalletActivity for followed wallets and append shadow
    ExecutedTrade rows. Caller owns the transaction.
    """
    subs = (
        db.query(CopySubscription)
        .filter(
            CopySubscription.status == "active",
            CopySubscription.mode == "shadow",
        )
        .all()
    )
    if not subs:
        return {"subscriptions": 0, "recorded": 0, "skipped": 0}

    subs_by_wallet: Dict[str, List[CopySubscription]] = {}
    for sub in subs:
        subs_by_wallet.setdefault(sub.wallet_address, []).append(sub)

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    activities = (
        db.query(WalletActivity)
        .filter(
            WalletActivity.wallet_address.in_(list(subs_by_wallet)),
            WalletActivity.activity_type.in_(["buy", "sell"]),
            WalletActivity.timestamp >= cutoff,
        )
        .order_by(WalletActivity.timestamp.asc())
        .all()
    )
    if not activities:
        return {"subscriptions": len(subs), "recorded": 0, "skipped": 0}

    signals = _latest_signal_by_token(db, list({a.token_address for a in activities}))
    scores = {
        w.address: w.sustainability_score
        for w in db.query(Wallet)
        .filter(Wallet.address.in_(list(subs_by_wallet)))
        .all()
    }

    # One IN query resolves which candidate rows already exist.
    candidates = []
    for activity in activities:
        for sub in subs_by_wallet[activity.wallet_address]:
            candidates.append((sub, activity))
    sigs = [
        f"shadow:{sub.id}:{activity.event_signature or activity.id}"
        for sub, activity in candidates
    ]
    existing = {
        row[0]
        for row in db.query(ExecutedTrade.signature)
        .filter(ExecutedTrade.signature.in_(sigs))
        .all()
    }

    recorded = skipped = 0
    for (sub, activity), sig in zip(candidates, sigs):
        if sig in existing:
            continue
        # Don't copy trades that predate the follow.
        activity_ts = _as_utc(activity.timestamp)
        started_at = _as_utc(sub.started_at)
        if started_at is not None and activity_ts is not None and activity_ts < started_at:
            continue

        signal = signals.get(activity.token_address)
        reason = _skip_reason(sub, activity, signal, scores.get(sub.wallet_address))
        db.add(
            ExecutedTrade(
                user_id=sub.user_id,
                token_address=activity.token_address,
                trade_type=activity.activity_type,
                source="copy_shadow",
                sol_amount=activity.sol_amount,
                price_at_trade=signal.price_usd if signal else None,
                signature=sig,
                status="skipped" if reason else "simulated",
                error_message=reason,
                copy_subscription_id=sub.id,
                rug_risk_at_trade=signal.rug_risk_score if signal else None,
                momentum_at_trade=signal.momentum_score if signal else None,
                executed_at=activity_ts,
            )
        )
        if reason:
            skipped += 1
        else:
            recorded += 1

    db.flush()
    if recorded or skipped:
        logger.info(
            "shadow_recorder: recorded=%d skipped=%d over %d subscriptions",
            recorded, skipped, len(subs),
        )
    return {"subscriptions": len(subs), "recorded": recorded, "skipped": skipped}
