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
    IncidentResponse,
    IncidentUpdate
)

from app.services.incident_service import (
    create_incident,
    get_incidents,
    get_incident,
    update_incident_status
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
    from app.models.job import Job
    from app.services import job_service
    from app.services.incident_service import get_incident as load
    from app.services.incident_analysis_service import create_ai_analysis as analyze

    # Job tracking: o estado do trabalho fica visível
    # e consultável (regra: toda a tarefa tem estado).
    setup_db = SessionLocal()
    job = job_service.create_job(
        setup_db,
        kind="ai_analysis",
        payload={"incident_id": incident_id}
    )
    job_id = job.id
    setup_db.close()

    db = SessionLocal()

    try:
        job = db.get(Job, job_id)
        job_service.mark_running(job)
        db.commit()

        incident = load(db, incident_id)

        if incident:
            analysis = analyze(db, incident)
            job_service.mark_completed(
                job,
                result={"analysis_id": analysis.id}
            )
        else:
            job_service.mark_failed(
                job,
                error=f"incident {incident_id} not found"
            )

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception(
            "AI analysis failed for incident %s",
            incident_id
        )
        try:
            job_service.mark_failed(job, error=str(exc))
            db.commit()
        except Exception:
            logger.exception(
                "could not record failure for job %s", job_id
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


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse
)
def patch_status(
    incident_id: int,
    update: IncidentUpdate,
    db: Session = Depends(get_db)
):
    incident = get_incident(db, incident_id)

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return update_incident_status(
        db,
        incident,
        update.status.value
    )


@router.delete(
    "/{incident_id}",
    status_code=200
)
def delete_incident(incident_id: int, db: Session = Depends(get_db)):
    """Remove an incident and its AI analyses (operator housekeeping)."""
    from app.models.incident_analysis import IncidentAnalysis
    from app.models.incident import Incident

    incident = db.get(Incident, incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    (
        db.query(IncidentAnalysis)
        .filter(IncidentAnalysis.incident_id == incident_id)
        .delete()
    )
    db.delete(incident)
    db.commit()

    return {"deleted": incident_id}
