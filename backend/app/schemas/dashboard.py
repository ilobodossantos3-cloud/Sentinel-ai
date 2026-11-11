from pydantic import BaseModel


class AlertStatsResponse(BaseModel):
    total: int

    # counts of ALL detections per severity
    by_severity: dict[str, int]

    # counts per lifecycle status
    by_status: dict[str, int]

    # counts of OPEN incidents per severity
    # (open = not false_positive and not closed)
    open_by_severity: dict[str, int]


class TopologyNode(BaseModel):
    ip: str
    name: str | None
    asset_type: str
    status: str
    last_seen_at: str | None = None


class TopologyEdge(BaseModel):
    source: str
    target: str
    incident_count: int
    last_event_at: str | None = None


class TopologyRecentEvent(BaseModel):
    id: int
    severity: str
    event_type: str
    source_ip: str
    destination_ip: str | None
    created_at: str | None = None


class TopologyResponse(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    recent_events: list[TopologyRecentEvent]


class PostureResponse(BaseModel):
    # null when there is not enough real data yet
    score: int | None

    # healthy | attention | high_risk | critical |
    # insufficient_data
    status: str

    message: str | None = None

    # open incidents per severity (the inputs of the score)
    breakdown: dict[str, int]

    # last 7 days: new detections per day (real observations)
    trend: list[dict]


class ActivityItem(BaseModel):
    type: str            # job | incident
    timestamp: str | None = None
    summary: str
    detail: dict = {}
