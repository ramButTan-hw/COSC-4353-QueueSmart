"""UserCredentials: who can log in. One row per account, holding what authentication needs.

The password is never stored, only its argon2 hash (see app/security.py). The email is the username: unique,
lowercase, and checked by the database as well as by the API. The person's name and contact details live in
UserProfile (app/tables/profile.py).
"""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import config
from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserCredentials(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        CheckConstraint("length(id) BETWEEN 1 AND 36", name="id_length"),
        CheckConstraint("length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("email LIKE '%_@_%'", name="email_has_at"),
        CheckConstraint("length(password_hash) >= 1", name="password_hash_present"),
        CheckConstraint("role IN (" + ", ".join(f"'{role}'" for role in config.ROLES) + ")", name="role_valid"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    # Lets the ORM insert the account before its profile when both are added together.
    profile: Mapped["UserProfile"] = relationship(  # noqa: F821
        back_populates="account", uselist=False, cascade="all, delete-orphan", passive_deletes=True,
        foreign_keys="UserProfile.user_id",
    )
