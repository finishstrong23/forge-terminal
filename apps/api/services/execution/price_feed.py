"""
SOL/USD price feed (M3, v1).

Two keyless sources, tried in order:
1. Jupiter price API (lite-api.jup.ag/price/v2)
2. CoinGecko simple price (fallback; aggressively rate-limited, so it only
   ever sees traffic when Jupiter is down)

The fetched price is Redis-cached for PRICE_TTL_SECONDS and refreshed by
tasks.refresh_sol_price on the beat schedule, so request paths normally hit
the cache. With Redis down every call fetches live (slower, still correct);
with both sources down get_sol_price_usd returns None and callers must
degrade explicitly (e.g. the shadow recorder skips USD-cap enforcement and
says so in the module docs).

Unblocks the USD risk caps stored on CopySubscription since Phase 2.
"""
import logging
from typing import Optional

import httpx

from core.redis_cache import cache

logger = logging.getLogger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"

JUPITER_PRICE_URL = f"https://lite-api.jup.ag/price/v2?ids={SOL_MINT}"
COINGECKO_PRICE_URL = (
    "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
)

PRICE_CACHE_KEY = "price:sol_usd"
PRICE_TTL_SECONDS = 90  # beat refreshes every 60s; TTL covers one missed run
HTTP_TIMEOUT_S = 5.0

TOKEN_PRICE_CACHE_PREFIX = "price:token_usd:"
TOKEN_PRICE_TTL_SECONDS = 60  # request-driven, no beat task; short and honest
TOKEN_PRICE_BATCH_LIMIT = 50  # Jupiter's documented ids-per-call ceiling


def fetch_sol_price_usd() -> Optional[float]:
    """Live fetch, Jupiter first then CoinGecko. None when both fail."""
    try:
        response = httpx.get(JUPITER_PRICE_URL, timeout=HTTP_TIMEOUT_S)
        response.raise_for_status()
        price = float(response.json()["data"][SOL_MINT]["price"])
        if price > 0:
            return price
    except Exception as exc:
        logger.warning("price_feed: Jupiter price fetch failed: %s", exc)

    try:
        response = httpx.get(COINGECKO_PRICE_URL, timeout=HTTP_TIMEOUT_S)
        response.raise_for_status()
        price = float(response.json()["solana"]["usd"])
        if price > 0:
            return price
    except Exception as exc:
        logger.warning("price_feed: CoinGecko price fetch failed: %s", exc)

    return None


def get_sol_price_usd() -> Optional[float]:
    """Cached price, fetching + caching on a miss. None when unavailable."""
    cached = cache.get(PRICE_CACHE_KEY)
    if isinstance(cached, (int, float)) and cached > 0:
        return float(cached)
    price = fetch_sol_price_usd()
    if price is not None:
        cache.set(PRICE_CACHE_KEY, price, ttl=PRICE_TTL_SECONDS)
    return price


def refresh_sol_price() -> Optional[float]:
    """Force-fetch and cache; the beat task's entry point."""
    price = fetch_sol_price_usd()
    if price is not None:
        cache.set(PRICE_CACHE_KEY, price, ttl=PRICE_TTL_SECONDS)
    return price


def fetch_token_prices_usd(mints: list[str]) -> dict[str, Optional[float]]:
    """Live batch fetch from Jupiter. Unknown/unlisted mints map to None;
    an unreachable API maps EVERY mint to None (callers show a dash)."""
    result: dict[str, Optional[float]] = {mint: None for mint in mints}
    for start in range(0, len(mints), TOKEN_PRICE_BATCH_LIMIT):
        batch = mints[start : start + TOKEN_PRICE_BATCH_LIMIT]
        try:
            response = httpx.get(
                f"https://lite-api.jup.ag/price/v2?ids={','.join(batch)}",
                timeout=HTTP_TIMEOUT_S,
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
        except Exception as exc:
            logger.warning("price_feed: Jupiter token-price fetch failed: %s", exc)
            continue
        for mint in batch:
            entry = data.get(mint)
            try:
                price = float(entry["price"]) if entry else None
            except (KeyError, TypeError, ValueError):
                price = None
            if price is not None and price > 0:
                result[mint] = price
    return result


def get_token_prices_usd(mints: list[str]) -> dict[str, Optional[float]]:
    """Cached per-mint token prices; misses are fetched in one batch.
    Deduplicates input; preserves None for anything unavailable."""
    unique = list(dict.fromkeys(mints))
    result: dict[str, Optional[float]] = {}
    misses: list[str] = []
    for mint in unique:
        cached = cache.get(TOKEN_PRICE_CACHE_PREFIX + mint)
        if isinstance(cached, (int, float)) and cached > 0:
            result[mint] = float(cached)
        else:
            misses.append(mint)
    if misses:
        fetched = fetch_token_prices_usd(misses)
        for mint, price in fetched.items():
            result[mint] = price
            if price is not None:
                cache.set(
                    TOKEN_PRICE_CACHE_PREFIX + mint, price,
                    ttl=TOKEN_PRICE_TTL_SECONDS,
                )
    return result
