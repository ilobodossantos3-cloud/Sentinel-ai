from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
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
    db: Session = Depends(get_db)
):
    asset = register_asset(
        db,
        ip=request.ip,
        name=request.name,
        asset_type=request.asset_type,
        os_name=request.os_name,
    )

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
    )
