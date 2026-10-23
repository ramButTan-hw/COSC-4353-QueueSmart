"""Keep queue state and modules 5/6 in one atomic in-memory change."""
from contextlib import contextmanager
from copy import deepcopy

from app import config
from app.store import db


@contextmanager
def transaction():
    with db.activity.lock:
        previous = deepcopy((db.queues, db.services, db._next_service_id, db._next_queue_entry_id,
                             db.activity.history.records, db.activity.notifications.items))
        try:
            yield
        except Exception:
            (db.queues, db.services, db._next_service_id, db._next_queue_entry_id,
             db.activity.history.records, db.activity.notifications.items) = previous
            raise


def visit_id(entry):
    return f"queue-{entry.id}"


def positions(service):
    return [{"type": "position", "participationId": visit_id(entry),
             "position": index, "queueOpen": service.open}
            for index, entry in enumerate(db.ordered_queue(service.id), 1)]


def apply(events):
    # Queue length is unbounded in A3; the internal event contract accepts batches of 1000.
    # Callers hold transaction(), so failure in any chunk rolls back the whole change.
    for offset in range(0, len(events), 1000):
        db.activity.apply(events[offset:offset + 1000])


def staff_alert(entry, kind, message):
    """One notification per staff account, stored on the server so it reaches staff in any browser."""
    for user in list(db.users.values()):
        if user.role == config.ROLE_STAFF:
            db.activity.notifications.add_to(user.id, config.ROLE_STAFF, visit_id(entry), kind, message, "info")


def queue_toggled(service):
    """Tell every student waiting in this queue that it was just opened or closed."""
    for entry in db.ordered_queue(service.id):
        db.activity.notifications.queue_state(db.activity.history.records[visit_id(entry)], service.open)


def joined(service, entry):
    ordered = db.ordered_queue(service.id)
    apply([{"type": "joined", "participationId": visit_id(entry), "userId": entry.user_id,
            "serviceId": service.id, "serviceName": service.name,
            "position": ordered.index(entry) + 1, "queueOpen": service.open}, *positions(service)])
    db.activity.history.records[visit_id(entry)]["joinedAt"] = int(entry.joined_at * 1000)
    staff_alert(entry, "student_joined", f"New student in {service.name}")


def completed(service, entries, outcome):
    apply([{"type": outcome, "participationId": visit_id(entry)} for entry in entries] + positions(service))
    if outcome == "left":
        for entry in entries:
            staff_alert(entry, "student_left", f"A student left the {service.name} queue")
    if outcome in ("served", "removed"):
        for entry in entries:
            record = db.activity.history.records[visit_id(entry)]
            message = (f"You've been served for {service.name}" if outcome == "served"
                       else f"You were removed from the {service.name} queue")
            db.activity.notifications.add(record, outcome, message, "success" if outcome == "served" else "error")
