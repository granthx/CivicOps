from __future__ import annotations

from datetime import timedelta

from app.config import settings
from app.domain import IncidentStatus
from app.services.notifications import dispatch_sla_escalation_alert
from app.services.sla import compute_sla_status
from app.utils import utcnow

from .conftest import login_headers


def test_compute_sla_status_states():
    now = utcnow()
    # On track
    on_track = compute_sla_status(
        created_at=now - timedelta(hours=2),
        due_at=now + timedelta(hours=22),
        priority="high",
        status="in_progress",
        now=now,
    )
    assert on_track.sla_state == "on_track"
    assert on_track.is_overdue is False

    # At risk (>= 75% elapsed)
    at_risk = compute_sla_status(
        created_at=now - timedelta(hours=20),
        due_at=now + timedelta(hours=4),
        priority="high",
        status="in_progress",
        now=now,
    )
    assert at_risk.sla_state == "at_risk"
    assert at_risk.is_overdue is False

    # Breached
    breached = compute_sla_status(
        created_at=now - timedelta(hours=30),
        due_at=now - timedelta(hours=6),
        priority="high",
        status="in_progress",
        now=now,
    )
    assert breached.sla_state == "breached"
    assert breached.is_overdue is True
    assert breached.remaining_hours < 0

    # Met when verified before due_at
    met = compute_sla_status(
        created_at=now - timedelta(hours=10),
        due_at=now + timedelta(hours=14),
        priority="high",
        status=IncidentStatus.VERIFIED.value,
        verified_at=now - timedelta(hours=1),
        now=now,
    )
    assert met.sla_state == "met"
    assert met.is_overdue is False


def test_work_order_auto_sla_and_analytics_counts(client):
    operator = login_headers(client, "demo.operator@civicops.local")
    incidents = client.get("/api/incidents", headers=operator).json()["items"]
    triaged_or_open = next(
        item for item in incidents if item["status"] in {"open", "triaged"}
    )
    if triaged_or_open["status"] == "open":
        client.patch(
            f"/api/incidents/{triaged_or_open['id']}/triage",
            headers=operator,
            json={
                "category": triaged_or_open["category"],
                "severity": triaged_or_open["severity"],
                "note": "Confirmed for SLA test.",
            },
        )

    teams = client.get("/api/teams", headers=operator).json()
    team_id = next(t["id"] for t in teams if t["ward_id"] == triaged_or_open["ward"]["id"])
    order_res = client.post(
        f"/api/incidents/{triaged_or_open['id']}/work-orders",
        headers=operator,
        json={
            "team_id": team_id,
            "instructions": "Clear waste within SLA window.",
        },
    )
    assert order_res.status_code in (200, 201)
    order = order_res.json()
    assert order["due_at"] is not None
    assert order["sla"] is not None
    assert order["sla"]["sla_state"] in {"on_track", "at_risk", "breached"}

    summary = client.get("/api/analytics/summary", headers=operator).json()
    assert "sla_breached_count" in summary
    assert "sla_at_risk_count" in summary


def test_citizen_feedback_only_after_verification_and_records_dispute(client):
    operator = login_headers(client, "demo.operator@civicops.local")
    incidents = client.get(
        "/api/incidents?include_resolved=true", headers=operator
    ).json()["items"]

    active_inc = next(i for i in incidents if i["status"] != "verified")
    active_detail = client.get(f"/api/incidents/{active_inc['id']}", headers=operator).json()
    active_rpt = active_detail["reports"][0]["public_id"]

    blocked = client.post(
        f"/api/reports/{active_rpt}/feedback",
        json={"rating": 4, "comment": "Too early", "resolved_satisfactorily": True},
    )
    assert blocked.status_code == 409

    verified_inc = next(i for i in incidents if i["status"] == "verified")
    verified_detail = client.get(
        f"/api/incidents/{verified_inc['id']}", headers=operator
    ).json()
    verified_rpt = verified_detail["reports"][0]["public_id"]

    fb = client.post(
        f"/api/reports/{verified_rpt}/feedback",
        json={
            "rating": 2,
            "comment": "Some debris still left behind near the corner.",
            "resolved_satisfactorily": False,
        },
    )
    assert fb.status_code == 200
    status_data = fb.json()
    assert status_data["citizen_rating"] == 2
    assert status_data["citizen_reopen_requested"] is True
    assert status_data["citizen_feedback"] == "Some debris still left behind near the corner."

    updated_detail = client.get(
        f"/api/incidents/{verified_inc['id']}", headers=operator
    ).json()
    assert any(
        ev["action"] == "citizen_disputed_resolution" for ev in updated_detail["activity"]
    )

    # Operator can reopen the verified work order following citizen dispute
    verified_wo_id = updated_detail["work_orders"][0]["id"]
    reopen_res = client.post(
        f"/api/work-orders/{verified_wo_id}/transition",
        headers=operator,
        json={"action": "reject_verification", "note": "Reopened following citizen dispute."},
    )
    assert reopen_res.status_code == 200
    assert reopen_res.json()["status"] == "reopened"


def test_sla_sweep_and_csv_export(client):
    field = login_headers(client, "demo.field@civicops.local")
    assert client.post("/api/analytics/sla-sweep", headers=field).status_code == 403

    operator = login_headers(client, "demo.operator@civicops.local")
    first = client.post("/api/analytics/sla-sweep", headers=operator)
    assert first.status_code == 200
    assert "escalated_count" in first.json()

    # Idempotent: immediate second sweep finds 0 new escalations
    second = client.post("/api/analytics/sla-sweep", headers=operator)
    assert second.status_code == 200
    assert second.json()["escalated_count"] == 0

    csv_res = client.get("/api/analytics/export.csv", headers=operator)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    lines = csv_res.text.strip().splitlines()
    assert len(lines) >= 2
    assert lines[0].startswith("public_id,title,category,severity,priority,status,ward")


def test_sla_webhook_notification_adapter_and_resilience(monkeypatch):
    # No-op when alert_webhook_url is unset
    monkeypatch.setattr(settings, "alert_webhook_url", None)
    assert (
        dispatch_sla_escalation_alert(
            work_order_public_id="WO-2026-0001",
            incident_public_id="INC-2026-0001",
            ward_name="Central Market",
            team_name="Crew A",
            remaining_hours=-4.5,
        )
        is False
    )

    # Dispatches JSON payload when configured
    captured = {}

    class FakeResp:
        status_code = 200

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(settings, "alert_webhook_url", "https://example.invalid/hook")
    monkeypatch.setattr("app.services.notifications.httpx.post", fake_post)
    assert (
        dispatch_sla_escalation_alert(
            work_order_public_id="WO-2026-0001",
            incident_public_id="INC-2026-0001",
            ward_name="Central Market",
            team_name="Crew A",
            remaining_hours=-4.5,
        )
        is True
    )
    assert captured["json"]["event"] == "sla_breach_escalated"
    assert captured["json"]["overdue_hours"] == 4.5

    # Network failure does not raise
    def failing_post(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("app.services.notifications.httpx.post", failing_post)
    assert (
        dispatch_sla_escalation_alert(
            work_order_public_id="WO-2026-0001",
            incident_public_id="INC-2026-0001",
            ward_name="Central Market",
            team_name="Crew A",
            remaining_hours=-4.5,
        )
        is False
    )


