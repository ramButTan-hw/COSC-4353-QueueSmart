from app.store import db


SERVICE = {
    "name": "Academic Advising",
    "description": "Student advising service.",
    "duration": 15,
    "priority": "medium",
}


def create_service(client, staff_headers):
    response = client.post(
        "/services",
        json=SERVICE,
        headers=staff_headers,
    )

    assert response.status_code == 201

    return response.json()["id"]


def open_service(client, staff_headers, service_id):
    response = client.post(
        f"/queues/{service_id}/open",
        headers=staff_headers,
    )

    assert response.status_code == 200


def test_student_can_join_open_queue(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_service(client, staff_headers, service_id)

    response = client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    assert response.status_code == 201
    assert response.json()["service_id"] == service_id
    assert response.json()["position"] == 1


def test_student_cannot_join_closed_queue(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)

    response = client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "queue_closed"


def test_student_cannot_join_twice(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_service(client, staff_headers, service_id)

    first = client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    second = client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "already_in_queue"


def test_student_can_leave_queue(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_service(client, staff_headers, service_id)

    client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    response = client.delete(
        f"/queues/{service_id}/leave",
        headers=student_headers,
    )

    assert response.status_code == 204
    assert db.get_queue(service_id) == []


def test_cannot_leave_when_not_in_queue(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)

    response = client.delete(
        f"/queues/{service_id}/leave",
        headers=student_headers,
    )

    assert response.status_code == 404


def test_staff_can_view_queue(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_service(client, staff_headers, service_id)

    client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    response = client.get(
        f"/queues/{service_id}",
        headers=staff_headers,
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert len(response.json()["entries"]) == 1


def test_student_cannot_view_queue_as_admin(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)

    response = client.get(
        f"/queues/{service_id}",
        headers=student_headers,
    )

    assert response.status_code == 403


def test_staff_can_serve_next(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_service(client, staff_headers, service_id)

    client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    response = client.post(
        f"/queues/{service_id}/serve-next",
        headers=staff_headers,
    )

    assert response.status_code == 200
    assert response.json()["position"] == 1
    assert db.get_queue(service_id) == []


def test_serve_next_empty_queue_returns_error(
    client,
    staff_headers,
):
    service_id = create_service(client, staff_headers)

    response = client.post(
        f"/queues/{service_id}/serve-next",
        headers=staff_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "queue_empty"


def test_same_priority_uses_arrival_order():
    first = db.add_queue_entry(
        1,
        "user-1",
        "medium",
        100.0,
    )

    second = db.add_queue_entry(
        1,
        "user-2",
        "medium",
        200.0,
    )

    ordered = db.ordered_queue(1)

    assert ordered == [first, second]


def test_priority_order():
    low = db.add_queue_entry(
        1,
        "low-user",
        "low",
        100.0,
    )

    high = db.add_queue_entry(
        1,
        "high-user",
        "high",
        200.0,
    )

    medium = db.add_queue_entry(
        1,
        "medium-user",
        "medium",
        150.0,
    )

    ordered = db.ordered_queue(1)

    assert ordered == [
        high,
        medium,
        low,
    ]


def test_staff_can_open_and_close_queue(
    client,
    staff_headers,
):
    service_id = create_service(client, staff_headers)

    opened = client.post(
        f"/queues/{service_id}/open",
        headers=staff_headers,
    )

    assert opened.status_code == 200
    assert opened.json()["open"] is True

    closed = client.post(
        f"/queues/{service_id}/close",
        headers=staff_headers,
    )

    assert closed.status_code == 200
    assert closed.json()["open"] is False


def test_deleting_service_clears_queue(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_service(client, staff_headers, service_id)

    client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    assert len(db.get_queue(service_id)) == 1

    response = client.delete(
        f"/services/{service_id}",
        headers=staff_headers,
    )

    assert response.status_code == 204
    assert db.get_queue(service_id) == []