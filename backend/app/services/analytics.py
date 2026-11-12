"""Operational metrics computed from persisted records."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..domain import (
    ACTIVE_INCIDENT_STATUSES,
    CATEGORY_LABELS,
    PRIORITY_ORDER,
    DuplicateStatus,
    IncidentStatus,
)
from ..models import CitizenReport, DuplicateCandidate, Incident, Ward, WorkOrder
from ..schemas import AnalyticsSummaryOut, CountItem, HotspotOut
from ..utils import utcnow
from .sla import compute_sla_status


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def analytics_summary(db: Session) -> AnalyticsSummaryOut:
    now = utcnow()
    week_ago = now - timedelta(days=7)
    active_status_values = sorted(ACTIVE_INCIDENT_STATUSES)

    active_incidents = db.scalar(
        select(func.count(Incident.id)).where(
            Incident.status.in_(active_status_values),
            Incident.merged_into_id.is_(None),
        )
    ) or 0
    awaiting_triage = db.scalar(
        select(func.count(Incident.id)).where(
            Incident.status == IncidentStatus.OPEN.value,
            Incident.merged_into_id.is_(None),
        )
    ) or 0
    in_progress = db.scalar(
        select(func.count(Incident.id)).where(
            Incident.status == IncidentStatus.IN_PROGRESS.value
        )
    ) or 0
    blocked = db.scalar(
        select(func.count(Incident.id)).where(
            Incident.status == IncidentStatus.BLOCKED.value
        )
    ) or 0
    verification_pending = db.scalar(
        select(func.count(Incident.id)).where(
            Incident.status == IncidentStatus.VERIFICATION_PENDING.value
        )
    ) or 0
    unassigned = db.scalar(
        select(func.count(Incident.id)).where(
            Incident.status.in_(
                [IncidentStatus.OPEN.value, IncidentStatus.TRIAGED.value]
            ),
            Incident.merged_into_id.is_(None),
        )
    ) or 0
    verified_last_7 = db.scalar(
        select(func.count(Incident.id)).where(
            Incident.status == IncidentStatus.VERIFIED.value,
            Incident.verified_at.is_not(None),
            Incident.verified_at >= week_ago,
        )
    ) or 0
    total_reports = db.scalar(select(func.count(CitizenReport.id))) or 0
    reports_last_7 = db.scalar(
        select(func.count(CitizenReport.id)).where(CitizenReport.created_at >= week_ago)
    ) or 0
    accepted_duplicates = db.scalar(
        select(func.count(DuplicateCandidate.id)).where(
            DuplicateCandidate.status == DuplicateStatus.ACCEPTED.value
        )
    ) or 0

    status_rows = db.execute(
        select(Incident.status, func.count(Incident.id))
        .where(Incident.status != IncidentStatus.MERGED.value)
        .group_by(Incident.status)
        .order_by(func.count(Incident.id).desc())
    ).all()
    category_rows = db.execute(
        select(Incident.category, func.count(Incident.id))
        .where(Incident.status != IncidentStatus.MERGED.value)
        .group_by(Incident.category)
        .order_by(func.count(Incident.id).desc())
    ).all()
    ward_rows = db.execute(
        select(Ward.name, func.count(Incident.id))
        .join(Incident, Incident.ward_id == Ward.id)
        .where(Incident.status != IncidentStatus.MERGED.value)
        .group_by(Ward.name)
        .order_by(func.count(Incident.id).desc())
    ).all()

    hotspots = list(
        db.scalars(
            select(Incident)
            .where(
                Incident.status.in_(active_status_values),
                Incident.merged_into_id.is_(None),
            )
            .options(
                selectinload(Incident.ward),
                selectinload(Incident.reports),
                selectinload(Incident.work_orders),
            )
        ).all()
    )
    sla_breached_count = 0
    sla_at_risk_count = 0
    for inc in hotspots:
        orders = sorted(inc.work_orders, key=lambda o: o.id, reverse=True)
        active_order = orders[0] if orders else None
        sla = compute_sla_status(
            created_at=inc.created_at,
            due_at=active_order.due_at if active_order else None,
            priority=inc.priority,
            status=inc.status,
            verified_at=inc.verified_at,
            now=now,
        )
        if sla.sla_state == "breached":
            sla_breached_count += 1
        elif sla.sla_state == "at_risk":
            sla_at_risk_count += 1
    hotspots.sort(
        key=lambda item: (
            PRIORITY_ORDER.get(item.priority, 0),
            len(item.reports),
            item.created_at,
        ),
        reverse=True,
    )

    return AnalyticsSummaryOut(
        generated_at=now,
        active_incidents=active_incidents,
        awaiting_triage=awaiting_triage,
        unassigned_incidents=unassigned,
        in_progress=in_progress,
        blocked=blocked,
        verification_pending=verification_pending,
        verified_last_7_days=verified_last_7,
        total_reports=total_reports,
        reports_last_7_days=reports_last_7,
        accepted_duplicate_links=accepted_duplicates,
        sla_breached_count=sla_breached_count,
        sla_at_risk_count=sla_at_risk_count,
        status_counts=[
            CountItem(key=status, label=_label(status), count=count)
            for status, count in status_rows
        ],
        category_counts=[
            CountItem(
                key=category,
                label=CATEGORY_LABELS.get(category, _label(category)),
                count=count,
            )
            for category, count in category_rows
        ],
        ward_counts=[
            CountItem(key=name, label=name, count=count) for name, count in ward_rows
        ],
        hotspots=[
            HotspotOut(
                incident_id=incident.id,
                public_id=incident.public_id,
                latitude=incident.latitude,
                longitude=incident.longitude,
                ward_name=incident.ward.name,
                category=incident.category,
                priority=incident.priority,
                status=incident.status,
                report_count=len(incident.reports),
            )
            for incident in hotspots[:8]
        ],
    )
