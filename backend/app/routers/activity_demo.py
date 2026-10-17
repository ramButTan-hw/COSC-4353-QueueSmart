"""Temporary A2 browser-queue bridge; replace when the queue module moves to Python.

The future queue module calls db.activity.apply(events) directly after validating its
queue operation. The read APIs in notifications.py and history.py remain unchanged.
"""
from fastapi import APIRouter, Depends, Response

from app import config
from app.activity.schemas import EventBatch
from app.deps import get_current_user
from app.errors import ApiError
from app.models import User
from app.store import db

router = APIRouter(prefix="/api", tags=["A2 queue bridge"])


@router.get("/session")
def session(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"id": db.activity.id}


@router.post("/queue-events")
def queue_events(body: EventBatch, user: User = Depends(get_current_user)):
    activity = db.activity
    with activity.lock:
        if user.role == config.ROLE_STAFF:
            for event in body.events:
                if event.type == "joined":
                    participant = db.get_user(event.user_id)
                    if participant is None or participant.role != config.ROLE_STUDENT:
                        raise ApiError(422, "validation_error", "Participant must be a registered student.")
            return activity.apply(body.events)

        # A student may join or leave only their own visit. Positions for other
        # participants are derived here, never accepted from a student's request.
        if len(body.events) != 1 or body.events[0].type not in ("joined", "left"):
            raise ApiError(403, "forbidden", "Students may only join or leave their own queue.")
        event = body.events[0]
        if event.type == "joined":
            if event.user_id != user.id:
                raise ApiError(403, "forbidden", "You may only join as yourself.")
            if not event.queue_open:
                raise ApiError(409, "conflict", "This queue is closed.")
            waiting = [r for r in activity.history.records.values()
                       if r["serviceId"] == event.service_id and r["outcome"] == "Waiting"]
            event = event.model_copy(update={"position": len(waiting) + 1})
            return activity.apply([event])

        record = activity.history.active(event.participation_id)
        if record["userId"] != user.id:
            raise ApiError(403, "forbidden", "You may only leave your own queue.")
        events = [event]
        for other in activity.history.records.values():
            if (other["serviceId"] == record["serviceId"] and other["outcome"] == "Waiting"
                    and other["position"] > record["position"]):
                events.append({"type": "position", "participationId": other["id"],
                               "position": other["position"] - 1, "queueOpen": other["queueOpen"]})
        activity.apply(events)
        return {"processed": 1}
