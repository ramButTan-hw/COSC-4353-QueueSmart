"""Two reusable routers and an optional bridge for the existing browser queue."""
from fastapi import APIRouter, Depends, Query
from .activity import Activity
from .errors import ActivityRoute
from .schemas import EventBatch


def create_routers(activity: Activity, user_dependency, *, demo_bridge: bool = False):
    notifications = APIRouter(prefix="/api/notifications", tags=["Notifications"], route_class=ActivityRoute)
    history = APIRouter(prefix="/api/history", tags=["History"], route_class=ActivityRoute)

    @notifications.get("")
    def list_notifications(user_id: str = Depends(user_dependency)):
        with activity.lock:
            return activity.notifications.list(user_id)

    @notifications.patch("/{notification_id}/read")
    def mark_read(notification_id: str, user_id: str = Depends(user_dependency)):
        with activity.lock:
            return activity.notifications.mark_read(user_id, notification_id)

    @notifications.post("/read-all")
    def mark_all_read(user_id: str = Depends(user_dependency)):
        with activity.lock:
            activity.notifications.mark_all_read(user_id)
        return {"read": True}

    @notifications.delete("")
    def clear_notifications(user_id: str = Depends(user_dependency)):
        with activity.lock:
            activity.notifications.clear(user_id)
        return {"cleared": True}

    @history.get("")
    def list_history(from_date: str | None = Query(default=None, alias="from"),
                     to_date: str | None = Query(default=None, alias="to"),
                     user_id: str = Depends(user_dependency)):
        with activity.lock:
            return activity.history.list(user_id, from_date, to_date)

    routers = [notifications, history]
    if demo_bridge:
        bridge = APIRouter(prefix="/api", tags=["A2 queue demo"], route_class=ActivityRoute)

        @bridge.get("/session")
        def session():
            return {"id": activity.id}

        @bridge.post("/queue-events")
        def queue_events(payload: EventBatch):
            return activity.apply(payload.events)

        routers.append(bridge)
    return routers
