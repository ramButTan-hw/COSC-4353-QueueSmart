"""In-memory data store shared by every module (no database in A3).

Other modules (services, queues, history, notifications) should add their own collections
here so the whole back end reads and writes the same objects. Everything resets when the
server restarts.
"""
from app import config
from app.models import Service, User
from app.security import hash_password


class Store:
    def __init__(self):
        # Callbacks run when a service is deleted, as hook(service). The queue module registers one
        # to cancel the waiting entries and notify those students. Not cleared by reset().
        self.service_deleted_hooks: list = []
        self.reset()

    def reset(self):
        self.users: dict[str, User] = {}
        self._email_index: dict[str, str] = {}
        self.services: dict[int, Service] = {}
        self._next_service_id = 1

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
    def add_service(self, name: str, description: str, duration: int, priority: str, open: bool = False) -> Service:
        service = Service(self._next_service_id, name, description, duration, priority, open)
        self._next_service_id += 1  # ids are never reused, even after a delete
        self.services[service.id] = service
        return service

    def get_service(self, service_id: int):
        return self.services.get(service_id)

    def list_services(self) -> list[Service]:
        return [self.services[i] for i in sorted(self.services)]

    def get_service_by_name(self, name: str):
        key = name.strip().lower()
        return next((s for s in self.services.values() if s.name.strip().lower() == key), None)

    def delete_service(self, service_id: int):
        service = self.services.pop(service_id, None)
        if service is not None:
            for hook in list(self.service_deleted_hooks):
                hook(service)
        return service


db = Store()


def seed_demo_users(store: Store = db):
    """Demo accounts so the UI can be tried right after startup (same ones as the A2 demo)."""
    demo = [
        ("11111111-1111-4111-8111-111111111111", "Demo Student", "student@uh.edu", config.ROLE_STUDENT),
        ("22222222-2222-4222-8222-222222222222", "Demo Staff", "admin@uh.edu", config.ROLE_STAFF),
    ]
    for user_id, name, email, role in demo:
        if store.get_user_by_email(email) is None:
            store.add_user(User(user_id, name, email, hash_password("Password1"), role))


def seed_demo_services(store: Store = db):
    """The same three services the A2 demo started with. Only seeds an empty catalogue."""
    if store.services:
        return
    store.add_service("Password Reset", "Account access and password recovery.", 10, "high", open=True)
    store.add_service("Wi-Fi / Network", "Campus Wi-Fi and device connectivity.", 15, "medium", open=True)
    store.add_service("Printing", "Printing setup, credits, and troubleshooting.", 5, "low", open=False)
