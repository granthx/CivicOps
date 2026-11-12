"""Demo-appropriate session authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials

from ..deps import CurrentUser, DbSession, bearer_scheme
from ..errors import UnauthorizedError
from ..schemas import LoginRequest, LoginResponse, UserOut
from ..serializers import user_out
from ..services.auth import authenticate, create_session, revoke_session
from ..utils import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    user = authenticate(db, payload.email, payload.password)
    if user is None:
        raise UnauthorizedError("Invalid email or password.")
    token, session = create_session(db, user)
    return LoginResponse(
        access_token=token,
        expires_at=session.expires_at,
        user=user_out(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.post("/logout")
def logout(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> dict[str, str]:
    if credentials:
        revoke_session(db, credentials.credentials)
    return {"status": "signed_out"}
