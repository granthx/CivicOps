import type { ReactNode } from "react";

import { Icon } from "@/components/Icon";
import {
  INCIDENT_STATUS_LABELS,
  PRIORITY_LABELS,
  TRIAGE_STATUS_LABELS,
  WORK_ORDER_STATUS_LABELS,
  priorityTone,
  statusTone,
} from "@/lib/format";
import type {
  IncidentStatus,
  Priority,
  SlaStatus,
  TriageStatus,
  WorkOrderStatus,
} from "@/lib/types";

export function StatusPill({
  status,
  label,
}: {
  status: IncidentStatus | WorkOrderStatus;
  label?: string;
}) {
  const text =
    label ??
    (status in INCIDENT_STATUS_LABELS
      ? INCIDENT_STATUS_LABELS[status as IncidentStatus]
      : WORK_ORDER_STATUS_LABELS[status as WorkOrderStatus]);
  return (
    <span className={`status-pill ${statusTone(status)}`}>
      <i aria-hidden="true" />
      {text}
    </span>
  );
}

export function PriorityPill({ priority }: { priority: Priority }) {
  return (
    <span className={`priority-pill ${priorityTone(priority)}`}>
      {PRIORITY_LABELS[priority]}
    </span>
  );
}

export function TriagePill({ status }: { status: TriageStatus }) {
  return <span className={`triage-pill triage-${status}`}>{TRIAGE_STATUS_LABELS[status]}</span>;
}

const SLA_LABELS: Record<SlaStatus["sla_state"], string> = {
  on_track: "SLA on track",
  at_risk: "SLA at risk",
  breached: "SLA breached",
  met: "SLA met",
};

const SLA_TONES: Record<SlaStatus["sla_state"], string> = {
  on_track: "tone-green",
  at_risk: "tone-amber",
  breached: "tone-red",
  met: "tone-green",
};

export function SlaPill({ sla }: { sla?: SlaStatus | null }) {
  if (!sla) return null;
  const suffix =
    sla.sla_state === "breached"
      ? ` (${Math.abs(sla.remaining_hours).toFixed(0)}h over)`
      : sla.sla_state === "met"
        ? ""
        : ` (${Math.max(0, sla.remaining_hours).toFixed(0)}h left)`;
  return (
    <span className={`status-pill ${SLA_TONES[sla.sla_state]}`}>
      {SLA_LABELS[sla.sla_state]}
      {suffix}
    </span>
  );
}

export function DemoBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span className="demo-badge" title="Synthetic demo data, not a real municipal record">
      <i aria-hidden="true" />
      {compact ? "Demo" : "Synthetic demo record"}
    </span>
  );
}

export function ConfidenceMeter({ value }: { value: number | null }) {
  const percent = value === null ? 0 : Math.round(value * 100);
  return (
    <div className="confidence">
      <div className="confidence-copy">
        <span>AI confidence</span>
        <strong>{value === null ? "Not available" : `${percent}%`}</strong>
      </div>
      <div
        className="confidence-track"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label="AI classification confidence"
      >
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function LoadingPanel({ label = "Loading workspace…" }: { label?: string }) {
  return (
    <div className="loading-panel" role="status">
      <span className="spinner" />
      <p>{label}</p>
    </div>
  );
}

export function ErrorPanel({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-panel" role="alert">
      <Icon name="alert" size={22} />
      <div>
        <strong>Something went wrong</strong>
        <p>{message}</p>
        {onRetry && (
          <button className="button button-small button-secondary" type="button" onClick={onRetry}>
            <Icon name="refresh" size={16} />
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyPanel({
  title,
  body,
  icon = "clipboard",
}: {
  title: string;
  body: string;
  icon?: "clipboard" | "search" | "check";
}) {
  return (
    <div className="empty-panel">
      <span className="empty-icon">
        <Icon name={icon} size={24} />
      </span>
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

export function DataProvenance() {
  return (
    <div className="provenance-note">
      <Icon name="shield" size={16} />
      <span>
        Seed records are synthetic. AI and priority recommendations require human
        confirmation before operational action.
      </span>
    </div>
  );
}
