"""
Execution REST endpoints (M3, v1 — read-only foundation).

GET /api/v1/execute/price  — cached SOL/USD price for the UI
GET /api/v1/execute/quote  — Jupiter swap quote (SOL input, v1)

Swap transaction building + submission lands with the wallet-connect
increment; nothing here moves funds.
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from services.execution import price_feed
from services.execution.jupiter import JupiterUnavailable, get_quote

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/execute")

LAMPORTS_PER_SOL = 1_000_000_000


@router.get("/price")
def sol_price():
    """Cached SOL/USD. 503 when no source is reachable (UI shows a dash)."""
    price = price_feed.get_sol_price_usd()
    if price is None:
        raise HTTPException(status_code=503, detail="Price feed unavailable")
    return {"sol_usd": price}


@router.get("/quote")
def swap_quote(
    output_mint: str = Query(..., min_length=32, max_length=64),
    amount_sol: float = Query(..., gt=0, le=10_000),
    slippage_bps: int = Query(100, ge=1, le=5_000),
):
    """
    Quote a SOL -> token swap. v1 fixes the input side to SOL, which covers
    the terminal's buy flow; sells come with the wallet increment.
    """
    try:
        quote = get_quote(
            input_mint=price_feed.SOL_MINT,
            output_mint=output_mint,
            amount_raw=int(amount_sol * LAMPORTS_PER_SOL),
            slippage_bps=slippage_bps,
        )
    except JupiterUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Trimmed passthrough: enough for a swap ticket without leaking the
    # full route plan payload.
    return {
        "input_mint": price_feed.SOL_MINT,
        "output_mint": output_mint,
        "in_amount": quote.get("inAmount"),
        "out_amount": quote.get("outAmount"),
        "other_amount_threshold": quote.get("otherAmountThreshold"),
        "price_impact_pct": quote.get("priceImpactPct"),
        "slippage_bps": quote.get("slippageBps", slippage_bps),
        "route_labels": [
            step.get("swapInfo", {}).get("label")
            for step in quote.get("routePlan", [])
            if isinstance(step, dict)
        ],
    }
