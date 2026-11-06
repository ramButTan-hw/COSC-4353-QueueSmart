"""Durable participation history and per-recipient notifications (A4 part 6)."""
from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HistoryRecord(Base):
    __tablename__ = "participation_history"
    __table_args__ = (
        CheckConstraint("length(id) BETWEEN 1 AND 100", name="id_length"),
        CheckConstraint("length(service_name) BETWEEN 1 AND 100", name="service_name_length"),
        CheckConstraint("service_id > 0 AND position > 0", name="positive_numbers"),
        CheckConstraint("joined_at >= 0", name="join_time_valid"),
        CheckConstraint("outcome IN ('Waiting', 'Served', 'Left queue', 'Removed')", name="outcome_valid"),
        CheckConstraint("(outcome = 'Waiting' AND completed_at IS NULL) OR "
                        "(outcome <> 'Waiting' AND completed_at >= joined_at AND completed_at IS NOT NULL)",
                        name="completion_valid"),
        CheckConstraint("close_notified IN (0, 1) AND next_notified IN (0, 1) AND queue_open IN (0, 1)",
                        name="flags_valid"),
    )

    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(100), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"), index=True)
    # Historical snapshots intentionally survive service deletion. Queue/service persistence is separate.
    service_id: Mapped[int] = mapped_column(BigInteger)
    service_name: Mapped[str] = mapped_column(String(100))
    joined_at: Mapped[int] = mapped_column(BigInteger)
    completed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    outcome: Mapped[str] = mapped_column(String(10))
    position: Mapped[int] = mapped_column(BigInteger)
    close_notified: Mapped[bool] = mapped_column(Boolean)
    next_notified: Mapped[bool] = mapped_column(Boolean)
    queue_open: Mapped[bool] = mapped_column(Boolean)


class NotificationRecord(Base):
    __tablename__ = "notification"
    __table_args__ = (
        CheckConstraint("length(id) BETWEEN 1 AND 36", name="id_length"),
        CheckConstraint("length(message) BETWEEN 1 AND 1000", name="message_length"),
        CheckConstraint("length(kind) BETWEEN 1 AND 40", name="kind_length"),
        CheckConstraint("role IN ('student', 'staff')", name="role_valid"),
        CheckConstraint("type IN ('success', 'warning', 'info', 'error')", name="type_valid"),
        CheckConstraint("status IN ('sent', 'viewed')", name="status_valid"),
        CheckConstraint("timestamp >= 0", name="timestamp_valid"),
    )

    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"), index=True)
    participation_id: Mapped[str] = mapped_column(ForeignKey("participation_history.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(1000))
    type: Mapped[str] = mapped_column(String(10))
    timestamp: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(6))
