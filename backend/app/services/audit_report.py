"""
Audit report generation and run-to-run comparison.

Everything here is built from persisted, real audit data —
no invented conclusions.
"""
from app.models.audit import Audit, AuditFinding, AuditTarget


SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]


def build_report(audit: Audit, target: AuditTarget, findings) -> str:
    """Plain-text (markdown) report with technical evidence."""
    lines = [
        f"# Relatório de Auditoria #{audit.id}",
        "",
        f"**Alvo:** {target.url}",
        f"**Estado:** {audit.status}",
        f"**Score:** {audit.score if audit.score is not None else '—'}/100",
        f"**Resumo:** {audit.summary or '—'}",
        f"**Âmbito/autorização:** {target.scope_note or 'não registada'}",
        f"**Início:** {audit.started_at or '—'}  ·  **Fim:** {audit.finished_at or '—'}",
        "",
        "## Achados",
        "",
    ]

    if not findings:
        lines.append("Sem achados nas verificações não destrutivas.")

    ordered = sorted(
        findings,
        key=lambda f: SEVERITY_ORDER.index(f.severity)
        if f.severity in SEVERITY_ORDER else 99,
    )

    for f in ordered:
        lines.extend([
            f"### [{f.severity}] {f.title}",
            "",
            f"- **Categoria:** {f.category}",
            f"- **Estado do achado:** {f.status}",
            "",
            "**Evidência:**",
            "",
            "```",
            f.evidence,
            "```",
            "",
        ])

        if f.impact:
            lines.append(f"**Impacto:** {f.impact}")
            lines.append("")

        if f.recommendation:
            lines.append(f"**Recomendação:** {f.recommendation}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _findings_by_key(findings) -> dict[tuple, AuditFinding]:
    return {
        (f.category, f.title): f for f in findings
    }


def compare_audits(audit_a: Audit, audit_b: Audit, findings_a, findings_b) -> dict:
    """Compare two finished audits of the SAME target.

    Matching key: (category, title). Findings that exist in B but
    not in A "appeared"; in A but not in B "disappeared"; the rest
    persisted, with severity/status change detection.
    """
    map_a = _findings_by_key(findings_a)
    map_b = _findings_by_key(findings_b)

    appeared = [
        {
            "category": f.category,
            "title": f.title,
            "severity": f.severity,
            "status": f.status,
        }
        for key, f in map_b.items() if key not in map_a
    ]

    disappeared = [
        {
            "category": f.category,
            "title": f.title,
            "severity": f.severity,
            "status": f.status,
        }
        for key, f in map_a.items() if key not in map_b
    ]

    persistent = []
    for key, f_a in map_a.items():
        f_b = map_b.get(key)
        if not f_b:
            continue

        persistent.append({
            "category": f_a.category,
            "title": f_a.title,
            "severity_a": f_a.severity,
            "severity_b": f_b.severity,
            "severity_changed": f_a.severity != f_b.severity,
            "status_a": f_a.status,
            "status_b": f_b.status,
        })

    score_a = audit_a.score
    score_b = audit_b.score

    return {
        "target_id": audit_a.target_id,
        "audit_a": audit_a.id,
        "audit_b": audit_b.id,
        "score_a": score_a,
        "score_b": score_b,
        "score_delta": (
            (score_b - score_a)
            if score_a is not None and score_b is not None
            else None
        ),
        "appeared": appeared,
        "disappeared": disappeared,
        "persistent": persistent,
    }
