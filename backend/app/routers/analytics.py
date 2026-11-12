"""Dashboard analytics routes."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import DbSession, OperatorUser, StaffUser
from ..domain import IncidentStatus
from ..models import Incident
from ..schemas import AnalyticsSummaryOut, HotspotListOut, SlaSweepOut
from ..services.analytics import analytics_summary
from ..services.hotspots import detect_hotspot_clusters
from ..services.sla import compute_sla_status, sweep_sla_escalations
from ..services.telemetry import get_telemetry_snapshot

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/telemetry")
def telemetry_snapshot(_user: StaffUser) -> dict:
    return get_telemetry_snapshot()


@router.get("/summary", response_model=AnalyticsSummaryOut)
def summary(db: DbSession, _user: StaffUser) -> AnalyticsSummaryOut:
    return analytics_summary(db)


@router.get("/hotspots", response_model=HotspotListOut)
def hotspots(
    db: DbSession,
    _user: StaffUser,
    window_days: int = Query(default=30, ge=1, le=365),
    radius_m: float = Query(default=150.0, ge=25.0, le=2000.0),
    ward_id: int | None = Query(default=None, ge=1),
) -> HotspotListOut:
    return detect_hotspot_clusters(
        db,
        window_days=window_days,
        radius_m=radius_m,
        ward_id=ward_id,
    )


@router.post("/sla-sweep", response_model=SlaSweepOut)
def sla_sweep(db: DbSession, user: OperatorUser) -> SlaSweepOut:
    return sweep_sla_escalations(db, actor=user)


@router.get("/export.csv")
def export_incidents_csv(db: DbSession, _user: StaffUser) -> StreamingResponse:
    incidents = list(
        db.scalars(
            select(Incident)
            .where(Incident.status != IncidentStatus.MERGED.value)
            .options(
                selectinload(Incident.ward),
                selectinload(Incident.reports),
                selectinload(Incident.work_orders),
            )
            .order_by(Incident.created_at.desc())
        ).all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "public_id",
            "title",
            "category",
            "severity",
            "priority",
            "status",
            "ward",
            "report_count",
            "sla_state",
            "due_at",
            "citizen_avg_rating",
            "reopen_requested",
            "created_at",
            "verified_at",
        ]
    )
    for inc in incidents:
        orders = sorted(inc.work_orders, key=lambda o: o.id, reverse=True)
        active = orders[0] if orders else None
        sla = compute_sla_status(
            created_at=inc.created_at,
            due_at=active.due_at if active else None,
            priority=inc.priority,
            status=inc.status,
            verified_at=inc.verified_at,
        )
        ratings = [r.citizen_rating for r in inc.reports if r.citizen_rating is not None]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else ""
        reopen_req = any(r.citizen_reopen_requested for r in inc.reports)
        writer.writerow(
            [
                inc.public_id,
                inc.title,
                inc.category,
                inc.severity,
                inc.priority,
                inc.status,
                inc.ward.name if inc.ward else "",
                len(inc.reports),
                sla.sla_state,
                sla.due_at.isoformat(),
                avg_rating,
                "yes" if reopen_req else "no",
                inc.created_at.isoformat(),
                inc.verified_at.isoformat() if inc.verified_at else "",
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="civicops-incidents.csv"'},
    )
