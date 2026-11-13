from __future__ import annotations

from sqlalchemy import func, select

from app.models import CitizenReport
from app.services.rate_limit import clear_rate_limits

from .conftest import jpeg_bytes, login_headers, refresh_session


def test_invalid_uploads_are_rejected_before_persistence(client, db):
    wards = client.get("/api/wards").json()
    reports_before = db.scalar(select(func.count(CitizenReport.id)))
    response = client.post(
        "/api/reports",
        data={
            "description": "Garbage has been piling up beside this community bin.",
            "latitude": "12.9712",
            "longitude": "77.5942",
            "ward_id": str(wards[0]["id"]),
        },
        files={"photo": ("fake.png", b"this is not an image", "image/png")},
    )
    assert response.status_code == 422
    assert "valid image" in response.json()["detail"].lower()
    refresh_session(db)
    assert db.scalar(select(func.count(CitizenReport.id))) == reports_before

    oversized = b"x" * (8 * 1024 * 1024 + 2)
    response = client.post(
        "/api/reports",
        data={
            "description": "Garbage has been piling up beside this community bin.",
            "latitude": "12.9712",
            "longitude": "77.5942",
            "ward_id": str(wards[0]["id"]),
        },
        files={"photo": ("huge.jpg", oversized, "image/jpeg")},
    )
    assert response.status_code == 422
    assert "too large" in response.json()["detail"].lower()


def test_evidence_upload_validates_image_content(client, db):
    operator = login_headers(client, "demo.operator@civicops.local")
    field = login_headers(client, "demo.field@civicops.local")
    orders = client.get("/api/work-orders?include_verified=true", headers=field).json()["items"]
    order = next(item for item in orders if item["status"] == "in_progress")
    response = client.post(
        f"/api/work-orders/{order['id']}/evidence",
        headers=field,
        data={"kind": "after_photo"},
        files={"photo": ("bad.jpg", b"not-an-image", "image/jpeg")},
    )
    assert response.status_code == 422
    detail = client.get(f"/api/work-orders/{order['id']}", headers=field).json()
    assert all(item["kind"] != "after_photo" for item in detail["evidence"])


def test_public_report_rate_limit(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "public_report_rate_limit_per_hour", 1)
    clear_rate_limits()
    wards = client.get("/api/wards").json()
    data = {
        "description": "Garbage has been piling up beside this community bin.",
        "latitude": "12.9712",
        "longitude": "77.5942",
        "ward_id": str(wards[0]["id"]),
    }
    first = client.post("/api/reports", data=data)
    assert first.status_code == 201, first.text
    second = client.post("/api/reports", data=data)
    assert second.status_code == 429
    assert second.json()["code"] == "rate_limited"
    clear_rate_limits()


def test_analytics_are_derived_from_stored_demo_records(client, db):
    operator = login_headers(client, "demo.operator@civicops.local")
    response = client.get("/api/analytics/summary", headers=operator)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["active_incidents"] == 7
    assert payload["awaiting_triage"] == 3
    assert payload["unassigned_incidents"] == 3
    assert payload["in_progress"] == 2
    assert payload["blocked"] == 1
    assert payload["verification_pending"] == 1
    assert payload["verified_last_7_days"] == 2
    assert payload["accepted_duplicate_links"] == 1
    assert payload["total_reports"] == db.scalar(select(func.count(CitizenReport.id)))
    assert len(payload["hotspots"]) == 7
    assert all(hotspot["report_count"] >= 1 for hotspot in payload["hotspots"])
    status_total = sum(item["count"] for item in payload["status_counts"])
    assert status_total == 9


def test_report_photo_requires_authentication_and_owner_or_staff(client):
    operator = login_headers(client, "demo.operator@civicops.local")
    incidents = client.get("/api/incidents", headers=operator).json()["items"]
    incident = next(item for item in incidents if item["report_count"] >= 1)
    detail = client.get(f"/api/incidents/{incident['id']}", headers=operator).json()
    media = detail["reports"][0]["media"][0]
    assert client.get(f"/api/media/{media['id']}").status_code == 401
    assert client.get(f"/api/media/{media['id']}", headers=operator).status_code == 200


def test_public_incident_map_is_accessible_without_auth_and_excludes_pii(client):
    response = client.get("/api/incidents/public-map")
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) >= 1

    first = items[0]
    expected_keys = {
        "id",
        "public_id",
        "title",
        "category",
        "priority",
        "status",
        "ward_name",
        "latitude",
        "longitude",
        "report_count",
        "primary_report_public_id",
        "created_at",
        "verified_at",
        "is_demo",
    }
    assert set(first.keys()) == expected_keys
    for forbidden in (
        "reporter_name",
        "reporter_contact",
        "triage_notes",
        "priority_override_reason",
        "reports",
    ):
        assert forbidden not in first


def test_randomize_delhi_demo_updates_delhi_timestamps_to_today(client):
    response = client.post("/api/incidents/public-map/randomize-demo")
    assert response.status_code == 200, response.text
    items = response.json()
    delhi_items = [
        item
        for item in items
        if item["ward_name"] in {"Connaught Place Ward", "Lajpat Nagar Ward"}
    ]
    assert len(delhi_items) == 3
    from datetime import datetime, timezone

    today_utc = datetime.now(timezone.utc).date()
    for item in delhi_items:
        parsed = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        assert parsed.date() == today_utc
        assert item["is_demo"] is True
