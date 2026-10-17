"""Password hashing and JWT helpers."""
import time

import jwt
from pwdlib import PasswordHash

from app import config
from app.errors import ApiError

_hasher = PasswordHash.recommended()  # argon2


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


# Checked when the email is unknown, so "no such account" and "wrong password" take the same time.
DUMMY_HASH = hash_password("not-a-real-password")


def create_access_token(user, ttl_seconds: int | None = None, now: int | None = None):
    """Return (token, expires_in_seconds). The token carries id, email and role, never the password."""
    ttl = config.TOKEN_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    issued = int(time.time()) if now is None else now
    payload = {"sub": user.id, "email": user.email, "role": user.role, "iat": issued, "exp": issued + ttl}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM), ttl


def decode_access_token(token: str) -> dict:
    """Return the token's claims, or raise a 401 ApiError if it is invalid or expired."""
    try:
        return jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "unauthorized", "Your session has expired. Please log in again.", headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError:
        raise ApiError(401, "unauthorized", "Invalid authentication token.", headers={"WWW-Authenticate": "Bearer"})
