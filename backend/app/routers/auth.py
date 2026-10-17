"""Authentication module: register, login, current user."""
import uuid

from fastapi import APIRouter, Depends

from app import config
from app.deps import get_current_user
from app.errors import ApiError
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenOut, UserOut
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.store import db

router = APIRouter(prefix="/auth", tags=["auth"])


def _public(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.name, email=user.email, role=user.role)


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest):
    if db.get_user_by_email(body.email) is not None:
        raise ApiError(409, "conflict", "An account with this email already exists.",
                       fields={"email": "An account with this email already exists."})
    # Registration only assign role = student
    user = User(str(uuid.uuid4()), body.name, body.email, hash_password(body.password), config.ROLE_STUDENT)
    db.add_user(user)
    return _public(user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest):
    user = db.get_user_by_email(body.email)
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise ApiError(401, "unauthorized", "Incorrect email or password.", headers={"WWW-Authenticate": "Bearer"})
    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in, user=_public(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _public(user)
