from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentAnalysisResponse(BaseModel):
    id: int
    incident_id: int

    threat_level: str
    risk_score: int = Field(ge=0, le=100)

    classification: str
    confidence: float = Field(ge=0, le=1)

    analysis: str

    indicators: list
    recommended_actions: list

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)