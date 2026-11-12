"""Citizen report intake and the persisted intake-to-incident workflow."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..domain import IncidentStatus, MediaKind, Role
from ..errors import ConflictError, NotFoundError, ValidationError
from ..models import CitizenReport, DuplicateCandidate, Incident, MediaAsset, User, Ward
from ..schemas import CitizenFeedbackCreate, PublicReportStatusOut, ReportCreate
from ..utils import new_public_id, utcnow
from .audit import record_audit
from .duplicates import suggest_duplicates
from .incidents import create_incident_from_report
from .media import PreparedAudio, PreparedImage, add_media, remove_stored_file
from .sla import compute_sla_status
from .triage import run_triage

logger = logging.getLogger(__name__)


def report_load_options():
    return (
        selectinload(CitizenReport.ward),
        selectinload(CitizenReport.media),
        selectinload(CitizenReport.incident).selectinload(Incident.work_orders),
    )


def get_report(db: Session, report_id: int) -> CitizenReport:
    report = db.scalar(
        select(CitizenReport)
        .where(CitizenReport.id == report_id)
        .options(*report_load_options())
    )
    if report is None:
        raise NotFoundError("Report not found.")
    return report


def get_report_by_public_id(db: Session, public_id: str) -> CitizenReport:
    report = db.scalar(
        select(CitizenReport)
        .where(CitizenReport.public_id == public_id)
        .options(*report_load_options())
    )
    if report is None:
        raise NotFoundError("Report not found.")
    return report


def get_candidates_for_report(
    db: Session, report_id: int
) -> list[DuplicateCandidate]:
    return list(
        db.scalars(
            select(DuplicateCandidate)
            .where(DuplicateCandidate.report_id == report_id)
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
            .order_by(DuplicateCandidate.score.desc(), DuplicateCandidate.id)
        ).all()
    )


def create_report(
    db: Session,
    *,
    payload: ReportCreate,
    actor: User | None,
    prepared_image: PreparedImage | None,
    prepared_audio: PreparedAudio | None = None,
) -> tuple[CitizenReport, Incident, list[DuplicateCandidate], list[str]]:
    ward = db.get(Ward, payload.ward_id)
    if ward is None:
        raise ValidationError("Select a valid ward.")

    report = CitizenReport(
        public_id=new_public_id("RPT"),
        citizen_id=actor.id if actor else None,
        reporter_name=payload.reporter_name or (actor.name if actor else None),
        reporter_contact=payload.reporter_contact,
        description=payload.description,
        preferred_language=payload.preferred_language,
        submitted_category=(
            payload.submitted_category.value if payload.submitted_category else None
        ),
        address=payload.address,
        ward_id=ward.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_demo=False,
    )
    db.add(report)
    stored_assets: list[MediaAsset] = []
    try:
        db.flush()
        if prepared_image is not None:
            stored_assets.append(
                add_media(
                    db,
                    prepared=prepared_image,
                    kind=MediaKind.REPORT_PHOTO,
                    uploaded_by=actor,
                    report_id=report.id,
                )
            )
        if prepared_audio is not None:
            stored_assets.append(
                add_media(
                    db,
                    prepared=prepared_audio,
                    kind=MediaKind.REPORT_AUDIO,
                    uploaded_by=actor,
                    report_id=report.id,
                )
            )
        record_audit(
            db,
            action="report_created",
            entity_type="report",
            entity_id=report.id,
            actor=actor,
            actor_role=Role.CITIZEN.value if actor is None else None,
            actor_name="Anonymous citizen" if actor is None else None,
            note="Citizen report persisted before AI enrichment.",
            metadata={
                "report_public_id": report.public_id,
                "has_photo": prepared_image is not None,
                "has_audio": prepared_audio is not None,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        for asset in stored_assets:
            remove_stored_file(asset.storage_key)
        raise

    warnings: list[str] = []
    # The report is now durable. AI enrichment cannot roll it back.
    outcome, triage_warnings = run_triage(
        db,
        report,
        image=prepared_image.data if prepared_image else None,
        image_content_type=prepared_image.content_type if prepared_image else None,
        audio=prepared_audio.data if prepared_audio else None,
        audio_content_type=prepared_audio.content_type if prepared_audio else None,
    )
    warnings.extend(triage_warnings)
    db.add(report)
    db.flush()

    try:
        incident = create_incident_from_report(db, report)
        record_audit(
            db,
            action="incident_created",
            entity_type="incident",
            entity_id=incident.id,
            actor=None,
            actor_role="system",
            actor_name="CivicOps intake",
            old_status=None,
            new_status=incident.status,
            note="Incident created automatically from a citizen report.",
            metadata={
                "incident_public_id": incident.public_id,
                "report_public_id": report.public_id,
            },
        )
        record_audit(
            db,
            action="ai_triage_completed",
            entity_type="incident",
            entity_id=incident.id,
            actor=None,
            actor_role="system",
            actor_name="AI triage service",
            old_status=incident.status,
            new_status=incident.status,
            note=outcome.output.rationale,
            metadata={
                "status": outcome.status.value,
                "provider": outcome.provider,
                "model": outcome.model,
                "fallback_used": outcome.fallback_used,
                "confidence": outcome.output.confidence,
                "category": outcome.output.category.value,
                "severity": outcome.output.severity.value,
                "human_review_required": True,
            },
        )
        candidates = suggest_duplicates(db, report)
        if candidates:
            record_audit(
                db,
                action="duplicate_suggestions_created",
                entity_type="incident",
                entity_id=incident.id,
                actor=None,
                actor_role="system",
                actor_name="Duplicate detection service",
                old_status=incident.status,
                new_status=incident.status,
                note="Duplicate suggestions require human review.",
                metadata={"count": len(candidates)},
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Incident workflow failed after report persistence: %s", report.public_id)
        raise

    report = get_report(db, report.id)
    incident = db.scalar(
        select(Incident)
        .where(Incident.id == incident.id)
        .options(
            selectinload(Incident.ward),
            selectinload(Incident.reports).selectinload(CitizenReport.ward),
            selectinload(Incident.reports).selectinload(CitizenReport.media),
            selectinload(Incident.work_orders),
        )
    )
    assert incident is not None
    candidates = get_candidates_for_report(db, report.id)
    return report, incident, candidates, warnings


def track_report(db: Session, public_id: str) -> PublicReportStatusOut:
    report = get_report_by_public_id(db, public_id)
    incident = report.incident
    sla_state = None
    due_at = None
    if incident is not None:
        orders = sorted(incident.work_orders, key=lambda o: o.id, reverse=True)
        active = orders[0] if orders else None
        sla = compute_sla_status(
            created_at=incident.created_at,
            due_at=active.due_at if active else None,
            priority=incident.priority,
            status=incident.status,
            verified_at=incident.verified_at,
        )
        sla_state = sla.sla_state
        due_at = sla.due_at
    return PublicReportStatusOut(
        public_id=report.public_id,
        submitted_at=report.created_at,
        category=report.ai_category,
        summary=report.ai_summary,
        incident_public_id=incident.public_id if incident else None,
        incident_status=incident.status if incident else None,
        verified_at=incident.verified_at if incident else None,
        sla_state=sla_state,
        due_at=due_at,
        citizen_rating=report.citizen_rating,
        citizen_feedback=report.citizen_feedback,
        citizen_feedback_at=report.citizen_feedback_at,
        citizen_reopen_requested=report.citizen_reopen_requested,
        is_demo=report.is_demo,
    )


def submit_citizen_feedback(
    db: Session, public_id: str, payload: CitizenFeedbackCreate
) -> PublicReportStatusOut:
    report = get_report_by_public_id(db, public_id)
    incident = report.incident
    if incident is None or incident.status != IncidentStatus.VERIFIED.value:
        raise ConflictError(
            "Feedback can only be submitted once the linked incident is verified."
        )

    now = utcnow()
    report.citizen_rating = payload.rating
    report.citizen_feedback = payload.comment
    report.citizen_feedback_at = now
    report.citizen_reopen_requested = not payload.resolved_satisfactorily
    db.add(report)

    action = (
        "citizen_feedback_received"
        if payload.resolved_satisfactorily
        else "citizen_disputed_resolution"
    )
    record_audit(
        db,
        action=action,
        entity_type="incident",
        entity_id=incident.id,
        actor=None,
        actor_role=Role.CITIZEN.value,
        actor_name="Citizen tracker",
        old_status=incident.status,
        new_status=incident.status,
        note=payload.comment
        or (
            f"Citizen rated resolution {payload.rating}/5."
            if payload.resolved_satisfactorily
            else f"Citizen disputed resolution ({payload.rating}/5) and requested follow-up."
        ),
        metadata={
            "report_public_id": report.public_id,
            "rating": payload.rating,
            "resolved_satisfactorily": payload.resolved_satisfactorily,
        },
    )
    db.commit()
    return track_report(db, public_id)
