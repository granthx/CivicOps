"""Public lookup data and operational reference endpoints."""

from __future__ import annotations

from sqlalchemy import select

from fastapi import APIRouter

from ..deps import DbSession, StaffUser
from ..models import Team, Ward
from ..schemas import TeamOut, WardOut

router = APIRouter(tags=["reference"])


@router.get("/wards", response_model=list[WardOut])
def list_wards(db: DbSession) -> list[WardOut]:
    wards = db.scalars(select(Ward).order_by(Ward.name)).all()
    return [WardOut.model_validate(ward) for ward in wards]


@router.get("/teams", response_model=list[TeamOut])
def list_teams(db: DbSession, _user: StaffUser) -> list[TeamOut]:
    teams = db.scalars(select(Team).where(Team.is_active.is_(True)).order_by(Team.name)).all()
    return [TeamOut.model_validate(team) for team in teams]
