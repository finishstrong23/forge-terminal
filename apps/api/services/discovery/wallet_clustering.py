"""
Wallet Clustering Service (ported verbatim from Pump.Fair)

Groups wallets by funding source for entity-adjusted buyer counts.
"""
from typing import Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from models.wallet import WalletActivity, WalletCluster

PROGRAM_ACCOUNTS = {
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1",
    "11111111111111111111111111111111",
}


def extract_wallet_from_event(event_data: Dict, is_buy: bool) -> Optional[str]:
    if is_buy:
        native_transfers = event_data.get("nativeTransfers", [])
        for transfer in native_transfers:
            from_account = transfer.get("fromUserAccount", "")
            amount = transfer.get("amount", 0)
            if amount > 10_000_000 and from_account not in PROGRAM_ACCOUNTS:
                return from_account

    token_transfers = event_data.get("tokenTransfers", [])
    for transfer in token_transfers:
        from_account = transfer.get("fromUserAccount", "")
        if from_account and from_account not in PROGRAM_ACCOUNTS:
            return from_account

    fee_payer = event_data.get("feePayer", "")
    if fee_payer and fee_payer not in PROGRAM_ACCOUNTS:
        return fee_payer

    return None


def record_wallet_activity(
    db: Session,
    wallet_address: str,
    token_address: str,
    activity_type: str,
    sol_amount: Optional[float],
    event_signature: Optional[str],
    timestamp: datetime,
) -> Optional[WalletActivity]:
    if not wallet_address or not token_address:
        return None

    if event_signature:
        existing = (
            db.query(WalletActivity)
            .filter(WalletActivity.event_signature == event_signature)
            .first()
        )
        if existing:
            return existing

    cluster_id = _get_wallet_cluster_id(db, wallet_address)

    activity = WalletActivity(
        wallet_address=wallet_address,
        token_address=token_address,
        activity_type=activity_type,
        sol_amount=sol_amount,
        event_signature=event_signature,
        cluster_id=cluster_id,
        timestamp=timestamp,
    )
    db.add(activity)
    db.flush()
    return activity


def _get_wallet_cluster_id(db: Session, wallet_address: str) -> Optional[str]:
    existing = (
        db.query(WalletActivity.cluster_id)
        .filter(
            WalletActivity.wallet_address == wallet_address,
            WalletActivity.cluster_id.isnot(None),
        )
        .first()
    )
    return existing[0] if existing else None


def assign_cluster(db: Session, wallet_address: str, funding_wallet: str) -> WalletCluster:
    cluster = (
        db.query(WalletCluster)
        .filter(WalletCluster.funding_wallet == funding_wallet)
        .first()
    )

    if not cluster:
        cluster = WalletCluster(funding_wallet=funding_wallet, wallet_count=1)
        db.add(cluster)
        db.flush()

    updated = (
        db.query(WalletActivity)
        .filter(
            WalletActivity.wallet_address == wallet_address,
            WalletActivity.cluster_id.is_(None),
        )
        .update({"cluster_id": cluster.id}, synchronize_session=False)
    )

    if updated > 0:
        cluster.wallet_count = (
            db.query(func.count(distinct(WalletActivity.wallet_address)))
            .filter(WalletActivity.cluster_id == cluster.id)
            .scalar()
            or 1
        )

    db.commit()
    return cluster


def recalculate_entity_adjusted_buyers(db: Session, token_address: str) -> int:
    clustered_entities = (
        db.query(func.count(distinct(WalletActivity.cluster_id)))
        .filter(
            WalletActivity.token_address == token_address,
            WalletActivity.activity_type == "buy",
            WalletActivity.cluster_id.isnot(None),
        )
        .scalar()
        or 0
    )

    unclustered_wallets = (
        db.query(func.count(distinct(WalletActivity.wallet_address)))
        .filter(
            WalletActivity.token_address == token_address,
            WalletActivity.activity_type == "buy",
            WalletActivity.cluster_id.is_(None),
        )
        .scalar()
        or 0
    )

    return max(clustered_entities + unclustered_wallets, 1)
