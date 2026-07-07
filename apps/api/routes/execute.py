"""
Execution REST endpoints (M3 — non-custodial).

GET  /api/v1/execute/price             — cached SOL/USD price for the UI
GET  /api/v1/execute/quote             — Jupiter swap quote (SOL input, v1)
POST /api/v1/execute/swap-transaction  — build unsigned swap tx (signed client-side)
POST /api/v1/execute/trades            — record a user-signed manual swap (auth)
GET  /api/v1/execute/trades            — the caller's manual trades (auth)

The server never holds keys and never submits transactions: it quotes and
builds; the user's wallet signs and sends. Recording is client-reported
v1 — a confirmation-checker beat task is future work (see ROADMAP M3).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.trade import ExecutedTrade
from models.user import User
from routes.auth import get_current_user
from services.execution import price_feed
from services.execution.jupiter import (
    JupiterUnavailable,
    get_quote,
    get_swap_transaction,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/execute")

LAMPORTS_PER_SOL = 1_000_000_000


@router.get("/token-meta")
def token_meta(mint: str = Query(..., min_length=32, max_length=64)):
    """Mint decimals for the swap ticket. decimals=null -> UI falls back to
    the documented 6-decimals assumption with its caveat."""
    from services.execution.token_meta import get_token_decimals

    return {"mint": mint, "decimals": get_token_decimals(mint)}


@router.get("/price")
def sol_price():
    """Cached SOL/USD. 503 when no source is reachable (UI shows a dash)."""
    price = price_feed.get_sol_price_usd()
    if price is None:
        raise HTTPException(status_code=503, detail="Price feed unavailable")
    return {"sol_usd": price}


@router.get("/quote")
def swap_quote(
    token_mint: str = Query(..., min_length=32, max_length=64,
                            description="The non-SOL side of the swap."),
    side: Literal["buy", "sell"] = Query(
        "buy", description="buy = SOL -> token, sell = token -> SOL."
    ),
    amount_sol: Optional[float] = Query(None, gt=0, le=10_000,
                                        description="Input SOL (buy side)."),
    amount_tokens: Optional[float] = Query(None, gt=0,
                                           description="Input tokens (sell side)."),
    token_decimals: int = Query(6, ge=0, le=12,
                                description="Token decimals for sell-amount conversion."),
    slippage_bps: int = Query(100, ge=1, le=5_000),
    include_raw: bool = Query(
        False, description="Include Jupiter's full quote for /swap-transaction."
    ),
):
    """Quote a swap between SOL and a token, either direction."""
    if side == "buy":
        if amount_sol is None:
            raise HTTPException(status_code=422, detail="amount_sol is required for buys")
        input_mint, output_mint = price_feed.SOL_MINT, token_mint
        amount_raw = int(amount_sol * LAMPORTS_PER_SOL)
    else:
        if amount_tokens is None:
            raise HTTPException(status_code=422, detail="amount_tokens is required for sells")
        input_mint, output_mint = token_mint, price_feed.SOL_MINT
        amount_raw = int(amount_tokens * (10 ** token_decimals))

    try:
        quote = get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=slippage_bps,
        )
    except JupiterUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Trimmed passthrough: enough for a swap ticket without leaking the
    # full route plan payload.
    result = {
        "input_mint": input_mint,
        "output_mint": output_mint,
        "side": side,
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
    if include_raw:
        # The /swap-transaction call needs Jupiter's untrimmed payload.
        result["quote_response"] = quote
    return result


class SwapTransactionRequest(BaseModel):
    quote_response: Dict[str, Any]
    user_public_key: str = Field(min_length=32, max_length=64)
    priority_fee_lamports: int = Field(0, ge=0, le=10_000_000)


@router.post("/swap-transaction")
def build_swap_transaction(body: SwapTransactionRequest):
    """
    Build the unsigned swap transaction for a previously fetched quote
    (GET /quote?include_raw=true). Signing happens in the user's wallet;
    the server never sees keys.
    """
    try:
        payload = get_swap_transaction(
            quote_response=body.quote_response,
            user_public_key=body.user_public_key,
            priority_fee_lamports=body.priority_fee_lamports,
        )
    except JupiterUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "swap_transaction": payload["swapTransaction"],
        "last_valid_block_height": payload.get("lastValidBlockHeight"),
    }


class ManualTradeCreate(BaseModel):
    token_address: str = Field(min_length=1)
    trade_type: Literal["buy", "sell"] = "buy"
    sol_amount: float = Field(gt=0)
    signature: str = Field(min_length=32, max_length=128)
    slippage_bps: Optional[int] = Field(None, ge=1, le=5_000)


class ManualTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    token_address: str
    trade_type: str
    source: str
    sol_amount: Optional[float] = None
    usd_value: Optional[float] = None
    slippage_pct: Optional[float] = None
    signature: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: datetime


class ManualTradeListResponse(BaseModel):
    trades: List[ManualTradeResponse]
    count: int


@router.post("/trades", response_model=ManualTradeResponse, status_code=201)
def record_manual_trade(
    body: ManualTradeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ManualTradeResponse:
    """
    Record a swap the user just signed and sent. Client-reported v1:
    status stays "submitted" until a confirmation checker exists, and the
    unique signature column dedupes double-reports (409).
    """
    existing = (
        db.query(ExecutedTrade.id)
        .filter(ExecutedTrade.signature == body.signature)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Trade already recorded")

    sol_price = price_feed.get_sol_price_usd()
    trade = ExecutedTrade(
        user_id=current_user.id,
        token_address=body.token_address,
        trade_type=body.trade_type,
        source="manual",
        sol_amount=body.sol_amount,
        usd_value=round(body.sol_amount * sol_price, 2) if sol_price else None,
        slippage_pct=(body.slippage_bps / 100.0) if body.slippage_bps else None,
        signature=body.signature,
        status="submitted",
        executed_at=datetime.now(timezone.utc),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    logger.info("execute/trades: user %s recorded %s %s SOL on %s",
                current_user.id, body.trade_type, body.sol_amount, body.token_address)
    return ManualTradeResponse.model_validate(trade)


@router.get("/trades", response_model=ManualTradeListResponse)
def list_manual_trades(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ManualTradeListResponse:
    trades = (
        db.query(ExecutedTrade)
        .filter(
            ExecutedTrade.user_id == current_user.id,
            ExecutedTrade.source == "manual",
        )
        .order_by(ExecutedTrade.created_at.desc())
        .limit(limit)
        .all()
    )
    return ManualTradeListResponse(
        trades=[ManualTradeResponse.model_validate(t) for t in trades],
        count=len(trades),
    )
