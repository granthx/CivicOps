"""Repeatable, clearly labelled synthetic demo data.

This module never contacts an AI provider and never presents seeded outcomes as
real municipal records.
"""

from __future__ import annotations

import io
import logging
from datetime import timedelta

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .domain import (
    Category,
    DuplicateStatus,
    IncidentStatus,
    MediaKind,
    Priority,
    Role,
    Severity,
    TriageStatus,
    WorkOrderStatus,
)
from .models import (
    AuditEvent,
    CitizenReport,
    DuplicateCandidate,
    Incident,
    Team,
    User,
    Ward,
    WorkOrder,
)
from .services.auth import hash_password
from .services.media import add_media, prepare_image
from .services.priority import apply_priority
from .utils import new_public_id, utcnow

logger = logging.getLogger(__name__)
DEMO_PASSWORD = "CivicOps!2026"
CITY = "Demo City (synthetic)"


def _audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int,
    actor: User | None,
    actor_name: str,
    actor_role: str,
    old_status: str | None,
    new_status: str | None,
    note: str,
    created_at,
    metadata: dict | None = None,
) -> None:
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
        note=note,
        actor_id=actor.id if actor else None,
        actor_name=actor_name,
        actor_role=actor_role,
        event_metadata=metadata or {},
        created_at=created_at,
    )
    db.add(event)


def _demo_image(title: str, subtitle: str, accent: tuple[int, int, int]):
    width, height = 1000, 680
    image = Image.new("RGB", (width, height), (238, 241, 238))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 110), fill=(32, 56, 47))
    draw.rectangle((70, 180, 930, 540), fill=(220, 225, 216), outline=(120, 132, 120), width=3)
    draw.ellipse((165, 215, 365, 415), fill=accent)
    draw.rounded_rectangle((500, 300, 860, 500), radius=16, fill=(178, 183, 170))
    for x, color in ((735, (193, 156, 80)), (780, (74, 102, 85)), (825, (214, 214, 202))):
        draw.rounded_rectangle((x - 24, 240, x + 24, 340), radius=8, fill=color)
    try:
        font_large = ImageFont.load_default(size=42)
        font_medium = ImageFont.load_default(size=28)
        font_small = ImageFont.load_default(size=21)
    except TypeError:
        font_large = font_medium = font_small = ImageFont.load_default()
    draw.text((70, 34), title, fill=(255, 255, 255), font=font_large)
    draw.text((70, 135), subtitle, fill=(38, 48, 42), font=font_medium)
    draw.text(
        (70, 585),
        "SYNTHETIC DEMO IMAGE - NOT REAL CITIZEN OR MUNICIPAL EVIDENCE",
        fill=(130, 43, 43),
        font=font_small,
    )
    draw.text((70, 620), "Demo City (synthetic) - CivicOps AI", fill=(85, 96, 88), font=font_small)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return prepare_image(
        buffer.getvalue(), f"{title.lower().replace(' ', '-')}.jpg", "image/jpeg"
    )


def _make_report(
    db: Session,
    *,
    ward: Ward,
    description: str,
    address: str,
    latitude: float,
    longitude: float,
    category: Category,
    severity: Severity,
    confidence: float,
    summary: str,
    indicators: list[str],
    rationale: str,
    created_at,
    citizen: User | None = None,
    reporter_name: str | None = None,
    reporter_contact: str | None = None,
    photo_title: str | None = None,
    photo_accent: tuple[int, int, int] = (97, 130, 90),
) -> CitizenReport:
    report = CitizenReport(
        public_id=new_public_id("RPT"),
        citizen_id=citizen.id if citizen else None,
        reporter_name=reporter_name,
        reporter_contact=reporter_contact,
        description=description,
        submitted_category=None,
        address=address,
        ward_id=ward.id,
        latitude=latitude,
        longitude=longitude,
        ai_status=TriageStatus.SUCCEEDED.value,
        ai_category=category.value,
        ai_severity=severity.value,
        ai_confidence=confidence,
        ai_summary=summary,
        ai_indicators=indicators,
        ai_rationale=rationale,
        ai_provider="seed-demo-review",
        ai_model=None,
        ai_fallback_used=False,
        ai_processed_at=created_at + timedelta(minutes=1),
        is_demo=True,
        created_at=created_at,
    )
    db.add(report)
    db.flush()
    if photo_title:
        prepared = _demo_image(
            photo_title,
            f"{ward.name} - synthetic citizen photo",
            photo_accent,
        )
        add_media(
            db,
            prepared=prepared,
            kind=MediaKind.REPORT_PHOTO,
            uploaded_by=citizen,
            report_id=report.id,
            is_demo=True,
        )
    _audit(
        db,
        action="report_created",
        entity_type="report",
        entity_id=report.id,
        actor=citizen,
        actor_name=citizen.name if citizen else "Anonymous citizen (demo)",
        actor_role=Role.CITIZEN.value,
        old_status=None,
        new_status=None,
        note="Synthetic report created for the demo dataset.",
        created_at=created_at,
        metadata={"report_public_id": report.public_id, "is_demo": True},
    )
    return report


def _make_incident(
    db: Session,
    *,
    report: CitizenReport,
    status: str,
    triaged_by: User | None,
    triaged_at,
    triage_notes: str | None,
    created_at,
) -> Incident:
    incident = Incident(
        public_id=new_public_id("INC"),
        title=f"{report.ai_summary[:90] if report.ai_summary else 'Waste issue'}",
        description=report.ai_summary or report.description,
        category=report.ai_category or "other_waste",
        severity=report.ai_severity or Severity.MODERATE.value,
        ward_id=report.ward_id,
        address=report.address,
        latitude=report.latitude,
        longitude=report.longitude,
        status=status,
        triaged_by_id=triaged_by.id if triaged_by else None,
        triaged_at=triaged_at,
        triage_notes=triage_notes,
        is_demo=True,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(incident)
    db.flush()
    report.incident_id = incident.id
    report.linked_at = created_at
    report.link_type = "created"
    report.link_reason = "Incident created from this synthetic report."
    apply_priority(incident, [report])
    db.add(incident)
    _audit(
        db,
        action="incident_created",
        entity_type="incident",
        entity_id=incident.id,
        actor=None,
        actor_name="CivicOps intake",
        actor_role="system",
        old_status=None,
        new_status=status,
        note="Synthetic incident created from a demo report.",
        created_at=created_at + timedelta(minutes=1),
        metadata={"incident_public_id": incident.public_id, "is_demo": True},
    )
    _audit(
        db,
        action="ai_triage_completed",
        entity_type="incident",
        entity_id=incident.id,
        actor=None,
        actor_name="AI triage service (demo record)",
        actor_role="system",
        old_status=status,
        new_status=status,
        note=report.ai_rationale,
        created_at=created_at + timedelta(minutes=2),
        metadata={
            "status": TriageStatus.SUCCEEDED.value,
            "provider": report.ai_provider,
            "confidence": report.ai_confidence,
            "human_review_required": True,
            "record_type": "synthetic seed",
        },
    )
    if triaged_by and triaged_at:
        _audit(
            db,
            action="incident_triaged",
            entity_type="incident",
            entity_id=incident.id,
            actor=triaged_by,
            actor_name=triaged_by.name,
            actor_role=triaged_by.role,
            old_status=IncidentStatus.OPEN.value,
            new_status=status,
            note=triage_notes or "Operator confirmed triage in the demo workflow.",
            created_at=triaged_at,
            metadata={"is_demo": True},
        )
    return incident


def _add_work_order(
    db: Session,
    *,
    incident: Incident,
    team: Team,
    operator: User,
    status: str,
    instructions: str,
    created_at,
    completion_note: str | None = None,
    verified_at=None,
    before_photo: tuple[str, tuple[int, int, int]] | None = None,
    after_photo: tuple[str, tuple[int, int, int]] | None = None,
) -> WorkOrder:
    order = WorkOrder(
        public_id=new_public_id("WO"),
        incident_id=incident.id,
        team_id=team.id,
        created_by_id=operator.id,
        instructions=instructions,
        due_at=created_at + timedelta(days=2),
        status=status,
        completion_note=completion_note,
        completed_at=created_at + timedelta(hours=8)
        if status in {WorkOrderStatus.COMPLETED.value, WorkOrderStatus.VERIFIED.value}
        else None,
        verified_at=verified_at,
        is_demo=True,
        created_at=created_at,
        updated_at=verified_at or created_at,
    )
    db.add(order)
    db.flush()

    _audit(
        db,
        action="work_order_created",
        entity_type="work_order",
        entity_id=order.id,
        actor=operator,
        actor_name=operator.name,
        actor_role=operator.role,
        old_status=None,
        new_status=WorkOrderStatus.ASSIGNED.value,
        note=instructions,
        created_at=created_at,
        metadata={
            "work_order_public_id": order.public_id,
            "incident_public_id": incident.public_id,
            "team": team.name,
            "is_demo": True,
        },
    )
    _audit(
        db,
        action="work_order_accepted",
        entity_type="work_order",
        entity_id=order.id,
        actor=None,
        actor_name=f"{team.name} lead (demo)",
        actor_role=Role.FIELD_WORKER.value,
        old_status=WorkOrderStatus.ASSIGNED.value,
        new_status=WorkOrderStatus.ACCEPTED.value,
        note="Demo crew accepted the assignment.",
        created_at=created_at + timedelta(minutes=35),
    )
    _audit(
        db,
        action="work_order_start",
        entity_type="work_order",
        entity_id=order.id,
        actor=None,
        actor_name=f"{team.name} lead (demo)",
        actor_role=Role.FIELD_WORKER.value,
        old_status=WorkOrderStatus.ACCEPTED.value,
        new_status=WorkOrderStatus.IN_PROGRESS.value,
        note="Demo crew started work."
        if status != WorkOrderStatus.BLOCKED.value
        else "Demo crew started work, then reported a site access issue.",
        created_at=created_at + timedelta(hours=1),
    )

    if before_photo:
        title, accent = before_photo
        asset = add_media(
            db,
            prepared=_demo_image(title, f"{team.name} - synthetic before-photo", accent),
            kind=MediaKind.BEFORE_PHOTO,
            uploaded_by=None,
            work_order_id=order.id,
            is_demo=True,
        )
        _audit(
            db,
            action="evidence_added",
            entity_type="work_order",
            entity_id=order.id,
            actor=None,
            actor_name=f"{team.name} lead (demo)",
            actor_role=Role.FIELD_WORKER.value,
            old_status=WorkOrderStatus.IN_PROGRESS.value,
            new_status=WorkOrderStatus.IN_PROGRESS.value,
            note="Synthetic before-photo attached.",
            created_at=created_at + timedelta(hours=2),
            metadata={"media_id": asset.id, "kind": MediaKind.BEFORE_PHOTO.value},
        )
    if after_photo:
        title, accent = after_photo
        asset = add_media(
            db,
            prepared=_demo_image(title, f"{team.name} - synthetic after-photo", accent),
            kind=MediaKind.AFTER_PHOTO,
            uploaded_by=None,
            work_order_id=order.id,
            is_demo=True,
        )
        _audit(
            db,
            action="evidence_added",
            entity_type="work_order",
            entity_id=order.id,
            actor=None,
            actor_name=f"{team.name} lead (demo)",
            actor_role=Role.FIELD_WORKER.value,
            old_status=WorkOrderStatus.IN_PROGRESS.value,
            new_status=WorkOrderStatus.IN_PROGRESS.value,
            note="Synthetic after-photo attached.",
            created_at=created_at + timedelta(hours=7),
            metadata={"media_id": asset.id, "kind": MediaKind.AFTER_PHOTO.value},
        )
        _audit(
            db,
            action="work_order_complete",
            entity_type="work_order",
            entity_id=order.id,
            actor=None,
            actor_name=f"{team.name} lead (demo)",
            actor_role=Role.FIELD_WORKER.value,
            old_status=WorkOrderStatus.IN_PROGRESS.value,
            new_status=WorkOrderStatus.COMPLETED.value,
            note=completion_note,
            created_at=created_at + timedelta(hours=8),
        )

    if status == WorkOrderStatus.BLOCKED.value:
        _audit(
            db,
            action="work_order_block",
            entity_type="work_order",
            entity_id=order.id,
            actor=None,
            actor_name=f"{team.name} lead (demo)",
            actor_role=Role.FIELD_WORKER.value,
            old_status=WorkOrderStatus.IN_PROGRESS.value,
            new_status=WorkOrderStatus.BLOCKED.value,
            note="Site gate was locked. Demo crew requested operator support.",
            created_at=created_at + timedelta(hours=3),
        )
    if status == WorkOrderStatus.VERIFIED.value and verified_at:
        _audit(
            db,
            action="work_order_verify",
            entity_type="work_order",
            entity_id=order.id,
            actor=operator,
            actor_name=operator.name,
            actor_role=operator.role,
            old_status=WorkOrderStatus.COMPLETED.value,
            new_status=WorkOrderStatus.VERIFIED.value,
            note="Operator verified the synthetic after-photo and closed the work order.",
            created_at=verified_at,
        )
    return order


def seed_demo_data(db: Session, *, force: bool = False) -> bool:
    if not force:
        existing = db.scalar(select(func.count(User.id))) or 0
        if existing:
            return False

    now = utcnow()
    password_hash = hash_password(DEMO_PASSWORD)

    wards = {
        "central": Ward(name="Central Market Ward", code="W-01", city=CITY),
        "lakeview": Ward(name="Lakeview Ward", code="W-02", city=CITY),
        "east": Ward(name="Industrial East Ward", code="W-03", city=CITY),
        "connaught": Ward(name="Connaught Place Ward", code="DL-01", city="New Delhi"),
        "lajpat": Ward(name="Lajpat Nagar Ward", code="DL-02", city="New Delhi"),
    }
    db.add_all(wards.values())
    db.flush()

    teams = {
        "central": Team(
            name="Central Sanitation Crew A", ward_id=wards["central"].id, team_type="sanitation"
        ),
        "lakeview": Team(
            name="Lakeview Sanitation Crew B", ward_id=wards["lakeview"].id, team_type="sanitation"
        ),
        "east": Team(
            name="Industrial East Response Crew", ward_id=wards["east"].id, team_type="sanitation"
        ),
        "delhi": Team(
            name="New Delhi Sanitation Crew C", ward_id=wards["connaught"].id, team_type="sanitation"
        ),
    }
    db.add_all(teams.values())
    db.flush()

    admin = User(
        name="Demo Admin",
        email="demo.admin@civicops.local",
        password_hash=password_hash,
        role=Role.ADMIN.value,
        is_demo=True,
    )
    operator = User(
        name="Demo Operator",
        email="demo.operator@civicops.local",
        password_hash=password_hash,
        role=Role.OPERATOR.value,
        is_demo=True,
    )
    field_worker = User(
        name="Demo Field Crew Lead",
        email="demo.field@civicops.local",
        password_hash=password_hash,
        role=Role.FIELD_WORKER.value,
        team_id=teams["central"].id,
        is_demo=True,
    )
    citizen = User(
        name="Demo Citizen",
        email="demo.citizen@civicops.local",
        password_hash=password_hash,
        role=Role.CITIZEN.value,
        is_demo=True,
    )
    db.add_all([admin, operator, field_worker, citizen])
    db.flush()

    # Two unmerged reports that the operator can consolidate during the demo.
    report_a1 = _make_report(
        db,
        ward=wards["central"],
        citizen=citizen,
        reporter_name="Demo Citizen",
        reporter_contact="demo.citizen@example.invalid",
        description=(
            "Garbage is piling up beside the community bin on 4th Cross. It has been "
            "there for three days and the bin is overflowing."
        ),
        address="4th Cross, near community bin, Central Market Ward",
        latitude=12.97110,
        longitude=77.59415,
        category=Category.OVERFLOWING_BIN,
        severity=Severity.HIGH,
        confidence=0.84,
        summary=(
            "Garbage has accumulated beside an overflowing community bin for three days."
        ),
        indicators=["overflowing bin", "waste beside bin", "three-day accumulation"],
        rationale=(
            "The report explicitly describes overflow and several days of accumulation. "
            "The location comes from the supplied map pin, not the photo."
        ),
        created_at=now - timedelta(hours=27),
        photo_title="Overflowing community bin",
        photo_accent=(137, 105, 70),
    )
    incident_a = _make_incident(
        db,
        report=report_a1,
        status=IncidentStatus.OPEN.value,
        triaged_by=None,
        triaged_at=None,
        triage_notes=None,
        created_at=report_a1.created_at,
    )

    report_a2 = _make_report(
        db,
        ward=wards["central"],
        reporter_name="Anonymous demo resident",
        description=(
            "The community garbage bin near 4th Cross is full and trash is spilling "
            "onto the footpath. Collection appears to have been missed."
        ),
        address="4th Cross footpath, Central Market Ward",
        latitude=12.97155,
        longitude=77.59452,
        category=Category.OVERFLOWING_BIN,
        severity=Severity.HIGH,
        confidence=0.79,
        summary="A full community bin is spilling waste onto the footpath.",
        indicators=["full bin", "spill onto footpath", "possible missed collection"],
        rationale=(
            "The text describes a full bin and spill. It does not establish whether one "
            "or multiple crews are responsible."
        ),
        created_at=now - timedelta(hours=11),
        photo_title="Waste beside community bin",
        photo_accent=(121, 112, 78),
    )
    incident_b = _make_incident(
        db,
        report=report_a2,
        status=IncidentStatus.OPEN.value,
        triaged_by=None,
        triaged_at=None,
        triage_notes=None,
        created_at=report_a2.created_at,
    )
    duplicate_pending = DuplicateCandidate(
        report_id=report_a2.id,
        candidate_report_id=report_a1.id,
        candidate_incident_id=incident_a.id,
        score=86.4,
        distance_m=58.7,
        reasons=[
            "59 m apart, within the 300 m search radius.",
            "Same suggested category (overflowing bin).",
            "74% description similarity.",
            "Reported 16.0 hours apart (strong candidate).",
        ],
        status=DuplicateStatus.SUGGESTED.value,
        created_at=now - timedelta(hours=10, minutes=58),
    )
    db.add(duplicate_pending)
    _audit(
        db,
        action="duplicate_suggestions_created",
        entity_type="incident",
        entity_id=incident_b.id,
        actor=None,
        actor_name="Duplicate detection service",
        actor_role="system",
        old_status=IncidentStatus.OPEN.value,
        new_status=IncidentStatus.OPEN.value,
        note="One duplicate candidate requires human review.",
        created_at=now - timedelta(hours=10, minutes=58),
        metadata={"count": 1, "is_demo": True},
    )

    # Active field work in the demo field worker's team.
    report_c = _make_report(
        db,
        ward=wards["central"],
        reporter_name="Synthetic resident C",
        description=(
            "The collection vehicle has not arrived for the market lane for two days. "
            "Waste bags are now blocking the service entrance."
        ),
        address="Market service lane, Central Market Ward",
        latitude=12.97210,
        longitude=77.59500,
        category=Category.MISSED_COLLECTION,
        severity=Severity.HIGH,
        confidence=0.81,
        summary="Two days of missed collection are blocking a market service entrance.",
        indicators=["missed collection", "two-day delay", "blocked service entrance"],
        rationale="The report describes a missed collection and access obstruction.",
        created_at=now - timedelta(hours=35),
        photo_title="Missed collection point",
        photo_accent=(107, 117, 83),
    )
    incident_c = _make_incident(
        db,
        report=report_c,
        status=IncidentStatus.IN_PROGRESS.value,
        triaged_by=operator,
        triaged_at=now - timedelta(hours=32),
        triage_notes="Confirmed missed collection. Priority retained for market access.",
        created_at=report_c.created_at,
    )
    order_c = _add_work_order(
        db,
        incident=incident_c,
        team=teams["central"],
        operator=operator,
        status=WorkOrderStatus.IN_PROGRESS.value,
        instructions=(
            "Clear the accumulated bags from the market service entrance, inspect the "
            "collection schedule, and upload an after-photo."
        ),
        created_at=now - timedelta(hours=30),
        before_photo=("Market service lane before clearance", (125, 112, 82)),
    )

    # Work completed and awaiting human verification.
    report_d = _make_report(
        db,
        ward=wards["lakeview"],
        reporter_name="Synthetic resident D",
        description=(
            "Construction debris and household waste have been dumped along the lake "
            "walking path. Sharp pieces are visible near the railing."
        ),
        address="Lakeview walking path, north railing",
        latitude=12.96020,
        longitude=77.58480,
        category=Category.ILLEGAL_DUMPING,
        severity=Severity.CRITICAL,
        confidence=0.9,
        summary="Dumped construction and household waste includes visible sharp pieces.",
        indicators=["construction debris", "household waste", "sharp pieces"],
        rationale=(
            "The description mentions sharp material, so severity is elevated. "
            "The operator must verify the hazard claim."
        ),
        created_at=now - timedelta(hours=20),
        photo_title="Dumping beside lake path",
        photo_accent=(119, 99, 81),
    )
    incident_d = _make_incident(
        db,
        report=report_d,
        status=IncidentStatus.VERIFICATION_PENDING.value,
        triaged_by=operator,
        triaged_at=now - timedelta(hours=18),
        triage_notes="Hazard note confirmed for planning; no injury reported.",
        created_at=report_d.created_at,
    )
    order_d = _add_work_order(
        db,
        incident=incident_d,
        team=teams["lakeview"],
        operator=operator,
        status=WorkOrderStatus.COMPLETED.value,
        instructions=(
            "Remove the dumped debris, isolate sharp material for safe handling, and "
            "photograph the cleared path."
        ),
        created_at=now - timedelta(hours=17),
        completion_note="Debris removed and path swept. Sharp material bagged separately.",
        before_photo=("Lake path dumping before", (119, 100, 79)),
        after_photo=("Lake path after clearance", (76, 121, 96)),
    )

    # A verified historical case with two preserved source reports.
    report_e1 = _make_report(
        db,
        ward=wards["east"],
        reporter_name="Synthetic resident E1",
        description=(
            "The industrial canteen bin is overflowing again and waste is blowing into "
            "the storm drain."
        ),
        address="Canteen corner, Industrial East Ward",
        latitude=12.98020,
        longitude=77.61110,
        category=Category.OVERFLOWING_BIN,
        severity=Severity.HIGH,
        confidence=0.83,
        summary="An overflowing canteen bin is discharging waste toward a storm drain.",
        indicators=["overflowing bin", "wind-blown waste", "storm drain"],
        rationale="The report names a storm drain, so containment matters.",
        created_at=now - timedelta(days=4, hours=2),
        photo_title="Overflowing canteen bin",
        photo_accent=(129, 112, 73),
    )
    incident_e = _make_incident(
        db,
        report=report_e1,
        status=IncidentStatus.VERIFIED.value,
        triaged_by=operator,
        triaged_at=now - timedelta(days=4),
        triage_notes="Duplicate risk near canteen confirmed for follow-up.",
        created_at=report_e1.created_at,
    )
    report_e2 = _make_report(
        db,
        ward=wards["east"],
        reporter_name="Synthetic resident E2",
        description=(
            "Waste from the canteen bins is overflowing and blowing into the drain "
            "behind the industrial unit."
        ),
        address="Rear drain, canteen, Industrial East Ward",
        latitude=12.98042,
        longitude=77.61135,
        category=Category.OVERFLOWING_BIN,
        severity=Severity.HIGH,
        confidence=0.77,
        summary="Canteen waste is overflowing and entering the rear drain.",
        indicators=["overflowing bins", "waste near drain"],
        rationale="Text overlaps strongly with an existing canteen-bin report.",
        created_at=now - timedelta(days=3, hours=20),
    )
    report_e2.incident_id = incident_e.id
    report_e2.linked_at = now - timedelta(days=3, hours=19)
    report_e2.linked_by_id = operator.id
    report_e2.link_type = "confirmed_duplicate"
    report_e2.link_reason = "Operator confirmed these reports describe one canteen-bin incident."
    duplicate_accepted = DuplicateCandidate(
        report_id=report_e2.id,
        candidate_report_id=report_e1.id,
        candidate_incident_id=incident_e.id,
        score=88.2,
        distance_m=37.4,
        reasons=[
            "37 m apart, within the 300 m search radius.",
            "Same suggested category (overflowing bin).",
            "82% description similarity.",
            "Reported 6.0 hours apart (strong candidate).",
        ],
        status=DuplicateStatus.ACCEPTED.value,
        reviewed_by_id=operator.id,
        reviewed_at=now - timedelta(days=3, hours=19),
        review_note="Confirmed. Both reports preserve their own photos and reporter details.",
        created_at=now - timedelta(days=3, hours=19, minutes=30),
    )
    db.add(duplicate_accepted)
    _audit(
        db,
        action="report_linked",
        entity_type="incident",
        entity_id=incident_e.id,
        actor=operator,
        actor_name=operator.name,
        actor_role=operator.role,
        old_status=IncidentStatus.OPEN.value,
        new_status=IncidentStatus.VERIFIED.value,
        note="Synthetic duplicate reports consolidated; both source reports preserved.",
        created_at=now - timedelta(days=3, hours=19),
        metadata={
            "report_public_id": report_e2.public_id,
            "source_incident_public_id": "merged demo source",
            "is_demo": True,
        },
    )
    apply_priority(incident_e, [report_e1, report_e2])
    incident_e.verified_at = now - timedelta(days=2)
    order_e = _add_work_order(
        db,
        incident=incident_e,
        team=teams["east"],
        operator=operator,
        status=WorkOrderStatus.VERIFIED.value,
        instructions=(
            "Clear the canteen waste, protect the storm drain, and provide before and "
            "after evidence."
        ),
        created_at=now - timedelta(days=3, hours=16),
        completion_note="Canteen waste removed and drain mouth cleared. Area disinfected.",
        verified_at=now - timedelta(days=2),
        before_photo=("Canteen bin before clearance", (132, 111, 72)),
        after_photo=("Canteen area after clearance", (79, 125, 98)),
    )

    # A blocked task that needs operator attention.
    report_f = _make_report(
        db,
        ward=wards["east"],
        reporter_name="Synthetic resident F",
        description=(
            "A large pile of mixed waste has appeared behind the closed depot. The gate "
            "is locked and the pile is growing."
        ),
        address="Rear depot gate, Industrial East Ward",
        latitude=12.97920,
        longitude=77.60950,
        category=Category.GARBAGE_ACCUMULATION,
        severity=Severity.HIGH,
        confidence=0.8,
        summary="A growing mixed-waste pile is behind a locked depot gate.",
        indicators=["large mixed-waste pile", "locked access", "recurring location"],
        rationale="Text supports a large accumulation and an access constraint.",
        created_at=now - timedelta(hours=42),
        photo_title="Waste pile behind depot",
        photo_accent=(118, 104, 76),
    )
    incident_f = _make_incident(
        db,
        report=report_f,
        status=IncidentStatus.BLOCKED.value,
        triaged_by=operator,
        triaged_at=now - timedelta(hours=40),
        triage_notes="Access constraint noted. Crew requested depot key.",
        created_at=report_f.created_at,
    )
    order_f = _add_work_order(
        db,
        incident=incident_f,
        team=teams["east"],
        operator=operator,
        status=WorkOrderStatus.BLOCKED.value,
        instructions=(
            "Clear the mixed waste behind the depot only after safe site access is "
            "confirmed by the operator."
        ),
        created_at=now - timedelta(hours=38),
        before_photo=("Depot gate waste pile", (117, 103, 77)),
    )

    # Delhi synthetic incidents (New Delhi wards alongside Bengaluru demo data).
    report_g = _make_report(
        db,
        ward=wards["connaught"],
        reporter_name="Synthetic resident G",
        description=(
            "Overflowing public dustbin outside Rajiv Chowk Metro Gate 4 is spilling "
            "plastic waste onto the pedestrian walkway."
        ),
        address="Outer Circle, near Gate 4, Connaught Place Ward, New Delhi",
        latitude=28.63150,
        longitude=77.21670,
        category=Category.OVERFLOWING_BIN,
        severity=Severity.HIGH,
        confidence=0.88,
        summary="Overflowing bin near Rajiv Chowk Gate 4 spilling onto walkway.",
        indicators=["overflowing public bin", "pedestrian walkway obstruction"],
        rationale="Clear overflowing bin report at a high-footfall metro exit.",
        created_at=now - timedelta(hours=3),
        photo_title="Connaught Place overflowing bin",
        photo_accent=(140, 95, 58),
    )
    _make_incident(
        db,
        report=report_g,
        status=IncidentStatus.OPEN.value,
        triaged_by=None,
        triaged_at=None,
        triage_notes=None,
        created_at=report_g.created_at,
    )

    report_h = _make_report(
        db,
        ward=wards["lajpat"],
        reporter_name="Synthetic resident H",
        description=(
            "Morning garbage collection has been skipped for two days in Lajpat Nagar "
            "Central Market lane; bags are piling up beside shop shutters."
        ),
        address="Central Market Service Lane, Lajpat Nagar Ward, New Delhi",
        latitude=28.56770,
        longitude=77.24330,
        category=Category.MISSED_COLLECTION,
        severity=Severity.MODERATE,
        confidence=0.85,
        summary="Two days of missed collection in Lajpat Nagar market lane.",
        indicators=["missed collection", "shopfront waste bags"],
        rationale="Multiple missed pickup cycles reported along market lane.",
        created_at=now - timedelta(hours=18),
        photo_title="Lajpat Nagar missed collection",
        photo_accent=(112, 92, 64),
    )
    incident_h = _make_incident(
        db,
        report=report_h,
        status=IncidentStatus.IN_PROGRESS.value,
        triaged_by=operator,
        triaged_at=now - timedelta(hours=16),
        triage_notes="Triaged for New Delhi afternoon compactor route.",
        created_at=report_h.created_at,
    )
    _add_work_order(
        db,
        incident=incident_h,
        team=teams["delhi"],
        operator=operator,
        status=WorkOrderStatus.IN_PROGRESS.value,
        instructions="Clear accumulated bags along Central Market service lane and confirm pickup.",
        created_at=now - timedelta(hours=15),
        before_photo=("Lajpat Nagar market lane before pickup", (112, 92, 64)),
    )

    report_i = _make_report(
        db,
        ward=wards["connaught"],
        reporter_name="Synthetic resident I",
        description=(
            "Dumped cardboard and market garbage accumulated near Janpath parking bay "
            "has been reported for clearance."
        ),
        address="Janpath Lane Parking Bay, Connaught Place Ward, New Delhi",
        latitude=28.62890,
        longitude=77.21920,
        category=Category.GARBAGE_ACCUMULATION,
        severity=Severity.MODERATE,
        confidence=0.82,
        summary="Accumulated market waste near Janpath parking bay.",
        indicators=["cardboard pile", "parking bay accumulation"],
        rationale="Localized commercial waste accumulation.",
        created_at=now - timedelta(days=2),
        photo_title="Janpath garbage accumulation",
        photo_accent=(126, 108, 78),
    )
    incident_i = _make_incident(
        db,
        report=report_i,
        status=IncidentStatus.VERIFIED.value,
        triaged_by=operator,
        triaged_at=now - timedelta(days=1, hours=20),
        triage_notes="Cleared and verified by New Delhi inspection.",
        created_at=report_i.created_at,
    )
    incident_i.verified_at = now - timedelta(days=1)
    _add_work_order(
        db,
        incident=incident_i,
        team=teams["delhi"],
        operator=operator,
        status=WorkOrderStatus.VERIFIED.value,
        instructions="Remove dumped cardboard and sweep Janpath parking bay.",
        created_at=now - timedelta(days=1, hours=18),
        completion_note="Waste cleared and bay swept.",
        verified_at=now - timedelta(days=1),
        before_photo=("Janpath bay before clearance", (126, 108, 78)),
        after_photo=("Janpath bay after clearance", (78, 124, 96)),
    )

    # Keep incident status/updated timestamps aligned with the final demo state.
    for incident, status, updated in (
        (incident_c, IncidentStatus.IN_PROGRESS.value, now - timedelta(hours=14)),
        (incident_d, IncidentStatus.VERIFICATION_PENDING.value, now - timedelta(hours=5)),
        (incident_e, IncidentStatus.VERIFIED.value, incident_e.verified_at),
        (incident_f, IncidentStatus.BLOCKED.value, now - timedelta(hours=7)),
        (incident_h, IncidentStatus.IN_PROGRESS.value, now - timedelta(hours=12)),
        (incident_i, IncidentStatus.VERIFIED.value, incident_i.verified_at),
    ):
        incident.status = status
        incident.updated_at = updated or now
        apply_priority(incident, list(incident.reports) if incident.reports else [])
        db.add(incident)

    db.commit()
    logger.info("Seeded synthetic CivicOps demo data with password %s", DEMO_PASSWORD)
    return True
