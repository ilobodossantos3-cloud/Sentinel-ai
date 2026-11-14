from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.services.vulnerability_service import (
    get_vulnerability_detail,
    get_vulnerability_inventory,
    set_vulnerability_status,
)


router = APIRouter(
    prefix="/vulnerabilities",
    tags=["Vulnerabilities"]
)


class VulnerabilityStatusUpdate(BaseModel):
    status: Literal["open", "fixed", "accepted"]


@router.get("/")
def list_vulnerabilities(
    status: str | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db)
):
    """Inventory derived from real audit findings.

    No CVEs are invented: internal IDs only until a real
    CVE feed is integrated.
    """
    return get_vulnerability_inventory(
        db, status=status, severity=severity
    )


@router.get("/{vuln_id}")
def vulnerability_detail(vuln_id: str, db: Session = Depends(get_db)):
    detail = get_vulnerability_detail(db, vuln_id)

    if not detail:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability not found"
        )

    return detail


@router.patch("/{vuln_id}")
def update_vulnerability_status(
    vuln_id: str,
    update: VulnerabilityStatusUpdate,
    db: Session = Depends(get_db)
):
    """Operator marks the vulnerability open | fixed | accepted.

    Writes to the latest underlying finding (source of truth).
    """
    finding = set_vulnerability_status(db, vuln_id, update.status)

    if not finding:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability not found"
        )

    return {"vuln_id": vuln_id, "status": finding.status}
