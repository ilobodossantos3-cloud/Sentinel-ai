from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.dashboard import (
    ActivityItem,
    AlertStatsResponse,
    PostureResponse,
    ThreatIntelResponse,
    TopologyResponse,
)

from app.services.posture_service import compute_posture
from app.services.stats_service import (
    get_activity,
    get_alert_stats,
    get_threat_intel,
    get_topology,
)


router = APIRouter(
    tags=["Dashboard"]
)


@router.get(
    "/stats/alerts",
    response_model=AlertStatsResponse
)
def alert_stats(db: Session = Depends(get_db)):
    return get_alert_stats(db)


@router.get(
    "/topology",
    response_model=TopologyResponse
)
def topology(
    recent_limit: int = Query(default=15, ge=1, le=50),
    db: Session = Depends(get_db)
):
    return get_topology(db, recent_limit=recent_limit)


@router.get(
    "/posture",
    response_model=PostureResponse
)
def posture(db: Session = Depends(get_db)):
    return compute_posture(db)


@router.get(
    "/activity",
    response_model=list[ActivityItem]
)
def activity(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    return get_activity(db, limit=limit)


@router.get(
    "/threat-intel",
    response_model=ThreatIntelResponse
)
def threat_intel(db: Session = Depends(get_db)):
    return get_threat_intel(db)
