"""Domain objects shared by every module."""
from dataclasses import dataclass


@dataclass
class User:
    id: str
    name: str
    email: str  # always stored lowercase
    password_hash: str
    role: str  # 'student' or 'staff'


@dataclass
class Service:
    id: int
    name: str
    description: str
    duration: int  # expected minutes per student
    priority: str  # 'low', 'medium' or 'high'
    open: bool = False  # whether the queue accepts new students (toggled by the queue module)
