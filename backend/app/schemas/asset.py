from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetResponse(BaseModel):
    ip: str
    name: str | None = None
    asset_type: str
    os_name: str | None = None

    is_registered: bool

    # monitored | attention | high_risk | critical | inactive
    # (derived from real incidents — never stored)
    status: str

    open_incidents: int

    first_seen_at: datetime
    last_seen_at: datetime

    audit_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AssetDetailResponse(AssetResponse):
    recent_incidents: list = Field(default_factory=list)


class AssetRegisterRequest(BaseModel):
    ip: str = Field(min_length=7, max_length=45)

    name: str | None = Field(default=None, max_length=100)

    # server | endpoint | firewall | router | gateway | iot |
    # application | user | unknown
    asset_type: str = Field(default="unknown", max_length=20)

    os_name: str | None = Field(default=None, max_length=100)
