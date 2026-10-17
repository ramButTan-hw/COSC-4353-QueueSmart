"""FastAPI API tests that can run without opening local ports."""
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from a3_activity import install_activity
from a3_activity.demo import create_app

JOIN = {"type": "joined", "participationId": "a", "userId": "alice",
        "serviceId": 1, "serviceName": "Help Desk", "position": 1, "queueOpen": True}


@pytest.fixture
def client():
    with TestClient(create_app(), headers={"X-QueueSmart-User": "alice"}) as client:
        yield client


def test_notification_and_history_api_lifecycle(client):
    response = client.post("/api/queue-events", json={"events": [JOIN]})
    assert response.status_code == 200 and response.json() == {"processed": 1}
    notices = client.get("/api/notifications")
    assert notices.headers["cache-control"] == "no-store"
    assert len(notices.json()) == 2
    assert client.get("/api/history").json()[0]["outcome"] == "Waiting"
    assert client.get("/api/history", headers={"X-QueueSmart-User": "bob"}).json() == []
    notification_id = notices.json()[0]["id"]
    assert client.patch(f"/api/notifications/{notification_id}/read",
                        headers={"X-QueueSmart-User": "bob"}).status_code == 404
    assert client.patch(f"/api/notifications/{notification_id}/read").json()["read"] is True
    assert client.post("/api/notifications/read-all").status_code == 200
    updated = client.get("/api/notifications").json()
    assert len(updated) == 2 and all(item["read"] for item in updated)
    assert client.post("/api/queue-events", json={"events": [
        {"type": "served", "participationId": "a"}]}).status_code == 200
    assert client.get("/api/history").json()[0]["outcome"] == "Served"
    assert client.delete("/api/notifications").status_code == 200
    assert client.get("/api/notifications").json() == []
    assert len(client.get("/api/history").json()) == 1


@pytest.mark.parametrize(("body", "status"), [("{", 400), ("[]", 400), ("{}", 400),
    ('{"events":[{}]}', 400),
    ('{"events":[{"type":"left","participationId":"missing"}]}', 404),
    ('{"padding":"' + "a" * 66000 + '"}', 413)])
def test_http_validation_errors_have_consistent_json(client, body, status):
    response = client.post("/api/queue-events", content=body,
                           headers={"Content-Type": "application/json"})
    assert response.status_code == status
    assert isinstance(response.json()["error"], str)


def test_identity_media_type_dates_and_duplicate_errors(client):
    assert client.post("/api/queue-events", content="{}").status_code == 415
    for identity in ("", " ", "u" * 255):
        assert client.get("/api/history", headers={"X-QueueSmart-User": identity}).status_code == 400
    with TestClient(create_app()) as anonymous:
        assert anonymous.get("/api/history").status_code == 400
    assert client.get("/api/history?from=bad").status_code == 400
    assert client.get("/api/history?from=2026-10-17&to=2026-10-16").status_code == 400
    client.post("/api/queue-events", json={"events": [JOIN]})
    assert client.post("/api/queue-events", json={"events": [JOIN]}).status_code == 409
    assert len(client.get("/api/history").json()) == 1


def test_demo_serves_frontend_and_excludes_source_files(client):
    for route in ("/", "/front%20page.html", "/history.html", "/js/backend.js", "/css/user.css"):
        response = client.get(route)
        assert response.status_code == 200 and "text/" in response.headers["content-type"]
    assert client.head("/history.html").status_code == 200
    for route in ("/a3_activity/activity.py", "/backend/server.cjs", "/.git/config", "/missing.html"):
        assert client.get(route).status_code == 404
    assert client.post("/history.html").status_code == 405


def test_api_documentation_exposes_the_browser_contract(client):
    schema = client.get("/openapi.json").json()
    assert {"/api/history", "/api/notifications", "/api/queue-events"} <= schema["paths"].keys()
    assert "participationId" in schema["components"]["schemas"]["JoinedEvent"]["properties"]
    assert client.get("/docs").status_code == 200


def test_app_instances_have_separate_memory_and_session(client):
    client.post("/api/queue-events", json={"events": [JOIN]})
    with TestClient(create_app(), headers={"X-QueueSmart-User": "alice"}) as other:
        assert other.get("/api/session").json() != client.get("/api/session").json()
        assert other.get("/api/history").json() == []
        assert other.get("/api/notifications").json() == []


def test_teammate_mount_does_not_change_other_routes_or_handlers():
    app = FastAPI()
    with pytest.raises(ValueError, match="authenticated user_dependency"):
        install_activity(app)

    def authenticated_id(authorization: str = Header()):
        return authorization.removeprefix("Bearer ")

    @app.get("/team-example")
    def team_example(count: int):
        return {"count": count}

    activity = install_activity(app, user_dependency=authenticated_id)
    activity.apply([JOIN])
    with TestClient(app, headers={"Authorization": "Bearer alice"}) as client:
        assert client.get("/api/history").json()[0]["userId"] == "alice"
        assert len(client.get("/api/notifications").json()) == 2
        assert client.get("/api/session").status_code == 404
        assert client.post("/api/queue-events", json={"events": [JOIN]}).status_code == 404
        assert client.get("/team-example?count=invalid").status_code == 422
        assert client.get("/team-example?count=2").json() == {"count": 2}
    with pytest.raises(RuntimeError):
        install_activity(app, user_dependency=authenticated_id)
