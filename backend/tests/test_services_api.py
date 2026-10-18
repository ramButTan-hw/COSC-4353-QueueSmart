import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import db, seed_demo_services

GOOD = {"name": "VPN Setup", "description": "Connect to the campus VPN.", "duration": 20, "priority": "medium"}


def make(client, staff_headers, **change):
    return client.post("/services", json={**GOOD, **change}, headers=staff_headers)


# ---------- list and view ----------

def test_list_requires_login(client):
    assert client.get("/services").status_code == 401


def test_list_is_empty_without_seed_data(client, student_headers):
    assert client.get("/services", headers=student_headers).json() == []


def test_students_can_list_and_view_services(client, student_headers, staff_headers):
    created = make(client, staff_headers).json()
    listing = client.get("/services", headers=student_headers)
    assert listing.status_code == 200 and listing.json() == [created]
    one = client.get(f"/services/{created['id']}", headers=student_headers)
    assert one.status_code == 200 and one.json() == created


def test_list_is_ordered_by_id(client, student_headers, staff_headers):
    for name in ("B", "A", "C"):
        make(client, staff_headers, name=name)
    assert [s["name"] for s in client.get("/services", headers=student_headers).json()] == ["B", "A", "C"]


def test_view_unknown_service_is_404(client, student_headers):
    r = client.get("/services/99", headers=student_headers)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_view_with_a_non_numeric_id_is_a_validation_error(client, student_headers):
    r = client.get("/services/abc", headers=student_headers)
    assert r.status_code == 422 and "service_id" in r.json()["error"]["fields"]


# ---------- create ----------

def test_staff_can_create_a_service(client, staff_headers):
    r = make(client, staff_headers)
    assert r.status_code == 201
    body = r.json()
    assert body == {"id": 1, "open": False, **GOOD}


def test_ids_increase(client, staff_headers):
    assert make(client, staff_headers, name="One").json()["id"] == 1
    assert make(client, staff_headers, name="Two").json()["id"] == 2


def test_create_trims_text(client, staff_headers):
    r = make(client, staff_headers, name="  Spaced  ", description="  text  ")
    assert r.json()["name"] == "Spaced" and r.json()["description"] == "text"


def test_students_cannot_create(client, student_headers):
    r = client.post("/services", json=GOOD, headers=student_headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_create_requires_login(client):
    assert client.post("/services", json=GOOD).status_code == 401


def test_a_student_gets_403_even_with_an_invalid_body(client, student_headers):
    assert client.post("/services", json={}, headers=student_headers).status_code == 403


def test_duplicate_name_is_a_conflict_ignoring_case_and_spaces(client, staff_headers):
    make(client, staff_headers, name="Printing")
    r = make(client, staff_headers, name="  printing ")
    assert r.status_code == 409
    assert r.json()["error"]["fields"]["name"] == "A service with this name already exists."


@pytest.mark.parametrize(
    "change, field, message",
    [
        ({"name": ""}, "name", "This field is required."),
        ({"name": "   "}, "name", "This field is required."),
        ({"name": "x" * 101}, "name", "Must be at most 100 characters."),
        ({"name": 5}, "name", "Must be a string."),
        ({"description": ""}, "description", "This field is required."),
        ({"description": "x" * 501}, "description", "Must be at most 500 characters."),
        ({"description": None}, "description", "Must be a string."),
        ({"duration": 0}, "duration", "Must be at least 1."),
        ({"duration": -5}, "duration", "Must be at least 1."),
        ({"duration": 481}, "duration", "Must be at most 480."),
        ({"duration": 1.5}, "duration", "Must be a whole number."),
        ({"duration": "30"}, "duration", "Must be a whole number."),
        ({"duration": True}, "duration", "Must be a whole number."),
        ({"duration": None}, "duration", "Must be a whole number."),
        ({"priority": "urgent"}, "priority", "Must be one of: 'low', 'medium' or 'high'."),
        ({"priority": "High"}, "priority", "Must be one of: 'low', 'medium' or 'high'."),
        ({"priority": 2}, "priority", "Must be one of: 'low', 'medium' or 'high'."),
        ({"open": True}, "open", "Unknown field."),
        ({"id": 7}, "id", "Unknown field."),
    ],
)
def test_create_validation_errors(client, staff_headers, change, field, message):
    r = make(client, staff_headers, **change)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error" and err["fields"][field] == message
    assert db.list_services() == []  # nothing was created


@pytest.mark.parametrize("missing", ["name", "description", "duration", "priority"])
def test_create_missing_field(client, staff_headers, missing):
    payload = {k: v for k, v in GOOD.items() if k != missing}
    r = client.post("/services", json=payload, headers=staff_headers)
    assert r.status_code == 422 and r.json()["error"]["fields"][missing] == "This field is required."


@pytest.mark.parametrize("duration", [1, 480])
@pytest.mark.parametrize("priority", ["low", "medium", "high"])
def test_boundary_values_are_accepted(client, staff_headers, duration, priority):
    name = f"S-{duration}-{priority}"
    assert make(client, staff_headers, name=name, duration=duration, priority=priority).status_code == 201


def test_name_of_exactly_100_characters_is_accepted(client, staff_headers):
    assert make(client, staff_headers, name="n" * 100).status_code == 201


# ---------- update (PATCH: only the fields sent change) ----------

def patch(client, headers, sid, **fields):
    return client.patch(f"/services/{sid}", json=fields, headers=headers)


def test_changing_only_the_priority_leaves_everything_else_alone(client, staff_headers):
    sid = make(client, staff_headers).json()["id"]
    r = patch(client, staff_headers, sid, priority="high")
    assert r.status_code == 200
    assert r.json() == {"id": sid, "open": False, **{**GOOD, "priority": "high"}}


def test_several_fields_can_change_at_once(client, staff_headers, student_headers):
    sid = make(client, staff_headers).json()["id"]
    change = {"name": "VPN", "description": "New text.", "duration": 25, "priority": "high"}
    r = patch(client, staff_headers, sid, **change)
    assert r.status_code == 200 and r.json() == {"id": sid, "open": False, **change}
    assert client.get(f"/services/{sid}", headers=student_headers).json()["name"] == "VPN"


def test_patch_trims_text(client, staff_headers):
    sid = make(client, staff_headers).json()["id"]
    assert patch(client, staff_headers, sid, name="  Trimmed ").json()["name"] == "Trimmed"


def test_update_does_not_touch_the_open_state(client, staff_headers):
    sid = make(client, staff_headers).json()["id"]
    db.get_service(sid).open = True  # as the queue module would
    assert patch(client, staff_headers, sid, duration=30).json()["open"] is True


def test_update_may_keep_its_own_name(client, staff_headers):
    sid = make(client, staff_headers).json()["id"]
    assert patch(client, staff_headers, sid, name=GOOD["name"].upper()).status_code == 200


def test_update_to_another_services_name_is_a_conflict(client, staff_headers):
    make(client, staff_headers, name="First")
    second = make(client, staff_headers, name="Second").json()["id"]
    r = patch(client, staff_headers, second, name="first")
    assert r.status_code == 409 and db.get_service(second).name == "Second"


def test_update_unknown_service_is_404(client, staff_headers):
    assert patch(client, staff_headers, 42, priority="low").status_code == 404


def test_an_empty_update_is_rejected(client, staff_headers):
    sid = make(client, staff_headers).json()["id"]
    r = client.patch(f"/services/{sid}", json={}, headers=staff_headers)
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["body"] == "Send at least one field to change."


@pytest.mark.parametrize(
    "change, field, message",
    [
        ({"name": ""}, "name", "This field is required."),
        ({"name": "x" * 101}, "name", "Must be at most 100 characters."),
        ({"name": None}, "name", "Must be a string."),
        ({"description": "   "}, "description", "This field is required."),
        ({"description": "x" * 501}, "description", "Must be at most 500 characters."),
        ({"duration": 0}, "duration", "Must be at least 1."),
        ({"duration": 481}, "duration", "Must be at most 480."),
        ({"duration": "30"}, "duration", "Must be a whole number."),
        ({"duration": None}, "duration", "Must be a whole number."),
        ({"priority": "urgent"}, "priority", "Must be one of: 'low', 'medium' or 'high'."),
        ({"priority": None}, "priority", "Must be one of: 'low', 'medium' or 'high'."),
        ({"open": True}, "open", "Unknown field."),
        ({"id": 9}, "id", "Unknown field."),
    ],
)
def test_update_validation_errors(client, staff_headers, change, field, message):
    sid = make(client, staff_headers).json()["id"]
    r = client.patch(f"/services/{sid}", json=change, headers=staff_headers)
    assert r.status_code == 422 and r.json()["error"]["fields"][field] == message
    stored = db.get_service(sid)
    assert (stored.name, stored.description, stored.duration, stored.priority) == tuple(GOOD.values())  # unchanged


def test_one_bad_field_stops_the_whole_update(client, staff_headers):
    sid = make(client, staff_headers).json()["id"]
    r = patch(client, staff_headers, sid, priority="high", duration=0)
    assert r.status_code == 422
    assert db.get_service(sid).priority == GOOD["priority"]  # the valid field was not applied either


def test_students_cannot_update(client, staff_headers, student_headers):
    sid = make(client, staff_headers).json()["id"]
    assert patch(client, student_headers, sid, priority="low").status_code == 403
    assert db.get_service(sid).priority == GOOD["priority"]


def test_update_requires_login(client):
    assert client.patch("/services/1", json={"priority": "low"}).status_code == 401


def test_put_is_no_longer_supported(client, staff_headers):
    sid = make(client, staff_headers).json()["id"]
    assert client.put(f"/services/{sid}", json=GOOD, headers=staff_headers).status_code == 405


# ---------- delete ----------

def test_staff_can_delete_a_service(client, staff_headers, student_headers):
    sid = make(client, staff_headers).json()["id"]
    r = client.delete(f"/services/{sid}", headers=staff_headers)
    assert r.status_code == 204 and r.content == b""
    assert client.get(f"/services/{sid}", headers=student_headers).status_code == 404
    assert client.get("/services", headers=student_headers).json() == []


def test_delete_unknown_service_is_404(client, staff_headers):
    assert client.delete("/services/9", headers=staff_headers).status_code == 404


def test_students_cannot_delete(client, staff_headers, student_headers):
    sid = make(client, staff_headers).json()["id"]
    assert client.delete(f"/services/{sid}", headers=student_headers).status_code == 403
    assert db.get_service(sid) is not None


def test_delete_requires_login(client):
    assert client.delete("/services/1").status_code == 401


def test_deleted_ids_are_not_reused(client, staff_headers):
    first = make(client, staff_headers, name="One").json()["id"]
    client.delete(f"/services/{first}", headers=staff_headers)
    assert make(client, staff_headers, name="Two").json()["id"] == first + 1


def test_delete_runs_hooks_so_the_queue_module_can_clean_up(client, staff_headers):
    """Deleting is allowed even with people waiting; the queue module registers a hook to handle them."""
    seen = []
    db.service_deleted_hooks.append(seen.append)
    try:
        sid = make(client, staff_headers).json()["id"]
        client.delete(f"/services/{sid}", headers=staff_headers)
    finally:
        db.service_deleted_hooks.remove(seen.append)
    assert [s.id for s in seen] == [sid] and seen[0].name == GOOD["name"]


def test_hooks_do_not_run_when_nothing_was_deleted(client, staff_headers):
    seen = []
    db.service_deleted_hooks.append(seen.append)
    try:
        client.delete("/services/9", headers=staff_headers)
    finally:
        db.service_deleted_hooks.remove(seen.append)
    assert seen == []


# ---------- seed data ----------

def test_seeding_creates_the_three_a2_services():
    seed_demo_services()
    services = db.list_services()
    assert [(s.name, s.duration, s.priority, s.open) for s in services] == [
        ("Password Reset", 10, "high", True),
        ("Wi-Fi / Network", 15, "medium", True),
        ("Printing", 5, "low", False),
    ]


def test_seeding_is_not_repeated():
    seed_demo_services()
    seed_demo_services()
    assert len(db.list_services()) == 3


def test_seeding_leaves_an_existing_catalogue_alone():
    db.add_service("Custom", "Mine.", 5, "low")
    seed_demo_services()
    assert [s.name for s in db.list_services()] == ["Custom"]


def test_startup_seeds_services():
    with TestClient(app) as c:
        tok = c.post("/auth/login", json={"email": "student@uh.edu", "password": "Password1"}).json()["access_token"]
        r = c.get("/services", headers={"Authorization": f"Bearer {tok}"})
    assert [s["name"] for s in r.json()] == ["Password Reset", "Wi-Fi / Network", "Printing"]
