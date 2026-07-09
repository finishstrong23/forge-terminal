"""
Portfolio positions (M3e) — aggregate ExecutedTrade into per-token holdings.

Only real on-chain trades count: status "submitted" (optimistic — the
confirmation checker resolves it within minutes) or "confirmed". Shadow
ledger rows (source="copy_shadow", status simulated/skipped) and
failed/expired trades never reach a position.

Quantities are average-cost accounted, and only when they're knowable:
token_amount is client-reported from the quote, so legacy rows may lack
it. Any missing token_amount on a side makes the derived numbers for that
token None rather than silently wrong — the UI shows a dash.

PnL is denominated in SOL (the currency the user actually spent), with
USD conversion left to the caller via the SOL price feed.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.trade import ExecutedTrade

POSITION_STATUSES = ("submitted", "confirmed")

# Ignore residual token dust below this many tokens when deciding whether
# a position is still open (float error from partial sells).
DUST_TOKENS = 1e-9


def compute_positions(db: Session, user_id: str) -> list[dict]:
    """Per-token aggregates for a user's real trades, newest activity first."""
    trades = (
        db.query(ExecutedTrade)
        .filter(
            ExecutedTrade.user_id == user_id,
            ExecutedTrade.status.in_(POSITION_STATUSES),
        )
        .order_by(ExecutedTrade.created_at.asc())
        .all()
    )

    by_token: dict[str, list[ExecutedTrade]] = {}
    for trade in trades:
        by_token.setdefault(trade.token_address, []).append(trade)

    positions = []
    for token, rows in by_token.items():
        bought_sol = sum(t.sol_amount or 0.0 for t in rows if t.trade_type == "buy")
        sold_sol = sum(t.sol_amount or 0.0 for t in rows if t.trade_type == "sell")

        buys = [t for t in rows if t.trade_type == "buy"]
        sells = [t for t in rows if t.trade_type == "sell"]
        buys_known = all(t.token_amount is not None for t in buys)
        sells_known = all(t.token_amount is not None for t in sells)

        bought_tokens = (
            sum(t.token_amount for t in buys) if buys and buys_known else None
        )
        sold_tokens = (
            sum(t.token_amount for t in sells) if sells_known else (None if sells else 0.0)
        )

        net_tokens: Optional[float] = None
        cost_basis_sol: Optional[float] = None
        realized_pnl_sol: Optional[float] = None
        if bought_tokens and bought_tokens > 0 and sold_tokens is not None:
            avg_cost = bought_sol / bought_tokens
            net_tokens = max(0.0, bought_tokens - sold_tokens)
            if net_tokens < DUST_TOKENS:
                net_tokens = 0.0
            cost_basis_sol = net_tokens * avg_cost
            realized_pnl_sol = sold_sol - sold_tokens * avg_cost

        # created_at is NOT NULL, so every row yields a timestamp.
        last_at: datetime = max(t.executed_at or t.created_at for t in rows)
        positions.append(
            {
                "token_address": token,
                "trade_count": len(rows),
                "last_trade_at": last_at,
                "bought_sol": round(bought_sol, 9),
                "sold_sol": round(sold_sol, 9),
                "net_tokens": net_tokens,
                "cost_basis_sol": cost_basis_sol,
                "realized_pnl_sol": realized_pnl_sol,
            }
        )

    positions.sort(
        key=lambda p: (p["last_trade_at"] is not None, p["last_trade_at"]),
        reverse=True,
    )
    return positions
