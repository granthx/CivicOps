"""Operator incident queue, detail and human decision endpoints."""

from __future__ import annotations

from datetime import timedelta
import math
import random

from fastapi import APIRouter, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import selectinload

from ..deps import DbSession, OperatorUser, StaffUser
from ..domain import (
    ACTIVE_INCIDENT_STATUSES,
    PRIORITY_ORDER,
    Category,
    IncidentStatus,
    Priority,
)
from ..models import CitizenReport, DuplicateCandidate, Incident, Ward, WorkOrder, utcnow
from ..schemas import (
    DuplicateCandidateOut,
    DuplicateReviewRequest,
    IncidentDetailOut,
    IncidentOut,
    IncidentPage,
    IncidentTriageRequest,
    PriorityOverrideRequest,
    PublicIncidentMapItem,
    WorkOrderCreateRequest,
    WorkOrderOut,
)
from ..serializers import (
    duplicate_candidate_out,
    incident_detail_out,
    incident_out,
    work_order_out,
)
from ..services.incidents import (
    get_incident,
    get_incident_activity,
    get_incident_duplicate_candidates,
    override_priority,
    review_duplicate,
    triage_incident,
)
from ..services.work_orders import create_work_order

router = APIRouter(prefix="/incidents", tags=["incidents"])
duplicate_router = APIRouter(prefix="/duplicate-candidates", tags=["duplicates"])


def _incident_options():
    return (
        selectinload(Incident.ward),
        selectinload(Incident.reports),
        selectinload(Incident.work_orders).selectinload(WorkOrder.team),
    )


@router.get("", response_model=IncidentPage)
def list_incidents(
    db: DbSession,
    _user: StaffUser,
    status_filters: list[IncidentStatus] = Query(default=[], alias="status"),
    category: Category | None = None,
    priority: Priority | None = None,
    ward_id: int | None = None,
    search: str | None = Query(default=None, max_length=120),
    include_resolved: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> IncidentPage:
    conditions = [Incident.status != IncidentStatus.MERGED.value]
    if status_filters:
        conditions.append(
            Incident.status.in_([value.value for value in status_filters])
        )
    elif not include_resolved:
        conditions.append(Incident.status.in_(sorted(ACTIVE_INCIDENT_STATUSES)))
    if category:
        conditions.append(Incident.category == category.value)
    if priority:
        conditions.append(Incident.priority == priority.value)
    if ward_id:
        conditions.append(Incident.ward_id == ward_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Incident.title.ilike(pattern),
                Incident.address.ilike(pattern),
                Incident.public_id.ilike(pattern),
            )
        )

    total = (
        db.scalar(select(func.count(Incident.id)).where(*conditions)) or 0
    )
    priority_case = case(
        {value: order for value, order in PRIORITY_ORDER.items()},
        value=Incident.priority,
        else_=0,
    )
    incidents = list(
        db.scalars(
            select(Incident)
            .where(*conditions)
            .options(*_incident_options())
            .order_by(priority_case.desc(), Incident.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return IncidentPage(
        items=[incident_out(incident) for incident in incidents],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/public-map", response_model=list[PublicIncidentMapItem])
def public_incident_map(
    db: DbSession,
    limit: int = Query(default=24, ge=1, le=50),
) -> list[PublicIncidentMapItem]:
    """Return citizen-safe incident summaries for the public homepage map."""
    incidents = list(
        db.scalars(
            select(Incident)
            .where(Incident.status != IncidentStatus.MERGED.value)
            .options(selectinload(Incident.ward), selectinload(Incident.reports))
            .order_by(Incident.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [
        PublicIncidentMapItem(
            id=incident.id,
            public_id=incident.public_id,
            title=incident.title,
            category=Category(incident.category),
            priority=Priority(incident.priority),
            status=IncidentStatus(incident.status),
            ward_name=incident.ward.name if incident.ward else None,
            latitude=incident.latitude,
            longitude=incident.longitude,
            report_count=len(incident.reports),
            primary_report_public_id=(
                incident.reports[0].public_id if incident.reports else None
            ),
            created_at=incident.created_at,
            verified_at=incident.verified_at,
            is_demo=incident.is_demo,
        )
        for incident in incidents
    ]


_DELHI_DEMO_SCENARIOS = [
    {
        "title": "Overflowing public bin outside Rajiv Chowk Metro Gate 4 spilling onto walkway.",
        "address": "Outer Circle, near Gate 4, Connaught Place, New Delhi",
        "latitude": 28.6315,
        "longitude": 77.2167,
        "category": Category.OVERFLOWING_BIN,
        "priority": Priority.HIGH,
    },
    {
        "title": "Two days of missed garbage collection beside Lajpat Nagar Central Market shutters.",
        "address": "Central Market Service Lane, Lajpat Nagar, New Delhi",
        "latitude": 28.5677,
        "longitude": 77.2433,
        "category": Category.MISSED_COLLECTION,
        "priority": Priority.MEDIUM,
    },
    {
        "title": "Mixed plastic and food waste accumulating near Karol Bagh Ajmal Khan Road.",
        "address": "Ajmal Khan Road corner, Karol Bagh, New Delhi",
        "latitude": 28.6519,
        "longitude": 77.1905,
        "category": Category.GARBAGE_ACCUMULATION,
        "priority": Priority.HIGH,
    },
    {
        "title": "Dumped renovation debris and packaging blocking Chandni Chowk service alley.",
        "address": "Dariba Kalan lane entrance, Chandni Chowk, New Delhi",
        "latitude": 28.6562,
        "longitude": 77.2310,
        "category": Category.ILLEGAL_DUMPING,
        "priority": Priority.HIGH,
    },
    {
        "title": "Overflowing community compactor bin near Saket District Centre parking.",
        "address": "Press Enclave Marg, Saket, New Delhi",
        "latitude": 28.5286,
        "longitude": 77.2193,
        "category": Category.OVERFLOWING_BIN,
        "priority": Priority.CRITICAL,
    },
    {
        "title": "Uncollected market waste bags piling up outside Hauz Khas Metro exit.",
        "address": "Outer Ring Road service lane, Hauz Khas, New Delhi",
        "latitude": 28.5434,
        "longitude": 77.2066,
        "category": Category.MISSED_COLLECTION,
        "priority": Priority.MEDIUM,
    },
    {
        "title": "Garden and household waste pile growing beside Rohini Sector 7 park gate.",
        "address": "Naharpur Road, Rohini Sector 7, New Delhi",
        "latitude": 28.7077,
        "longitude": 77.1156,
        "category": Category.GARBAGE_ACCUMULATION,
        "priority": Priority.MEDIUM,
    },
    {
        "title": "Accumulated cardboard and market waste near Janpath parking bay.",
        "address": "Janpath Lane Parking Bay, Connaught Place, New Delhi",
        "latitude": 28.6289,
        "longitude": 77.2192,
        "category": Category.GARBAGE_ACCUMULATION,
        "priority": Priority.MEDIUM,
    },
]


@router.post("/public-map/randomize-demo", response_model=list[PublicIncidentMapItem])
def randomize_delhi_demo_incidents(
    db: DbSession,
    limit: int = Query(default=24, ge=1, le=50),
) -> list[PublicIncidentMapItem]:
    """Randomize synthetic New Delhi demo places, complaints, and today's timestamps."""
    delhi_incidents = list(
        db.scalars(
            select(Incident)
            .join(Ward, Incident.ward_id == Ward.id)
            .where(
                Incident.is_demo.is_(True),
                Incident.status != IncidentStatus.MERGED.value,
                Ward.city == "New Delhi",
            )
            .options(selectinload(Incident.reports))
        ).all()
    )
    if delhi_incidents:
        now = utcnow()
        chosen = random.sample(
            _DELHI_DEMO_SCENARIOS,
            k=min(len(delhi_incidents), len(_DELHI_DEMO_SCENARIOS)),
        )
        for index, incident in enumerate(delhi_incidents):
            scenario = chosen[index % len(chosen)]
            jitter_lat = random.uniform(-0.0022, 0.0022)
            jitter_lng = random.uniform(-0.0022, 0.0022)
            created_at = now - timedelta(minutes=random.randint(8, 175))
            incident.title = str(scenario["title"])
            incident.address = str(scenario["address"])
            incident.category = scenario["category"].value
            incident.priority = scenario["priority"].value
            incident.latitude = round(float(scenario["latitude"]) + jitter_lat, 5)
            incident.longitude = round(float(scenario["longitude"]) + jitter_lng, 5)
            incident.created_at = created_at
            incident.updated_at = now
            if incident.status == IncidentStatus.VERIFIED.value:
                incident.verified_at = now - timedelta(minutes=random.randint(2, 25))
            for report in incident.reports:
                if report.is_demo:
                    report.latitude = incident.latitude
                    report.longitude = incident.longitude
                    report.address = incident.address
                    report.ai_category = incident.category
                    report.ai_summary = incident.title
                    report.created_at = created_at
        db.commit()

    return public_incident_map(db=db, limit=limit)


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def incident_detail(
    incident_id: int, db: DbSession, _user: StaffUser
) -> IncidentDetailOut:
    incident = get_incident(db, incident_id)
    return incident_detail_out(
        incident,
        activity=get_incident_activity(db, incident),
        duplicates=get_incident_duplicate_candidates(db, incident),
    )


@router.patch("/{incident_id}/triage", response_model=IncidentOut)
def confirm_triage(
    incident_id: int,
    payload: IncidentTriageRequest,
    db: DbSession,
    user: OperatorUser,
) -> IncidentOut:
    incident = get_incident(db, incident_id)
    triage_incident(
        db,
        incident=incident,
        actor=user,
        category=payload.category,
        severity=payload.severity,
        note=payload.note,
    )
    return incident_out(get_incident(db, incident_id))


@router.post("/{incident_id}/priority-override", response_model=IncidentOut)
def set_priority_override(
    incident_id: int,
    payload: PriorityOverrideRequest,
    db: DbSession,
    user: OperatorUser,
) -> IncidentOut:
    incident = get_incident(db, incident_id)
    override_priority(db, incident=incident, actor=user, payload=payload)
    return incident_out(get_incident(db, incident_id))


@router.post("/{incident_id}/work-orders", response_model=WorkOrderOut)
def assign_work_order(
    incident_id: int,
    payload: WorkOrderCreateRequest,
    db: DbSession,
    user: OperatorUser,
) -> WorkOrderOut:
    incident = get_incident(db, incident_id)
    order = create_work_order(db, incident=incident, actor=user, payload=payload)
    return work_order_out(order)


@duplicate_router.post("/{candidate_id}/review", response_model=DuplicateCandidateOut)
def review_candidate(
    candidate_id: int,
    payload: DuplicateReviewRequest,
    db: DbSession,
    user: OperatorUser,
) -> DuplicateCandidateOut:
    candidate: DuplicateCandidate = review_duplicate(
        db,
        candidate_id=candidate_id,
        actor=user,
        decision=payload.decision,
        note=payload.note,
    )
    return duplicate_candidate_out(candidate)
