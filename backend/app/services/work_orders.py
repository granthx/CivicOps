"""Human-approved work-order lifecycle and field evidence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from ..domain import (
    ACTION_ROLE_REQUIREMENT,
    INCIDENT_STATUS_FOR_WORK_ORDER,
    WORK_ORDER_ACTION_TARGET,
    WORK_ORDER_TRANSITIONS,
    IncidentStatus,
    MediaKind,
    Role,
    WorkOrderStatus,
)
from ..errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..models import (
    AuditEvent,
    CitizenReport,
    Incident,
    MediaAsset,
    Team,
    User,
    WorkOrder,
)
from ..schemas import WorkOrderCreateRequest, WorkOrderTransitionRequest
from ..utils import new_public_id, utcnow
from .audit import record_audit
from .incidents import parse_due_at
from .media import PreparedImage, add_media, remove_stored_file
from .sla import default_sla_due_at


def get_work_order(db: Session, work_order_id: int) -> WorkOrder:
    order = db.scalar(
        select(WorkOrder)
        .where(WorkOrder.id == work_order_id)
        .options(
            selectinload(WorkOrder.team).selectinload(Team.ward),
            selectinload(WorkOrder.evidence),
            selectinload(WorkOrder.incident).selectinload(Incident.ward),
            selectinload(WorkOrder.incident)
            .selectinload(Incident.reports)
            .selectinload(CitizenReport.media),
            selectinload(WorkOrder.incident)
            .selectinload(Incident.reports)
            .selectinload(CitizenReport.ward),
        )
    )
    if order is None:
        raise NotFoundError("Work order not found.")
    return order


def ensure_work_order_access(order: WorkOrder, actor: User) -> None:
    if actor.role in {Role.OPERATOR.value, Role.ADMIN.value}:
        return
    if actor.role == Role.FIELD_WORKER.value and order.team_id == actor.team_id:
        return
    raise ForbiddenError("This work order is not assigned to your team.")


def create_work_order(
    db: Session,
    *,
    incident: Incident,
    actor: User,
    payload: WorkOrderCreateRequest,
) -> WorkOrder:
    if incident.status != IncidentStatus.TRIAGED.value:
        raise ConflictError(
            "Confirm incident triage before creating a work order."
        )
    existing = db.scalar(
        select(func.count(WorkOrder.id)).where(WorkOrder.incident_id == incident.id)
    )
    if existing:
        raise ConflictError("This incident already has a work order in the MVP workflow.")
    team = db.get(Team, payload.team_id)
    if team is None or not team.is_active:
        raise ValidationError("Select an active field team.")
    if team.ward_id != incident.ward_id:
        raise ValidationError("The team must be assigned to the incident's ward.")

    due_at = parse_due_at(payload.due_at) or default_sla_due_at(utcnow(), incident.priority)
    previous_incident_status = incident.status
    order = WorkOrder(
        public_id=new_public_id("WO"),
        incident_id=incident.id,
        team_id=team.id,
        created_by_id=actor.id,
        instructions=payload.instructions,
        due_at=due_at,
        status=WorkOrderStatus.ASSIGNED.value,
    )
    db.add(order)
    incident.status = IncidentStatus.ASSIGNED.value
    db.add(incident)
    db.flush()
    record_audit(
        db,
        action="work_order_created",
        entity_type="work_order",
        entity_id=order.id,
        actor=actor,
        old_status=None,
        new_status=order.status,
        note=payload.instructions,
        metadata={
            "work_order_public_id": order.public_id,
            "incident_public_id": incident.public_id,
            "team": team.name,
            "previous_incident_status": previous_incident_status,
            "new_incident_status": incident.status,
        },
    )
    db.commit()
    return get_work_order(db, order.id)


def _required_note(action: str, note: str | None) -> str | None:
    if action in {"block", "complete", "reject_verification"} and not (note and note.strip()):
        raise ValidationError("A note is required for this work-order action.")
    return note.strip() if note else None


def transition_work_order(
    db: Session,
    *,
    order: WorkOrder,
    actor: User,
    payload: WorkOrderTransitionRequest,
) -> WorkOrder:
    ensure_work_order_access(order, actor)
    if actor.role not in ACTION_ROLE_REQUIREMENT[payload.action]:
        raise ForbiddenError("Your role cannot perform this work-order action.")
    if order.incident.status == IncidentStatus.MERGED.value:
        raise ConflictError("Merged incidents cannot be worked on.")

    target = WORK_ORDER_ACTION_TARGET[payload.action]
    if target not in WORK_ORDER_TRANSITIONS.get(order.status, set()):
        raise ConflictError(
            f"Cannot {payload.action.replace('_', ' ')} a work order that is "
            f"{order.status.replace('_', ' ')}."
        )
    note = _required_note(payload.action, payload.note)

    if payload.action == "complete":
        after_photos = db.scalar(
            select(func.count(MediaAsset.id)).where(
                MediaAsset.work_order_id == order.id,
                MediaAsset.kind == MediaKind.AFTER_PHOTO.value,
            )
        )
        if not after_photos:
            raise ConflictError(
                "Upload at least one after-photo before marking work complete."
            )

    previous_order_status = order.status
    previous_incident_status = order.incident.status
    now = utcnow()
    order.status = target
    if payload.action == "complete":
        order.completed_at = now
        order.completion_note = note
    if payload.action == "verify":
        order.verified_at = now
        order.verification_note = note
    if payload.action == "reject_verification":
        order.verification_note = note
        order.completed_at = None

    new_incident_status = INCIDENT_STATUS_FOR_WORK_ORDER[target]
    order.incident.status = new_incident_status
    if new_incident_status == IncidentStatus.VERIFIED.value:
        order.incident.verified_at = now
    elif new_incident_status == IncidentStatus.REOPENED.value:
        order.incident.verified_at = None

    db.add(order)
    db.add(order.incident)
    record_audit(
        db,
        action=f"work_order_{payload.action}",
        entity_type="work_order",
        entity_id=order.id,
        actor=actor,
        old_status=previous_order_status,
        new_status=target,
        note=note,
        metadata={
            "work_order_public_id": order.public_id,
            "incident_public_id": order.incident.public_id,
            "previous_incident_status": previous_incident_status,
            "new_incident_status": new_incident_status,
        },
    )
    db.commit()
    return get_work_order(db, order.id)


def add_work_order_evidence(
    db: Session,
    *,
    order: WorkOrder,
    actor: User,
    prepared: PreparedImage,
    kind: MediaKind,
    original_filename: str | None = None,
) -> MediaAsset:
    ensure_work_order_access(order, actor)
    if order.status == WorkOrderStatus.VERIFIED.value:
        raise ConflictError("Verified work orders cannot receive new evidence.")
    if kind not in {MediaKind.BEFORE_PHOTO, MediaKind.AFTER_PHOTO}:
        raise ValidationError("Evidence must be a before-photo or after-photo.")

    asset = add_media(
        db,
        prepared=prepared,
        kind=kind,
        uploaded_by=actor,
        work_order_id=order.id,
    )
    try:
        db.flush()
        record_audit(
            db,
            action="evidence_added",
            entity_type="work_order",
            entity_id=order.id,
            actor=actor,
            old_status=order.status,
            new_status=order.status,
            note=f"{kind.value.replace('_', ' ').title()} uploaded.",
            metadata={
                "media_id": asset.id,
                "media_public_id": asset.public_id,
                "kind": kind.value,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        remove_stored_file(asset.storage_key)
        raise
    return asset


def get_work_order_activity(db: Session, order: WorkOrder) -> list[AuditEvent]:
    return list(
        db.scalars(
            select(AuditEvent)
            .where(
                and_(
                    AuditEvent.entity_type == "work_order",
                    AuditEvent.entity_id == order.id,
                )
            )
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(100)
        ).all()
    )


def serialize_due_at(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC).replace(tzinfo=None) if value else None
