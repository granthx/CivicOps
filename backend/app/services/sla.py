"""Deterministic SLA deadline and escalation status computation."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..domain import IncidentStatus, Priority, WorkOrderStatus
from ..models import User, WorkOrder
from ..schemas import SlaStatusOut, SlaSweepOut
from ..utils import utcnow
from .audit import record_audit
from .notifications import dispatch_sla_escalation_alert

_SLA_HOURS_BY_PRIORITY: dict[str, int] = {
    Priority.CRITICAL.value: settings.sla_hours_critical,
    Priority.HIGH.value: settings.sla_hours_high,
    Priority.MEDIUM.value: settings.sla_hours_medium,
    Priority.LOW.value: settings.sla_hours_low,
}


def sla_hours_for_priority(priority: str) -> int:
    return _SLA_HOURS_BY_PRIORITY.get(priority, settings.sla_hours_medium)


def default_sla_due_at(created_at: datetime, priority: str) -> datetime:
    return created_at + timedelta(hours=sla_hours_for_priority(priority))


def compute_sla_status(
    *,
    created_at: datetime,
    due_at: datetime | None,
    priority: str,
    status: str,
    verified_at: datetime | None = None,
    now: datetime | None = None,
) -> SlaStatusOut:
    """Compute transparent SLA compliance state for an incident or work order."""
    now = now or utcnow()
    effective_due = due_at or default_sla_due_at(created_at, priority)
    total_seconds = max(1.0, (effective_due - created_at).total_seconds())

    if status in {IncidentStatus.VERIFIED.value, WorkOrderStatus.VERIFIED.value}:
        closed_at = verified_at or now
        remaining = round((effective_due - closed_at).total_seconds() / 3600, 1)
        is_overdue = closed_at > effective_due
        return SlaStatusOut(
            sla_state="breached" if is_overdue else "met",
            due_at=effective_due,
            remaining_hours=remaining,
            is_overdue=is_overdue,
        )

    remaining_seconds = (effective_due - now).total_seconds()
    remaining_hours = round(remaining_seconds / 3600, 1)
    if remaining_seconds <= 0:
        return SlaStatusOut(
            sla_state="breached",
            due_at=effective_due,
            remaining_hours=remaining_hours,
            is_overdue=True,
        )

    elapsed_ratio = (now - created_at).total_seconds() / total_seconds
    if elapsed_ratio >= settings.sla_warning_ratio:
        sla_state = "at_risk"
    else:
        sla_state = "on_track"

    return SlaStatusOut(
        sla_state=sla_state,
        due_at=effective_due,
        remaining_hours=remaining_hours,
        is_overdue=False,
    )


def sweep_sla_escalations(
    db: Session,
    *,
    actor: User | None = None,
    now: datetime | None = None,
) -> SlaSweepOut:
    """Idempotently mark newly breached active work orders and record audit events."""
    now = now or utcnow()
    active_orders = list(
        db.scalars(
            select(WorkOrder)
            .where(
                WorkOrder.status != WorkOrderStatus.VERIFIED.value,
                WorkOrder.sla_escalated_at.is_(None),
            )
            .options(selectinload(WorkOrder.incident), selectinload(WorkOrder.team))
        ).all()
    )
    escalated_ids: list[str] = []
    pending_alerts: list[dict] = []
    for order in active_orders:
        if order.incident is None:
            continue
        sla = compute_sla_status(
            created_at=order.created_at,
            due_at=order.due_at,
            priority=order.incident.priority,
            status=order.status,
            verified_at=order.verified_at,
            now=now,
        )
        if sla.sla_state == "breached":
            order.sla_escalated_at = now
            db.add(order)
            escalated_ids.append(order.public_id)
            team_name = order.team.name if order.team else "crew"
            ward_name = order.incident.ward.name if order.incident.ward else "unknown"
            record_audit(
                db,
                action="sla_breach_escalated",
                entity_type="incident",
                entity_id=order.incident_id,
                actor=actor,
                actor_role=actor.role if actor else "system",
                actor_name=actor.name if actor else "SLA escalation sweep",
                old_status=order.incident.status,
                new_status=order.incident.status,
                note=(
                    f"Work order {order.public_id} ({team_name}) "
                    f"exceeded SLA deadline ({abs(sla.remaining_hours):.1f}h overdue)."
                ),
                metadata={
                    "work_order_public_id": order.public_id,
                    "due_at": sla.due_at.isoformat(),
                    "remaining_hours": sla.remaining_hours,
                },
            )
            pending_alerts.append(
                {
                    "work_order_public_id": order.public_id,
                    "incident_public_id": order.incident.public_id,
                    "ward_name": ward_name,
                    "team_name": team_name,
                    "remaining_hours": sla.remaining_hours,
                }
            )
    if escalated_ids:
        db.commit()
        for alert in pending_alerts:
            dispatch_sla_escalation_alert(**alert)
    return SlaSweepOut(
        swept_at=now,
        escalated_count=len(escalated_ids),
        escalated_work_order_public_ids=escalated_ids,
    )

