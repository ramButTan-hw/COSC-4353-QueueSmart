"""Module 6: in-memory visits, outcomes, and UTC join-date filtering."""
from datetime import datetime, timezone
import re
from .errors import ApiError


def date_range(from_date=None, to_date=None):
    def parse(value, field):
        if value is None:
            return None
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ApiError(400, f"{field} must be YYYY-MM-DD.")
        try:
            return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError as error:
            raise ApiError(400, f"{field} must be a valid date.") from error

    start, end = parse(from_date, "from"), parse(to_date, "to")
    if start is not None and end is not None and start > end:
        raise ApiError(400, "from cannot be after to.")
    return start, None if end is None else end + 86400000


class History:
    def __init__(self, clock):
        self.clock = clock
        self.records = {}

    def join(self, event):
        if event.participation_id in self.records:
            raise ApiError(409, "Participation already exists.")
        if any(record["userId"] == event.user_id and record["outcome"] == "Waiting" for record in self.records.values()):
            raise ApiError(409, "User already has an active participation.")
        record = {
            "id": event.participation_id, "userId": event.user_id, "serviceId": event.service_id,
            "serviceName": event.service_name, "joinedAt": self.clock(), "completedAt": None,
            "outcome": "Waiting", "closeNotified": False,
        }
        self.records[record["id"]] = record
        return record

    def active(self, participation_id):
        record = self.records.get(participation_id)
        if record is None:
            raise ApiError(404, "Participation not found.")
        if record["outcome"] != "Waiting":
            raise ApiError(409, "Participation is already complete.")
        return record

    def complete(self, record, event_type):
        record["outcome"] = {"served": "Served", "left": "Left queue", "removed": "Removed"}[event_type]
        record["completedAt"] = self.clock()

    def list(self, user_id, from_date=None, to_date=None):
        start, end = date_range(from_date, to_date)
        results = []
        for record in reversed(list(self.records.values())):
            if record["userId"] != user_id:
                continue
            if start is not None and record["joinedAt"] < start:
                continue
            if end is not None and record["joinedAt"] >= end:
                continue
            public = {key: value for key, value in record.items() if key != "closeNotified"}
            public["date"] = record["completedAt"] if record["completedAt"] is not None else record["joinedAt"]
            results.append(public)
        return results
