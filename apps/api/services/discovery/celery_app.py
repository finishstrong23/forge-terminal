"""
Celery Application Configuration
=================================

Background task processing for Forge Terminal using Redis as broker.

Usage:
    # Start worker:
    celery -A services.discovery.celery_app worker --loglevel=info --concurrency=2

    # Start beat scheduler (periodic tasks):
    celery -A services.discovery.celery_app beat --loglevel=info

    # Start both (dev only):
    celery -A services.discovery.celery_app worker --beat --loglevel=info --concurrency=2
"""
import os
import re
from datetime import datetime, timezone

from celery import Celery
from celery.schedules import crontab
from celery.signals import beat_init, task_failure, worker_ready

# Strip secrets that routinely appear in exception text (Helius api-key
# query params, redis/postgres credentials in connection URLs) before it's
# stored where an operator could read it.
_SECRET_PATTERNS = [
    (re.compile(r"(api-key=)[^&\s\"']+", re.I), r"\1<redacted>"),
    (re.compile(r"(://[^:/\s]+:)[^@/\s]+(@)"), r"\1<redacted>\2"),
]


def _redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text

# Task failures should reach Sentry, not just worker logs (M5 alerting).
# CeleryIntegration hooks task_failure; release/environment match the API.
_SENTRY_DSN = os.getenv("SENTRY_DSN")
if _SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.05,
        release=os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA"),
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
    )

# Read Redis URL from environment (same as config.py)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_ALWAYS_EAGER = os.getenv("CELERY_ALWAYS_EAGER", "false").lower() == "true"

celery_app = Celery(
    "pumpfair",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["services.discovery.tasks"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_soft_time_limit=120,  # soft limit: 2 minutes
    task_time_limit=180,       # hard limit: 3 minutes
    task_acks_late=True,       # acknowledge after completion (safer)
    worker_prefetch_multiplier=1,  # fetch one task at a time

    # Results
    result_expires=3600,  # expire results after 1 hour

    # Testing mode: run tasks synchronously in-process
    task_always_eager=CELERY_ALWAYS_EAGER,
    task_eager_propagates=CELERY_ALWAYS_EAGER,

    # Survive a broker that's down at boot (e.g. Redis restarting) instead
    # of exiting — Railway's ON_FAILURE restart cap can otherwise leave the
    # process permanently stopped after a long outage.
    broker_connection_retry_on_startup=True,
)


# --- process-level liveness + failure capture (M0 diagnostics) -----------
# /health/celery-debug reads these to tell "process never started" apart
# from "process runs but tasks fail" — without needing Railway log access.

@worker_ready.connect
def _mark_worker_ready(**_kwargs):
    from core.heartbeat import beat as _heartbeat

    _heartbeat("process:worker")


@beat_init.connect
def _mark_beat_started(**_kwargs):
    from core.heartbeat import beat as _heartbeat

    _heartbeat("process:beat")


@task_failure.connect
def _record_task_failure(sender=None, exception=None, **_kwargs):
    """Persist the most recent task exception so production failures are
    visible in /health/celery-debug. Must never break the task path."""
    from core.redis_cache import cache

    try:
        cache.set(
            "celery:last_task_failure",
            {
                "task": getattr(sender, "name", str(sender)),
                "error": _redact(f"{type(exception).__name__}: {exception}")[:500],
                "at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=7 * 24 * 3600,
        )
    except Exception:
        pass

# Periodic tasks (Celery Beat schedule)
celery_app.conf.beat_schedule = {
    "aggregate-metrics-5m": {
        "task": "tasks.aggregate_metric_snapshots",
        "schedule": 300.0,  # every 5 minutes
    },
    "discover-new-tokens": {
        "task": "tasks.discover_new_tokens",
        "schedule": 60.0,  # every 60 seconds
    },
    "score-wallets-15m": {
        "task": "tasks.score_wallets",
        "schedule": 900.0,  # every 15 minutes
    },
    "record-shadow-trades": {
        "task": "tasks.record_shadow_trades",
        "schedule": 60.0,  # every 60 seconds
    },
    "refresh-sol-price": {
        "task": "tasks.refresh_sol_price",
        "schedule": 60.0,  # every 60 seconds
    },
    "enrich-token-metadata": {
        "task": "tasks.enrich_token_metadata",
        "schedule": 60.0,  # every 60 seconds
    },
    "check-trade-confirmations": {
        "task": "tasks.check_trade_confirmations",
        "schedule": 120.0,  # every 2 minutes
    },
    "send-email-digest-hourly": {
        "task": "tasks.send_email_digest",
        "schedule": 3600.0,  # every hour
        "kwargs": {"frequency": "hourly"},
    },
    "send-email-digest-daily": {
        "task": "tasks.send_email_digest",
        "schedule": crontab(hour=9, minute=0),  # 9 AM UTC daily
        "kwargs": {"frequency": "daily"},
    },
}
