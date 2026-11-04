from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

# JSONB em PostgreSQL; JSON genérico em outros SGBD.
ListJSON = JSON().with_variant(JSONB(), "postgresql")


class IncidentAnalysis(Base):
    __tablename__ = "incident_analyses"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    incident_id = Column(
        Integer,
        ForeignKey("incidents.id"),
        nullable=False,
        unique=True
    )

    threat_level = Column(
        String(20),
        nullable=False
    )

    risk_score = Column(
        Integer,
        nullable=False
    )

    classification = Column(
        String(255),
        nullable=False
    )

    confidence = Column(
        Float,
        nullable=False
    )

    analysis = Column(
        Text,
        nullable=False
    )

    indicators = Column(
        ListJSON,
        nullable=False,
        default=list
    )

    recommended_actions = Column(
        ListJSON,
        nullable=False,
        default=list
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )