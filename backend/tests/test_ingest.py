"""Phase 1 / B4 — ingester observation endpoint tests."""
from app.models.asset import Asset


def test_observations_feed_asset_inventory(client, db_session):
    response = client.post("/ingest/observations", json=[
        {"ip": "10.20.30.40"},
        {"ip": "10.20.30.41"},
    ])

    assert response.status_code == 202
    assert response.json()["observed"] == 2

    assets = db_session.query(Asset).all()
    assert {a.ip for a in assets} == {"10.20.30.40", "10.20.30.41"}
    assert all(a.is_registered is False for a in assets)


def test_observations_never_create_incidents_or_duplicates(client, db_session):
    from app.models.incident import Incident

    # duplicates within the SAME batch (autoflush=False regression)
    client.post("/ingest/observations", json=[
        {"ip": "10.20.30.40"},
        {"ip": "10.20.30.40"},
        {"ip": "10.20.30.40"},
    ])
    client.post("/ingest/observations", json=[{"ip": "10.20.30.40"}])

    assert db_session.query(Asset).count() == 1
    assert db_session.query(Incident).count() == 0


def test_observations_reject_invalid_ip(client):
    response = client.post("/ingest/observations", json=[
        {"ip": "not-an-ip"}
    ])
    assert response.status_code == 422
