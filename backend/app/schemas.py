"""Request and response shapes, with all input validation rules.

Rules (same limits as the A2 front end where they overlap):
  name      required, trimmed, 1-100 characters
  email     required, trimmed, valid format, at most 254 characters, stored lowercase
  password  register: 8-128 characters with at least one letter and one number
            login:    required, at most 128 characters
Services:
  name        required, trimmed, 1-100 characters, unique (case-insensitive; checked in the router)
  description required, trimmed, 1-500 characters
  duration    whole number of minutes, 1-480 (no strings, floats or booleans)
  priority    'low', 'medium' or 'high'
Unknown fields are rejected.
"""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMAIL_MAX = 254
NAME_MAX = 100
PASSWORD_MIN = 8
PASSWORD_MAX = 128
DESCRIPTION_MAX = 500
DURATION_MIN = 1
DURATION_MAX = 480

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


class ServiceIn(_Strict):
    name: Name
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX)]
    duration: Annotated[int, Field(strict=True, ge=DURATION_MIN, le=DURATION_MAX)]
    priority: Literal["low", "medium", "high"]


class ServiceUpdate(_Strict):
    name: Name = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX)] = None
    duration: Annotated[int, Field(strict=True, ge=DURATION_MIN, le=DURATION_MAX)] = None
    priority: Literal["low", "medium", "high"] = None

    @model_validator(mode="after")
    def _something_to_change(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one field to change.")
        return self


class ServiceOut(BaseModel):
    id: int
    name: str
    description: str
    duration: int
    priority: str
    open: bool

class QueueEntryOut(BaseModel):
    id: int
    service_id: int
    user_id: str
    user_name: str
    priority: str
    joined_at: float
    position: int
    estimated_wait_minutes: int


class QueueOut(BaseModel):
    service_id: int
    service_name: str
    open: bool
    count: int
    estimated_wait_minutes: int  # Estimate for the next student joining this service.
    entries: list[QueueEntryOut]
