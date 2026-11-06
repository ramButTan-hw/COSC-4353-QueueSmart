"""Database persistence helpers for Queue and QueueEntry."""

from sqlalchemy import select

from app import database
from app.models import QueueEntry, Service
from app.tables.queue import QueueEntryTable, QueueTable
from app.tables.service import ServiceTable


def _ensure_service(session, service: Service) -> ServiceTable:
    """Make sure the service referenced by a queue exists in SQL."""
    row = session.get(ServiceTable, service.id)

    if row is None:
        row = ServiceTable(
            id=service.id,
            name=service.name,
            description=service.description,
            duration=service.duration,
            priority=service.priority,
            is_open=service.open,
        )
        session.add(row)
        session.flush()
    else:
        row.name = service.name
        row.description = service.description
        row.duration = service.duration
        row.priority = service.priority
        row.is_open = service.open

    return row


def _ensure_queue(session, service: Service) -> QueueTable:
    """Return the service's queue row, creating it when needed."""
    _ensure_service(session, service)

    queue = session.scalars(
        select(QueueTable).where(
            QueueTable.service_id == service.id
        )
    ).first()

    status = "open" if service.open else "closed"

    if queue is None:
        queue = QueueTable(
            service_id=service.id,
            status=status,
        )
        session.add(queue)
        session.flush()
    else:
        queue.status = status

    return queue


def set_queue_status(service: Service) -> None:
    """Persist the current open/closed queue state."""
    with database.SessionLocal() as session:
        _ensure_queue(session, service)
        session.commit()


def add_entry(
    service: Service,
    entry: QueueEntry,
    position: int,
) -> None:
    """Persist a newly joined student."""
    with database.SessionLocal() as session:
        queue = _ensure_queue(session, service)

        session.add(
            QueueEntryTable(
                id=entry.id,
                queue_id=queue.id,
                user_id=entry.user_id,
                position=position,
                status="waiting",
            )
        )

        session.commit()


def finish_entry(
    service_id: int,
    user_id: str,
    status: str,
) -> None:
    """Mark a waiting entry as served or canceled."""
    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).first()

        if queue is None:
            return

        entry = session.scalars(
            select(QueueEntryTable)
            .where(
                QueueEntryTable.queue_id == queue.id,
                QueueEntryTable.user_id == user_id,
                QueueEntryTable.status == "waiting",
            )
            .order_by(QueueEntryTable.id.desc())
        ).first()

        if entry is not None:
            entry.status = status
            session.commit()


def sync_positions(
    service_id: int,
    entries: list[QueueEntry],
) -> None:
    """Save the current positions of all waiting students."""
    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).first()

        if queue is None:
            return

        for position, current in enumerate(entries, start=1):
            row = session.scalars(
                select(QueueEntryTable).where(
                    QueueEntryTable.queue_id == queue.id,
                    QueueEntryTable.user_id == current.user_id,
                    QueueEntryTable.status == "waiting",
                )
            ).first()

            if row is not None:
                row.position = position

        session.commit()


def delete_queue(service_id: int) -> None:
    """Delete a service's queue and cascade its entries."""
    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).first()

        if queue is not None:
            session.delete(queue)
            session.commit()