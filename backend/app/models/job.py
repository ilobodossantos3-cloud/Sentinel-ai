from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    Integer,
    String,
    DateTime,
    Text
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

# JSONB em PostgreSQL; JSON genérico em outros SGBD.
DictJSON = JSON().with_variant(JSONB(), "postgresql")


class Job(Base):
    """Long-running task tracked with an explicit lifecycle.

    Statuses follow the project rule: every check/task must be
    pending, running, completed, failed or partial.
    """

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)

    # ai_analysis | audit | skill | ... (open set)
    kind = Column(String(50), nullable=False, index=True)

    # pending | running | completed | failed | partial
    status = Column(String(20), nullable=False, default="pending", index=True)

    payload = Column(DictJSON, nullable=False, default=dict)

    result = Column(DictJSON, nullable=True)

    error = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    started_at = Column(DateTime, nullable=True)

    finished_at = Column(DateTime, nullable=True)
