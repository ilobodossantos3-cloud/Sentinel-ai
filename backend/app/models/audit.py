from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text
)

from app.core.database import Base


class AuditTarget(Base):
    """A target explicitly authorized for security auditing."""

    __tablename__ = "audit_targets"

    id = Column(Integer, primary_key=True, index=True)

    url = Column(String(500), nullable=False, unique=True)

    host = Column(String(255), nullable=False, index=True)

    scope_note = Column(Text, nullable=True)

    # Authorization must be explicitly affirmed by the operator
    # on every audit request (stored per target for traceability).
    authorized = Column(Boolean, nullable=False, default=False)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class Audit(Base):
    """One audit execution against a target.

    Lifecycle mirrors the Job rule: pending -> running ->
    completed | failed | partial.
    """

    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, index=True)

    target_id = Column(
        Integer,
        ForeignKey("audit_targets.id"),
        nullable=False
    )

    job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=True
    )

    # pending | running | completed | failed | partial
    status = Column(String(20), nullable=False, default="pending", index=True)

    # computed from finding severities (same weights as posture)
    score = Column(Integer, nullable=True)

    summary = Column(Text, nullable=True)

    error = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)

    finished_at = Column(DateTime, nullable=True)


class AuditFinding(Base):
    """One concrete result with technical evidence — never invented."""

    __tablename__ = "audit_findings"

    id = Column(Integer, primary_key=True, index=True)

    audit_id = Column(
        Integer,
        ForeignKey("audits.id"),
        nullable=False
    )

    # recon | config | tls | webapp | vuln
    category = Column(String(20), nullable=False)

    title = Column(String(255), nullable=False)

    # CRITICAL | HIGH | MEDIUM | LOW | INFORMATIONAL
    severity = Column(String(20), nullable=False)

    # technical evidence (headers observed, cert dates, status codes…)
    evidence = Column(Text, nullable=False)

    impact = Column(Text, nullable=True)

    recommendation = Column(Text, nullable=True)

    # open | fixed | accepted (managed later)
    status = Column(String(20), nullable=False, default="open")
