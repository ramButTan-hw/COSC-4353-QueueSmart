"""Server-side notifications for position changes, queue open/close, and staff alerts."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import User
from app.security import create_access_token
from app.store import db, seed_demo_services

POSITION = "You moved to position {} in Password Reset."


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def users():
    seed_demo_services()
    result = {}
    for name in ("a", "b", "c", "d", "e", "staff", "staff2"):
        role = "staff" if name.startswith("staff") else "student"
        user = User(name, name.title(), f"{name}@uh.edu", "unused", role)
        db.add_user(user)
        result[name] = {"Authorization": "Bearer " + create_access_token(user)[0]}
    return result


def join(client, users, name, service=1):
    r = client.post(f"/queues/{service}/join", headers=users[name])
    assert r.status_code == 201, r.text


def notices(client, users, name):
    return client.get("/api/notifications", headers=users[name]).json()


def messages(client, users, name):
    return [n["message"] for n in notices(client, users, name)]


def line_up(client, users, names="abcde"):
    for name in names:
        join(client, users, name)
    return {name: len(notices(client, users, name)) for name in names}


def new_messages(client, users, name, before):
    return messages(client, users, name)[: len(notices(client, users, name)) - before[name]]


# ---------- position changes ----------

def test_someone_ahead_leaving_tells_everyone_behind_where_they_are_now(client, users):
    before = line_up(client, users)
    assert client.delete("/queues/1/leave", headers=users["a"]).status_code == 204
    assert new_messages(client, users, "d", before) == [POSITION.format(3)]
    assert new_messages(client, users, "e", before) == [POSITION.format(4)]


def test_staff_reordering_tells_both_students_who_swapped(client, users):
    before = line_up(client, users)
    r = client.post("/queues/1/move", headers=users["staff"], json={"user_id": "e", "direction": "up"})
    assert r.status_code == 200
    assert new_messages(client, users, "e", before) == [POSITION.format(4)]
    assert new_messages(client, users, "d", before) == [POSITION.format(5)]
    for untouched in "abc":
        assert new_messages(client, users, untouched, before) == []


def test_serving_moves_everyone_up(client, users):
    before = line_up(client, users)
    assert client.post("/queues/1/serve-next", headers=users["staff"]).status_code == 200
    assert new_messages(client, users, "a", before) == ["You've been served for Password Reset"]
    assert new_messages(client, users, "e", before) == [POSITION.format(4)]


def test_removing_a_student_moves_those_behind_up(client, users):
    before = line_up(client, users)
    assert client.delete("/queues/1/members/c", headers=users["staff"]).status_code == 204
    assert new_messages(client, users, "c", before) == ["You were removed from the Password Reset queue"]
    assert new_messages(client, users, "e", before) == [POSITION.format(4)]


def test_no_message_when_a_students_position_did_not_change(client, users):
    before = line_up(client, users)
    client.delete("/queues/1/leave", headers=users["e"])  # last in line leaves
    for name in "abcd":
        assert new_messages(client, users, name, before) == []


def test_a_reminder_replaces_the_position_message_instead_of_doubling_it(client, users):
    before = line_up(client, users)
    client.delete("/queues/1/leave", headers=users["a"])
    # c moved 3 -> 2, which earns the reminder; it must not also get "You moved to position 2"
    assert new_messages(client, users, "c", before) == ["You're nearly next for Password Reset. Please head to the help desk."]


def test_reminder_fires_again_when_a_student_reaches_position_one(client, users):
    before = line_up(client, users, "ab")
    assert messages(client, users, "b")[0].startswith("You're nearly next")
    client.delete("/queues/1/leave", headers=users["a"])
    assert new_messages(client, users, "b", before) == ["You're next for Password Reset. Please head to the help desk."]
    join(client, users, "c")
    client.delete("/queues/1/leave", headers=users["c"])  # position events that change nothing for b
    reminders = [n for n in notices(client, users, "b") if n["kind"] == "close"]
    assert len(reminders) == 2  # nearly next, then next, never repeated


def test_a_higher_priority_joiner_pushes_others_back_and_they_are_told(client, users):
    before = line_up(client, users, "ab")
    join(client, users, "c", service=2)  # different queue: nobody in service 1 hears about it
    assert new_messages(client, users, "a", before) == [] and new_messages(client, users, "b", before) == []


# ---------- queue opened / closed ----------

def test_closing_and_opening_a_queue_tells_the_students_waiting_in_it(client, users):
    before = line_up(client, users, "abc")
    assert client.post("/queues/1/close", headers=users["staff"]).status_code == 200
    for name in "abc":
        n = notices(client, users, name)[0]
        assert n["message"] == "Password Reset queue is now closed." and n["type"] == "warning" and n["kind"] == "queue_closed"
    before = {name: len(notices(client, users, name)) for name in "abc"}
    assert client.post("/queues/1/open", headers=users["staff"]).status_code == 200
    for name in "abc":
        assert "Password Reset queue is now open." in new_messages(client, users, name, before)
        assert next(n for n in notices(client, users, name) if n["kind"] == "queue_open")["type"] == "info"


def test_opening_again_reminds_students_near_the_front_after_the_pause(client, users):
    line_up(client, users, "ab")
    client.post("/queues/1/close", headers=users["staff"])
    client.delete("/queues/1/leave", headers=users["a"])  # b moves to 1 while paused: no reminder yet
    assert not any(n["message"].startswith("You're next") for n in notices(client, users, "b"))
    client.post("/queues/1/open", headers=users["staff"])
    assert any(n["message"].startswith("You're next") for n in notices(client, users, "b"))


def test_repeating_open_or_close_does_not_spam(client, users):
    line_up(client, users, "ab")
    client.post("/queues/1/close", headers=users["staff"])
    before = {name: len(notices(client, users, name)) for name in "ab"}
    client.post("/queues/1/close", headers=users["staff"])  # already closed
    assert {name: len(notices(client, users, name)) for name in "ab"} == before
    client.post("/queues/1/open", headers=users["staff"])
    before = {name: len(notices(client, users, name)) for name in "ab"}
    client.post("/queues/1/open", headers=users["staff"])  # already open
    assert {name: len(notices(client, users, name)) for name in "ab"} == before


def test_open_and_close_only_reach_students_in_that_queue(client, users):
    join(client, users, "a", service=1)
    join(client, users, "b", service=2)
    before = {name: len(notices(client, users, name)) for name in "ab"}
    client.post("/queues/1/close", headers=users["staff"])
    assert new_messages(client, users, "a", before) == ["Password Reset queue is now closed."]
    assert new_messages(client, users, "b", before) == []


def test_opening_an_empty_queue_is_fine(client, users):
    assert client.post("/queues/3/open", headers=users["staff"]).status_code == 200
    assert client.post("/queues/3/close", headers=users["staff"]).status_code == 200


# ---------- staff alerts ----------

def test_every_staff_account_is_told_when_a_student_joins_and_leaves(client, users):
    join(client, users, "a")
    for staff in ("staff", "staff2"):
        n = notices(client, users, staff)
        assert [x["message"] for x in n] == ["New student in Password Reset"]
        assert n[0]["role"] == "staff" and n[0]["recipientId"] == staff and n[0]["kind"] == "student_joined"
    client.delete("/queues/1/leave", headers=users["a"])
    for staff in ("staff", "staff2"):
        assert messages(client, users, staff)[0] == "A student left the Password Reset queue"
        assert len(notices(client, users, staff)) == 2


def test_staff_alerts_are_private_to_staff_and_work_with_read_and_clear(client, users):
    join(client, users, "a")
    assert all("New student" not in m for m in messages(client, users, "a"))
    assert all("New student" not in m for m in messages(client, users, "b"))
    n = notices(client, users, "staff")[0]
    assert client.patch(f"/api/notifications/{n['id']}/read", headers=users["staff"]).json()["read"] is True
    assert client.patch(f"/api/notifications/{n['id']}/read", headers=users["staff2"]).status_code == 404
    client.delete("/api/notifications", headers=users["staff"])
    assert notices(client, users, "staff") == [] and len(notices(client, users, "staff2")) == 1


def test_serving_or_removing_does_not_create_more_staff_alerts(client, users):
    for name in "abc":
        join(client, users, name)
    count = len(notices(client, users, "staff"))
    client.post("/queues/1/serve-next", headers=users["staff"])
    client.delete("/queues/1/members/b", headers=users["staff"])
    client.post("/queues/1/close", headers=users["staff"])
    assert len(notices(client, users, "staff")) == count


def test_joining_still_works_when_there_are_no_staff_accounts(client, users):
    for name in ("staff", "staff2"):
        del db.users[name]
    join(client, users, "a")
    assert any(m.startswith("You joined") for m in messages(client, users, "a"))


def test_staff_do_not_see_student_style_notifications(client, users):
    line_up(client, users, "ab")
    client.post("/queues/1/close", headers=users["staff"])
    assert all(n["role"] == "staff" for n in notices(client, users, "staff"))


# ---------- safety ----------

def test_a_refused_request_leaves_no_notifications_behind(client, users):
    line_up(client, users, "ab")
    client.post("/queues/1/close", headers=users["staff"])
    snapshot = {name: len(notices(client, users, name)) for name in ("a", "b", "staff")}
    assert client.post("/queues/1/serve-next", headers=users["staff"]).status_code == 409
    assert client.post("/queues/1/move", headers=users["staff"], json={"user_id": "zz", "direction": "up"}).status_code == 404
    assert client.post("/queues/99/open", headers=users["staff"]).status_code == 404
    assert {name: len(notices(client, users, name)) for name in ("a", "b", "staff")} == snapshot


def test_history_does_not_expose_the_internal_reminder_flags(client, users):
    join(client, users, "a")
    record = client.get("/api/history", headers=users["a"]).json()[0]
    assert not {"closeNotified", "nextNotified", "position", "queueOpen"} & set(record)
