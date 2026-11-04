import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query
)
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse
)

from app.services.incident_service import (
    create_incident,
    get_incidents,
    get_incident
)

from app.services.incident_analysis_service import (
    create_ai_analysis
)


logger = logging.getLogger("sentinelai")

router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"]
)


def run_ai_analysis(incident_id: int):
    from app.core.database import SessionLocal
    from app.services.incident_service import get_incident as load
    from app.services.incident_analysis_service import create_ai_analysis as analyze

    db = SessionLocal()

    try:
        incident = load(db, incident_id)

        if incident:
            analyze(db, incident)
    except Exception:
        logger.exception(
            "AI analysis failed for incident %s",
            incident_id
        )
    finally:
        db.close()


@router.post(
    "/",
    response_model=IncidentResponse,
    status_code=201
)
def create(
    incident: IncidentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    created_incident = create_incident(
        db,
        incident
    )

    # A análise corre em background:
    # a resposta HTTP não fica à espera do LLM.
    background_tasks.add_task(
        run_ai_analysis,
        created_incident.id
    )

    return created_incident


@router.get(
    "/",
    response_model=list[IncidentResponse]
)
def list_all(
    severity: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db)
):
    return get_incidents(
        db,
        severity=severity,
        skip=skip,
        limit=limit
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse
)
def get_one(
    incident_id: int,
    db: Session = Depends(get_db)
):
    incident = get_incident(
        db,
        incident_id
    )

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return incident


@router.post(
    "/simulate",
    response_model=IncidentResponse,
    status_code=201
)
def simulate_attack(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):

    incident_data = IncidentCreate(
        source_ip="10.10.10.50",
        destination_ip="10.10.10.10",
        source_port=54321,
        destination_port=22,
        protocol="TCP",
        event_type="SSH_BRUTE_FORCE",
        severity="HIGH",
        description="Simulated SSH brute-force attack for testing"
    )

    created_incident = create_incident(
        db,
        incident_data
    )

    background_tasks.add_task(
        run_ai_analysis,
        created_incident.id
    )

    return created_incident
