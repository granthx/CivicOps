"""Secure local media intake and access control for the MVP."""

from __future__ import annotations

import hashlib
import io
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..config import settings
from ..domain import MediaKind, Role
from ..errors import ForbiddenError, NotFoundError, ValidationError
from ..models import MediaAsset, User, WorkOrder
from ..utils import new_public_id

ALLOWED_CLAIMED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_DIMENSION = 2000

ALLOWED_AUDIO_TYPES: dict[str, str] = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


@dataclass
class PreparedImage:
    data: bytes
    original_filename: str
    content_type: str
    width: int
    height: int
    sha256: str


@dataclass
class PreparedAudio:
    data: bytes
    original_filename: str
    content_type: str
    extension: str
    sha256: str


def _safe_original_name(filename: str | None) -> str:
    name = Path(filename or "upload").name
    name = "".join(char for char in name if char.isprintable()).strip()
    return (name or "upload")[:255]


def prepare_image(
    raw: bytes,
    filename: str | None,
    claimed_content_type: str | None,
    max_bytes: int | None = None,
) -> PreparedImage:
    max_bytes = max_bytes or settings.max_upload_mb * 1024 * 1024
    if not raw:
        raise ValidationError("The uploaded image is empty.")
    if len(raw) > max_bytes:
        raise ValidationError(
            f"Image is too large. The maximum size is {settings.max_upload_mb} MB."
        )
    if claimed_content_type and claimed_content_type.lower() not in ALLOWED_CLAIMED_TYPES:
        raise ValidationError("Only JPEG, PNG or WebP images are allowed.")

    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise ValidationError("Only JPEG, PNG or WebP images are allowed.")
            if source.width * source.height > settings.max_image_pixels:
                raise ValidationError("Image dimensions are too large.")
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.mode in {"RGBA", "LA"}:
                background = Image.new("RGB", image.size, (255, 255, 255))
                alpha = image.getchannel("A")
                background.paste(image.convert("RGB"), mask=alpha)
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            clean = io.BytesIO()
            image.save(clean, format="JPEG", quality=86, optimize=True)
            data = clean.getvalue()
            width, height = image.size
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("The uploaded file is not a valid image.") from exc
    except Image.DecompressionBombError as exc:
        raise ValidationError("Image dimensions are too large.") from exc

    return PreparedImage(
        data=data,
        original_filename=_safe_original_name(filename),
        content_type="image/jpeg",
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _is_valid_audio_bytes(raw: bytes) -> bool:
    if len(raw) < 12:
        return False
    if raw.startswith(b"RIFF") and raw[8:12] == b"WAVE":
        return True
    if raw.startswith(b"OggS"):
        return True
    if raw.startswith(b"\x1a\x45\xdf\xa3"):
        return True
    if raw.startswith(b"ID3") or (raw[0] == 0xFF and (raw[1] & 0xE0) == 0xE0):
        return True
    if raw[4:8] == b"ftyp":
        return True
    return False


def prepare_audio(
    raw: bytes,
    filename: str | None,
    claimed_content_type: str | None,
    max_bytes: int | None = None,
) -> PreparedAudio:
    max_bytes = max_bytes or settings.max_upload_mb * 1024 * 1024
    if not raw or len(raw) < 32:
        raise ValidationError("The uploaded audio recording is empty or too short.")
    if len(raw) > max_bytes:
        raise ValidationError(
            f"Audio recording is too large. The maximum size is {settings.max_upload_mb} MB."
        )
    base_type = (claimed_content_type or "").split(";")[0].strip().lower()
    if base_type not in ALLOWED_AUDIO_TYPES:
        raise ValidationError(
            "Only WebM, OGG, MP3, M4A, or WAV audio recordings are allowed."
        )
    if not _is_valid_audio_bytes(raw):
        raise ValidationError("The uploaded file is not a valid audio recording.")
    return PreparedAudio(
        data=raw,
        original_filename=_safe_original_name(filename),
        content_type=base_type,
        extension=ALLOWED_AUDIO_TYPES[base_type],
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _write_stored_bytes(data: bytes, extension: str, kind: MediaKind) -> tuple[str, Path]:
    now = datetime.now(UTC)
    relative = Path(kind.value) / f"{now.year:04d}" / f"{now.month:02d}"
    storage_key = (relative / f"{secrets.token_hex(16)}{extension}").as_posix()
    destination = settings.upload_path / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, destination)
    return storage_key, destination


def write_prepared_image(prepared: PreparedImage, kind: MediaKind) -> tuple[str, Path]:
    return _write_stored_bytes(prepared.data, ".jpg", kind)


def storage_path(storage_key: str) -> Path:
    root = settings.upload_path.resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents and path != root:
        raise NotFoundError("Media file not found.")
    return path


def remove_stored_file(storage_key: str) -> None:
    try:
        storage_path(storage_key).unlink(missing_ok=True)
    except NotFoundError:
        return


def add_media(
    db: Session,
    *,
    prepared: PreparedImage | PreparedAudio,
    kind: MediaKind,
    uploaded_by: User | None,
    report_id: int | None = None,
    work_order_id: int | None = None,
    is_demo: bool = False,
) -> MediaAsset:
    if isinstance(prepared, PreparedAudio):
        storage_key, _path = _write_stored_bytes(prepared.data, prepared.extension, kind)
        width, height = 0, 0
    else:
        storage_key, _path = write_prepared_image(prepared, kind)
        width, height = prepared.width, prepared.height
    asset = MediaAsset(
        public_id=new_public_id("MED"),
        kind=kind.value,
        storage_key=storage_key,
        original_filename=prepared.original_filename,
        content_type=prepared.content_type,
        size_bytes=len(prepared.data),
        width=width,
        height=height,
        sha256=prepared.sha256,
        report_id=report_id,
        work_order_id=work_order_id,
        uploaded_by_id=uploaded_by.id if uploaded_by else None,
        is_demo=is_demo,
    )
    db.add(asset)
    return asset


def ensure_media_access(media: MediaAsset, user: User) -> None:
    if user.role in {Role.OPERATOR.value, Role.ADMIN.value}:
        return
    if user.role == Role.FIELD_WORKER.value and media.work_order_id:
        order = media.work_order
        if order is not None and order.team_id == user.team_id:
            return
    if user.role == Role.FIELD_WORKER.value and media.report is not None:
        incident = media.report.incident
        if incident is not None and any(
            order.team_id == user.team_id for order in incident.work_orders
        ):
            return
    if media.report is not None and media.report.citizen_id == user.id:
        return
    raise ForbiddenError("You do not have access to this media.")
