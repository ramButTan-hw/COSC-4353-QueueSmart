"""Service table: the services offered by the organization.

    Service ID         id                (generated, never reused)
    Service name       name              1-100 characters, unique ignoring upper/lower case
    Description        description       1-500 characters
    Expected duration  duration_minutes  whole minutes, 1-480
    Priority level     priority          'low', 'medium' or 'high'

`is_open` is not one of the five catalogue fields: it records whether the service's queue is open,
which the queue module switches and reads.
"""
from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, false, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base, register_seeder
from app.models import Service

NAME_MAX = 100
DESCRIPTION_MAX = 500
DURATION_MIN = 1
DURATION_MAX = 480


class ServiceTable(Base):
    __tablename__ = "service"
    __table_args__ = (
        CheckConstraint(f"length(name) BETWEEN 1 AND {NAME_MAX}", name="name_length"),
        CheckConstraint(f"length(description) BETWEEN 1 AND {DESCRIPTION_MAX}", name="description_length"),
        CheckConstraint(f"duration_minutes BETWEEN {DURATION_MIN} AND {DURATION_MAX}", name="duration_range"),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="priority_valid"),
        # Without this SQLite may hand out the id of a deleted service again, and history refers to ids.
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(NAME_MAX), nullable=False)
    description: Mapped[str] = mapped_column(String(DESCRIPTION_MAX), nullable=False)
    duration: Mapped[int] = mapped_column("duration_minutes", Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String(6), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())


# Names are unique regardless of case, the same rule the API checks first to give a friendly message.
Index("uq_service_name_lower", func.lower(ServiceTable.name), unique=True)


def to_service(row: ServiceTable) -> Service:
    """The plain object the rest of the back end (queues, activity) works with."""
    return Service(row.id, row.name, row.description, row.duration, row.priority, row.is_open)


def find_by_name(session: Session, name: str, except_id: int | None = None) -> ServiceTable | None:
    query = select(ServiceTable).where(func.lower(ServiceTable.name) == name.strip().lower())
    if except_id is not None:
        query = query.where(ServiceTable.id != except_id)
    return session.scalars(query).first()


DEMO_SERVICES = (
    ("Password Reset", "Account access and password recovery.", 10, "high", True),
    ("Wi-Fi / Network", "Campus Wi-Fi and device connectivity.", 15, "medium", True),
    ("Printing", "Printing setup, credits, and troubleshooting.", 5, "low", False),
)


@register_seeder
def seed_services(session: Session) -> None:
    """The three services the A2 demo started with. Does nothing if any service already exists."""
    if session.scalar(select(func.count()).select_from(ServiceTable)):
        return
    for name, description, duration, priority, is_open in DEMO_SERVICES:
        session.add(ServiceTable(name=name, description=description, duration=duration,
                                 priority=priority, is_open=is_open))
