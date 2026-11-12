"""Field-team work-order endpoints and evidence upload."""

from __future__ import annotations

import math

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..config import settings
from ..deps import DbSession, FieldOrStaffUser
from ..domain import MediaKind, Role, WorkOrderStatus
from ..errors import ValidationError
from ..models import CitizenReport, Incident, Team, WorkOrder
from ..schemas import (
    MediaOut,
    WorkOrderDetailOut,
    WorkOrderPage,
    WorkOrderTransitionRequest,
    WorkOrderOut,
)
from ..serializers import media_out, work_order_detail_out, work_order_out
from ..services.media import prepare_image
from ..services.work_orders import (
    add_work_order_evidence,
    ensure_work_order_access,
    get_work_order,
    get_work_order_activity,
    transition_work_order,
)

router = APIRouter(prefix="/work-orders", tags=["work orders"])


def _list_options():
    return (
        selectinload(WorkOrder.team),
        selectinload(WorkOrder.evidence),
        selectinload(WorkOrder.incident).selectinload(Incident.ward),
    )


@router.get("", response_model=WorkOrderPage)
def list_work_orders(
    db: DbSession,
    user: FieldOrStaffUser,
    status_filters: list[WorkOrderStatus] = Query(default=[], alias="status"),
    include_verified: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> WorkOrderPage:
    conditions = []
    if user.role == Role.FIELD_WORKER.value:
        if user.team_id is None:
            return WorkOrderPage(items=[], total=0, page=page, page_size=page_size, pages=0)
        conditions.append(WorkOrder.team_id == user.team_id)
    if status_filters:
        conditions.append(WorkOrder.status.in_([value.value for value in status_filters]))
    elif not include_verified:
        conditions.append(WorkOrder.status != WorkOrderStatus.VERIFIED.value)

    total = db.scalar(select(func.count(WorkOrder.id)).where(*conditions)) or 0
    orders = list(
        db.scalars(
            select(WorkOrder)
            .where(*conditions)
            .options(*_list_options())
            .order_by(
                WorkOrder.due_at.is_(None),
                WorkOrder.due_at.asc(),
                WorkOrder.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return WorkOrderPage(
        items=[work_order_out(order) for order in orders],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{work_order_id}", response_model=WorkOrderDetailOut)
def work_order_detail(
    work_order_id: int, db: DbSession, user: FieldOrStaffUser
) -> WorkOrderDetailOut:
    order = get_work_order(db, work_order_id)
    ensure_work_order_access(order, user)
    return work_order_detail_out(
        order, activity=get_work_order_activity(db, order)
    )


@router.post("/{work_order_id}/transition", response_model=WorkOrderOut)
def update_work_order(
    work_order_id: int,
    payload: WorkOrderTransitionRequest,
    db: DbSession,
    user: FieldOrStaffUser,
) -> WorkOrderOut:
    order = get_work_order(db, work_order_id)
    updated = transition_work_order(db, order=order, actor=user, payload=payload)
    return work_order_out(updated)


@router.post("/{work_order_id}/evidence", response_model=MediaOut)
def upload_work_order_evidence(
    work_order_id: int,
    db: DbSession,
    user: FieldOrStaffUser,
    kind: str = Form(...),
    photo: UploadFile = File(...),
) -> MediaOut:
    order = get_work_order(db, work_order_id)
    ensure_work_order_access(order, user)
    try:
        media_kind = MediaKind(kind)
    except ValueError as exc:
        raise ValidationError("Evidence kind must be before_photo or after_photo.") from exc
    if media_kind not in {MediaKind.BEFORE_PHOTO, MediaKind.AFTER_PHOTO}:
        raise ValidationError("Evidence kind must be before_photo or after_photo.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    raw = photo.file.read(max_bytes + 1)
    prepared = prepare_image(
        raw, photo.filename, photo.content_type, max_bytes=max_bytes
    )
    asset = add_work_order_evidence(
        db,
        order=order,
        actor=user,
        prepared=prepared,
        kind=media_kind,
        original_filename=photo.filename,
    )
    return media_out(asset)
