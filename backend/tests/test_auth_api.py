import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.deps import require_staff
from app.errors import ApiError
from app.main import app
from app.models import User
from app.security import create_access_token
from app.store import db, seed_demo_users
from tests.conftest import VALID, bearer


# ---------- register ----------

def test_register_creates_a_student(client):
    r = client.post("/auth/register", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Alex Nguyen" and body["email"] == "alex@uh.edu" and body["role"] == "student"
    assert body["id"]
    assert "password" not in body and "password_hash" not in body


def test_register_normalizes_email_and_trims_name(client):
    r = client.post("/auth/register", json={**VALID, "name": "  Alex  ", "email": "  ALEX@UH.EDU "})
    assert r.status_code == 201
    assert r.json()["email"] == "alex@uh.edu" and r.json()["name"] == "Alex"


def test_register_ignores_a_requested_role(client):
    r = client.post("/auth/register", json={**VALID, "role": "staff"})
    assert r.status_code == 422  # unknown fields are rejected, so nobody can self-assign staff
    assert r.json()["error"]["fields"]["role"] == "Unknown field."


def test_register_duplicate_email_is_a_conflict_regardless_of_case(client, registered):
    r = client.post("/auth/register", json={**VALID, "email": "ALEX@uh.edu"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"
    assert "email" in r.json()["error"]["fields"]


def test_register_stores_a_hash_not_the_password(client):
    client.post("/auth/register", json=VALID)
    stored = db.get_user_by_email("alex@uh.edu")
    assert stored.password_hash != VALID["password"]


@pytest.mark.parametrize(
    "change, field, message",
    [
        ({"name": ""}, "name", "This field is required."),
        ({"name": "   "}, "name", "This field is required."),
        ({"name": "x" * 101}, "name", "Must be at most 100 characters."),
        ({"email": ""}, "email", "This field is required."),
        ({"email": "not-an-email"}, "email", "Enter a valid email address."),
        ({"email": "a@b"}, "email", "Enter a valid email address."),
        ({"email": "a" * 250 + "@b.co"}, "email", "Must be at most 254 characters."),
        ({"password": "short1"}, "password", "Must be at least 8 characters."),
        ({"password": "x" * 129 + "1"}, "password", "Must be at most 128 characters."),
        ({"password": "alllettersnodigits"}, "password", "Password must contain at least one letter and one number."),
        ({"password": "12345678"}, "password", "Password must contain at least one letter and one number."),
        ({"name": 123}, "name", "Must be a string."),
        ({"email": ["a@b.co"]}, "email", "Must be a string."),
        ({"password": 12345678}, "password", "Must be a string."),
    ],
)
def test_register_validation_errors(client, change, field, message):
    r = client.post("/auth/register", json={**VALID, **change})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["fields"][field] == message


@pytest.mark.parametrize("missing", ["name", "email", "password"])
def test_register_missing_field(client, missing):
    payload = {k: v for k, v in VALID.items() if k != missing}
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["fields"][missing] == "This field is required."


def test_register_reports_every_bad_field_at_once(client):
    r = client.post("/auth/register", json={"name": "", "email": "bad", "password": "x"})
    assert set(r.json()["error"]["fields"]) == {"name", "email", "password"}


def test_register_invalid_json_body(client):
    r = client.post("/auth/register", content="{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


# ---------- login ----------

def test_login_returns_bearer_token_and_user(client, registered):
    r = client.post("/auth/login", json=registered)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == config.TOKEN_TTL_SECONDS
    assert body["access_token"]
    assert body["user"]["email"] == "alex@uh.edu" and body["user"]["role"] == "student"


def test_login_is_case_and_space_insensitive_for_email(client, registered):
    r = client.post("/auth/login", json={"email": " ALEX@uh.edu ", "password": registered["password"]})
    assert r.status_code == 200


def test_login_wrong_password_and_unknown_email_look_the_same(client, registered):
    wrong_pw = client.post("/auth/login", json={"email": registered["email"], "password": "WrongPass1"})
    unknown = client.post("/auth/login", json={"email": "nobody@uh.edu", "password": "WrongPass1"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()
    assert wrong_pw.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"email": "", "password": "x"}, "email"),
        ({"email": "bad", "password": "x"}, "email"),
        ({"email": "a@b.co", "password": ""}, "password"),
        ({"email": "a@b.co"}, "password"),
        ({"password": "x"}, "email"),
        ({"email": "a@b.co", "password": 5}, "password"),
        ({"email": "a@b.co", "password": "x" * 129}, "password"),
    ],
)
def test_login_validation_errors(client, payload, field):
    r = client.post("/auth/login", json=payload)
    assert r.status_code == 422
    assert field in r.json()["error"]["fields"]


# ---------- /auth/me and protected access ----------

def test_me_returns_the_logged_in_user(client, token):
    r = client.get("/auth/me", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["email"] == "alex@uh.edu"


def test_me_without_a_token_is_unauthorized(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_with_a_non_bearer_scheme_is_unauthorized(client):
    assert client.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_me_with_a_bad_token_is_unauthorized(client):
    assert client.get("/auth/me", headers=bearer("garbage")).status_code == 401


def test_me_with_an_expired_token_is_unauthorized(client, registered):
    user = db.get_user_by_email(registered["email"])
    expired, _ = create_access_token(user, ttl_seconds=60, now=int(time.time()) - 3600)
    r = client.get("/auth/me", headers=bearer(expired))
    assert r.status_code == 401
    assert "expired" in r.json()["error"]["message"].lower()


def test_token_for_a_user_that_no_longer_exists_is_rejected(client, token):
    db.reset()  # like a server restart: accounts are gone but the old token still verifies
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


# ---------- roles ----------

def test_require_staff_blocks_students():
    student = User("s", "S", "s@uh.edu", "x", config.ROLE_STUDENT)
    with pytest.raises(ApiError) as exc:
        require_staff(student)
    assert exc.value.status_code == 403
    assert exc.value.code == "forbidden"


def test_require_staff_allows_staff():
    staff = User("a", "A", "a@uh.edu", "x", config.ROLE_STAFF)
    assert require_staff(staff) is staff


# ---------- seeded demo accounts ----------

def test_startup_seeds_demo_student_and_staff():
    with TestClient(app) as c:  # entering the context runs the startup seeding
        student = c.post("/auth/login", json={"email": "student@uh.edu", "password": "Password1"})
        staff = c.post("/auth/login", json={"email": "admin@uh.edu", "password": "Password1"})
    assert student.status_code == 200 and student.json()["user"]["role"] == "student"
    assert staff.status_code == 200 and staff.json()["user"]["role"] == "staff"


def test_seeding_twice_does_not_duplicate_accounts():
    seed_demo_users()
    seed_demo_users()
    assert len(db.users) == 2


# ---------- app-level behaviour ----------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unknown_route_uses_the_standard_error_shape(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_wrong_method_uses_the_standard_error_shape(client):
    r = client.get("/auth/login")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"


def test_cors_allows_the_front_end_origin_and_auth_header(client):
    r = client.options(
        "/auth/me",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert "authorization" in r.headers["access-control-allow-headers"].lower()
