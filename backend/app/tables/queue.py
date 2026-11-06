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

class QueueEntryTable(Base):
    __tablename__ = "queue_entry"
    __table_args__ = (
        CheckConstraint(
            "position >= 1",
            name="position_positive",
        ),
        CheckConstraint(
            "status IN ('waiting', 'served', 'canceled')",
            name="status_valid",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    queue_id: Mapped[int] = mapped_column(
        ForeignKey("queue.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    join_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
    )

    status: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="waiting",
    )
    # Nullable for databases created before queue/history integration. Startup backfills these.
    participation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(6), nullable=True)
