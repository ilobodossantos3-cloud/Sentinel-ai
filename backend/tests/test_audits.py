"""Phase 2 / A1 — audit foundation tests.

The audit engine runs against a real LOCAL http server
(no external network). Non-destructive checks only.
"""
import threading
import http.server
import socketserver

import pytest

from app.models.audit import Audit, AuditFinding, AuditTarget
from app.models.job import Job
from app.services import audit_engine
from app.services.audit_engine import run_audit


BANNER = b"""HTTP/1.1 200 OK
Server: nginx/1.24.0
Content-Type: text/html
Content-Length: 6

<html>ok</html>
"""


class LocalHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/robots.txt":
            self.send_response(200)
            self.send_header("Server", "nginx/1.24.0")
            self.send_header("Content-Type", "text/plain")
            body = b"User-agent: *\nDisallow: /admin\n"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header("Server", "nginx/1.24.0")
        self.send_header("Content-Type", "text/html")
        body = b"<html>ok</html>"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    with socketserver.TCPServer(("127.0.0.1", 0), LocalHandler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()


def test_audit_requires_explicit_authorization(client):
    response = client.post("/audits/", json={
        "url": "http://example.com",
        "authorized": False,
    })
    assert response.status_code == 403


def test_audit_rejects_invalid_url(client):
    response = client.post("/audits/", json={
        "url": "ftp://nope",
        "authorized": True,
    })
    assert response.status_code == 422


def test_audit_lifecycle_with_local_server(client, db_session, local_server, monkeypatch):
    # the POST schedules run_audit as a FastAPI background task;
    # neutralise it so we control the single synchronous execution
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    created = client.post("/audits/", json={
        "url": local_server,
        "authorized": True,
        "scope_note": "test target",
    })
    assert created.status_code == 202
    audit_id = created.json()["id"]
    job_id = created.json()["job_id"]

    # run synchronously for determinism (background in production)
    run_audit(audit_id)

    detail = client.get(f"/audits/{audit_id}").json()

    assert detail["status"] == "completed"
    assert detail["target_url"] == local_server

    titles = [f["title"] for f in detail["findings"]]
    # real, evidenced findings from the local server (plain http target)
    assert any("content-security-policy" in t.lower() for t in titles)
    assert any("Server version disclosed" in t for t in titles)
    assert any("robots.txt" in t for t in titles)
    assert any("HTTP only" in t for t in titles)
    # HSTS never applies to a plain http target
    assert not any("strict-transport-security" in t.lower() for t in titles)

    # every finding carries evidence
    assert all(f["evidence"] for f in detail["findings"])

    # score follows the documented penalty formula
    expected_penalty = sum(
        audit_engine.SEVERITY_PENALTIES[f["severity"]]
        for f in detail["findings"]
    )
    assert detail["score"] == max(0, 100 - expected_penalty)

    # job lifecycle completed
    job = db_session.get(Job, job_id)
    assert job.status == "completed"

    # findings persisted
    assert (
        db_session.query(AuditFinding)
        .filter_by(audit_id=audit_id)
        .count()
        == len(detail["findings"])
    )


def test_report_contains_evidence(client, local_server, monkeypatch):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)
    created = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created.json()["id"])

    response = client.get(f"/audits/{created.json()['id']}/report")

    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]

    report = response.text
    assert f"Relatório de Auditoria #{created.json()['id']}" in report
    assert local_server in report
    # real evidence made it into the report
    assert "nginx/1.24.0" in report
    assert "Recomendação:" in report


def test_compare_runs_appeared_disappeared_persistent(
    client, local_server, monkeypatch
):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    # run A: real local server (server version disclosed, no cookie)
    created_a = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created_a.json()["id"])

    # run B: canned response WITHOUT Server version, WITH cookie
    def fake_get(url, timeout=10):
        return {
            "url": url,
            "status": 200,
            "headers": {
                "content-type": "text/html",
                "set-cookie": "sid=1; HttpOnly; Secure",
            },
            "body": "<html>ok</html>",
            "error": None,
        }

    monkeypatch.setattr("app.services.audit_engine.http_get", fake_get)
    created_b = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created_b.json()["id"])

    response = client.get(
        "/audits/compare",
        params={"a": created_a.json()["id"], "b": created_b.json()["id"]}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["audit_a"] == created_a.json()["id"]
    assert data["target_id"] == created_a.json()["target_id"]
    assert isinstance(data["score_delta"], int)

    titles_a = [t["title"] for t in data["disappeared"]]
    titles_b = [t["title"] for t in data["appeared"]]
    persistent_titles = [t["title"] for t in data["persistent"]]

    # Server version was in A, gone in B
    assert any("Server version disclosed" in t for t in titles_a)
    assert not any("Server version disclosed" in t for t in titles_b)

    # cookie finding appears in B (headers changed)
    assert any("Cookie without security flags" in t for t in titles_b)

    # missing CSP existed in both -> persistent
    assert any("content-security-policy" in t.lower() for t in persistent_titles)

    # scores differ between the two runs
    assert data["score_a"] != data["score_b"]


def test_compare_rejects_different_targets(client, local_server, monkeypatch):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)
    a = client.post("/audits/", json={"url": local_server, "authorized": True})
    b = client.post("/audits/", json={"url": "http://127.0.0.1:9/", "authorized": True})

    response = client.get(
        "/audits/compare",
        params={"a": a.json()["id"], "b": b.json()["id"]}
    )
    assert response.status_code == 400
    assert "same target" in response.json()["detail"]


def test_patch_finding_status(client, local_server, monkeypatch, db_session):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)
    created = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created.json()["id"])
    finding_id = created and client.get(f"/audits/{created.json()['id']}").json()["findings"][0]["id"]

    response = client.patch(
        f"/audits/{created.json()['id']}/findings/{finding_id}",
        json={"status": "fixed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "fixed"

    # invalid status rejected
    bad = client.patch(
        f"/audits/{created.json()['id']}/findings/{finding_id}",
        json={"status": "whatever"},
    )
    assert bad.status_code == 422


def test_hsts_checked_on_https_targets():
    """Unit: HSTS missing is flagged only for https targets."""
    fake_https = {
        "status": 200,
        "headers": {"server": "nginx"},
    }

    findings = audit_engine.check_security_headers(
        fake_https, "https://example.com"
    )
    titles = [f["title"] for f in findings]
    assert any("strict-transport-security" in t.lower() for t in titles)

    fake_http = dict(fake_https)
    findings_http = audit_engine.check_security_headers(
        fake_http, "http://example.com"
    )
    titles_http = [f["title"] for f in findings_http]
    assert not any("strict-transport-security" in t.lower() for t in titles_http)


def test_cookie_and_powered_by_checks():
    """Unit: cookie flags and X-Powered-By disclosure."""
    fake_response = {
        "status": 200,
        "headers": {
            "set-cookie": "session=abc123; HttpOnly",
            "x-powered-by": "Express",
        },
    }

    findings = audit_engine.check_security_headers(
        fake_response, "https://example.com"
    )
    titles = [f["title"] for f in findings]
    assert any("Cookie without security flags" in t for t in titles)
    assert any("X-Powered-By" in t for t in titles)

    # cookie finding must name the missing flags precisely
    cookie = next(f for f in findings if "Cookie" in f["title"])
    assert "Secure ausente" in cookie["impact"]
    assert "SameSite ausente" in cookie["impact"]


def test_audit_unreachable_target_fails_honestly(client, db_session, monkeypatch):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    created = client.post("/audits/", json={
        "url": "http://127.0.0.1:9/",  # discard port, nothing listens
        "authorized": True,
    })
    audit_id = created.json()["id"]

    run_audit(audit_id)

    detail = client.get(f"/audits/{audit_id}").json()
    assert detail["status"] == "failed"
    assert "unreachable" in detail["error"]


def test_repeated_audit_reuses_target(client, db_session, local_server):
    for _ in range(2):
        client.post("/audits/", json={"url": local_server, "authorized": True})

    assert db_session.query(AuditTarget).count() == 1
    assert db_session.query(Audit).count() == 2
