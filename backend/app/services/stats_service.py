from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.job import Job

from app.services.asset_service import (
    get_asset_statuses,
    get_assets,
)


def get_threat_intel(db: Session, limit: int = 25) -> dict:
    """Aggregate IOCs and threat levels from the AI analyses
    of real incidents (no external feeds yet, no fabricated data)."""
    from app.models.incident_analysis import IncidentAnalysis

    analyses = (
        db.query(IncidentAnalysis)
        .order_by(IncidentAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )

    threat_counts: dict[str, int] = {}
    indicators: list = []

    for analysis in analyses:
        threat_counts[analysis.threat_level] = (
            threat_counts.get(analysis.threat_level, 0) + 1
        )

        for indicator in analysis.indicators or []:
            if isinstance(indicator, dict):
                entry = dict(indicator)
            else:
                entry = {"value": str(indicator)}

            entry["incident_id"] = analysis.incident_id
            indicators.append(entry)

    return {
        "analyses_considered": len(analyses),
        "threat_levels": threat_counts,
        "indicators": indicators,
    }


def get_alert_stats(db: Session) -> dict:
    incidents = db.query(Incident).all()

    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    open_by_severity: dict[str, int] = {}

    open_statuses = {"new", "investigating", "confirmed"}

    for incident in incidents:
        by_severity[incident.severity] = (
            by_severity.get(incident.severity, 0) + 1
        )
        by_status[incident.status] = (
            by_status.get(incident.status, 0) + 1
        )

        if incident.status in open_statuses:
            open_by_severity[incident.severity] = (
                open_by_severity.get(incident.severity, 0) + 1
            )

    return {
        "total": len(incidents),
        "by_severity": by_severity,
        "by_status": by_status,
        "open_by_severity": open_by_severity,
    }


def get_topology(db: Session, recent_limit: int = 15) -> dict:
    statuses = get_asset_statuses(db)
    assets = get_assets(db)

    nodes = [
        {
            "ip": asset.ip,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "status": statuses.get(asset.ip, "monitored"),
            "last_seen_at": str(asset.last_seen_at),
        }
        for asset in assets
    ]

    # Edges: real source -> destination pairs observed in incidents.
    edge_rows = (
        db.query(
            Incident.source_ip,
            Incident.destination_ip,
            func.count(Incident.id),
            func.max(Incident.created_at),
        )
        .filter(Incident.destination_ip.isnot(None))
        .group_by(
            Incident.source_ip, Incident.destination_ip
        )
        .all()
    )

    edges = [
        {
            "source": source_ip,
            "target": destination_ip,
            "incident_count": count,
            "last_event_at": str(last_event_at),
        }
        for source_ip, destination_ip, count, last_event_at
        in edge_rows
    ]

    recent = (
        db.query(Incident)
        .order_by(Incident.created_at.desc())
        .limit(recent_limit)
        .all()
    )

    recent_events = [
        {
            "id": incident.id,
            "severity": incident.severity,
            "event_type": incident.event_type,
            "source_ip": incident.source_ip,
            "destination_ip": incident.destination_ip,
            "created_at": str(incident.created_at),
        }
        for incident in recent
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "recent_events": recent_events,
    }


def get_activity(db: Session, limit: int = 20) -> list[dict]:
    items: list[dict] = []

    jobs = (
        db.query(Job)
        .order_by(Job.created_at.desc())
        .limit(10)
        .all()
    )

    for job in jobs:
        items.append({
            "type": "job",
            "timestamp": str(job.created_at),
            "summary": (
                f"job {job.kind} — {job.status}"
                + (
                    f" (incident #{job.payload.get('incident_id')})"
                    if job.payload.get("incident_id")
                    else ""
                )
            ),
            "detail": {
                "id": job.id,
                "kind": job.kind,
                "status": job.status,
                "payload": job.payload,
                "error": job.error,
            },
        })

    incidents = (
        db.query(Incident)
        .order_by(Incident.created_at.desc())
        .limit(10)
        .all()
    )

    for incident in incidents:
        items.append({
            "type": "incident",
            "timestamp": str(incident.created_at),
            "summary": (
                f"{incident.severity} — {incident.event_type} "
                f"from {incident.source_ip}"
            ),
            "detail": {
                "id": incident.id,
                "severity": incident.severity,
                "status": incident.status,
                "source_ip": incident.source_ip,
                "destination_ip": incident.destination_ip,
            },
        })

    items.sort(key=lambda item: item["timestamp"] or "", reverse=True)

    return items[:limit]
