"""Database persistence helpers for Queue and QueueEntry."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, inspect
from sqlalchemy.schema import CreateColumn

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
    with database.session_scope(write=True) as session:
        _ensure_queue(session, service)
        session.flush()


def add_entry(
    service: Service,
    entry: QueueEntry,
    position: int,
) -> None:
    """Persist a newly joined student."""
    with database.session_scope(write=True) as session:
        queue = _ensure_queue(session, service)

        entry.participation_id = str(uuid4())
        row = QueueEntryTable(
            queue_id=queue.id, user_id=entry.user_id, position=position,
            status="waiting", join_time=datetime.fromtimestamp(entry.joined_at, timezone.utc),
            priority=entry.priority, participation_id=entry.participation_id,
        )
        session.add(row)
        session.flush()
        entry.id = row.id
        entry.joined_at = row.join_time.timestamp()  # Match the database microsecond precision.



def finish_entry(
    service_id: int,
    user_id: str,
    status: str,
) -> None:
    """Mark a waiting entry as served or canceled."""
    with database.session_scope(write=True) as session:
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
            session.flush()


def sync_positions(
    service_id: int,
    entries: list[QueueEntry],
) -> None:
    """Save the current positions of all waiting students."""
    with database.session_scope(write=True) as session:
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
                row.priority = current.priority

        session.flush()


def delete_queue(service_id: int) -> None:
    """Delete a service's queue and cascade its entries."""
    with database.session_scope(write=True) as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).first()

        if queue is not None:
            session.delete(queue)
            session.flush()

def upgrade_queue_columns():
    """Add nullable integration fields without deleting existing queue data."""
    existing = {column["name"] for column in inspect(database.engine).get_columns("queue_entry")}
    with database.engine.begin() as connection:
        for name in ("participation_id", "priority"):
            if name not in existing:
                column = QueueEntryTable.__table__.c[name]
                ddl = str(CreateColumn(column).compile(dialect=database.engine.dialect))
                connection.exec_driver_sql("ALTER TABLE queue_entry ADD COLUMN " + ddl)


def restore_store():
    """Restore persisted services and waiting queues before activity recovery runs."""
    from app.store import db
    from app.tables.activity import HistoryRecord
    from app.tables.service import to_service

    with db.activity.lock, database.session_scope(write=True) as session:
        services = list(session.scalars(select(ServiceTable).order_by(ServiceTable.id)))
        db.services = {row.id: to_service(row) for row in services}
        db._next_service_id = max(db.services, default=0) + 1
        db.queues = {}
        queues = {row.id: row for row in session.scalars(select(QueueTable))}
        for queue in queues.values():
            db.services[queue.service_id].open = queue.status == "open"
        entries = list(session.scalars(select(QueueEntryTable).order_by(QueueEntryTable.position, QueueEntryTable.id)))
        histories = list(session.scalars(select(HistoryRecord).order_by(HistoryRecord.sequence)))
        for row in entries:
            if row.status != "waiting":
                continue
            service = db.services[queues[row.queue_id].service_id]
            # Retain old UUID-prefixed history IDs when upgrading a previously merged database.
            history = next((h for h in histories if h.id == row.participation_id), None)
            if row.participation_id is None:
                history = next((h for h in reversed(histories)
                                if h.user_id == row.user_id and h.service_id == service.id
                                and h.id.endswith(f"-{row.id}")), None)
            if history is not None and history.outcome != "Waiting":
                row.status = "served" if history.outcome == "Served" else "canceled"
                continue
            row.participation_id = history.id if history else (row.participation_id or str(uuid4()))
            row.priority = row.priority or service.priority
            joined_at = row.join_time.replace(tzinfo=timezone.utc).timestamp()
            entry = QueueEntry(row.id, service.id, row.user_id, row.priority, joined_at,
                               order=row.position, participation_id=row.participation_id)
            db.queues.setdefault(service.id, []).append(entry)
            if history is None:
                # Legacy queues can predate the history module. Preserve their original join time.
                session.add(HistoryRecord(
                    id=row.participation_id, user_id=row.user_id, service_id=service.id,
                    service_name=service.name, joined_at=int(joined_at * 1000), completed_at=None,
                    outcome="Waiting", position=row.position, queue_open=service.open,
                    close_notified=False, next_notified=False,
                ))
        db._next_queue_entry_id = max((row.id for row in entries), default=0) + 1
