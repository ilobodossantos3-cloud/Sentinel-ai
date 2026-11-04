from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.incident_analysis import (
    IncidentAnalysisResponse
)

from app.services.incident_analysis_service import (
    create_ai_analysis,
    get_analysis
)

from app.services.incident_service import get_incident


router = APIRouter(
    prefix="/incidents",
    tags=["AI Analysis"]
)


@router.get(
    "/{incident_id}/analysis",
    response_model=IncidentAnalysisResponse
)
def get_incident_analysis(
    incident_id: int,
    db: Session = Depends(get_db)
):
    analysis = get_analysis(
        db,
        incident_id
    )

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="AI analysis not found"
        )

    return analysis


@router.post(
    "/{incident_id}/analysis",
    response_model=IncidentAnalysisResponse
)
def regenerate_incident_analysis(
    incident_id: int,
    db: Session = Depends(get_db)
):
    incident = get_incident(db, incident_id)

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    try:
        analysis = create_ai_analysis(db, incident)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="AI analysis failed"
        )

    return analysis
