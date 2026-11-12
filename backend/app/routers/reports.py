"""Citizen report intake and public tracking routes."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile, status

from ..config import settings
from ..deps import DbSession, OptionalUser, StaffUser
from ..schemas import (
    CitizenFeedbackCreate,
    DuplicateCandidateOut,
    PublicReportStatusOut,
    ReportCreate,
    ReportSubmissionOut,
)
from ..serializers import duplicate_candidate_out, incident_out, report_out
from ..services.media import prepare_audio, prepare_image
from ..services.rate_limit import enforce_report_rate_limit
from ..services.reports import (
    create_report,
    get_candidates_for_report,
    get_report_by_public_id,
    submit_citizen_feedback,
    track_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportSubmissionOut, status_code=status.HTTP_201_CREATED)
def submit_report(
    request: Request,
    db: DbSession,
    user: OptionalUser,
    latitude: float = Form(...),
    longitude: float = Form(...),
    ward_id: int = Form(...),
    description: str = Form(default=""),
    address: str | None = Form(default=None),
    submitted_category: str | None = Form(default=None),
    preferred_language: str | None = Form(default=None),
    reporter_name: str | None = Form(default=None),
    reporter_contact: str | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    audio: UploadFile | None = File(default=None),
) -> ReportSubmissionOut:
    client_key = request.client.host if request.client else "unknown"
    enforce_report_rate_limit(client_key, settings.public_report_rate_limit_per_hour)

    payload = ReportCreate(
        description=description,
        latitude=latitude,
        longitude=longitude,
        ward_id=ward_id,
        address=address or None,
        submitted_category=submitted_category or None,
        preferred_language=preferred_language or None,
        has_audio=audio is not None,
        reporter_name=reporter_name or None,
        reporter_contact=reporter_contact or None,
    )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    prepared = None
    if photo is not None:
        raw = photo.file.read(max_bytes + 1)
        prepared = prepare_image(
            raw,
            photo.filename,
            photo.content_type,
            max_bytes=max_bytes,
        )

    prepared_audio = None
    if audio is not None:
        raw_audio = audio.file.read(max_bytes + 1)
        prepared_audio = prepare_audio(
            raw_audio,
            audio.filename,
            audio.content_type,
            max_bytes=max_bytes,
        )

    report, incident, candidates, warnings = create_report(
        db,
        payload=payload,
        actor=user,
        prepared_image=prepared,
        prepared_audio=prepared_audio,
    )
    return ReportSubmissionOut(
        report=report_out(report, include_private=False),
        incident=incident_out(incident),
        duplicate_candidates=[duplicate_candidate_out(item) for item in candidates],
        warnings=warnings,
    )


@router.get("/{public_id}/status", response_model=PublicReportStatusOut)
def public_report_status(public_id: str, db: DbSession) -> PublicReportStatusOut:
    return track_report(db, public_id)


@router.post("/{public_id}/feedback", response_model=PublicReportStatusOut)
def public_report_feedback(
    public_id: str,
    payload: CitizenFeedbackCreate,
    db: DbSession,
) -> PublicReportStatusOut:
    return submit_citizen_feedback(db, public_id, payload)


@router.get("/{public_id}/duplicate-candidates", response_model=list[DuplicateCandidateOut])
def report_duplicates(
    public_id: str, db: DbSession, _user: StaffUser
) -> list[DuplicateCandidateOut]:
    report = get_report_by_public_id(db, public_id)
    return [
        duplicate_candidate_out(candidate)
        for candidate in get_candidates_for_report(db, report.id)
    ]
