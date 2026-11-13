"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Icon } from "@/components/Icon";
import { IncidentMap } from "@/components/IncidentMap";
import { RoleGate } from "@/components/RoleGate";
import { SecureAudio, SecureImage } from "@/components/SecureImage";
import {
  ConfidenceMeter,
  DemoBadge,
  ErrorPanel,
  LoadingPanel,
  PriorityPill,
  StatusPill,
  TriagePill,
} from "@/components/Ui";
import { apiFetch, errorMessage } from "@/lib/api";
import {
  CATEGORY_LABELS,
  DUPLICATE_STATUS_LABELS,
  MEDIA_KIND_LABELS,
  PRIORITY_LABELS,
  SEVERITY_LABELS,
  WORK_ORDER_STATUS_LABELS,
  actionLabel,
  formatDate,
  toDateTimeInput,
} from "@/lib/format";
import type {
  Category,
  DuplicateCandidate,
  IncidentDetail,
  Priority,
  Report,
  Severity,
  Team,
  WorkOrder,
} from "@/lib/types";

const categoryOptions = Object.entries(CATEGORY_LABELS) as [Category, string][];
const severityOptions = Object.entries(SEVERITY_LABELS) as [Severity, string][];
const priorityOptions = Object.entries(PRIORITY_LABELS) as [Priority, string][];

function originalToCandidateGap(candidate: DuplicateCandidate): string {
  return `${candidate.distance_m.toFixed(0)} m from the candidate report`;
}

function ReportPhotos({ report }: { report: Report }) {
  if (report.media.length === 0) {
    return <p className="field-help">No media was attached to this report.</p>;
  }
  return (
    <div className="media-grid">
      {report.media.map((media) => (
        <figure className="media-figure" key={media.id}>
          {media.kind === "report_audio" ? (
            <SecureAudio media={media} />
          ) : (
            <SecureImage media={media} className="secure-image" />
          )}
          <figcaption>{MEDIA_KIND_LABELS[media.kind]}</figcaption>
        </figure>
      ))}
    </div>
  );
}

function EvidenceGallery({ order }: { order: WorkOrder }) {
  if (order.evidence.length === 0) {
    return <p className="field-help">No work-order evidence has been uploaded yet.</p>;
  }
  return (
    <div className="media-grid">
      {order.evidence.map((media) => (
        <figure className="media-figure" key={media.id}>
          <SecureImage media={media} className="secure-image" />
          <figcaption>{MEDIA_KIND_LABELS[media.kind]}</figcaption>
        </figure>
      ))}
    </div>
  );
}

function IncidentContent() {
  const params = useParams<{ id: string }>();
  const incidentId = Number(params.id);

  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [triageCategory, setTriageCategory] = useState<Category>("other_waste");
  const [triageSeverity, setTriageSeverity] = useState<Severity>("moderate");
  const [triageNote, setTriageNote] = useState("");
  const [savingTriage, setSavingTriage] = useState(false);
  const [triageError, setTriageError] = useState<string | null>(null);

  const [overridePriority, setOverridePriority] = useState<Priority>("medium");
  const [overrideReason, setOverrideReason] = useState("");
  const [savingOverride, setSavingOverride] = useState(false);
  const [overrideError, setOverrideError] = useState<string | null>(null);

  const [reviewNotes, setReviewNotes] = useState<Record<number, string>>({});
  const [reviewingId, setReviewingId] = useState<number | null>(null);

  const [teamId, setTeamId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [dueAt, setDueAt] = useState(toDateTimeInput(2));
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [workOrderError, setWorkOrderError] = useState<string | null>(null);

  const [verificationNote, setVerificationNote] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);

  const load = useCallback(
    async (initial = false) => {
      if (!Number.isFinite(incidentId) || incidentId <= 0) {
        setError("This incident reference is not valid.");
        setLoading(false);
        return;
      }
      if (initial) setLoading(true);
      setRefreshing(true);
      setError(null);
      try {
        const [detail, teamList] = await Promise.all([
          apiFetch<IncidentDetail>(`/incidents/${incidentId}`),
          apiFetch<Team[]>("/teams"),
        ]);
        setIncident(detail);
        setTeams(teamList);
        setTriageCategory(detail.category);
        setTriageSeverity(detail.severity);
        setTriageNote("");
        setOverridePriority(detail.priority);
        setReviewNotes({});
        const eligible = teamList.find(
          (team) => team.ward_id === detail.ward.id && team.is_active,
        );
        setTeamId((current) => current || (eligible ? String(eligible.id) : ""));
      } catch (caught) {
        setError(errorMessage(caught));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [incidentId],
  );

  useEffect(() => {
    // Authenticated, client-side fetch: loading state is intentionally set
    // before the request. This is a route-parameter synchronization effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(true);
  }, [load]);

  async function saveTriage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTriageError(null);
    setActionMessage(null);
    setActionError(null);
    if (triageNote.trim().length < 3) {
      setTriageError("Add a short review note so the decision is auditable.");
      return;
    }
    setSavingTriage(true);
    try {
      await apiFetch(`/incidents/${incidentId}/triage`, {
        method: "PATCH",
        body: {
          category: triageCategory,
          severity: triageSeverity,
          note: triageNote.trim(),
        },
      });
      await load();
      setActionMessage(
        "Triage confirmed. The actor, previous status and new status were recorded.",
      );
    } catch (caught) {
      setTriageError(errorMessage(caught));
    } finally {
      setSavingTriage(false);
    }
  }

  async function savePriorityOverride(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOverrideError(null);
    setActionMessage(null);
    setActionError(null);
    if (overrideReason.trim().length < 10) {
      setOverrideError("Explain the reason in at least 10 characters.");
      return;
    }
    setSavingOverride(true);
    try {
      await apiFetch(`/incidents/${incidentId}/priority-override`, {
        method: "POST",
        body: { priority: overridePriority, reason: overrideReason.trim() },
      });
      await load();
      setOverrideReason("");
      setActionMessage("Priority override saved with an operator reason.");
    } catch (caught) {
      setOverrideError(errorMessage(caught));
    } finally {
      setSavingOverride(false);
    }
  }

  async function reviewDuplicate(candidate: DuplicateCandidate, decision: "accept" | "reject") {
    if (
      decision === "accept" &&
      !window.confirm(
        "Link this source report to the candidate incident? Both reports and all photos remain stored. The source incident is archived only if it becomes empty.",
      )
    ) {
      return;
    }
    setActionMessage(null);
    setActionError(null);
    setReviewingId(candidate.id);
    try {
      await apiFetch(`/duplicate-candidates/${candidate.id}/review`, {
        method: "POST",
        body: {
          decision,
          note: reviewNotes[candidate.id]?.trim() || null,
        },
      });
      await load();
      setActionMessage(
        decision === "accept"
          ? "Duplicate relationship confirmed. Source reports remain preserved in the audit trail."
          : "Reports kept separate. The suggestion was closed with a human review record.",
      );
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setReviewingId(null);
    }
  }

  async function createWorkOrder(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorkOrderError(null);
    setActionMessage(null);
    setActionError(null);
    if (!teamId) {
      setWorkOrderError("Select the crew that should receive this task.");
      return;
    }
    if (instructions.trim().length < 10) {
      setWorkOrderError("Provide clear instructions of at least 10 characters.");
      return;
    }
    let dueIso: string | null = null;
    if (dueAt) {
      const parsed = new Date(dueAt);
      if (Number.isNaN(parsed.getTime())) {
        setWorkOrderError("Enter a valid due date or leave it blank.");
        return;
      }
      dueIso = parsed.toISOString();
    }
    setCreatingOrder(true);
    try {
      await apiFetch(`/incidents/${incidentId}/work-orders`, {
        method: "POST",
        body: {
          team_id: Number(teamId),
          instructions: instructions.trim(),
          due_at: dueIso,
        },
      });
      setInstructions("");
      await load();
      setActionMessage(
        "Work order assigned. The incident moved to Assigned and the crew can now accept the task.",
      );
    } catch (caught) {
      setWorkOrderError(errorMessage(caught));
    } finally {
      setCreatingOrder(false);
    }
  }

  async function reviewResolution(order: WorkOrder, action: "verify" | "reject_verification") {
    setVerificationError(null);
    setActionMessage(null);
    setActionError(null);
    if (action === "reject_verification" && verificationNote.trim().length < 3) {
      setVerificationError("Explain why the evidence is insufficient before reopening.");
      return;
    }
    setVerifying(true);
    try {
      await apiFetch(`/work-orders/${order.id}/transition`, {
        method: "POST",
        body: {
          action,
          note: verificationNote.trim() || null,
        },
      });
      setVerificationNote("");
      await load();
      setActionMessage(
        action === "verify"
          ? "Resolution verified. The incident and work order are now closed with an audit record."
          : "Verification rejected. The work order was reopened for corrective action.",
      );
    } catch (caught) {
      setVerificationError(errorMessage(caught));
    } finally {
      setVerifying(false);
    }
  }

  if (loading && !incident) {
    return (
      <div className="shell page-shell">
        <LoadingPanel label="Loading incident workspace…" />
      </div>
    );
  }

  if (error && !incident) {
    return (
      <div className="shell narrow-page">
        <ErrorPanel message={error} onRetry={() => void load(true)} />
        <div className="button-row" style={{ marginTop: 16 }}>
          <Link className="button button-secondary" href="/dashboard">
            <Icon name="chevron-left" size={16} />
            Back to queue
          </Link>
        </div>
      </div>
    );
  }

  if (!incident) return null;

  const latestOrder = incident.work_orders[0] ?? null;
  const eligibleTeams = teams.filter(
    (team) => team.ward_id === incident.ward.id && team.is_active,
  );
  const canTriage = !["verified", "merged"].includes(incident.status);
  const closed = incident.status === "verified" || incident.status === "merged";
  const factors = incident.priority_factors?.factors ?? [];
  const disputedReports = incident.reports.filter((r) => r.citizen_reopen_requested);

  async function reopenFromDispute() {
    if (!latestOrder) return;
    setVerifying(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await apiFetch(`/work-orders/${latestOrder.id}/transition`, {
        method: "POST",
        body: JSON.stringify({
          action: "reject_verification",
          note: "Reopened by operator following citizen dispute feedback.",
        }),
      });
      await load(true);
      setActionMessage("Work order reopened following citizen dispute.");
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="shell incident-page">
      <Link className="back-link" href="/dashboard">
        <Icon name="chevron-left" size={15} />
        Back to incident queue
      </Link>

      <header className="surface incident-head">
        <div className="incident-head-main">
          <div className="incident-kicker">
            <span className="mono">{incident.public_id}</span>
            <StatusPill status={incident.status} />
            <PriorityPill priority={incident.priority} />
            {incident.is_demo && <DemoBadge compact />}
          </div>
          <h1>{incident.title}</h1>
          <p className="incident-sub">
            {CATEGORY_LABELS[incident.category]} · {incident.ward.name} ·{" "}
            {incident.address ?? "Location pin submitted"}
          </p>
          <div className="incident-metrics">
            <div>
              <span>Source reports</span>
              <strong>{incident.report_count}</strong>
            </div>
            <div>
              <span>Priority score</span>
              <strong>{Math.round(incident.priority_score)} / 100</strong>
            </div>
            <div>
              <span>Severity</span>
              <strong>{SEVERITY_LABELS[incident.severity]}</strong>
            </div>
            <div>
              <span>Created</span>
              <strong>{formatDate(incident.created_at)}</strong>
            </div>
            <div>
              <span>Triaged</span>
              <strong>{incident.triaged_at ? formatDate(incident.triaged_at) : "Not yet"}</strong>
            </div>
          </div>
        </div>
        <div className="incident-head-actions">
          {latestOrder && (
            <Link
              className="button button-secondary button-small"
              href={`/field/${latestOrder.id}`}
            >
              <Icon name="route" size={16} />
              Open field task
            </Link>
          )}
          <button
            className="button button-secondary button-small"
            type="button"
            onClick={() => void load()}
            disabled={refreshing}
          >
            <Icon name="refresh" size={15} />
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {actionMessage && (
        <div className="notice notice-success" role="status" style={{ marginBottom: 14 }}>
          <Icon name="check" size={18} />
          <div>
            <strong>Action recorded</strong>
            <p>{actionMessage}</p>
          </div>
        </div>
      )}

      {actionError && (
        <div className="notice notice-error" role="alert" style={{ marginBottom: 14 }}>
          <Icon name="alert" size={18} />
          <div>
            <strong>Action failed</strong>
            <p>{actionError}</p>
          </div>
        </div>
      )}

      {disputedReports.length > 0 && (
        <div className="notice notice-warning" role="alert" style={{ marginBottom: 14 }}>
          <Icon name="alert" size={18} />
          <div style={{ flex: 1 }}>
            <strong>Citizen disputed resolution</strong>
            <p style={{ marginBottom: latestOrder?.status === "verified" ? 10 : 0 }}>
              {disputedReports.length} citizen report
              {disputedReports.length === 1 ? "" : "s"} indicated the issue still persists
              {disputedReports[0]?.citizen_feedback
                ? `: “${disputedReports[0].citizen_feedback}”`
                : "."}
            </p>
            {latestOrder?.status === "verified" && (
              <button
                type="button"
                className="button button-small button-primary"
                disabled={verifying}
                onClick={() => void reopenFromDispute()}
              >
                {verifying ? "Reopening…" : "Reopen work order"}
              </button>
            )}
          </div>
        </div>
      )}

      <div className="incident-layout">
        <div className="incident-main">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Reported issue</h2>
                <p>Summary and location come from persisted source reports.</p>
              </div>
              <span className="panel-note">Incident {incident.public_id}</span>
            </div>
            <p className="body-copy">{incident.description}</p>

            {incident.priority_overridden && (
              <div className="notice notice-warning">
                <Icon name="alert" size={17} />
                <div>
                  <strong>Priority has a recorded human override</strong>
                  <p>{incident.priority_override_reason}</p>
                </div>
              </div>
            )}

            <div className="location-band">
              <IncidentMap
                points={[
                  {
                    id: incident.id,
                    latitude: incident.latitude,
                    longitude: incident.longitude,
                    publicId: incident.public_id,
                    title: incident.title,
                    priority: incident.priority,
                    reportCount: incident.report_count,
                  },
                ]}
                height={255}
                label="Incident location map"
              />
              <div className="location-info">
                <div>
                  <span>Ward</span>
                  <strong>{incident.ward.name}</strong>
                </div>
                <div>
                  <span>Location note</span>
                  <strong>{incident.address ?? "No landmark supplied"}</strong>
                </div>
                <div>
                  <span>Coordinates</span>
                  <strong className="mono">
                    {incident.latitude.toFixed(5)}, {incident.longitude.toFixed(5)}
                  </strong>
                </div>
                <div>
                  <span>Last updated</span>
                  <strong>{formatDate(incident.updated_at)}</strong>
                </div>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Duplicate suggestions</h2>
                <p>
                  Geographic proximity, category, text similarity and recency.
                  A human decides every relationship.
                </p>
              </div>
              <span className="panel-note">
                {incident.duplicate_candidates.length} candidate
                {incident.duplicate_candidates.length === 1 ? "" : "s"}
              </span>
            </div>

            {incident.duplicate_candidates.length === 0 ? (
              <p className="field-help">
                No duplicate candidates are attached to this incident. Nearby
                reports may still exist outside the configured search window.
              </p>
            ) : (
              incident.duplicate_candidates.map((candidate) => (
                <article
                  className={`duplicate-card is-${candidate.status}`}
                  key={candidate.id}
                >
                  <div className="duplicate-top">
                    <span className="match-score">
                      {Math.round(candidate.score)}% match
                    </span>
                    <span className="muted">{originalToCandidateGap(candidate)}</span>
                    <span className="spacer" />
                    <span className={`duplicate-status ${candidate.status}`}>
                      {DUPLICATE_STATUS_LABELS[candidate.status]}
                    </span>
                  </div>
                  <h3>
                    Candidate report{" "}
                    <span className="mono">{candidate.candidate_report.public_id}</span>
                  </h3>
                  <p>{candidate.candidate_report.description}</p>
                  <ul className="reason-list">
                    {candidate.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                  <div className="duplicate-meta">
                    <span>
                      Reported {formatDate(candidate.candidate_report.created_at)}
                    </span>
                    <span>{candidate.candidate_report.ward_name}</span>
                    <span>
                      Candidate incident{" "}
                      <span className="mono">
                        {candidate.candidate_incident_public_id ?? "not linked"}
                      </span>
                    </span>
                    {candidate.candidate_incident_status && (
                      <span>
                        Current status:{" "}
                        {candidate.candidate_incident_status.replaceAll("_", " ")}
                      </span>
                    )}
                  </div>

                  {candidate.status === "suggested" ? (
                    <div className="duplicate-actions">
                      <div className="field">
                        <label htmlFor={`duplicate-note-${candidate.id}`}>
                          Review note <span className="optional">(optional)</span>
                        </label>
                        <textarea
                          id={`duplicate-note-${candidate.id}`}
                          value={reviewNotes[candidate.id] ?? ""}
                          onChange={(event) =>
                            setReviewNotes((current) => ({
                              ...current,
                              [candidate.id]: event.target.value,
                            }))
                          }
                          maxLength={500}
                          placeholder="Why are these the same issue, or why are they separate?"
                        />
                      </div>
                      <p className="duplicate-warning">
                        Accepting links the source report to the candidate
                        incident and preserves every report, photo and reporter
                        record. An empty source incident is archived as merged.
                      </p>
                      <div className="button-row">
                        <button
                          className="button button-primary button-small"
                          type="button"
                          onClick={() => void reviewDuplicate(candidate, "accept")}
                          disabled={reviewingId === candidate.id}
                        >
                          <Icon name="layers" size={15} />
                          {reviewingId === candidate.id ? "Saving…" : "Confirm duplicate"}
                        </button>
                        <button
                          className="button button-secondary button-small"
                          type="button"
                          onClick={() => void reviewDuplicate(candidate, "reject")}
                          disabled={reviewingId === candidate.id}
                        >
                          Keep separate
                        </button>
                      </div>
                    </div>
                  ) : (
                    candidate.review_note && (
                      <p className="field-help" style={{ marginTop: 10 }}>
                        Human review: {candidate.review_note}
                        {candidate.reviewed_at
                          ? ` · ${formatDate(candidate.reviewed_at)}`
                          : ""}
                      </p>
                    )
                  )}
                </article>
              ))
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Source reports</h2>
                <p>
                  Every citizen report remains its own record, including its
                  original text and evidence.
                </p>
              </div>
              <span className="panel-note">{incident.reports.length} preserved</span>
            </div>

            {incident.reports.map((report) => (
              <article className="report-card" key={report.id}>
                <div className="report-card-head">
                  <span className="mono">{report.public_id}</span>
                  <TriagePill status={report.ai_status} />
                  {report.is_demo && <DemoBadge compact />}
                  <span className="spacer" />
                  <span className="report-date">
                    {formatDate(report.created_at)}
                  </span>
                </div>
                <p className="report-description">{report.description}</p>
                {(report.detected_language || report.voice_transcript) && (
                  <div className="field-help" style={{ marginTop: 6, marginBottom: 8 }}>
                    {report.detected_language && (
                      <span className="pill" style={{ marginRight: 8 }}>
                        Language: {report.detected_language}
                      </span>
                    )}
                    {report.voice_transcript && (
                      <div style={{ marginTop: 6 }}>
                        <strong>Voice transcript:</strong> {report.voice_transcript}
                      </div>
                    )}
                  </div>
                )}

                <div className="ai-box">
                  <div className="ai-box-head">
                    <Icon name="spark" size={15} />
                    <strong>AI triage · advisory</strong>
                    {report.ai_provider && (
                      <span className="mono" style={{ color: "#637a69" }}>
                        {report.ai_provider}
                      </span>
                    )}
                  </div>
                  {report.ai_summary && (
                    <p className="ai-summary">{report.ai_summary}</p>
                  )}
                  {report.ai_rationale && <p>{report.ai_rationale}</p>}
                  {report.ai_indicators.length > 0 && (
                    <ul className="indicator-list">
                      {report.ai_indicators.map((indicator) => (
                        <li key={indicator}>{indicator}</li>
                      ))}
                    </ul>
                  )}
                  <ConfidenceMeter value={report.ai_confidence} />
                  <div className="ai-details">
                    <span>
                      Category:{" "}
                      {report.ai_category
                        ? CATEGORY_LABELS[report.ai_category]
                        : "not classified"}
                    </span>
                    <span>
                      Severity:{" "}
                      {report.ai_severity
                        ? SEVERITY_LABELS[report.ai_severity]
                        : "not assessed"}
                    </span>
                    <span>
                      Fallback: {report.ai_fallback_used ? "yes · rules used" : "no"}
                    </span>
                    {report.ai_processed_at && (
                      <span>Processed {formatDate(report.ai_processed_at)}</span>
                    )}
                  </div>
                  {report.ai_error && (
                    <p className="field-error" style={{ marginTop: 7 }}>
                      Provider note: {report.ai_error}
                    </p>
                  )}
                </div>

                <ReportPhotos report={report} />

                <div className="reporter-line">
                  <span>Reporter: {report.reporter_name ?? "Anonymous"}</span>
                  <span>
                    Contact: {report.reporter_contact ?? "not supplied"}
                  </span>
                  <span>
                    Link:{" "}
                    {report.link_type === "confirmed_duplicate"
                      ? "confirmed duplicate"
                      : "created this incident"}
                  </span>
                </div>
              </article>
            ))}

            <p className="field-help" style={{ marginTop: 12 }}>
              Reporter contact details are visible only to operators and
              administrators. Field task views withhold them by default.
            </p>
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Work order</h2>
                <p>Dispatch is a human decision with explicit lifecycle states.</p>
              </div>
              {latestOrder && <StatusPill status={latestOrder.status} />}
            </div>

            {latestOrder ? (
              <>
                <div className="work-order-summary">
                  <div>
                    <span className="field-help">Work order</span>
                    <div className="mono" style={{ fontWeight: 650 }}>
                      {latestOrder.public_id}
                    </div>
                    <span className="field-help">
                      {WORK_ORDER_STATUS_LABELS[latestOrder.status]}
                    </span>
                  </div>
                  <div>
                    <span className="field-help">Assigned crew</span>
                    <div style={{ fontWeight: 650, fontSize: "0.85rem" }}>
                      {latestOrder.team.name}
                    </div>
                    <span className="field-help">
                      Due {formatDate(latestOrder.due_at)}
                    </span>
                  </div>
                </div>
                <div className="work-order-instructions">
                  <span>Instructions</span>
                  {latestOrder.instructions}
                </div>
                {latestOrder.completion_note && (
                  <div className="work-order-instructions">
                    <span>Field completion note</span>
                    {latestOrder.completion_note}
                  </div>
                )}
                {latestOrder.verification_note && (
                  <div className="work-order-instructions">
                    <span>Verification note</span>
                    {latestOrder.verification_note}
                  </div>
                )}
                <EvidenceGallery order={latestOrder} />

                {latestOrder.status === "completed" && (
                  <form
                    className="evidence-upload"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void reviewResolution(latestOrder, "verify");
                    }}
                  >
                    <h3>Human resolution review</h3>
                    <p>
                      Check the before/after evidence and field note. Only an
                      operator or administrator can close this incident.
                    </p>
                    {verificationError && (
                      <p className="field-error" role="alert" style={{ marginBottom: 9 }}>
                        {verificationError}
                      </p>
                    )}
                    <div className="field">
                      <label htmlFor="verification-note">
                        Verification note{" "}
                        <span className="optional">(required to reject)</span>
                      </label>
                      <textarea
                        id="verification-note"
                        value={verificationNote}
                        onChange={(event) => setVerificationNote(event.target.value)}
                        maxLength={1000}
                        placeholder="What did you check? If rejecting, what is missing?"
                      />
                    </div>
                    <div className="button-row">
                      <button
                        className="button button-primary button-small"
                        type="submit"
                        disabled={verifying}
                      >
                        <Icon name="check" size={15} />
                        {verifying ? "Saving…" : "Verify resolution"}
                      </button>
                      <button
                        className="button button-quiet-danger button-small"
                        type="button"
                        onClick={() => void reviewResolution(latestOrder, "reject_verification")}
                        disabled={verifying}
                      >
                        Reject verification
                      </button>
                    </div>
                  </form>
                )}

                <div className="button-row" style={{ marginTop: 16 }}>
                  <Link className="button button-secondary button-small" href={`/field/${latestOrder.id}`}>
                    <Icon name="route" size={15} />
                    Open field task
                  </Link>
                  <span className="field-help">
                    Field crew actions and evidence upload happen in the field task
                    workspace.
                  </span>
                </div>
              </>
            ) : closed ? (
              <p className="field-help">
                This incident is closed and has no work order attached.
              </p>
            ) : incident.status === "open" ? (
              <div className="notice notice-info">
                <Icon name="clock" size={18} />
                <div>
                  <strong>Confirm triage before assigning work</strong>
                  <p>
                    Use the triage panel to confirm the category, severity and
                    review note. The API enforces this sequence.
                  </p>
                </div>
              </div>
            ) : (
              <form className="stack-form" onSubmit={createWorkOrder}>
                {workOrderError && (
                  <div className="notice notice-error" role="alert">
                    <Icon name="alert" size={17} />
                    <div>
                      <strong>Work order not created</strong>
                      <p>{workOrderError}</p>
                    </div>
                  </div>
                )}
                <div className="field-row">
                  <div className="field">
                    <label htmlFor="work-order-team">Assign to crew</label>
                    <select
                      id="work-order-team"
                      value={teamId}
                      onChange={(event) => setTeamId(event.target.value)}
                      required
                    >
                      <option value="">Select an active crew</option>
                      {eligibleTeams.map((team) => (
                        <option value={String(team.id)} key={team.id}>
                          {team.name}
                        </option>
                      ))}
                    </select>
                    <p className="field-help">
                      Only active crews in {incident.ward.name} are eligible.
                    </p>
                  </div>
                  <div className="field">
                    <label htmlFor="work-order-due">
                      Due <span className="optional">(optional)</span>
                    </label>
                    <input
                      id="work-order-due"
                      type="datetime-local"
                      value={dueAt}
                      onChange={(event) => setDueAt(event.target.value)}
                    />
                  </div>
                </div>
                <div className="field">
                  <label htmlFor="work-order-instructions">Instructions</label>
                  <textarea
                    id="work-order-instructions"
                    value={instructions}
                    onChange={(event) => setInstructions(event.target.value)}
                    maxLength={2000}
                    minLength={10}
                    required
                    placeholder="Describe the required work, access constraints and evidence expected."
                  />
                </div>
                <div className="form-actions">
                  <p className="form-actions-note">
                    Creating this order moves the incident to Assigned.
                  </p>
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={creatingOrder}
                  >
                    <Icon name="clipboard" size={16} />
                    {creatingOrder ? "Assigning…" : "Assign work order"}
                  </button>
                </div>
              </form>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Audit history</h2>
                <p>
                  Incidents and work orders share one chronological record of
                  human decisions and system events.
                </p>
              </div>
              <span className="panel-note">{incident.activity.length} events</span>
            </div>
            {incident.activity.length === 0 ? (
              <p className="field-help">No activity has been recorded.</p>
            ) : (
              <ol className="timeline">
                {incident.activity.map((event) => {
                  const isSystem = event.actor_role === "system";
                  return (
                    <li className="timeline-item" key={event.id}>
                      <span
                        className={
                          isSystem
                            ? "timeline-dot is-ai"
                            : event.old_status && event.new_status
                              ? "timeline-dot is-status"
                              : "timeline-dot is-human"
                        }
                      />
                      <strong>{actionLabel(event.action)}</strong>
                      <div className="timeline-meta">
                        <span>
                          {event.actor_name} · {event.actor_role.replaceAll("_", " ")}
                        </span>
                        <span>{formatDate(event.created_at)}</span>
                      </div>
                      {event.old_status && event.new_status && (
                        <span className="timeline-transition">
                          {event.old_status.replaceAll("_", " ")} →{" "}
                          {event.new_status.replaceAll("_", " ")}
                        </span>
                      )}
                      {event.note && <p>{event.note}</p>}
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        </div>

        <aside className="incident-rail">
          <section className="panel">
            <div className="panel-head">
              <h2>Human triage</h2>
              <span className="panel-note">{incident.triaged_at ? "Confirmed" : "Pending"}</span>
            </div>

            {!canTriage ? (
              <div className="notice notice-info">
                <Icon name="shield" size={17} />
                <div>
                  <strong>This incident is closed</strong>
                  <p>{incident.triaged_at ? `Confirmed ${formatDate(incident.triaged_at)}.` : "No further triage is permitted."}</p>
                </div>
              </div>
            ) : (
              <form className="stack-form" onSubmit={saveTriage}>
                {triageError && (
                  <p className="field-error" role="alert">
                    {triageError}
                  </p>
                )}
                <div className="field">
                  <label htmlFor="triage-category">Category</label>
                  <select
                    id="triage-category"
                    value={triageCategory}
                    onChange={(event) =>
                      setTriageCategory(event.target.value as Category)
                    }
                  >
                    {categoryOptions.map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="triage-severity">Severity</label>
                  <select
                    id="triage-severity"
                    value={triageSeverity}
                    onChange={(event) =>
                      setTriageSeverity(event.target.value as Severity)
                    }
                  >
                    {severityOptions.map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="triage-note">Review note</label>
                  <textarea
                    id="triage-note"
                    value={triageNote}
                    onChange={(event) => setTriageNote(event.target.value)}
                    maxLength={1000}
                    placeholder="What did you confirm, and from which evidence?"
                  />
                </div>
                <button
                  className="button button-primary button-block"
                  type="submit"
                  disabled={savingTriage}
                >
                  <Icon name="check" size={16} />
                  {savingTriage
                    ? "Saving triage…"
                    : incident.triaged_at
                      ? "Update triage"
                      : "Confirm triage"}
                </button>
                <p className="rail-note">
                  Confirmation records the actor and enables work-order
                  assignment. AI suggestions are not treated as confirmed.
                </p>
              </form>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Priority</h2>
              <span className="panel-note">Advisory score</span>
            </div>
            <div className="priority-hero">
              <div className="priority-score">
                {Math.round(incident.priority_score)}
                <small> / 100</small>
              </div>
              <div className="priority-hero-copy">
                <PriorityPill priority={incident.priority} />
                <span>
                  Recommended: {PRIORITY_LABELS[incident.recommended_priority]}
                </span>
              </div>
            </div>

            {incident.priority_overridden && (
              <div className="notice notice-warning" style={{ marginBottom: 12 }}>
                <Icon name="alert" size={16} />
                <div>
                  <strong>Operator override</strong>
                  <p>{incident.priority_override_reason}</p>
                </div>
              </div>
            )}

            {factors.length === 0 ? (
              <p className="field-help">No priority factors are stored.</p>
            ) : (
              <div className="factor-list">
                {factors.map((factor) => (
                  <div className="factor-row" key={factor.label}>
                    <span>{factor.label}</span>
                    <strong>
                      {factor.points} / {factor.max_points}
                    </strong>
                    <div className="factor-bar" aria-hidden="true">
                      <i
                        style={{
                          width: `${Math.min(
                            100,
                            (factor.points / Math.max(factor.max_points, 1)) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                    <span className="factor-explain">{factor.explanation}</span>
                  </div>
                ))}
              </div>
            )}

            {incident.priority_factors?.disclaimer && (
              <p className="rail-note">{incident.priority_factors.disclaimer}</p>
            )}

            {!closed && (
              <details className="override-box">
                <summary>Override priority with a reason</summary>
                <form className="stack-form" onSubmit={savePriorityOverride}>
                  {overrideError && (
                    <p className="field-error" role="alert">
                      {overrideError}
                    </p>
                  )}
                  <div className="field">
                    <label htmlFor="override-priority">Priority</label>
                    <select
                      id="override-priority"
                      value={overridePriority}
                      onChange={(event) =>
                        setOverridePriority(event.target.value as Priority)
                      }
                    >
                      {priorityOptions.map(([value, label]) => (
                        <option value={value} key={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="override-reason">Reason</label>
                    <textarea
                      id="override-reason"
                      value={overrideReason}
                      onChange={(event) => setOverrideReason(event.target.value)}
                      minLength={10}
                      maxLength={500}
                      placeholder="Explain the operational context for this override."
                    />
                  </div>
                  <button
                    className="button button-secondary button-block"
                    type="submit"
                    disabled={savingOverride}
                  >
                    {savingOverride ? "Saving override…" : "Save override"}
                  </button>
                </form>
              </details>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Governance</h2>
              <span className="panel-note">Record facts</span>
            </div>
            <div className="rail-kv">
              <div>
                <span>Incident</span>
                <strong className="mono">{incident.public_id}</strong>
              </div>
              <div>
                <span>Ward</span>
                <strong>{incident.ward.name}</strong>
              </div>
              <div>
                <span>Work order</span>
                <strong className="mono">
                  {latestOrder?.public_id ?? "Not assigned"}
                </strong>
              </div>
              <div>
                <span>Created</span>
                <strong>{formatDate(incident.created_at)}</strong>
              </div>
              <div>
                <span>Updated</span>
                <strong>{formatDate(incident.updated_at)}</strong>
              </div>
              <div>
                <span>Priority source</span>
                <strong>
                  {incident.priority_overridden ? "Human override" : "Rule score"}
                </strong>
              </div>
            </div>
            <p className="rail-note">
              AI and priority suggestions are advisory. Human confirmation is
              required for triage, merge, dispatch and resolution verification.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

export default function IncidentPage() {
  return (
    <RoleGate roles={["operator", "admin"]}>
      <IncidentContent />
    </RoleGate>
  );
}
