from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException
)
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.asset import (
    AssetDetailResponse,
    AssetRegisterRequest,
    AssetResponse,
)

from app.services.asset_service import (
    get_asset_by_ip,
    get_asset_statuses,
    get_assets,
    get_open_incident_count,
    get_recent_incidents,
    register_asset,
)
from app.services.audit_checks import determine_web_url
from app.services.audit_engine import run_audit
from app.services.scheduler_service import create_audit_for_url


router = APIRouter(
    prefix="/assets",
    tags=["Assets"]
)


@router.get(
    "/",
    response_model=list[AssetResponse]
)
def list_assets(db: Session = Depends(get_db)):
    statuses = get_asset_statuses(db)
    assets = get_assets(db)

    return [
        AssetResponse(
            ip=asset.ip,
            name=asset.name,
            asset_type=asset.asset_type,
            os_name=asset.os_name,
            is_registered=asset.is_registered,
            status=statuses.get(asset.ip, "monitored"),
            open_incidents=get_open_incident_count(db, asset.ip),
            first_seen_at=asset.first_seen_at,
            last_seen_at=asset.last_seen_at,
            audit_url=asset.audit_url,
        )
        for asset in assets
    ]


@router.get(
    "/{ip}",
    response_model=AssetDetailResponse
)
def asset_detail(ip: str, db: Session = Depends(get_db)):
    asset = get_asset_by_ip(db, ip)

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    statuses = get_asset_statuses(db)

    recent = get_recent_incidents(db, ip)

    return AssetDetailResponse(
        ip=asset.ip,
        name=asset.name,
        asset_type=asset.asset_type,
        os_name=asset.os_name,
        is_registered=asset.is_registered,
        status=statuses.get(asset.ip, "monitored"),
        open_incidents=get_open_incident_count(db, ip),
        first_seen_at=asset.first_seen_at,
        last_seen_at=asset.last_seen_at,
        audit_url=asset.audit_url,
        recent_incidents=[
            {
                "id": incident.id,
                "severity": incident.severity,
                "event_type": incident.event_type,
                "status": incident.status,
                "created_at": str(incident.created_at),
                "description": incident.description,
            }
            for incident in recent
        ],
    )


@router.post(
    "/",
    response_model=AssetResponse,
    status_code=201
)
def register(
    request: AssetRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    asset = register_asset(
        db,
        ip=request.ip,
        name=request.name,
        asset_type=request.asset_type,
        os_name=request.os_name,
    )

    # Immediate security analysis: probe for a web service
    # (https preferred) and launch an audit in the background.
    if not asset.audit_url:
        asset.audit_url = determine_web_url(asset.ip)
        db.commit()

    audit_id = None
    if asset.audit_url:
        audit = create_audit_for_url(
            db, asset.audit_url, scope_note="auto: registered asset"
        )
        audit_id = audit.id
        background_tasks.add_task(run_audit, audit_id)

    return AssetResponse(
        ip=asset.ip,
        name=asset.name,
        asset_type=asset.asset_type,
        os_name=asset.os_name,
        is_registered=asset.is_registered,
        status="monitored",
        open_incidents=get_open_incident_count(db, asset.ip),
        first_seen_at=asset.first_seen_at,
        last_seen_at=asset.last_seen_at,
        audit_url=asset.audit_url,
    )


@router.post(
    "/{ip}/audit",
    status_code=202
)
def audit_asset_now(
    ip: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manual on-demand security analysis of an asset."""
    asset = get_asset_by_ip(db, ip)

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if not asset.audit_url:
        asset.audit_url = determine_web_url(asset.ip)
        db.commit()

    if not asset.audit_url:
        # honest: no web service found, nothing to audit yet
        raise HTTPException(
            status_code=409,
            detail=(
                "No web service detected on this asset "
                "(ports 443/80 unreachable) — nothing to audit"
            )
        )

    audit = create_audit_for_url(
        db, asset.audit_url, scope_note="manual: on-demand"
    )
    background_tasks.add_task(run_audit, audit.id)

    return {"audit_id": audit.id, "target_url": asset.audit_url}


@router.delete(
    "/{ip}",
    status_code=200
)
def delete_asset(ip: str, db: Session = Depends(get_db)):
    """Remove an asset from the inventory.

    Incident history is preserved (it is the SOC record); the asset
    re-appears automatically if traffic is observed again.
    """
    asset = get_asset_by_ip(db, ip)

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    db.delete(asset)
    db.commit()

    return {"deleted": ip}
