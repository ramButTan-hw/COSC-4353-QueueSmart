"""QueueSmart A3 modules 5 and 6: reusable FastAPI package."""
from fastapi import FastAPI
from .activity import Activity
from .errors import ApiError, activity_error
from .identity import demo_user_id
from .middleware import EventBodyLimit
from .routes import create_routers


def install_activity(app: FastAPI, *, user_dependency=None,
                     demo_bridge: bool = False, activity: Activity | None = None) -> Activity:
    """Mount notification/history APIs; return the event sink for the team's queue module.

    Supply user_dependency returning the authenticated user's string ID in the team's app.
    The demo bridge is for the A2 browser queue and is disabled by default.
    """
    if user_dependency is None:
        if not demo_bridge:
            raise ValueError("Supply the team's authenticated user_dependency.")
        user_dependency = demo_user_id
    if getattr(app.state, "queuesmart_activity", None) is not None:
        raise RuntimeError("Activity modules are already installed on this app.")
    store = activity if activity is not None else Activity()
    app.state.queuesmart_activity = store
    app.add_exception_handler(ApiError, activity_error)
    if demo_bridge:
        app.add_middleware(EventBodyLimit)
    for router in create_routers(store, user_dependency, demo_bridge=demo_bridge):
        app.include_router(router)
    return store


__all__ = ["Activity", "ApiError", "install_activity"]
