from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text

from app.core.database import Base


class Incident(Base):
    """Detection alert raised by a sensor (e.g. Suricata).

    Lifecycle (status):
      new -> investigating -> confirmed | false_positive -> closed
    """

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)

    source_ip = Column(String(45), nullable=False)
    destination_ip = Column(String(45), nullable=True)

    source_port = Column(Integer, nullable=True)
    destination_port = Column(Integer, nullable=True)

    protocol = Column(String(20), nullable=True)

    event_type = Column(String(100), nullable=False)

    severity = Column(String(20), nullable=False, index=True)

    # new | investigating | confirmed | false_positive | closed
    status = Column(String(20), nullable=False, default="new", index=True)

    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )