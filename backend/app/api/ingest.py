from fastapi import APIRouter, Depends
from pydantic import BaseModel, IPvAnyAddress
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.services.asset_service import upsert_asset_by_ip


router = APIRouter(
    prefix="/ingest",
    tags=["Ingest"]
)


class ObservationRequest(BaseModel):
    ip: IPvAnyAddress


@router.post(
    "/observations",
    status_code=202
)
def observations(
    records: list[ObservationRequest],
    db: Session = Depends(get_db)
):
    """Traffic observations from the ingester.

    These do NOT create incidents: they only feed the asset
    inventory (first/last seen) with real sensor data.
    """
    for record in records:
        upsert_asset_by_ip(db, str(record.ip))

    db.commit()

    return {"observed": len(records)}
