"""In-Memory Sliding Window Rate Limiter for FastAPI endpoints.

Protects backend public and webhook endpoints from request flooding and AI quota exhaustion.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List, Optional, Tuple


class RateLimitExceededError(Exception):
    """Raised when a client exceeds the allowed request rate."""

    def __init__(self, retry_after: int, message: str = "Rate limit exceeded. Please retry later."):
        super().__init__(message)
        self.retry_after = retry_after


class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, default_limit: int = 60, window_seconds: int = 60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(
        self,
        key: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> Tuple[bool, int, int]:
        """Check if request for given key is allowed under rate limit.

        Args:
            key: Rate limit bucket key (e.g. client IP or Zendesk subdomain).
            limit: Maximum requests allowed in window (defaults to self.default_limit).
            window: Sliding window duration in seconds (defaults to self.window_seconds).

        Returns:
            Tuple of (is_allowed: bool, remaining_requests: int, retry_after_seconds: int).
        """
        max_limit = limit or self.default_limit
        window_duration = window or self.window_seconds
        now = time.time()
        cutoff = now - window_duration

        with self._lock:
            timestamps = self._requests[key]
            # Remove timestamps outside sliding window
            valid_timestamps = [t for t in timestamps if t > cutoff]
            self._requests[key] = valid_timestamps

            if len(valid_timestamps) >= max_limit:
                oldest_timestamp = valid_timestamps[0]
                retry_after = max(1, int(window_duration - (now - oldest_timestamp)))
                return False, 0, retry_after

            # Allow request and append current timestamp
            valid_timestamps.append(now)
            remaining = max(0, max_limit - len(valid_timestamps))
            return True, remaining, 0

    def check(self, key: str, limit: Optional[int] = None, window: Optional[int] = None):
        """Check rate limit and raise RateLimitExceededError if exceeded."""
        allowed, _, retry_after = self.is_allowed(key, limit=limit, window=window)
        if not allowed:
            raise RateLimitExceededError(retry_after=retry_after)

    def clear(self):
        """Reset rate limiter state (used in tests)."""
        with self._lock:
            self._requests.clear()


# Default singleton instance (60 requests per minute)
_global_rate_limiter = SlidingWindowRateLimiter(default_limit=60, window_seconds=60)


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Retrieve singleton rate limiter instance."""
    return _global_rate_limiter
