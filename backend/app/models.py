"""Domain objects shared by every module."""
from dataclasses import dataclass


@dataclass
class User:
    id: str
    name: str
    email: str
    password_hash: str
    role: str


@dataclass
class Service:
    id: int
    name: str
    description: str
    duration: int
    priority: str
    open: bool = False


@dataclass
class QueueEntry:
    id: int
    service_id: int
    user_id: str
    priority: str
    joined_at: float
    order: float | None = None  # Staff ordering within a priority tier; arrival time is retained.
