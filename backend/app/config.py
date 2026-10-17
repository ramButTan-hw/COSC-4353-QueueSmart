"""Settings, read from environment variables with development defaults.

Values are read at import time. Other modules should access them as `config.NAME`
(not `from app.config import NAME`) so tests can override them.
"""
import os

# Signing key for JWTs. Set JWT_SECRET in the environment for anything beyond local testing.
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-secret-change-me-before-real-use-0123456789")
JWT_ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = int(os.environ.get("JWT_EXPIRES_MINUTES", "60")) * 60

# Front-end origins allowed to call the API from the browser (CORS).
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if o.strip()
]

ROLE_STUDENT = "student"
ROLE_STAFF = "staff"
ROLES = (ROLE_STUDENT, ROLE_STAFF)
