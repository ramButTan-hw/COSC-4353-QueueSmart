"""Module 5: notification access is always scoped to the authenticated user."""
from fastapi import APIRouter, Depends, Response

from app.deps import get_current_user
from app.models import User
from app.store import db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    with db.activity.lock:
        return db.activity.notifications.list(user.id)


@router.patch("/{notification_id}/read")
def mark_read(notification_id: str, user: User = Depends(get_current_user)):
    with db.activity.lock:
        return db.activity.notifications.mark_read(user.id, notification_id)


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user)):
    with db.activity.lock:
        db.activity.notifications.mark_all_read(user.id)
    return {"read": True}


@router.delete("")
def clear_notifications(user: User = Depends(get_current_user)):
    with db.activity.lock:
        db.activity.notifications.clear(user.id)
    return {"cleared": True}
