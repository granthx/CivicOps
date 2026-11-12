"""Reusable FastAPI authentication and authorisation dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .domain import Role
from .errors import ForbiddenError, UnauthorizedError
from .models import User
from .services.auth import resolve_session

bearer_scheme = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return resolve_session(db, credentials.credentials)


def get_current_user(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> User:
    if user is None:
        raise UnauthorizedError()
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = {role.value for role in roles}

    def dependency(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed:
            raise ForbiddenError()
        return user

    return dependency


require_staff = require_roles(Role.OPERATOR, Role.ADMIN)
require_operator = require_roles(Role.OPERATOR, Role.ADMIN)
require_field_or_staff = require_roles(Role.FIELD_WORKER, Role.OPERATOR, Role.ADMIN)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
StaffUser = Annotated[User, Depends(require_staff)]
OperatorUser = Annotated[User, Depends(require_operator)]
FieldOrStaffUser = Annotated[User, Depends(require_field_or_staff)]
