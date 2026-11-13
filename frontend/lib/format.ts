import type {
  Category,
  DuplicateStatus,
  IncidentStatus,
  MediaKind,
  Priority,
  Severity,
  TriageStatus,
  WorkOrderStatus,
} from "./types";

export const CATEGORY_LABELS: Record<Category, string> = {
  garbage_accumulation: "Garbage accumulation",
  overflowing_bin: "Overflowing bin",
  missed_collection: "Missed collection",
  illegal_dumping: "Illegal dumping",
  dead_animal: "Dead animal",
  other_waste: "Other waste",
};

export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Awaiting triage",
  triaged: "Triaged",
  assigned: "Assigned",
  in_progress: "In progress",
  blocked: "Blocked",
  verification_pending: "Verification pending",
  verified: "Verified",
  reopened: "Reopened",
  merged: "Merged",
};

export const WORK_ORDER_STATUS_LABELS: Record<WorkOrderStatus, string> = {
  assigned: "Assigned",
  accepted: "Accepted",
  in_progress: "In progress",
  blocked: "Blocked",
  completed: "Awaiting verification",
  verified: "Verified",
  reopened: "Reopened",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  critical: "Critical",
};

export const TRIAGE_STATUS_LABELS: Record<TriageStatus, string> = {
  pending: "Pending",
  succeeded: "Triage complete",
  failed: "Triage failed",
  needs_review: "Needs review",
};

export const DUPLICATE_STATUS_LABELS: Record<DuplicateStatus, string> = {
  suggested: "Awaiting review",
  accepted: "Confirmed duplicate",
  rejected: "Reviewed separately",
};

export const MEDIA_KIND_LABELS: Record<MediaKind, string> = {
  report_photo: "Citizen photo",
  report_audio: "Citizen voice note",
  before_photo: "Before photo",
  after_photo: "After photo",
};

const ACTION_LABELS: Record<string, string> = {
  report_created: "Report submitted",
  incident_created: "Incident created",
  ai_triage_completed: "AI triage suggestion recorded",
  duplicate_suggestions_created: "Duplicate suggestion created",
  incident_triaged: "Operator confirmed triage",
  priority_overridden: "Operator overrode priority",
  report_linked: "Report linked",
  incident_merged: "Source incident merged",
  duplicate_accepted: "Duplicate confirmed",
  duplicate_rejected: "Duplicate rejected",
  work_order_created: "Work order assigned",
  work_order_accept: "Crew accepted work",
  work_order_start: "Work started",
  work_order_block: "Work blocked",
  work_order_resume: "Work resumed",
  work_order_complete: "Work marked complete",
  work_order_verify: "Resolution verified",
  work_order_reject_verification: "Verification rejected",
  evidence_added: "Evidence attached",
};

export function actionLabel(action: string): string {
  return (
    ACTION_LABELS[action] ??
    action.replaceAll("_", " ").replace(/^\w/, (char) => char.toUpperCase())
  );
}

export function parseApiDate(value: string): Date {
  const hasZone = /[zZ]|[+-]\d{2}:\d{2}$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not set";
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return "Not set";
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatDay(value: string | null | undefined): string {
  if (!value) return "Not set";
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatCoordinates(latitude: number, longitude: number): string {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

export function toDateTimeInput(daysFromNow = 1): string {
  const date = new Date(Date.now() + daysFromNow * 24 * 60 * 60 * 1000);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export function percent(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function statusTone(status: string): string {
  return `tone-${status.replaceAll("_", "-")}`;
}

export function priorityTone(priority: Priority): string {
  return `tone-${priority}`;
}
