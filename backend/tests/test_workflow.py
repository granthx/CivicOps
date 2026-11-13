from __future__ import annotations

from sqlalchemy import func, select

from app.domain import DuplicateStatus, IncidentStatus
from app.models import CitizenReport, DuplicateCandidate, Incident, User, WorkOrder

from .conftest import jpeg_bytes, login_headers, refresh_session


def test_public_report_is_persisted_triaged_and_suggested(client, db):
    wards = client.get("/api/wards").json()
    central = next(ward for ward in wards if ward["code"] == "W-01")
    reports_before = db.scalar(select(func.count(CitizenReport.id)))

    response = client.post(
        "/api/reports",
        data={
            "description": (
                "The community garbage bin is overflowing and waste is piling up "
                "on the footpath beside 4th Cross."
            ),
            "latitude": "12.97128",
            "longitude": "77.59430",
            "ward_id": str(central["id"]),
            "address": "4th Cross footpath",
            "reporter_name": "Test resident",
            "reporter_contact": "private@example.invalid",
        },
        files={"photo": ("evidence.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()

    assert payload["report"]["ai_status"] in {"succeeded", "needs_review"}
    assert payload["report"]["ai_provider"] == "rules-v1"
    assert payload["report"]["ai_fallback_used"] is True
    assert payload["report"]["media"]
    assert payload["report"]["reporter_contact"] is None
    assert payload["incident"]["status"] == "open"
    assert payload["incident"]["report_count"] == 1
    assert payload["warnings"]
    assert payload["duplicate_candidates"], "Nearby synthetic reports should be suggested"
    top = payload["duplicate_candidates"][0]
    assert top["status"] == "suggested"
    assert top["distance_m"] < 300
    assert len(top["reasons"]) >= 3
    refresh_session(db)
    assert db.scalar(select(func.count(CitizenReport.id))) == reports_before + 1

    status = client.get(f"/api/reports/{payload['report']['public_id']}/status")
    assert status.status_code == 200
    assert status.json()["incident_status"] == "open"


def test_duplicate_confirmation_preserves_both_reports_and_archives_source(client, db):
    operator = login_headers(client, "demo.operator@civicops.local")
    candidate = db.scalar(
        select(DuplicateCandidate).where(
            DuplicateCandidate.status == DuplicateStatus.SUGGESTED.value
        )
    )
    assert candidate is not None
    source_incident_id = candidate.report.incident_id
    target_incident_id = candidate.candidate_incident_id

    response = client.post(
        f"/api/duplicate-candidates/{candidate.id}/review",
        headers=operator,
        json={
            "decision": "accept",
            "note": "Confirmed: same community bin and overlapping time window.",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"

    target = client.get(f"/api/incidents/{target_incident_id}", headers=operator)
    assert target.status_code == 200
    target_payload = target.json()
    assert target_payload["report_count"] == 2
    assert len({report["public_id"] for report in target_payload["reports"]}) == 2
    assert any(
        item["action"] == "duplicate_accepted" for item in target_payload["activity"]
    )

    refresh_session(db)
    source = db.get(Incident, source_incident_id)
    assert source is not None
    assert source.status == IncidentStatus.MERGED.value
    assert source.merged_into_id == target_incident_id
    assert db.scalar(select(func.count(CitizenReport.id))) == 10


def test_work_order_lifecycle_requires_evidence_and_operator_verification(client, db):
    operator = login_headers(client, "demo.operator@civicops.local")
    field = login_headers(client, "demo.field@civicops.local")
    incidents = client.get("/api/incidents", headers=operator).json()["items"]
    central_open = next(
        item
        for item in incidents
        if item["status"] == "open" and item["ward"]["code"] == "W-01"
    )
    teams = client.get("/api/teams", headers=operator).json()
    central_team = next(team for team in teams if team["name"].startswith("Central"))

    triage = client.patch(
        f"/api/incidents/{central_open['id']}/triage",
        headers=operator,
        json={
            "category": "overflowing_bin",
            "severity": "high",
            "note": "Confirmed shared overflowing bin during operator review.",
        },
    )
    assert triage.status_code == 200
    assert triage.json()["status"] == "triaged"

    forbidden = client.post(
        f"/api/incidents/{central_open['id']}/work-orders",
        headers=field,
        json={
            "team_id": central_team["id"],
            "instructions": "Field workers cannot assign their own work.",
        },
    )
    assert forbidden.status_code == 403

    assignment = client.post(
        f"/api/incidents/{central_open['id']}/work-orders",
        headers=operator,
        json={
            "team_id": central_team["id"],
            "instructions": (
                "Clear the overflowing bin area, check the collection frequency, "
                "and upload an after-photo."
            ),
            "due_at": None,
        },
    )
    assert assignment.status_code == 200, assignment.text
    order_id = assignment.json()["id"]
    assert assignment.json()["status"] == "assigned"

    invalid = client.post(
        f"/api/work-orders/{order_id}/transition",
        headers=field,
        json={"action": "complete", "note": "Trying to skip the lifecycle."},
    )
    assert invalid.status_code == 409

    assert (
        client.post(
            f"/api/work-orders/{order_id}/transition",
            headers=field,
            json={"action": "accept", "note": "Accepted by crew lead."},
        ).status_code
        == 200
    )
    started = client.post(
        f"/api/work-orders/{order_id}/transition",
        headers=field,
        json={"action": "start", "note": "Crew on site."},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    missing_photo = client.post(
        f"/api/work-orders/{order_id}/transition",
        headers=field,
        json={"action": "complete", "note": "No photograph yet."},
    )
    assert missing_photo.status_code == 409
    assert "after-photo" in missing_photo.json()["detail"].lower()

    evidence = client.post(
        f"/api/work-orders/{order_id}/evidence",
        headers=field,
        data={"kind": "after_photo"},
        files={"photo": ("after.jpg", jpeg_bytes((70, 130, 90)), "image/jpeg")},
    )
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["kind"] == "after_photo"

    completed = client.post(
        f"/api/work-orders/{order_id}/transition",
        headers=field,
        json={"action": "complete", "note": "Area cleared and photographed."},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    field_verify = client.post(
        f"/api/work-orders/{order_id}/transition",
        headers=field,
        json={"action": "verify", "note": "Self-verification must be blocked."},
    )
    assert field_verify.status_code == 403

    verified = client.post(
        f"/api/work-orders/{order_id}/transition",
        headers=operator,
        json={"action": "verify", "note": "Before/after evidence checked."},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"

    incident = client.get(f"/api/incidents/{central_open['id']}", headers=operator).json()
    assert incident["status"] == "verified"
    assert any(item["action"] == "work_order_verify" for item in incident["activity"])
    assert client.get("/api/work-orders?include_verified=false", headers=field).status_code == 200


def test_duplicate_rejection_keeps_reports_separate(client, db):
    operator = login_headers(client, "demo.operator@civicops.local")
    candidate = db.scalar(
        select(DuplicateCandidate).where(
            DuplicateCandidate.status == DuplicateStatus.SUGGESTED.value
        )
    )
    source_id = candidate.report.incident_id
    target_id = candidate.candidate_incident_id

    response = client.post(
        f"/api/duplicate-candidates/{candidate.id}/review",
        headers=operator,
        json={"decision": "reject", "note": "Evidence suggests two different bins."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    refresh_session(db)
    assert db.get(Incident, source_id).status == IncidentStatus.OPEN.value
    assert db.get(Incident, target_id).status == IncidentStatus.OPEN.value
    source_report = db.scalar(
        select(CitizenReport).where(CitizenReport.incident_id == source_id)
    )
    assert source_report is not None


def test_work_order_team_scope_and_report_privacy(client, db):
    operator = login_headers(client, "demo.operator@civicops.local")
    field = login_headers(client, "demo.field@civicops.local")
    field_user = db.scalar(select(User).where(User.email == "demo.field@civicops.local"))
    field_order = db.scalar(
        select(WorkOrder).where(WorkOrder.team_id == field_user.team_id)
    )
    other_order = db.scalar(
        select(WorkOrder).where(WorkOrder.team_id != field_user.team_id)
    )
    assert field_order is not None and other_order is not None

    detail = client.get(f"/api/work-orders/{field_order.id}", headers=field)
    assert detail.status_code == 200
    payload = detail.json()
    assert all(report["reporter_contact"] is None for report in payload["reports"])

    # Even an operator-only incident screen must not leak to a field worker.
    assert client.get(f"/api/incidents/{field_order.incident_id}", headers=field).status_code == 403

    # Add private synthetic contact and confirm only operator detail returns it.
    report = db.scalar(select(CitizenReport).where(CitizenReport.incident_id == field_order.incident_id))
    report.reporter_contact = "private-test-contact"
    db.commit()
    operator_detail = client.get(
        f"/api/incidents/{field_order.incident_id}", headers=operator
    )
    assert operator_detail.status_code == 200
    assert operator_detail.json()["reports"][0]["reporter_contact"] == "private-test-contact"
    field_detail = client.get(f"/api/work-orders/{field_order.id}", headers=field)
    assert field_detail.json()["reports"][0]["reporter_contact"] is None

    assigned_media = field_detail.json()["reports"][0]["media"][0]
    assert client.get(f"/api/media/{assigned_media['id']}", headers=field).status_code == 200

    other_work_order = client.get(f"/api/work-orders/{other_order.id}", headers=field)
    assert other_work_order.status_code == 403
    assert (
        client.post(
            f"/api/work-orders/{other_order.id}/transition",
            headers=field,
            json={"action": "accept", "note": "Not mine."},
        ).status_code
        == 403
    )


def test_authentication_and_role_boundaries(client):
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "demo.operator@civicops.local", "password": "wrong-password"},
        ).status_code
        == 401
    )
    assert client.get("/api/incidents").status_code == 401
    field = login_headers(client, "demo.field@civicops.local")
    assert client.get("/api/incidents", headers=field).status_code == 403
    assert client.get("/api/analytics/summary", headers=field).status_code == 403
