"""SQL unit of work around the existing event rules.

Each outer transaction reloads committed data, runs the rules, and writes only changed
rows. Nested event batches share the same transaction with staff alerts and queue changes.
The in-memory Activity remains available for isolated business-rule unit tests.
"""
from contextlib import contextmanager
from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import database
from app.errors import ApiError
from app.tables.activity import HistoryRecord, NotificationRecord
from .service import Activity


HISTORY_FIELDS = {
    "id": "id", "userId": "user_id", "serviceId": "service_id", "serviceName": "service_name",
    "joinedAt": "joined_at", "completedAt": "completed_at", "outcome": "outcome",
    "position": "position", "closeNotified": "close_notified", "nextNotified": "next_notified",
    "queueOpen": "queue_open",
}
NOTICE_FIELDS = {
    "id": "id", "recipientId": "recipient_id", "participationId": "participation_id",
    "role": "role", "kind": "kind", "message": "message", "type": "type", "ts": "timestamp",
}


def unpack(row, fields):
    return {key: getattr(row, column) for key, column in fields.items()}


def synchronize(session, rows, records, model, fields, notification=False):
    remaining = {row.id: row for row in rows}
    for record in records:
        row = remaining.pop(record["id"], None)
        if row is None:
            row = model()
            session.add(row)
        for key, column in fields.items():
            setattr(row, column, record[key])
        if notification:
            row.status = "viewed" if record["read"] else "sent"
    for row in remaining.values():
        session.delete(row)


class PersistentActivity(Activity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._in_transaction = False

    @contextmanager
    def transaction(self):
        with self.lock:
            if self._in_transaction:
                yield
                return
            with database.session_scope() as session:
                histories = list(session.scalars(select(HistoryRecord).order_by(HistoryRecord.sequence)))
                notices = list(session.scalars(select(NotificationRecord).order_by(NotificationRecord.sequence)))
                self.history.records = {row.id: unpack(row, HISTORY_FIELDS) for row in histories}
                self.notifications.items = [
                    {**unpack(row, NOTICE_FIELDS), "read": row.status == "viewed"} for row in reversed(notices)
                ]
                previous = deepcopy((self.history.records, self.notifications.items))
                self._in_transaction = True
                try:
                    yield
                    synchronize(session, histories, self.history.records.values(), HistoryRecord, HISTORY_FIELDS)
                    # Flush parent history before inserting notifications with foreign keys.
                    session.flush()
                    synchronize(session, notices, reversed(self.notifications.items), NotificationRecord,
                                NOTICE_FIELDS, notification=True)
                    database.commit(session, "Invalid notification or history data.")
                except Exception as error:
                    session.rollback()
                    self.history.records, self.notifications.items = previous
                    if isinstance(error, IntegrityError):
                        raise ApiError(409, "conflict", "Invalid notification or history data.") from error
                    raise
                finally:
                    self._in_transaction = False

    def apply(self, events):
        with self.transaction():
            return super().apply(events)
