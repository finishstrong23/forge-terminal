"""
Manual-trade confirmation checker (M3c).

Recorded manual swaps land as status="submitted" (client-reported, see
routes/execute.py). This beat task resolves them against the chain via a
single batched getSignatureStatuses RPC call:

- finalized/confirmed with no error  -> status "confirmed"
- landed with an error               -> status "failed" (+ error message)
- unknown after EXPIRY_MINUTES       -> status "failed" ("not found on
  chain" — the blockhash expired, the transaction can never land)
- unknown but younger than that     -> left as "submitted" for next run

RPC endpoint precedence: SOLANA_RPC_URL, then HELIUS_RPC_URL, then the
public mainnet endpoint (rate-limited; fine for one batched call/minute).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from models.trade import ExecutedTrade

logger = logging.getLogger(__name__)

PUBLIC_RPC_URL = "https://api.mainnet-beta.solana.com"
HTTP_TIMEOUT_S = 8.0
BATCH_LIMIT = 100  # getSignatureStatuses max batch size is 256; stay modest
EXPIRY_MINUTES = 15


def _rpc_url() -> str:
    return (
        getattr(settings, "SOLANA_RPC_URL", None)
        or settings.HELIUS_RPC_URL
        or PUBLIC_RPC_URL
    )


def fetch_signature_statuses(signatures: List[str]) -> Optional[List[Optional[Dict[str, Any]]]]:
    """One batched getSignatureStatuses call. None on RPC failure."""
    if not signatures:
        return []
    try:
        response = httpx.post(
            _rpc_url(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignatureStatuses",
                "params": [signatures, {"searchTransactionHistory": True}],
            },
            timeout=HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return response.json()["result"]["value"]
    except Exception as exc:
        logger.warning("confirmations: getSignatureStatuses failed: %s", exc)
        return None


def check_pending_trades(db: Session) -> Dict[str, int]:
    """Resolve submitted manual trades. Caller owns the transaction."""
    pending = (
        db.query(ExecutedTrade)
        .filter(
            ExecutedTrade.source == "manual",
            ExecutedTrade.status == "submitted",
            ExecutedTrade.signature.isnot(None),
        )
        .order_by(ExecutedTrade.created_at.asc())
        .limit(BATCH_LIMIT)
        .all()
    )
    if not pending:
        return {"pending": 0, "confirmed": 0, "failed": 0}

    statuses = fetch_signature_statuses([t.signature for t in pending])
    if statuses is None:
        # RPC down — try again next run, everything stays submitted.
        return {"pending": len(pending), "confirmed": 0, "failed": 0}

    now = datetime.now(timezone.utc)
    expiry_cutoff = now - timedelta(minutes=EXPIRY_MINUTES)
    confirmed = failed = 0
    for trade, status in zip(pending, statuses):
        if status is None:
            created = trade.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created is not None and created < expiry_cutoff:
                trade.status = "failed"
                trade.error_message = "not found on chain (blockhash expired)"
                failed += 1
            continue
        if status.get("err"):
            trade.status = "failed"
            trade.error_message = f"on-chain error: {status['err']}"
            failed += 1
        elif status.get("confirmationStatus") in {"confirmed", "finalized"}:
            trade.status = "confirmed"
            trade.error_message = None
            confirmed += 1
        # "processed" -> leave submitted; next run will see it deeper.

    db.flush()
    if confirmed or failed:
        logger.info(
            "confirmations: %d confirmed, %d failed of %d pending",
            confirmed, failed, len(pending),
        )
    return {"pending": len(pending), "confirmed": confirmed, "failed": failed}
