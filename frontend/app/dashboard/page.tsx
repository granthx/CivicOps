"use client";

import Link from "next/link";
import { useCallback, useDeferredValue, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { RoleGate } from "@/components/RoleGate";
import { IncidentMap, type MapPoint } from "@/components/IncidentMap";
import {
  DataProvenance,
  DemoBadge,
  ErrorPanel,
  LoadingPanel,
  PriorityPill,
  SlaPill,
  StatusPill,
} from "@/components/Ui";
import { apiBlob, apiFetch, buildQuery, errorMessage } from "@/lib/api";
import {
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  formatShortDate,
  parseApiDate,
} from "@/lib/format";
import type {
  AnalyticsSummary,
  CountItem,
  HotspotCluster,
  HotspotListResponse,
  Incident,
  IncidentStatus,
  Page,
  Priority,
  SlaSweepResponse,
  Ward,
} from "@/lib/types";

const PRIORITY_MIX: Priority[] = ["critical", "high", "medium", "low"];
const PRIORITY_COLORS: Record<Priority, string> = {
  critical: "#a83f2d",
  high: "#bb6b22",
  medium: "#4d735c",
  low: "#7f897f",
};

const statusOptions: { value: IncidentStatus | ""; label: string }[] = [
  { value: "", label: "All active" },
  { value: "open", label: "Awaiting triage" },
  { value: "triaged", label: "Triaged" },
  { value: "assigned", label: "Assigned" },
  { value: "in_progress", label: "In progress" },
  { value: "blocked", label: "Blocked" },
  { value: "verification_pending", label: "Verification pending" },
  { value: "verified", label: "Verified" },
  { value: "reopened", label: "Reopened" },
];

function ageLabel(value: string): string {
  const created = parseApiDate(value).getTime();
  if (Number.isNaN(created)) return "unknown age";
  const hours = Math.max(0, (Date.now() - created) / 3_600_000);
  if (hours < 1) return "under 1h old";
  if (hours < 24) return `${Math.floor(hours)}h old`;
  return `${Math.floor(hours / 24)}d old`;
}

function Breakdown({
  items,
  emptyLabel,
}: {
  items: CountItem[];
  emptyLabel: string;
}) {
  if (items.length === 0) {
    return <p className="field-help">{emptyLabel}</p>;
  }
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <div className="breakdown-list">
      {items.slice(0, 6).map((item) => (
        <div className="breakdown-row" key={item.key}>
          <span>{item.label}</span>
          <strong>{item.count}</strong>
          <div className="breakdown-bar" aria-hidden="true">
            <i style={{ width: `${(item.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function DashboardContent() {
  const [incidents, setIncidents] = useState<Page<Incident> | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [hotspotData, setHotspotData] = useState<HotspotListResponse | null>(null);
  const [showHotspots, setShowHotspots] = useState(true);
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);
  const [wards, setWards] = useState<Ward[]>([]);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [status, setStatus] = useState<IncidentStatus | "">("");
  const [priority, setPriority] = useState<Priority | "">("");
  const [wardId, setWardId] = useState("");
  const [includeResolved, setIncludeResolved] = useState(false);
  const [slaBreachedOnly, setSlaBreachedOnly] = useState(false);
  const [sweeping, setSweeping] = useState(false);
  const [sweepMessage, setSweepMessage] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const requestRef = useRef(0);

  const fetchWorkspace = useCallback(async () => {
    const requestId = ++requestRef.current;
    setRefreshing(true);
    setError(null);
    try {
      const query = buildQuery({
        status: status ? [status] : [],
        priority: priority || undefined,
        ward_id: wardId || undefined,
        search: deferredSearch.trim() || undefined,
        include_resolved: includeResolved,
        page,
        page_size: 25,
      });
      const hotspotQuery = buildQuery({
        ward_id: wardId || undefined,
      });
      const [incidentPage, analytics, hotspotsRes] = await Promise.all([
        apiFetch<Page<Incident>>(`/incidents${query}`),
        apiFetch<AnalyticsSummary>("/analytics/summary"),
        apiFetch<HotspotListResponse>(`/analytics/hotspots${hotspotQuery}`),
      ]);
      if (requestId !== requestRef.current) return;
      setIncidents(incidentPage);
      setSummary(analytics);
      setHotspotData(hotspotsRes);
      setLastUpdated(new Date());
    } catch (caught) {
      if (requestId !== requestRef.current) return;
      setError(errorMessage(caught));
    } finally {
      if (requestId === requestRef.current) {
        setRefreshing(false);
        setLoading(false);
      }
    }
  }, [status, priority, wardId, deferredSearch, includeResolved, page]);

  useEffect(() => {
    // Authenticated, client-side fetch: loading state is intentionally set
    // before the request. This is a mount/filter synchronization effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchWorkspace();
  }, [fetchWorkspace]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Ward[]>("/wards")
      .then((response) => {
        if (!cancelled) setWards(response);
      })
      .catch(() => {
        // Ward options are a convenience; the queue still works without them.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const points: MapPoint[] =
    incidents?.items.map((incident) => ({
      id: incident.id,
      latitude: incident.latitude,
      longitude: incident.longitude,
      publicId: incident.public_id,
      title: incident.title,
      priority: incident.priority,
      reportCount: incident.report_count,
    })) ?? [];

  const priorityCounts = PRIORITY_MIX.map((value) => ({
    value,
    count: incidents?.items.filter((incident) => incident.priority === value).length ?? 0,
  }));
  const priorityTotal = priorityCounts.reduce((total, item) => total + item.count, 0);

  function applyStatFilter(next: IncidentStatus | "", resolved = false) {
    setStatus(next);
    setIncludeResolved(resolved);
    setPage(1);
  }

  function clearFilters() {
    setSearch("");
    setStatus("");
    setPriority("");
    setWardId("");
    setIncludeResolved(false);
    setSlaBreachedOnly(false);
    setPage(1);
  }

  async function runSlaSweep() {
    setSweeping(true);
    setSweepMessage(null);
    try {
      const res = await apiFetch<SlaSweepResponse>("/analytics/sla-sweep", {
        method: "POST",
      });
      setSweepMessage(
        res.escalated_count > 0
          ? `Escalated ${res.escalated_count} overdue work order${res.escalated_count === 1 ? "" : "s"}.`
          : "No new SLA breaches to escalate.",
      );
      void fetchWorkspace();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSweeping(false);
    }
  }

  async function exportCsv() {
    setExporting(true);
    try {
      const blob = await apiBlob("/analytics/export.csv");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "civicops-incidents.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setExporting(false);
    }
  }

  const displayedItems = slaBreachedOnly
    ? (incidents?.items.filter((inc) => inc.sla?.sla_state === "breached") ?? [])
    : (incidents?.items ?? []);

  const hasFilters =
    search.length > 0 ||
    status !== "" ||
    priority !== "" ||
    wardId !== "" ||
    includeResolved ||
    slaBreachedOnly;

  return (
    <div className="shell dashboard-page">
      <header className="dashboard-head">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="eyebrow">Operations</span>
            <DemoBadge compact />
          </div>
          <h1>Incident queue</h1>
          <p>
            Review AI-assisted suggestions, confirm operations and keep every
            decision visible. The map and queue use persisted API data.
          </p>
        </div>
        <div className="dashboard-head-actions">
          <div className="refresh-stamp">
            <div>{lastUpdated ? `Updated ${formatShortDate(lastUpdated.toISOString())}` : "Not loaded"}</div>
            {refreshing && <div>Refreshing…</div>}
            {sweepMessage && <div>{sweepMessage}</div>}
          </div>
          <button
            className="button button-secondary button-small"
            type="button"
            onClick={() => void runSlaSweep()}
            disabled={sweeping}
          >
            {sweeping ? "Sweeping…" : "Run SLA sweep"}
          </button>
          <button
            className="button button-secondary button-small"
            type="button"
            onClick={() => void exportCsv()}
            disabled={exporting}
          >
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
          <button
            className="button button-secondary button-small"
            type="button"
            onClick={() => void fetchWorkspace()}
            disabled={refreshing}
          >
            <Icon name="refresh" size={15} />
            Refresh
          </button>
        </div>
      </header>

      {summary && (
        <div className="stat-grid" aria-label="Operational summary">
          <button
            type="button"
            className="stat-card"
            onClick={clearFilters}
            title="Show all active incidents"
          >
            <span className="stat-label">Active incidents</span>
            <strong>{summary.active_incidents}</strong>
            <small>{summary.unassigned_incidents} unassigned</small>
          </button>
          <button
            type="button"
            className="stat-card is-attention"
            onClick={() => applyStatFilter("open")}
          >
            <span className="stat-label">Awaiting triage</span>
            <strong>{summary.awaiting_triage}</strong>
            <small>Human review required</small>
          </button>
          <button
            type="button"
            className="stat-card"
            onClick={() => applyStatFilter("in_progress")}
          >
            <span className="stat-label">In progress</span>
            <strong>{summary.in_progress}</strong>
            <small>Crews working</small>
          </button>
          <button
            type="button"
            className="stat-card"
            onClick={() => applyStatFilter("verification_pending")}
          >
            <span className="stat-label">Verification pending</span>
            <strong>{summary.verification_pending}</strong>
            <small>Evidence review</small>
          </button>
          <button
            type="button"
            className="stat-card is-alert"
            onClick={() => applyStatFilter("blocked")}
          >
            <span className="stat-label">Blocked</span>
            <strong>{summary.blocked}</strong>
            <small>Needs intervention</small>
          </button>
          <button
            type="button"
            className="stat-card"
            onClick={() => applyStatFilter("verified")}
          >
            <span className="stat-label">Verified · 7d</span>
            <strong>{summary.verified_last_7_days}</strong>
            <small>{summary.reports_last_7_days} reports this week</small>
          </button>
          <button
            type="button"
            className={`stat-card ${summary.sla_breached_count > 0 ? "is-alert" : ""}`}
            onClick={() => {
              setSlaBreachedOnly((prev) => !prev);
              setIncludeResolved(false);
              setPage(1);
            }}
            title="Toggle overdue / SLA-breached incidents"
          >
            <span className="stat-label">SLA breached</span>
            <strong>{summary.sla_breached_count}</strong>
            <small>
              {slaBreachedOnly ? "Showing breached only" : `${summary.sla_at_risk_count} at risk`}
            </small>
          </button>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: 18 }}>
          <ErrorPanel message={error} onRetry={() => void fetchWorkspace()} />
        </div>
      )}

      <div className="workspace">
        <section className="panel workspace-map" aria-label="Incident hotspot map">
          <div className="workspace-map-head">
            <div>
              <h2>Hotspot map</h2>
              <p>
                Showing {incidents?.total ?? 0} matching incident
                {incidents?.total === 1 ? "" : "s"} ·{" "}
                {hotspotData?.clusters.length ?? 0} spatial cluster
                {hotspotData?.clusters.length === 1 ? "" : "s"}
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button
                type="button"
                className={`button button-small ${showHotspots ? "button-primary" : "button-secondary"}`}
                onClick={() => setShowHotspots((prev) => !prev)}
                aria-pressed={showHotspots}
              >
                {showHotspots ? "Hotspot zones on" : "Hotspot zones off"}
              </button>
              <span className="panel-note">Ward view</span>
            </div>
          </div>
          <IncidentMap
            points={points}
            hotspots={hotspotData?.clusters ?? []}
            showHotspots={showHotspots}
            selectedClusterId={selectedClusterId}
            onSelectCluster={(cluster: HotspotCluster) => {
              setSelectedClusterId(cluster.cluster_id);
              const firstIncidentId = cluster.incident_ids[0];
              if (firstIncidentId) {
                setSelectedId(firstIncidentId);
                document
                  .getElementById(`queue-incident-${firstIncidentId}`)
                  ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
              }
            }}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id);
              document
                .getElementById(`queue-incident-${id}`)
                ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }}
            height={430}
            label="Incident priority map"
          />
          <div className="priority-mix">
            <h3>Priority mix in this view</h3>
            <div className="mix-bar" aria-hidden="true">
              {priorityCounts.map((item) =>
                item.count > 0 ? (
                  <span
                    key={item.value}
                    style={{
                      width: `${(item.count / Math.max(priorityTotal, 1)) * 100}%`,
                      background: PRIORITY_COLORS[item.value],
                    }}
                  />
                ) : null,
              )}
            </div>
            <div className="mix-legend">
              {priorityCounts.map((item) => (
                <span key={item.value}>
                  <i style={{ background: PRIORITY_COLORS[item.value] }} />
                  {PRIORITY_LABELS[item.value]} {item.count}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section className="panel workspace-queue" aria-label="Incident queue">
          <div className="queue-head">
            <div>
              <h2>Priority queue</h2>
              <p className="field-help" style={{ marginTop: 2 }}>
                Highest priority and oldest first
              </p>
            </div>
            <span className="queue-count">{incidents?.total ?? 0}</span>
          </div>

          <div className="queue-toolbar">
            <div className="search-field">
              <Icon name="search" size={15} />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                placeholder="Search ID, title or address"
                aria-label="Search incidents"
                spellCheck={false}
              />
            </div>
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as IncidentStatus | "");
                setPage(1);
              }}
              aria-label="Filter by status"
            >
              {statusOptions.map((option) => (
                <option value={option.value} key={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={priority}
              onChange={(event) => {
                setPriority(event.target.value as Priority | "");
                setPage(1);
              }}
              aria-label="Filter by priority"
            >
              <option value="">All priorities</option>
              {PRIORITY_MIX.map((value) => (
                <option value={value} key={value}>
                  {PRIORITY_LABELS[value]}
                </option>
              ))}
            </select>
            <select
              value={wardId}
              onChange={(event) => {
                setWardId(event.target.value);
                setPage(1);
              }}
              aria-label="Filter by ward"
            >
              <option value="">All wards</option>
              {wards.map((ward) => (
                <option value={String(ward.id)} key={ward.id}>
                  {ward.name}
                </option>
              ))}
            </select>
          </div>

          <div className="queue-toolbar-foot">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={includeResolved}
                disabled={status !== "" && status !== "verified"}
                onChange={(event) => {
                  setIncludeResolved(event.target.checked);
                  setPage(1);
                }}
              />
              Include resolved in active view
            </label>
            {hasFilters ? (
              <button className="text-button" type="button" onClick={clearFilters}>
                Clear filters
              </button>
            ) : (
              <span>{refreshing ? "Updating…" : "Filters ready"}</span>
            )}
          </div>

          {loading && !incidents ? (
            <LoadingPanel label="Loading incident queue…" />
          ) : displayedItems.length > 0 ? (
            <ul className="queue-list">
              {displayedItems.map((incident) => (
                <li
                  className={
                    selectedId === incident.id
                      ? "queue-card is-selected"
                      : "queue-card"
                  }
                  id={`queue-incident-${incident.id}`}
                  key={incident.id}
                >
                  <Link
                    href={`/incidents/${incident.id}`}
                    onMouseEnter={() => setSelectedId(incident.id)}
                  >
                    <div className="queue-card-top">
                      <PriorityPill priority={incident.priority} />
                      <StatusPill status={incident.status} />
                      <SlaPill sla={incident.sla} />
                      <span className="mono">{incident.public_id}</span>
                    </div>
                    <h3>{incident.title}</h3>
                    <p>
                      {incident.address ?? "Location pin submitted"} ·{" "}
                      {incident.ward.name}
                    </p>
                    <div className="queue-card-footer">
                      <span>{CATEGORY_LABELS[incident.category]}</span>
                      <span>
                        <strong>{incident.report_count}</strong> report
                        {incident.report_count === 1 ? "" : "s"}
                      </span>
                      <span>{ageLabel(incident.created_at)}</span>
                      {incident.active_work_order && (
                        <span>
                          <strong>{incident.active_work_order.team_name}</strong>
                        </span>
                      )}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="queue-empty">
              <p style={{ marginBottom: 10 }}>
                No incidents match the current filters.
              </p>
              {hasFilters && (
                <button
                  className="button button-small button-secondary"
                  type="button"
                  onClick={clearFilters}
                >
                  Clear filters
                </button>
              )}
            </div>
          )}

          {incidents && incidents.pages > 1 && (
            <div className="pagination">
              <span>
                Page {incidents.page} of {incidents.pages}
              </span>
              <div className="button-row">
                <button
                  className="button button-small button-secondary"
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={incidents.page <= 1 || refreshing}
                >
                  <Icon name="chevron-left" size={14} />
                  Previous
                </button>
                <button
                  className="button button-small button-secondary"
                  type="button"
                  onClick={() =>
                    setPage((current) =>
                      Math.min(incidents.pages, current + 1),
                    )
                  }
                  disabled={incidents.page >= incidents.pages || refreshing}
                >
                  Next
                  <Icon name="chevron-right" size={14} />
                </button>
              </div>
            </div>
          )}
        </section>
      </div>

      {summary && (
        <div className="dashboard-lower">
          <section className="panel">
            <div className="panel-head">
              <h2>Category mix</h2>
              <span className="panel-note">All records</span>
            </div>
            <Breakdown
              items={summary.category_counts}
              emptyLabel="No categorised incidents yet."
            />
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Ward load</h2>
              <span className="panel-note">Across wards</span>
            </div>
            <Breakdown
              items={summary.ward_counts}
              emptyLabel="No ward records yet."
            />
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Chronic hotspot clusters</h2>
              <span className="panel-note">
                {hotspotData ? `${hotspotData.window_days}d · ${hotspotData.radius_m}m` : "Spatial"}
              </span>
            </div>
            {!hotspotData || hotspotData.clusters.length === 0 ? (
              <p className="field-help">
                No recurring spatial clusters detected in the current window.
              </p>
            ) : (
              <div className="breakdown-list">
                {hotspotData.clusters.slice(0, 4).map((cluster) => (
                  <div
                    key={cluster.cluster_id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                      paddingBottom: 8,
                      borderBottom: "1px solid var(--border-subtle, #e4e8e4)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 10,
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedClusterId(cluster.cluster_id);
                            setShowHotspots(true);
                            if (cluster.incident_ids[0]) {
                              setSelectedId(cluster.incident_ids[0]);
                            }
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            padding: 0,
                            cursor: "pointer",
                            fontSize: "0.8rem",
                            fontWeight: 650,
                            textAlign: "left",
                            color: "inherit",
                            textDecoration: "underline",
                          }}
                        >
                          {cluster.cluster_id} · {cluster.ward_name}
                        </button>
                        <div className="field-help">
                          {cluster.incident_count} incidents · {cluster.total_reports} reports ·{" "}
                          {CATEGORY_LABELS[cluster.top_category]} · Score {cluster.chronic_score}
                        </div>
                      </div>
                      <PriorityPill priority={cluster.max_priority} />
                    </div>
                    <div className="field-help" style={{ fontSize: "0.74rem" }}>
                      {cluster.recommendation}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      <DataProvenance />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RoleGate roles={["operator", "admin"]}>
      <DashboardContent />
    </RoleGate>
  );
}
