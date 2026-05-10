"""
Alert Service
==============

Evaluates token signals against user preferences and dispatches alerts
via WebSocket and/or email.

Tier gating:
- Free: No alerts
- Pro: WebSocket + hourly email digest
- Ultra/Lifetime: WebSocket + instant email + custom filters
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from models.token import TokenSignal
from models.user import User
from models.alert import UserAlertPreference, Alert
from services.discovery.scoring_engine import scorer
from core.config import settings


# Tiers that can receive alerts
ALERT_TIERS = {"pro", "ultra", "lifetime"}


def check_and_broadcast(db: Session, signal: TokenSignal):
    """
    Check if a signal should trigger alerts, and dispatch them.
    Called after scoring in the webhook processing pipeline.
    """
    # Check alert criteria
    should_alert, reason = scorer.should_send_alert(
        signal.rug_risk_score or 100,
        signal.momentum_score or 0,
        signal.confidence_score or 0,
    )

    if not should_alert:
        return

    # Build alert message
    explainability = signal.explainability_data or {}
    promising = explainability.get("promising", [])
    top_reason = promising[0] if promising else "Strong signal detected"

    alert_message = (
        f"{signal.symbol}: Momentum {signal.momentum_score:.0f} | "
        f"Risk {signal.rug_risk_score:.0f} | "
        f"Confidence {signal.confidence_score:.0f} - {top_reason}"
    )

    alert_data = {
        "type": "high_momentum",
        "token_address": signal.token_address,
        "symbol": signal.symbol,
        "name": signal.name,
        "momentum_score": signal.momentum_score,
        "rug_risk_score": signal.rug_risk_score,
        "confidence_score": signal.confidence_score,
        "explainability": explainability,
        "pump_fun_url": signal.pump_fun_url or f"https://pump.fun/{signal.token_address}",
        "message": alert_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Send WebSocket broadcast to eligible users
    _dispatch_websocket_alert(alert_data)

    # Send email alerts to eligible users
    _dispatch_email_alerts(db, signal, alert_data, alert_message)


def _dispatch_websocket_alert(alert_data: dict):
    """
    Push alert to connected WebSocket clients.
    Only Pro+ users receive alerts (tier gating is in the WebSocket endpoint).
    """
    try:
        import asyncio
        from services.discovery.websocket_manager import manager

        # Try to get the running event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(manager.send_to_tier("pro", {
                "event": "token_alert",
                "data": alert_data,
            }))
        except RuntimeError:
            # No running loop (called from Celery worker) -- skip WebSocket
            # WebSocket alerts only work from the FastAPI process
            pass
    except Exception as e:
        print(f"WebSocket alert dispatch failed: {e}")


def _dispatch_email_alerts(
    db: Session,
    signal: TokenSignal,
    alert_data: dict,
    alert_message: str,
):
    """
    Send email alerts to users with matching preferences.
    Respects per-user filters and cooldown.
    """
    # Get users with email alerts enabled
    prefs = db.query(UserAlertPreference).join(User).filter(
        UserAlertPreference.email_enabled == True,
        User.subscription_tier.in_(ALERT_TIERS),
    ).all()

    for pref in prefs:
        # Check if signal matches user's filters
        if signal.momentum_score < (pref.min_momentum or 60):
            continue
        if signal.rug_risk_score > (pref.max_rug_risk or 40):
            continue
        if signal.confidence_score < (pref.min_confidence or 70):
            continue

        # Check cooldown
        if _is_on_cooldown(db, pref.user_id, signal.token_address, pref.cooldown_minutes or 5):
            continue

        # Record alert
        alert = Alert(
            user_id=pref.user_id,
            token_address=signal.token_address,
            alert_type="high_momentum",
            delivery_method="email",
            delivery_status="pending",
            momentum_score=signal.momentum_score,
            rug_risk_score=signal.rug_risk_score,
            confidence_score=signal.confidence_score,
            message=alert_message,
        )
        db.add(alert)

        # Instant email for ultra/lifetime users
        if pref.email_digest_frequency == "instant":
            user = db.query(User).filter(User.id == pref.user_id).first()
            if user and user.subscription_tier in ("ultra", "lifetime"):
                try:
                    from services.discovery.tasks import send_alert_email
                    send_alert_email.delay(user.email, alert_data)
                    alert.delivery_status = "sent"
                    alert.sent_at = datetime.now(timezone.utc)
                except Exception as e:
                    print(f"Failed to queue email for {user.email}: {e}")
                    alert.delivery_status = "failed"

    db.commit()


def _is_on_cooldown(
    db: Session,
    user_id: str,
    token_address: str,
    cooldown_minutes: int,
) -> bool:
    """Check if an alert was recently sent for this user+token."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    recent = db.query(Alert).filter(
        Alert.user_id == user_id,
        Alert.token_address == token_address,
        Alert.created_at >= cutoff,
    ).first()
    return recent is not None


def send_email(to_email: str, subject: str, body_html: str) -> bool:
    """
    Send an email via SMTP.
    Returns True on success, False on failure.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        print("SMTP not configured -- skipping email")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.ALERT_FROM_EMAIL
        msg["To"] = to_email

        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.ALERT_FROM_EMAIL, to_email, msg.as_string())

        return True

    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False


def build_alert_email_html(alert_data: dict) -> str:
    """Build HTML email body for a token alert."""
    symbol = alert_data.get("symbol", "UNKNOWN")
    momentum = alert_data.get("momentum_score", 0)
    risk = alert_data.get("rug_risk_score", 0)
    confidence = alert_data.get("confidence_score", 0)
    message = alert_data.get("message", "")
    pump_url = alert_data.get("pump_fun_url", "")

    explainability = alert_data.get("explainability", {})
    promising = explainability.get("promising", [])
    risks = explainability.get("risks", [])

    promising_html = "".join(f"<li>{r}</li>" for r in promising)
    risks_html = "".join(f"<li>{r}</li>" for r in risks)

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Forge Terminal Alert: {symbol}</h2>
        <p>{message}</p>

        <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Momentum</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{momentum:.0f}/100</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Rug Risk</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{risk:.0f}/100</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Confidence</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{confidence:.0f}/100</td>
            </tr>
        </table>

        <h3>Why It's Promising</h3>
        <ul>{promising_html if promising_html else '<li>Strong signal detected</li>'}</ul>

        <h3>Risks</h3>
        <ul>{risks_html if risks_html else '<li>None detected</li>'}</ul>

        <p><a href="{pump_url}" style="background: #6366f1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px;">View on Pump.fun</a></p>

        <p style="color: #888; font-size: 12px; margin-top: 24px;">
            This alert was generated by Forge Terminal. You can manage your alert preferences in the dashboard.
        </p>
    </body>
    </html>
    """


def send_digest_emails(db: Session, frequency: str = "hourly"):
    """
    Send batched email digests. Called by the periodic Celery task.

    Collects unsent alerts for users with the given digest frequency,
    batches them into a single email per user.
    """
    # Find unsent alerts for users with this frequency
    prefs = db.query(UserAlertPreference).filter(
        UserAlertPreference.email_enabled == True,
        UserAlertPreference.email_digest_frequency == frequency,
    ).all()

    emails_sent = 0
    for pref in prefs:
        user = db.query(User).filter(User.id == pref.user_id).first()
        if not user or user.subscription_tier not in ALERT_TIERS:
            continue

        # Get pending alerts for this user
        pending_alerts = db.query(Alert).filter(
            Alert.user_id == pref.user_id,
            Alert.delivery_method == "email",
            Alert.delivery_status == "pending",
        ).order_by(Alert.created_at.desc()).limit(20).all()

        if not pending_alerts:
            continue

        # Build digest
        alerts_html = ""
        for alert in pending_alerts:
            alerts_html += f"""
            <div style="border: 1px solid #ddd; padding: 12px; margin: 8px 0; border-radius: 6px;">
                <strong>{alert.token_address[:12]}...</strong>
                <br>Momentum: {alert.momentum_score:.0f} | Risk: {alert.rug_risk_score:.0f} | Confidence: {alert.confidence_score:.0f}
                <br><small>{alert.message or ''}</small>
            </div>
            """

        subject = f"Forge Terminal: {len(pending_alerts)} token alert(s) - {frequency} digest"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Forge Terminal Alert Digest</h2>
            <p>{len(pending_alerts)} token(s) matched your alert criteria:</p>
            {alerts_html}
            <p style="color: #888; font-size: 12px; margin-top: 24px;">
                Manage your alert preferences in the Forge Terminal dashboard.
            </p>
        </body>
        </html>
        """

        if send_email(user.email, subject, body):
            for alert in pending_alerts:
                alert.delivery_status = "sent"
                alert.sent_at = datetime.now(timezone.utc)
            emails_sent += 1
        else:
            for alert in pending_alerts:
                alert.delivery_status = "failed"

    db.commit()
    return emails_sent
