from datetime import datetime, timezone
from typing import List
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="QueueSmart - Wait-Time Estimation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Models ----------

class Service(BaseModel):
    id: str
    name: str
    expected_duration_minutes: int = Field(..., gt=0)


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=1)
    expected_duration_minutes: int = Field(..., gt=0)


class QueueEntry(BaseModel):
    id: str
    service_id: str
    user_email: str
    position: int
    estimated_wait_minutes: int
    joined_at: datetime


class JoinRequest(BaseModel):
    service_id: str
    user_email: str = Field(..., min_length=3)


class WaitEstimateRequest(BaseModel):
    position: int = Field(..., ge=1, description="1-based position in queue")
    expected_duration_minutes: int = Field(..., gt=0)


class WaitEstimateResponse(BaseModel):
    position: int
    expected_duration_minutes: int
    estimated_wait_minutes: int
    formula: str


# ---------- In-memory data ----------

services_db: dict[str, Service] = {}
queue_db: List[QueueEntry] = []  # append order == join order

_seed_id = str(uuid.uuid4())
services_db[_seed_id] = Service(
    id=_seed_id, name="IT Help Desk", expected_duration_minutes=10
)


# ---------- Core rule-based wait-time estimation ----------

def estimate_wait_minutes(position: int, expected_duration_minutes: int) -> int:
    """
    Rule: wait time = position x expected duration per person.
    Position is 1-based (1 = next in line). Returns 0 for position <= 0.
    """
    if position <= 0:
        return 0
    return position * expected_duration_minutes


def service_entries(service_id: str) -> List[QueueEntry]:
    return [e for e in queue_db if e.service_id == service_id]


def recalculate_queue(service_id: str) -> None:
    """Recompute positions and wait times for everyone in a service's queue."""
    service = services_db.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    for idx, entry in enumerate(service_entries(service_id), start=1):
        entry.position = idx
        entry.estimated_wait_minutes = estimate_wait_minutes(
            idx, service.expected_duration_minutes
        )


# ---------- Endpoints ----------

@app.get("/")
def root():
    return {"status": "ok", "message": "QueueSmart wait-time estimation API"}


@app.get("/services", response_model=List[Service])
def list_services():
    return list(services_db.values())


@app.post("/services", response_model=Service, status_code=201)
def create_service(payload: ServiceCreate):
    service = Service(id=str(uuid.uuid4()), **payload.model_dump())
    services_db[service.id] = service
    return service


@app.post("/estimate", response_model=WaitEstimateResponse)
def get_wait_estimate(payload: WaitEstimateRequest):
    """Example: position=3, duration=10 -> wait=30 minutes."""
    wait = estimate_wait_minutes(payload.position, payload.expected_duration_minutes)
    return WaitEstimateResponse(
        position=payload.position,
        expected_duration_minutes=payload.expected_duration_minutes,
        estimated_wait_minutes=wait,
        formula=f"{payload.position} × {payload.expected_duration_minutes} = {wait} minutes",
    )


@app.post("/queue/join", response_model=QueueEntry, status_code=201)
def join_queue(payload: JoinRequest):
    """Join a queue; position and wait time are computed automatically."""
    service = services_db.get(payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    email = payload.user_email.strip().lower()
    if any(e.user_email == email for e in service_entries(service.id)):
        raise HTTPException(status_code=409, detail="User already in this queue")

    entry = QueueEntry(
        id=str(uuid.uuid4()),
        service_id=service.id,
        user_email=email,
        position=0,
        estimated_wait_minutes=0,
        joined_at=datetime.now(timezone.utc),
    )
    queue_db.append(entry)
    recalculate_queue(service.id)
    return entry


@app.get("/queue/{service_id}", response_model=List[QueueEntry])
def get_queue(service_id: str):
    """View the queue with positions and estimated wait times."""
    if service_id not in services_db:
        raise HTTPException(status_code=404, detail="Service not found")
    return service_entries(service_id)


@app.get("/queue/status/{service_id}/{user_email}", response_model=QueueEntry)
def get_status(service_id: str, user_email: str):
    """A user's current position and estimated wait time."""
    email = user_email.strip().lower()
    for e in queue_db:
        if e.service_id == service_id and e.user_email == email:
            return e
    raise HTTPException(status_code=404, detail="User not in this queue")


@app.post("/queue/{service_id}/serve-next", response_model=QueueEntry)
def serve_next(service_id: str):
    """Serve the next person, then recalculate everyone behind them."""
    if service_id not in services_db:
        raise HTTPException(status_code=404, detail="Service not found")

    entries = service_entries(service_id)
    if not entries:
        raise HTTPException(status_code=404, detail="Queue is empty")

    served = entries[0]
    queue_db.remove(served)
    recalculate_queue(service_id)
    return served


@app.delete("/queue/{service_id}/{user_email}", status_code=204)
def leave_queue(service_id: str, user_email: str):
    """A user leaves the queue; everyone behind moves up."""
    if service_id not in services_db:
        raise HTTPException(status_code=404, detail="Service not found")

    email = user_email.strip().lower()
    for e in queue_db:
        if e.service_id == service_id and e.user_email == email:
            queue_db.remove(e)
            recalculate_queue(service_id)
            return
    raise HTTPException(status_code=404, detail="User not in this queue")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
