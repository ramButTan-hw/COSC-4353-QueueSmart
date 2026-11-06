# A4 Part 6 Notification and History

Repository: https://github.com/ramButTan-hw/COSC-4353-QueueSmart

The PDF handoff is at `output/pdf/QueueSmart-A4-Part6.pdf`.

This handoff covers part 6 only. Merge it with the other members' schema and contribution
sections before submitting the group's single Word or PDF file to Canvas.

## Implementation

- Added `participation_history` and `notification` SQLAlchemy tables, registered with the
  existing database startup. SQLite remains the default database; no new server is needed.
- Added required fields, unique public IDs, user foreign keys, a notification-to-history
  foreign key, length checks, valid status checks, and timestamp/completion checks.
- Persisted join, position, queue open/close, completion, staff, and interruption alerts.
- Persisted notification read/read-all/clear actions and kept history when notifications
  are cleared. Database `sent`/`viewed` maps to the existing API `read` boolean.
- Preserved authenticated per-user access, newest-first ordering, UTC history date filters,
  and the existing frontend response shapes.
- Used one transaction for history changes and all associated notifications, including
  nested event batches. A failed flush or commit restores runtime queue state and rolls
  back database changes. Only changed SQL rows are written.

`schema.sql` is generated from the actual SQLAlchemy models for SQLite. Create the team's
`user_credentials` table first. The two `sequence` columns are primary keys; public `id`
columns are unique. Recipient/user foreign keys reference `user_credentials.id` and
notification participation references `participation_history.id`. Account deletion cascades
to related activity. Service ID and service name are historical snapshots, intentionally
not cascading service foreign keys, so a deleted service's completed visits remain visible.
Timestamps are UTC Unix milliseconds.

## Integration limits for the team

Service and queue runtime state still lives in memory. At startup, a waiting visit without
a live queue entry becomes `Removed` and receives an interruption notice. Completed visits
and prior notifications remain saved, and the user can join again. Participation IDs contain
a runtime UUID so reset queue counters do not overwrite previous history.

Use one backend worker until queue persistence is integrated. The activity unit of work
loads the activity records to reuse the existing business rules; SQL filtering/pagination
should replace this approach if the dataset becomes large. The queue persistence owner
should supply stable participation IDs and restore live queue entries before recovery runs,
or replace recovery when queues become durable. No Queue/QueueEntry table migration is
claimed by this contribution.

## Validation evidence

Verified on November 5, 2026 with Python 3.14 and the existing frozen `backend/uv.lock`:

- Backend: **371 passed**; statement coverage **90.24%** (1,063 / 1,178 statements).
- New activity persistence module and activity table module: **100% statement coverage**.
- Frontend/API integration: **15 passed**, including an actual server process restart using
  a temporary SQLite file.
- Added 26 database-focused cases covering restart durability, status writes, recipient
  isolation, clearing, rollback, constraints, cascading deletion, and restart recovery.
- Existing tests continue to cover date boundaries, reminders, queue events and API access.

See `coverage-summary.txt` for the report summary. The HTML report is generated locally at
`backend/htmlcov/index.html`; it is not committed. Coverage includes the existing unused
`Wait-Time Estimation Logic.py` file rather than hiding it from the denominator.

Install dependencies with `cd backend` and `uv sync --frozen`, then return to the
repository root to run:

```sh
npm test
npm run test:coverage
```

For an explicit 80% coverage gate, run from `backend`:

```sh
uv run pytest -q --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=80
```

The coverage result above is from the last successful full run. A later redundant rerun
was not executed because automatic approval review reached its usage limit. After that
successful run, only documentation and removal of an unnecessary test wrapper changed;
application behavior did not change.

## Contribution text for the group table

**Group member:** replace with your full name.

**Contribution:** Implemented A4 part 6 database persistence for notifications and
participation history. Added SQLAlchemy models with keys and validation constraints,
transactional queue-event integration, durable read/clear actions, restart recovery,
database unit tests and a real process restart integration test. Prepared the SQL schema
and coverage summary for the group submission.

**Discussion notes:** Reused the team's SQLAlchemy/SQLite foundation and credentials foreign
keys while preserving the A3 API and UI contracts. Coordinated interface needed with the
queue persistence module: stable participation IDs and startup restoration before recovery.
Service names remain historical snapshots after service deletion.

This discussion text describes the integration design; replace it with actual team meeting
notes if the submission requires a record of discussions that occurred.

## Before the group submits

Review these changes, commit and push this branch under your own configured Git identity,
and open a pull request for the team to merge. The work in this handoff has not been committed
or pushed automatically. Add all four members' real names and verified contributions, include
the remaining tables' schema, and submit one combined Word/PDF document to Canvas. Do not
upload source code to Canvas.
