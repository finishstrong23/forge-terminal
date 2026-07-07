"""
Beat-task heartbeats (M0 pipeline diagnostics).

Each periodic Celery task calls beat(<task name>) on successful completion;
GET /health/pipeline compares the recorded timestamps against each task's
expected cadence to say WHICH scheduled task is dead, not just that data
looks stale.

Backed by the shared Redis cache wrapper, so this degrades gracefully:
with Redis down, heartbeats read as None ("unknown") and the health
endpoint reports the Redis outage itself as the primary problem.
"""
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

from core.redis_cache import cache

_PREFIX = "heartbeat:"
_TTL_SECONDS = 7 * 24 * 3600  # keep a week; staleness math happens at read time


def beat(task_name: str) -> None:
    """Record a successful completion of a periodic task. Never raises."""
    try:
        cache.set(
            f"{_PREFIX}{task_name}",
            datetime.now(timezone.utc).isoformat(),
            ttl=_TTL_SECONDS,
        )
    except Exception:
        # A monitoring write must never take down the task it monitors.
        pass


def read(task_names: Iterable[str]) -> Dict[str, Optional[datetime]]:
    """Last completion time per task; None = never recorded / Redis down."""
    result: Dict[str, Optional[datetime]] = {}
    for name in task_names:
        value = cache.get(f"{_PREFIX}{name}")
        try:
            result[name] = datetime.fromisoformat(value) if value else None
        except (TypeError, ValueError):
            result[name] = None
    return result
