# QueueSmart FastAPI: notifications and history (A3 parts 5 and 6)

This directory is a self-contained FastAPI implementation of **notification triggers** and **user queue history**. It does not own authentication, services, or queue ordering. Its files do not replace the existing Node demo or the team's FastAPI application, so the branches can be merged with minimal file overlap.

## Run with the current A2 interface

From the repository root, with Python 3.11+ and Node.js 22+ available:

```sh
python3 -m venv a3_activity/.venv
a3_activity/.venv/bin/python -m pip install -r a3_activity/requirements-dev.txt
a3_activity/.venv/bin/python -m a3_activity
```

Open `http://127.0.0.1:3000/`. The current `js/backend.js`, `js/store.js`, notifications bell, and history page use this FastAPI instance through their existing `/api` calls. The demo keeps its queue in browser storage and uses the optional `/api/queue-events` bridge to send changes to FastAPI. `X-QueueSmart-User` is **only a demo identity header**; it is not authentication. The default port can be changed with `PORT=3001` before the final command. Data resets when the process restarts. Run one worker because the data is in memory.

The existing `npm start` still launches the earlier Node backend. The FastAPI command above is the preview for this branch; no shared start script or frontend file was changed.

## Mount in the team's FastAPI app

Install the package requirements into the team's Python environment (or add compatible versions to the team's dependency file). Mount the modules during app construction:

```python
from fastapi import FastAPI
from a3_activity import install_activity
from my_team_auth import authenticated_user_id  # dependency returns a string ID

app = FastAPI()
activity = install_activity(app, user_dependency=authenticated_user_id)
```

`user_dependency` is required in the team app. Use the same authenticated user ID that the queue module stores in its participation records. The installer adds only notification and history routes; it does **not** add the A2 `/api/session` or `/api/queue-events` bridge by default, and it does not replace the app's general validation/error handlers. The activity store is also available as `app.state.queuesmart_activity`.

After the team's queue module validates a change, send a batch of events while that change is controlled by the queue service. For example:

```python
activity.apply([
    {
        "type": "joined", "participationId": "visit-123", "userId": "alice",
        "serviceId": 1, "serviceName": "Help Desk", "position": 3, "queueOpen": True,
    }
])
activity.apply([
    {"type": "position", "participationId": "visit-123", "position": 2, "queueOpen": True}
])
activity.apply([{"type": "served", "participationId": "visit-123"}])
```

Supported completion types are `served`, `left`, and `removed`. Send a `position` event for each affected waiting participant after reorder, serve, leave, removal, or reopening; `queueOpen` prevents a near-front alert while a queue is closed. A single `apply()` batch is atomic for activity data: invalid events roll back all history and notifications in that batch. The team queue module should call it as part of its controlled state transition. In-memory state does not span processes; a database can replace the store in A4.

The shared response contract matches the existing browser adapter:

| Route | Result |
| --- | --- |
| `GET /api/notifications` | Current user's notices, newest first |
| `PATCH /api/notifications/{id}/read` | Mark one of the current user's notices read |
| `POST /api/notifications/read-all` | Mark the current user's notices read |
| `DELETE /api/notifications` | Clear the current user's notices |
| `GET /api/history` | Current user's participation records, newest first |
| `GET /api/history?from=YYYY-MM-DD&to=YYYY-MM-DD` | Inclusive UTC join-date filter |

The optional **demo-only** bridge adds `GET /api/session` and `POST /api/queue-events`. History returns `joinedAt`, `completedAt`, and `date` as Unix milliseconds for the current A2 UI; it also returns `outcome` (`Waiting`, `Served`, `Left queue`, or `Removed`).

## Tests

From the repository root:

```sh
COVERAGE_FILE=a3_activity/.coverage a3_activity/.venv/bin/python -m pytest -q -p no:cacheprovider a3_activity/tests --cov=a3_activity --cov-config=a3_activity/.coveragerc --cov-report=term-missing
node --test a3_activity/tests/frontend_bridge.cjs
```

Python tests cover real join, near-front, completion, user isolation, date boundaries, rollback, and invalid input behavior. The Node test runs the unmodified A2 browser modules against a temporary local FastAPI server, including error recovery and reset on server restart. A local loopback port is required for that integration test.

For conflict-free integration, merge this directory as its own contribution first, then wire `install_activity` and `activity.apply()` in the team's app and queue service. The future wiring may need small edits to the team's files; this branch makes no such edits now.
