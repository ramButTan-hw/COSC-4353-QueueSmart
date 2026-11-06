from sqlalchemy import select

from app import database
from app.tables.queue import QueueEntryTable, QueueTable


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


def open_queue(client, staff_headers, service_id):
    response = client.post(
        f"/queues/{service_id}/open",
        headers=staff_headers,
    )
    assert response.status_code == 200


def test_open_and_close_are_saved_to_database(
    client,
    staff_headers,
):
    service_id = create_service(client, staff_headers)

    open_queue(client, staff_headers, service_id)

    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).one()

        assert queue.status == "open"

    response = client.post(
        f"/queues/{service_id}/close",
        headers=staff_headers,
    )
    assert response.status_code == 200

    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).one()

        assert queue.status == "closed"


def test_join_is_saved_as_waiting(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_queue(client, staff_headers, service_id)

    response = client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    assert response.status_code == 201
    user_id = response.json()["user_id"]

    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).one()

        entry = session.scalars(
            select(QueueEntryTable).where(
                QueueEntryTable.queue_id == queue.id,
                QueueEntryTable.user_id == user_id,
            )
        ).one()

        assert entry.status == "waiting"
        assert entry.position == 1
        assert entry.join_time is not None


def test_leave_is_saved_as_canceled(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_queue(client, staff_headers, service_id)

    joined = client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    user_id = joined.json()["user_id"]

    response = client.delete(
        f"/queues/{service_id}/leave",
        headers=student_headers,
    )

    assert response.status_code == 204

    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).one()

        entry = session.scalars(
            select(QueueEntryTable).where(
                QueueEntryTable.queue_id == queue.id,
                QueueEntryTable.user_id == user_id,
            )
        ).one()

        assert entry.status == "canceled"


def test_serve_is_saved_as_served(
    client,
    student_headers,
    staff_headers,
):
    service_id = create_service(client, staff_headers)
    open_queue(client, staff_headers, service_id)

    joined = client.post(
        f"/queues/{service_id}/join",
        headers=student_headers,
    )

    user_id = joined.json()["user_id"]

    response = client.post(
        f"/queues/{service_id}/serve-next",
        headers=staff_headers,
    )

    assert response.status_code == 200

    with database.SessionLocal() as session:
        queue = session.scalars(
            select(QueueTable).where(
                QueueTable.service_id == service_id
            )
        ).one()

        entry = session.scalars(
            select(QueueEntryTable).where(
                QueueEntryTable.queue_id == queue.id,
                QueueEntryTable.user_id == user_id,
            )
        ).one()

        assert entry.status == "served"