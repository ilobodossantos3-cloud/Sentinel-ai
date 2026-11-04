from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


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

    model_config = ConfigDict(from_attributes=True)