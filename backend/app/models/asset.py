from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String
)

from app.core.database import Base


class Asset(Base):
    """Device observed by the platform or manually registered.

    The security status is never stored: it is derived on read
    from the incidents/verifications associated with the asset.
    """

    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)

    ip = Column(String(45), unique=True, nullable=False, index=True)

    name = Column(String(100), nullable=True)

    # server | endpoint | firewall | router | gateway | iot |
    # application | user | unknown
    asset_type = Column(String(20), nullable=False, default="unknown")

    os_name = Column(String(100), nullable=True)

    # True when manually registered by an operator;
    # False when only inferred from observed traffic.
    is_registered = Column(Boolean, nullable=False, default=False)

    first_seen_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    last_seen_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
