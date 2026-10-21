"""Module 6: authenticated participation history and optional UTC date filters."""
from fastapi import APIRouter, Depends, Query, Response

from app.deps import get_current_user
from app.models import User
from app.store import db

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(response: Response,
                 from_date: str | None = Query(default=None, alias="from"),
                 to_date: str | None = Query(default=None, alias="to"),
                 user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    with db.activity.lock:
        return db.activity.history.list(user.id, from_date, to_date)
