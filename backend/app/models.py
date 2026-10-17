"""Domain objects shared by every module."""
from dataclasses import dataclass


@dataclass
class User:
    id: str
    name: str
    email: str  # always stored lowercase
    password_hash: str
    role: str  # 'student' or 'staff'
