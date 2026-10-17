"""Module 5: per-user notifications for joining and approaching the front."""
from copy import deepcopy
from uuid import uuid4
from .errors import ApiError


class Notifications:
    def __init__(self, clock):
        self.clock = clock
        self.items = []

    def joined(self, record, position):
        self.add(record, "joined", f"You joined {record['serviceName']} at position {position}.", "success")

    def close(self, record, position, queue_open):
        if queue_open and position <= 2 and not record["closeNotified"]:
            record["closeNotified"] = True
            label = "next" if position == 1 else "nearly next"
            self.add(record, "close", f"You're {label} for {record['serviceName']}. Please head to the help desk.", "warning")

    def add(self, record, kind, message, notification_type):
        self.items.insert(0, {
            "id": str(uuid4()), "recipientId": record["userId"], "role": "student",
            "participationId": record["id"], "kind": kind, "message": message,
            "type": notification_type, "ts": self.clock(), "read": False,
        })

    def list(self, user_id):
        return deepcopy([item for item in self.items if item["recipientId"] == user_id])

    def mark_read(self, user_id, notification_id):
        for item in self.items:
            if item["id"] == notification_id and item["recipientId"] == user_id:
                item["read"] = True
                return deepcopy(item)
        raise ApiError(404, "Notification not found.")

    def mark_all_read(self, user_id):
        for item in self.items:
            if item["recipientId"] == user_id:
                item["read"] = True

    def clear(self, user_id):
        self.items = [item for item in self.items if item["recipientId"] != user_id]
