"""Queue Management Module.

Students can:
- Join an open queue
- Leave a queue

Staff can:
- View a queue
- Serve the next student
- Open and close queues

Queue ordering uses priority first and arrival time second.
"""

import time

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from app import config, queue_activity
from app.deps import get_current_user, require_staff
from app.errors import ApiError
from app.models import QueueEntry, Service, User
from app.schemas import QueueEntryOut, QueueOut
from app.store import db


router = APIRouter(prefix="/queues", tags=["queues"])


@router.get("")
def queue_summaries(user: User = Depends(get_current_user)):
    """Counts for everyone; students see only their own entry, staff see all entries."""
    with db.activity.lock:
        results = []
        for service in db.list_services():
            ordered = db.ordered_queue(service.id)
            entries = [_entry_out(entry, index) for index, entry in enumerate(ordered, 1)
                       if user.role == config.ROLE_STAFF or entry.user_id == user.id]
            results.append({"service_id": service.id, "count": len(ordered),
                            "open": service.open, "entries": entries})
        return results


def _find_service(service_id: int) -> Service:
    service = db.get_service(service_id)

    if service is None:
        raise ApiError(
            404,
            "not_found",
            "Service not found.",
        )

    return service


def _entry_out(
    entry: QueueEntry,
    position: int,
) -> QueueEntryOut:
    user = db.get_user(entry.user_id)

    return QueueEntryOut(
        id=entry.id,
        service_id=entry.service_id,
        user_id=entry.user_id,
        user_name=user.name if user else "Unknown User",
        priority=entry.priority,
        joined_at=entry.joined_at,
        position=position,
    )


def _queue_out(service: Service) -> QueueOut:
    ordered = db.ordered_queue(service.id)

    entries = [
        _entry_out(entry, position)
        for position, entry in enumerate(ordered, start=1)
    ]

    return QueueOut(
        service_id=service.id,
        service_name=service.name,
        open=service.open,
        count=len(entries),
        entries=entries,
    )


def _remove_deleted_service_queue(service: Service):
    entries = db.clear_queue(service.id)
    queue_activity.completed(service, entries, "removed")


if _remove_deleted_service_queue not in db.service_deleted_hooks:
    db.service_deleted_hooks.append(_remove_deleted_service_queue)


@router.post(
    "/{service_id}/join",
    response_model=QueueEntryOut,
    status_code=201,
)
def join_queue(
    service_id: int,
    user: User = Depends(get_current_user),
):
    with queue_activity.transaction():
        service = _find_service(service_id)

        if user.role != config.ROLE_STUDENT:
            raise ApiError(
                403,
                "forbidden",
                "Only students can join a queue.",
            )

        if not service.open:
            raise ApiError(
                409,
                "queue_closed",
                "This queue is currently closed.",
            )

        existing = db.find_queue_entry(
            service_id,
            user.id,
        )

        if existing is not None:
            raise ApiError(
                409,
                "already_in_queue",
                "You are already in this queue.",
            )

        entry = db.add_queue_entry(
            service_id=service.id,
            user_id=user.id,
            priority=service.priority,
            joined_at=time.time(),
        )

        ordered = db.ordered_queue(service.id)

        position = next(
            index
            for index, item in enumerate(ordered, start=1)
            if item.id == entry.id
        )

        queue_activity.joined(service, entry)
        return _entry_out(
            entry,
            position,
        )


@router.delete(
    "/{service_id}/leave",
    status_code=204,
)
def leave_queue(
    service_id: int,
    user: User = Depends(get_current_user),
):
    with queue_activity.transaction():
        _find_service(service_id)

        entry = db.remove_queue_entry(
            service_id,
            user.id,
        )

        if entry is None:
            raise ApiError(
                404,
                "not_found",
                "You are not currently in this queue.",
            )

        queue_activity.completed(db.get_service(service_id), [entry], "left")
        return Response(status_code=204)


@router.get(
    "/{service_id}",
    response_model=QueueOut,
)
def view_queue(
    service_id: int,
    user: User = Depends(require_staff),
):
    service = _find_service(service_id)

    return _queue_out(service)


@router.post(
    "/{service_id}/serve-next",
    response_model=QueueEntryOut,
)
def serve_next(
    service_id: int,
    user: User = Depends(require_staff),
):
    with queue_activity.transaction():
        service = _find_service(service_id)

        ordered = db.ordered_queue(service.id)

        if not ordered:
            raise ApiError(
                409,
                "queue_empty",
                "There are no students waiting in this queue.",
            )

        if not service.open:
            raise ApiError(409, "queue_closed", "Open this queue before serving.")

        next_entry = ordered[0]

        db.remove_queue_entry(
            service.id,
            next_entry.user_id,
        )

        queue_activity.completed(service, [next_entry], "served")
        return _entry_out(
            next_entry,
            1,
        )


@router.post(
    "/{service_id}/open",
    response_model=QueueOut,
)
def open_queue(
    service_id: int,
    user: User = Depends(require_staff),
):
    with queue_activity.transaction():
        service = _find_service(service_id)

        service.open = True
        queue_activity.apply(queue_activity.positions(service))

        return _queue_out(service)


@router.post(
    "/{service_id}/close",
    response_model=QueueOut,
)
def close_queue(
    service_id: int,
    user: User = Depends(require_staff),
):
    with queue_activity.transaction():
        service = _find_service(service_id)

        service.open = False
        queue_activity.apply(queue_activity.positions(service))

        return _queue_out(service)


@router.delete("/{service_id}/members/{user_id}", status_code=204)
def remove_member(service_id: int, user_id: str, staff: User = Depends(require_staff)):
    with queue_activity.transaction():
        service = _find_service(service_id)
        entry = db.remove_queue_entry(service_id, user_id)
        if entry is None:
            raise ApiError(404, "not_found", "Student is not in this queue.")
        queue_activity.completed(service, [entry], "removed")
    return Response(status_code=204)


class MoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=254)
    direction: Literal["up", "down"]


@router.post("/{service_id}/move", response_model=QueueOut)
def move_member(service_id: int, body: MoveRequest, staff: User = Depends(require_staff)):
    with queue_activity.transaction():
        service = _find_service(service_id)
        ordered = db.ordered_queue(service_id)
        index = next((i for i, entry in enumerate(ordered) if entry.user_id == body.user_id), None)
        if index is None:
            raise ApiError(404, "not_found", "Student is not in this queue.")
        target = index + (-1 if body.direction == "up" else 1)
        if 0 <= target < len(ordered):
            if ordered[index].priority != ordered[target].priority:
                raise ApiError(409, "conflict", "Students can only move within the same priority level.")
            ordered[index], ordered[target] = ordered[target], ordered[index]
            for rank, entry in enumerate(ordered):
                entry.order = rank
            queue_activity.apply(queue_activity.positions(service))
        return _queue_out(service)
