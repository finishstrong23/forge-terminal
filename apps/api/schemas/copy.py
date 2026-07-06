"""
Pydantic models for the Copy Intelligence leaderboard.

Shared between:
- routes/copy.py — GET /api/v1/copy/leaderboard, GET /api/v1/copy/wallets/{address}

The service layer (services/copy/leaderboard.py) returns plain dicts with ISO
timestamps so results can be Redis-cached as JSON; these models validate and
type the wire format on the way out.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


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
