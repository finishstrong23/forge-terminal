"""
Copy-subscription REST endpoints (Phase 2 — shadow mode only).

POST  /api/v1/copy/subscriptions        — follow a wallet (shadow mode)
GET   /api/v1/copy/subscriptions        — list the caller's subscriptions
PATCH /api/v1/copy/subscriptions/{id}   — pause / resume / stop
GET   /api/v1/copy/trades               — the caller's shadow-trade ledger

All routes require a Bearer token (routes.auth.get_current_user). Shadow
mode records what copy-execution WOULD do (services/copy/shadow_recorder.py
on the beat schedule); actual Jupiter-routed execution is the Phase 3
layer, at which point mode="live" unlocks.

Status state machine:
    active --pause--> paused --resume--> active
    active/paused --stop--> stopped (terminal)
"""
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from models.trade import CopySubscription, ExecutedTrade
from models.user import User
from models.wallet import WalletActivity
from routes.auth import get_current_user
from schemas.copy import (
    CopySubscriptionAction,
    CopySubscriptionCreate,
    CopySubscriptionListResponse,
    CopySubscriptionResponse,
    ShadowTradeListResponse,
    ShadowTradeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/copy")


@router.post("/subscriptions", response_model=CopySubscriptionResponse, status_code=201)
def create_subscription(
    body: CopySubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CopySubscriptionResponse:
    """
    Follow a wallet in shadow mode.

    404 if the wallet has never appeared in the discovery pipeline — there
    would be nothing to shadow. 409 if the caller already has a non-stopped
    subscription for it.
    """
    has_activity = (
        db.query(WalletActivity.id)
        .filter(WalletActivity.wallet_address == body.wallet_address)
        .first()
    )
    if not has_activity:
        raise HTTPException(status_code=404, detail="Wallet has no recorded activity")

    duplicate = (
        db.query(CopySubscription.id)
        .filter(
            CopySubscription.user_id == current_user.id,
            CopySubscription.wallet_address == body.wallet_address,
            CopySubscription.status != "stopped",
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Already subscribed to this wallet"
        )

    sub = CopySubscription(
        user_id=current_user.id,
        wallet_address=body.wallet_address,
        mode=body.mode,
        status="active",
        max_position_usd=body.max_position_usd,
        daily_loss_cap_usd=body.daily_loss_cap_usd,
        slippage_tolerance=body.slippage_tolerance,
        min_sustainability_score=body.min_sustainability_score,
        token_blacklist=body.token_blacklist,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    logger.info(
        "copy/subscriptions: user %s follows %s (%s)",
        current_user.id, body.wallet_address, body.mode,
    )
    return CopySubscriptionResponse.model_validate(sub)


@router.get("/subscriptions", response_model=CopySubscriptionListResponse)
def list_subscriptions(
    status: Optional[Literal["active", "paused", "stopped"]] = Query(
        None, description="Filter by status; omit for all."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CopySubscriptionListResponse:
    query = db.query(CopySubscription).filter(
        CopySubscription.user_id == current_user.id
    )
    if status is not None:
        query = query.filter(CopySubscription.status == status)
    subs = query.order_by(CopySubscription.created_at.desc()).all()
    return CopySubscriptionListResponse(
        subscriptions=[CopySubscriptionResponse.model_validate(s) for s in subs],
        count=len(subs),
    )


@router.patch("/subscriptions/{subscription_id}", response_model=CopySubscriptionResponse)
def update_subscription(
    subscription_id: str,
    body: CopySubscriptionAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CopySubscriptionResponse:
    # Scoped to the caller: someone else's subscription id is a 404, not a
    # 403, so ids can't be probed.
    sub = (
        db.query(CopySubscription)
        .filter(
            CopySubscription.id == subscription_id,
            CopySubscription.user_id == current_user.id,
        )
        .first()
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    now = datetime.now(timezone.utc)
    if sub.status == "stopped":
        raise HTTPException(status_code=409, detail="Subscription already stopped")

    if body.action == "pause":
        if sub.status != "active":
            raise HTTPException(status_code=409, detail="Only active subscriptions can be paused")
        sub.status = "paused"
        sub.paused_at = now
    elif body.action == "resume":
        if sub.status != "paused":
            raise HTTPException(status_code=409, detail="Only paused subscriptions can be resumed")
        sub.status = "active"
        sub.paused_at = None
    else:  # stop
        sub.status = "stopped"
        sub.stopped_at = now

    db.commit()
    db.refresh(sub)
    return CopySubscriptionResponse.model_validate(sub)


@router.get("/trades", response_model=ShadowTradeListResponse)
def list_shadow_trades(
    status: Optional[Literal["simulated", "skipped"]] = Query(
        None, description="Filter by status; omit for all."
    ),
    subscription_id: Optional[str] = Query(
        None, description="Only trades from one subscription."
    ),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShadowTradeListResponse:
    """The caller's shadow-trade ledger, newest first."""
    query = db.query(ExecutedTrade).filter(
        ExecutedTrade.user_id == current_user.id,
        ExecutedTrade.source == "copy_shadow",
    )
    if status is not None:
        query = query.filter(ExecutedTrade.status == status)
    if subscription_id is not None:
        query = query.filter(ExecutedTrade.copy_subscription_id == subscription_id)
    trades = query.order_by(ExecutedTrade.created_at.desc()).limit(limit).all()
    return ShadowTradeListResponse(
        trades=[ShadowTradeResponse.model_validate(t) for t in trades],
        count=len(trades),
    )
