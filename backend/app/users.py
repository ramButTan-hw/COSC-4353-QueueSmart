"""Everything the app does with user accounts, on top of the UserCredentials and UserProfile tables.

Two ways to call it:
  * with a session, inside a request:  users.find_by_email(session, ...), users.create_user(session, ...)
  * standalone, when there is no request session (queue code, tests): users.lookup(...), users.save(...)

The rest of the app works with the plain `User` object (app/models.py): id, name, email, password_hash, role. The
name comes from the profile.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, database
from app.models import User
from app.security import hash_password
from app.tables.credentials import UserCredentials
from app.tables.profile import UserProfile

DEMO_PASSWORD = "Password1"
DEMO_USERS = [
    ("11111111-1111-4111-8111-111111111111", "Demo Student", "student@uh.edu", config.ROLE_STUDENT),
    ("22222222-2222-4222-8222-222222222222", "Demo Staff", "admin@uh.edu", config.ROLE_STAFF),
]


def _to_user(credentials: UserCredentials, profile: UserProfile) -> User:
    return User(credentials.id, profile.full_name, credentials.email, credentials.password_hash, credentials.role)


def _select_users():
    return select(UserCredentials, UserProfile).join(UserProfile, UserProfile.user_id == UserCredentials.id)


def create_user(session: Session, user: User, phone: str | None = None, preferences: str | None = None) -> User:
    """Add the account and its profile together. The caller commits (use database.commit), and that is where a
    duplicate email or any other violated constraint is reported."""
    session.add(UserCredentials(
        id=user.id, email=user.email, password_hash=user.password_hash, role=user.role,
        profile=UserProfile(user_id=user.id, email=user.email, full_name=user.name, phone=phone, preferences=preferences),
    ))
    return user


def find_by_email(session: Session, email: str) -> User | None:
    row = session.execute(_select_users().where(UserCredentials.email == email.strip().lower())).first()
    return _to_user(*row) if row else None


def find_by_id(session: Session, user_id: str) -> User | None:
    row = session.execute(_select_users().where(UserCredentials.id == user_id)).first()
    return _to_user(*row) if row else None


def staff_ids(session: Session) -> list[str]:
    return list(session.scalars(select(UserCredentials.id).where(UserCredentials.role == config.ROLE_STAFF).order_by(UserCredentials.id)))


def get_profile(session: Session, user_id: str) -> UserProfile | None:
    return session.get(UserProfile, user_id)


def update_profile(session: Session, user_id: str, changes: dict) -> UserProfile | None:
    """Apply only the given fields (full_name, phone, preferences). The caller commits."""
    profile = session.get(UserProfile, user_id)
    if profile is not None:
        for field, value in changes.items():
            setattr(profile, field, value)
        session.flush()
    return profile


# ---- standalone versions (their own short session) ----

def lookup(user_id: str) -> User | None:
    with database.session_scope() as session:
        return find_by_id(session, user_id)


def lookup_by_email(email: str) -> User | None:
    with database.session_scope() as session:
        return find_by_email(session, email)


def lookup_staff_ids() -> list[str]:
    with database.session_scope() as session:
        return staff_ids(session)


def save(user: User, phone: str | None = None, preferences: str | None = None) -> User:
    with database.session_scope() as session:
        create_user(session, user, phone, preferences)
        database.commit(session, "An account with this email already exists.")
    return user


@database.register_seeder
def seed_demo_users(session: Session) -> None:
    """The two demo accounts, created only when missing."""
    for user_id, name, email, role in DEMO_USERS:
        if find_by_email(session, email) is None:
            create_user(session, User(user_id, name, email, hash_password(DEMO_PASSWORD), role))
