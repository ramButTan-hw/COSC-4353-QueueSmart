"""In-memory data store shared by every module (no database in A3).

Other modules (services, queues, history, notifications) should add their own collections
here so the whole back end reads and writes the same objects. Everything resets when the
server restarts.
"""

from app import config
from app.activity import Activity
from app.models import User, Service, QueueEntry
from app.security import hash_password


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class Store:
    def __init__(self):
        # Callbacks run when a service is deleted, as hook(service).
        # The queue module can register one to clean up queue entries.
        # Hooks are not cleared by reset().
        self.service_deleted_hooks: list = []
        self.reset()

    def reset(self):
        # --- users ---
        self.users: dict[str, User] = {}
        self._email_index: dict[str, str] = {}
        self.activity = Activity()

        # --- services ---
        self.services: dict[int, Service] = {}
        self._next_service_id = 1

        # --- queues ---
        self.queues: dict[int, list[QueueEntry]] = {}
        self._next_queue_entry_id = 1

    # --- users ---

    def add_user(self, user: User) -> User:
        self.users[user.id] = user
        self._email_index[user.email] = user.id
        return user

    def get_user(self, user_id: str):
        return self.users.get(user_id)

    def get_user_by_email(self, email: str):
        user_id = self._email_index.get(email.strip().lower())
        return self.users.get(user_id) if user_id else None

    # --- services ---

    def add_service(
        self,
        name: str,
        description: str,
        duration: int,
        priority: str,
        open: bool = False,
    ) -> Service:
        service = Service(
            self._next_service_id,
            name,
            description,
            duration,
            priority,
            open,
        )

        self._next_service_id += 1
        self.services[service.id] = service

        return service

    def get_service(self, service_id: int):
        return self.services.get(service_id)

    def list_services(self) -> list[Service]:
        return [
            self.services[i]
            for i in sorted(self.services)
        ]

    def get_service_by_name(self, name: str):
        key = name.strip().lower()

        return next(
            (
                service
                for service in self.services.values()
                if service.name.strip().lower() == key
            ),
            None,
        )

    def delete_service(self, service_id: int):
        service = self.services.pop(service_id, None)

        if service is not None:
            for hook in list(self.service_deleted_hooks):
                hook(service)

        return service

    # --- queues ---

    def add_queue_entry(
        self,
        service_id: int,
        user_id: str,
        priority: str,
        joined_at: float,
    ) -> QueueEntry:
        entry = QueueEntry(
            id=self._next_queue_entry_id,
            service_id=service_id,
            user_id=user_id,
            priority=priority,
            joined_at=joined_at,
        )

        self._next_queue_entry_id += 1

        if service_id not in self.queues:
            self.queues[service_id] = []

        self.queues[service_id].append(entry)

        return entry

    def get_queue(self, service_id: int) -> list[QueueEntry]:
        return self.queues.get(service_id, [])

    def find_queue_entry(
        self,
        service_id: int,
        user_id: str,
    ):
        return next(
            (
                entry
                for entry in self.get_queue(service_id)
                if entry.user_id == user_id
            ),
            None,
        )

    def remove_queue_entry(
        self,
        service_id: int,
        user_id: str,
    ):
        entry = self.find_queue_entry(
            service_id,
            user_id,
        )

        if entry is None:
            return None

        self.queues[service_id].remove(entry)

        return entry

    def ordered_queue(
        self,
        service_id: int,
    ) -> list[QueueEntry]:
        return sorted(
            self.get_queue(service_id),
            key=lambda entry: (
                PRIORITY_ORDER.get(
                    entry.priority,
                    1,
                ),
                entry.order if entry.order is not None else entry.joined_at,
                entry.id,
            ),
        )

    def pop_next_queue_entry(
        self,
        service_id: int,
    ):
        ordered = self.ordered_queue(service_id)

        if not ordered:
            return None

        next_entry = ordered[0]

        self.queues[service_id].remove(
            next_entry
        )

        return next_entry

    def clear_queue(
        self,
        service_id: int,
    ):
        return self.queues.pop(
            service_id,
            [],
        )


db = Store()


def seed_demo_users(store: Store = db):
    """Demo accounts so the UI can be tried right after startup."""

    demo = [
        (
            "11111111-1111-4111-8111-111111111111",
            "Demo Student",
            "student@uh.edu",
            config.ROLE_STUDENT,
        ),
        (
            "22222222-2222-4222-8222-222222222222",
            "Demo Staff",
            "admin@uh.edu",
            config.ROLE_STAFF,
        ),
    ]

    for user_id, name, email, role in demo:
        if store.get_user_by_email(email) is None:
            store.add_user(
                User(
                    user_id,
                    name,
                    email,
                    hash_password("Password1"),
                    role,
                )
            )


def seed_demo_services(store: Store = db):
    """The same three services the A2 demo started with."""

    if store.services:
        return

    store.add_service(
        "Password Reset",
        "Account access and password recovery.",
        10,
        "high",
        open=True,
    )

    store.add_service(
        "Wi-Fi / Network",
        "Campus Wi-Fi and device connectivity.",
        15,
        "medium",
        open=True,
    )

    store.add_service(
        "Printing",
        "Printing setup, credits, and troubleshooting.",
        5,
        "low",
        open=False,
    )
