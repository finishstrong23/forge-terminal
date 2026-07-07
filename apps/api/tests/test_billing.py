"""Billing endpoints + Stripe webhook tier sync (SDK stubbed)."""
import pytest


@pytest.fixture()
def user_client(client, db):
    r = client.post("/api/v1/auth/register",
                    json={"email": "payer@example.com", "password": "password123"})
    assert r.status_code == 201
    body = r.json()
    return client, {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def _subscription_obj(sub_id="sub_123", customer="cus_123", status="active", **extra):
    return {
        "object": "subscription",
        "id": sub_id,
        "customer": customer,
        "status": status,
        "cancel_at_period_end": False,
        "current_period_start": 1_700_000_000,
        "current_period_end": 1_702_600_000,
        "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
        **extra,
    }


def test_unconfigured_billing_answers_503_and_status_reports_it(user_client):
    client, auth, _ = user_client
    assert client.post("/api/v1/billing/checkout", json={}, headers=auth).status_code == 503
    assert client.post("/api/v1/billing/portal", headers=auth).status_code == 503

    r = client.get("/api/v1/billing/status", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free" and body["billing_configured"] is False
    assert body["subscription"] is None


def test_billing_endpoints_require_auth(client, db):
    assert client.get("/api/v1/billing/status").status_code == 401
    assert client.post("/api/v1/billing/checkout", json={}).status_code == 401


def test_webhook_requires_signature_header(client, db):
    r = client.post("/api/v1/webhooks/stripe", content=b"{}")
    assert r.status_code == 400


def test_webhook_lifecycle_syncs_tier(user_client, db, monkeypatch):
    """checkout.completed -> pro; subscription.updated keeps/downgrades;
    subscription.deleted -> free. Signature verification stubbed."""
    from models.user import Subscription, User
    from routes import billing as billing_routes
    from services.billing import stripe_service

    client, auth, user_id = user_client
    events = {}

    def fake_verify(payload, signature):
        return events["current"]

    monkeypatch.setattr(billing_routes.stripe_service, "verify_webhook", fake_verify)

    def post_event(event):
        events["current"] = event
        return client.post("/api/v1/webhooks/stripe", content=b"{}",
                           headers={"Stripe-Signature": "t=stub"})

    # 1. Checkout completes -> pro.
    r = post_event({
        "type": "checkout.session.completed",
        "data": {"object": {
            "object": "checkout.session",
            "client_reference_id": user_id,
            "customer": "cus_123",
            "subscription": "sub_123",
            "metadata": {"user_id": user_id, "billing_cycle": "monthly"},
        }},
    })
    assert r.status_code == 200 and r.json()["tier"] == "pro"
    user = db.query(User).filter(User.id == user_id).first()
    db.refresh(user)
    assert user.subscription_tier == "pro" and user.stripe_customer_id == "cus_123"
    sub_row = db.query(Subscription).filter(Subscription.user_id == user_id).one()
    assert sub_row.stripe_subscription_id == "sub_123" and sub_row.status == "active"

    # 2. Subscription update with active status stays pro; period fields land.
    r = post_event({
        "type": "customer.subscription.updated",
        "data": {"object": _subscription_obj()},
    })
    assert r.json()["tier"] == "pro"
    db.refresh(sub_row)
    assert sub_row.current_period_end is not None
    assert sub_row.stripe_price_id == "price_pro_monthly"

    # 3. Update to unpaid downgrades.
    r = post_event({
        "type": "customer.subscription.updated",
        "data": {"object": _subscription_obj(status="unpaid")},
    })
    assert r.json()["tier"] == "free"

    # 4. Re-activation upgrades again, then deletion downgrades for good.
    post_event({
        "type": "customer.subscription.updated",
        "data": {"object": _subscription_obj(status="active")},
    })
    r = post_event({
        "type": "customer.subscription.deleted",
        "data": {"object": _subscription_obj(status="canceled")},
    })
    assert r.json()["tier"] == "free"
    db.refresh(user)
    db.refresh(sub_row)
    assert user.subscription_tier == "free"
    assert sub_row.status == "canceled" and sub_row.canceled_at is not None

    # 5. Irrelevant/unknown events are acknowledged, not errors.
    r = post_event({"type": "invoice.finalized",
                    "data": {"object": {"customer": "cus_123"}}})
    assert r.status_code == 200 and r.json()["handled"] is False

    # 6. Status endpoint reflects the final state.
    status = client.get("/api/v1/billing/status", headers=auth).json()
    assert status["tier"] == "free"
    assert status["subscription"]["status"] == "canceled"


def test_webhook_with_no_matching_user_is_acknowledged(client, db, monkeypatch):
    from routes import billing as billing_routes

    monkeypatch.setattr(
        billing_routes.stripe_service, "verify_webhook",
        lambda p, s: {"type": "customer.subscription.updated",
                      "data": {"object": {"customer": "cus_ghost"}}},
    )
    r = client.post("/api/v1/webhooks/stripe", content=b"{}",
                    headers={"Stripe-Signature": "t=stub"})
    assert r.status_code == 200 and r.json()["handled"] is False
