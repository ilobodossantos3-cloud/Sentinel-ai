"""Phase 3 / C1 — real threat-intelligence feed tests.

Network is stubbed: tests inject canned feed bodies, but the
parsers and DB flow run for real.
"""
import pytest

from app.models.job import Job
from app.models.threat_intel import ThreatIntelEntry
from app.services import intel_service
from app.services.intel_service import parse_feed, refresh_feed


FIREHOL_BODY = """
# FireHOL Level1
; comments ignored
1.0.1.0/24
1.2.3.4
5.6.7.8
"""
FEODO_BODY = '[{"ip_address": "9.9.9.9", "malware": "emotet"}, {"ip_address": "8.8.4.4", "malware": "dridex"}]'

TOR_BODY = "10.100.0.1\nnot-an-ip\n10.100.0.2\n"

IPSUM_BODY = """# ipsum
1.1.1.1\t5
2.2.2.2\t2
3.3.3.3\t3
"""


def test_parsers():
    assert parse_feed("netset", FIREHOL_BODY) == [
        "1.0.1.0/24", "1.2.3.4", "5.6.7.8",
    ]  # CIDRs kept, comments ignored
    assert parse_feed("plain_list", TOR_BODY) == ["10.100.0.1", "10.100.0.2"]
    assert parse_feed("feodo_json", FEODO_BODY) == ["9.9.9.9", "8.8.4.4"]
    # ipsum: only reports >= 3
    assert parse_feed("ipsum", IPSUM_BODY) == ["1.1.1.1", "3.3.3.3"]


@pytest.fixture(autouse=True)
def stub_feed_downloads(monkeypatch):
    """No real network in tests: every feed download is canned."""
    canned = {
        intel_service.FEEDS["firehol_level1"]["url"]: FIREHOL_BODY,
        intel_service.FEEDS["feodo_c2"]["url"]: FEODO_BODY,
        intel_service.FEEDS["tor_exit"]["url"]: TOR_BODY,
        intel_service.FEEDS["ipsum"]["url"]: IPSUM_BODY,
    }
    monkeypatch.setattr(
        intel_service, "fetch_url", lambda url: canned[url]
    )


def test_refresh_feed_replaces_entries(db_session):
    refresh_feed(db_session, "firehol_level1")
    assert (
        db_session.query(ThreatIntelEntry)
        .filter_by(source="firehol_level1")
        .count()
        == 3
    )

    # second refresh with new body replaces old content
    intel_service.fetch_url = lambda url: "7.7.7.7\n"
    refresh_feed(db_session, "firehol_level1")

    ips = {
        r.ip
        for r in db_session.query(ThreatIntelEntry)
        .filter_by(source="firehol_level1")
        .all()
    }
    assert ips == {"7.7.7.7"}


def test_feeds_status_reflects_refresh(db_session):
    refresh_feed(db_session, "feodo_c2")
    status = {s["source"]: s for s in intel_service.feeds_status(db_session)}

    assert status["feodo_c2"]["entries"] == 2
    assert status["feodo_c2"]["last_refresh"] is not None
    assert status["firehol_level1"]["entries"] == 0
    assert status["firehol_level1"]["empty"] is True


def test_incident_matches_feeds(client, db_session, monkeypatch):
    # incident whose source IP appears in a feed
    incident = client.post("/incidents/", json={
        "source_ip": "9.9.9.9",
        "destination_ip": "10.10.10.10",
        "source_port": 1234,
        "destination_port": 22,
        "protocol": "TCP",
        "event_type": "SID_1",
        "severity": "HIGH",
        "description": "test",
    }).json()

    refresh_feed(db_session, "feodo_c2")

    response = client.get(f"/incidents/{incident['id']}/intel").json()
    matches = response["matches"]

    assert len(matches) == 1
    assert matches[0]["ip"] == "9.9.9.9"
    assert matches[0]["source"] == "feodo_c2"
    assert matches[0]["category"] == "botnet_c2"

    # incident with no matches -> honestly empty, never "clean"
    clean = client.post("/incidents/", json={
        "source_ip": "123.123.123.123",
        "destination_ip": "10.10.10.10",
        "source_port": 1,
        "destination_port": 2,
        "protocol": "TCP",
        "event_type": "SID_2",
        "severity": "LOW",
        "description": "test",
    }).json()
    empty = client.get(f"/incidents/{clean['id']}/intel").json()
    assert empty["matches"] == []


def test_cidr_containment_match(client, db_session):
    """An IP inside a CIDR feed entry matches by containment."""
    refresh_feed(db_session, "firehol_level1")

    incident = client.post("/incidents/", json={
        "source_ip": "1.0.1.55",  # inside 1.0.1.0/24
        "destination_ip": "10.10.10.10",
        "source_port": 1234,
        "destination_port": 80,
        "protocol": "TCP",
        "event_type": "SID_3",
        "severity": "HIGH",
        "description": "test cidr",
    }).json()

    matches = client.get(f"/incidents/{incident['id']}/intel").json()["matches"]

    assert len(matches) == 1
    assert matches[0]["ip"] == "1.0.1.0/24"
    assert matches[0]["source"] == "firehol_level1"

    # outside the network -> no match
    outside = client.post("/incidents/", json={
        "source_ip": "1.0.2.55",
        "destination_ip": "10.10.10.10",
        "source_port": 1,
        "destination_port": 2,
        "protocol": "TCP",
        "event_type": "SID_4",
        "severity": "LOW",
        "description": "outside",
    }).json()
    assert client.get(f"/incidents/{outside['id']}/intel").json()["matches"] == []


def test_refresh_endpoint_background_job(client, db_session, monkeypatch):
    # stub ALL feed downloads with canned bodies per URL
    canned = {
        intel_service.FEEDS["firehol_level1"]["url"]: FIREHOL_BODY,
        intel_service.FEEDS["feodo_c2"]["url"]: FEODO_BODY,
        intel_service.FEEDS["tor_exit"]["url"]: TOR_BODY,
        intel_service.FEEDS["ipsum"]["url"]: IPSUM_BODY,
    }
    monkeypatch.setattr(
        intel_service, "fetch_url",
        lambda url: canned[url],
    )

    created = client.post("/threat-intel/refresh", json=None)
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    # run the background task synchronously for determinism
    intel_service.run_intel_refresh(job_id)

    job = client.get(f"/threat-intel/job/{job_id}").json()
    assert job["status"] == "completed"
    assert job["result"]["total_entries"] == 3 + 2 + 2 + 2

    status = {s["source"]: s for s in client.get("/threat-intel/feeds").json()}
    assert all(s["entries"] > 0 for s in status.values())


def test_refresh_failure_is_honest(client, db_session, monkeypatch):
    def boom(url):
        raise OSError("network down")

    monkeypatch.setattr(intel_service, "fetch_url", boom)

    created = client.post("/threat-intel/refresh", json=None)
    job_id = created.json()["job_id"]

    intel_service.run_intel_refresh(job_id)

    job = client.get(f"/threat-intel/job/{job_id}").json()
    assert job["status"] == "failed"
    assert "network down" in job["error"]

    # no entries were fabricated
    assert db_session.query(ThreatIntelEntry).count() == 0


def test_unknown_source_rejected(client):
    response = client.post(
        "/threat-intel/refresh",
        json={"sources": ["made_up_feed"]},
    )
    assert response.status_code == 422
