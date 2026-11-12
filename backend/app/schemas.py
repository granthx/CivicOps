"""Validated API request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .domain import (
    Category,
    DuplicateStatus,
    IncidentStatus,
    MediaKind,
    Priority,
    Role,
    Severity,
    TriageStatus,
    WorkOrderStatus,
)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: Role
    team_id: int | None = None
    team_name: str | None = None
    is_demo: bool


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class WardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    city: str


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ward_id: int
    team_type: str
    is_active: bool


class MediaOut(BaseModel):
    id: int
    public_id: str
    kind: MediaKind
    content_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime


class ReportOut(BaseModel):
    id: int
    public_id: str
    description: str
    preferred_language: str | None = None
    voice_transcript: str | None = None
    detected_language: str | None = None
    address: str | None
    latitude: float
    longitude: float
    ward: WardOut
    submitted_category: Category | None
    ai_status: TriageStatus
    ai_category: Category | None
    ai_severity: Severity | None
    ai_confidence: float | None
    ai_summary: str | None
    ai_indicators: list[str]
    ai_rationale: str | None
    ai_provider: str | None
    ai_model: str | None
    ai_fallback_used: bool
    ai_error: str | None
    ai_processed_at: datetime | None
    incident_id: int | None
    incident_public_id: str | None
    link_type: str | None
    reporter_name: str | None = None
    reporter_contact: str | None = None
    citizen_rating: int | None = None
    citizen_feedback: str | None = None
    citizen_reopen_requested: bool = False
    is_demo: bool
    media: list[MediaOut]
    created_at: datetime


class CandidateReportOut(BaseModel):
    id: int
    public_id: str
    description: str
    latitude: float
    longitude: float
    ward_name: str
    ai_category: Category | None
    created_at: datetime
    media: list[MediaOut]


class DuplicateCandidateOut(BaseModel):
    id: int
    score: float
    distance_m: float
    reasons: list[str]
    status: DuplicateStatus
    candidate_report: CandidateReportOut
    candidate_incident_id: int | None
    candidate_incident_public_id: str | None
    candidate_incident_status: IncidentStatus | None
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime


class PriorityFactorOut(BaseModel):
    label: str
    points: float
    max_points: float
    explanation: str


class PriorityFactorsOut(BaseModel):
    score: float
    priority: Priority
    factors: list[PriorityFactorOut]
    generated_at: str


class WorkOrderBriefOut(BaseModel):
    id: int
    public_id: str
    status: WorkOrderStatus
    team_id: int
    team_name: str
    due_at: datetime | None


class SlaStatusOut(BaseModel):
    sla_state: str  # "on_track" | "at_risk" | "breached" | "met"
    due_at: datetime
    remaining_hours: float
    is_overdue: bool


class IncidentOut(BaseModel):
    id: int
    public_id: str
    title: str
    description: str
    category: Category
    severity: Severity
    status: IncidentStatus
    priority: Priority
    recommended_priority: Priority
    priority_score: float
    priority_factors: PriorityFactorsOut | None
    priority_overridden: bool
    priority_override_reason: str | None
    ward: WardOut
    address: str | None
    latitude: float
    longitude: float
    report_count: int
    active_work_order: WorkOrderBriefOut | None
    sla: SlaStatusOut | None = None
    triaged_at: datetime | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class AuditEventOut(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int
    old_status: str | None
    new_status: str | None
    note: str | None
    actor_name: str
    actor_role: str
    event_metadata: dict
    created_at: datetime


class WorkOrderIncidentOut(BaseModel):
    id: int
    public_id: str
    title: str
    description: str
    category: Category
    priority: Priority
    status: IncidentStatus
    latitude: float
    longitude: float
    address: str | None
    ward: WardOut


class WorkOrderOut(BaseModel):
    id: int
    public_id: str
    incident_id: int
    incident: WorkOrderIncidentOut
    team: TeamOut
    instructions: str
    due_at: datetime | None
    status: WorkOrderStatus
    completion_note: str | None
    verification_note: str | None
    completed_at: datetime | None
    verified_at: datetime | None
    evidence: list[MediaOut]
    sla: SlaStatusOut | None = None
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class WorkOrderDetailOut(WorkOrderOut):
    reports: list[ReportOut]
    activity: list[AuditEventOut]


class WorkOrderPage(BaseModel):
    items: list[WorkOrderOut]
    total: int
    page: int
    page_size: int
    pages: int


class IncidentDetailOut(IncidentOut):
    reports: list[ReportOut]
    work_orders: list[WorkOrderOut]
    activity: list[AuditEventOut]
    duplicate_candidates: list[DuplicateCandidateOut]


class ReportSubmissionOut(BaseModel):
    report: ReportOut
    incident: IncidentOut
    duplicate_candidates: list[DuplicateCandidateOut]
    warnings: list[str] = Field(default_factory=list)


class IncidentPage(BaseModel):
    items: list[IncidentOut]
    total: int
    page: int
    page_size: int
    pages: int


class ReportCreate(BaseModel):
    description: str = Field(default="", max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    ward_id: int
    address: str | None = Field(default=None, max_length=300)
    submitted_category: Category | None = None
    preferred_language: str | None = Field(default=None, max_length=20)
    has_audio: bool = False
    reporter_name: str | None = Field(default=None, max_length=120)
    reporter_contact: str | None = Field(default=None, max_length=255)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_location_and_content(self) -> ReportCreate:
        if not self.has_audio and len(self.description) < 10:
            raise ValueError("Please provide a little more detail (at least 10 characters).")
        if self.has_audio and not self.description:
            self.description = "Voice note complaint attached."
        if self.latitude == 0 and self.longitude == 0:
            raise ValueError("A valid location pin is required.")
        return self


class IncidentTriageRequest(BaseModel):
    category: Category | None = None
    severity: Severity | None = None
    note: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def require_change(self) -> IncidentTriageRequest:
        if self.category is None and self.severity is None:
            raise ValueError("Provide a category or severity to confirm triage.")
        return self


class PriorityOverrideRequest(BaseModel):
    priority: Priority
    reason: str = Field(min_length=10, max_length=500)


class DuplicateReviewRequest(BaseModel):
    decision: Literal["accept", "reject"]
    note: str | None = Field(default=None, max_length=500)


class WorkOrderCreateRequest(BaseModel):
    team_id: int
    instructions: str = Field(min_length=10, max_length=2000)
    due_at: datetime | None = None


class WorkOrderTransitionRequest(BaseModel):
    action: Literal[
        "accept",
        "start",
        "block",
        "resume",
        "complete",
        "verify",
        "reject_verification",
    ]
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_note_for_key_actions(self) -> WorkOrderTransitionRequest:
        if self.action in {"block", "complete", "reject_verification"} and not self.note:
            raise ValueError("A note is required for this action.")
        return self


class EvidenceKindRequest(BaseModel):
    kind: Literal[MediaKind.BEFORE_PHOTO, MediaKind.AFTER_PHOTO]


class PublicReportStatusOut(BaseModel):
    public_id: str
    submitted_at: datetime
    category: Category | None
    summary: str | None
    incident_public_id: str | None
    incident_status: IncidentStatus | None
    verified_at: datetime | None = None
    sla_state: str | None = None
    due_at: datetime | None = None
    citizen_rating: int | None = None
    citizen_feedback: str | None = None
    citizen_feedback_at: datetime | None = None
    citizen_reopen_requested: bool = False
    is_demo: bool


class CitizenFeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)
    resolved_satisfactorily: bool = True

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class CountItem(BaseModel):
    key: str
    label: str
    count: int


class HotspotOut(BaseModel):
    incident_id: int
    public_id: str
    latitude: float
    longitude: float
    ward_name: str
    category: Category
    priority: Priority
    status: IncidentStatus
    report_count: int


class AnalyticsSummaryOut(BaseModel):
    generated_at: datetime
    active_incidents: int
    awaiting_triage: int
    unassigned_incidents: int
    in_progress: int
    blocked: int
    verification_pending: int
    verified_last_7_days: int
    total_reports: int
    reports_last_7_days: int
    accepted_duplicate_links: int
    sla_breached_count: int = 0
    sla_at_risk_count: int = 0
    status_counts: list[CountItem]
    category_counts: list[CountItem]
    ward_counts: list[CountItem]
    hotspots: list[HotspotOut]


class HotspotClusterOut(BaseModel):
    cluster_id: str
    latitude: float
    longitude: float
    radius_m: float
    ward_name: str
    incident_count: int
    active_incident_count: int
    total_reports: int
    top_category: Category
    max_priority: Priority
    chronic_score: float
    is_chronic: bool
    recommendation: str
    incident_ids: list[int]
    public_ids: list[str]
    latest_incident_at: datetime


class HotspotListOut(BaseModel):
    generated_at: datetime
    window_days: int
    radius_m: float
    clusters: list[HotspotClusterOut]


class SlaSweepOut(BaseModel):
    swept_at: datetime
    escalated_count: int
    escalated_work_order_public_ids: list[str]


class PublicIncidentMapItem(BaseModel):
    id: int
    public_id: str
    title: str
    category: Category
    priority: Priority
    status: IncidentStatus
    ward_name: str | None = None
    latitude: float
    longitude: float
    report_count: int
    primary_report_public_id: str | None = None
    created_at: datetime
    verified_at: datetime | None = None
    is_demo: bool


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=600)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    history: list[ChatTurn] = Field(default_factory=list, max_length=10)


class ChatResponse(BaseModel):
    reply: str
    guardrail_triggered: bool = False
    refusal_reason: str | None = None
    provider: str
    suggestions: list[str] = Field(default_factory=list)
