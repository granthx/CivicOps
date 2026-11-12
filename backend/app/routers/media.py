"""Authenticated access to controlled local media."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, DbSession
from ..errors import NotFoundError
from ..models import CitizenReport, Incident, MediaAsset, User, WorkOrder
from ..services.media import ensure_media_access, storage_path

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{media_id}")
def get_media(
    media_id: int, db: DbSession, user: CurrentUser
) -> FileResponse:
    media = db.scalar(
        select(MediaAsset)
        .where(MediaAsset.id == media_id)
        .options(
            selectinload(MediaAsset.report)
            .selectinload(CitizenReport.incident)
            .selectinload(Incident.work_orders),
            selectinload(MediaAsset.work_order),
        )
    )
    if media is None:
        raise NotFoundError("Media not found.")
    ensure_media_access(media, user)
    path = storage_path(media.storage_key)
    if not path.exists():
        raise NotFoundError("Media file not found on disk.")
    return FileResponse(
        path,
        media_type=media.content_type,
        filename=media.original_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=300"},
    )
