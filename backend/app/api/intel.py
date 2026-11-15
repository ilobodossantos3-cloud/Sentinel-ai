from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.incident import Incident
from app.models.job import Job

from app.services import job_service
from app.services.intel_service import (
    feeds_status,
    incident_intel,
    run_intel_refresh,
)


router = APIRouter(prefix="/threat-intel", tags=["Threat Intel"])


class IntelRefreshRequest(BaseModel):
    # refresh all feeds when omitted
    sources: list[str] | None = None


@router.get("/feeds")
def get_feeds_status(db: Session = Depends(get_db)):
    """Per-feed status: entry counts and last successful refresh."""
    return feeds_status(db)


@router.post("/refresh", status_code=202)
def refresh_feeds(
    request: IntelRefreshRequest | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """Download/refresh real threat-intelligence feeds.

    Free public sources only; failures are reported honestly
    (job partial/failed), never papered over.
    """
    from app.services.intel_service import FEEDS

    if request and request.sources:
        unknown = [s for s in request.sources if s not in FEEDS]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown feed(s): {', '.join(unknown)}"
            )

    job = job_service.create_job(
        db,
        kind="intel_refresh",
        payload={"sources": request.sources if request else None},
    )

    background_tasks.add_task(run_intel_refresh, job.id)

    return {"job_id": job.id, "status": "scheduled"}


@router.get("/job/{job_id}")
def refresh_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)

    if not job or job.kind != "intel_refresh":
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "status": job.status,
        "result": job.result,
        "error": job.error,
    }


# Incident enrichment (derived on read)
incident_intel_router = APIRouter(tags=["Threat Intel"])


@incident_intel_router.get("/incidents/{incident_id}/intel")
def incident_feed_matches(incident_id: int, db: Session = Depends(get_db)):
    """Feed entries matching this incident's IPs.

    Returns [] until feeds are refreshed — an empty list means
    "no matches yet", never "clean".
    """
    incident = db.get(Incident, incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    matches = incident_intel(db, incident)

    return {"incident_id": incident_id, "matches": matches}
