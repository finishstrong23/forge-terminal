"""
Pump.fun API Rate Limiter
===========================

Shared rate limiter for all Pump.fun API calls. Prevents Cloudflare bans
by enforcing:
- Minimum 10 seconds between requests
- Max 3 requests per minute
- 5-minute cooldown after rate limit hit
- 15-minute cooldown after Cloudflare block

Used by webhook_handler.py and token_discovery.py.
"""
import time
from typing import Optional


PUMP_FUN_MIN_INTERVAL = 10     # seconds between requests
PUMP_FUN_MAX_PER_MINUTE = 3    # max requests per minute
PUMP_FUN_COOLDOWN = 300        # 5-minute cooldown after rate limit
PUMP_FUN_CLOUDFLARE_COOLDOWN = 900  # 15-minute cooldown after CF block


class PumpFunRateLimiter:
    """
    Rate limiter for Pump.fun API calls.
    Thread-safe for single-process use. For multi-process (Celery workers),
    state should ideally be in Redis -- this is a future enhancement.
    """

    def __init__(self):
        self._last_request: float = 0
        self._request_count: int = 0
        self._minute_start: float = time.time()
        self._disabled: bool = False
        self._disabled_until: float = 0

    def can_call(self) -> bool:
        """Check if we can make a Pump.fun API call."""
        now = time.time()

        # Check if disabled (cooldown active)
        if self._disabled:
            if now < self._disabled_until:
                return False
            self._disabled = False

        # Reset minute counter if a minute has passed
        if now - self._minute_start > 60:
            self._request_count = 0
            self._minute_start = now

        # Check per-minute limit
        if self._request_count >= PUMP_FUN_MAX_PER_MINUTE:
            return False

        # Check minimum interval between requests
        if now - self._last_request < PUMP_FUN_MIN_INTERVAL:
            return False

        return True

    def record_request(self):
        """Record that a request was made."""
        self._last_request = time.time()
        self._request_count += 1

    def disable(self, duration: int = PUMP_FUN_COOLDOWN):
        """Temporarily disable API calls after rate limit hit."""
        self._disabled = True
        self._disabled_until = time.time() + duration
        print(f"Pump.fun API disabled for {duration}s due to rate limiting")

    def disable_cloudflare(self):
        """Longer cooldown after Cloudflare block."""
        self.disable(PUMP_FUN_CLOUDFLARE_COOLDOWN)

    @property
    def status(self) -> dict:
        """Return current rate limiter status."""
        now = time.time()
        return {
            "disabled": self._disabled,
            "disabled_remaining_seconds": max(0, int(self._disabled_until - now)) if self._disabled else 0,
            "requests_this_minute": self._request_count,
            "max_per_minute": PUMP_FUN_MAX_PER_MINUTE,
            "seconds_since_last_request": int(now - self._last_request) if self._last_request > 0 else None,
        }


# Singleton instance shared across the process
rate_limiter = PumpFunRateLimiter()
