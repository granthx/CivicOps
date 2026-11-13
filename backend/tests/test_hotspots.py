from __future__ import annotations

from .conftest import login_headers


def test_hotspots_endpoint_requires_staff_and_returns_clusters(client):
    assert client.get("/api/analytics/hotspots").status_code == 401
    citizen = login_headers(client, "demo.citizen@civicops.local")
    assert client.get("/api/analytics/hotspots", headers=citizen).status_code == 403

    operator = login_headers(client, "demo.operator@civicops.local")
    response = client.get("/api/analytics/hotspots", headers=operator)
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_days"] == 30
    assert payload["radius_m"] == 150.0
    assert len(payload["clusters"]) >= 1
    top = payload["clusters"][0]
    assert top["cluster_id"] == "HS-01"
    assert top["incident_count"] >= 2
    assert top["chronic_score"] > 0
    assert top["is_chronic"] is True
    assert "within 150m" in top["recommendation"]


def test_hotspot_priority_boost_applies_only_near_existing_incidents(client):
    operator = login_headers(client, "demo.operator@civicops.local")
    wards = client.get("/api/wards").json()
    ward_id = wards[0]["id"]

    # Submit near the seeded Central Market cluster (~12.9711, 77.59415)
    near_res = client.post(
        "/api/reports",
        data={
            "description": "Overflowing community bin spilling onto footpath near central market.",
            "latitude": "12.97120",
            "longitude": "77.59420",
            "ward_id": str(ward_id),
        },
    )
    assert near_res.status_code == 201
    near_incident_id = near_res.json()["incident"]["id"]
    near_incident = client.get(
        f"/api/incidents/{near_incident_id}", headers=operator
    ).json()
    near_factors = {f["label"]: f for f in near_incident["priority_factors"]["factors"]}
    assert "Hotspot" in near_factors
    assert near_factors["Hotspot"]["points"] == 15.0

    # Submit far away from any seeded incident (~13.05, 77.70)
    far_res = client.post(
        "/api/reports",
        data={
            "description": "Small pile of dry leaves and litter on residential lane.",
            "latitude": "13.05000",
            "longitude": "77.70000",
            "ward_id": str(ward_id),
        },
    )
    assert far_res.status_code == 201
    far_incident_id = far_res.json()["incident"]["id"]
    far_incident = client.get(
        f"/api/incidents/{far_incident_id}", headers=operator
    ).json()
    far_factors = {f["label"]: f for f in far_incident["priority_factors"]["factors"]}
    assert "Hotspot" in far_factors
    assert far_factors["Hotspot"]["points"] == 0.0


def test_grid_bucket_clustering_boundary_accuracy(client):
    operator = login_headers(client, "demo.operator@civicops.local")
    wards = client.get("/api/wards").json()
    ward_id = wards[0]["id"]

    # Create two incidents ~111m apart (0.001 deg latitude) at an isolated location
    base_lat, base_lon = 13.12000, 77.75000
    r1 = client.post(
        "/api/reports",
        data={
            "description": "Overflowing waste bin at isolated sector point A.",
            "latitude": str(base_lat),
            "longitude": str(base_lon),
            "ward_id": str(ward_id),
        },
    )
    r2 = client.post(
        "/api/reports",
        data={
            "description": "Garbage accumulation beside point A (~111m north).",
            "latitude": str(base_lat + 0.0010),
            "longitude": str(base_lon),
            "ward_id": str(ward_id),
        },
    )
    # Create a third incident ~250m south of point A (outside 150m radius)
    r3 = client.post(
        "/api/reports",
        data={
            "description": "Separate litter pile ~250m south of point A.",
            "latitude": str(base_lat - 0.00225),
            "longitude": str(base_lon),
            "ward_id": str(ward_id),
        },
    )
    assert r1.status_code == 201 and r2.status_code == 201 and r3.status_code == 201
    id1 = r1.json()["incident"]["id"]
    id2 = r2.json()["incident"]["id"]
    id3 = r3.json()["incident"]["id"]

    clusters = client.get("/api/analytics/hotspots", headers=operator).json()["clusters"]
    matching = [c for c in clusters if id1 in c["incident_ids"]]
    assert len(matching) == 1
    assert id2 in matching[0]["incident_ids"]
    assert id3 not in matching[0]["incident_ids"]

