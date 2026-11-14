from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AuditCreate(BaseModel):
    url: str = Field(min_length=10, max_length=500)

    # Explicit authorization — audits NEVER run without it.
    authorized: bool

    scope_note: str | None = Field(default=None, max_length=2000)


class AuditFindingResponse(BaseModel):
    id: int
    audit_id: int

    category: str
    title: str
    severity: str

    evidence: str
    impact: str | None = None
    recommendation: str | None = None

    status: str

    model_config = ConfigDict(from_attributes=True)


class AuditResponse(BaseModel):
    id: int
    target_id: int
    job_id: int | None = None

    status: str
    score: int | None = None
    summary: str | None = None
    error: str | None = None

    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditDetailResponse(AuditResponse):
    target_url: str
    findings: list[AuditFindingResponse] = Field(default_factory=list)


class FindingStatusUpdate(BaseModel):
    status: Literal["open", "fixed", "accepted"]
