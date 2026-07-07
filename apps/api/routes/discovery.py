"""
Discovery feed REST endpoint.

GET /api/v1/discovery/feed — paginated chronological feed of fully-scored
tokens. The frontend Discovery page calls this on initial render and as a
WebSocket reconnect fallback.
"""
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from models.token import TokenSignal
from models.user import User
from routes.auth import get_current_user_optional
from schemas.discovery import FeedResponse, TokenFeedItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/discovery")

# Fraction of requests that pay for the filtered-out observability COUNT.
OBSERVABILITY_SAMPLE_RATE = 0.05


def free_tier_cutoff(user: Optional[User]) -> Optional[datetime]:
    """
    Free/anonymous callers see signals delayed by FREE_TIER_DELAY_MINUTES;
    paid tiers see realtime. Returns the max scan_timestamp allowed, or
    None for no restriction.
    """
    if user is not None and user.subscription_tier != "free":
        return None
    if settings.FREE_TIER_DELAY_MINUTES <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(minutes=settings.FREE_TIER_DELAY_MINUTES)


@router.get("/feed", response_model=FeedResponse)
def get_discovery_feed(
    limit: int = Query(50, ge=1, le=200, description="Max tokens to return (1-200, default 50)."),
    since: Optional[datetime] = Query(
        None,
        description="ISO 8601 timestamp. Returns tokens with scan_timestamp strictly > since (cursor pagination).",
    ),
    hide_honeypots: bool = Query(True, description="Drop tokens flagged as honeypots."),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> FeedResponse:
    """
    Chronological feed of fully-scored tokens.

    Filters out tokens with NULL momentum_score or rug_risk_score — partial
    scoring runs (e.g. when the metrics aggregation step errors before
    score assignment) should not surface in the feed.

    Free/anonymous callers get signals delayed by FREE_TIER_DELAY_MINUTES;
    paid tiers see realtime.

    Pagination: pass `since=<scan_timestamp of last item from previous page>`
    to fetch older entries. The comparison is strict-greater-than, so adjacent
    page boundaries don't double-count.
    """
    base_filters = [
        TokenSignal.momentum_score.isnot(None),
        TokenSignal.rug_risk_score.isnot(None),
    ]
    cutoff = free_tier_cutoff(current_user)
    if cutoff is not None:
        base_filters.append(TokenSignal.scan_timestamp <= cutoff)
    window_filters = []
    if since is not None:
        window_filters.append(TokenSignal.scan_timestamp > since)
    if hide_honeypots:
        base_filters.append(TokenSignal.is_honeypot.is_(False))

    # Fetch limit+1 so we can compute has_more without a separate COUNT.
    rows = (
        db.query(TokenSignal)
        .filter(*base_filters, *window_filters)
        .order_by(desc(TokenSignal.scan_timestamp))
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    # Observability: count tokens that the null-score filter dropped within
    # the cursor window (or last hour if no cursor). Sampled 1-in-20 so the
    # COUNT never becomes a hot-path cost on large tables (was TODO(scaling)).
    if random.random() < OBSERVABILITY_SAMPLE_RATE:
        count_window = window_filters or [
            TokenSignal.scan_timestamp > datetime.now(timezone.utc) - timedelta(hours=1)
        ]
        filtered_out = (
            db.query(TokenSignal)
            .filter(
                *count_window,
                or_(
                    TokenSignal.momentum_score.is_(None),
                    TokenSignal.rug_risk_score.is_(None),
                ),
            )
            .count()
        )
        logger.info(
            "discovery/feed (sampled): returned=%d filtered_out=%d (in cursor-window or last 1h) since=%s limit=%d hide_honeypots=%s",
            len(rows), filtered_out, since.isoformat() if since else None, limit, hide_honeypots,
        )

    return FeedResponse(
        tokens=[TokenFeedItem.from_signal(s) for s in rows],
        count=len(rows),
        has_more=has_more,
    )
