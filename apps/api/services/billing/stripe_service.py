"""
Stripe billing (M2, v1): checkout, customer portal, and webhook-driven
tier sync.

Tier model: "free" (default) and "pro" (Stripe subscription on
STRIPE_PRICE_PRO_MONTHLY / STRIPE_PRICE_PRO_YEARLY). User.subscription_tier
is the single source of truth the rest of the app reads (feed delay,
follow limits, WS gating); this module is the only writer.

Configuration is optional by design: with no STRIPE_SECRET_KEY the billing
routes answer 503 and everyone stays on the free tier — the app never
breaks because billing isn't set up yet.

Webhook handlers accept plain event dicts (event["type"],
event["data"]["object"]) so tests can drive the full lifecycle without the
Stripe SDK; signature verification happens at the route boundary via
verify_webhook().
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from sqlalchemy.orm import Session

from core.config import settings
from models.user import Subscription, User

logger = logging.getLogger(__name__)

PRICE_BY_CYCLE = {
    "monthly": lambda: settings.STRIPE_PRICE_PRO_MONTHLY,
    "yearly": lambda: settings.STRIPE_PRICE_PRO_YEARLY,
}

# Stripe subscription statuses that grant the paid tier.
ACTIVE_STATUSES = {"active", "trialing", "past_due"}


def is_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _api_key() -> str:
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY missing)")
    return settings.STRIPE_SECRET_KEY


def _ensure_customer(db: Session, user: User) -> str:
    """Return the user's Stripe customer id, creating the customer once."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe.Customer.create(
        api_key=_api_key(),
        email=user.email,
        metadata={"user_id": user.id},
    )
    user.stripe_customer_id = customer["id"]
    db.commit()
    return user.stripe_customer_id


def create_checkout_session(db: Session, user: User, billing_cycle: str) -> str:
    """Create a subscription checkout session; returns the redirect URL."""
    price_id = PRICE_BY_CYCLE[billing_cycle]()
    if not price_id:
        raise RuntimeError(f"No Stripe price configured for {billing_cycle} billing")
    customer_id = _ensure_customer(db, user)
    session = stripe.checkout.Session.create(
        api_key=_api_key(),
        mode="subscription",
        customer=customer_id,
        client_reference_id=user.id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/settings?billing=success",
        cancel_url=f"{settings.FRONTEND_URL}/settings?billing=cancelled",
        metadata={"user_id": user.id, "billing_cycle": billing_cycle},
    )
    return session["url"]


def create_portal_session(user: User) -> str:
    """Customer-portal URL for managing/cancelling the subscription."""
    if not user.stripe_customer_id:
        raise RuntimeError("User has no Stripe customer yet")
    session = stripe.billing_portal.Session.create(
        api_key=_api_key(),
        customer=user.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/settings",
    )
    return session["url"]


def verify_webhook(payload: bytes, signature_header: str) -> Dict[str, Any]:
    """Verify the Stripe-Signature header and parse the event."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured")
    return stripe.Webhook.construct_event(
        payload, signature_header, settings.STRIPE_WEBHOOK_SECRET
    )


def _ts(epoch: Optional[Any]) -> Optional[datetime]:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _find_user(db: Session, obj: Dict[str, Any]) -> Optional[User]:
    """Resolve the User a webhook object belongs to."""
    user_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user
    customer_id = obj.get("customer")
    if customer_id:
        return db.query(User).filter(User.stripe_customer_id == customer_id).first()
    return None


def _upsert_subscription_row(
    db: Session, user: User, obj: Dict[str, Any], tier: str, status: str
) -> None:
    stripe_sub_id = obj.get("id") if obj.get("object") == "subscription" else obj.get("subscription")
    row = None
    if stripe_sub_id:
        row = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub_id)
            .first()
        )
    if row is None:
        row = Subscription(
            user_id=user.id,
            stripe_subscription_id=stripe_sub_id,
            tier=tier,
            billing_cycle=(obj.get("metadata") or {}).get("billing_cycle", "monthly"),
            status=status,
        )
        db.add(row)
    row.tier = tier
    row.status = status
    # Period fields live top-level on classic API versions and on the first
    # subscription item on newer ones — read whichever is present.
    items = ((obj.get("items") or {}).get("data") or [{}])[0]
    row.current_period_start = _ts(
        obj.get("current_period_start") or items.get("current_period_start")
    )
    row.current_period_end = _ts(
        obj.get("current_period_end") or items.get("current_period_end")
    )
    row.cancel_at_period_end = bool(obj.get("cancel_at_period_end", False))
    if status == "canceled":
        row.canceled_at = _ts(obj.get("canceled_at")) or datetime.now(timezone.utc)
    price = (items.get("price") or {}) if isinstance(items, dict) else {}
    if price.get("id"):
        row.stripe_price_id = price["id"]


def handle_webhook_event(db: Session, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a verified Stripe event. Unknown event types are acknowledged and
    ignored — Stripe retries on non-2xx, so "not relevant" must not error.
    """
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    user = _find_user(db, obj)
    if user is None:
        logger.warning("stripe webhook %s: no matching user; ignoring", event_type)
        return {"handled": False, "reason": "no matching user"}

    if event_type == "checkout.session.completed":
        if obj.get("customer") and not user.stripe_customer_id:
            user.stripe_customer_id = obj["customer"]
        user.subscription_tier = "pro"
        user.subscription_starts_at = datetime.now(timezone.utc)
        _upsert_subscription_row(db, user, obj, tier="pro", status="active")

    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        status = obj.get("status", "active")
        tier = "pro" if status in ACTIVE_STATUSES else "free"
        user.subscription_tier = tier
        user.subscription_ends_at = (
            _ts(obj.get("current_period_end")) if obj.get("cancel_at_period_end") else None
        )
        _upsert_subscription_row(db, user, obj, tier="pro", status=status)

    elif event_type == "customer.subscription.deleted":
        user.subscription_tier = "free"
        user.subscription_ends_at = datetime.now(timezone.utc)
        _upsert_subscription_row(db, user, obj, tier="pro", status="canceled")

    else:
        return {"handled": False, "reason": f"ignored event type {event_type}"}

    db.commit()
    logger.info(
        "stripe webhook %s: user %s -> tier %s",
        event_type, user.id, user.subscription_tier,
    )
    return {"handled": True, "user_id": user.id, "tier": user.subscription_tier}
