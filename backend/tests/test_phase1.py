"""Phase 1 / B1 — data foundation tests.

Rules under test:
- assets enter the inventory only through real observations;
- every incident has an explicit lifecycle status;
- every task is tracked as a job with explicit state;
- AI analysis upsert never duplicates.
"""
from app.models.asset import Asset
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate
from app.services import job_service
from app.services.asset_service import (
    get_assets,
    register_asset,
)
from app.services.incident_service import (
    create_incident,
    update_incident_status,
)


VALID_INCIDENT = {
    "source_ip": "203.0.113.10",
    "destination_ip": "10.10.10.10",
    "source_port": 50000,
    "destination_port": 22,
    "protocol": "TCP",
    "event_type": "SSH_BRUTE_FORCE",
    "severity": "HIGH",
    "description": "test incident",
}


# --- assets -------------------------------------------------


def test_incident_creation_upserts_assets(db_session):
    create_incident(db_session, IncidentCreate(**VALID_INCIDENT))
    create_incident(db_session, IncidentCreate(**{
        **VALID_INCIDENT,
        "source_ip": "198.51.100.5",
    }))

    assets = get_assets(db_session)

    ips = {asset.ip for asset in assets}
    assert ips == {"203.0.113.10", "198.51.100.5", "10.10.10.10"}

    # inferred, never fabricated
    assert all(asset.is_registered is False for asset in assets)


def test_repeated_incidents_do_not_duplicate_assets(db_session):
    create_incident(db_session, IncidentCreate(**VALID_INCIDENT))
    create_incident(db_session, IncidentCreate(**VALID_INCIDENT))

    assets = get_assets(db_session)
    assert len(assets) == 2


def test_manual_registration_marks_asset(db_session):
    create_incident(db_session, IncidentCreate(**VALID_INCIDENT))

    register_asset(
        db_session,
        ip="10.10.10.10",
        name="web-server-01",
        asset_type="server",
        os_name="Linux",
    )

    assets = get_assets(db_session)
    registered = [a for a in assets if a.ip == "10.10.10.10"][0]

    assert registered.is_registered is True
    assert registered.asset_type == "server"
    assert registered.name == "web-server-01"


# --- incident lifecycle -------------------------------------


def test_new_incident_starts_as_new(db_session):
    incident = create_incident(
        db_session, IncidentCreate(**VALID_INCIDENT)
    )
    assert incident.status == "new"


def test_status_update_follows_lifecycle(db_session):
    incident = create_incident(
        db_session, IncidentCreate(**VALID_INCIDENT)
    )

    for status in ("investigating", "confirmed", "closed"):
        updated = update_incident_status(
            db_session, incident, status
        )
        assert updated.status == status


# --- jobs ---------------------------------------------------


def test_job_full_lifecycle(db_session):
    job = job_service.create_job(
        db_session,
        kind="ai_analysis",
        payload={"incident_id": 1},
    )

    assert job.status == "pending"

    job_service.mark_running(job)
    assert job.status == "running"
    assert job.started_at is not None

    job_service.mark_completed(job, result={"analysis_id": 1})
    assert job.status == "completed"
    assert job.finished_at is not None
    assert job.result == {"analysis_id": 1}


def test_job_failure_records_error(db_session):
    job = job_service.create_job(db_session, kind="ai_analysis")

    job_service.mark_failed(job, error="llm unavailable")

    assert job.status == "failed"
    assert job.error == "llm unavailable"
    assert job.finished_at is not None


# --- AI analysis upsert -------------------------------------


def test_reanalysis_replaces_without_duplicates(db_session, monkeypatch):
    from app.services import incident_analysis_service as analysis_svc

    fake_result = {
        "threat_level": "HIGH",
        "risk_score": 70,
        "classification": "brute force",
        "confidence": 0.8,
        "analysis": "first pass",
        "indicators": ["203.0.113.10"],
        "recommended_actions": ["block ip"],
    }

    monkeypatch.setattr(
        analysis_svc, "analyze_incident", lambda data: fake_result
    )

    incident = create_incident(
        db_session, IncidentCreate(**VALID_INCIDENT)
    )

    analysis_svc.create_ai_analysis(db_session, incident)
    fake_result["risk_score"] = 85
    analysis = analysis_svc.create_ai_analysis(db_session, incident)

    assert analysis.risk_score == 85
    assert analysis.incident_id == incident.id

    count = db_session.query(Incident).count()
    analyses = db_session.query(
        __import__("app.models.incident_analysis", fromlist=["IncidentAnalysis"]).IncidentAnalysis
    ).all()
    assert count == 1
    assert len(analyses) == 1


# --- API surface --------------------------------------------


def test_api_accepts_informational_severity(client):
    response = client.post("/incidents/", json={
        **VALID_INCIDENT,
        "severity": "INFORMATIONAL",
    })
    assert response.status_code == 201
    assert response.json()["status"] == "new"


def test_api_rejects_invalid_severity(client):
    response = client.post("/incidents/", json={
        **VALID_INCIDENT,
        "severity": "EXTREME",
    })
    assert response.status_code == 422


def test_api_patch_status(client):
    created = client.post("/incidents/", json=VALID_INCIDENT)
    incident_id = created.json()["id"]

    response = client.patch(
        f"/incidents/{incident_id}",
        json={"status": "investigating"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "investigating"


def test_api_patch_status_404(client):
    response = client.patch(
        "/incidents/999", json={"status": "closed"}
    )
    assert response.status_code == 404


def test_api_invalid_status_rejected(client):
    created = client.post("/incidents/", json=VALID_INCIDENT)
    incident_id = created.json()["id"]

    response = client.patch(
        f"/incidents/{incident_id}",
        json={"status": "deleted"},
    )
    assert response.status_code == 422
