"""Profile module: read and update your own profile (name, optional phone, preferences)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import database, users
from app.deps import get_current_user
from app.errors import ApiError
from app.models import User
from app.schemas import ProfileOut, ProfileUpdate
from app.tables.profile import UserProfile

router = APIRouter(prefix="/profile", tags=["profile"])


def _out(profile: UserProfile | None) -> ProfileOut:
    if profile is None:
        raise ApiError(404, "not_found", "Profile not found.")
    return ProfileOut(user_id=profile.user_id, email=profile.email, full_name=profile.full_name,
                      phone=profile.phone, preferences=profile.preferences)


@router.get("", response_model=ProfileOut)
def get_my_profile(user: User = Depends(get_current_user), session: Session = Depends(database.get_session)):
    return _out(users.get_profile(session, user.id))


@router.patch("", response_model=ProfileOut)
def update_my_profile(body: ProfileUpdate, user: User = Depends(get_current_user),
                      session: Session = Depends(database.get_session)):
    changes = {field: getattr(body, field) for field in body.model_fields_set}
    profile = _out(users.update_profile(session, user.id, changes))
    database.commit(session)
    return profile
