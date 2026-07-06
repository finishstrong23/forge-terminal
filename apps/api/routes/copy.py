"""
Copy Intelligence REST endpoints (Phase 2, v1).

GET /api/v1/copy/leaderboard        — ranked wallet leaderboard over a window
GET /api/v1/copy/wallets/{address}  — one wallet's stats + recent trade history

Both aggregate WalletActivity rows recorded by the discovery webhook pipeline.
The leaderboard runs a double GROUP BY over wallet_activities, so responses
are cached in Redis for LEADERBOARD_CACHE_TTL seconds (graceful no-op when
Redis is down — core.redis_cache falls back to computing every request).
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.redis_cache import cache
from schemas.copy import LeaderboardResponse, WalletDetailResponse
from services.copy.leaderboard import compute_leaderboard, compute_wallet_detail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/copy")

LEADERBOARD_CACHE_TTL = 60  # seconds

Window = Literal["24h", "7d", "30d"]


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    window: Window = Query("24h", description="Aggregation window."),
    limit: int = Query(25, ge=1, le=100, description="Max wallets to return."),
    offset: int = Query(0, ge=0, description="Rank offset for pagination."),
    min_trades: int = Query(3, ge=1, description="Minimum in-window trades to qualify."),
    exclude_clustered: bool = Query(
        False, description="Drop wallets linked to a funding cluster (insider signal)."
    ),
    db: Session = Depends(get_db),
) -> LeaderboardResponse:
    """
    Wallet leaderboard ranked by net SOL flow (sells - buys) in the window.

    win_rate is null for wallets with no closed positions yet. Wallets with
    fewer than `min_trades` in-window trades are excluded as noise.
    """
    cache_key = (
        f"copy:leaderboard:{window}:{limit}:{offset}:{min_trades}:{exclude_clustered}"
    )
    result = cache.get_or_compute(
        cache_key,
        lambda: compute_leaderboard(
            db,
            window=window,
            limit=limit,
            offset=offset,
            min_trades=min_trades,
            exclude_clustered=exclude_clustered,
        ),
        ttl=LEADERBOARD_CACHE_TTL,
    )
    return LeaderboardResponse(
        entries=result["entries"],
        count=len(result["entries"]),
        has_more=result["has_more"],
        window=window,
    )


@router.get("/wallets/{wallet_address}", response_model=WalletDetailResponse)
def get_wallet_detail(
    wallet_address: str,
    window: Window = Query("24h", description="Aggregation window for stats."),
    db: Session = Depends(get_db),
) -> WalletDetailResponse:
    """
    Windowed stats plus recent trade history (all-time, latest 50 events)
    for a single wallet. 404 if the wallet has never recorded activity.
    """
    result = compute_wallet_detail(db, wallet_address, window=window)
    if result is None:
        raise HTTPException(status_code=404, detail="Wallet has no recorded activity")
    return WalletDetailResponse(
        wallet=result["wallet"],
        window=window,
        recent_activity=result["recent_activity"],
    )
