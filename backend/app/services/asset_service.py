from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.asset import Asset


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
