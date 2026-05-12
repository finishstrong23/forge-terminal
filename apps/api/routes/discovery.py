"""
Discovery feed REST endpoint.

GET /api/v1/discovery/feed — paginated chronological feed of fully-scored
tokens. The frontend Discovery page calls this on initial render and as a
WebSocket reconnect fallback.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.token import TokenSignal
from schemas.discovery import FeedResponse, TokenFeedItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/discovery")


@router.get("/feed", response_model=FeedResponse)
def get_discovery_feed(
    limit: int = Query(50, ge=1, le=200, description="Max tokens to return (1-200, default 50)."),
    since: Optional[datetime] = Query(
        None,
        description="ISO 8601 timestamp. Returns tokens with scan_timestamp strictly > since (cursor pagination).",
    ),
    hide_honeypots: bool = Query(True, description="Drop tokens flagged as honeypots."),
    db: Session = Depends(get_db),
) -> FeedResponse:
    """
    Chronological feed of fully-scored tokens.

    Filters out tokens with NULL momentum_score or rug_risk_score — partial
    scoring runs (e.g. when the metrics aggregation step errors before
    score assignment) should not surface in the feed.

    Pagination: pass `since=<scan_timestamp of last item from previous page>`
    to fetch older entries. The comparison is strict-greater-than, so adjacent
    page boundaries don't double-count.
    """
    base_filters = [
        TokenSignal.momentum_score.isnot(None),
        TokenSignal.rug_risk_score.isnot(None),
    ]
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
    # the cursor window (or last hour if no cursor). Bounded to avoid a full
    # table scan on every request as the tokens table grows.
    # TODO(scaling): sample (1 in N requests) or move to periodic Celery task if traffic grows.
    # Per-request COUNT becomes a hot-path cost on large tables.
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
        "discovery/feed: returned=%d filtered_out=%d (in cursor-window or last 1h) since=%s limit=%d hide_honeypots=%s",
        len(rows), filtered_out, since.isoformat() if since else None, limit, hide_honeypots,
    )

    return FeedResponse(
        tokens=[TokenFeedItem.from_signal(s) for s in rows],
        count=len(rows),
        has_more=has_more,
    )
