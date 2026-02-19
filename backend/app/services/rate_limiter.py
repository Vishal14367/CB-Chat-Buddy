"""
In-memory rate limiter for Groq API usage tracking.
Tracks tokens per minute and requests per day with proactive throttling.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class RateLimitStatus:
    """Result of a rate limit check."""
    allowed: bool
    status: str  # "ok", "degraded", "cached_only", "blocked"
    message: Optional[str] = None


@dataclass
class RateLimitInfo:
    """Current rate limit usage statistics."""
    tokens_this_minute: int
    tpm_limit: int
    requests_today: int
    rpd_limit: int
    tpm_percent: float
    rpd_percent: float


class RateLimiter:
    """In-memory rate limiter with proactive throttling.

    Tracks:
    - Tokens per minute (TPM) — resets every 60 seconds
    - Requests per day (RPD) — resets at midnight UTC

    Throttling thresholds:
    - 80% daily: "degraded" status (show warning banner)
    - 95% daily: "cached_only" status (skip LLM, serve cached only)
    - 100%: "blocked" status (friendly message with wait time)
    """

    def __init__(self, tpm_limit: int = 30000, rpd_limit: int = 1000):
        self.tpm_limit = tpm_limit
        self.rpd_limit = rpd_limit

        self._tokens_this_minute = 0
        self._minute_start = time.time()
        self._requests_today = 0
        self._day_key = self._get_day_key()
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0

        # Minimum delay between requests (milliseconds)
        self._min_delay_ms = 100

    def _get_day_key(self) -> str:
        """Get current UTC date as string for daily counter."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_reset_counters(self):
        """Reset counters if minute/day has rolled over."""
        now = time.time()

        # Reset minute counter
        if now - self._minute_start >= 60:
            self._tokens_this_minute = 0
            self._minute_start = now

        # Reset daily counter
        current_day = self._get_day_key()
        if current_day != self._day_key:
            self._requests_today = 0
            self._day_key = current_day

    async def acquire(self) -> RateLimitStatus:
        """Check rate limits and enforce minimum delay between requests.

        Returns a RateLimitStatus indicating whether the request should proceed.
        """
        async with self._lock:
            self._maybe_reset_counters()

            daily_pct = (self._requests_today / self.rpd_limit) * 100 if self.rpd_limit > 0 else 0

            # Check if blocked (100% daily)
            if self._requests_today >= self.rpd_limit:
                hours_left = self._hours_until_midnight()
                if hours_left > 1:
                    wait_msg = f"in about {int(hours_left)} hours"
                else:
                    wait_msg = "tomorrow"
                return RateLimitStatus(
                    allowed=False,
                    status="blocked",
                    message=self._friendly_blocked_message(wait_msg)
                )

            # Check if cached_only (95% daily)
            if daily_pct >= 95:
                return RateLimitStatus(
                    allowed=False,
                    status="cached_only",
                    message=(
                        "Heads up — we're almost out of tokens for today! "
                        "I'm running on limited capacity right now.\n\n"
                        "Your tokens reset at **midnight UTC** (every 24 hours), "
                        "so full power will be back soon.\n\n"
                        "If you need help right now, our "
                        "[Discord community](https://discord.gg/codebasics) "
                        "is always active!"
                    )
                )

            # Enforce minimum delay between requests
            now = time.time()
            elapsed_ms = (now - self._last_request_time) * 1000
            if elapsed_ms < self._min_delay_ms:
                wait_s = (self._min_delay_ms - elapsed_ms) / 1000
                await asyncio.sleep(wait_s)

            self._last_request_time = time.time()
            self._requests_today += 1

            # Check if degraded (80% daily)
            if daily_pct >= 80:
                return RateLimitStatus(
                    allowed=True,
                    status="degraded",
                    message=None
                )

            return RateLimitStatus(allowed=True, status="ok")

    def record_usage(self, tokens_used: int):
        """Record token usage after a successful LLM call."""
        self._tokens_this_minute += tokens_used

    def get_status(self) -> dict:
        """Get current rate limit statistics."""
        self._maybe_reset_counters()
        return {
            "tokens_this_minute": self._tokens_this_minute,
            "tpm_limit": self.tpm_limit,
            "requests_today": self._requests_today,
            "rpd_limit": self.rpd_limit,
            "tpm_percent": round((self._tokens_this_minute / self.tpm_limit) * 100, 1) if self.tpm_limit > 0 else 0,
            "rpd_percent": round((self._requests_today / self.rpd_limit) * 100, 1) if self.rpd_limit > 0 else 0
        }

    def _hours_until_midnight(self) -> float:
        """Calculate hours until midnight UTC."""
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now > midnight:
            from datetime import timedelta
            midnight += timedelta(days=1)
        return (midnight - now).total_seconds() / 3600

    @staticmethod
    def _friendly_blocked_message(wait_time: str) -> str:
        """Generate a Peter-Pandey-styled rate limit message."""
        return (
            f"Hey! Looks like we've used up all the tokens for today "
            f"— you've been learning hard, and I respect that!\n\n"
            f"Your tokens reset every **24 hours** (midnight UTC), "
            f"so you'll be back in action **{wait_time}**.\n\n"
            f"**Pro tip for next session:** stick to focused, "
            f"lecture-specific questions — you'll get way more value "
            f"per token that way!\n\n"
            f"In the meantime, if you're stuck on something urgent, "
            f"our [Discord community](https://discord.gg/codebasics) "
            f"is always active and super helpful.\n\n"
            f"See you soon! 💪"
        )
