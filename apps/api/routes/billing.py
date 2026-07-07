"""
Billing REST endpoints (M2).

POST /api/v1/billing/checkout   — start a Pro subscription (returns Stripe URL)
POST /api/v1/billing/portal     — manage/cancel via Stripe customer portal
GET  /api/v1/billing/status     — caller's tier + subscription record
POST /api/v1/webhooks/stripe    — Stripe events (signature-verified)

All except the webhook require a Bearer token. When Stripe isn't
configured (no STRIPE_SECRET_KEY) checkout/portal answer 503 and the app
runs free-tier-only.
"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import Subscription, User
from routes.auth import get_current_user
from services.billing import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class CheckoutRequest(BaseModel):
    billing_cycle: Literal["monthly", "yearly"] = "monthly"


class RedirectResponse(BaseModel):
    url: str


@router.post("/billing/checkout", response_model=RedirectResponse)
def create_checkout(
    body: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    if not stripe_service.is_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured")
    if current_user.subscription_tier != "free":
        raise HTTPException(status_code=409, detail="Already subscribed")
    try:
        url = stripe_service.create_checkout_session(db, current_user, body.billing_cycle)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return RedirectResponse(url=url)


@router.post("/billing/portal", response_model=RedirectResponse)
def create_portal(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    if not stripe_service.is_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured")
    try:
        url = stripe_service.create_portal_session(current_user)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=url)


@router.get("/billing/status")
def billing_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    return {
        "tier": current_user.subscription_tier,
        "billing_configured": stripe_service.is_configured(),
        "has_stripe_customer": bool(current_user.stripe_customer_id),
        "subscription": None
        if subscription is None
        else {
            "status": subscription.status,
            "billing_cycle": subscription.billing_cycle,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
        },
    }


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    if stripe_signature is None:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
    payload = await request.body()
    try:
        event = stripe_service.verify_webhook(payload, stripe_signature)
    except RuntimeError as exc:
        # Webhook secret not configured — surface as service unavailable.
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    result = stripe_service.handle_webhook_event(db, event)
    return {"received": True, **result}
