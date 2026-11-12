"""Transparent, deterministic incident priority rules."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..config import settings
from ..domain import SEVERITY_ORDER, Priority, Severity
from ..models import CitizenReport, Incident
from ..utils import clamp, utcnow

SEVERITY_POINTS = {
    Severity.LOW.value: settings.priority_weight_low,
    Severity.MODERATE.value: settings.priority_weight_moderate,
    Severity.HIGH.value: settings.priority_weight_high,
    Severity.CRITICAL.value: settings.priority_weight_critical,
}


def _priority_from_score(score: float) -> Priority:
    if score >= settings.priority_threshold_critical:
        return Priority.CRITICAL
    if score >= settings.priority_threshold_high:
        return Priority.HIGH
    if score >= settings.priority_threshold_medium:
        return Priority.MEDIUM
    return Priority.LOW


def calculate_priority(
    reports: list[CitizenReport],
    *,
    now: datetime | None = None,
    hotspot_context: tuple[bool, int, str] | None = None,
) -> dict[str, Any]:
    """Calculate a 0-100 advisory score from documented, observable factors.

    The score is not a scientifically validated risk model. It is a municipal
    triage aid that an operator may override with a recorded reason.
    """
    now = now or utcnow()
    if not reports:
        reports = []

    severity = max(
        (report.ai_severity or Severity.MODERATE.value for report in reports),
        key=lambda value: SEVERITY_ORDER.get(value, 1),
        default=Severity.MODERATE.value,
    )
    severity_points = SEVERITY_POINTS.get(
        severity, settings.priority_weight_moderate
    )

    report_count = max(1, len(reports))
    recurrence_points = clamp(
        (report_count - 1) * settings.priority_recurrence_step,
        0.0,
        settings.priority_recurrence_cap,
    )

    oldest = min((report.created_at for report in reports), default=now)
    age_hours = max(0.0, (now - oldest).total_seconds() / 3600)
    age_ratio = (
        age_hours / settings.priority_age_cap_hours
        if settings.priority_age_cap_hours > 0
        else 1.0
    )
    age_points = clamp(
        age_ratio * settings.priority_age_points_cap,
        0.0,
        settings.priority_age_points_cap,
    )

    in_hotspot, _nearby_count, hotspot_explanation = (
        hotspot_context
        if hotspot_context is not None
        else (False, 0, "Spatial hotspot context not evaluated.")
    )
    hotspot_points = settings.priority_hotspot_boost if in_hotspot else 0.0

    score = round(
        clamp(severity_points + recurrence_points + age_points + hotspot_points, 0.0, 100.0),
        1,
    )
    priority = _priority_from_score(score)
    generated_at = now.isoformat(timespec="seconds") + "Z"

    factors: list[dict[str, Any]] = [
        {
            "label": "Severity",
            "points": round(severity_points, 1),
            "max_points": settings.priority_weight_critical,
            "explanation": f"Highest assessed severity is {severity}.",
        },
        {
            "label": "Recurrence",
            "points": round(recurrence_points, 1),
            "max_points": settings.priority_recurrence_cap,
            "explanation": (
                f"{report_count} linked report"
                f"{'s' if report_count != 1 else ''} at this incident."
            ),
        },
        {
            "label": "Age",
            "points": round(age_points, 1),
            "max_points": settings.priority_age_points_cap,
            "explanation": (
                f"Oldest linked report is {age_hours:.1f} hours old "
                f"(capped at {settings.priority_age_cap_hours:.0f} hours)."
            ),
        },
    ]
    if hotspot_context is not None:
        factors.append(
            {
                "label": "Hotspot",
                "points": round(hotspot_points, 1),
                "max_points": settings.priority_hotspot_boost,
                "explanation": hotspot_explanation,
            }
        )

    return {
        "score": score,
        "priority": priority.value,
        "factors": factors,
        "generated_at": generated_at,
        "model": "civicops-priority-v1",
        "disclaimer": (
            "Deterministic triage aid, not a validated risk score. "
            "An operator must review and may override it."
        ),
    }


def apply_priority(
    incident: Incident,
    reports: list[CitizenReport],
    *,
    now: datetime | None = None,
    hotspot_context: tuple[bool, int, str] | None = None,
) -> None:
    result = calculate_priority(reports, now=now, hotspot_context=hotspot_context)
    incident.priority_score = result["score"]
    incident.recommended_priority = result["priority"]
    incident.priority_factors = result
    incident.severity = max(
        (report.ai_severity or Severity.MODERATE.value for report in reports),
        key=lambda value: SEVERITY_ORDER.get(value, 1),
        default=incident.severity,
    )
    if not incident.priority_overridden:
        incident.priority = result["priority"]
