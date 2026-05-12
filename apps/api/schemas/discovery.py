"""
Pydantic models for the Discovery feed.

Shared between:
- routes/discovery.py        — GET /api/v1/discovery/feed (REST)
- (Milestone 3) websocket    — /ws/discovery broadcast payload

`TokenFeedItem.from_signal(...)` builds an instance from a TokenSignal ORM
object, applying the field translations needed by the frontend
(age_minutes -> age_seconds derivation, total_holders -> holder_count rename,
None flags -> empty list, etc.) so route handlers don't reimplement them.
"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict

from models.token import TokenSignal


class TokenFeedItem(BaseModel):
    """
    A single scored token in the discovery feed.

    rug_risk_score and momentum_score are non-Optional here because the feed
    endpoints filter rows where these are NULL. Other score/metric fields
    remain Optional so partially-aggregated tokens still serialize cleanly.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    token_address: Optional[str] = None
    symbol: Optional[str] = None
    name: Optional[str] = None
    scan_timestamp: datetime
    age_minutes: Optional[float] = None
    age_seconds: Optional[int] = None
    price_usd: Optional[float] = None
    market_cap: Optional[float] = None
    volume_1h: Optional[float] = None
    liquidity_usd: Optional[float] = None
    rug_risk_score: float
    momentum_score: float
    confidence_score: Optional[float] = None
    holder_count: Optional[int] = None
    buy_ratio_1h: Optional[float] = None
    is_honeypot: bool = False
    flags: List[str] = []
    source_dex: str = "pump_fun"  # TODO(task-2): derive from event data when multi-DEX lands
    explainability: Optional[Any] = None

    @classmethod
    def from_signal(cls, s: TokenSignal) -> "TokenFeedItem":
        age_seconds = int(s.age_minutes * 60) if s.age_minutes is not None else None
        return cls(
            id=s.id,
            token_address=s.token_address,
            symbol=s.symbol,
            name=s.name,
            scan_timestamp=s.scan_timestamp,
            age_minutes=s.age_minutes,
            age_seconds=age_seconds,
            price_usd=s.price_usd,
            market_cap=s.market_cap,
            volume_1h=s.volume_1h,
            liquidity_usd=s.liquidity_usd,
            rug_risk_score=s.rug_risk_score,
            momentum_score=s.momentum_score,
            confidence_score=s.confidence_score,
            holder_count=s.total_holders,
            buy_ratio_1h=s.buy_ratio_1h,
            is_honeypot=bool(s.is_honeypot),
            flags=s.flags or [],
            source_dex="pump_fun",  # TODO(task-2): derive from event data when multi-DEX lands
            explainability=s.explainability_data,
        )


class FeedResponse(BaseModel):
    """Envelope for GET /api/v1/discovery/feed."""
    tokens: List[TokenFeedItem]
    count: int
    has_more: bool
