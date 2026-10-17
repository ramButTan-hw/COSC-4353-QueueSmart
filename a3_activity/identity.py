"""Demo-only identity dependency; replace with the team's authenticated dependency."""
from typing import Annotated
from fastapi import Header
from .errors import ApiError


def demo_user_id(x_queuesmart_user: Annotated[str | None, Header()] = None) -> str:
    if not x_queuesmart_user or not x_queuesmart_user.strip() or len(x_queuesmart_user.strip()) > 254:
        raise ApiError(400, "X-QueueSmart-User must be a nonempty string of at most 254 characters.")
    return x_queuesmart_user.strip()
