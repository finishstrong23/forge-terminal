"""create initial tables

Revision ID: 000
Revises: None
Create Date: 2026-05-11

Base schema for Forge Terminal. Creates all tables defined under
apps/api/models/, intentionally omitting tier_level and pump_fun_url
on `tokens` — those are added by migration 001 to preserve its history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- Independent tables (no FKs) ----

    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("subscription_tier", sa.String(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_trial", sa.Boolean(), nullable=True),
        sa.Column("subscription_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "wallets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("is_tracked", sa.Boolean(), nullable=True),
        sa.Column("pnl_30d", sa.Float(), nullable=True),
        sa.Column("pnl_60d", sa.Float(), nullable=True),
        sa.Column("pnl_90d", sa.Float(), nullable=True),
        sa.Column("win_rate_30d", sa.Float(), nullable=True),
        sa.Column("trade_count_30d", sa.Integer(), nullable=True),
        sa.Column("avg_hold_minutes", sa.Float(), nullable=True),
        sa.Column("sustainability_score", sa.Float(), nullable=True),
        sa.Column("sustainability_grade", sa.String(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address"),
    )
    op.create_index("ix_wallets_address", "wallets", ["address"])

    op.create_table(
        "wallet_clusters",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("funding_wallet", sa.String(), nullable=True),
        sa.Column("wallet_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_clusters_funding_wallet", "wallet_clusters", ["funding_wallet"])

    # tokens — tier_level and pump_fun_url intentionally omitted; added by 001
    op.create_table(
        "tokens",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scan_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chain_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("token_address", sa.String(), nullable=True),
        sa.Column("bonding_curve_address", sa.String(), nullable=True),
        sa.Column("dev_wallet", sa.String(), nullable=True),
        sa.Column("price_usd", sa.Float(), nullable=True),
        sa.Column("liquidity_usd", sa.Float(), nullable=True),
        sa.Column("fdv", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("volume_5m", sa.Float(), nullable=True),
        sa.Column("volume_1h", sa.Float(), nullable=True),
        sa.Column("volume_6h", sa.Float(), nullable=True),
        sa.Column("volume_24h", sa.Float(), nullable=True),
        sa.Column("buys_5m", sa.Integer(), nullable=True),
        sa.Column("sells_5m", sa.Integer(), nullable=True),
        sa.Column("buys_1h", sa.Integer(), nullable=True),
        sa.Column("sells_1h", sa.Integer(), nullable=True),
        sa.Column("buys_24h", sa.Integer(), nullable=True),
        sa.Column("sells_24h", sa.Integer(), nullable=True),
        sa.Column("buy_ratio_5m", sa.Float(), nullable=True),
        sa.Column("buy_ratio_1h", sa.Float(), nullable=True),
        sa.Column("buy_ratio_24h", sa.Float(), nullable=True),
        sa.Column("price_change_5m", sa.Float(), nullable=True),
        sa.Column("price_change_1h", sa.Float(), nullable=True),
        sa.Column("price_change_6h", sa.Float(), nullable=True),
        sa.Column("price_change_24h", sa.Float(), nullable=True),
        sa.Column("pair_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("age_hours", sa.Float(), nullable=True),
        sa.Column("age_minutes", sa.Float(), nullable=True),
        sa.Column("total_holders", sa.Integer(), nullable=True),
        sa.Column("entity_adjusted_buyers", sa.Integer(), nullable=True),
        sa.Column("holder_concentration", sa.Float(), nullable=True),
        sa.Column("creator_cluster_pct", sa.Float(), nullable=True),
        sa.Column("instant_buy_pct", sa.Float(), nullable=True),
        sa.Column("net_sol_flow_15m", sa.Float(), nullable=True),
        sa.Column("retention_5m", sa.Float(), nullable=True),
        sa.Column("holder_growth_rate", sa.Float(), nullable=True),
        sa.Column("rug_risk_score", sa.Float(), nullable=True),
        sa.Column("momentum_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("explainability_data", sa.JSON(), nullable=True),
        sa.Column("flags", sa.JSON(), nullable=True),
        sa.Column("is_honeypot", sa.Boolean(), nullable=True),
        sa.Column("honeypot_reason", sa.String(), nullable=True),
        sa.Column("has_graduated", sa.Boolean(), nullable=True),
        sa.Column("graduation_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tokens_scan_timestamp", "tokens", ["scan_timestamp"])
    op.create_index("ix_tokens_token_address", "tokens", ["token_address"])
    op.create_index("ix_tokens_bonding_curve_address", "tokens", ["bonding_curve_address"])
    op.create_index("ix_tokens_dev_wallet", "tokens", ["dev_wallet"])
    op.create_index("ix_tokens_rug_risk_score", "tokens", ["rug_risk_score"])
    op.create_index("ix_tokens_momentum_score", "tokens", ["momentum_score"])
    op.create_index("ix_tokens_confidence_score", "tokens", ["confidence_score"])
    op.create_index("ix_tokens_is_honeypot", "tokens", ["is_honeypot"])

    op.create_table(
        "token_scores",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rug_risk_score", sa.Float(), nullable=True),
        sa.Column("momentum_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("explainability_data", sa.JSON(), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_token_scores_token_address", "token_scores", ["token_address"])
    op.create_index("ix_token_scores_scored_at", "token_scores", ["scored_at"])

    op.create_table(
        "helius_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("mint_address", sa.String(), nullable=True),
        sa.Column("bonding_curve_address", sa.String(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signature"),
    )
    op.create_index("ix_helius_events_event_type", "helius_events", ["event_type"])
    op.create_index("ix_helius_events_signature", "helius_events", ["signature"])
    op.create_index("ix_helius_events_mint_address", "helius_events", ["mint_address"])
    op.create_index("ix_helius_events_bonding_curve_address", "helius_events", ["bonding_curve_address"])
    op.create_index("ix_helius_events_processed", "helius_events", ["processed"])
    op.create_index("ix_helius_events_event_timestamp", "helius_events", ["event_timestamp"])

    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("window_type", sa.String(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buys", sa.Integer(), nullable=True),
        sa.Column("sells", sa.Integer(), nullable=True),
        sa.Column("unique_buyers", sa.Integer(), nullable=True),
        sa.Column("unique_sellers", sa.Integer(), nullable=True),
        sa.Column("sol_inflow", sa.Float(), nullable=True),
        sa.Column("sol_outflow", sa.Float(), nullable=True),
        sa.Column("net_sol_flow", sa.Float(), nullable=True),
        sa.Column("holder_count_start", sa.Integer(), nullable=True),
        sa.Column("holder_count_end", sa.Integer(), nullable=True),
        sa.Column("retention_pct", sa.Float(), nullable=True),
        sa.Column("buy_ratio", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metric_snapshots_token_address", "metric_snapshots", ["token_address"])
    op.create_index("ix_metric_snapshots_window_type", "metric_snapshots", ["window_type"])
    op.create_index("ix_snapshot_token_window", "metric_snapshots", ["token_address", "window_type", "window_start"])

    # ---- Tables with foreign keys (created after their targets) ----

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("stripe_price_id", sa.String(), nullable=True),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("billing_cycle", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )

    op.create_table(
        "wallet_trades",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("wallet_address", sa.String(), nullable=False),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("trade_type", sa.String(), nullable=False),
        sa.Column("sol_amount", sa.Float(), nullable=True),
        sa.Column("token_amount", sa.Float(), nullable=True),
        sa.Column("usd_value", sa.Float(), nullable=True),
        sa.Column("price_at_trade", sa.Float(), nullable=True),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["wallet_address"], ["wallets.address"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signature"),
    )
    op.create_index("ix_wallet_trades_wallet_address", "wallet_trades", ["wallet_address"])
    op.create_index("ix_wallet_trades_token_address", "wallet_trades", ["token_address"])
    op.create_index("ix_wallet_trades_signature", "wallet_trades", ["signature"])
    op.create_index("ix_wallet_trades_timestamp", "wallet_trades", ["timestamp"])
    op.create_index("ix_wallet_trade_wallet_time", "wallet_trades", ["wallet_address", "timestamp"])

    op.create_table(
        "wallet_scores",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("wallet_address", sa.String(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("persistence_score", sa.Float(), nullable=True),
        sa.Column("win_rate_score", sa.Float(), nullable=True),
        sa.Column("hold_pattern_score", sa.Float(), nullable=True),
        sa.Column("insider_penalty", sa.Float(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["wallet_address"], ["wallets.address"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_scores_wallet_address", "wallet_scores", ["wallet_address"])

    op.create_table(
        "wallet_activities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("wallet_address", sa.String(), nullable=False),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("activity_type", sa.String(), nullable=False),
        sa.Column("sol_amount", sa.Float(), nullable=True),
        sa.Column("event_signature", sa.String(), nullable=True),
        sa.Column("cluster_id", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cluster_id"], ["wallet_clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_activities_wallet_address", "wallet_activities", ["wallet_address"])
    op.create_index("ix_wallet_activities_token_address", "wallet_activities", ["token_address"])
    op.create_index("ix_wallet_activities_event_signature", "wallet_activities", ["event_signature"])
    op.create_index("ix_wallet_activities_cluster_id", "wallet_activities", ["cluster_id"])
    op.create_index("ix_wallet_token", "wallet_activities", ["wallet_address", "token_address"])
    op.create_index("ix_wallet_activity_token_time", "wallet_activities", ["token_address", "timestamp"])

    op.create_table(
        "copy_subscriptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("wallet_address", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("max_position_usd", sa.Float(), nullable=True),
        sa.Column("daily_loss_cap_usd", sa.Float(), nullable=True),
        sa.Column("slippage_tolerance", sa.Float(), nullable=True),
        sa.Column("min_sustainability_score", sa.Float(), nullable=True),
        sa.Column("token_blacklist", sa.JSON(), nullable=True),
        sa.Column("execution_wallet_pubkey", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copy_subscriptions_user_id", "copy_subscriptions", ["user_id"])
    op.create_index("ix_copy_subscriptions_wallet_address", "copy_subscriptions", ["wallet_address"])

    op.create_table(
        "executed_trades",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("trade_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("sol_amount", sa.Float(), nullable=True),
        sa.Column("token_amount", sa.Float(), nullable=True),
        sa.Column("usd_value", sa.Float(), nullable=True),
        sa.Column("price_at_trade", sa.Float(), nullable=True),
        sa.Column("slippage_pct", sa.Float(), nullable=True),
        sa.Column("fee_amount", sa.Float(), nullable=True),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("copy_subscription_id", sa.String(), nullable=True),
        sa.Column("rug_risk_at_trade", sa.Float(), nullable=True),
        sa.Column("momentum_at_trade", sa.Float(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["copy_subscription_id"], ["copy_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signature"),
    )
    op.create_index("ix_executed_trades_user_id", "executed_trades", ["user_id"])
    op.create_index("ix_executed_trades_token_address", "executed_trades", ["token_address"])
    op.create_index("ix_executed_trades_signature", "executed_trades", ["signature"])
    op.create_index("ix_executed_trade_user_time", "executed_trades", ["user_id", "created_at"])

    op.create_table(
        "user_alert_preferences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("websocket_enabled", sa.Boolean(), nullable=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=True),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=True),
        sa.Column("telegram_bot_token", sa.String(), nullable=True),
        sa.Column("telegram_chat_id", sa.String(), nullable=True),
        sa.Column("email_digest_frequency", sa.String(), nullable=True),
        sa.Column("min_momentum", sa.Float(), nullable=True),
        sa.Column("max_rug_risk", sa.Float(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_alert_preferences_user_id", "user_alert_preferences", ["user_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("token_address", sa.String(), nullable=False),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("delivery_method", sa.String(), nullable=False),
        sa.Column("delivery_status", sa.String(), nullable=True),
        sa.Column("momentum_score", sa.Float(), nullable=True),
        sa.Column("rug_risk_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
    op.create_index("ix_alerts_token_address", "alerts", ["token_address"])
    op.create_index("ix_alert_user_token", "alerts", ["user_id", "token_address"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("user_alert_preferences")
    op.drop_table("executed_trades")
    op.drop_table("copy_subscriptions")
    op.drop_table("wallet_activities")
    op.drop_table("wallet_scores")
    op.drop_table("wallet_trades")
    op.drop_table("subscriptions")
    op.drop_table("metric_snapshots")
    op.drop_table("helius_events")
    op.drop_table("token_scores")
    op.drop_table("tokens")
    op.drop_table("wallet_clusters")
    op.drop_table("wallets")
    op.drop_table("users")
