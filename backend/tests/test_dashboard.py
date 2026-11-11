"""Phase 1 / B2 — aggregation API tests.

All dashboard data must be derived from real observations;
these tests pin that behaviour.
"""
from datetime import datetime, timedelta, timezone

from app.models.incident import Incident
from app.schemas.incident import IncidentCreate
from app.services import job_service
from app.services.incident_service import (
    create_incident,
    update_incident_status,
)
from app.services.asset_service import register_asset


def make_incident(db, **overrides):
    data = {
        "source_ip": "203.0.113.10",
        "destination_ip": "10.10.10.10",
        "protocol": "TCP",
        "event_type": "TEST_EVENT",
        "severity": "HIGH",
        "description": "seed",
    }
    data.update(overrides)
    return create_incident(db, IncidentCreate(**data))


# --- stats ---------------------------------------------------


def test_alert_stats_counts_all_and_open(db_session, client):
    a = make_incident(db_session, severity="CRITICAL")
    make_incident(db_session, severity="HIGH")
    make_incident(db_session, severity="HIGH")
    make_incident(db_session, severity="LOW")
    update_incident_status(db_session, a, "false_positive")

    stats = client.get("/stats/alerts").json()

    assert stats["total"] == 4
    assert stats["by_severity"]["CRITICAL"] == 1
    assert stats["by_severity"]["HIGH"] == 2
    assert stats["open_by_severity"].get("CRITICAL", 0) == 0
    assert stats["open_by_severity"]["HIGH"] == 2
    assert stats["by_status"]["false_positive"] == 1


# --- topology ------------------------------------------------


def test_topology_derived_from_real_observations(db_session, client):
    make_incident(
        db_session,
        source_ip="203.0.113.10",
        destination_ip="10.10.10.10",
    )
    make_incident(
        db_session,
        source_ip="203.0.113.10",
        destination_ip="10.10.10.10",
    )
    make_incident(
        db_session,
        source_ip="203.0.113.77",
        destination_ip="10.10.10.20",
    )

    topo = client.get("/topology").json()

    ips = {node["ip"] for node in topo["nodes"]}
    assert ips == {"203.0.113.10", "10.10.10.10", "203.0.113.77", "10.10.10.20"}

    edges = {
        (edge["source"], edge["target"]): edge["incident_count"]
        for edge in topo["edges"]
    }
    assert edges[("203.0.113.10", "10.10.10.10")] == 2
    assert edges[("203.0.113.77", "10.10.10.20")] == 1

    assert len(topo["recent_events"]) == 3


# --- asset status --------------------------------------------


def test_asset_status_critical_when_open_critical(db_session, client):
    incident = make_incident(db_session, severity="CRITICAL")

    assets = client.get("/assets/").json()
    target = [a for a in assets if a["ip"] == "203.0.113.10"][0]
    assert target["status"] == "critical"
    assert target["open_incidents"] == 1

    update_incident_status(db_session, incident, "closed")

    assets = client.get("/assets/").json()
    target = [a for a in assets if a["ip"] == "203.0.113.10"][0]
    assert target["status"] == "monitored"
    assert target["open_incidents"] == 0


def test_asset_inactive_without_recent_observations(db_session, client):
    register_asset(db_session, ip="10.0.0.99", name="old-server")

    asset = (
        db_session.query(__import__("app.models.asset", fromlist=["Asset"]).Asset)
        .filter_by(ip="10.0.0.99")
        .first()
    )
    asset.last_seen_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.commit()

    assets = client.get("/assets/").json()
    target = [a for a in assets if a["ip"] == "10.0.0.99"][0]
    assert target["status"] == "inactive"


def test_open_low_severity_keeps_asset_monitored(db_session, client):
    make_incident(db_session, severity="INFORMATIONAL")

    assets = client.get("/assets/").json()
    target = [a for a in assets if a["ip"] == "203.0.113.10"][0]
    assert target["status"] == "monitored"


def test_asset_detail_includes_recent_incidents(db_session, client):
    make_incident(db_session)

    detail = client.get("/assets/203.0.113.10").json()
    assert detail["open_incidents"] == 1
    assert len(detail["recent_incidents"]) == 1

    missing = client.get("/assets/10.9.9.9")
    assert missing.status_code == 404


# --- posture -------------------------------------------------


def test_posture_score_formula(db_session, client):
    make_incident(db_session, severity="CRITICAL")   # 25
    make_incident(db_session, severity="HIGH")       # 10

    posture = client.get("/posture").json()

    assert posture["score"] == 65
    assert posture["status"] == "high_risk"
    assert posture["breakdown"]["CRITICAL"] == 1
    assert posture["breakdown"]["HIGH"] == 1


def test_posture_empty_is_insufficient_data(db_session, client):
    posture = client.get("/posture").json()

    assert posture["score"] is None
    assert posture["status"] == "insufficient_data"
    assert posture["message"] is not None


def test_posture_recovers_after_resolution(db_session, client):
    incident = make_incident(db_session, severity="CRITICAL")
    update_incident_status(db_session, incident, "closed")

    posture = client.get("/posture").json()

    assert posture["score"] == 100
    assert posture["status"] == "healthy"


def test_posture_trend_counts_real_detections(db_session, client):
    today = datetime.now(timezone.utc)
    three_days_ago = today - timedelta(days=3)

    incident = make_incident(db_session)
    incident.created_at = three_days_ago
    make_incident(db_session)
    make_incident(db_session)
    db_session.commit()

    posture = client.get("/posture").json()
    trend = {entry["date"]: entry["new_incidents"] for entry in posture["trend"]}

    assert trend[str(today.date())] == 2
    assert trend[str(three_days_ago.date())] == 1
    assert sum(trend.values()) == 3


# --- activity ------------------------------------------------


def test_activity_mixes_jobs_and_incidents(db_session, client):
    make_incident(db_session)
    job_service.create_job(db_session, kind="ai_analysis", payload={"incident_id": 1})

    activity = client.get("/activity").json()

    types = {item["type"] for item in activity}
    assert "incident" in types
    assert "job" in types


# --- manual asset registration -------------------------------


def test_register_asset_endpoint(db_session, client):
    response = client.post("/assets/", json={
        "ip": "192.168.1.7",
        "name": "gateway",
        "asset_type": "firewall",
    })

    assert response.status_code == 201
    assert response.json()["is_registered"] is True
    assert response.json()["asset_type"] == "firewall"

    # re-registering updates, never duplicates
    client.post("/assets/", json={"ip": "192.168.1.7", "name": "gateway-2"})

    assets = client.get("/assets/").json()
    matching = [a for a in assets if a["ip"] == "192.168.1.7"]
    assert len(matching) == 1
    assert matching[0]["name"] == "gateway-2"


# --- threat intelligence -------------------------------------


def test_threat_intel_aggregates_real_analyses(db_session, client):
    from app.models.incident_analysis import IncidentAnalysis
    from app.models.incident import Incident as IncidentModel

    incident = make_incident(db_session)
    db_session.add(IncidentAnalysis(
        incident_id=incident.id,
        threat_level="CRITICAL",
        risk_score=90,
        classification="brute force",
        confidence=0.9,
        analysis="ok",
        indicators=[{"type": "ip", "value": "203.0.113.10"}],
        recommended_actions=["block"],
    ))
    db_session.commit()

    intel = client.get("/threat-intel").json()

    assert intel["analyses_considered"] == 1
    assert intel["threat_levels"]["CRITICAL"] == 1
    assert intel["indicators"][0]["value"] == "203.0.113.10"
    assert intel["indicators"][0]["incident_id"] == incident.id


def test_threat_intel_empty_is_empty_not_fabricated(client):
    intel = client.get("/threat-intel").json()
    assert intel["analyses_considered"] == 0
    assert intel["indicators"] == []
    assert intel["threat_levels"] == {}
