"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { Icon } from "@/components/Icon";
import { RoleGate } from "@/components/RoleGate";
import {
  DemoBadge,
  ErrorPanel,
  LoadingPanel,
  PriorityPill,
  SlaPill,
  StatusPill,
} from "@/components/Ui";
import { apiFetch, buildQuery, errorMessage } from "@/lib/api";
import {
  CATEGORY_LABELS,
  WORK_ORDER_STATUS_LABELS,
  formatDate,
} from "@/lib/format";
import type { Page, WorkOrder, WorkOrderStatus } from "@/lib/types";

const statusFilters: { value: WorkOrderStatus | ""; label: string }[] = [
  { value: "", label: "Active" },
  { value: "assigned", label: "Assigned" },
  { value: "in_progress", label: "In progress" },
  { value: "blocked", label: "Blocked" },
  { value: "completed", label: "Awaiting verification" },
  { value: "verified", label: "Verified" },
];

function FieldContent() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<Page<WorkOrder> | null>(null);
  const [status, setStatus] = useState<WorkOrderStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (initial = false) => {
      if (initial) setLoading(true);
      setRefreshing(true);
      setError(null);
      try {
        const query = buildQuery({
          status: status ? [status] : [],
          include_verified: false,
          page_size: 100,
        });
        const response = await apiFetch<Page<WorkOrder>>(`/work-orders${query}`);
        setOrders(response);
      } catch (caught) {
        setError(errorMessage(caught));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [status],
  );

  useEffect(() => {
    // Authenticated, client-side fetch: loading state is intentionally set
    // before the request. This is a mount/filter synchronization effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(true);
  }, [load]);

  const isOperator = user?.role === "operator" || user?.role === "admin";
  const activeCount =
    orders?.items.filter((order) => order.status !== "verified").length ?? 0;

  return (
    <div className="shell field-page">
      <header className="dashboard-head">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="eyebrow">{isOperator ? "Operations" : "Field workspace"}</span>
            <DemoBadge compact />
          </div>
          <h1>{isOperator ? "Field task board" : "My field tasks"}</h1>
          <p>
            {isOperator
              ? "Every crew task across wards. Open one to follow progress, evidence and verification."
              : user?.team_name
                ? `Showing work orders assigned to ${user.team_name}. The API scopes this list to your team.`
                : "No team is assigned to this account. Ask an administrator to configure crew access."}
          </p>
        </div>
        <div className="dashboard-head-actions">
          <span className="refresh-stamp">
            {activeCount} active task{activeCount === 1 ? "" : "s"} in view
          </span>
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

      <div className="field-toolbar">
        <div className="segmented" role="group" aria-label="Filter tasks by status">
          {statusFilters.map((filter) => (
            <button
              type="button"
              key={filter.value}
              className={status === filter.value ? "is-active" : undefined}
              onClick={() => setStatus(filter.value)}
              aria-pressed={status === filter.value}
            >
              {filter.label}
            </button>
          ))}
        </div>
        {isOperator && (
          <Link className="button button-secondary button-small" href="/dashboard">
            <Icon name="chevron-left" size={15} />
            Incident queue
          </Link>
        )}
      </div>

      {error && (
        <div style={{ marginBottom: 18 }}>
          <ErrorPanel message={error} onRetry={() => void load()} />
        </div>
      )}

      {loading && !orders ? (
        <LoadingPanel label="Loading field tasks…" />
      ) : orders && orders.items.length > 0 ? (
        <div className="task-grid">
          {orders.items.map((order) => (
            <article className="task-card" key={order.id}>
              <div className="task-card-head">
                <StatusPill status={order.status} />
                <PriorityPill priority={order.incident.priority} />
                <SlaPill sla={order.sla} />
                <span className="mono">{order.public_id}</span>
              </div>
              <div className="task-card-body">
                <h3>
                  <Link href={`/field/${order.id}`}>{order.incident.title}</Link>
                </h3>
                <p>{order.incident.address ?? order.incident.ward.name}</p>
                <div className="task-card-meta">
                  <span>{CATEGORY_LABELS[order.incident.category]}</span>
                  <span>{order.incident.ward.name}</span>
                  <span>Due {formatDate(order.due_at)}</span>
                </div>
                <div className="task-card-meta">
                  <span className="mono">{order.incident.public_id}</span>
                  {isOperator && <span>{order.team.name}</span>}
                  <span>
                    {order.evidence.length} evidence item
                    {order.evidence.length === 1 ? "" : "s"}
                  </span>
                </div>
              </div>
              <div className="task-card-foot">
                <span>
                  {order.status === "verified"
                    ? `Verified ${formatDate(order.verified_at)}`
                    : order.status === "completed"
                      ? "Operator verification required"
                      : WORK_ORDER_STATUS_LABELS[order.status]}
                </span>
                <Link className="text-button" href={`/field/${order.id}`}>
                  Open task
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="surface empty-panel">
          <span className="empty-icon">
            <Icon name="check" size={25} />
          </span>
          <strong>No tasks in this view</strong>
          <p>
            {status === ""
              ? "There are no active tasks for this account. Try another filter or refresh."
              : "No work orders match this status for your account."}
          </p>
        </div>
      )}

      <div className="provenance-note">
        <Icon name="shield" size={16} />
        <span>
          Reporter contact details are not included in field task responses.
          Evidence uploads are validated and stored through the authenticated
          API.
        </span>
      </div>
    </div>
  );
}

export default function FieldPage() {
  return (
    <RoleGate roles={["field_worker", "operator", "admin"]}>
      <FieldContent />
    </RoleGate>
  );
}
