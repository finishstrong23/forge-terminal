from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, JSON, Text, Index
from datetime import datetime, timezone

from .base import Base, generate_uuid


class TokenSignal(Base):
    __tablename__ = "tokens"

    id = Column(String, primary_key=True, default=generate_uuid)
    scan_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    chain_id = Column(String, nullable=False, default="solana")

    symbol = Column(String, nullable=True)
    name = Column(String, nullable=True)
    token_address = Column(String, nullable=True, index=True)
    bonding_curve_address = Column(String, nullable=True, index=True)
    dev_wallet = Column(String, nullable=True, index=True)

    price_usd = Column(Float, nullable=True)
    liquidity_usd = Column(Float, nullable=True)
    fdv = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)

    volume_5m = Column(Float, nullable=True)
    volume_1h = Column(Float, nullable=True)
    volume_6h = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)

    buys_5m = Column(Integer, nullable=True)
    sells_5m = Column(Integer, nullable=True)
    buys_1h = Column(Integer, nullable=True)
    sells_1h = Column(Integer, nullable=True)
    buys_24h = Column(Integer, nullable=True)
    sells_24h = Column(Integer, nullable=True)

    buy_ratio_5m = Column(Float, nullable=True)
    buy_ratio_1h = Column(Float, nullable=True)
    buy_ratio_24h = Column(Float, nullable=True)

    price_change_5m = Column(Float, nullable=True)
    price_change_1h = Column(Float, nullable=True)
    price_change_6h = Column(Float, nullable=True)
    price_change_24h = Column(Float, nullable=True)

    pair_created_at = Column(DateTime(timezone=True), nullable=True)
    age_hours = Column(Float, nullable=True)
    age_minutes = Column(Float, nullable=True)

    total_holders = Column(Integer, nullable=True)
    entity_adjusted_buyers = Column(Integer, nullable=True)
    holder_concentration = Column(Float, nullable=True)
    creator_cluster_pct = Column(Float, nullable=True)
    instant_buy_pct = Column(Float, nullable=True)
    net_sol_flow_15m = Column(Float, nullable=True)
    retention_5m = Column(Float, nullable=True)
    holder_growth_rate = Column(Float, nullable=True)

    rug_risk_score = Column(Float, nullable=True, index=True)
    momentum_score = Column(Float, nullable=True, index=True)
    confidence_score = Column(Float, nullable=True, index=True)

    explainability_data = Column(JSON, nullable=True)
    flags = Column(JSON, nullable=True)
    is_honeypot = Column(Boolean, default=False, index=True)
    honeypot_reason = Column(String, nullable=True)

    tier_level = Column(String, default="free", index=True)
    pump_fun_url = Column(String, nullable=True)

    has_graduated = Column(Boolean, default=False)
    graduation_timestamp = Column(DateTime(timezone=True), nullable=True)
    token_metadata = Column(JSON, nullable=True)


class TokenScore(Base):
    __tablename__ = "token_scores"

    id = Column(String, primary_key=True, default=generate_uuid)
    token_address = Column(String, nullable=False, index=True)
    scored_at = Column(DateTime(timezone=True), nullable=False, index=True)
    rug_risk_score = Column(Float, nullable=True)
    momentum_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    explainability_data = Column(JSON, nullable=True)
    input_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class HeliusEvent(Base):
    __tablename__ = "helius_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    event_type = Column(String, nullable=False, index=True)
    signature = Column(String, nullable=False, unique=True, index=True)
    mint_address = Column(String, nullable=True, index=True)
    bonding_curve_address = Column(String, nullable=True, index=True)
    raw_data = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    token_address = Column(String, nullable=False, index=True)
    window_type = Column(String, nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    buys = Column(Integer, default=0)
    sells = Column(Integer, default=0)
    unique_buyers = Column(Integer, default=0)
    unique_sellers = Column(Integer, default=0)
    sol_inflow = Column(Float, default=0.0)
    sol_outflow = Column(Float, default=0.0)
    net_sol_flow = Column(Float, default=0.0)
    holder_count_start = Column(Integer, nullable=True)
    holder_count_end = Column(Integer, nullable=True)
    retention_pct = Column(Float, nullable=True)
    buy_ratio = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_snapshot_token_window", "token_address", "window_type", "window_start"),
    )
