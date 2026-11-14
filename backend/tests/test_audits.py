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
