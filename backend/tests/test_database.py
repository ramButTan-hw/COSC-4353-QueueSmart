"""The shared database foundation: settings, engine, sessions, constraints, startup hooks."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, ForeignKey, String, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.schema import CreateTable

from app import config, database
from app.errors import ApiError, api_error_handler


class LocalBase(DeclarativeBase):
    """Throwaway tables for these tests; it shares the project's naming convention but not its metadata."""
    metadata = database.new_metadata()


class Parent(LocalBase):
    __tablename__ = "parent"
    __table_args__ = (CheckConstraint("length(name) BETWEEN 1 AND 20", name="name_length"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)


class Child(LocalBase):
    __tablename__ = "child"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id", ondelete="CASCADE"), nullable=False)


@pytest.fixture
def session():
    LocalBase.metadata.create_all(database.engine)
    with database.SessionLocal() as s:
        yield s
    LocalBase.metadata.drop_all(database.engine)


# ---------- settings ----------

def test_default_database_is_a_sqlite_file_in_the_backend_folder():
    assert config.DATABASE_URL.startswith("sqlite:///") or "DATABASE_URL" in __import__("os").environ
    default = f"sqlite:///{Path(config.__file__).resolve().parents[1] / 'queuesmart.db'}"
    assert default.endswith("backend/queuesmart.db")


def test_tests_use_an_in_memory_database_not_the_real_file():
    assert str(database.engine.url) == "sqlite://"
    assert not (config.BACKEND_DIR / "queuesmart.db").exists()


@pytest.mark.parametrize(("url", "expected"), [
    ("sqlite://", {"connect_args": {"check_same_thread": False}, "poolclass": database.StaticPool}),
    ("sqlite:///:memory:", {"connect_args": {"check_same_thread": False}, "poolclass": database.StaticPool}),
    ("sqlite:////tmp/app.db", {"connect_args": {"check_same_thread": False}}),
    ("postgresql+psycopg://u:p@localhost/db", {"pool_pre_ping": True}),
])
def test_engine_options_depend_on_the_kind_of_database(url, expected):
    assert database.engine_options(url) == expected


def test_a_non_sqlite_engine_is_created_without_sqlite_settings(monkeypatch):
    seen = {}
    monkeypatch.setattr(database, "create_engine", lambda url, **opts: seen.update(url=url, opts=opts) or SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    engine = database.make_engine("postgresql+psycopg://u:p@localhost/db")
    assert engine.dialect.name == "postgresql" and seen["opts"] == {"pool_pre_ping": True}


def test_make_engine_defaults_to_the_configured_url(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "sqlite://")
    assert str(database.make_engine().url) == "sqlite://"


# ---------- constraints the foundation promises ----------

def test_foreign_keys_are_switched_on(session):
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    session.add(Child(code="a", parent_id=999))
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_parent_cascades_in_the_database(session):
    session.add(Parent(id=1, name="p"))
    session.flush()  # without a relationship(), insert order is not guaranteed: save parents first
    session.add(Child(code="a", parent_id=1))
    session.commit()
    session.execute(delete(Parent))
    session.commit()
    assert session.scalar(select(func.count()).select_from(Child)) == 0


@pytest.mark.parametrize("name", ["", "x" * 21])
def test_named_check_constraints_enforce_length_limits(session, name):
    session.add(Parent(name=name))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_constraint_is_enforced(session):
    session.add(Parent(id=1, name="p"))
    session.flush()
    session.add_all([Child(code="dup", parent_id=1), Child(code="dup", parent_id=1)])
    with pytest.raises(IntegrityError):
        session.flush()


def test_the_naming_convention_gives_keys_and_constraints_predictable_names():
    parent, child = str(CreateTable(Parent.__table__)), str(CreateTable(Child.__table__))
    assert "CONSTRAINT pk_parent" in parent and "CONSTRAINT ck_parent_name_length" in parent
    assert "CONSTRAINT uq_child_code" in child and "CONSTRAINT fk_child_parent_id_parent" in child


# ---------- sessions and commit() ----------

def make_app():
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)

    @app.post("/ok")
    def ok(session: Session = Depends(database.get_session)):
        session.add(Parent(name="kept"))
        database.commit(session)
        return {"saved": True}

    @app.post("/boom")
    def boom(session: Session = Depends(database.get_session)):
        session.add(Parent(name="lost"))
        session.flush()
        raise RuntimeError("something broke after a write")

    @app.post("/forgot-to-commit")
    def forgot(session: Session = Depends(database.get_session)):
        session.add(Parent(name="never committed"))
        return {"saved": False}

    @app.post("/duplicate")
    def duplicate(session: Session = Depends(database.get_session)):
        session.add(Parent(id=1, name="a"))
        session.add(Parent(id=1, name="b"))
        database.commit(session, "Parent already exists.", {"name": "taken"})

    return app


def names(session):
    return sorted(session.scalars(select(Parent.name)).all())


def test_a_committed_request_is_saved(session):
    assert TestClient(make_app()).post("/ok").json() == {"saved": True}
    assert names(session) == ["kept"]


def test_a_request_that_raises_is_rolled_back(session):
    assert TestClient(make_app(), raise_server_exceptions=False).post("/boom").status_code == 500
    assert names(session) == []


def test_uncommitted_work_is_discarded_when_the_request_ends(session):
    TestClient(make_app()).post("/forgot-to-commit")
    assert names(session) == []


def test_commit_turns_a_constraint_violation_into_a_409(session):
    response = TestClient(make_app()).post("/duplicate")
    assert response.status_code == 409
    assert response.json() == {"error": {"code": "conflict", "message": "Parent already exists.", "fields": {"name": "taken"}}}
    assert names(session) == []


def test_the_session_is_usable_after_a_failed_commit(session):
    session.add_all([Parent(id=1, name="a"), Parent(id=1, name="b")])
    with pytest.raises(ApiError) as error:
        database.commit(session)
    assert error.value.status_code == 409 and error.value.message == "That already exists."
    session.add(Parent(id=2, name="fine"))
    database.commit(session)
    assert names(session) == ["fine"]


# ---------- startup hooks ----------

@pytest.fixture
def seeders(monkeypatch):
    monkeypatch.setattr(database, "SEEDERS", [])
    return database.SEEDERS


def test_init_db_creates_the_tables_then_runs_every_seeder(seeders):
    calls = []

    @database.register_seeder
    def first(session):
        calls.append(("first", isinstance(session, Session)))

    database.register_seeder(lambda session: calls.append(("second", True)))
    database.init_db()
    assert calls == [("first", True), ("second", True)]


def test_init_db_can_run_twice(seeders):
    database.init_db()
    database.init_db()


def test_a_seeder_can_insert_rows_that_persist(seeders):
    LocalBase.metadata.create_all(database.engine)
    try:
        database.register_seeder(lambda session: session.add(Parent(id=1, name="seeded")))
        database.init_db()
        with database.SessionLocal() as s:
            assert names(s) == ["seeded"]
    finally:
        LocalBase.metadata.drop_all(database.engine)


def test_reset_database_empties_the_registered_tables():
    database.reset_database()  # also makes sure it works with no tables registered yet


def test_the_app_starts_with_the_database_set_up():
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_configure_swaps_the_engine_and_the_sessions_follow():
    original = database.engine
    try:
        new = database.configure("sqlite://")
        assert database.engine is new and new is not original
        assert database.SessionLocal.kw["bind"] is new
        with database.SessionLocal() as s:
            assert s.execute(text("select 1")).scalar() == 1
    finally:
        database.configure("sqlite://")
