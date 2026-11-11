from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class Severity(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    CLOSED = "closed"


class IncidentCreate(BaseModel):
    source_ip: str
    destination_ip: str | None = None

    source_port: int | None = None
    destination_port: int | None = None

    protocol: str | None = None

    event_type: str
    severity: Severity

    description: str | None = None


class IncidentResponse(IncidentCreate):
    id: int
    created_at: datetime
    status: IncidentStatus = IncidentStatus.NEW

    model_config = ConfigDict(from_attributes=True)


class IncidentUpdate(BaseModel):
    """Partial update — investigation workflow."""

    status: IncidentStatus