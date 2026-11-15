"""Phase 3 / C2 — deletion, on-demand & scheduled analysis tests."""
from app.models.asset import Asset
from app.models.audit import Audit, AuditFinding
from app.models.incident import Incident
from app.services import scheduler_service
from app.services.audit_engine import run_audit


def test_delete_asset(client, db_session, monkeypatch):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    created = client.post("/assets/", json={"ip": "10.99.0.1", "name": "x"})
    assert created.status_code == 201

    response = client.delete("/assets/10.99.0.1")
    assert response.status_code == 200
    assert db_session.query(Asset).filter_by(ip="10.99.0.1").count() == 0

    assert client.delete("/assets/10.99.0.1").status_code == 404


def test_delete_incident_with_analyses(client, db_session):
    created = client.post("/incidents/", json={
        "source_ip": "10.99.0.2",
        "destination_ip": "10.10.10.10",
        "source_port": 1,
        "destination_port": 2,
        "protocol": "TCP",
        "event_type": "SID_9",
        "severity": "HIGH",
        "description": "temp",
    }).json()
    incident_id = created["id"]

    response = client.delete(f"/incidents/{incident_id}")
    assert response.status_code == 200

    assert (
        db_session.query(Incident).filter_by(id=incident_id).count() == 0
    )
    from app.models.incident_analysis import IncidentAnalysis
    assert (
        db_session.query(IncidentAnalysis)
        .filter_by(incident_id=incident_id)
        .count()
        == 0
    )
    assert client.delete("/incidents/99999").status_code == 404


def test_delete_audit_with_findings(client, local_server, monkeypatch):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)
    created = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created.json()["id"])
    audit_id = created.json()["id"]

    response = client.delete(f"/audits/{audit_id}")
    assert response.status_code == 200
    assert client.get(f"/audits/{audit_id}").status_code == 404
    assert client.delete(f"/audits/{audit_id}").status_code == 404


def test_register_asset_triggers_auto_audit(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.api.assets.determine_web_url",
        lambda host, timeout=3: f"http://{host}",
    )
    monkeypatch.setattr("app.api.assets.run_audit", lambda audit_id: None)

    created = client.post("/assets/", json={"ip": "10.99.1.5"})
    assert created.status_code == 201
    assert created.json()["audit_url"] == "http://10.99.1.5"

    # an audit was created in background for the asset
    audits = client.get("/audits/").json()
    assert any(
        a["target_id"] and a["job_id"] for a in audits
    )
    # the newest audit is the asset's auto-audit (pending — run stubbed)
    newest = audits[0]
    assert newest["status"] == "pending"


def test_register_asset_without_web_service_no_audit(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.api.assets.determine_web_url",
        lambda host, timeout=3: None,
    )

    created = client.post("/assets/", json={"ip": "10.99.2.5"})
    assert created.status_code == 201
    assert created.json()["audit_url"] is None


def test_manual_asset_audit(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.api.assets.determine_web_url",
        lambda host, timeout=3: f"http://{host}",
    )
    monkeypatch.setattr("app.api.assets.run_audit", lambda audit_id: None)

    client.post("/assets/", json={"ip": "10.99.3.5"})

    response = client.post("/assets/10.99.3.5/audit")
    assert response.status_code == 202
    assert response.json()["target_url"] == "http://10.99.3.5"

    # run it for real against an unreachable port -> honest failure
    real_audit_id = response.json()["audit_id"]
    run_audit(real_audit_id)
    detail = client.get(f"/audits/{real_audit_id}").json()
    assert detail["status"] == "failed"

    # asset with no web service -> 409, nothing to audit
    monkeypatch.setattr(
        "app.api.assets.determine_web_url",
        lambda host, timeout=3: None,
    )
    client.post("/assets/", json={"ip": "10.99.4.5"})
    assert client.post("/assets/10.99.4.5/audit").status_code == 409


def test_sweep_audits_targets_and_registered_assets(
    client, db_session, local_server, monkeypatch
):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)
    monkeypatch.setattr(
        "app.api.assets.determine_web_url",
        lambda host, timeout=3: f"http://{host}",
    )
    monkeypatch.setattr("app.api.assets.run_audit", lambda audit_id: None)

    # 1 authorized target + 1 registered asset (audit_url set)
    client.post("/audits/", json={"url": local_server, "authorized": True})
    client.post("/assets/", json={"ip": "10.99.5.5", "name": "web01"})

    before = len(client.get("/audits/").json())

    # run sweep synchronously for determinism
    count = scheduler_service.run_sweep()
    assert count == 2  # target + asset

    after = client.get("/audits/").json()
    assert len(after) == before + 2

    # sweep state updated honestly
    status = client.get("/audits/schedule").json()
    assert status["last_run"] is not None
    assert status["last_run_audits"] == 2
    assert status["interval_seconds"] >= 30


def test_sweep_endpoint_background(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.scheduler_service.run_sweep", lambda: 0
    )
    response = client.post("/audits/sweep")
    assert response.status_code == 202
    assert response.json()["status"] == "sweep started"
