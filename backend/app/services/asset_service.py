from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.incident import Incident


# Lifecycle states that still represent risk.
OPEN_STATUSES = ("new", "investigating", "confirmed")

# An asset with no observation for longer than this is
# considered inactive (based on real last_seen data only).
INACTIVITY_THRESHOLD = timedelta(hours=24)

# Highest severity still open -> asset status.
SEVERITY_TO_STATUS = {
    "CRITICAL": "critical",
    "HIGH": "high_risk",
    "MEDIUM": "attention",
    "LOW": "monitored",
    "INFORMATIONAL": "monitored",
}


def upsert_asset_by_ip(db: Session, ip: str | None) -> Asset | None:
    """Register or touch an asset inferred from observed traffic.

    Assets only enter the inventory through real observations
    (never fabricated), matching the project honesty rules.
    """
    if not ip:
        return None

    now = datetime.now(timezone.utc)

    asset = db.query(Asset).filter(Asset.ip == ip).first()

    if not asset:
        asset = Asset(ip=ip, first_seen_at=now)
        db.add(asset)

    asset.last_seen_at = now

    return asset


def upsert_assets_from_incident(db: Session, incident) -> None:
    upsert_asset_by_ip(db, incident.source_ip)
    upsert_asset_by_ip(db, incident.destination_ip)


def get_assets(db: Session):
    return db.query(Asset).order_by(
        Asset.last_seen_at.desc()
    ).all()


def get_asset_by_ip(db: Session, ip: str):
    return db.query(Asset).filter(Asset.ip == ip).first()


def _as_utc(dt: datetime) -> datetime:
    """Dialect-safe normalisation: SQLite and PG
    `timestamp` (no tz) return naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_asset_statuses(db: Session) -> dict[str, str]:
    """Derive each asset security status from open incidents.

    No status is ever stored: it is always computed from real
    observations (project honesty rules).
    """
    now = datetime.now(timezone.utc)

    open_incidents = (
        db.query(Incident)
        .filter(Incident.status.in_(OPEN_STATUSES))
        .all()
    )

    max_severity: dict[str, str] = {}

    rank = {
        "INFORMATIONAL": 0,
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }

    for incident in open_incidents:
        for ip in (incident.source_ip, incident.destination_ip):
            if not ip:
                continue

            current = max_severity.get(ip)

            if current is None or rank[incident.severity] > rank[current]:
                max_severity[ip] = incident.severity

    assets = db.query(Asset).all()

    statuses: dict[str, str] = {}

    for asset in assets:
        severity = max_severity.get(asset.ip)

        if severity:
            statuses[asset.ip] = SEVERITY_TO_STATUS[severity]
        elif now - _as_utc(asset.last_seen_at) > INACTIVITY_THRESHOLD:
            # no recent observation — inactive, not offline
            statuses[asset.ip] = "inactive"
        else:
            statuses[asset.ip] = "monitored"

    return statuses


def get_open_incident_count(db: Session, ip: str) -> int:
    return (
        db.query(Incident)
        .filter(Incident.status.in_(OPEN_STATUSES))
        .filter(
            (Incident.source_ip == ip)
            | (Incident.destination_ip == ip)
        )
        .count()
    )


def get_recent_incidents(db: Session, ip: str, limit: int = 10):
    return (
        db.query(Incident)
        .filter(
            (Incident.source_ip == ip)
            | (Incident.destination_ip == ip)
        )
        .order_by(Incident.created_at.desc())
        .limit(limit)
        .all()
    )


def register_asset(
    db: Session,
    ip: str,
    name: str | None = None,
    asset_type: str = "unknown",
    os_name: str | None = None,
) -> Asset:
    """Manual asset registration by an operator."""
    now = datetime.now(timezone.utc)

    asset = db.query(Asset).filter(Asset.ip == ip).first()

    if not asset:
        asset = Asset(ip=ip, first_seen_at=now)

    asset.name = name
    asset.asset_type = asset_type
    asset.os_name = os_name
    asset.is_registered = True
    asset.last_seen_at = now

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset
