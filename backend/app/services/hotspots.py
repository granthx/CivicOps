"""Deterministic spatial-temporal hotspot clustering and chronic zone detection."""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..domain import (
    ACTIVE_INCIDENT_STATUSES,
    CATEGORY_LABELS,
    PRIORITY_ORDER,
    Category,
    IncidentStatus,
    Priority,
)
from ..models import Incident
from ..schemas import HotspotClusterOut, HotspotListOut
from ..utils import clamp, haversine_m, utcnow

_RECOMMENDATIONS: dict[str, str] = {
    Category.OVERFLOWING_BIN.value: "Recurring bin overflow zone — review bin capacity or increase collection frequency.",
    Category.ILLEGAL_DUMPING.value: "Chronic illegal dumping blackspot — consider signage, enforcement patrol, and scheduled clearance.",
    Category.GARBAGE_ACCUMULATION.value: "Persistent garbage accumulation site — schedule preventive street sweeping and container placement.",
    Category.MISSED_COLLECTION.value: "Repeated missed-collection corridor — audit route coverage and crew dispatch timing.",
    Category.DEAD_ANIMAL.value: "Repeated sanitation hazard reports — prioritise rapid response and inspect nearby waste points.",
    Category.OTHER_WASTE.value: "Recurring waste complaint zone — conduct ward supervisor site inspection.",
}


def _build_recommendation(
    category: str, incident_count: int, total_reports: int, radius_m: float
) -> str:
    base = _RECOMMENDATIONS.get(
        category,
        "Recurring waste hotspot — conduct ward supervisor inspection.",
    )
    label = CATEGORY_LABELS.get(category, "Waste issue").lower()
    return (
        f"{incident_count} incidents ({total_reports} reports) within "
        f"{int(radius_m)}m for {label}. {base}"
    )


def get_hotspot_context(
    db: Session,
    *,
    latitude: float,
    longitude: float,
    exclude_incident_id: int | None = None,
    now: datetime | None = None,
) -> tuple[bool, int, str]:
    """Check whether a coordinate falls inside an active spatial-temporal hotspot."""
    now = now or utcnow()
    cutoff = now - timedelta(days=settings.hotspot_window_days)
    radius = settings.hotspot_radius_m

    lat_delta = radius / 111_320.0
    cos_lat = max(0.01, math.cos(math.radians(latitude)))
    lon_delta = radius / (111_320.0 * cos_lat)

    query = select(Incident).where(
        Incident.status != IncidentStatus.MERGED.value,
        Incident.merged_into_id.is_(None),
        Incident.created_at >= cutoff,
        Incident.latitude.between(latitude - lat_delta, latitude + lat_delta),
        Incident.longitude.between(longitude - lon_delta, longitude + lon_delta),
    )
    if exclude_incident_id is not None:
        query = query.where(Incident.id != exclude_incident_id)

    candidates = list(db.scalars(query).all())
    nearby_count = sum(
        1
        for candidate in candidates
        if haversine_m(latitude, longitude, candidate.latitude, candidate.longitude)
        <= radius
    )
    threshold = max(1, settings.hotspot_min_incidents - 1)
    in_hotspot = nearby_count >= threshold
    if in_hotspot:
        explanation = (
            f"Located within {int(radius)}m of {nearby_count} other "
            f"incident{'s' if nearby_count != 1 else ''} in the last "
            f"{settings.hotspot_window_days} days."
        )
    else:
        explanation = (
            f"Not in a recurring cluster ({nearby_count} nearby incident"
            f"{'s' if nearby_count != 1 else ''} within {int(radius)}m)."
        )
    return in_hotspot, nearby_count, explanation


def detect_hotspot_clusters(
    db: Session,
    *,
    window_days: int | None = None,
    radius_m: float | None = None,
    ward_id: int | None = None,
    now: datetime | None = None,
) -> HotspotListOut:
    """Group nearby incidents into deterministic spatial-temporal hotspot clusters."""
    now = now or utcnow()
    effective_window = window_days if window_days is not None else settings.hotspot_window_days
    effective_radius = radius_m if radius_m is not None else settings.hotspot_radius_m
    cutoff = now - timedelta(days=effective_window)

    query = (
        select(Incident)
        .where(
            Incident.status != IncidentStatus.MERGED.value,
            Incident.merged_into_id.is_(None),
            Incident.created_at >= cutoff,
        )
        .options(selectinload(Incident.ward), selectinload(Incident.reports))
        .order_by(Incident.id.asc())
    )
    if ward_id is not None:
        query = query.where(Incident.ward_id == ward_id)

    incidents = list(db.scalars(query).all())
    n = len(incidents)
    raw_clusters: list[list[Incident]] = []
    if n > 0:
        # Spatial grid-bucket index: cell size >= effective_radius in both axes
        # so any neighbor within effective_radius is guaranteed to be in the 3x3 cells.
        lat_step = max(1e-7, effective_radius / 110_574.0)
        max_abs_lat = max(abs(inc.latitude) for inc in incidents)
        cos_lat = max(0.01, math.cos(math.radians(min(89.0, max_abs_lat))))
        lon_step = max(1e-7, effective_radius / (111_320.0 * cos_lat))

        grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        cells: list[tuple[int, int]] = []
        for idx, inc in enumerate(incidents):
            cell = (
                math.floor(inc.latitude / lat_step),
                math.floor(inc.longitude / lon_step),
            )
            cells.append(cell)
            grid[cell].append(idx)

        visited = [False] * n
        for start in range(n):
            if visited[start]:
                continue
            visited[start] = True
            queue: deque[int] = deque([start])
            component: list[Incident] = []
            while queue:
                idx = queue.popleft()
                inc = incidents[idx]
                component.append(inc)
                row, col = cells[idx]
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        for nxt in grid.get((row + dr, col + dc), ()):
                            if visited[nxt]:
                                continue
                            other = incidents[nxt]
                            if (
                                haversine_m(
                                    inc.latitude,
                                    inc.longitude,
                                    other.latitude,
                                    other.longitude,
                                )
                                <= effective_radius
                            ):
                                visited[nxt] = True
                                queue.append(nxt)
            total_reports = sum(max(1, len(item.reports)) for item in component)
            if len(component) >= settings.hotspot_min_incidents or total_reports >= 3:
                raw_clusters.append(component)

    clusters: list[HotspotClusterOut] = []
    for component in raw_clusters:
        incident_count = len(component)
        active_count = sum(
            1 for item in component if item.status in ACTIVE_INCIDENT_STATUSES
        )
        total_reports = sum(max(1, len(item.reports)) for item in component)
        centroid_lat = round(sum(item.latitude for item in component) / incident_count, 6)
        centroid_lon = round(sum(item.longitude for item in component) / incident_count, 6)
        ward_name = Counter(
            item.ward.name for item in component if item.ward is not None
        ).most_common(1)[0][0]
        top_category = Counter(item.category for item in component).most_common(1)[0][0]
        max_priority = max(
            (item.priority for item in component),
            key=lambda p: PRIORITY_ORDER.get(p, 0),
            default=Priority.MEDIUM.value,
        )
        chronic_score = round(
            clamp(
                incident_count * 22.0 + total_reports * 8.0 + active_count * 10.0,
                0.0,
                100.0,
            ),
            1,
        )
        latest_at = max(item.created_at for item in component)
        recommendation = _build_recommendation(
            top_category, incident_count, total_reports, effective_radius
        )
        clusters.append(
            HotspotClusterOut(
                cluster_id="",
                latitude=centroid_lat,
                longitude=centroid_lon,
                radius_m=effective_radius,
                ward_name=ward_name,
                incident_count=incident_count,
                active_incident_count=active_count,
                total_reports=total_reports,
                top_category=Category(top_category),
                max_priority=Priority(max_priority),
                chronic_score=chronic_score,
                is_chronic=True,
                recommendation=recommendation,
                incident_ids=[item.id for item in component],
                public_ids=[item.public_id for item in component],
                latest_incident_at=latest_at,
            )
        )

    clusters.sort(
        key=lambda c: (
            c.chronic_score,
            c.active_incident_count,
            c.total_reports,
            c.latest_incident_at,
        ),
        reverse=True,
    )
    for idx, cluster in enumerate(clusters, start=1):
        cluster.cluster_id = f"HS-{idx:02d}"

    return HotspotListOut(
        generated_at=now,
        window_days=effective_window,
        radius_m=effective_radius,
        clusters=clusters,
    )

