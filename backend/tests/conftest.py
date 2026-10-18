import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import hash_password
from app.store import db


@pytest.fixture(autouse=True)
def clean_store():
    """Every test starts with an empty in-memory store."""
    db.reset()
    yield
    db.reset()


@pytest.fixture
def client():
    # No `with` block, so the startup seeding of demo accounts does not run.
    return TestClient(app)


VALID = {"name": "Alex Nguyen", "email": "alex@uh.edu", "password": "Passw0rdOK"}


@pytest.fixture
def registered(client):
    """A registered student; returns the credentials used."""
    assert client.post("/auth/register", json=VALID).status_code == 201
    return {"email": VALID["email"], "password": VALID["password"]}


@pytest.fixture
def token(client, registered):
    return client.post("/auth/login", json=registered).json()["access_token"]


def bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def student_headers(token):
    return bearer(token)


@pytest.fixture
def staff_headers(client):
    """Headers for a staff user (registration only creates students, so the user is added directly)."""
    db.add_user(User("staff-1", "Sam Staff", "staff@uh.edu", hash_password("Passw0rd1"), "staff"))
    tok = client.post("/auth/login", json={"email": "staff@uh.edu", "password": "Passw0rd1"}).json()["access_token"]
    return bearer(tok)
