# QueueSmart — COSC 4353

A2 browser UI plus **A3 modules 5 (Notifications) and 6 (History)**. The new backend uses JavaScript, Node.js's built-in HTTP server, and in-memory collections. This shares the UI's language and requires no installed packages or database.

## Run

Requires Node.js 22 or newer.

```sh
npm start
```

Open [QueueSmart](http://localhost:3000) through the server rather than opening HTML files directly. Use the existing demo login with any valid email and a password of at least six characters. `PORT=3001 npm start` selects a different port.

## Modules implemented

- **Notifications:** the backend creates a user-targeted confirmation on joining and one near-front reminder per visit when the user reaches position 1 or 2 in an open queue. Closed queues defer the reminder until reopening. Reordering and repeated position updates do not duplicate reminders. The existing bell and dashboard fetch these messages, with five-second polling. Read-one, read-all, and clear actions update the backend.
- **History:** each join starts a visit with a service snapshot and server-generated timestamp. Serving, leaving, and removal complete that visit with an outcome and completion time. Users see only their requested identity's records, newest visit first. The history page displays joined/completed times, outcome badges, a visit count, and quick date ranges (All time, Today, Last 7 days, Last 30 days). Custom start/end dates are inclusive; either can be left blank. Apply dates confirms a custom range and Reset filters returns to all visits. Invalid ranges display an error without showing unfiltered results.
- **Validation:** event objects enforce required fields, types, nonblank strings, length limits, positive integer IDs/positions, and valid event names. Invalid batches return JSON errors without partial writes. Repeated joins, overlapping active visits, and updates to completed visits are rejected.

All notification/history data disappears on server restart. A new server session also starts fresh browser demo queues on page reload. No database is used. Existing supplementary A2 messages (staff alerts, queue open/closed, served/removed) still use browser storage.

Authentication, service management, queue ordering, and wait-time estimation remain the existing A2 browser demo. The event hook connects those queue actions to modules 5 and 6; it does not implement modules 1–4. Consequently, queues still synchronize only between tabs of the same browser, not across devices.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/session` | Current in-memory session ID, used to reset the browser demo after restart |
| POST | `/api/queue-events` | Apply a validated batch of participation events atomically |
| GET | `/api/notifications` | List the requested user's notifications |
| PATCH | `/api/notifications/:id/read` | Mark a notification read |
| POST | `/api/notifications/read-all` | Mark the user's notifications read |
| DELETE | `/api/notifications` | Clear the user's notifications without changing history |
| GET | `/api/history?from=2026-10-01&to=2026-10-31` | List visits, optionally filtered by inclusive UTC join-date range |

Notification/history requests use the `X-QueueSmart-User` header, populated from the A2 demo identity. **This header is not authentication** and can be impersonated. Event ingestion is a trusted demo integration hook; module 1 must supply authenticated identity/authorization before deployment. The server binds to the local machine by default.

Queue-event request example (`Content-Type: application/json`):

```json
{
  "events": [
    {
      "type": "joined",
      "participationId": "unique-visit-id",
      "userId": "student@example.com",
      "serviceId": 1,
      "serviceName": "Password Reset",
      "position": 3,
      "queueOpen": true
    }
  ]
}
```

A `position` event requires `participationId`, `position`, and `queueOpen`. A `served`, `left`, or `removed` event requires `participationId`. Each visit ID must be unique; generate a new one when rejoining. Clearing notifications does not reset the once-per-visit reminder flag.

Requests accept 1–1000 events and up to 64 KiB of JSON. `participationId` and `serviceName` allow 100 characters; `userId` allows 254. Numeric values must be positive safe integers. Errors use `{ "error": "message" }`, with 400 for validation, 404 for missing resources, 409 for lifecycle conflicts, 413 for oversized bodies, and 415 for unsupported body content types.

The history page uses local calendar dates for its browser filters; API date filters use UTC calendar dates. Both filter by the join time. History responses include `id`, `userId`, `serviceId`, `serviceName`, `joinedAt`, `completedAt`, and `outcome`; timestamps are Unix milliseconds. `date` is a display compatibility alias for completion time or, while waiting, join time.

## Tests

```sh
npm test
npm run test:coverage
npm run test:strength
```

The tests use Node.js's built-in runner and cover business rules, validation, recipient isolation, batch rollback, real HTTP responses, and the browser adapter/store calling the API. No external test dependencies are required. HTTP integration tests need permission to bind local ports.

Latest verification: **24 tests passed; 98.71% backend line coverage**, exceeding A3's 70–80% target. Run `npm run test:coverage` to regenerate the coverage report.

The tests assert behavior rather than just successful execution: exact server timestamps, all participation outcomes, recipient isolation, rollback after a partially applied batch, duplicate-reminder prevention, valid field-length boundaries, and date filtering at midnight. Date helper tests cover year changes and 23/25-hour daylight-saving days in America/Chicago.

`npm run test:strength` temporarily introduces 12 plausible backend regressions into isolated copies of the source (such as mixed recipients, incorrect outcomes, missing rollback, and wrong date boundaries). All 12 are caught by the business-rule unit tests. The check leaves the real application files untouched. This is a targeted regression check, not a claim that every possible bug is covered.

Manual check: log in as a student, join an open queue, inspect the bell, and visit History. In another tab, log in as staff and serve/remove the student; the student's history updates within five seconds. Leaving a queue records “Left queue.”
