"""A4 part 6: real SQL writes, restart durability, constraints and atomicity."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app import database, queue_activity
from app.activity.persistence import PersistentActivity
from app.errors import ApiError
from app.main import create_app
from app.models import User
from app.security import create_access_token
from app.store import db, seed_demo_services
from app.tables.activity import HistoryRecord, NotificationRecord
from app.tables.credentials import UserCredentials


@pytest.fixture
def actors():
    seed_demo_services()
    headers = {}
    for name in ("alice", "bob", "staff"):
        user = User(name, name.title(), f"{name}@uh.edu", "unused", "staff" if name == "staff" else "student")
        db.add_user(user)
        headers[name] = {"Authorization": "Bearer " + create_access_token(user)[0]}
    return headers


def join(client, actors, name="alice"):
    response = client.post("/queues/1/join", headers=actors[name])
    assert response.status_code == 201, response.text


def snapshot():
    activity = PersistentActivity()
    with activity.transaction():
        return activity.history.list("alice"), activity.notifications.list("alice")


def test_api_writes_history_notifications_and_viewed_status(client, actors):
    join(client, actors)
    with database.SessionLocal() as session:
        history = session.scalar(select(HistoryRecord))
        assert history.user_id == "alice" and history.outcome == "Waiting"
        notices = list(session.scalars(select(NotificationRecord)))
        assert len(notices) == 3  # joined, next, and staff alert
        assert all(n.participation_id == history.id and n.status == "sent" for n in notices)
    notice = client.get("/api/notifications", headers=actors["alice"]).json()[0]
    assert client.patch(f"/api/notifications/{notice['id']}/read", headers=actors["bob"]).status_code == 404
    assert client.patch(f"/api/notifications/{notice['id']}/read", headers=actors["alice"]).status_code == 200
    with database.SessionLocal() as session:
        assert session.scalar(select(NotificationRecord.status).where(NotificationRecord.id == notice["id"])) == "viewed"
    assert snapshot()[1][0]["read"] is True


def test_read_all_and_clear_survive_new_activity_and_keep_other_users(client, actors):
    join(client, actors)
    join(client, actors, "bob")
    client.post("/api/notifications/read-all", headers=actors["alice"])
    assert all(n["read"] for n in snapshot()[1])
    client.delete("/api/notifications", headers=actors["alice"])
    assert snapshot()[1] == []
    assert len(snapshot()[0]) == 1
    assert all(not n["read"] for n in client.get("/api/notifications", headers=actors["bob"]).json())


def test_file_database_survives_engine_and_store_restart(tmp_path):
    original_url = str(database.engine.url)
    url = f"sqlite:///{(tmp_path / 'activity.db').as_posix()}"
    try:
        database.configure(url)
        with TestClient(create_app()) as client:
            login = client.post("/auth/login", json={"email": "student@uh.edu", "password": "Password1"})
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            assert client.post("/queues/1/join", headers=headers).status_code == 201
            assert client.delete("/queues/1/leave", headers=headers).status_code == 204
            client.post("/api/notifications/read-all", headers=headers)
            before_history = client.get("/api/history", headers=headers).json()
            before_notices = client.get("/api/notifications", headers=headers).json()
        db.reset()
        database.configure(url)  # dispose all connections and reconnect to the same disk file
        with TestClient(create_app()) as client:
            assert client.get("/api/history", headers=headers).json() == before_history
            assert client.get("/api/notifications", headers=headers).json() == before_notices
            assert client.post("/queues/1/join", headers=headers).status_code == 201
            visits = client.get("/api/history", headers=headers).json()
            assert len(visits) == 2 and visits[0]["id"] != visits[1]["id"]
    finally:
        db.reset()
        database.configure(original_url)
        database.reset_database()


def test_restart_recovers_orphan_waiting_visits_once(client, actors):
    join(client, actors)
    db.reset()
    seed_demo_services()
    queue_activity.recover_interrupted_visits()
    first = snapshot()
    assert first[0][0]["outcome"] == "Removed"
    assert first[1][0]["kind"] == "interrupted"
    queue_activity.recover_interrupted_visits()
    assert snapshot() == first
    join(client, actors)
    assert len(snapshot()[0]) == 2
    queue_activity.recover_interrupted_visits()
    assert snapshot()[0][0]["outcome"] == "Waiting"  # a live queue is not interrupted


def test_error_after_history_flush_rolls_back_database_and_queue(client, actors, monkeypatch):
    join(client, actors)
    before = snapshot()
    def fail_commit(session, *args):
        session.flush()
        raise ApiError(409, "conflict", "Injected commit failure")
    with monkeypatch.context() as patch:
        patch.setattr(database, "commit", fail_commit)
        assert client.delete("/queues/1/leave", headers=actors["alice"]).status_code == 409
    assert snapshot() == before
    assert db.get_queue(1)[0].user_id == "alice"


def test_invalid_history_flush_rolls_back_and_returns_conflict(client, actors, monkeypatch):
    original = db.activity.history.join
    def invalid_join(event):
        record = original(event)
        record["serviceName"] = "x" * 101
        return record
    monkeypatch.setattr(db.activity.history, "join", invalid_join)
    assert client.post("/queues/1/join", headers=actors["alice"]).status_code == 409
    assert snapshot() == ([], []) and db.get_queue(1) == []


@pytest.mark.parametrize("model, values", [
    (NotificationRecord, {"message": ""}),
    (NotificationRecord, {"message": "x" * 1001}),
    (NotificationRecord, {"message": None}),
    (NotificationRecord, {"status": "invalid"}),
    (NotificationRecord, {"timestamp": -1}),
    (NotificationRecord, {"recipient_id": "missing"}),
    (NotificationRecord, {"participation_id": "missing"}),
    (NotificationRecord, {"role": "invalid"}),
    (NotificationRecord, {"type": "invalid"}),
    (NotificationRecord, {"kind": "x" * 41}),
    (HistoryRecord, {"user_id": "missing"}),
    (HistoryRecord, {"service_name": "x" * 101}),
    (HistoryRecord, {"position": 0}),
    (HistoryRecord, {"service_id": 0}),
    (HistoryRecord, {"outcome": "invalid"}),
    (HistoryRecord, {"outcome": "Served"}),
    (HistoryRecord, {"completed_at": 100}),
    (HistoryRecord, {"joined_at": -1}),
])
def test_database_rejects_invalid_direct_writes(client, actors, model, values):
    join(client, actors)
    before = snapshot()
    with database.SessionLocal() as session:
        with pytest.raises(IntegrityError):
            session.execute(update(model).values(**values))
            session.commit()
        session.rollback()
    assert snapshot() == before


def test_foreign_keys_cascade_account_deletion(client, actors):
    join(client, actors)
    with database.SessionLocal() as session:
        session.execute(delete(UserCredentials).where(UserCredentials.id == "alice"))
        session.commit()
        assert session.scalar(select(HistoryRecord)) is None
        assert session.scalar(select(NotificationRecord)) is None


def test_failed_event_batch_is_not_partially_persisted(actors):
    activity = PersistentActivity()
    with pytest.raises(ApiError):
        activity.apply([
            {"type": "joined", "participationId": "a", "userId": "alice", "serviceId": 1,
             "serviceName": "Desk", "position": 1, "queueOpen": True},
            {"type": "served", "participationId": "missing"},
        ])
    assert snapshot() == ([], [])
