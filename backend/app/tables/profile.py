"""UserProfile: details about the person behind an account. Exactly one row per UserCredentials row.

user_id is both the primary key and a foreign key to the account, and email references the account's email, so a
profile cannot exist without its account and is removed with it. Phone and preferences are optional.
"""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserProfile(Base):
    __tablename__ = "user_profile"
    __table_args__ = (
        CheckConstraint("length(full_name) BETWEEN 1 AND 100 AND length(trim(full_name)) >= 1", name="full_name_length"),
        CheckConstraint("phone IS NULL OR length(phone) BETWEEN 7 AND 30", name="phone_length"),
        CheckConstraint("preferences IS NULL OR length(preferences) BETWEEN 1 AND 500", name="preferences_length"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_credentials.id", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str] = mapped_column(
        String(254), ForeignKey("user_credentials.email", ondelete="CASCADE", onupdate="CASCADE"), unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    preferences: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    account: Mapped["UserCredentials"] = relationship(back_populates="profile", foreign_keys=[user_id])  # noqa: F821
