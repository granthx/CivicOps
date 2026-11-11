"""Small shared utilities."""

from __future__ import annotations

import math
import secrets
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC timestamp for SQLite portability."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_public_id(prefix: str) -> str:
    year = datetime.now(UTC).year
    return f"{prefix}-{year}-{secrets.token_hex(4).upper()}"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two WGS84 coordinates."""
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))
