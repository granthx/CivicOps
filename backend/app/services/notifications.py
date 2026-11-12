"""Outbound notification adapter for SLA escalations (optional webhook)."""

from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def dispatch_sla_escalation_alert(
    *,
    work_order_public_id: str,
    incident_public_id: str,
    ward_name: str,
    team_name: str,
    remaining_hours: float,
) -> bool:
    """Send an SLA breach notification to the configured webhook, if any.

    Failures are logged and never roll back persisted SLA escalations.
    """
    if not settings.alert_webhook_url:
        return False

    payload = {
        "event": "sla_breach_escalated",
        "work_order_public_id": work_order_public_id,
        "incident_public_id": incident_public_id,
        "ward": ward_name,
        "team": team_name,
        "overdue_hours": round(abs(remaining_hours), 1),
    }
    try:
        response = httpx.post(settings.alert_webhook_url, json=payload, timeout=5.0)
        if response.status_code >= 400:
            logger.warning(
                "SLA alert webhook returned HTTP %s for %s",
                response.status_code,
                work_order_public_id,
            )
            return False
        return True
    except Exception as exc:
        logger.warning(
            "SLA alert webhook failed for %s: %s",
            work_order_public_id,
            type(exc).__name__,
        )
        return False

