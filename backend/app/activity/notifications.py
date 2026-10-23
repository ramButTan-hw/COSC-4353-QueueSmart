"""Module 5: per-user notifications (students: joining, position changes, near the front, queue open/closed,
served/removed; staff: students joining and leaving)."""
from copy import deepcopy
from uuid import uuid4
from app.errors import ApiError


class Notifications:
    def __init__(self, clock):
        self.clock = clock
        self.items = []

    def joined(self, record, position):
        self.add(record, "joined", f"You joined {record['serviceName']} at position {position}.", "success")

    def close(self, record, position, queue_open):
        """Reminder for a student near the front of an OPEN queue: once at position 2 ("nearly next") and
        once more at position 1 ("next"). Returns True when a reminder was sent."""
        if not queue_open or position > 2:
            return False
        if position == 1 and not record.get("nextNotified"):
            record["nextNotified"] = record["closeNotified"] = True
            label = "next"
        elif position == 2 and not record["closeNotified"]:
            record["closeNotified"] = True
            label = "nearly next"
        else:
            return False
        self.add(record, "close", f"You're {label} for {record['serviceName']}. Please head to the help desk.", "warning")
        return True

    def moved(self, record, position):
        self.add(record, "moved", f"You moved to position {position} in {record['serviceName']}.", "info")

    def queue_state(self, record, is_open):
        if is_open:
            self.add(record, "queue_open", f"{record['serviceName']} queue is now open.", "info")
        else:
            self.add(record, "queue_closed", f"{record['serviceName']} queue is now closed.", "warning")

    def add(self, record, kind, message, notification_type):
        self.add_to(record["userId"], "student", record["id"], kind, message, notification_type)

    def add_to(self, recipient_id, role, participation_id, kind, message, notification_type):
        self.items.insert(0, {
            "id": str(uuid4()), "recipientId": recipient_id, "role": role,
            "participationId": participation_id, "kind": kind, "message": message,
            "type": notification_type, "ts": self.clock(), "read": False,
        })

    def list(self, user_id):
        return deepcopy([item for item in self.items if item["recipientId"] == user_id])

    def mark_read(self, user_id, notification_id):
        for item in self.items:
            if item["id"] == notification_id and item["recipientId"] == user_id:
                item["read"] = True
                return deepcopy(item)
        raise ApiError(404, "not_found", "Notification not found.")

    def mark_all_read(self, user_id):
        for item in self.items:
            if item["recipientId"] == user_id:
                item["read"] = True

    def clear(self, user_id):
        self.items = [item for item in self.items if item["recipientId"] != user_id]
