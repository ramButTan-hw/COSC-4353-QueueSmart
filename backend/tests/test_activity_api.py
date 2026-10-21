"""Modules 5/6 exercised through the team's real authentication dependencies."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import create_access_token
from app.store import db


def account(user_id, role="student"):
    user = User(user_id, user_id.title(), f"{user_id}@uh.edu", "unused", role)
    db.add_user(user)
    token, _ = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def join(user_id="alice", **changes):
    return {"type": "joined", "participationId": "visit-" + user_id,
            "userId": user_id, "serviceId": 1, "serviceName": "Help Desk",
            "position": 1, "queueOpen": True, **changes}


def events(client, headers, *items):
    return client.post("/api/queue-events", headers=headers, json={"events": list(items)})


@pytest.mark.parametrize(("method", "path"), [
    ("get", "/api/session"), ("get", "/api/history"), ("get", "/api/notifications"),
    ("delete", "/api/notifications"), ("post", "/api/notifications/read-all"),
    ("patch", "/api/notifications/anything/read"), ("post", "/api/queue-events")])
def test_activity_routes_require_real_authentication(client, method, path):
    response = getattr(client, method)(path, headers={"X-QueueSmart-User": "alice"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_join_leave_shifts_reminders_and_returns_only_the_authenticated_users_data(client):
    users = {name: account(name) for name in ("alice", "bob", "charlie")}
    for name, headers in users.items():
        # The bridge derives the real position even if the browser supplies 1.
        assert events(client, headers, join(name)).status_code == 200
    assert len(client.get("/api/notifications", headers=users["charlie"]).json()) == 1
    assert events(client, users["alice"], {"type": "left", "participationId": "visit-alice"}).status_code == 200
    charlie = client.get("/api/notifications", headers=users["charlie"])
    assert charlie.headers["cache-control"] == "no-store"
    assert [n["kind"] for n in charlie.json()] == ["close", "joined"]
    assert "nearly next" in charlie.json()[0]["message"]
    history = client.get("/api/history?userId=bob", headers={**users["alice"], "X-QueueSmart-User": "bob"})
    assert history.headers["cache-control"] == "no-store"
    assert len(history.json()) == 1
    assert history.json()[0]["userId"] == "alice"
    assert history.json()[0]["outcome"] == "Left queue"
    assert "position" not in history.json()[0]
    assert "closeNotified" not in history.json()[0]


def test_notification_read_and_clear_cannot_affect_another_user_or_history(client):
    alice, bob = account("alice"), account("bob")
    events(client, alice, join())
    events(client, bob, join("bob"))
    notices = client.get("/api/notifications", headers=alice).json()
    notification_id = notices[0]["id"]
    path = f"/api/notifications/{notification_id}/read"
    assert client.patch(path, headers=bob).status_code == 404
    assert client.patch(path, headers=alice).json()["read"] is True
    assert client.post("/api/notifications/read-all", headers=alice).json() == {"read": True}
    updated = client.get("/api/notifications", headers=alice).json()
    assert len(updated) == 2 and all(n["read"] for n in updated)
    assert client.delete("/api/notifications", headers=alice).json() == {"cleared": True}
    assert client.get("/api/notifications", headers=alice).json() == []
    assert len(client.get("/api/notifications", headers=bob).json()) == 2
    assert len(client.get("/api/history", headers=alice).json()) == 1


@pytest.mark.parametrize("operation", [
    {"type": "served", "participationId": "visit-bob"},
    {"type": "removed", "participationId": "visit-bob"},
    {"type": "left", "participationId": "visit-bob"},
    {"type": "position", "participationId": "visit-bob", "position": 1, "queueOpen": True},
    join("bob", participationId="forged"),
])
def test_student_cannot_mutate_another_users_activity(client, operation):
    alice, bob = account("alice"), account("bob")
    events(client, bob, join("bob"))
    before = client.get("/api/history", headers=bob).json()
    response = events(client, alice, operation)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert client.get("/api/history", headers=bob).json() == before
    assert client.get("/api/history", headers=alice).json() == []


def test_student_cannot_bypass_checks_with_a_batch_and_closed_join_is_rejected(client):
    alice = account("alice")
    assert events(client, alice, join(), {"type": "served", "participationId": "visit-alice"}).status_code == 403
    assert events(client, alice, join(queueOpen=False)).status_code == 409
    assert client.get("/api/history", headers=alice).json() == []


def test_staff_events_are_atomic_and_preserve_completed_visits(client):
    alice, staff = account("alice"), account("staff", "staff")
    events(client, alice, join())
    served = {"type": "served", "participationId": "visit-alice"}
    response = events(client, staff, served, {"type": "left", "participationId": "missing"})
    assert response.status_code == 404
    assert client.get("/api/history", headers=alice).json()[0]["outcome"] == "Waiting"
    assert events(client, staff, served).json() == {"processed": 1}
    result = client.get("/api/history", headers=alice).json()[0]
    assert result["outcome"] == "Served" and result["completedAt"] >= result["joinedAt"]
    assert events(client, staff, served).status_code == 409
    assert events(client, staff, join("missing")).status_code == 422
    assert events(client, staff, join("staff")).status_code == 422


@pytest.mark.parametrize("body", [None, [], {}, {"events": []}, {"events": [{}]},
    {"events": [join(position=True)]}, {"events": [join(userId="a" * 255)]},
    {"events": [join(), {"type": "left", "participationId": ""}]}])
def test_invalid_http_input_uses_the_shared_error_format_and_never_partially_writes(client, body):
    headers = account("staff", "staff")
    response = client.post("/api/queue-events", headers=headers, json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error" and error["fields"]
    assert db.activity.history.records == {}
    assert db.activity.notifications.items == []


def test_invalid_dates_and_missing_participation_return_shared_errors(client):
    alice = account("alice")
    for query in ("from=bad", "from=2026-02-30", "from=2026-10-17&to=2026-10-16"):
        response = client.get("/api/history?" + query, headers=alice)
        assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"
    assert events(client, alice, {"type": "left", "participationId": "missing"}).status_code == 404


def test_store_reset_clears_activity_and_changes_demo_session(client):
    alice = account("alice")
    session = client.get("/api/session", headers=alice).json()
    events(client, alice, join())
    db.reset()
    assert db.activity.history.records == {} and db.activity.notifications.items == []
    assert db.activity.id != session["id"]
    assert client.get("/api/history", headers=alice).status_code == 401


def test_actual_login_token_works_with_activity_and_ui_is_served_safely():
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"email": "student@uh.edu", "password": "Password1"})
        assert login.status_code == 200
        identity = login.json()
        headers = {"Authorization": "Bearer " + identity["access_token"]}
        assert events(client, headers, join(identity["user"]["id"])).status_code == 200
        assert len(client.get("/api/history", headers=headers).json()) == 1
        for path in ("/", "/front%20page.html", "/history.html", "/js/backend.js", "/css/user.css"):
            assert client.get(path).status_code == 200
        for path in ("/backend/app/security.py", "/.git/config", "/missing.html"):
            assert client.get(path).status_code == 404
        schema = client.get("/openapi.json").json()
        assert "/auth/login" in schema["paths"] and "/api/history" in schema["paths"]
        assert "Bearer" in str(schema["paths"]["/api/history"]["get"]["security"])
