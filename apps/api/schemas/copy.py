"""
Pydantic models for the Copy Intelligence leaderboard.

Shared between:
- routes/copy.py — GET /api/v1/copy/leaderboard, GET /api/v1/copy/wallets/{address}

The service layer (services/copy/leaderboard.py) returns plain dicts with ISO
timestamps so results can be Redis-cached as JSON; these models validate and
type the wire format on the way out.
"""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class WalletStats(BaseModel):
    """Windowed performance stats for one wallet (SOL-flow PnL proxy, v1)."""
    wallet_address: str
    total_trades: int
    buy_count: int
    sell_count: int
    tokens_traded: int
    closed_positions: int
    wins: int
    win_rate: Optional[float] = None
    sol_in: float
    sol_out: float
    net_sol: float
    active_days: int
    sustainability_score: float
    sustainability_grade: Optional[str] = None
    is_clustered: bool = False
    last_active: Optional[datetime] = None


class LeaderboardEntry(WalletStats):
    """A ranked leaderboard row."""
    rank: int


class LeaderboardResponse(BaseModel):
    """Envelope for GET /api/v1/copy/leaderboard."""
    entries: List[LeaderboardEntry]
    count: int
    has_more: bool
    window: str


class WalletActivityItem(BaseModel):
    """One row of a wallet's recent trade history."""
    token_address: str
    symbol: Optional[str] = None
    activity_type: str
    sol_amount: Optional[float] = None
    signature: Optional[str] = None
    timestamp: Optional[datetime] = None


class WalletDetailResponse(BaseModel):
    """Envelope for GET /api/v1/copy/wallets/{address}."""
    wallet: WalletStats
    window: str
    recent_activity: List[WalletActivityItem]


class ScoreSnapshot(BaseModel):
    """One persisted WalletScore row (written by tasks.score_wallets)."""
    scored_at: datetime
    total_score: Optional[float] = None
    grade: Optional[str] = None
    persistence_score: Optional[float] = None
    win_rate_score: Optional[float] = None
    hold_pattern_score: Optional[float] = None
    insider_penalty: Optional[float] = None


class ScoreHistoryResponse(BaseModel):
    """Envelope for GET /api/v1/copy/wallets/{address}/score-history."""
    wallet_address: str
    snapshots: List[ScoreSnapshot]
    count: int


class CopySubscriptionCreate(BaseModel):
    """
    Follow a wallet. v1 allows shadow mode only — trades are recorded, not
    executed. Live copy execution lands with the Phase 3 execution layer.
    """
    wallet_address: str = Field(min_length=1)
    mode: Literal["shadow"] = "shadow"
    max_position_usd: Optional[float] = Field(None, gt=0)
    daily_loss_cap_usd: Optional[float] = Field(None, gt=0)
    slippage_tolerance: Optional[float] = Field(None, ge=0, le=1)
    min_sustainability_score: Optional[float] = Field(None, ge=0, le=100)
    token_blacklist: Optional[List[str]] = None


class CopySubscriptionAction(BaseModel):
    """PATCH body for state transitions."""
    action: Literal["pause", "resume", "stop"]


class CopySubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    wallet_address: str
    mode: str
    status: str
    max_position_usd: Optional[float] = None
    daily_loss_cap_usd: Optional[float] = None
    slippage_tolerance: Optional[float] = None
    min_sustainability_score: Optional[float] = None
    token_blacklist: Optional[List[str]] = None
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    created_at: datetime


class CopySubscriptionListResponse(BaseModel):
    """Envelope for GET /api/v1/copy/subscriptions."""
    subscriptions: List[CopySubscriptionResponse]
    count: int


class ShadowTradeResponse(BaseModel):
    """One row of the caller's shadow-trade ledger (ExecutedTrade)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    token_address: str
    trade_type: str
    source: str
    sol_amount: Optional[float] = None
    usd_value: Optional[float] = None
    price_at_trade: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    copy_subscription_id: Optional[str] = None
    rug_risk_at_trade: Optional[float] = None
    momentum_at_trade: Optional[float] = None
    executed_at: Optional[datetime] = None
    created_at: datetime


class ShadowTradeListResponse(BaseModel):
    """Envelope for GET /api/v1/copy/trades."""
    trades: List[ShadowTradeResponse]
    count: int
