from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, Text, ForeignKey, Index
from datetime import datetime, timezone

from .base import Base, generate_uuid


class UserAlertPreference(Base):
    __tablename__ = "user_alert_preferences"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    websocket_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=False)
    telegram_enabled = Column(Boolean, default=False)
    telegram_bot_token = Column(String, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
    email_digest_frequency = Column(String, default="instant")
    min_momentum = Column(Float, default=60.0)
    max_rug_risk = Column(Float, default=40.0)
    min_confidence = Column(Float, default=70.0)
    cooldown_minutes = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    token_address = Column(String, nullable=False, index=True)
    alert_type = Column(String, nullable=False)
    delivery_method = Column(String, nullable=False)
    delivery_status = Column(String, default="pending")
    momentum_score = Column(Float, nullable=True)
    rug_risk_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_alert_user_token", "user_id", "token_address"),
    )
