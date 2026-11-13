"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { CATEGORY_LABELS, formatShortDate, parseApiDate } from "@/lib/format";
import type { IncidentStatus, PublicIncidentMapItem } from "@/lib/types";
import { IncidentMap } from "./IncidentMap";
import { DemoBadge, ErrorPanel, LoadingPanel, PriorityPill, StatusPill } from "./Ui";

const DELHI_WARDS = new Set(["Connaught Place Ward", "Lajpat Nagar Ward"]);

type CityFilter = "all" | "delhi" | "bengaluru";
type StatusFilter = "all" | IncidentStatus;

export function PublicMapSection() {
  const [items, setItems] = useState<PublicIncidentMapItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [cityFilter, setCityFilter] = useState<CityFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [randomizing, setRandomizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        let data = await apiFetch<PublicIncidentMapItem[]>("/incidents/public-map");
        const today = new Date().toDateString();
        const hasTodayDelhiDemo = data.some(
          (item) =>
            item.is_demo &&
            item.ward_name &&
            DELHI_WARDS.has(item.ward_name) &&
            parseApiDate(item.created_at).toDateString() === today,
        );
        if (!hasTodayDelhiDemo) {
          data = await apiFetch<PublicIncidentMapItem[]>(
            "/incidents/public-map/randomize-demo",
            { method: "POST" },
          );
        }
        if (!active) return;
        setItems(data);
        if (data.length > 0) {
          setSelectedId(data[0].id);
        }
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof Error
            ? err.message
            : "Could not load public complaint map."
        );
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  async function handleRandomizeDelhi() {
    setRandomizing(true);
    setError(null);
    try {
      const data = await apiFetch<PublicIncidentMapItem[]>(
        "/incidents/public-map/randomize-demo",
        { method: "POST" },
      );
      setItems(data);
      const firstDelhi = data.find(
        (item) => item.ward_name && DELHI_WARDS.has(item.ward_name),
      );
      if (firstDelhi) {
        setSelectedId(firstDelhi.id);
      } else if (data.length > 0) {
        setSelectedId(data[0].id);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not randomize Delhi demo complaints."
      );
    } finally {
      setRandomizing(false);
    }
  }

  const stats = useMemo(() => {
    let open = 0;
    let inProgress = 0;
    let verified = 0;
    for (const item of items) {
      if (item.status === "open" || item.status === "triaged") open += 1;
      else if (item.status === "in_progress" || item.status === "assigned")
        inProgress += 1;
      else if (item.status === "verified") verified += 1;
    }
    return { total: items.length, open, inProgress, verified };
  }, [items]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      const isDelhi = Boolean(item.ward_name && DELHI_WARDS.has(item.ward_name));
      if (cityFilter === "delhi" && !isDelhi) return false;
      if (cityFilter === "bengaluru" && isDelhi) return false;
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (q) {
        const hay = `${item.public_id} ${item.title} ${item.ward_name ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, cityFilter, statusFilter, search]);

  const effectiveSelectedId = useMemo(() => {
    if (filteredItems.some((item) => item.id === selectedId)) return selectedId;
    return filteredItems[0]?.id ?? null;
  }, [filteredItems, selectedId]);

  const mapPoints = filteredItems.map((item) => ({
    id: item.id,
    latitude: item.latitude,
    longitude: item.longitude,
    publicId: item.public_id,
    title: item.title,
    priority: item.priority,
    reportCount: item.report_count,
  }));

  const selected =
    filteredItems.find((item) => item.id === effectiveSelectedId) ?? null;

  return (
    <section className="home-section" aria-labelledby="public-map-heading">
      <div className="shell">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Public complaint map</span>
            <h2 id="public-map-heading">
              Live ward complaints and resolution progress.
            </h2>
            <p>
              Citizens can inspect lodged waste incidents, ward locations,
              report counts and verification status without signing in.
              Reporter names, phone numbers and internal staff notes are never
              shown publicly.
            </p>
          </div>
          <div className="pill-row">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void handleRandomizeDelhi()}
              disabled={loading || randomizing}
            >
              {randomizing ? "Randomizing..." : "Randomize Delhi demo"}
            </button>
            <Link className="button button-secondary" href="/report">
              Report a new issue
            </Link>
          </div>
        </div>

        {loading ? (
          <LoadingPanel label="Loading public ward complaints..." />
        ) : error ? (
          <ErrorPanel message={error} />
        ) : items.length === 0 ? (
          <div className="panel">
            <p className="muted">
              No public waste incidents are currently listed. Use the Report an
              issue page to submit the first complaint.
            </p>
          </div>
        ) : (
          <>
            <div className="public-stats-strip" aria-label="Public complaint summary">
              <div className="public-stat-card">
                <span className="public-stat-label">Public incidents</span>
                <strong>{stats.total}</strong>
              </div>
              <div className="public-stat-card">
                <span className="public-stat-label">Awaiting triage</span>
                <strong>{stats.open}</strong>
              </div>
              <div className="public-stat-card">
                <span className="public-stat-label">In progress</span>
                <strong>{stats.inProgress}</strong>
              </div>
              <div className="public-stat-card">
                <span className="public-stat-label">Verified closed</span>
                <strong>{stats.verified}</strong>
              </div>
            </div>

            <div className="public-map-toolbar">
              <div className="pill-row" role="group" aria-label="Filter by city">
                {(
                  [
                    ["all", "All cities"],
                    ["delhi", "New Delhi"],
                    ["bengaluru", "Bengaluru"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    className={
                      cityFilter === value
                        ? "button button-primary button-small"
                        : "button button-secondary button-small"
                    }
                    onClick={() => setCityFilter(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div className="public-map-filters">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                  aria-label="Filter by status"
                >
                  <option value="all">All statuses</option>
                  <option value="open">Awaiting triage</option>
                  <option value="in_progress">In progress</option>
                  <option value="verification_pending">Verification pending</option>
                  <option value="blocked">Blocked</option>
                  <option value="verified">Verified</option>
                </select>
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search ward, issue, or INC-2026-..."
                  aria-label="Search public complaints"
                />
              </div>
            </div>

            {filteredItems.length === 0 ? (
              <div className="panel">
                <p className="muted">
                  No complaints match the current city, status, or search filter.
                </p>
              </div>
            ) : (
              <div className="public-map-grid">
                <div className="public-map-canvas">
                  <IncidentMap
                    points={mapPoints}
                    selectedId={effectiveSelectedId}
                    onSelect={setSelectedId}
                    height={420}
                    label="Public ward waste complaint map"
                  />
                  {selected ? (
                    <div className="public-map-selected">
                      <div className="public-map-selected-head">
                        <span className="mono">{selected.public_id}</span>
                        <div className="pill-row">
                          <StatusPill status={selected.status} />
                          <PriorityPill priority={selected.priority} />
                          {selected.is_demo ? <DemoBadge /> : null}
                        </div>
                      </div>
                      <strong>{selected.title}</strong>
                      <div className="public-map-selected-foot">
                        <p className="muted">
                          {CATEGORY_LABELS[selected.category]} ·{" "}
                          {selected.ward_name || "Unassigned ward"} ·{" "}
                          {selected.report_count}{" "}
                          {selected.report_count === 1 ? "report" : "reports"} ·
                          Logged {formatShortDate(selected.created_at)}
                          {selected.verified_at
                            ? ` · Verified ${formatShortDate(selected.verified_at)}`
                            : ""}
                        </p>
                        {selected.primary_report_public_id ? (
                          <Link
                            className="button button-secondary button-small"
                            href={`/track?id=${encodeURIComponent(selected.primary_report_public_id)}`}
                          >
                            Track status
                          </Link>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="public-complaint-list" role="list" aria-label="Lodged complaints">
                  {filteredItems.map((item) => {
                    const isSelected = item.id === effectiveSelectedId;
                    return (
                      <div
                        key={item.id}
                        role="listitem"
                        className={
                          isSelected
                            ? "public-complaint-card is-selected"
                            : "public-complaint-card"
                        }
                        onClick={() => setSelectedId(item.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setSelectedId(item.id);
                          }
                        }}
                        tabIndex={0}
                      >
                        <div className="public-complaint-card-top">
                          <span className="mono">{item.public_id}</span>
                          <div className="pill-row">
                            <StatusPill status={item.status} />
                            <PriorityPill priority={item.priority} />
                          </div>
                        </div>
                        <strong>{item.title}</strong>
                        <div className="public-complaint-card-foot">
                          <div className="public-complaint-card-meta">
                            <span>{CATEGORY_LABELS[item.category]}</span>
                            <span>{item.ward_name || "Ward pending"}</span>
                            <span>
                              {item.report_count}{" "}
                              {item.report_count === 1 ? "report" : "reports"}
                            </span>
                            <span>{formatShortDate(item.created_at)}</span>
                          </div>
                          {item.primary_report_public_id ? (
                            <Link
                              className="public-track-link"
                              href={`/track?id=${encodeURIComponent(item.primary_report_public_id)}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              Track →
                            </Link>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
