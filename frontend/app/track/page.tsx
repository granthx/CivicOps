"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { DemoBadge, StatusPill } from "@/components/Ui";
import { apiFetch, errorMessage } from "@/lib/api";
import {
  CATEGORY_LABELS,
  formatDate,
  INCIDENT_STATUS_LABELS,
} from "@/lib/format";
import type { IncidentStatus, PublicReportStatus } from "@/lib/types";

function statusExplanation(status: IncidentStatus | null): string {
  if (!status) return "An incident has not yet been created for this report.";
  switch (status) {
    case "open":
      return "The report is stored and waiting for an operator to review the AI-assisted triage.";
    case "triaged":
      return "An operator has confirmed the category and severity. The incident can now be assigned.";
    case "assigned":
      return "A human-approved work order has been assigned to a field crew.";
    case "in_progress":
      return "A field crew has started work on the assigned task.";
    case "blocked":
      return "The field crew reported a blocker. An operator is expected to review it.";
    case "verification_pending":
      return "Field work is marked complete. An operator must verify the evidence before closure.";
    case "verified":
      return "An operator verified the resolution evidence and closed the incident.";
    case "reopened":
      return "Verification was rejected. The task has been reopened for corrective work.";
    case "merged":
      return "This report was consolidated into another incident after human review.";
    default:
      return INCIDENT_STATUS_LABELS[status];
  }
}

function TrackContent() {
  const searchParams = useSearchParams();
  const [reportId, setReportId] = useState(searchParams.get("id") ?? "");
  const [result, setResult] = useState<PublicReportStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [rating, setRating] = useState<number>(5);
  const [resolvedSatisfactorily, setResolvedSatisfactorily] = useState<boolean>(true);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [speechNotice, setSpeechNotice] = useState<string | null>(null);
  const autoLookup = useRef(false);

  const lookup = useCallback(async (publicId: string) => {
    const normalized = publicId.trim().toUpperCase();
    if (!normalized) {
      setError("Enter the report ID shown when you submitted the report.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await apiFetch<PublicReportStatus>(
        `/reports/${encodeURIComponent(normalized)}/status`,
      );
      setResult(response);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const requested = searchParams.get("id");
    if (requested && !autoLookup.current) {
      autoLookup.current = true;
      setReportId(requested);
      void lookup(requested);
    }
  }, [searchParams, lookup]);

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  function toggleSpeakStatus() {
    if (!result) return;
    setSpeechNotice(null);
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setSpeechNotice("Audio status readout is not supported in this browser.");
      return;
    }
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const statusText = result.incident_status
      ? INCIDENT_STATUS_LABELS[result.incident_status]
      : "Not linked to an incident yet";
    const explanation = statusExplanation(result.incident_status);
    const summary = result.summary ? `Summary: ${result.summary}` : "";
    const utterance = new SpeechSynthesisUtterance(
      `Report ${result.public_id}. Current status: ${statusText}. ${explanation} ${summary}`,
    );
    utterance.lang = "en-IN";
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => {
      setSpeaking(false);
      setSpeechNotice("Unable to play audio readout on this device.");
    };
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void lookup(reportId);
  }

  async function handleFeedbackSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!result) return;
    setFeedbackError(null);
    setFeedbackSubmitting(true);
    try {
      const updated = await apiFetch<PublicReportStatus>(
        `/reports/${encodeURIComponent(result.public_id)}/feedback`,
        {
          method: "POST",
          body: JSON.stringify({
            rating,
            comment: feedbackComment.trim() || null,
            resolved_satisfactorily: resolvedSatisfactorily,
          }),
        },
      );
      setResult(updated);
    } catch (caught) {
      setFeedbackError(errorMessage(caught));
    } finally {
      setFeedbackSubmitting(false);
    }
  }

  return (
    <div className="shell page-shell">
      <div className="track-panel">
        <header className="page-head" style={{ marginBottom: 22 }}>
          <div className="page-head-copy">
            <span className="eyebrow">Citizen tracking</span>
            <h1>Follow a report</h1>
            <p>
              Enter the report ID you received after submission. This public
              view shows the current incident status and a short summary, not
              internal notes or reporter contact details.
            </p>
          </div>
        </header>

        <form className="surface track-form" onSubmit={handleSubmit}>
          <div className="inline-form">
            <div className="field">
              <label htmlFor="track-report-id">Report ID</label>
              <input
                id="track-report-id"
                value={reportId}
                onChange={(event) => setReportId(event.target.value)}
                placeholder="RPT-2026-XXXXXXXX"
                autoComplete="off"
                spellCheck={false}
                required
              />
              <p className="field-help">
                IDs use the format <span className="mono">RPT-2026-XXXXXXXX</span>.
              </p>
            </div>
            <button
              className="button button-primary"
              type="submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="spinner spinner-small" />
                  Checking…
                </>
              ) : (
                <>
                  <Icon name="search" size={17} />
                  Check status
                </>
              )}
            </button>
          </div>
        </form>

        {error && (
          <div className="notice notice-error" role="alert" style={{ marginTop: 18 }}>
            <Icon name="alert" size={18} />
            <div>
              <strong>Could not find that report</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {loading && (
          <div className="surface track-result" role="status">
            <div className="loading-panel" style={{ minHeight: 150 }}>
              <span className="spinner" />
              <p>Looking up the latest persisted status…</p>
            </div>
          </div>
        )}

        {result && !loading && (
          <section className="surface track-result" aria-live="polite">
            <div className="track-result-head">
              <div>
                <span className="eyebrow">Report status</span>
                <h2 className="mono" style={{ marginTop: 6 }}>
                  {result.public_id}
                </h2>
                <span className="mono">Submitted {formatDate(result.submitted_at)}</span>
              </div>
              <div className="button-row">
                <button
                  type="button"
                  className="button button-secondary button-small"
                  onClick={toggleSpeakStatus}
                >
                  {speaking ? "Stop audio" : "Listen to status"}
                </button>
                {result.is_demo && <DemoBadge />}
                {result.incident_status ? (
                  <StatusPill status={result.incident_status} />
                ) : (
                  <span className="status-pill tone-open">
                    <i aria-hidden="true" />
                    Not linked
                  </span>
                )}
              </div>
            </div>

            {speechNotice && (
              <p className="field-help" style={{ marginBottom: 10 }}>
                {speechNotice}
              </p>
            )}

            {result.summary ? (
              <p className="track-summary">{result.summary}</p>
            ) : (
              <p className="track-summary muted">
                No AI summary is available for this report.
              </p>
            )}

            <div className="notice notice-info" style={{ marginBottom: 18 }}>
              <Icon name="clock" size={18} />
              <div>
                <strong>
                  {result.incident_status
                    ? INCIDENT_STATUS_LABELS[result.incident_status]
                    : "Awaiting an incident"}
                </strong>
                <p>{statusExplanation(result.incident_status)}</p>
              </div>
            </div>

            <div className="track-meta">
              <div>
                <span>Suggested category</span>
                <strong>
                  {result.category ? CATEGORY_LABELS[result.category] : "Pending review"}
                </strong>
              </div>
              <div>
                <span>Incident reference</span>
                <strong className="mono">
                  {result.incident_public_id ?? "Not assigned"}
                </strong>
              </div>
              <div>
                <span>Submitted</span>
                <strong>{formatDate(result.submitted_at)}</strong>
              </div>
              {result.due_at && (
                <div>
                  <span>{result.verified_at ? "Verified" : "SLA target"}</span>
                  <strong>
                    {formatDate(result.verified_at ?? result.due_at)}
                  </strong>
                </div>
              )}
            </div>

            {result.incident_status === "verified" && (
              <div
                style={{
                  marginTop: 20,
                  padding: 16,
                  borderRadius: 10,
                  border: "1px solid var(--border-subtle, #dce2dc)",
                  background: "var(--surface-muted, #f6f8f6)",
                }}
              >
                <span className="eyebrow">Citizen feedback</span>
                <h3 style={{ marginTop: 4, marginBottom: 6 }}>
                  Confirm resolution
                </h3>
                {result.citizen_rating != null ? (
                  <div className="stack-form">
                    <p style={{ margin: 0 }}>
                      <strong>Your rating:</strong> {result.citizen_rating} / 5{" "}
                      {result.citizen_reopen_requested
                        ? "· Follow-up requested"
                        : "· Confirmed resolved"}
                    </p>
                    {result.citizen_feedback && (
                      <p className="field-help" style={{ margin: 0 }}>
                        “{result.citizen_feedback}”
                      </p>
                    )}
                  </div>
                ) : (
                  <form className="stack-form" onSubmit={handleFeedbackSubmit}>
                    {feedbackError && (
                      <div className="notice notice-error" role="alert">
                        <Icon name="alert" size={16} />
                        <span>{feedbackError}</span>
                      </div>
                    )}
                    <div className="field">
                      <span className="field-label">Rate the cleanup</span>
                      <div style={{ display: "flex", gap: 6 }}>
                        {[1, 2, 3, 4, 5].map((value) => (
                          <button
                            key={value}
                            type="button"
                            className={`button button-small ${
                              rating === value ? "button-primary" : "button-secondary"
                            }`}
                            onClick={() => setRating(value)}
                            aria-pressed={rating === value}
                          >
                            {value} ★
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="field">
                      <span className="field-label">Was the waste cleared?</span>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button
                          type="button"
                          className={`button button-small ${
                            resolvedSatisfactorily ? "button-primary" : "button-secondary"
                          }`}
                          onClick={() => setResolvedSatisfactorily(true)}
                          aria-pressed={resolvedSatisfactorily}
                        >
                          Yes, resolved
                        </button>
                        <button
                          type="button"
                          className={`button button-small ${
                            !resolvedSatisfactorily ? "button-primary" : "button-secondary"
                          }`}
                          onClick={() => setResolvedSatisfactorily(false)}
                          aria-pressed={!resolvedSatisfactorily}
                        >
                          No, issue still persists
                        </button>
                      </div>
                    </div>
                    <div className="field">
                      <label htmlFor="citizen-feedback-comment">
                        Comment <span className="optional">(optional)</span>
                      </label>
                      <textarea
                        id="citizen-feedback-comment"
                        rows={2}
                        maxLength={500}
                        value={feedbackComment}
                        onChange={(e) => setFeedbackComment(e.target.value)}
                        placeholder="Share whether the site is clean or if follow-up is needed."
                      />
                    </div>
                    <button
                      type="submit"
                      className="button button-primary button-small"
                      disabled={feedbackSubmitting}
                    >
                      {feedbackSubmitting ? "Submitting…" : "Submit feedback"}
                    </button>
                  </form>
                )}
              </div>
            )}

            <div className="button-row" style={{ marginTop: 22 }}>
              <Link className="button button-secondary" href="/report">
                Report another issue
              </Link>
              {result.incident_status && (
                <Link className="button button-primary" href="/login">
                  Staff sign in
                  <Icon name="arrow" size={17} />
                </Link>
              )}
            </div>
          </section>
        )}

        <div className="provenance-note">
          <Icon name="shield" size={16} />
          <span>
            Status is read from the persisted incident record. AI triage and
            duplicate suggestions remain advisory until a human reviews them.
          </span>
        </div>
      </div>
    </div>
  );
}

export default function TrackPage() {
  return (
    <Suspense
      fallback={
        <div className="shell page-loading" role="status">
          <span className="spinner" />
          <p>Loading report tracking…</p>
        </div>
      }
    >
      <TrackContent />
    </Suspense>
  );
}
