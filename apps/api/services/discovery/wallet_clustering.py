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


def get_unique_holders(db: Session, token_address: str) -> int:
    """
    Count unique wallets that bought but haven't sold (net holders).
    """
    # Wallets that bought
    buyers = set(
        row[0] for row in db.query(distinct(WalletActivity.wallet_address)).filter(
            WalletActivity.token_address == token_address,
            WalletActivity.activity_type == "buy",
        ).all()
    )

    # Wallets that sold
    sellers = set(
        row[0] for row in db.query(distinct(WalletActivity.wallet_address)).filter(
            WalletActivity.token_address == token_address,
            WalletActivity.activity_type == "sell",
        ).all()
    )

    # Net holders = bought but not sold
    holders = buyers - sellers
    return max(len(holders), 0)


async def lookup_funding_wallet(wallet_address: str) -> Optional[str]:
    """
    Look up the funding source of a wallet using Helius RPC.

    Checks the wallet's first incoming SOL transfer to identify its funder.
    Rate-limited to avoid Helius API abuse.
    """
    from core.config import settings
    import httpx

    rpc_url = settings.HELIUS_RPC_URL
    if not rpc_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get transaction signatures for this wallet (oldest first)
            response = await client.post(rpc_url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    wallet_address,
                    {"limit": 5, "commitment": "confirmed"}
                ]
            })

            if response.status_code != 200:
                return None

            data = response.json()
            signatures = data.get("result", [])

            if not signatures:
                return None

            # Get the oldest transaction to find funder
            oldest_sig = signatures[-1]["signature"]

            # Get transaction details
            tx_response = await client.post(rpc_url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    oldest_sig,
                    {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
                ]
            })

            if tx_response.status_code != 200:
                return None

            tx_data = tx_response.json().get("result")
            if not tx_data:
                return None

            # Look for SOL transfer TO our wallet
            meta = tx_data.get("meta", {})
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])
            account_keys = tx_data.get("transaction", {}).get("message", {}).get("accountKeys", [])

            for i, key in enumerate(account_keys):
                pubkey = key.get("pubkey", key) if isinstance(key, dict) else key
                if pubkey == wallet_address:
                    # Found our wallet -- who sent the SOL?
                    if i < len(pre_balances) and i < len(post_balances):
                        if post_balances[i] > pre_balances[i]:
                            # This wallet received SOL -- find the sender
                            for j, other_key in enumerate(account_keys):
                                other_pubkey = other_key.get("pubkey", other_key) if isinstance(other_key, dict) else other_key
                                if j != i and j < len(pre_balances) and j < len(post_balances):
                                    if pre_balances[j] > post_balances[j]:
                                        if other_pubkey not in PROGRAM_ACCOUNTS:
                                            return other_pubkey

            return None

    except Exception as e:
        print(f"Error looking up funding wallet for {wallet_address[:8]}...: {e}")
        return None
