# QueueSmart — COSC 4353

QueueSmart uses one **Python/FastAPI backend** with in-memory data for A3. The authentication module is integrated with modules **5 (Notifications)** and **6 (History)**. The A2 interface calls these APIs with the login token. No database is required.

## Run

Requires Python 3.11+ and `uv`. From the repository root:

```sh
cd backend
uv sync --frozen
uv run uvicorn app.main:app --reload --port 8001
```

Open [QueueSmart](http://localhost:8001) and [API documentation](http://localhost:8001/docs). FastAPI serves both the UI and API, so a separate frontend server is unnecessary. Run one worker because the data is in memory. Restarting the backend clears activity and registered accounts; the demo accounts are recreated.

| Account | Email | Password |
| --- | --- | --- |
| Student | `student@uh.edu` | `Password1` |
| Staff | `admin@uh.edu` | `Password1` |

The server assigns the role after login. Public registration through `/auth/register` creates students only. Login tokens and the current user are stored per tab, so separate student and staff tabs can be used for testing. Log out clears both. The default signing key is for local development; the existing authentication configuration supports `JWT_SECRET` and `JWT_EXPIRES_MINUTES`.

After dependency setup, `npm start` from the repository root also starts FastAPI on port 8001. `PORT=8002 npm start` selects another port. Node.js 22+ is used only for these command shortcuts and JavaScript tests; there is no Node backend.

## Modules 5 and 6

- **Notifications:** joining creates a personal confirmation. Reaching position 1 or 2 in an open queue creates one near-front reminder per visit. Paused queues defer it until reopening; reordering and clearing notifications do not cause duplicates. Read-one, read-all, and clear actions affect only the authenticated user. The bell and dashboard refresh from the API.
- **History:** each join records the service name and server timestamp. Serving, leaving, or removal records an outcome and completion timestamp. The UI displays joined/completed dates and times, outcome badges, visit counts, quick ranges, and inclusive custom date filters. Invalid ranges display an error.
- **Validation:** required fields, strict types, maximum text lengths, positive integer IDs/positions, valid event types, and batch size are checked. Duplicate joins, overlapping active visits, and updates to completed visits are rejected. Failed event batches roll back history, notification messages, and reminder state together.

Notifications and history use the teammate's `get_current_user` dependency, shared `db` store, and structured error responses. Identity headers or query parameters cannot select another user's data.

**Remaining A2 scope:** services, queue controls, and estimated wait times still use the browser demo until modules 2–4 are implemented by the team. Queue state is shared between tabs of the same browser, not across devices. Supplementary A2 messages (staff join/leave alerts, served/removed, queue open/closed) remain in browser storage. The required join and near-front notifications come from FastAPI.

## API

All activity endpoints require `Authorization: Bearer <access_token>` from `POST /auth/login`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/notifications` | Current user's notices, newest first |
| PATCH | `/api/notifications/{id}/read` | Mark one of the current user's notices read |
| POST | `/api/notifications/read-all` | Mark all of the current user's notices read |
| DELETE | `/api/notifications` | Clear notices without changing history |
| GET | `/api/history` | Current user's visits, newest first |
| GET | `/api/history?from=2026-10-01&to=2026-10-31` | Inclusive UTC join-date filter |
| GET | `/api/session` | In-memory session ID used to reset the browser demo queue |
| POST | `/api/queue-events` | Temporary authenticated bridge from the A2 browser queue |

History timestamps (`joinedAt`, `completedAt`, and `date`) are Unix milliseconds. `date` is a compatibility alias for completion time or, while waiting, join time. Outcomes are `Waiting`, `Served`, `Left queue`, and `Removed`. The history page filters by local calendar dates; optional API date filters use UTC. Both filter by join time.

Errors use the shared shape `{ "error": { "code": "...", "message": "...", "fields": { ... } } }`. Field details are included for request validation. Statuses include 401 for missing/invalid authentication, 403 for disallowed actions, 404 for missing resources, 409 for lifecycle conflicts, and 422 for invalid input.

## Integration with the team's queue module

Implementation is in `backend/app/activity/` and the notification/history routers. The only shared backend wiring is router registration in `app/main.py` and `self.activity = Activity()` in the shared store. The teammate's auth logic and locked dependencies are unchanged.

Once the team implements queue operations in Python, call the shared activity service as part of each validated queue change:

```python
from app.store import db

# IDs must match the authenticated user and the queue module's service/visit IDs.
db.activity.apply([
    {
        "type": "joined", "participationId": "unique-visit-id", "userId": student.id,
        "serviceId": service.id, "serviceName": service.name,
        "position": 3, "queueOpen": True,
    }
])
```

For position changes, send `type: "position"`, `participationId`, `position`, and `queueOpen`. For completion, send `type: "served"`, `"left"`, or `"removed"`, plus `participationId`. Batch a completion and affected users' new positions together. Use a new participation ID when someone rejoins. Clearing notifications preserves the reminder flag on the visit.

`apply()` validates the entire batch and rolls back activity changes on failure. Call it inside the queue service's controlled state transition; it does not roll back the queue module's own collections. Batches allow 1–1000 events. Participation IDs and service names allow 1–100 characters, user IDs 1–254, and numeric IDs/positions must be positive JavaScript-safe integers.

The temporary bridge is isolated in `app/routers/activity_demo.py`. Students can submit only one own join or leave; the bridge derives positions and other users' reminders after a leave. Staff can submit completion and position batches. Service names and open/closed state still come from the browser demo because there is no backend service module yet. When the real queue API is connected, remove this bridge router and route frontend queue actions through that API. The notification and history read APIs can stay as they are.

## Tests

After `uv sync --frozen`, from the repository root:

```sh
npm test
npm run test:coverage
npm run test:strength
```

Or run the Python suite directly from `backend/`:

```sh
uv run pytest --cov=app --cov-report=term-missing --cov-report=html
uv run python check_test_strength.py
```

Verification: **124 Python tests and 8 JavaScript tests pass**, with **100% backend statement coverage**. The coverage report excludes tests and includes the existing auth module. The JavaScript suite exercises date boundaries and the actual browser adapter/store against a local FastAPI server using real registration and login tokens, including session expiry handling. Those integration tests need permission to bind loopback ports.

Tests check exact timestamps and outcomes, per-user access, forbidden student actions, rollback after partial processing, one reminder per visit, field-length boundaries, and inclusive midnight filters. Date helper tests include year changes and 23/25-hour daylight-saving days in America/Chicago.

The strength check introduces 12 deliberate regressions into temporary copies, such as wrong recipients, duplicate reminders, incorrect outcomes, missing rollback, and wrong date boundaries. All 12 are caught by the Python business-rule tests. This checks specific regressions, not every possible bug.

Manual check: log in as the demo student, join an open queue, inspect the bell, and open History. In another tab, log in as demo staff and serve/remove the student. History refreshes within five seconds. Leaving a queue records `Left queue`. Clear the notifications and confirm the visit remains in History.
