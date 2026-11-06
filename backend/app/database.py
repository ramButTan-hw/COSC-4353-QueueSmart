"""Database setup shared by every module: engine, sessions, base class for tables, startup hooks.

How to use it (see also README "Database"):

  Tables    Put each module's tables in app/tables/<module>.py as subclasses of `Base`, and import that
            file in app/tables/__init__.py. Give every CheckConstraint a name (the naming convention
            below needs it). SQLite ignores VARCHAR(n), so enforce length limits with CheckConstraints.
  Routers   Take `session: Session = Depends(get_session)`. Call `commit(session)` yourself at the end of
            the endpoint so a failed commit becomes a proper API error. Anything not committed is rolled
            back when the request ends or raises.
  Seeding   `@register_seeder` a function(session) that inserts demo rows if they are missing. It runs at
            startup after the tables exist.
  Tests     tests/conftest.py gives every test an empty in-memory database (reset_database()).

The connection comes from config.DATABASE_URL (env var DATABASE_URL). Always use `database.engine` and
`database.SessionLocal` through the module, never `from app.database import engine`, because
configure() swaps them.
"""
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.errors import ApiError

# Stable names for keys and constraints, so the generated SQL (and error messages) are predictable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def new_metadata() -> MetaData:
    return MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = new_metadata()


def engine_options(url: str) -> dict:
    """Connection settings that depend on the kind of database."""
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        # FastAPI runs endpoints in worker threads, so the connection must be usable from any thread.
        options: dict = {"connect_args": {"check_same_thread": False}}
        if parsed.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool  # an in-memory database only exists on one connection
        return options
    return {"pool_pre_ping": True}


def make_engine(url: str | None = None) -> Engine:
    engine = create_engine(url or config.DATABASE_URL, **engine_options(url or config.DATABASE_URL))
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            # SQLite does not enforce foreign keys unless this is switched on for every connection.
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
active_session: ContextVar[Session | None] = ContextVar("active_session", default=None)


@contextmanager
def session_scope(*, write=False):
    """Reuse the event transaction for nested helpers; only its owner may commit."""
    current = active_session.get()
    if current is not None:
        yield current
        return
    with SessionLocal() as session:
        token = active_session.set(session)
        try:
            yield session
            if write:
                commit(session)
        finally:
            active_session.reset(token)



def configure(url: str | None = None) -> Engine:
    """Point the app at a different database (used by tests and scripts)."""
    global engine
    engine.dispose()
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
    return engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request. Commit inside the endpoint with commit()."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def commit(session: Session, conflict_message: str = "That already exists.", conflict_fields: dict | None = None) -> None:
    """Commit, turning a violated unique/foreign-key/check constraint into a 409 instead of a crash."""
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApiError(409, "conflict", conflict_message, fields=conflict_fields) from error


SEEDERS: list[Callable[[Session], None]] = []


def register_seeder(function: Callable[[Session], None]) -> Callable[[Session], None]:
    """Decorator: run function(session) at startup. It must be safe to run on every start."""
    SEEDERS.append(function)
    return function


def _load_tables() -> None:
    import app.tables  # noqa: F401  (importing it registers every table on Base.metadata)


def init_db() -> None:
    """Create any missing tables, then run the seeders. Called once at application startup."""
    _load_tables()
    Base.metadata.create_all(engine)
    from app.queue_database import upgrade_queue_columns
    upgrade_queue_columns()
    with SessionLocal() as session:
        for seed in SEEDERS:
            seed(session)
        session.commit()


def reset_database() -> None:
    """Empty every table (tests): drop and recreate them all."""
    _load_tables()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
