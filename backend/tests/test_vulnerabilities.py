"""Phase 2/3 — vulnerability inventory tests.

Derived read-model from real audit findings. No invented CVEs.
"""
from app.services.vulnerability_service import vuln_id_for


def test_empty_inventory_is_honestly_empty(client):
    response = client.get("/vulnerabilities/")
    data = response.json()

    assert response.status_code == 200
    assert data["vulnerabilities"] == []
    assert data["stats"]["total"] == 0
    assert data["stats"]["open"] == 0


def test_vuln_id_is_deterministic():
    assert (
        vuln_id_for(1, "config", "missing CSP")
        == vuln_id_for(1, "config", "missing CSP")
    )
    assert (
        vuln_id_for(1, "config", "missing CSP")
        != vuln_id_for(2, "config", "missing CSP")
    )
    assert vuln_id_for(1, "config", "x").startswith("VULN-")


def test_inventory_groups_findings_across_audits(
    client, local_server, monkeypatch
):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    # run A: real local server (Server version disclosed, no cookie)
    a = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_id = a.json()["id"]

    from app.services.audit_engine import run_audit
    run_audit(run_id)

    # run B: no Server version header, with cookie
    def fake_get(url, timeout=10):
        return {
            "url": url,
            "status": 200,
            "headers": {"content-type": "text/html"},
            "body": "<html>ok</html>",
            "error": None,
        }

    monkeypatch.setattr("app.services.audit_engine.http_get", fake_get)
    b = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(b.json()["id"])

    data = client.get("/vulnerabilities/").json()
    vulns = data["vulnerabilities"]

    # CSP missing in BOTH audits -> grouped, detected in 2 audits
    csp = next(
        v for v in vulns if "content-security-policy" in v["title"].lower()
    )
    assert csp["detected_in_audits"] == [run_id, run_id + 1]
    assert csp["status"] == "open"
    assert csp["missing_in_latest_audit"] is False

    # Server version disclosed only in A -> missing in latest audit
    server = next(
        v for v in vulns if "Server version disclosed" in v["title"]
    )
    assert server["detected_in_audits"] == [run_id]
    assert server["missing_in_latest_audit"] is True
    assert server["status"] == "open"  # honest: still open, just not re-detected

    # stats make sense
    assert data["stats"]["total"] == len(vulns)
    assert data["stats"]["open"] >= 1
    assert data["stats"]["not_detected_in_latest"] >= 1

    # worst severity first
    severities = [v["severity"] for v in vulns]
    rank = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranks = [rank.get(s, 9) for s in severities]
    assert ranks == sorted(ranks)


def test_vulnerability_detail_has_history(client, local_server, monkeypatch):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    from app.services.audit_engine import run_audit
    created = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created.json()["id"])

    data = client.get("/vulnerabilities/").json()
    vuln_id = data["vulnerabilities"][0]["vuln_id"]

    detail = client.get(f"/vulnerabilities/{vuln_id}").json()

    assert detail["vuln_id"] == vuln_id
    assert len(detail["history"]) >= 1
    assert all(h["evidence"] for h in detail["history"])

    missing = client.get("/vulnerabilities/VULN-00000000")
    assert missing.status_code == 404


def test_patch_vulnerability_status_writes_latest_finding(
    client, local_server, monkeypatch
):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    from app.services.audit_engine import run_audit
    created = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created.json()["id"])

    data = client.get("/vulnerabilities/").json()
    vuln_id = data["vulnerabilities"][0]["vuln_id"]

    response = client.patch(
        f"/vulnerabilities/{vuln_id}", json={"status": "fixed"}
    )
    assert response.status_code == 200

    # inventory now reflects it
    refreshed = client.get("/vulnerabilities/").json()
    vuln = next(
        v for v in refreshed["vulnerabilities"] if v["vuln_id"] == vuln_id
    )
    assert vuln["status"] == "fixed"
    assert refreshed["stats"]["fixed"] >= 1

    bad = client.patch(f"/vulnerabilities/{vuln_id}", json={"status": "nope"})
    assert bad.status_code == 422


def test_severity_filter(client, local_server, monkeypatch):
    monkeypatch.setattr("app.api.audits.run_audit", lambda audit_id: None)

    from app.services.audit_engine import run_audit
    created = client.post("/audits/", json={"url": local_server, "authorized": True})
    run_audit(created.json()["id"])

    high = client.get("/vulnerabilities/", params={"severity": "HIGH"}).json()
    assert all(v["severity"] == "HIGH" for v in high["vulnerabilities"])
    assert len(high["vulnerabilities"]) >= 1
