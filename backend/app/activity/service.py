"""Atomic event sink that the team's queue module can call after a queue change."""
from copy import deepcopy
from threading import RLock
from time import time_ns
from uuid import uuid4
from pydantic import ValidationError
from app.errors import ApiError
from .history import History
from .notifications import Notifications
from .schemas import EventBatch


def now_ms():
    return time_ns() // 1_000_000


class Activity:
    def __init__(self, clock=now_ms):
        self.id = str(uuid4())
        self.lock = RLock()
        self.notifications = Notifications(clock)
        self.history = History(clock)

    def apply(self, events):
        try:
            batch = EventBatch.model_validate({"events": events})
        except ValidationError as error:
            first = error.errors()[0]
            raise ApiError(422, "validation_error", f"{'.'.join(map(str, first['loc']))}: {first['msg']}") from error
        with self.lock:
            previous = deepcopy((self.history.records, self.notifications.items))
            try:
                for event in batch.events:
                    record = self.history.join(event) if event.type == "joined" else self.history.active(event.participation_id)
                    if event.type == "joined":
                        self.notifications.joined(record, event.position)
                    if event.type in ("joined", "position"):
                        record["position"] = event.position
                        record["queueOpen"] = event.queue_open
                        self.notifications.close(record, event.position, event.queue_open)
                    else:
                        self.history.complete(record, event.type)
            except Exception:
                self.history.records, self.notifications.items = previous
                raise
        return {"processed": len(batch.events)}
