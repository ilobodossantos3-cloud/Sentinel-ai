from urllib.parse import urlsplit

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException
)
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.audit import Audit, AuditFinding, AuditTarget
from app.models.job import Job

from app.schemas.audit import (
    AuditCreate,
    AuditDetailResponse,
    AuditResponse,
)

from app.services import job_service
from app.services.audit_engine import run_audit


router = APIRouter(
    prefix="/audits",
    tags=["Audits"]
)


def _validate_target(url: str) -> tuple[str, str]:
    """Validate and normalize the target URL (http/https only)."""
    parts = urlsplit(url.strip())

    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise HTTPException(
            status_code=422,
            detail="Target must be a valid http(s):// URL"
        )

    normalized = f"{parts.scheme}://{parts.netloc}{parts.path or ''}"

    return normalized, parts.netloc


@router.post(
    "/",
    response_model=AuditResponse,
    status_code=202
)
def create_audit(
    request: AuditCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if not request.authorized:
        raise HTTPException(
            status_code=403,
            detail=(
                "Authorization not affirmed: audits only run on "
                "targets you are authorized to test"
            )
        )

    url, host = _validate_target(request.url)

    target = (
        db.query(AuditTarget)
        .filter(AuditTarget.url == url)
        .first()
    )

    if not target:
        target = AuditTarget(url=url, host=host, authorized=True)
        db.add(target)

    target.authorized = True
    if request.scope_note:
        target.scope_note = request.scope_note

    job = job_service.create_job(
        db,
        kind="audit",
        payload={"target_url": url}
    )

    audit = Audit(target_id=target.id, job_id=job.id)
    db.add(audit)
    db.commit()
    db.refresh(audit)

    background_tasks.add_task(run_audit, audit.id)

    return audit


@router.get(
    "/",
    response_model=list[AuditResponse]
)
def list_audits(db: Session = Depends(get_db)):
    return (
        db.query(Audit)
        .order_by(Audit.id.desc())
        .limit(50)
        .all()
    )


@router.get(
    "/{audit_id}",
    response_model=AuditDetailResponse
)
def audit_detail(audit_id: int, db: Session = Depends(get_db)):
    audit = db.get(Audit, audit_id)

    if not audit:
        raise HTTPException(
            status_code=404,
            detail="Audit not found"
        )

    target = db.get(AuditTarget, audit.target_id)

    findings = (
        db.query(AuditFinding)
        .filter(AuditFinding.audit_id == audit.id)
        .order_by(AuditFinding.id.asc())
        .all()
    )

    detail = AuditDetailResponse(
        id=audit.id,
        target_id=audit.target_id,
        job_id=audit.job_id,
        status=audit.status,
        score=audit.score,
        summary=audit.summary,
        error=audit.error,
        started_at=audit.started_at,
        finished_at=audit.finished_at,
        target_url=target.url,
        findings=findings,
    )

    return detail
