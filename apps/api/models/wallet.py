from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base, generate_uuid


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(String, primary_key=True, default=generate_uuid)
    address = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=True)
    is_tracked = Column(Boolean, default=False)
    pnl_30d = Column(Float, nullable=True)
    pnl_60d = Column(Float, nullable=True)
    pnl_90d = Column(Float, nullable=True)
    win_rate_30d = Column(Float, nullable=True)
    trade_count_30d = Column(Integer, nullable=True)
    avg_hold_minutes = Column(Float, nullable=True)
    sustainability_score = Column(Float, nullable=True)
    sustainability_grade = Column(String, nullable=True)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_active = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WalletTrade(Base):
    __tablename__ = "wallet_trades"

    id = Column(String, primary_key=True, default=generate_uuid)
    wallet_address = Column(String, ForeignKey("wallets.address"), nullable=False, index=True)
    token_address = Column(String, nullable=False, index=True)
    trade_type = Column(String, nullable=False)
    sol_amount = Column(Float, nullable=True)
    token_amount = Column(Float, nullable=True)
    usd_value = Column(Float, nullable=True)
    price_at_trade = Column(Float, nullable=True)
    signature = Column(String, nullable=True, unique=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_wallet_trade_wallet_time", "wallet_address", "timestamp"),
    )


class WalletScore(Base):
    __tablename__ = "wallet_scores"

    id = Column(String, primary_key=True, default=generate_uuid)
    wallet_address = Column(String, ForeignKey("wallets.address"), nullable=False, index=True)
    scored_at = Column(DateTime(timezone=True), nullable=False)
    persistence_score = Column(Float, nullable=True)
    win_rate_score = Column(Float, nullable=True)
    hold_pattern_score = Column(Float, nullable=True)
    insider_penalty = Column(Float, nullable=True)
    total_score = Column(Float, nullable=True)
    grade = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WalletCluster(Base):
    __tablename__ = "wallet_clusters"

    id = Column(String, primary_key=True, default=generate_uuid)
    funding_wallet = Column(String, nullable=True, index=True)
    wallet_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WalletActivity(Base):
    __tablename__ = "wallet_activities"

    id = Column(String, primary_key=True, default=generate_uuid)
    wallet_address = Column(String, nullable=False, index=True)
    token_address = Column(String, nullable=False, index=True)
    activity_type = Column(String, nullable=False)
    sol_amount = Column(Float, nullable=True)
    event_signature = Column(String, nullable=True, index=True)
    cluster_id = Column(String, ForeignKey("wallet_clusters.id"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_wallet_token", "wallet_address", "token_address"),
        Index("ix_wallet_activity_token_time", "token_address", "timestamp"),
    )
