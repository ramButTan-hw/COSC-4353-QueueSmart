"""UserCredentials and UserProfile: the tables, the account logic, registration, and the profile endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app import database, users
from app.errors import ApiError
from app.main import app
from app.models import User
from app.routers.profile import _out
from app.security import hash_password, verify_password
from app.tables.credentials import UserCredentials
from app.tables.profile import UserProfile
from tests.conftest import VALID, bearer


@pytest.fixture
def session():
    with database.SessionLocal() as s:
        yield s


def credentials(**overrides):
    values = dict(id="u1", email="a@uh.edu", password_hash="hash", role="student")
    return UserCredentials(**{**values, **overrides})


def profile(**overrides):
    values = dict(user_id="u1", email="a@uh.edu", full_name="Alex")
    return UserProfile(**{**values, **overrides})


def save_account(session, **overrides):
    session.add(credentials(**overrides))
    session.flush()


def count(session, table):
    return session.scalar(select(func.count()).select_from(table))


def row_for(email):
    with database.SessionLocal() as s:
        return s.execute(select(UserCredentials, UserProfile).join(UserProfile, UserProfile.user_id == UserCredentials.id)
                         .where(UserCredentials.email == email)).first()


# ---------- UserCredentials table ----------

def test_a_valid_account_is_saved_with_a_creation_time(session):
    save_account(session)
    session.commit()
    saved = session.get(UserCredentials, "u1")
    assert (saved.email, saved.role) == ("a@uh.edu", "student") and saved.created_at is not None


def test_emails_are_unique(session):
    save_account(session)
    session.add(credentials(id="u2"))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(("field", "value"), [
    ("email", "Alex@uh.edu"),            # must be lowercase
    ("email", "no-at-sign"),
    ("email", "@uh.edu"),
    ("email", "alex@"),
    ("email", "a" * 250 + "@uh.edu"),    # longer than 254
    ("role", "admin"),
    ("role", ""),
    ("password_hash", ""),
    ("id", "i" * 37),
    ("id", ""),
])
def test_the_database_rejects_invalid_accounts(session, field, value):
    session.add(credentials(**{field: value}))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("field", ["email", "password_hash", "role"])
def test_required_account_columns_cannot_be_missing(session, field):
    session.add(credentials(**{field: None}))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("role", ["student", "staff"])
def test_both_roles_are_allowed(session, role):
    save_account(session, role=role)


# ---------- UserProfile table ----------

def test_a_profile_needs_an_existing_account(session):
    session.add(profile(user_id="missing"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_profiles_email_must_belong_to_an_account(session):
    save_account(session)
    session.add(profile(email="other@uh.edu"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_an_account_has_at_most_one_profile(session):
    save_account(session)
    session.add(profile())
    session.flush()
    session.add(profile(email="a@uh.edu"))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_the_full_name_must_be_1_to_100_visible_characters(session, name):
    save_account(session)
    session.add(profile(full_name=name))
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_name_of_exactly_100_characters_is_fine(session):
    save_account(session)
    session.add(profile(full_name="n" * 100))
    session.flush()


@pytest.mark.parametrize(("field", "value"), [("phone", "123456"), ("phone", "1" * 31), ("preferences", ""), ("preferences", "p" * 501)])
def test_optional_fields_have_length_limits(session, field, value):
    save_account(session)
    session.add(profile(**{field: value}))
    with pytest.raises(IntegrityError):
        session.flush()


def test_optional_fields_may_be_missing_or_at_their_limits(session):
    save_account(session)
    session.add(profile(phone=None, preferences=None))
    session.flush()
    session.execute(update(UserProfile).values(phone="1" * 30, preferences="p" * 500))
    session.flush()


def test_deleting_an_account_deletes_its_profile(session):
    save_account(session)
    session.add(profile())
    session.commit()
    session.execute(delete(UserCredentials))
    session.commit()
    assert count(session, UserProfile) == 0


def test_changing_an_accounts_email_updates_its_profile(session):
    save_account(session)
    session.add(profile())
    session.commit()
    session.execute(update(UserCredentials).values(email="new@uh.edu"))
    session.commit()
    assert session.get(UserProfile, "u1").email == "new@uh.edu"


def test_keys_and_constraints_have_predictable_names():
    accounts, profiles = str(CreateTable(UserCredentials.__table__)), str(CreateTable(UserProfile.__table__))
    for name in ("pk_user_credentials", "uq_user_credentials_email", "ck_user_credentials_role_valid", "ck_user_credentials_email_lowercase"):
        assert f"CONSTRAINT {name}" in accounts
    for name in ("pk_user_profile", "fk_user_profile_user_id_user_credentials", "fk_user_profile_email_user_credentials", "ck_user_profile_full_name_length"):
        assert f"CONSTRAINT {name}" in profiles


# ---------- account logic (app/users.py) ----------

def make_user(**overrides):
    return User(**{**dict(id="u1", name="Alex Nguyen", email="alex@uh.edu", password_hash=hash_password("Passw0rdOK"), role="student"), **overrides})


def test_create_user_saves_the_account_and_the_profile_together(session):
    users.create_user(session, make_user(), phone="713-555-0100", preferences="email me")
    database.commit(session)
    assert session.get(UserCredentials, "u1").email == "alex@uh.edu"
    saved = session.get(UserProfile, "u1")
    assert (saved.full_name, saved.phone, saved.preferences) == ("Alex Nguyen", "713-555-0100", "email me")


def test_users_come_back_as_plain_user_objects_found_by_id_or_email(session):
    user = make_user()
    users.create_user(session, user)
    database.commit(session)
    assert users.find_by_id(session, "u1") == user
    assert users.find_by_email(session, "  ALEX@uh.edu ") == user
    assert users.find_by_email(session, "nobody@uh.edu") is None and users.find_by_id(session, "nope") is None


def test_a_failed_profile_leaves_no_account_behind(session):
    users.create_user(session, make_user(name=""))
    with pytest.raises(ApiError):  # the commit reports the violated constraint
        database.commit(session)
    assert count(session, UserCredentials) == 0 and count(session, UserProfile) == 0


def test_staff_ids_lists_only_staff(session):
    for user_id, role in (("b", "student"), ("s2", "staff"), ("s1", "staff")):
        users.create_user(session, make_user(id=user_id, email=f"{user_id}@uh.edu", role=role))
    database.commit(session)
    assert users.staff_ids(session) == ["s1", "s2"]


def test_the_standalone_helpers_use_their_own_session():
    user = users.save(make_user())
    assert users.lookup("u1") == user and users.lookup_by_email("alex@uh.edu") == user and users.lookup("zzz") is None
    assert users.lookup_staff_ids() == []
    with pytest.raises(ApiError) as error:
        users.save(make_user(id="u2"))  # same email
    assert error.value.status_code == 409


def test_updating_a_profile_changes_only_the_given_fields(session):
    users.create_user(session, make_user(), phone="713-555-0100")
    updated = users.update_profile(session, "u1", {"full_name": "Alex N."})
    assert (updated.full_name, updated.phone) == ("Alex N.", "713-555-0100")
    assert users.update_profile(session, "missing", {"full_name": "x"}) is None


# ---------- demo accounts ----------

def test_the_demo_accounts_are_created_with_hashed_passwords(session):
    database.init_db()
    for user_id, name, email, role in users.DEMO_USERS:
        stored = session.get(UserCredentials, user_id)
        assert stored.email == email and stored.role == role
        assert stored.password_hash != users.DEMO_PASSWORD and stored.password_hash.startswith("$argon2")
        assert verify_password(users.DEMO_PASSWORD, stored.password_hash)
        assert session.get(UserProfile, user_id).full_name == name


def test_demo_accounts_are_not_recreated_or_overwritten(session):
    database.init_db()
    session.execute(update(UserProfile).where(UserProfile.user_id == users.DEMO_USERS[0][0]).values(full_name="Renamed"))
    session.commit()
    database.init_db()
    assert count(session, UserCredentials) == 2
    assert session.get(UserProfile, users.DEMO_USERS[0][0]).full_name == "Renamed"


# ---------- registration ----------

def test_registering_saves_hashed_credentials_and_a_profile(client):
    r = client.post("/auth/register", json={**VALID, "phone": " 713 555 0100 ", "preferences": "  text me  "})
    assert r.status_code == 201
    credentials_row, profile_row = row_for("alex@uh.edu")
    assert credentials_row.id == r.json()["id"] and credentials_row.role == "student"
    assert credentials_row.password_hash != VALID["password"] and credentials_row.password_hash.startswith("$argon2")
    assert (profile_row.full_name, profile_row.phone, profile_row.preferences) == ("Alex Nguyen", "713 555 0100", "text me")


def test_phone_and_preferences_are_optional_when_registering(client):
    assert client.post("/auth/register", json=VALID).status_code == 201
    _, profile_row = row_for("alex@uh.edu")
    assert profile_row.phone is None and profile_row.preferences is None


@pytest.mark.parametrize(("field", "value", "message"), [
    ("phone", "abc", "Enter a valid phone number"),
    ("phone", "123456", "Enter a valid phone number"),
    ("phone", "(((((((((", "Enter a valid phone number"),
    ("phone", "1" * 31, "Must be at most 30 characters."),
    ("phone", "", "This field is required."),
    ("preferences", "p" * 501, "Must be at most 500 characters."),
    ("preferences", "   ", "This field is required."),
])
def test_invalid_phone_or_preferences_are_rejected_when_registering(client, field, value, message):
    r = client.post("/auth/register", json={**VALID, field: value})
    assert r.status_code == 422 and r.json()["error"]["fields"][field].startswith(message)
    assert row_for("alex@uh.edu") is None


def test_a_duplicate_email_creates_nothing_new(client, registered, session):
    r = client.post("/auth/register", json={**VALID, "email": "ALEX@uh.edu", "name": "Someone Else"})
    assert r.status_code == 409 and r.json()["error"]["fields"] == {"email": "An account with this email already exists."}
    assert count(session, UserCredentials) == 1 and count(session, UserProfile) == 1


def test_two_sign_ups_racing_for_one_email_are_stopped_by_the_database(client, registered, session, monkeypatch):
    monkeypatch.setattr(users, "find_by_email", lambda *args: None)  # both requests saw "free" before either saved
    r = client.post("/auth/register", json={**VALID, "name": "Second Person"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"
    assert count(session, UserCredentials) == 1 and count(session, UserProfile) == 1
    assert session.scalar(select(UserProfile.full_name)) == "Alex Nguyen"


def test_accounts_survive_a_restart_when_the_database_is_a_file(tmp_path):
    url = f"sqlite:///{tmp_path / 'queuesmart.db'}"
    try:
        database.configure(url)
        database.init_db()
        with TestClient(app) as running:
            assert running.post("/auth/register", json={**VALID, "phone": "713-555-0100"}).status_code == 201
        database.configure(url)  # a brand-new engine and connections, like starting the server again
        with TestClient(app) as restarted:
            login = restarted.post("/auth/login", json={"email": VALID["email"], "password": VALID["password"]})
            assert login.status_code == 200 and login.json()["user"]["name"] == "Alex Nguyen"
            me = restarted.get("/profile", headers=bearer(login.json()["access_token"]))
            assert me.json()["phone"] == "713-555-0100"
            assert restarted.post("/auth/login", json={"email": "student@uh.edu", "password": "Password1"}).status_code == 200
        assert (tmp_path / "queuesmart.db").stat().st_size > 0
    finally:
        database.configure("sqlite://")


# ---------- profile endpoints ----------

def test_the_profile_requires_a_login(client):
    assert client.get("/profile").status_code == 401
    assert client.patch("/profile", json={"full_name": "x"}).status_code == 401


def test_you_can_read_your_own_profile(client, token, registered):
    r = client.get("/profile", headers=bearer(token))
    assert r.status_code == 200
    assert r.json() == {"user_id": r.json()["user_id"], "email": "alex@uh.edu", "full_name": "Alex Nguyen", "phone": None, "preferences": None}


def test_a_changed_name_shows_up_everywhere(client, token, registered):
    r = client.patch("/profile", json={"full_name": "  Alexander N.  "}, headers=bearer(token))
    assert r.status_code == 200 and r.json()["full_name"] == "Alexander N."
    assert client.get("/auth/me", headers=bearer(token)).json()["name"] == "Alexander N."
    assert client.post("/auth/login", json=registered).json()["user"]["name"] == "Alexander N."
    assert row_for("alex@uh.edu")[1].full_name == "Alexander N."


def test_phone_and_preferences_can_be_set_changed_and_cleared(client, token):
    headers = bearer(token)
    r = client.patch("/profile", json={"phone": "+1 (713) 555-0100", "preferences": "email only"}, headers=headers)
    assert (r.json()["phone"], r.json()["preferences"]) == ("+1 (713) 555-0100", "email only")
    assert client.patch("/profile", json={"phone": None}, headers=headers).json()["phone"] is None
    got = client.get("/profile", headers=headers).json()
    assert got["phone"] is None and got["preferences"] == "email only" and got["full_name"] == "Alex Nguyen"
    assert client.patch("/profile", json={"preferences": None}, headers=headers).json()["preferences"] is None


@pytest.mark.parametrize(("body", "field", "message"), [
    ({}, "body", "Send at least one field to change."),
    ({"full_name": ""}, "full_name", "This field is required."),
    ({"full_name": "   "}, "full_name", "This field is required."),
    ({"full_name": "x" * 101}, "full_name", "Must be at most 100 characters."),
    ({"full_name": None}, "full_name", "Must be a string."),
    ({"full_name": 5}, "full_name", "Must be a string."),
    ({"phone": "12"}, "phone", "Enter a valid phone number"),
    ({"phone": "x" * 31}, "phone", "Must be at most 30 characters."),
    ({"preferences": "p" * 501}, "preferences", "Must be at most 500 characters."),
    ({"preferences": ""}, "preferences", "This field is required."),
    ({"email": "other@uh.edu"}, "email", "Unknown field."),
    ({"role": "staff"}, "role", "Unknown field."),
])
def test_invalid_profile_updates_are_rejected_and_change_nothing(client, token, body, field, message):
    r = client.patch("/profile", json=body, headers=bearer(token))
    assert r.status_code == 422 and r.json()["error"]["fields"][field].startswith(message)
    assert row_for("alex@uh.edu")[1].full_name == "Alex Nguyen"


def test_one_users_update_never_touches_another_users_profile(client, token):
    client.post("/auth/register", json={**VALID, "email": "bo@uh.edu", "name": "Bo Tran"})
    other = client.post("/auth/login", json={"email": "bo@uh.edu", "password": VALID["password"]}).json()["access_token"]
    client.patch("/profile", json={"full_name": "Changed", "phone": "713-555-0100"}, headers=bearer(token))
    assert client.get("/profile", headers=bearer(other)).json()["full_name"] == "Bo Tran"
    assert client.get("/profile", headers=bearer(other)).json()["phone"] is None


def test_staff_have_a_profile_too(client, staff_headers):
    assert client.get("/profile", headers=staff_headers).json()["full_name"] == "Sam Staff"


def test_an_account_without_a_profile_cannot_log_in_or_authenticate(client, session):
    from app.security import create_access_token
    save_account(session, id="orphan", email="orphan@uh.edu", password_hash=hash_password("Passw0rdOK"))
    session.commit()
    token_for_orphan, _ = create_access_token(User("orphan", "x", "orphan@uh.edu", "h", "student"))
    assert client.get("/auth/me", headers=bearer(token_for_orphan)).status_code == 401
    assert client.post("/auth/login", json={"email": "orphan@uh.edu", "password": "Passw0rdOK"}).status_code == 401


def test_a_missing_profile_is_reported_as_not_found():
    with pytest.raises(ApiError) as error:
        _out(None)
    assert error.value.status_code == 404
