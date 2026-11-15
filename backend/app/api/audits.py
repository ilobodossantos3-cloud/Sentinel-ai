from urllib.parse import urlsplit

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query
)
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.audit import Audit, AuditFinding, AuditTarget
from app.models.job import Job

from app.schemas.audit import (
    AuditCreate,
    AuditDetailResponse,
    AuditResponse,
    FindingStatusUpdate,
)

from app.services import job_service
from app.services.audit_engine import run_audit
from app.services.audit_report import build_report, compare_audits


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
    "/compare",
    response_model=dict
)
def compare_runs(
    a: int = Query(..., description="ID da auditoria base"),
    b: int = Query(..., description="ID da auditoria a comparar"),
    db: Session = Depends(get_db)
):
    """Compare two finished audits. Both must target the same target."""
    audit_a = db.get(Audit, a)
    audit_b = db.get(Audit, b)

    if not audit_a or not audit_b:
        raise HTTPException(
            status_code=404,
            detail="Audit not found"
        )

    if audit_a.target_id != audit_b.target_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison only makes sense between audits of the same target"
        )

    for audit in (audit_a, audit_b):
        if not audit.finished_at:
            raise HTTPException(
                status_code=400,
                detail=f"Audit #{audit.id} has not finished yet"
            )

    findings_a = (
        db.query(AuditFinding)
        .filter(AuditFinding.audit_id == audit_a.id)
        .all()
    )
    findings_b = (
        db.query(AuditFinding)
        .filter(AuditFinding.audit_id == audit_b.id)
        .all()
    )

    return compare_audits(audit_a, audit_b, findings_a, findings_b)


@router.get(
    "/{audit_id}/report",
    response_class=PlainTextResponse
)
def audit_report(audit_id: int, db: Session = Depends(get_db)):
    """Markdown report with all findings and technical evidence."""
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

    return PlainTextResponse(
        content=build_report(audit, target, findings),
        media_type="text/markdown; charset=utf-8",
    )


@router.patch(
    "/{audit_id}/findings/{finding_id}",
    response_model=dict
)
def update_finding_status(
    audit_id: int,
    finding_id: int,
    update: FindingStatusUpdate,
    db: Session = Depends(get_db)
):
    """Operator marks a finding open | fixed | accepted."""
    finding = (
        db.query(AuditFinding)
        .filter(
            AuditFinding.id == finding_id,
            AuditFinding.audit_id == audit_id,
        )
        .first()
    )

    if not finding:
        raise HTTPException(
            status_code=404,
            detail="Finding not found"
        )

    finding.status = update.status
    db.commit()

    return {"id": finding.id, "status": finding.status}


@router.get(
    "/schedule"
)
def schedule_status():
    """Scheduler state: interval, last sweep, counts."""
    from app.services.scheduler_service import get_schedule_status
    return get_schedule_status()


@router.post(
    "/sweep",
    status_code=202
)
def sweep_now(background_tasks: BackgroundTasks):
    """Audit ALL known systems/assets immediately (manual sweep)."""
    from app.services.scheduler_service import run_sweep

    background_tasks.add_task(run_sweep)

    return {"status": "sweep started"}


@router.delete(
    "/{audit_id}",
    status_code=200
)
def delete_audit(audit_id: int, db: Session = Depends(get_db)):
    """Remove an audit and its findings (operator housekeeping)."""
    audit = db.get(Audit, audit_id)

    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    (
        db.query(AuditFinding)
        .filter(AuditFinding.audit_id == audit_id)
        .delete()
    )
    db.delete(audit)
    db.commit()

    return {"deleted": audit_id}


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
