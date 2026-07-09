"""
Execution REST endpoints (M3 — non-custodial).

GET  /api/v1/execute/price             — cached SOL/USD price for the UI
GET  /api/v1/execute/quote             — Jupiter swap quote (SOL input, v1)
POST /api/v1/execute/swap-transaction  — build unsigned swap tx (signed client-side)
POST /api/v1/execute/trades            — record a user-signed manual swap (auth)
GET  /api/v1/execute/trades            — the caller's manual trades (auth)
GET  /api/v1/execute/positions         — per-token holdings + PnL (auth)

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
from models.token import TokenSignal
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
    # Quoted token quantity (received on buys, spent on sells). Optional so
    # older clients keep working; positions need it for quantity math.
    token_amount: Optional[float] = Field(None, gt=0)
    signature: str = Field(min_length=32, max_length=128)
    slippage_bps: Optional[int] = Field(None, ge=1, le=5_000)


class ManualTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    token_address: str
    trade_type: str
    source: str
    sol_amount: Optional[float] = None
    token_amount: Optional[float] = None
    usd_value: Optional[float] = None
    slippage_pct: Optional[float] = None
    signature: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    rug_risk_at_trade: Optional[float] = None
    momentum_at_trade: Optional[float] = None
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
    # Risk context at the moment of the trade (ROADMAP M3): the latest
    # scored signal for this mint, if discovery has seen it.
    latest_signal = (
        db.query(TokenSignal.rug_risk_score, TokenSignal.momentum_score)
        .filter(TokenSignal.token_address == body.token_address)
        .order_by(TokenSignal.scan_timestamp.desc())
        .first()
    )
    trade = ExecutedTrade(
        user_id=current_user.id,
        token_address=body.token_address,
        trade_type=body.trade_type,
        source="manual",
        sol_amount=body.sol_amount,
        token_amount=body.token_amount,
        usd_value=round(body.sol_amount * sol_price, 2) if sol_price else None,
        price_at_trade=sol_price,
        slippage_pct=(body.slippage_bps / 100.0) if body.slippage_bps else None,
        signature=body.signature,
        status="submitted",
        rug_risk_at_trade=latest_signal.rug_risk_score if latest_signal else None,
        momentum_at_trade=latest_signal.momentum_score if latest_signal else None,
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


class Position(BaseModel):
    token_address: str
    trade_count: int
    last_trade_at: Optional[datetime] = None
    bought_sol: float
    sold_sol: float
    net_tokens: Optional[float] = None
    cost_basis_sol: Optional[float] = None
    realized_pnl_sol: Optional[float] = None
    token_price_usd: Optional[float] = None
    value_sol: Optional[float] = None
    unrealized_pnl_sol: Optional[float] = None


class PositionsResponse(BaseModel):
    positions: List[Position]
    count: int
    sol_usd: Optional[float] = None


@router.get("/positions", response_model=PositionsResponse)
def list_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PositionsResponse:
    """
    Per-token holdings + PnL from the caller's real trades (submitted or
    confirmed). Quantities/PnL are None wherever the inputs aren't knowable
    (legacy rows without token_amount, price feed down) — the UI shows a
    dash instead of a guess.
    """
    from services.execution.positions import compute_positions

    rows = compute_positions(db, current_user.id)

    sol_usd = price_feed.get_sol_price_usd()
    open_mints = [
        r["token_address"] for r in rows
        if r["net_tokens"] is not None and r["net_tokens"] > 0
    ]
    token_prices = price_feed.get_token_prices_usd(open_mints) if open_mints else {}

    positions = []
    for r in rows:
        price_usd = token_prices.get(r["token_address"])
        value_sol = unrealized = None
        if (
            price_usd is not None
            and sol_usd
            and r["net_tokens"] is not None
            and r["net_tokens"] > 0
        ):
            value_sol = r["net_tokens"] * price_usd / sol_usd
            if r["cost_basis_sol"] is not None:
                unrealized = value_sol - r["cost_basis_sol"]
        positions.append(
            Position(
                **r,
                token_price_usd=price_usd,
                value_sol=value_sol,
                unrealized_pnl_sol=unrealized,
            )
        )
    return PositionsResponse(positions=positions, count=len(positions), sol_usd=sol_usd)
