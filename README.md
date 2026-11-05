# QueueSmart — COSC 4353

A queue management application with a Python/FastAPI backend and an HTML, CSS, and JavaScript frontend. The backend talks to a database through SQLAlchemy (SQLite by default). User accounts and profiles are saved in the database and survive restarts; services, queues, notifications and history are still kept in memory until their tables are added.

## Setup

Requires Python 3.11+ and uv.

```sh
cd backend
uv sync --frozen
uv run uvicorn app.main:app --reload --port 8001
```

Open [QueueSmart](http://localhost:8001). API documentation is available at [localhost:8001/docs](http://localhost:8001/docs).

## Database

The database is set up in `backend/app/database.py`. By default it is a SQLite file, `backend/queuesmart.db`, which is created on first start and ignored by git. There is nothing to install and no Docker needed. Delete the file to start from an empty database. Tables are created at startup but not migrated, so if you pull a change that alters a table and the app complains about missing columns, delete the file and let it rebuild.

To use a different SQLite file, set `DATABASE_URL` before starting the server, for example `DATABASE_URL=sqlite:///other.db`.

Tables inside the db: user_credentials (columns: id, email, role, password_hash) and user_profile (columns: user_id, email, full_name, phone, prferences, updated at)

The tables have 2 seeded accounts: student and staff

Adding a table:

1. Create `backend/app/tables/<module>.py` with your tables as subclasses of `Base`, and import it in `backend/app/tables/__init__.py`. Give every `CheckConstraint` a `name=`. SQLite ignores `VARCHAR(n)` lengths, so enforce length limits with a `CheckConstraint` such as `length(name) BETWEEN 1 AND 100`.
2. In a router, take `session: Session = Depends(get_session)` and call `commit(session)` yourself at the end. Work that is not committed is rolled back, and a violated unique or foreign-key constraint becomes a 409.
3. Demo data goes in a function decorated with `@register_seeder`. It runs at startup and must be safe to run every time.
4. Tests get an empty in-memory database automatically (`tests/conftest.py`), so they never touch the real file.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Student | student@uh.edu | Password1 |
| Staff | admin@uh.edu | Password1 |

## Tests

With Node.js 22+ installed, run from the repository root after setup:

```sh
npm test
npm run test:coverage
```
