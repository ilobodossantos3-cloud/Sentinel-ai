from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class ThreatIntelEntry(Base):
    """One IP from a real, public threat-intelligence feed.

    Only populated by actual feed downloads (FireHOL, abuse.ch,
    Tor Project, IPsum). Never invented, never AI-generated.
    """

    __tablename__ = "threat_intel"

    id = Column(Integer, primary_key=True, index=True)

    ip = Column(String(45), nullable=False, index=True)

    # firehol_level1 | feodo_c2 | tor_exit | ipsum
    source = Column(String(50), nullable=False, index=True)

    # malicious | botnet_c2 | anonymity | suspicious
    category = Column(String(50), nullable=False)

    first_seen = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    last_seen = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
