"""Queue database table 
A queue belongs to one service and records whether that service's
queue is currently open or closed.
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class QueueTable(Base):
    __tablename__ = "queue"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'closed')",
            name="status_valid",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(6),
        nullable=False,
        default="closed",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
    )