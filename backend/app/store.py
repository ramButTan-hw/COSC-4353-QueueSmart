"""In-memory data store shared by every module (no database in A3).

Other modules (services, queues, history, notifications) should add their own collections
here so the whole back end reads and writes the same objects. Everything resets when the
server restarts.
"""
from app import config
from app.activity import Activity
from app.models import User
from app.security import hash_password


class Store:
    def __init__(self):
        self.reset()

    def reset(self):
        self.users: dict[str, User] = {}
        self._email_index: dict[str, str] = {}
        self.activity = Activity()

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
