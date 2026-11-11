from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job import Job


def create_job(db: Session, kind: str, payload: dict | None = None) -> Job:
    job = Job(kind=kind, payload=payload or {})
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_running(job: Job) -> Job:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    return job


def mark_completed(job: Job, result: dict | None = None) -> Job:
    job.status = "completed"
    job.result = result
    job.finished_at = datetime.now(timezone.utc)
    return job


def mark_failed(job: Job, error: str) -> Job:
    job.status = "failed"
    job.error = error
    job.finished_at = datetime.now(timezone.utc)
    return job


def mark_partial(job: Job, result: dict | None = None) -> Job:
    job.status = "partial"
    job.result = result
    job.finished_at = datetime.now(timezone.utc)
    return job
