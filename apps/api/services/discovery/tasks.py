"""
Celery Task Definitions
========================

All background tasks for Forge Terminal. Each task creates its own DB session
since Celery workers run outside FastAPI's dependency injection.
"""
from services.discovery.celery_app import celery_app
from core.database import SessionLocal
from datetime import datetime, timezone


def _get_db():
    """Create a standalone DB session for Celery tasks"""
    return SessionLocal()


# ==================== WEBHOOK PROCESSING ====================

@celery_app.task(name="tasks.process_webhook_event", bind=True, max_retries=3)
def process_webhook_event(self, event_id: str):
    """
    Process a single Helius webhook event in the background.

    Called from webhook_handler.helius_webhook() after storing the raw event.
    """
    db = _get_db()
    try:
        from models.token import HeliusEvent
        from services.discovery.webhook_handler import HeliusWebhookProcessor

        event = db.query(HeliusEvent).filter(HeliusEvent.id == event_id).first()
        if not event:
            print(f"Event {event_id} not found")
            return {"status": "not_found", "event_id": event_id}

        if event.processed:
            return {"status": "already_processed", "event_id": event_id}

        processor = HeliusWebhookProcessor(db)
        signal = processor.process_event(event)

        if signal:
            return {
                "status": "processed",
                "event_id": event_id,
                "token": signal.symbol,
                "momentum": signal.momentum_score,
            }
        return {"status": "skipped", "event_id": event_id}

    except Exception as exc:
        db.rollback()
        print(f"Task process_webhook_event failed for {event_id}: {exc}")
        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()


# ==================== METADATA ====================

@celery_app.task(name="tasks.refresh_token_metadata", bind=True, max_retries=2)
def refresh_token_metadata(self, token_address: str):
    """
    Refresh Pump.fun metadata for a single token.
    """
    db = _get_db()
    try:
        from models.token import TokenSignal
        from services.discovery.webhook_handler import fetch_pump_fun_metadata_sync

        token = db.query(TokenSignal).filter(
            TokenSignal.token_address == token_address
        ).first()

        if not token:
            return {"status": "not_found"}

        metadata = fetch_pump_fun_metadata_sync(token_address)
        if metadata:
            token.symbol = metadata.get("symbol", token.symbol)
            token.name = metadata.get("name", token.name)
            token.token_metadata = metadata
            token.dev_wallet = metadata.get("creator")
            token.has_graduated = metadata.get("complete", False)
            if metadata.get("market_cap"):
                token.market_cap = metadata["market_cap"]
            db.commit()
            return {"status": "updated", "symbol": token.symbol}

        return {"status": "no_metadata"}

    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


# ==================== SCORE RECALCULATION ====================

@celery_app.task(name="tasks.recalculate_scores")
def recalculate_scores(token_address: str):
    """
    Recalculate scores for a single token using live wallet-activity metrics
    with fallback to stored TokenSignal fields.
    """
    db = _get_db()
    try:
        from models.token import TokenSignal
        from services.discovery.scoring_engine import score_token
        from services.discovery.metrics_aggregator import get_current_metrics
        from services.discovery.wallet_clustering import recalculate_entity_adjusted_buyers

        token = db.query(TokenSignal).filter(
            TokenSignal.token_address == token_address
        ).first()

        if not token:
            return {"status": "not_found"}

        # Update age
        if token.pair_created_at:
            age = datetime.now(timezone.utc) - token.pair_created_at
            token.age_minutes = age.total_seconds() / 60
            token.age_hours = token.age_minutes / 60

        # Try live metrics from WalletActivity (Phase 2)
        live = get_current_metrics(db, token_address)
        has_wallet_data = live.get("total_unique_buyers", 0) > 0

        if has_wallet_data:
            token.buys_5m = live["buys_5m"]
            token.sells_5m = live["sells_5m"]
            token.buy_ratio_5m = live["buy_ratio_5m"]
            token.net_sol_flow_15m = live["net_sol_flow_15m"]
            token.retention_5m = live["retention_5m"]
            token.total_holders = live["total_holders"]
            token.entity_adjusted_buyers = recalculate_entity_adjusted_buyers(
                db, token_address
            )

        # Holder concentration heuristic
        holders = max(token.entity_adjusted_buyers or 1, 1)
        if holders >= 50:
            token.holder_concentration = max(10, 50 - (holders - 50) * 0.5)
        elif holders >= 20:
            token.holder_concentration = max(20, 70 - (holders - 20) * 0.67)
        elif holders >= 10:
            token.holder_concentration = max(30, 80 - (holders - 10) * 1)
        else:
            token.holder_concentration = max(50, 100 - holders * 5)

        holder_growth_rate = 0
        if token.age_minutes and token.age_minutes > 0:
            holder_growth_rate = holders / token.age_minutes
            token.holder_growth_rate = holder_growth_rate

        token_data = {
            "holder_concentration": token.holder_concentration or 0,
            "creator_cluster_pct": token.creator_cluster_pct or 0,
            "instant_buy_pct": token.instant_buy_pct or 0,
            "entity_adjusted_buyers": token.entity_adjusted_buyers or 1,
            "net_sol_flow_15m": token.net_sol_flow_15m or 0,
            "retention_5m": token.retention_5m or 100,
            "buys_5m": token.buys_5m or 0,
            "sells_5m": token.sells_5m or 0,
            "buy_ratio_5m": token.buy_ratio_5m or 50,
            "age_minutes": token.age_minutes or 0,
            "has_freeze_authority": False,
            "has_mint_authority": False,
            "last_update_minutes_ago": 0,
            "holder_growth_rate": holder_growth_rate,
            "total_holders": token.total_holders or 1,
        }

        scores = score_token(token_data)
        token.rug_risk_score = scores["rug_risk_score"]
        token.momentum_score = scores["momentum_score"]
        token.confidence_score = scores["confidence_score"]
        token.explainability_data = scores["explainability_data"]

        db.commit()
        return {"status": "recalculated", "momentum": token.momentum_score}

    except Exception as exc:
        db.rollback()
        print(f"Failed to recalculate scores for {token_address}: {exc}")
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


# ==================== WALLET CLUSTERING ====================

@celery_app.task(name="tasks.resolve_wallet_cluster", bind=True, max_retries=2)
def resolve_wallet_cluster(self, wallet_address: str):
    """
    Look up funding source for a wallet and assign it to a cluster.
    Uses Helius RPC to find the wallet's initial funder.
    """
    import asyncio
    from services.discovery.wallet_clustering import lookup_funding_wallet, assign_cluster

    db = _get_db()
    try:
        # Run async lookup synchronously in Celery worker
        loop = asyncio.new_event_loop()
        try:
            funding_wallet = loop.run_until_complete(lookup_funding_wallet(wallet_address))
        finally:
            loop.close()

        if not funding_wallet:
            return {"status": "no_funder_found", "wallet": wallet_address[:8]}

        cluster = assign_cluster(db, wallet_address, funding_wallet)

        # Recalculate entity_adjusted_buyers for all tokens this wallet touched
        from models.wallet import WalletActivity
        from models.token import TokenSignal
        from sqlalchemy import distinct as sa_distinct

        token_addresses = [
            row[0] for row in db.query(sa_distinct(WalletActivity.token_address)).filter(
                WalletActivity.wallet_address == wallet_address
            ).all()
        ]

        from services.discovery.wallet_clustering import recalculate_entity_adjusted_buyers
        for token_addr in token_addresses:
            new_count = recalculate_entity_adjusted_buyers(db, token_addr)
            token = db.query(TokenSignal).filter(
                TokenSignal.token_address == token_addr
            ).first()
            if token:
                token.entity_adjusted_buyers = new_count

        db.commit()
        return {
            "status": "clustered",
            "wallet": wallet_address[:8],
            "cluster_id": cluster.id[:8],
            "tokens_updated": len(token_addresses),
        }

    except Exception as exc:
        db.rollback()
        print(f"Failed to resolve cluster for {wallet_address[:8]}: {exc}")
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


# ==================== METRICS AGGREGATION ====================

@celery_app.task(name="tasks.aggregate_metric_snapshots")
def aggregate_metric_snapshots():
    """
    Periodic task: aggregate metric snapshots for active tokens.
    Runs every 5 minutes via Celery Beat.
    """
    from core.heartbeat import beat
    from services.discovery.metrics_aggregator import aggregate_active_tokens

    db = _get_db()
    try:
        count = aggregate_active_tokens(db)
        beat("aggregate_metric_snapshots")
        return {"status": "completed", "snapshots_created": count}
    except Exception as exc:
        db.rollback()
        print(f"Failed to aggregate metrics: {exc}")
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


# ==================== COPY INTELLIGENCE ====================

@celery_app.task(name="tasks.score_wallets")
def score_wallets():
    """
    Periodic task: persist wallet aggregates + WalletScore snapshots for the
    copy-intelligence leaderboard (30d window).
    Runs every 15 minutes via Celery Beat.
    """
    from core.heartbeat import beat
    from services.copy.wallet_scoring import score_and_persist_wallets

    db = _get_db()
    try:
        result = score_and_persist_wallets(db)
        db.commit()
        beat("score_wallets")
        return {"status": "completed", **result}
    except Exception as exc:
        db.rollback()
        print(f"Failed to score wallets: {exc}")
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="tasks.record_shadow_trades")
def record_shadow_trades():
    """
    Periodic task: append shadow ExecutedTrade rows for active copy
    subscriptions from recent WalletActivity.
    Runs every 60 seconds via Celery Beat (15-min rescan window; the unique
    shadow signature makes reruns idempotent).
    """
    from core.heartbeat import beat
    from services.copy.shadow_recorder import record_shadow_trades as _record

    db = _get_db()
    try:
        result = _record(db)
        db.commit()
        beat("record_shadow_trades")
        return {"status": "completed", **result}
    except Exception as exc:
        db.rollback()
        print(f"Failed to record shadow trades: {exc}")
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


# ==================== EXECUTION ====================

@celery_app.task(name="tasks.refresh_sol_price")
def refresh_sol_price():
    """
    Periodic task: refresh the cached SOL/USD price.
    Runs every 60 seconds via Celery Beat.
    """
    from core.heartbeat import beat
    from services.execution.price_feed import refresh_sol_price as _refresh

    price = _refresh()
    beat("refresh_sol_price")
    if price is None:
        return {"status": "no_price"}
    return {"status": "completed", "sol_usd": price}


# ==================== TOKEN DISCOVERY ====================

@celery_app.task(name="tasks.discover_new_tokens")
def discover_new_tokens():
    """
    Periodic task: poll for new Pump.fun token launches.
    Runs every 60 seconds via Celery Beat.
    """
    import asyncio
    import os
    from core.heartbeat import beat
    from services.discovery.token_discovery import poll_new_tokens, process_discovered_tokens

    # Heartbeat on every scheduled execution (including disabled/no-op runs):
    # it answers "is beat firing this task", while /health/pipeline's data
    # freshness answers "is anything being found".
    beat("discover_new_tokens")

    if os.getenv("DISCOVERY_ENABLED", "true").lower() != "true":
        return {"status": "disabled"}

    loop = asyncio.new_event_loop()
    try:
        tokens = loop.run_until_complete(poll_new_tokens())
    finally:
        loop.close()

    if not tokens:
        return {"status": "no_new_tokens"}

    result = process_discovered_tokens(tokens)
    return {"status": "completed", **result}


@celery_app.task(name="tasks.track_new_token", bind=True, max_retries=2)
def track_new_token(self, mint_address: str):
    """
    Fetch metadata and create initial signal for a newly discovered token.
    """
    db = _get_db()
    try:
        from models.token import TokenSignal
        from services.discovery.webhook_handler import fetch_pump_fun_metadata_sync

        existing = db.query(TokenSignal).filter(
            TokenSignal.token_address == mint_address
        ).first()
        if existing:
            return {"status": "already_tracked"}

        metadata = fetch_pump_fun_metadata_sync(mint_address)

        signal = TokenSignal(
            token_address=mint_address,
            chain_id="solana",
            symbol=metadata.get("symbol", "UNKNOWN") if metadata else "UNKNOWN",
            name=metadata.get("name", "Unknown Token") if metadata else "Unknown Token",
            dev_wallet=metadata.get("creator") if metadata else None,
            has_graduated=metadata.get("complete", False) if metadata else False,
            market_cap=metadata.get("market_cap") if metadata else None,
            token_metadata=metadata,
            tier_level="ultra",
            scan_timestamp=datetime.now(timezone.utc),
            pair_created_at=datetime.now(timezone.utc),
            age_minutes=0.0,
            pump_fun_url=f"https://pump.fun/{mint_address}",
            total_holders=1,
            entity_adjusted_buyers=1,
            buys_5m=0,
            sells_5m=0,
            retention_5m=100,
            momentum_score=0,
            rug_risk_score=50,
            confidence_score=0,
        )
        db.add(signal)
        db.commit()
        return {"status": "created", "symbol": signal.symbol}

    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


# ==================== ALERTS ====================

@celery_app.task(name="tasks.send_email_digest")
def send_email_digest(frequency: str = "hourly"):
    """
    Periodic task: send batched email digest of alerts.
    Runs hourly via Celery Beat.
    """
    from core.heartbeat import beat
    from services.discovery.alert_service import send_digest_emails

    db = _get_db()
    try:
        count = send_digest_emails(db, frequency)
        beat("send_email_digest")
        return {"status": "completed", "emails_sent": count}
    except Exception as exc:
        db.rollback()
        print(f"Failed to send email digest: {exc}")
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="tasks.send_alert_email")
def send_alert_email(user_email: str, alert_data: dict):
    """
    Send a single instant alert email to a user.
    """
    from services.discovery.alert_service import send_email, build_alert_email_html

    symbol = alert_data.get("symbol", "UNKNOWN")
    subject = f"Forge Terminal Alert: {symbol} - Strong Signal Detected"
    body = build_alert_email_html(alert_data)

    success = send_email(user_email, subject, body)
    return {"status": "sent" if success else "failed", "email": user_email}
