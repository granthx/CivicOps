"""Layered, explainable duplicate suggestions.

No suggestion is ever auto-accepted. A human operator confirms or rejects each
candidate, and every source report remains intact.
"""

from __future__ import annotations

import math
import re
from datetime import timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..domain import DuplicateStatus
from ..models import CitizenReport, DuplicateCandidate
from ..utils import haversine_m, utcnow

_WORD_RE = re.compile(r"[^a-z0-9\s]")


def _normalized_text(value: str) -> str:
    return " ".join(_WORD_RE.sub(" ", value.lower()).split())


def _confidence_label(score: float) -> str:
    if score >= 75:
        return "strong candidate"
    if score >= 55:
        return "possible duplicate"
    return "weak candidate"


def suggest_duplicates(
    db: Session,
    report: CitizenReport,
    *,
    now=None,
) -> list[DuplicateCandidate]:
    now = now or utcnow()
    cutoff = now - timedelta(hours=settings.duplicate_window_hours)
    radius = settings.duplicate_radius_m

    lat_delta = radius / 111_320.0
    cos_lat = max(0.01, math.cos(math.radians(report.latitude)))
    lon_delta = radius / (111_320.0 * cos_lat)

    query = select(CitizenReport).where(
        CitizenReport.id != report.id,
        CitizenReport.created_at >= cutoff,
        CitizenReport.latitude.between(report.latitude - lat_delta, report.latitude + lat_delta),
        CitizenReport.longitude.between(
            report.longitude - lon_delta, report.longitude + lon_delta
        ),
    )
    candidates = list(db.scalars(query).all())
    existing = set(
        db.scalars(
            select(DuplicateCandidate.candidate_report_id).where(
                DuplicateCandidate.report_id == report.id
            )
        ).all()
    )

    report_category = report.ai_category or report.submitted_category or "other_waste"
    report_text = _normalized_text(report.description)
    scored: list[tuple[float, CitizenReport, float, list[str]]] = []

    for candidate in candidates:
        if candidate.id in existing:
            continue
        if report.incident_id and candidate.incident_id == report.incident_id:
            continue

        distance = haversine_m(
            report.latitude, report.longitude, candidate.latitude, candidate.longitude
        )
        if distance > radius:
            continue

        proximity_points = 45.0 * max(0.0, 1.0 - (distance / radius))
        candidate_category = (
            candidate.ai_category or candidate.submitted_category or "other_waste"
        )
        category_points = 20.0 if report_category == candidate_category else 0.0
        text_ratio = SequenceMatcher(
            None, report_text, _normalized_text(candidate.description)
        ).ratio()
        text_points = 25.0 * text_ratio
        age_hours = max(0.0, (now - candidate.created_at).total_seconds() / 3600)
        recency_points = 10.0 * max(
            0.0, 1.0 - (age_hours / settings.duplicate_window_hours)
        )
        score = round(
            proximity_points + category_points + text_points + recency_points, 1
        )
        if score < settings.duplicate_min_score:
            continue

        reasons = [
            f"{distance:.0f} m apart, within the {radius:.0f} m search radius.",
            (
                f"Same suggested category ({report_category.replace('_', ' ')})."
                if category_points
                else "Different suggested categories; a human must verify."
            ),
            f"{text_ratio * 100:.0f}% description similarity.",
            f"Reported {age_hours:.1f} hours apart ({_confidence_label(score)}).",
        ]
        scored.append((score, candidate, distance, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)
    results: list[DuplicateCandidate] = []
    for score, candidate, distance, reasons in scored[: settings.duplicate_max_results]:
        suggestion = DuplicateCandidate(
            report_id=report.id,
            candidate_report_id=candidate.id,
            candidate_incident_id=candidate.incident_id,
            score=score,
            distance_m=round(distance, 1),
            reasons=reasons,
            status=DuplicateStatus.SUGGESTED.value,
        )
        db.add(suggestion)
        results.append(suggestion)
    return results
