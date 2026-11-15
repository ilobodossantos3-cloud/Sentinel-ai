"""
Scheduled security sweeps.

Every AUDIT_SCHEDULE_SECONDS, the platform audits:
- all audit targets, and
- all REGISTERED assets with a known web URL (audit_url).

Observed-but-unregistered IPs (possible attackers seen in traffic)
are deliberately NOT probed: we do not audit the attacker.

The sweep can also be triggered manually at any time
(POST /audits/sweep). Everything is honest: audits that cannot
connect record "target unreachable" as a failed audit.
"""
import threading
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.models.asset import Asset
from app.models.audit import Audit, AuditTarget
from app.services import job_service
from app.services.audit_engine import run_audit


# module state (single-process dev; also readable via GET /audits/schedule)
_state_lock = threading.Lock()
_state = {
    "enabled": settings.AUDIT_SCHEDULE_ENABLED,
    "interval_seconds": settings.AUDIT_SCHEDULE_SECONDS,
    "last_run": None,
    "last_run_audits": 0,
    "running": False,
    "thread_started": False,
}


def get_schedule_status() -> dict:
    with _state_lock:
        return dict(_state)


def collect_sweep_targets(db) -> list[tuple[str, str]]:
    """(kind, url) pairs to audit in one sweep."""
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()

    for audit_target in (
        db.query(AuditTarget).filter(AuditTarget.authorized.is_(True)).all()
    ):
        if audit_target.url not in seen:
            targets.append(("target", audit_target.url))
            seen.add(audit_target.url)

    for asset in (
        db.query(Asset)
        .filter(Asset.is_registered.is_(True))
        .filter(Asset.audit_url.isnot(None))
        .all()
    ):
        if asset.audit_url not in seen:
            targets.append(("asset", asset.audit_url))
            seen.add(asset.audit_url)

    return targets


def create_audit_for_url(db, url: str, scope_note: str) -> Audit | None:
    """Create an Audit (and its Job) for a URL; returns None if
    the URL is not a valid http(s) target."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)

    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None

    host = parts.netloc

    target = (
        db.query(AuditTarget).filter(AuditTarget.url == url).first()
    )
    if not target:
        target = AuditTarget(url=url, host=host, authorized=True)
        db.add(target)

    job = job_service.create_job(
        db, kind="audit", payload={"target_url": url, "sweep": True}
    )

    audit = Audit(target_id=target.id, job_id=job.id)
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return audit


def run_sweep() -> int:
    """Audit every known target/asset once. Returns count started."""
    from app.core.database import SessionLocal

    with _state_lock:
        if _state["running"]:
            return 0
        _state["running"] = True

    started = 0

    try:
        db = SessionLocal()
        try:
            targets = collect_sweep_targets(db)
        finally:
            db.close()

        for _kind, url in targets:
            db = SessionLocal()
            try:
                audit = create_audit_for_url(
                    db, url, scope_note="automatic sweep"
                )
                audit_id = audit.id if audit else None
            finally:
                db.close()

            if audit_id:
                # run synchronously in this worker thread
                run_audit(audit_id)
                started += 1
    finally:
        with _state_lock:
            _state["running"] = False
            _state["last_run"] = datetime.now(timezone.utc).isoformat()
            _state["last_run_audits"] = started

    return started


def _loop():
    while True:
        with _state_lock:
            interval = _state["interval_seconds"]
            enabled = _state["enabled"]

        if enabled:
            try:
                run_sweep()
            except Exception as exc:  # never kill the loop silently
                import logging
                logging.getLogger("sentinelai").error(
                    "sweep failed: %s", exc
                )

        time.sleep(max(30, interval))


def start_scheduler():
    """Start the background sweep thread (once)."""
    with _state_lock:
        if _state["thread_started"] or not _state["enabled"]:
            return
        _state["thread_started"] = True

    thread = threading.Thread(target=_loop, daemon=True, name="audit-sweep")
    thread.start()
