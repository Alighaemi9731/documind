"""In-process per-key rate limiter (base profile, no Redis).

A fixed-window counter keyed by ``(bucket, key)`` — e.g. per-IP on
``/register`` and ``/login`` to blunt brute-force. Distributed limiting lands
behind the opt-in ``worker`` profile (Redis) later; this is intentionally
simple and process-local.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Window:
    count: int = 0
    reset_at: float = 0.0


@dataclass
class RateLimiter:
    """Fixed-window limiter. Not safe across processes (single uvicorn worker)."""

    max_attempts: int = 10
    window_seconds: float = 60.0
    _buckets: dict[str, _Window] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self, key: str) -> bool:
        """Record an attempt for ``key``; return False once over the limit."""
        now = time.monotonic()
        with self._lock:
            window = self._buckets.get(key)
            if window is None or now >= window.reset_at:
                window = _Window(count=0, reset_at=now + self.window_seconds)
                self._buckets[key] = window
            window.count += 1
            return window.count <= self.max_attempts

    def reset(self, key: str) -> None:
        """Clear a key's counter (e.g. after a successful login)."""
        with self._lock:
            self._buckets.pop(key, None)


# Module-level limiters used by the auth routes. Login is limited per-IP AND
# per-email so a single account can't be brute-forced from many IPs. Counters
# are NOT reset on success (a lucky guess must not clear the failure window).
login_limiter = RateLimiter(max_attempts=10, window_seconds=300.0)
login_email_limiter = RateLimiter(max_attempts=10, window_seconds=900.0)
register_limiter = RateLimiter(max_attempts=20, window_seconds=3600.0)


__all__ = [
    "RateLimiter",
    "login_limiter",
    "login_email_limiter",
    "register_limiter",
]
