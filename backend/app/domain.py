"""Domain constants and explicit workflow rules."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    CITIZEN = "citizen"
    FIELD_WORKER = "field_worker"
    OPERATOR = "operator"
    ADMIN = "admin"


STAFF_ROLES = {Role.OPERATOR.value, Role.ADMIN.value}
OPERATOR_ROLES = {Role.OPERATOR.value, Role.ADMIN.value}


class Category(str, Enum):
    GARBAGE_ACCUMULATION = "garbage_accumulation"
    OVERFLOWING_BIN = "overflowing_bin"
    MISSED_COLLECTION = "missed_collection"
    ILLEGAL_DUMPING = "illegal_dumping"
    DEAD_ANIMAL = "dead_animal"
    OTHER_WASTE = "other_waste"


class Severity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER = {
    Severity.LOW.value: 0,
    Severity.MODERATE.value: 1,
    Severity.HIGH.value: 2,
    Severity.CRITICAL.value: 3,
}


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_ORDER = {
    Priority.LOW.value: 0,
    Priority.MEDIUM.value: 1,
    Priority.HIGH.value: 2,
    Priority.CRITICAL.value: 3,
}


class IncidentStatus(str, Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    VERIFICATION_PENDING = "verification_pending"
    VERIFIED = "verified"
    REOPENED = "reopened"
    MERGED = "merged"


ACTIVE_INCIDENT_STATUSES = {
    IncidentStatus.OPEN.value,
    IncidentStatus.TRIAGED.value,
    IncidentStatus.ASSIGNED.value,
    IncidentStatus.IN_PROGRESS.value,
    IncidentStatus.BLOCKED.value,
    IncidentStatus.VERIFICATION_PENDING.value,
    IncidentStatus.REOPENED.value,
}


class WorkOrderStatus(str, Enum):
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    VERIFIED = "verified"
    REOPENED = "reopened"


class TriageStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class DuplicateStatus(str, Enum):
    SUGGESTED = "suggested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class MediaKind(str, Enum):
    REPORT_PHOTO = "report_photo"
    REPORT_AUDIO = "report_audio"
    BEFORE_PHOTO = "before_photo"
    AFTER_PHOTO = "after_photo"


WORK_ORDER_TRANSITIONS: dict[str, set[str]] = {
    WorkOrderStatus.ASSIGNED.value: {WorkOrderStatus.ACCEPTED.value},
    WorkOrderStatus.ACCEPTED.value: {
        WorkOrderStatus.IN_PROGRESS.value,
        WorkOrderStatus.BLOCKED.value,
    },
    WorkOrderStatus.IN_PROGRESS.value: {
        WorkOrderStatus.BLOCKED.value,
        WorkOrderStatus.COMPLETED.value,
    },
    WorkOrderStatus.BLOCKED.value: {WorkOrderStatus.IN_PROGRESS.value},
    WorkOrderStatus.COMPLETED.value: {
        WorkOrderStatus.VERIFIED.value,
        WorkOrderStatus.REOPENED.value,
    },
    WorkOrderStatus.REOPENED.value: {WorkOrderStatus.IN_PROGRESS.value},
    WorkOrderStatus.VERIFIED.value: {WorkOrderStatus.REOPENED.value},
}

INCIDENT_STATUS_FOR_WORK_ORDER = {
    WorkOrderStatus.ASSIGNED.value: IncidentStatus.ASSIGNED.value,
    WorkOrderStatus.ACCEPTED.value: IncidentStatus.ASSIGNED.value,
    WorkOrderStatus.IN_PROGRESS.value: IncidentStatus.IN_PROGRESS.value,
    WorkOrderStatus.BLOCKED.value: IncidentStatus.BLOCKED.value,
    WorkOrderStatus.COMPLETED.value: IncidentStatus.VERIFICATION_PENDING.value,
    WorkOrderStatus.VERIFIED.value: IncidentStatus.VERIFIED.value,
    WorkOrderStatus.REOPENED.value: IncidentStatus.REOPENED.value,
}

WORK_ORDER_ACTION_TARGET = {
    "accept": WorkOrderStatus.ACCEPTED.value,
    "start": WorkOrderStatus.IN_PROGRESS.value,
    "block": WorkOrderStatus.BLOCKED.value,
    "resume": WorkOrderStatus.IN_PROGRESS.value,
    "complete": WorkOrderStatus.COMPLETED.value,
    "verify": WorkOrderStatus.VERIFIED.value,
    "reject_verification": WorkOrderStatus.REOPENED.value,
}

ACTION_ROLE_REQUIREMENT = {
    "accept": {Role.FIELD_WORKER.value, Role.OPERATOR.value, Role.ADMIN.value},
    "start": {Role.FIELD_WORKER.value, Role.OPERATOR.value, Role.ADMIN.value},
    "block": {Role.FIELD_WORKER.value, Role.OPERATOR.value, Role.ADMIN.value},
    "resume": {Role.FIELD_WORKER.value, Role.OPERATOR.value, Role.ADMIN.value},
    "complete": {Role.FIELD_WORKER.value, Role.OPERATOR.value, Role.ADMIN.value},
    "verify": {Role.OPERATOR.value, Role.ADMIN.value},
    "reject_verification": {Role.OPERATOR.value, Role.ADMIN.value},
}


CATEGORY_LABELS = {
    Category.GARBAGE_ACCUMULATION.value: "Garbage accumulation",
    Category.OVERFLOWING_BIN.value: "Overflowing bin",
    Category.MISSED_COLLECTION.value: "Missed collection",
    Category.ILLEGAL_DUMPING.value: "Illegal dumping",
    Category.DEAD_ANIMAL.value: "Dead animal",
    Category.OTHER_WASTE.value: "Other waste",
}
