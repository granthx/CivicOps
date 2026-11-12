"""In-process fixed-window rate limiting for the public intake endpoint.

This is intentionally simple for the MVP. It is per-process and resets on
restart; production deployments should use a shared Redis-backed limiter.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from ..errors import AppError

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()
WINDOW_SECONDS = 3600


def _enforce_bucket(bucket_key: str, limit: int, message: str) -> None:
    now = time.time()
    cutoff = now - WINDOW_SECONDS
    with _lock:
        values = [stamp for stamp in _buckets[bucket_key] if stamp >= cutoff]
        if len(values) >= limit:
            _buckets[bucket_key] = values
            raise AppError(429, message, "rate_limited")
        values.append(now)
        _buckets[bucket_key] = values


def enforce_report_rate_limit(client_key: str, limit: int) -> None:
    _enforce_bucket(
        f"report:{client_key}",
        limit,
        "Too many reports from this connection. Please try again later.",
    )


def enforce_chat_rate_limit(client_key: str, limit: int) -> None:
    _enforce_bucket(
        f"chat:{client_key}",
        limit,
        "Too many chat requests from this connection. Please try again later.",
    )


def clear_rate_limits() -> None:
    """Test helper."""
    with _lock:
        _buckets.clear()
