import time

import jwt
import pytest

from app import config
from app.errors import ApiError
from app.models import User
from app.security import create_access_token, decode_access_token, hash_password, verify_password

USER = User("u-1", "Alex", "alex@uh.edu", "unused", "student")


def test_password_is_hashed_and_verifiable():
    hashed = hash_password("Passw0rdOK")
    assert hashed != "Passw0rdOK"
    assert verify_password("Passw0rdOK", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hashes_are_salted():
    assert hash_password("Passw0rdOK") != hash_password("Passw0rdOK")


def test_token_carries_identity_and_role_but_no_password():
    tok, expires_in = create_access_token(USER)
    claims = decode_access_token(tok)
    assert claims["sub"] == "u-1"
    assert claims["email"] == "alex@uh.edu"
    assert claims["role"] == "student"
    assert claims["exp"] - claims["iat"] == expires_in == config.TOKEN_TTL_SECONDS
    assert "password" not in claims and "password_hash" not in claims


def test_expired_token_is_rejected():
    tok, _ = create_access_token(USER, ttl_seconds=60, now=int(time.time()) - 3600)
    with pytest.raises(ApiError) as exc:
        decode_access_token(tok)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.message.lower()


def test_tampered_token_is_rejected():
    tok, _ = create_access_token(USER)
    with pytest.raises(ApiError) as exc:
        decode_access_token(tok[:-3] + ("AAA" if not tok.endswith("AAA") else "BBB"))
    assert exc.value.status_code == 401


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode({"sub": "u-1", "exp": int(time.time()) + 600}, "some-other-secret-that-is-long-enough-123", algorithm="HS256")
    with pytest.raises(ApiError) as exc:
        decode_access_token(forged)
    assert exc.value.status_code == 401


def test_token_without_expiry_is_rejected():
    no_exp = jwt.encode({"sub": "u-1"}, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    with pytest.raises(ApiError):
        decode_access_token(no_exp)


def test_garbage_token_is_rejected():
    with pytest.raises(ApiError):
        decode_access_token("not-a-jwt")
