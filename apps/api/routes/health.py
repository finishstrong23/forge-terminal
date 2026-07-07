"""
Health endpoints.

GET /health          — liveness: process up, DB reachable. Cheap; suitable
                       for load-balancer checks.
GET /health/pipeline — M0 diagnostics: is the DATA PIPELINE alive? Reports
                       per-subsystem state (DB, Redis, webhook ingestion
                       freshness, scored-token freshness, per-beat-task
                       heartbeat staleness) so "the feed is empty" becomes
                       "task X hasn't run in Y minutes". Point uptime
                       monitors at this one.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core import heartbeat
from core.database import get_db
from core.redis_cache import cache
from models.token import HeliusEvent, TokenSignal
from models.wallet import WalletActivity

router = APIRouter()

# task name -> max seconds since last heartbeat before it counts as stale.
# Derived from the beat schedule (celery_app.py) with generous headroom.
BEAT_STALENESS_LIMITS = {
    "discover_new_tokens": 5 * 60,          # runs every 60s
    "record_shadow_trades": 5 * 60,         # runs every 60s
    "aggregate_metric_snapshots": 20 * 60,  # runs every 5m
    "score_wallets": 45 * 60,               # runs every 15m
    "send_email_digest": 25 * 3600,         # hourly + daily variants
}


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "version": "0.1.0",
    }


def _iso(ts: Optional[datetime]) -> Optional[str]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat()


def _age_seconds(ts: Optional[datetime], now: datetime) -> Optional[int]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0, int((now - ts).total_seconds()))


@router.get("/health/pipeline")
def pipeline_health(db: Session = Depends(get_db)):
    """
    Always returns 200 with a `status` field ("ok" | "degraded" | "down")
    so monitors can alert on content, and a browser can always read the
    details. "down" = DB unreachable; "degraded" = Redis down, any beat
    task stale/unknown, or no webhook events in the last hour.
    """
    now = datetime.now(timezone.utc)
    problems = []

    # --- database ---
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        problems.append(f"database unreachable: {exc}")

    # --- redis ---
    redis_report = cache.health_check()
    redis_ok = redis_report.get("status") in {"ok", "healthy", "connected"} or bool(
        cache.available
    )
    if not redis_ok:
        problems.append("redis unavailable (caching + heartbeats disabled)")

    # --- data freshness (only meaningful with a database) ---
    ingestion = discovery = wallet_activity = None
    if db_ok:
        one_hour_ago = now - timedelta(hours=1)

        last_event = db.query(func.max(HeliusEvent.received_at)).scalar()
        events_last_hour = (
            db.query(func.count(HeliusEvent.id))
            .filter(HeliusEvent.received_at >= one_hour_ago)
            .scalar()
            or 0
        )
        backlog = (
            db.query(func.count(HeliusEvent.id))
            .filter(HeliusEvent.processed.is_(False))
            .scalar()
            or 0
        )
        ingestion = {
            "last_event_at": _iso(last_event),
            "age_seconds": _age_seconds(last_event, now),
            "events_last_hour": int(events_last_hour),
            "unprocessed_backlog": int(backlog),
        }
        if events_last_hour == 0:
            problems.append(
                "no Helius webhook events in the last hour (webhook registration / worker?)"
            )

        last_scored = (
            db.query(func.max(TokenSignal.scan_timestamp))
            .filter(
                TokenSignal.momentum_score.isnot(None),
                TokenSignal.rug_risk_score.isnot(None),
            )
            .scalar()
        )
        tokens_last_hour = (
            db.query(func.count(TokenSignal.id))
            .filter(TokenSignal.scan_timestamp >= one_hour_ago)
            .scalar()
            or 0
        )
        discovery = {
            "last_scored_token_at": _iso(last_scored),
            "age_seconds": _age_seconds(last_scored, now),
            "tokens_last_hour": int(tokens_last_hour),
        }

        last_activity = db.query(func.max(WalletActivity.timestamp)).scalar()
        wallet_activity = {
            "last_at": _iso(last_activity),
            "age_seconds": _age_seconds(last_activity, now),
        }

    # --- beat-task heartbeats (Redis-backed) ---
    beats = heartbeat.read(BEAT_STALENESS_LIMITS)
    beat_report = {}
    for task, limit in BEAT_STALENESS_LIMITS.items():
        last = beats.get(task)
        age = _age_seconds(last, now)
        if last is None:
            state = "unknown" if not redis_ok else "never"
        else:
            state = "stale" if age is not None and age > limit else "ok"
        beat_report[task] = {
            "last_run_at": _iso(last),
            "age_seconds": age,
            "max_age_seconds": limit,
            "state": state,
        }
        if state in {"stale", "never"}:
            problems.append(f"beat task {task}: {state} (is the beat/worker process running?)")

    status = "down" if not db_ok else ("degraded" if problems else "ok")
    return {
        "status": status,
        "checked_at": _iso(now),
        "problems": problems,
        "database": {"ok": db_ok},
        "redis": {"ok": redis_ok, **({} if redis_ok else {"detail": redis_report})},
        "ingestion": ingestion,
        "discovery": discovery,
        "wallet_activity": wallet_activity,
        "beat_tasks": beat_report,
    }
