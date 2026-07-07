import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from core.database import get_db
from models.token import TokenSignal
from models.user import User
from routes.auth import get_current_user_optional
from routes.discovery import free_tier_cutoff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/signals/latest")
def get_latest_signals(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    min_momentum: float = Query(0, ge=0, le=100),
    max_rug_risk: float = Query(100, ge=0, le=100),
    min_confidence: float = Query(0, ge=0, le=100),
    hide_honeypots: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    # Filter out partially-scored tokens; same policy as /discovery/feed.
    query = db.query(TokenSignal).filter(
        TokenSignal.momentum_score.isnot(None),
        TokenSignal.rug_risk_score.isnot(None),
    )
    # Free/anonymous callers get delayed signals; paid tiers see realtime.
    cutoff = free_tier_cutoff(current_user)
    if cutoff is not None:
        query = query.filter(TokenSignal.scan_timestamp <= cutoff)

    if hide_honeypots:
        query = query.filter(TokenSignal.is_honeypot.is_(False))
    if min_momentum > 0:
        query = query.filter(TokenSignal.momentum_score >= min_momentum)
    if max_rug_risk < 100:
        query = query.filter(TokenSignal.rug_risk_score <= max_rug_risk)
    if min_confidence > 0:
        query = query.filter(TokenSignal.confidence_score >= min_confidence)

    total = query.count()
    signals = (
        query.order_by(desc(TokenSignal.momentum_score))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Observability: count tokens dropped by the null-score filter in the
    # last hour. Bounded to avoid a full table scan on every request as the
    # tokens table grows.
    # TODO(scaling): sample (1 in N requests) or move to periodic Celery task if traffic grows.
    # Per-request COUNT becomes a hot-path cost on large tables.
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    filtered_out = (
        db.query(TokenSignal)
        .filter(
            TokenSignal.scan_timestamp > one_hour_ago,
            or_(
                TokenSignal.momentum_score.is_(None),
                TokenSignal.rug_risk_score.is_(None),
            ),
        )
        .count()
    )
    logger.info(
        "signals/latest: returned=%d total_matching=%d filtered_out=%d (last 1h) page=%d per_page=%d",
        len(signals), total, filtered_out, page, per_page,
    )

    return {
        "signals": [
            {
                "id": s.id,
                "symbol": s.symbol,
                "name": s.name,
                "token_address": s.token_address,
                "price_usd": s.price_usd,
                "market_cap": s.market_cap,
                "volume_1h": s.volume_1h,
                "liquidity_usd": s.liquidity_usd,
                "rug_risk_score": s.rug_risk_score,
                "momentum_score": s.momentum_score,
                "confidence_score": s.confidence_score,
                "age_minutes": s.age_minutes,
                "holder_count": s.total_holders,
                "buy_ratio_1h": s.buy_ratio_1h,
                "is_honeypot": s.is_honeypot,
                "flags": s.flags or [],
                "explainability": s.explainability_data,
            }
            for s in signals
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
