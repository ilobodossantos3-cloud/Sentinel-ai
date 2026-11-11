from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.incident import Incident

from app.services.asset_service import OPEN_STATUSES


# Score formula (documented, derived only from real data):
#   score = 100 - sum(penalty per OPEN incident, by severity)
# Penalties: CRITICAL 25, HIGH 10, MEDIUM 5, LOW 2, INFORMATIONAL 1
# Clamped to 0. With no observations at all the score is
# reported as unknown instead of a fake 100.
PENALTIES = {
    "CRITICAL": 25,
    "HIGH": 10,
    "MEDIUM": 5,
    "LOW": 2,
    "INFORMATIONAL": 1,
}

STATUS_THRESHOLDS = [
    (90, "healthy"),
    (75, "attention"),
    (50, "high_risk"),
    (0, "critical"),
]


def compute_posture(db: Session) -> dict:
    now = datetime.now(timezone.utc)

    open_incidents = (
        db.query(Incident)
        .filter(Incident.status.in_(OPEN_STATUSES))
        .all()
    )

    all_incidents = db.query(Incident.created_at).all()
    asset_count = db.query(Asset.id).count()

    breakdown = {severity: 0 for severity in PENALTIES}

    for incident in open_incidents:
        breakdown[incident.severity] += 1

    penalty = sum(
        PENALTIES[severity] * count
        for severity, count in breakdown.items()
    )

    has_observations = bool(all_incidents) or asset_count > 0

    if not has_observations:
        score = None
        status = "insufficient_data"
        message = (
            "No observations collected yet. "
            "The score is only computed from real data."
        )
    else:
        score = max(0, 100 - penalty)
        status = next(
            label
            for threshold, label in STATUS_THRESHOLDS
            if score >= threshold
        )
        message = None

    # Trend: real detections per day, last 7 days.
    days = [
        (now - timedelta(days=offset)).date().isoformat()
        for offset in range(6, -1, -1)
    ]

    counts = {day: 0 for day in days}

    for (created_at,) in all_incidents:
        day = str(created_at)[:10]
        if day in counts:
            counts[day] += 1

    trend = [
        {"date": day, "new_incidents": counts[day]}
        for day in days
    ]

    return {
        "score": score,
        "status": status,
        "message": message,
        "breakdown": breakdown,
        "trend": trend,
    }
