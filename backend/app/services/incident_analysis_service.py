from sqlalchemy.orm import Session

from app.models.incident_analysis import IncidentAnalysis
from app.services.ai_analyzer import analyze_incident


def create_ai_analysis(db: Session, incident) -> IncidentAnalysis:

    incident_data = {
        "id": incident.id,
        "source_ip": incident.source_ip,
        "destination_ip": incident.destination_ip,
        "source_port": incident.source_port,
        "destination_port": incident.destination_port,
        "protocol": incident.protocol,
        "event_type": incident.event_type,
        "severity": incident.severity,
        "description": incident.description,
    }

    result = analyze_incident(incident_data)

    # Re-análise: substitui uma análise existente
    # em vez de violar o constraint unique.
    analysis = (
        db.query(IncidentAnalysis)
        .filter(IncidentAnalysis.incident_id == incident.id)
        .first()
    )

    if not analysis:
        analysis = IncidentAnalysis(incident_id=incident.id)
        db.add(analysis)

    analysis.threat_level = result["threat_level"]
    analysis.risk_score = result["risk_score"]
    analysis.classification = result["classification"]
    analysis.confidence = result["confidence"]
    analysis.analysis = result["analysis"]
    analysis.indicators = result["indicators"]
    analysis.recommended_actions = result["recommended_actions"]

    db.commit()
    db.refresh(analysis)

    return analysis


def get_analysis(db: Session, incident_id: int):
    return (
        db.query(IncidentAnalysis)
        .filter(IncidentAnalysis.incident_id == incident_id)
        .first()
    )