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
from celery import Celery
from celery.schedules import crontab

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
)

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
