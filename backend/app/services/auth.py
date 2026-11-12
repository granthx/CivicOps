"""Password and opaque session-token handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuthSession, User
from ..utils import utcnow

def hash_password(password: str) -> str:
    iterations = settings.password_iterations
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(40)
    auth_session = AuthSession(
        token_hash=_token_hash(token),
        user_id=user.id,
        expires_at=utcnow() + timedelta(hours=settings.session_hours),
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return token, auth_session


def resolve_session(db: Session, token: str) -> User | None:
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _token_hash(token))
    )
    if auth_session is None or auth_session.expires_at <= utcnow():
        return None
    user = db.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(db: Session, token: str) -> None:
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _token_hash(token))
    )
    if auth_session is not None:
        db.delete(auth_session)
        db.commit()
