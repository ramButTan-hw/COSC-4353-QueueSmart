"""Dependencies every other module uses to protect its endpoints.

    @router.get("/something")
    def something(user: User = Depends(get_current_user)): ...      # any logged-in user

    @router.post("/admin-thing")
    def admin_thing(user: User = Depends(require_staff)): ...       # staff only

Other modules should not parse tokens themselves.
"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import config
from app.errors import ApiError
from app.models import User
from app.security import decode_access_token
from app.store import db

_bearer = HTTPBearer(auto_error=False, description="JWT from POST /auth/login")


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    if credentials is None:
        raise ApiError(401, "unauthorized", "Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    claims = decode_access_token(credentials.credentials)
    user = db.get_user(claims["sub"])
    if user is None:  # e.g. the server restarted and in-memory accounts are gone
        raise ApiError(401, "unauthorized", "Invalid authentication token.", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role != config.ROLE_STAFF:
        raise ApiError(403, "forbidden", "Staff access is required.")
    return user
