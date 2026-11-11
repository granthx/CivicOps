"""Persistent domain model for CivicOps AI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .domain import (
    DuplicateStatus,
    IncidentStatus,
    Role,
    TriageStatus,
    WorkOrderStatus,
)
from .utils import utcnow


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    teams: Mapped[list[Team]] = relationship(back_populates="ward")
    incidents: Mapped[list[Incident]] = relationship(back_populates="ward")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"), nullable=False)
    team_type: Mapped[str] = mapped_column(String(50), default="sanitation", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    ward: Mapped[Ward] = relationship(back_populates="teams")
    members: Mapped[list[User]] = relationship(back_populates="team")
    work_orders: Mapped[list[WorkOrder]] = relationship(back_populates="team")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default=Role.CITIZEN.value, nullable=False)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    team: Mapped[Team | None] = relationship(back_populates="members")
    sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")
    reports: Mapped[list[CitizenReport]] = relationship(
        back_populates="citizen", foreign_keys="CitizenReport.citizen_id"
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class CitizenReport(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_incident_created", "incident_id", "created_at"),
        Index("ix_reports_created", "created_at"),
        Index("ix_reports_ward", "ward_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    citizen_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reporter_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reporter_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    voice_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    submitted_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    ai_status: Mapped[str] = mapped_column(
        String(30), default=TriageStatus.PENDING.value, nullable=False, index=True
    )
    ai_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_indicators: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ai_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id"), nullable=True, index=True
    )
    linked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    linked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    link_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_type: Mapped[str | None] = mapped_column(String(30), nullable=True)

    citizen_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citizen_feedback: Mapped[str | None] = mapped_column(String(500), nullable=True)
    citizen_feedback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    citizen_reopen_requested: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )

    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    citizen: Mapped[User | None] = relationship(
        back_populates="reports", foreign_keys=[citizen_id]
    )
    ward: Mapped[Ward] = relationship()
    incident: Mapped[Incident | None] = relationship(back_populates="reports")
    media: Mapped[list[MediaAsset]] = relationship(back_populates="report")
    duplicate_candidates: Mapped[list[DuplicateCandidate]] = relationship(
        back_populates="report", foreign_keys="DuplicateCandidate.report_id"
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status_priority", "status", "priority"),
        Index("ix_incidents_created", "created_at"),
        Index("ix_incidents_ward", "ward_id"),
        Index("ix_incidents_location", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="moderate", nullable=False)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), default=IncidentStatus.OPEN.value, nullable=False, index=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False, index=True)
    recommended_priority: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False
    )
    priority_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    priority_factors: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    priority_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority_override_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority_overridden_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    priority_overridden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    triaged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triaged_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    triage_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    merged_into_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id"), nullable=True, index=True
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    ward: Mapped[Ward] = relationship(back_populates="incidents")
    reports: Mapped[list[CitizenReport]] = relationship(
        back_populates="incident", foreign_keys="CitizenReport.incident_id"
    )
    work_orders: Mapped[list[WorkOrder]] = relationship(back_populates="incident")
    merged_into: Mapped[Incident | None] = relationship(
        remote_side="Incident.id", foreign_keys=[merged_into_id]
    )
    triaged_by: Mapped[User | None] = relationship(foreign_keys=[triaged_by_id])
    priority_overridden_by: Mapped[User | None] = relationship(
        foreign_keys=[priority_overridden_by_id]
    )


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        Index("ix_work_orders_incident_status", "incident_id", "status"),
        Index("ix_work_orders_team_status", "team_id", "status"),
        Index("ix_work_orders_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default=WorkOrderStatus.ASSIGNED.value, nullable=False, index=True
    )
    completion_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    verification_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    incident: Mapped[Incident] = relationship(back_populates="work_orders")
    team: Mapped[Team] = relationship(back_populates="work_orders")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    evidence: Mapped[list[MediaAsset]] = relationship(back_populates="work_order")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_orders.id"), nullable=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    report: Mapped[CitizenReport | None] = relationship(back_populates="media")
    work_order: Mapped[WorkOrder | None] = relationship(back_populates="evidence")
    uploaded_by: Mapped[User | None] = relationship()


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        UniqueConstraint("report_id", "candidate_report_id", name="uq_duplicate_pair"),
        Index("ix_duplicate_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), nullable=False)
    candidate_report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), nullable=False)
    candidate_incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id"), nullable=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=DuplicateStatus.SUGGESTED.value, nullable=False
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    report: Mapped[CitizenReport] = relationship(
        back_populates="duplicate_candidates", foreign_keys=[report_id]
    )
    candidate_report: Mapped[CitizenReport] = relationship(foreign_keys=[candidate_report_id])
    candidate_incident: Mapped[Incident | None] = relationship(
        foreign_keys=[candidate_incident_id]
    )
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    actor: Mapped[User | None] = relationship()
