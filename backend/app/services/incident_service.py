from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.schemas.incident import IncidentCreate


def create_incident(
    db: Session,
    incident_data: IncidentCreate
):
    incident = Incident(
        **incident_data.model_dump()
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return incident


def get_incidents(
    db: Session,
    severity: str | None = None,
    skip: int = 0,
    limit: int = 100
):
    query = db.query(Incident)

    if severity:
        query = query.filter(
            Incident.severity == severity.upper()
        )

    return (
        query
        .order_by(Incident.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_incident(
    db: Session,
    incident_id: int
):
    return db.query(Incident).filter(
        Incident.id == incident_id
    ).first()