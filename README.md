# QueueSmart — COSC 4353

QueueSmart uses one **Python/FastAPI backend** with in-memory data for A3. The team’s authentication, service, and queue modules are integrated with modules **5 (Notifications)** and **6 (History)**. The A2 interface calls these APIs with the login token. No database is required.

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
- **Validation:** required fields, strict types, maximum text lengths, positive integer IDs/positions, valid event types, and batch size are checked. Duplicate joins, overlapping active visits, and updates to completed visits are rejected. Failed queue operations roll back queue entries, service state, history, notification messages, and reminder state together.

Notifications and history use the teammate's `get_current_user` dependency, shared `db` store, and structured error responses. Identity headers or query parameters cannot select another user's data.

The UI reads services and queue positions from FastAPI and refreshes every five seconds. Student queue summaries expose counts and the student’s own position; staff can see the full queue. Estimated waits use the actual position and service duration. Required student notifications, including served/removed messages, come from the backend. Optional staff join/leave alerts remain local to the browser.

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
| GET | `/services` | List services from the shared store |
| GET | `/queues` | Queue counts and entries visible to the signed-in user |
| POST | `/queues/{id}/join` | Join and create history/notifications |
| DELETE | `/queues/{id}/leave` | Leave and complete the visit |
| POST | `/queues/{id}/serve-next` | Staff serves one student |
| POST | `/queues/{id}/open` or `/close` | Staff changes queue availability |
| DELETE | `/queues/{id}/members/{user_id}` | Staff removes a student |
| POST | `/queues/{id}/move` | Staff reorders within a priority level |

History timestamps (`joinedAt`, `completedAt`, and `date`) are Unix milliseconds. `date` is a compatibility alias for completion time or, while waiting, join time. Outcomes are `Waiting`, `Served`, `Left queue`, and `Removed`. The history page filters by local calendar dates; optional API date filters use UTC. Both filter by join time.

Errors use the shared shape `{ "error": { "code": "...", "message": "...", "fields": { ... } } }`. Field details are included for request validation. Statuses include 401 for missing/invalid authentication, 403 for disallowed actions, 404 for missing resources, 409 for lifecycle conflicts, and 422 for invalid input.

## Integration with the team's queue module

Modules 5 and 6 live in `backend/app/activity/` and the notification/history routers. `backend/app/queue_activity.py` connects them to the team's existing queue routes. Queue joins, departures, serving, reordering, reopening, and service deletion update activity inside the same locked, reversible in-memory operation. The team's authentication logic, service management, original queue endpoints, priority ordering, and locked dependencies remain in place.

The frontend sends queue actions through `js/api.js` to `/queues`; `js/store.js` keeps only a read cache. The temporary `/api/queue-events` and `/api/session` demo routes have been removed. Browsers can no longer invent visits independently of the real queue. A new queue entry ID gives each rejoin a distinct history record, and manual moves preserve the original arrival timestamp.

Activity events are internal Python data, validated by `Activity.apply()`. Batches allow 1–1000 events; the queue integration splits larger updates within the surrounding transaction. Participation IDs and service names allow 1–100 characters, user IDs 1–254, and numeric IDs/positions must be positive JavaScript-safe integers.

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

Verification: **216 Python tests and 12 JavaScript tests pass**, with **86% backend statement coverage**. Modules 5 and 6 and their queue integration have 100% statement coverage. Overall coverage includes the team’s standalone wait-time prototype, which is not wired into the main FastAPI app or exercised by this suite. The JavaScript suite exercises date boundaries and the actual browser adapter/store against a local FastAPI server using real registration and login tokens, including session expiry handling and independent browser storage. Page regression tests also check JavaScript syntax, the actual login page’s scripts, session initialization, and one admin action per click. Those integration tests need permission to bind loopback ports.

Tests check exact timestamps and outcomes, per-user access, forbidden student actions, rollback after partial processing, one reminder per visit, field-length boundaries, and inclusive midnight filters. Date helper tests include year changes and 23/25-hour daylight-saving days in America/Chicago.

The strength check introduces 12 deliberate regressions into temporary copies, such as wrong recipients, duplicate reminders, incorrect outcomes, missing rollback, and wrong date boundaries. All 12 are caught by the Python business-rule tests. This checks specific regressions, not every possible bug.

Manual check: log in as the demo student, join an open queue, inspect the bell, and open History. In another tab, log in as demo staff and serve/remove the student. History refreshes within five seconds. Leaving a queue records `Left queue`. Clear the notifications and confirm the visit remains in History.
