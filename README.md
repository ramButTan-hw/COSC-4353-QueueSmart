# QueueSmart — COSC 4353

A queue management application with a Python/FastAPI backend and an HTML, CSS, and JavaScript frontend. Data is stored in memory and resets when the server restarts.

## Setup

Requires Python 3.11+ and uv.

```sh
cd backend
uv sync --frozen
uv run uvicorn app.main:app --reload --port 8001
```

Open [QueueSmart](http://localhost:8001). API documentation is available at [localhost:8001/docs](http://localhost:8001/docs).

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
