"""Incident creation, human triage, duplicate review and report linking."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..domain import (
    CATEGORY_LABELS,
    DuplicateStatus,
    IncidentStatus,
    Priority,
    Severity,
)
from ..errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    AuditEvent,
    CitizenReport,
    DuplicateCandidate,
    Incident,
    MediaAsset,
    User,
    WorkOrder,
)
from ..schemas import PriorityOverrideRequest
from ..utils import new_public_id, utcnow
from .audit import record_audit
from .hotspots import get_hotspot_context
from .priority import apply_priority


def create_incident_from_report(
    db: Session, report: CitizenReport, *, is_demo: bool = False
) -> Incident:
    category = report.ai_category or report.submitted_category or "other_waste"
    severity = report.ai_severity or Severity.MODERATE.value
    label = CATEGORY_LABELS.get(category, "Waste issue")
    location = report.address or report.ward.name
    incident = Incident(
        public_id=new_public_id("INC"),
        title=f"{label} near {location}",
        description=report.ai_summary or report.description,
        category=category,
        severity=severity,
        ward_id=report.ward_id,
        address=report.address,
        latitude=report.latitude,
        longitude=report.longitude,
        status=IncidentStatus.OPEN.value,
        is_demo=is_demo,
    )
    db.add(incident)
    db.flush()
    report.incident_id = incident.id
    report.linked_at = utcnow()
    report.link_type = "created"
    report.link_reason = "Incident created from this citizen report."
    db.flush()
    hotspot_ctx = get_hotspot_context(
        db,
        latitude=incident.latitude,
        longitude=incident.longitude,
        exclude_incident_id=incident.id,
    )
    apply_priority(incident, [report], hotspot_context=hotspot_ctx)
    db.add(incident)
    return incident


def get_incident(db: Session, incident_id: int) -> Incident:
    incident = db.scalar(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.ward),
            selectinload(Incident.reports).selectinload(CitizenReport.ward),
            selectinload(Incident.reports).selectinload(CitizenReport.media),
            selectinload(Incident.work_orders).selectinload(WorkOrder.team),
            selectinload(Incident.work_orders).selectinload(WorkOrder.evidence),
            selectinload(Incident.work_orders).selectinload(WorkOrder.incident),
        )
    )
    if incident is None:
        raise NotFoundError("Incident not found.")
    return incident


def _resolve_target_incident(db: Session, incident: Incident) -> Incident:
    seen: set[int] = set()
    target = incident
    while target.merged_into_id and target.id not in seen:
        seen.add(target.id)
        next_target = db.get(Incident, target.merged_into_id)
        if next_target is None:
            break
        target = next_target
    if target.status == IncidentStatus.MERGED.value:
        raise ConflictError("This incident has been merged and cannot receive reports.")
    return target


def link_report_to_incident(
    db: Session,
    *,
    report: CitizenReport,
    target: Incident,
    actor: User,
    reason: str,
) -> Incident:
    target = _resolve_target_incident(db, target)
    if report.incident_id == target.id:
        raise ConflictError("This report is already linked to the incident.")

    old_incident = db.get(Incident, report.incident_id) if report.incident_id else None
    report.incident_id = target.id
    report.linked_at = utcnow()
    report.linked_by_id = actor.id
    report.link_reason = reason
    report.link_type = "confirmed_duplicate"
    db.flush()

    record_audit(
        db,
        action="report_linked",
        entity_type="incident",
        entity_id=target.id,
        actor=actor,
        old_status=None,
        new_status=target.status,
        note=reason,
        metadata={
            "report_public_id": report.public_id,
            "source_incident_public_id": old_incident.public_id if old_incident else None,
        },
    )

    if old_incident is not None and old_incident.id != target.id:
        remaining_reports = db.scalar(
            select(func.count(CitizenReport.id)).where(
                CitizenReport.incident_id == old_incident.id
            )
        )
        remaining_orders = db.scalar(
            select(func.count(WorkOrder.id)).where(WorkOrder.incident_id == old_incident.id)
        )
        if remaining_reports == 0 and remaining_orders == 0:
            previous = old_incident.status
            old_incident.status = IncidentStatus.MERGED.value
            old_incident.merged_into_id = target.id
            record_audit(
                db,
                action="incident_merged",
                entity_type="incident",
                entity_id=old_incident.id,
                actor=actor,
                old_status=previous,
                new_status=IncidentStatus.MERGED.value,
                note=f"Empty source incident merged into {target.public_id}.",
                metadata={"target_incident_public_id": target.public_id},
            )

    db.flush()
    target_reports = list(
        db.scalars(select(CitizenReport).where(CitizenReport.incident_id == target.id)).all()
    )
    hotspot_ctx = get_hotspot_context(
        db,
        latitude=target.latitude,
        longitude=target.longitude,
        exclude_incident_id=target.id,
    )
    apply_priority(target, target_reports, hotspot_context=hotspot_ctx)
    db.add(target)
    db.flush()
    return target


def review_duplicate(
    db: Session,
    *,
    candidate_id: int,
    actor: User,
    decision: str,
    note: str | None,
) -> DuplicateCandidate:
    candidate = db.scalar(
        select(DuplicateCandidate)
        .where(DuplicateCandidate.id == candidate_id)
        .options(
            selectinload(DuplicateCandidate.report),
            selectinload(DuplicateCandidate.candidate_report),
        )
    )
    if candidate is None:
        raise NotFoundError("Duplicate suggestion not found.")
    if candidate.status != DuplicateStatus.SUGGESTED.value:
        raise ConflictError("This duplicate suggestion has already been reviewed.")

    if decision == "accept":
        if not candidate.candidate_incident_id:
            raise ConflictError("The candidate report is not attached to an incident.")
        target = db.get(Incident, candidate.candidate_incident_id)
        if target is None:
            raise ConflictError("The candidate incident no longer exists.")
        target = link_report_to_incident(
            db,
            report=candidate.report,
            target=target,
            actor=actor,
            reason=note or "Operator confirmed duplicate report relationship.",
        )
        candidate.status = DuplicateStatus.ACCEPTED.value
        candidate.review_note = note
        candidate.reviewed_by_id = actor.id
        candidate.reviewed_at = utcnow()
        record_audit(
            db,
            action="duplicate_accepted",
            entity_type="incident",
            entity_id=target.id,
            actor=actor,
            old_status=None,
            new_status=target.status,
            note=note or "Operator confirmed a duplicate report.",
            metadata={
                "report_public_id": candidate.report.public_id,
                "candidate_report_public_id": candidate.candidate_report.public_id,
                "score": candidate.score,
            },
        )
    elif decision == "reject":
        candidate.status = DuplicateStatus.REJECTED.value
        candidate.review_note = note
        candidate.reviewed_by_id = actor.id
        candidate.reviewed_at = utcnow()
        record_audit(
            db,
            action="duplicate_rejected",
            entity_type="incident",
            entity_id=candidate.report.incident_id or 0,
            actor=actor,
            old_status=None,
            new_status=None,
            note=note or "Operator rejected the suggested duplicate.",
            metadata={
                "report_public_id": candidate.report.public_id,
                "candidate_report_public_id": candidate.candidate_report.public_id,
                "score": candidate.score,
            },
        )
    else:
        raise ValidationError("Decision must be accept or reject.")

    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def triage_incident(
    db: Session,
    *,
    incident: Incident,
    actor: User,
    category,
    severity,
    note: str,
) -> Incident:
    if incident.status in {IncidentStatus.MERGED.value, IncidentStatus.VERIFIED.value}:
        raise ConflictError("This incident can no longer be triaged.")
    previous = incident.status
    if category is not None:
        incident.category = category.value if hasattr(category, "value") else str(category)
    if severity is not None:
        incident.severity = severity.value if hasattr(severity, "value") else str(severity)
    incident.triaged_at = utcnow()
    incident.triaged_by_id = actor.id
    incident.triage_notes = note
    if incident.status == IncidentStatus.OPEN.value:
        incident.status = IncidentStatus.TRIAGED.value
    reports = list(
        db.scalars(select(CitizenReport).where(CitizenReport.incident_id == incident.id)).all()
    )
    hotspot_ctx = get_hotspot_context(
        db,
        latitude=incident.latitude,
        longitude=incident.longitude,
        exclude_incident_id=incident.id,
    )
    apply_priority(incident, reports, hotspot_context=hotspot_ctx)
    db.add(incident)
    record_audit(
        db,
        action="incident_triaged",
        entity_type="incident",
        entity_id=incident.id,
        actor=actor,
        old_status=previous,
        new_status=incident.status,
        note=note,
        metadata={
            "category": incident.category,
            "severity": incident.severity,
            "recommended_priority": incident.recommended_priority,
        },
    )
    db.commit()
    db.refresh(incident)
    return incident


def override_priority(
    db: Session,
    *,
    incident: Incident,
    actor: User,
    payload: PriorityOverrideRequest,
) -> Incident:
    if incident.status in {IncidentStatus.MERGED.value, IncidentStatus.VERIFIED.value}:
        raise ConflictError("Priority cannot be changed for this incident.")
    previous = incident.priority
    incident.priority = payload.priority.value
    incident.priority_overridden = True
    incident.priority_override_reason = payload.reason
    incident.priority_overridden_by_id = actor.id
    incident.priority_overridden_at = utcnow()
    db.add(incident)
    record_audit(
        db,
        action="priority_overridden",
        entity_type="incident",
        entity_id=incident.id,
        actor=actor,
        old_status=incident.status,
        new_status=incident.status,
        note=payload.reason,
        metadata={
            "previous_priority": previous,
            "new_priority": payload.priority.value,
            "recommended_priority": incident.recommended_priority,
        },
    )
    db.commit()
    db.refresh(incident)
    return incident


def get_incident_duplicate_candidates(
    db: Session, incident: Incident
) -> list[DuplicateCandidate]:
    report_ids = [report.id for report in incident.reports]
    if not report_ids:
        return []
    return list(
        db.scalars(
            select(DuplicateCandidate)
            .where(DuplicateCandidate.report_id.in_(report_ids))
            .options(
                selectinload(DuplicateCandidate.report),
                selectinload(DuplicateCandidate.candidate_report).selectinload(
                    CitizenReport.ward
                ),
                selectinload(DuplicateCandidate.candidate_report).selectinload(
                    CitizenReport.media
                ),
                selectinload(DuplicateCandidate.candidate_incident),
            )
            .order_by(DuplicateCandidate.score.desc(), DuplicateCandidate.created_at.desc())
        ).all()
    )


def get_incident_activity(db: Session, incident: Incident) -> list[AuditEvent]:
    work_order_ids = [order.id for order in incident.work_orders]
    conditions = [
        and_(AuditEvent.entity_type == "incident", AuditEvent.entity_id == incident.id)
    ]
    if work_order_ids:
        conditions.append(
            and_(
                AuditEvent.entity_type == "work_order",
                AuditEvent.entity_id.in_(work_order_ids),
            )
        )
    return list(
        db.scalars(
            select(AuditEvent)
            .where(or_(*conditions))
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(100)
        ).all()
    )


def parse_due_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        from datetime import UTC

        value = value.astimezone(UTC).replace(tzinfo=None)
    if value <= utcnow():
        raise ValidationError("The due date must be in the future.")
    return value
