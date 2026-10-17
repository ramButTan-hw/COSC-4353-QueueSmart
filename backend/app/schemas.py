"""Request and response shapes, with all input validation rules.

Rules (same limits as the A2 front end where they overlap):
  name      required, trimmed, 1-100 characters
  email     required, trimmed, valid format, at most 254 characters, stored lowercase
  password  register: 8-128 characters with at least one letter and one number
            login:    required, at most 128 characters
Unknown fields are rejected.
"""
import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMAIL_MAX = 254
NAME_MAX = 100
PASSWORD_MIN = 8
PASSWORD_MAX = 128

Email = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=EMAIL_MAX)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_email(value: str) -> str:
    if not EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address.")
    return value


class RegisterRequest(_Strict):
    name: Name
    email: Email
    password: Annotated[str, StringConstraints(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)]

    @field_validator("email")
    @classmethod
    def _email_format(cls, value: str) -> str:
        return _check_email(value)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
            raise ValueError("Password must contain at least one letter and one number.")
        return value


class LoginRequest(_Strict):
    email: Email
    password: Annotated[str, StringConstraints(min_length=1, max_length=PASSWORD_MAX)]

    @field_validator("email")
    @classmethod
    def _email_format(cls, value: str) -> str:
        return _check_email(value)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
