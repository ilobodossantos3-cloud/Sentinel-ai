"""
Audit engine: runs the non-destructive checks against an
authorized target, persists findings with evidence, and updates
the audit + job lifecycle.

Severity weights match the posture score for consistency.
"""
from datetime import datetime, timezone

from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.audit import Audit, AuditFinding, AuditTarget
from app.models.job import Job
from app.services import job_service
from app.services.audit_checks import http_get, tls_info


SEVERITY_PENALTIES = {
    "CRITICAL": 25,
    "HIGH": 10,
    "MEDIUM": 5,
    "LOW": 2,
    "INFORMATIONAL": 1,
}

SECURITY_HEADERS = [
    ("content-security-policy", "MEDIUM"),
    ("x-content-type-options", "LOW"),
    ("x-frame-options", "MEDIUM"),
    ("referrer-policy", "LOW"),
    ("permissions-policy", "INFORMATIONAL"),
]


def _now():
    return datetime.now(timezone.utc)


def check_security_headers(response: dict, base_url: str) -> list[dict]:
    """Missing security headers (evidence: full header set)."""
    findings = []

    headers = response.get("headers") or {}

    evidence_headers = "\n".join(
        f"{key}: {value}" for key, value in headers.items()
    ) or "(no headers received)"

    scheme = urlsplit(base_url).scheme

    # HSTS only makes sense on https responses
    if scheme == "https" and "strict-transport-security" not in headers:
        findings.append({
            "category": "config",
            "title": "Security header missing: strict-transport-security",
            "severity": "HIGH",
            "evidence": (
                f"GET {base_url} -> HTTP {response.get('status')}. "
                f"Response headers:\n{evidence_headers}"
            ),
            "impact": "Permite downgrade de ligação e MITM.",
            "recommendation": "Configurar o header Strict-Transport-Security.",
        })

    for header, severity in SECURITY_HEADERS:
        if header not in headers:
            findings.append({
                "category": "config",
                "title": f"Security header missing: {header}",
                "severity": severity,
                "evidence": (
                    f"GET {base_url} -> HTTP {response.get('status')}. "
                    f"Response headers:\n{evidence_headers}"
                ),
                "impact": "Reduz a defesa do browser contra ataques comuns.",
                "recommendation": f"Configurar o header {header}.",
            })

    server = headers.get("server")
    if server and any(char.isdigit() for char in server):
        findings.append({
            "category": "recon",
            "title": "Server version disclosed",
            "severity": "INFORMATIONAL",
            "evidence": f"Header Server: {server}",
            "impact": "Expõe a versão exacta do software, facilitando recon.",
            "recommendation": "Remover a versão do header Server.",
        })

    set_cookie = headers.get("set-cookie")
    if set_cookie:
        lowered = set_cookie.lower()
        issues = []
        if "httponly" not in lowered:
            issues.append("HttpOnly ausente")
        if "secure" not in lowered:
            issues.append("Secure ausente")
        if "samesite" not in lowered:
            issues.append("SameSite ausente")
        if issues:
            findings.append({
                "category": "webapp",
                "title": "Cookie without security flags",
                "severity": "MEDIUM",
                "evidence": f"Set-Cookie: {set_cookie}",
                "impact": "; ".join(issues) + " — risco de roubo de sessão.",
                "recommendation": "Definir HttpOnly, Secure e SameSite nos cookies.",
            })

    powered_by = headers.get("x-powered-by")
    if powered_by:
        findings.append({
            "category": "recon",
            "title": "X-Powered-By disclosure",
            "severity": "INFORMATIONAL",
            "evidence": f"Header X-Powered-By: {powered_by}",
            "impact": "Expõe a stack tecnológica, facilitando recon.",
            "recommendation": "Remover o header X-Powered-By.",
        })

    return findings


def check_tls(target_scheme: str, host: str) -> list[dict]:
    """TLS certificate checks (only for https targets)."""
    if target_scheme != "https":
        return []

    info = tls_info(host)

    if info.get("error"):
        return [{
            "category": "tls",
            "title": "TLS certificate problem",
            "severity": "HIGH",
            "evidence": f"TLS to {host}:443: {info['error']}",
            "impact": "Certificado inválido quebra a confiança e permite MITM.",
            "recommendation": "Instalar um certificado válido e actualizado.",
        }]

    findings = []
    days_left = info.get("days_left")

    if days_left is not None:
        if days_left < 0:
            findings.append({
                "category": "tls",
                "title": "TLS certificate expired",
                "severity": "CRITICAL",
                "evidence": f"Cert expira em {info['not_after']} ({days_left} dias)",
                "impact": "Browsers recusam a ligação.",
                "recommendation": "Renovar imediatamente o certificado.",
            })
        elif days_left < 14:
            findings.append({
                "category": "tls",
                "title": "TLS certificate expiring soon",
                "severity": "HIGH",
                "evidence": f"Cert expira em {days_left} dias ({info['not_after']})",
                "impact": "Risco de expiração em produção.",
                "recommendation": "Renovar o certificado.",
            })
        elif days_left < 30:
            findings.append({
                "category": "tls",
                "title": "TLS certificate renewal window",
                "severity": "MEDIUM",
                "evidence": f"Cert expira em {days_left} dias",
                "impact": "Expiração próxima.",
                "recommendation": "Renovar o certificado nas próximas semanas.",
            })

    return findings


def check_https_redirect(target_url: str) -> list[dict]:
    """If the target is https, verify http:// redirects to it."""
    parts = urlsplit(target_url)

    if parts.scheme != "https":
        return []

    http_url = f"http://{parts.netloc}"
    response = http_get(http_url)

    if response.get("error"):
        return []  # http unreachable — nothing to flag

    location = (response.get("headers") or {}).get("location", "")

    if not str(response.get("status", "")).startswith("3") or "https" not in location:
        return [{
            "category": "config",
            "title": "HTTP does not redirect to HTTPS",
            "severity": "MEDIUM",
            "evidence": (
                f"GET {http_url} -> HTTP {response.get('status')}, "
                f"Location: {location or '(none)'}"
            ),
            "impact": "Utilizadores podem usar a versão não encriptada.",
            "recommendation": "Redireccionar 301/302 de HTTP para HTTPS.",
        }]

    return []


def check_http_only_target(target_url: str) -> list[dict]:
    """Plain http target: HTTPS availability check."""
    parts = urlsplit(target_url)

    if parts.scheme != "http":
        return []

    https_url = f"https://{parts.netloc}"
    probe = http_get(https_url, timeout=5)

    if probe.get("error"):
        return [{
            "category": "config",
            "title": "Site served over HTTP only",
            "severity": "HIGH",
            "evidence": f"GET {target_url} OK; TLS probe {https_url}: {probe['error']}",
            "impact": "Tráfego sem encriptação (intercepção/modificação).",
            "recommendation": "Activar HTTPS com certificado válido.",
        }]

    return []


def check_public_exposure(target_url: str) -> list[dict]:
    """robots.txt / sitemap.xml presence (recon, informational)."""
    findings = []

    for path, title in (("/robots.txt", "robots.txt"), ("/sitemap.xml", "sitemap.xml")):
        base = target_url.rstrip("/")
        response = http_get(f"{base}{path}")

        if response.get("error"):
            continue

        if response.get("status") == 200 and response.get("body"):
            snippet = response["body"][:200]
            findings.append({
                "category": "recon",
                "title": f"Public {title} present",
                "severity": "INFORMATIONAL",
                "evidence": f"GET {base}{path} -> 200\n{snippet}",
                "impact": "Informa a estrutura pública do site (uso legítimo, mas enumerável).",
                "recommendation": "Rever directivas Disallow por informação sensível.",
            })

    return findings


def run_checks(target_url: str) -> tuple[list[dict], list[str]]:
    """Run all checks; returns (findings, check_errors)."""
    findings: list[dict] = []
    errors: list[str] = []

    response = http_get(target_url)

    if response.get("error"):
        errors.append(f"target unreachable: {response['error']}")
        return findings, errors

    findings.extend(check_security_headers(response, target_url))
    findings.extend(check_https_redirect(target_url))
    findings.extend(check_http_only_target(target_url))
    findings.extend(check_public_exposure(target_url))

    parts = urlsplit(target_url)
    findings.extend(check_tls(parts.scheme, parts.hostname))

    return findings, errors


def run_audit(audit_id: int):
    """Background worker: execute the audit for an authorized target."""
    db: Session = SessionLocal()

    try:
        audit = db.get(Audit, audit_id)

        if not audit:
            return

        target = db.get(AuditTarget, audit.target_id)

        job = db.get(Job, audit.job_id) if audit.job_id else None

        audit.status = "running"
        audit.started_at = _now()

        if job:
            job_service.mark_running(job)

        db.commit()

        try:
            findings, errors = run_checks(target.url)
        except Exception as exc:  # engine bug — record honestly
            findings, errors = [], [f"engine error: {exc}"]

        db.add(audit)

        for finding in findings:
            db.add(AuditFinding(
                audit_id=audit.id,
                status="open",
                **finding
            ))

        penalty = sum(
            SEVERITY_PENALTIES[finding["severity"]]
            for finding in findings
        )
        audit.score = max(0, 100 - penalty)

        counts = {}
        for finding in findings:
            counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1

        audit.summary = (
            f"{len(findings)} achados (" +
            ", ".join(f"{sev}: {n}" for sev, n in sorted(counts.items())) +
            ")"
        ) if findings else "Sem achados nas verificações não destrutivas."

        if errors and findings:
            audit.status = "partial"
        elif errors and not findings:
            audit.status = "failed"
            audit.error = "; ".join(errors)
        else:
            audit.status = "completed"

        audit.finished_at = _now()

        if job:
            if audit.status == "completed":
                job_service.mark_completed(
                    job, result={"audit_id": audit.id, "score": audit.score}
                )
            elif audit.status == "partial":
                job_service.mark_partial(
                    job, result={"audit_id": audit.id, "check_errors": errors}
                )
            else:
                job_service.mark_failed(job, error=audit.error or "audit failed")

        db.commit()

    except Exception as exc:
        db.rollback()
        try:
            audit = db.get(Audit, audit_id)
            if audit:
                audit.status = "failed"
                audit.error = str(exc)
                audit.finished_at = _now()
                if audit.job_id:
                    job = db.get(Job, audit.job_id)
                    if job:
                        job_service.mark_failed(job, error=str(exc))
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
