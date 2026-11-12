"""Explicit, role-aware API serialization boundaries."""

from __future__ import annotations

from .models import (
    AuditEvent,
    CitizenReport,
    DuplicateCandidate,
    Incident,
    MediaAsset,
    Team,
    User,
    Ward,
    WorkOrder,
)
from .schemas import (
    AuditEventOut,
    CandidateReportOut,
    DuplicateCandidateOut,
    IncidentDetailOut,
    IncidentOut,
    MediaOut,
    PriorityFactorsOut,
    ReportOut,
    TeamOut,
    UserOut,
    WardOut,
    WorkOrderBriefOut,
    WorkOrderDetailOut,
    WorkOrderIncidentOut,
    WorkOrderOut,
)
from .services.sla import compute_sla_status


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        team_id=user.team_id,
        team_name=user.team.name if user.team else None,
        is_demo=user.is_demo,
    )


def ward_out(ward: Ward) -> WardOut:
    return WardOut(
        id=ward.id,
        name=ward.name,
        code=ward.code,
        city=ward.city,
    )


def team_out(team: Team) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        ward_id=team.ward_id,
        team_type=team.team_type,
        is_active=team.is_active,
    )


def media_out(media: MediaAsset) -> MediaOut:
    return MediaOut(
        id=media.id,
        public_id=media.public_id,
        kind=media.kind,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        width=media.width,
        height=media.height,
        created_at=media.created_at,
    )


def report_out(report: CitizenReport, *, include_private: bool = False) -> ReportOut:
    return ReportOut(
        id=report.id,
        public_id=report.public_id,
        description=report.description,
        preferred_language=report.preferred_language,
        voice_transcript=report.voice_transcript,
        detected_language=report.detected_language,
        address=report.address,
        latitude=report.latitude,
        longitude=report.longitude,
        ward=ward_out(report.ward),
        submitted_category=report.submitted_category,
        ai_status=report.ai_status,
        ai_category=report.ai_category,
        ai_severity=report.ai_severity,
        ai_confidence=report.ai_confidence,
        ai_summary=report.ai_summary,
        ai_indicators=report.ai_indicators or [],
        ai_rationale=report.ai_rationale,
        ai_provider=report.ai_provider,
        ai_model=report.ai_model,
        ai_fallback_used=report.ai_fallback_used,
        ai_error=report.ai_error,
        ai_processed_at=report.ai_processed_at,
        incident_id=report.incident_id,
        incident_public_id=report.incident.public_id if report.incident else None,
        link_type=report.link_type,
        reporter_name=report.reporter_name if include_private else None,
        reporter_contact=report.reporter_contact if include_private else None,
        citizen_rating=report.citizen_rating,
        citizen_feedback=report.citizen_feedback,
        citizen_reopen_requested=report.citizen_reopen_requested,
        is_demo=report.is_demo,
        media=[media_out(media) for media in sorted(report.media, key=lambda m: m.id)],
        created_at=report.created_at,
    )


def candidate_report_out(report: CitizenReport) -> CandidateReportOut:
    return CandidateReportOut(
        id=report.id,
        public_id=report.public_id,
        description=report.description,
        latitude=report.latitude,
        longitude=report.longitude,
        ward_name=report.ward.name,
        ai_category=report.ai_category,
        created_at=report.created_at,
        media=[media_out(media) for media in sorted(report.media, key=lambda m: m.id)],
    )


def duplicate_candidate_out(candidate: DuplicateCandidate) -> DuplicateCandidateOut:
    incident = candidate.candidate_incident
    return DuplicateCandidateOut(
        id=candidate.id,
        score=candidate.score,
        distance_m=candidate.distance_m,
        reasons=candidate.reasons or [],
        status=candidate.status,
        candidate_report=candidate_report_out(candidate.candidate_report),
        candidate_incident_id=candidate.candidate_incident_id,
        candidate_incident_public_id=incident.public_id if incident else None,
        candidate_incident_status=incident.status if incident else None,
        review_note=candidate.review_note,
        reviewed_at=candidate.reviewed_at,
        created_at=candidate.created_at,
    )


def priority_factors_out(incident: Incident) -> PriorityFactorsOut | None:
    data = incident.priority_factors or {}
    if not data or "factors" not in data:
        return None
    return PriorityFactorsOut.model_validate(data)


def incident_out(incident: Incident) -> IncidentOut:
    orders = sorted(incident.work_orders, key=lambda order: order.id, reverse=True)
    active = orders[0] if orders else None
    return IncidentOut(
        id=incident.id,
        public_id=incident.public_id,
        title=incident.title,
        description=incident.description,
        category=incident.category,
        severity=incident.severity,
        status=incident.status,
        priority=incident.priority,
        recommended_priority=incident.recommended_priority,
        priority_score=incident.priority_score,
        priority_factors=priority_factors_out(incident),
        priority_overridden=incident.priority_overridden,
        priority_override_reason=incident.priority_override_reason,
        ward=ward_out(incident.ward),
        address=incident.address,
        latitude=incident.latitude,
        longitude=incident.longitude,
        report_count=len(incident.reports),
        active_work_order=(
            WorkOrderBriefOut(
                id=active.id,
                public_id=active.public_id,
                status=active.status,
                team_id=active.team_id,
                team_name=active.team.name,
                due_at=active.due_at,
            )
            if active
            else None
        ),
        sla=compute_sla_status(
            created_at=incident.created_at,
            due_at=active.due_at if active else None,
            priority=incident.priority,
            status=incident.status,
            verified_at=incident.verified_at,
        ),
        triaged_at=incident.triaged_at,
        is_demo=incident.is_demo,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


def audit_event_out(event: AuditEvent) -> AuditEventOut:
    return AuditEventOut(
        id=event.id,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        old_status=event.old_status,
        new_status=event.new_status,
        note=event.note,
        actor_name=event.actor_name,
        actor_role=event.actor_role,
        event_metadata=event.event_metadata or {},
        created_at=event.created_at,
    )


def work_order_incident_out(incident: Incident) -> WorkOrderIncidentOut:
    return WorkOrderIncidentOut(
        id=incident.id,
        public_id=incident.public_id,
        title=incident.title,
        description=incident.description,
        category=incident.category,
        priority=incident.priority,
        status=incident.status,
        latitude=incident.latitude,
        longitude=incident.longitude,
        address=incident.address,
        ward=ward_out(incident.ward),
    )


def work_order_out(order: WorkOrder) -> WorkOrderOut:
    return WorkOrderOut(
        id=order.id,
        public_id=order.public_id,
        incident_id=order.incident_id,
        incident=work_order_incident_out(order.incident),
        team=team_out(order.team),
        instructions=order.instructions,
        due_at=order.due_at,
        status=order.status,
        completion_note=order.completion_note,
        verification_note=order.verification_note,
        completed_at=order.completed_at,
        verified_at=order.verified_at,
        evidence=[media_out(asset) for asset in sorted(order.evidence, key=lambda a: a.id)],
        sla=compute_sla_status(
            created_at=order.created_at,
            due_at=order.due_at,
            priority=order.incident.priority,
            status=order.status,
            verified_at=order.verified_at,
        ),
        is_demo=order.is_demo,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def incident_detail_out(
    incident: Incident,
    *,
    activity: list[AuditEvent],
    duplicates: list[DuplicateCandidate],
) -> IncidentDetailOut:
    base = incident_out(incident)
    return IncidentDetailOut(
        **base.model_dump(),
        reports=[report_out(report, include_private=True) for report in incident.reports],
        work_orders=[
            work_order_out(order)
            for order in sorted(incident.work_orders, key=lambda item: item.id, reverse=True)
        ],
        activity=[audit_event_out(event) for event in activity],
        duplicate_candidates=[duplicate_candidate_out(item) for item in duplicates],
    )


def work_order_detail_out(
    order: WorkOrder, *, activity: list[AuditEvent]
) -> WorkOrderDetailOut:
    base = work_order_out(order)
    return WorkOrderDetailOut(
        **base.model_dump(),
        reports=[
            report_out(report, include_private=False)
            for report in sorted(order.incident.reports, key=lambda item: item.created_at)
        ],
        activity=[audit_event_out(event) for event in activity],
    )
