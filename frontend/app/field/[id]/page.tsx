"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { Icon } from "@/components/Icon";
import { IncidentMap } from "@/components/IncidentMap";
import { RoleGate } from "@/components/RoleGate";
import { SecureImage } from "@/components/SecureImage";
import {
  DemoBadge,
  ErrorPanel,
  LoadingPanel,
  PriorityPill,
  StatusPill,
} from "@/components/Ui";
import { apiFetch, errorMessage } from "@/lib/api";
import {
  CATEGORY_LABELS,
  MEDIA_KIND_LABELS,
  WORK_ORDER_STATUS_LABELS,
  actionLabel,
  formatDate,
} from "@/lib/format";
import type {
  MediaAsset,
  MediaKind,
  WorkOrderDetail,
  WorkOrderStatus,
} from "@/lib/types";

const MAX_EVIDENCE_BYTES = 8 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

type TransitionAction =
  | "accept"
  | "start"
  | "block"
  | "resume"
  | "complete"
  | "verify"
  | "reject_verification";

function statusBrief(status: WorkOrderStatus): string {
  switch (status) {
    case "assigned":
      return "This task has been dispatched to your crew. Accept it to confirm you have seen the assignment.";
    case "accepted":
      return "The crew has accepted the task. Start work when the team is on site.";
    case "in_progress":
      return "Work is underway. Upload a before-photo, then an after-photo before marking the job complete.";
    case "blocked":
      return "Progress is blocked. Record why, then resume once the blocker is cleared.";
    case "completed":
      return "Field work is complete and waiting for an operator to check the evidence.";
    case "verified":
      return "An operator verified the resolution evidence. This work order is closed.";
    case "reopened":
      return "Verification was rejected. The crew can resume corrective work and upload fresh evidence.";
    default:
      return WORK_ORDER_STATUS_LABELS[status];
  }
}

function EvidenceGroup({
  title,
  items,
  empty,
}: {
  title: string;
  items: MediaAsset[];
  empty: string;
}) {
  return (
    <div>
      <div className="evidence-section-title">
        <span>{title}</span>
        <span>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="field-help">{empty}</p>
      ) : (
        <div className="media-grid">
          {items.map((media) => (
            <figure className="media-figure" key={media.id}>
              <SecureImage media={media} className="secure-image" />
              <figcaption>
                {MEDIA_KIND_LABELS[media.kind]} ·{" "}
                {formatDate(media.created_at)}
              </figcaption>
            </figure>
          ))}
        </div>
      )}
    </div>
  );
}

function FieldTaskContent() {
  const params = useParams<{ id: string }>();
  const orderId = Number(params.id);
  const { user } = useAuth();

  const [order, setOrder] = useState<WorkOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNote, setActionNote] = useState("");
  const [acting, setActing] = useState<TransitionAction | null>(null);

  const [evidenceKind, setEvidenceKind] = useState<Exclude<MediaKind, "report_photo">>(
    "before_photo",
  );
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const evidenceInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(
    async (initial = false) => {
      if (!Number.isFinite(orderId) || orderId <= 0) {
        setError("This work-order reference is not valid.");
        setLoading(false);
        return;
      }
      if (initial) setLoading(true);
      setRefreshing(true);
      setError(null);
      try {
        const detail = await apiFetch<WorkOrderDetail>(`/work-orders/${orderId}`);
        setOrder(detail);
      } catch (caught) {
        setError(errorMessage(caught));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [orderId],
  );

  useEffect(() => {
    // Authenticated, client-side fetch: loading state is intentionally set
    // before the request. This is a route-parameter synchronization effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(true);
  }, [load]);

  const isOperator = user?.role === "operator" || user?.role === "admin";
  const beforeEvidence =
    order?.evidence.filter((item) => item.kind === "before_photo") ?? [];
  const afterEvidence =
    order?.evidence.filter((item) => item.kind === "after_photo") ?? [];

  async function runTransition(action: TransitionAction, requiresNote: boolean) {
    if (!order) return;
    setActionMessage(null);
    setActionError(null);
    if (requiresNote && actionNote.trim().length < 3) {
      setActionError(
        action === "complete"
          ? "Add a short completion note describing the work done."
          : action === "block"
            ? "Explain the blocker so an operator can help."
            : "Explain why the evidence is insufficient before reopening.",
      );
      return;
    }
    if (action === "complete" && afterEvidence.length === 0) {
      setActionError("Upload at least one after-photo before marking the work complete.");
      return;
    }
    setActing(action);
    try {
      await apiFetch(`/work-orders/${order.id}/transition`, {
        method: "POST",
        body: { action, note: actionNote.trim() || null },
      });
      setActionNote("");
      await load();
      setActionMessage(
        `${WORK_ORDER_STATUS_LABELS[
          action === "verify"
            ? "verified"
            : action === "reject_verification"
              ? "reopened"
              : action === "complete"
                ? "completed"
                : action === "block"
                  ? "blocked"
                  : action === "resume" || action === "start"
                    ? "in_progress"
                    : "accepted"
        ]} action recorded in the audit history.`,
      );
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setActing(null);
    }
  }

  function handleEvidenceChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setFileError(null);
    setActionMessage(null);
    if (!file) {
      setEvidenceFile(null);
      return;
    }
    if (!ALLOWED_TYPES.includes(file.type)) {
      setFileError("Choose a JPEG, PNG or WebP image.");
      setEvidenceFile(null);
      if (evidenceInputRef.current) evidenceInputRef.current.value = "";
      return;
    }
    if (file.size > MAX_EVIDENCE_BYTES) {
      setFileError("The evidence photo must be 8 MB or smaller.");
      setEvidenceFile(null);
      if (evidenceInputRef.current) evidenceInputRef.current.value = "";
      return;
    }
    setEvidenceFile(file);
  }

  async function uploadEvidence(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!order) return;
    setActionMessage(null);
    setActionError(null);
    setFileError(null);
    if (!evidenceFile) {
      setFileError("Choose a photo to upload.");
      return;
    }
    const formData = new FormData();
    formData.append("kind", evidenceKind);
    formData.append("photo", evidenceFile);
    setUploading(true);
    try {
      await apiFetch(`/work-orders/${order.id}/evidence`, {
        method: "POST",
        body: formData,
      });
      setEvidenceFile(null);
      if (evidenceInputRef.current) evidenceInputRef.current.value = "";
      await load();
      setActionMessage(
        `${evidenceKind === "before_photo" ? "Before" : "After"} photo uploaded and recorded as evidence.`,
      );
      if (evidenceKind === "before_photo" && afterEvidence.length === 0) {
        setEvidenceKind("after_photo");
      }
    } catch (caught) {
      setFileError(errorMessage(caught));
    } finally {
      setUploading(false);
    }
  }

  if (loading && !order) {
    return (
      <div className="shell page-shell">
        <LoadingPanel label="Loading field task…" />
      </div>
    );
  }

  if (error && !order) {
    return (
      <div className="shell narrow-page">
        <ErrorPanel message={error} onRetry={() => void load(true)} />
        <div className="button-row" style={{ marginTop: 16 }}>
          <Link className="button button-secondary" href="/field">
            <Icon name="chevron-left" size={16} />
            Back to field tasks
          </Link>
        </div>
      </div>
    );
  }

  if (!order) return null;

  const status = order.status;
  const editable = status !== "verified";

  return (
    <div className="shell field-page">
      <Link className="back-link" href="/field">
        <Icon name="chevron-left" size={15} />
        {isOperator ? "Back to field task board" : "Back to my tasks"}
      </Link>

      <header className="surface field-head">
        <div>
          <div className="incident-kicker">
            <span className="mono">{order.public_id}</span>
            <StatusPill status={order.status} />
            <PriorityPill priority={order.incident.priority} />
            {order.is_demo && <DemoBadge compact />}
          </div>
          <h1>{order.incident.title}</h1>
          <p>
            {CATEGORY_LABELS[order.incident.category]} · {order.incident.ward.name} ·{" "}
            {order.incident.address ?? "Location pin supplied"}
          </p>
          <div className="incident-metrics">
            <div>
              <span>Assigned crew</span>
              <strong>{order.team.name}</strong>
            </div>
            <div>
              <span>Incident</span>
              <strong className="mono">{order.incident.public_id}</strong>
            </div>
            <div>
              <span>Due</span>
              <strong>{formatDate(order.due_at)}</strong>
            </div>
            <div>
              <span>Source reports</span>
              <strong>{order.reports.length}</strong>
            </div>
          </div>
        </div>
        <div className="dashboard-head-actions">
          {isOperator && (
            <Link
              className="button button-secondary button-small"
              href={`/incidents/${order.incident_id}`}
            >
              <Icon name="clipboard" size={15} />
              Incident workspace
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
            <strong>Saved</strong>
            <p>{actionMessage}</p>
          </div>
        </div>
      )}

      {actionError && (
        <div className="notice notice-error" role="alert" style={{ marginBottom: 14 }}>
          <Icon name="alert" size={18} />
          <div>
            <strong>Action not completed</strong>
            <p>{actionError}</p>
          </div>
        </div>
      )}

      {error && order && (
        <div style={{ marginBottom: 14 }}>
          <ErrorPanel message={error} onRetry={() => void load()} />
        </div>
      )}

      <div className="task-detail-grid">
        <div>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Task brief</h2>
                <p>Instructions approved by an operator.</p>
              </div>
              <span className="panel-note">{WORK_ORDER_STATUS_LABELS[order.status]}</span>
            </div>
            <div className="work-order-instructions">
              <span>Instructions</span>
              {order.instructions}
            </div>
            <div className="notice notice-info">
              <Icon name="shield" size={17} />
              <div>
                <strong>{WORK_ORDER_STATUS_LABELS[status]}</strong>
                <p>{statusBrief(status)}</p>
              </div>
            </div>
            {order.completion_note && (
              <div className="work-order-instructions" style={{ marginTop: 14 }}>
                <span>Completion note</span>
                {order.completion_note}
              </div>
            )}
            {order.verification_note && (
              <div className="work-order-instructions">
                <span>Verification review</span>
                {order.verification_note}
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Location</h2>
                <p>
                  {order.incident.address ?? "Use the coordinates and map pin."} ·{" "}
                  {order.incident.ward.name}
                </p>
              </div>
              <span className="mono" style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
                {order.incident.latitude.toFixed(5)},{" "}
                {order.incident.longitude.toFixed(5)}
              </span>
            </div>
            <IncidentMap
              points={[
                {
                  id: order.incident.id,
                  latitude: order.incident.latitude,
                  longitude: order.incident.longitude,
                  publicId: order.incident.public_id,
                  title: order.incident.title,
                  priority: order.incident.priority,
                  reportCount: order.reports.length,
                },
              ]}
              height={280}
              label="Work order location map"
            />
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Evidence</h2>
                <p>
                  Photos are re-encoded to remove metadata. At least one
                  after-photo is required before completion.
                </p>
              </div>
              <span className="panel-note">{order.evidence.length} attached</span>
            </div>

            <EvidenceGroup
              title="Before photos"
              items={beforeEvidence}
              empty="No before-photo has been uploaded."
            />
            <EvidenceGroup
              title="After photos"
              items={afterEvidence}
              empty="No after-photo has been uploaded yet."
            />

            {editable ? (
              <form className="evidence-upload" onSubmit={uploadEvidence}>
                <h3>Upload evidence</h3>
                <p>
                  Take a clear photo that shows the condition. Do not include
                  faces, documents or personal information.
                </p>
                {fileError && (
                  <p className="field-error" role="alert" style={{ marginBottom: 9 }}>
                    {fileError}
                  </p>
                )}
                <div className="upload-row">
                  <div className="field">
                    <label htmlFor="evidence-kind">Evidence type</label>
                    <select
                      id="evidence-kind"
                      value={evidenceKind}
                      onChange={(event) => {
                        setEvidenceKind(
                          event.target.value as Exclude<MediaKind, "report_photo">,
                        );
                        setFileError(null);
                      }}
                    >
                      <option value="before_photo">Before photo</option>
                      <option value="after_photo">After photo</option>
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="evidence-photo">Photo</label>
                    <input
                      id="evidence-photo"
                      ref={evidenceInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleEvidenceChange}
                    />
                  </div>
                </div>
                <div className="button-row" style={{ marginTop: 10 }}>
                  <button
                    className="button button-secondary button-small"
                    type="submit"
                    disabled={uploading || !evidenceFile}
                  >
                    <Icon name="upload" size={15} />
                    {uploading ? "Uploading…" : "Upload photo"}
                  </button>
                  {evidenceFile && (
                    <span className="field-help">
                      {evidenceFile.name} ·{" "}
                      {(evidenceFile.size / 1024 / 1024).toFixed(1)} MB
                    </span>
                  )}
                </div>
              </form>
            ) : (
              <p className="field-help" style={{ marginTop: 14 }}>
                Verified work orders are closed and cannot receive new evidence.
              </p>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Citizen reports</h2>
                <p>
                  Source reports linked to this incident. Reporter contact
                  details are withheld from field tasks.
                </p>
              </div>
              <span className="panel-note">{order.reports.length} preserved</span>
            </div>
            {order.reports.length === 0 ? (
              <p className="field-help">No source reports are linked.</p>
            ) : (
              order.reports.map((report) => (
                <article className="report-card" key={report.id}>
                  <div className="report-card-head">
                    <span className="mono">{report.public_id}</span>
                    <span className="spacer" />
                    <span className="report-date">{formatDate(report.created_at)}</span>
                  </div>
                  <p className="report-description">{report.description}</p>
                  {report.ai_summary && (
                    <div className="ai-box">
                      <div className="ai-box-head">
                        <Icon name="spark" size={15} />
                        <strong>AI summary · advisory</strong>
                      </div>
                      <p className="ai-summary">{report.ai_summary}</p>
                      {report.ai_indicators.length > 0 && (
                        <ul className="indicator-list">
                          {report.ai_indicators.map((indicator) => (
                            <li key={indicator}>{indicator}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  {report.media.length > 0 && (
                    <div className="media-grid">
                      {report.media.map((media) => (
                        <figure className="media-figure" key={media.id}>
                          <SecureImage media={media} className="secure-image" />
                          <figcaption>{MEDIA_KIND_LABELS[media.kind]}</figcaption>
                        </figure>
                      ))}
                    </div>
                  )}
                </article>
              ))
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Task activity</h2>
                <p>Field actions and evidence uploads recorded by the API.</p>
              </div>
              <span className="panel-note">{order.activity.length} events</span>
            </div>
            {order.activity.length === 0 ? (
              <p className="field-help">No activity has been recorded.</p>
            ) : (
              <ol className="timeline">
                {order.activity.map((event) => (
                  <li className="timeline-item" key={event.id}>
                    <span className="timeline-dot is-human" />
                    <strong>{actionLabel(event.action)}</strong>
                    <div className="timeline-meta">
                      <span>
                        {event.actor_name} · {event.actor_role.replaceAll("_", " ")}
                      </span>
                      <span>{formatDate(event.created_at)}</span>
                    </div>
                    {event.old_status && event.new_status &&
                      event.old_status !== event.new_status && (
                        <span className="timeline-transition">
                          {event.old_status.replaceAll("_", " ")} →{" "}
                          {event.new_status.replaceAll("_", " ")}
                        </span>
                      )}
                    {event.note && <p>{event.note}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        <aside className="incident-rail">
          <section className="panel action-panel">
            <div className="panel-head">
              <h2>Next action</h2>
              <span className="panel-note">Human-controlled</span>
            </div>
            <p className="field-help" style={{ marginTop: 0 }}>
              {statusBrief(status)}
            </p>

            {editable && (
              <div className="field" style={{ marginTop: 12 }}>
                <label htmlFor="action-note">
                  Note{" "}
                  <span className="optional">
                    {status === "in_progress" || status === "blocked"
                      ? "(required for block/complete)"
                      : "(optional)"}
                  </span>
                </label>
                <textarea
                  id="action-note"
                  value={actionNote}
                  onChange={(event) => setActionNote(event.target.value)}
                  maxLength={1000}
                  placeholder="What changed, what you found, or what is blocking the work."
                />
              </div>
            )}

            {status === "assigned" && (
              <button
                className="button button-primary button-block"
                type="button"
                onClick={() => void runTransition("accept", false)}
                disabled={acting !== null}
              >
                <Icon name="check" size={16} />
                {acting === "accept" ? "Accepting…" : "Accept task"}
              </button>
            )}

            {status === "accepted" && (
              <>
                <button
                  className="button button-primary button-block"
                  type="button"
                  onClick={() => void runTransition("start", false)}
                  disabled={acting !== null}
                >
                  <Icon name="route" size={16} />
                  {acting === "start" ? "Starting…" : "Start work"}
                </button>
                <button
                  className="button button-quiet-danger button-block"
                  type="button"
                  onClick={() => void runTransition("block", true)}
                  disabled={acting !== null}
                >
                  <Icon name="alert" size={16} />
                  {acting === "block" ? "Saving…" : "Report a blocker"}
                </button>
              </>
            )}

            {status === "in_progress" && (
              <>
                <button
                  className="button button-primary button-block"
                  type="button"
                  onClick={() => void runTransition("complete", true)}
                  disabled={acting !== null}
                >
                  <Icon name="check" size={16} />
                  {acting === "complete" ? "Submitting…" : "Mark work complete"}
                </button>
                {afterEvidence.length === 0 && (
                  <p className="rail-note">
                    An after-photo is required before completion. Upload one in
                    the evidence panel first.
                  </p>
                )}
                <button
                  className="button button-quiet-danger button-block"
                  type="button"
                  onClick={() => void runTransition("block", true)}
                  disabled={acting !== null}
                >
                  <Icon name="alert" size={16} />
                  {acting === "block" ? "Saving…" : "Report a blocker"}
                </button>
              </>
            )}

            {(status === "blocked" || status === "reopened") && (
              <button
                className="button button-primary button-block"
                type="button"
                onClick={() => void runTransition("resume", false)}
                disabled={acting !== null}
              >
                <Icon name="refresh" size={16} />
                {acting === "resume" ? "Resuming…" : "Resume work"}
              </button>
            )}

            {status === "completed" && (
              <>
                {isOperator ? (
                  <>
                    <button
                      className="button button-primary button-block"
                      type="button"
                      onClick={() => void runTransition("verify", false)}
                      disabled={acting !== null}
                    >
                      <Icon name="shield" size={16} />
                      {acting === "verify" ? "Verifying…" : "Verify resolution"}
                    </button>
                    <button
                      className="button button-quiet-danger button-block"
                      type="button"
                      onClick={() => void runTransition("reject_verification", true)}
                      disabled={acting !== null}
                    >
                      <Icon name="close" size={16} />
                      {acting === "reject_verification"
                        ? "Reopening…"
                        : "Reject verification"}
                    </button>
                    <p className="rail-note">
                      Verification is an operator decision. Check the after-photo
                      and completion note before closing the incident.
                    </p>
                  </>
                ) : (
                  <div className="notice notice-info">
                    <Icon name="clock" size={17} />
                    <div>
                      <strong>Waiting for operator verification</strong>
                      <p>
                        Your completion note and after-photo are on record. No
                        further field action is available.
                      </p>
                    </div>
                  </div>
                )}
              </>
            )}

            {status === "verified" && (
              <div className="notice notice-success">
                <Icon name="check" size={18} />
                <div>
                  <strong>Resolution verified</strong>
                  <p>
                    Closed {formatDate(order.verified_at)}. The incident and work
                    order remain in the audit history.
                  </p>
                </div>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Task facts</h2>
              <span className="panel-note">Record</span>
            </div>
            <div className="rail-kv">
              <div>
                <span>Work order</span>
                <strong className="mono">{order.public_id}</strong>
              </div>
              <div>
                <span>Crew</span>
                <strong>{order.team.name}</strong>
              </div>
              <div>
                <span>Created</span>
                <strong>{formatDate(order.created_at)}</strong>
              </div>
              <div>
                <span>Due</span>
                <strong>{formatDate(order.due_at)}</strong>
              </div>
              <div>
                <span>Completed</span>
                <strong>{formatDate(order.completed_at)}</strong>
              </div>
              <div>
                <span>Verified</span>
                <strong>{formatDate(order.verified_at)}</strong>
              </div>
            </div>
            <p className="rail-note">
              Reporter contact information is intentionally absent from this
              field view. Use the incident reference for all coordination.
            </p>
          </section>
        </aside>
      </div>

      <div className="provenance-note">
        <Icon name="shield" size={16} />
        <span>
          Field actions are validated by the API against role and lifecycle
          rules. Every transition records the actor, previous status, new status
          and optional note.
        </span>
      </div>
    </div>
  );
}

export default function FieldTaskPage() {
  return (
    <RoleGate roles={["field_worker", "operator", "admin"]}>
      <FieldTaskContent />
    </RoleGate>
  );
}
