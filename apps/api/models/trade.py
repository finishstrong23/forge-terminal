from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, JSON, ForeignKey, Index
from datetime import datetime, timezone

from .base import Base, generate_uuid


class CopySubscription(Base):
    __tablename__ = "copy_subscriptions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    wallet_address = Column(String, nullable=False, index=True)
    mode = Column(String, nullable=False, default="shadow")
    status = Column(String, nullable=False, default="active")
    max_position_usd = Column(Float, nullable=True)
    daily_loss_cap_usd = Column(Float, nullable=True)
    slippage_tolerance = Column(Float, nullable=True)
    min_sustainability_score = Column(Float, nullable=True)
    token_blacklist = Column(JSON, nullable=True)
    execution_wallet_pubkey = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    paused_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ExecutedTrade(Base):
    __tablename__ = "executed_trades"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_address = Column(String, nullable=False, index=True)
    trade_type = Column(String, nullable=False)
    source = Column(String, nullable=False, default="manual")
    sol_amount = Column(Float, nullable=True)
    token_amount = Column(Float, nullable=True)
    usd_value = Column(Float, nullable=True)
    price_at_trade = Column(Float, nullable=True)
    slippage_pct = Column(Float, nullable=True)
    fee_amount = Column(Float, nullable=True)
    signature = Column(String, nullable=True, unique=True, index=True)
    status = Column(String, nullable=False, default="pending")
    error_message = Column(String, nullable=True)
    copy_subscription_id = Column(String, ForeignKey("copy_subscriptions.id"), nullable=True)
    rug_risk_at_trade = Column(Float, nullable=True)
    momentum_at_trade = Column(Float, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_executed_trade_user_time", "user_id", "created_at"),
    )
