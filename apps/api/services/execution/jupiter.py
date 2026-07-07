"""
Jupiter quote client (M3, v1 — quotes only).

Wraps Jupiter's v6 quote API for the Execute page's swap ticket. Swap
transaction building (POST /swap) lands with the wallet-connect increment;
quoting is read-only and needs no keys.
"""
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
HTTP_TIMEOUT_S = 8.0


class JupiterUnavailable(RuntimeError):
    """Jupiter didn't answer usefully — callers map this to a 503."""


def get_quote(
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 100,
) -> Dict[str, Any]:
    """
    Fetch a swap quote. `amount_raw` is in the input token's base units
    (lamports for SOL). Raises JupiterUnavailable on network/API failure.
    """
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "slippageBps": str(slippage_bps),
    }
    try:
        response = httpx.get(JUPITER_QUOTE_URL, params=params, timeout=HTTP_TIMEOUT_S)
        response.raise_for_status()
        quote = response.json()
    except Exception as exc:
        logger.warning("jupiter: quote fetch failed: %s", exc)
        raise JupiterUnavailable(f"Jupiter quote unavailable: {exc}") from exc

    if not isinstance(quote, dict) or "outAmount" not in quote:
        raise JupiterUnavailable("Jupiter returned an unexpected quote payload")
    return quote


def get_swap_transaction(
    quote_response: Dict[str, Any],
    user_public_key: str,
    priority_fee_lamports: int = 0,
) -> Dict[str, Any]:
    """
    Build an unsigned swap transaction from a full quote payload. The
    server never sees a private key — the returned base64 transaction is
    signed client-side by the user's wallet.
    """
    body: Dict[str, Any] = {
        "quoteResponse": quote_response,
        "userPublicKey": user_public_key,
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
    }
    if priority_fee_lamports > 0:
        body["prioritizationFeeLamports"] = priority_fee_lamports
    try:
        response = httpx.post(JUPITER_SWAP_URL, json=body, timeout=HTTP_TIMEOUT_S)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("jupiter: swap build failed: %s", exc)
        raise JupiterUnavailable(f"Jupiter swap unavailable: {exc}") from exc

    if not isinstance(payload, dict) or "swapTransaction" not in payload:
        raise JupiterUnavailable("Jupiter returned an unexpected swap payload")
    return payload
