"""Tests for the Assignment 4 Queue database table."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import database
from app.tables.queue import QueueEntryTable, QueueTable
from app.tables.service import ServiceTable
from app.tables.credentials import UserCredentials


def add_service(session):
    service = ServiceTable(
        name="Advising",
        description="Academic advising service.",
        duration=15,
        priority="medium",
        is_open=False,
    )
    session.add(service)
    session.flush()
    return service

def add_user(session, user_id="student-1"):
    user = UserCredentials(
        id=user_id,
        email=f"{user_id}@uh.edu",
        password_hash="hashed-password",
        role="student",
    )
    session.add(user)
    session.flush()
    return user

def test_queue_can_be_created_for_service():
    with database.SessionLocal() as session:
        service = add_service(session)

        queue = QueueTable(
            service_id=service.id,
            status="open",
        )

        session.add(queue)
        session.commit()

        assert queue.id is not None
        assert queue.service_id == service.id
        assert queue.status == "open"
        assert queue.created_at is not None


def test_queue_defaults_to_closed():
    with database.SessionLocal() as session:
        service = add_service(session)

        queue = QueueTable(service_id=service.id)

        session.add(queue)
        session.commit()

        assert queue.status == "closed"


@pytest.mark.parametrize("status", ["waiting", "OPEN", "", "invalid"])
def test_queue_rejects_invalid_status(status):
    with database.SessionLocal() as session:
        service = add_service(session)

        session.add(
            QueueTable(
                service_id=service.id,
                status=status,
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()


def test_queue_requires_a_real_service():
    with database.SessionLocal() as session:
        session.add(
            QueueTable(
                service_id=999999,
                status="open",
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()


def test_service_can_only_have_one_queue():
    with database.SessionLocal() as session:
        service = add_service(session)

        session.add(
            QueueTable(
                service_id=service.id,
                status="open",
            )
        )
        session.commit()

        session.add(
            QueueTable(
                service_id=service.id,
                status="closed",
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()


def test_deleting_service_deletes_its_queue():
    with database.SessionLocal() as session:
        service = add_service(session)

        session.add(
            QueueTable(
                service_id=service.id,
                status="open",
            )
        )
        session.commit()

        session.delete(service)
        session.commit()

        count = session.scalar(
            select(func.count()).select_from(QueueTable)
        )

        assert count == 0

def test_queue_entry_can_be_created():
    with database.SessionLocal() as session:
        service = add_service(session)
        user = add_user(session)

        queue = QueueTable(
            service_id=service.id,
            status="open",
        )
        session.add(queue)
        session.flush()

        entry = QueueEntryTable(
            queue_id=queue.id,
            user_id=user.id,
            position=1,
            status="waiting",
        )

        session.add(entry)
        session.commit()

        assert entry.id is not None
        assert entry.queue_id == queue.id
        assert entry.user_id == user.id
        assert entry.position == 1
        assert entry.status == "waiting"
        assert entry.join_time is not None


def test_queue_entry_defaults_to_waiting():
    with database.SessionLocal() as session:
        service = add_service(session)
        user = add_user(session)

        queue = QueueTable(service_id=service.id)
        session.add(queue)
        session.flush()

        entry = QueueEntryTable(
            queue_id=queue.id,
            user_id=user.id,
            position=1,
        )

        session.add(entry)
        session.commit()

        assert entry.status == "waiting"


@pytest.mark.parametrize(
    "status",
    ["open", "closed", "left", "", "WAITING"],
)
def test_queue_entry_rejects_invalid_status(status):
    with database.SessionLocal() as session:
        service = add_service(session)
        user = add_user(session)

        queue = QueueTable(service_id=service.id)
        session.add(queue)
        session.flush()

        session.add(
            QueueEntryTable(
                queue_id=queue.id,
                user_id=user.id,
                position=1,
                status=status,
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()


@pytest.mark.parametrize("position", [0, -1, -10])
def test_queue_entry_requires_positive_position(position):
    with database.SessionLocal() as session:
        service = add_service(session)
        user = add_user(session)

        queue = QueueTable(service_id=service.id)
        session.add(queue)
        session.flush()

        session.add(
            QueueEntryTable(
                queue_id=queue.id,
                user_id=user.id,
                position=position,
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()


def test_queue_entry_requires_real_queue():
    with database.SessionLocal() as session:
        user = add_user(session)

        session.add(
            QueueEntryTable(
                queue_id=999999,
                user_id=user.id,
                position=1,
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()


def test_queue_entry_requires_real_user():
    with database.SessionLocal() as session:
        service = add_service(session)

        queue = QueueTable(service_id=service.id)
        session.add(queue)
        session.flush()

        session.add(
            QueueEntryTable(
                queue_id=queue.id,
                user_id="does-not-exist",
                position=1,
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()


def test_deleting_queue_deletes_queue_entries():
    with database.SessionLocal() as session:
        service = add_service(session)
        user = add_user(session)

        queue = QueueTable(service_id=service.id)
        session.add(queue)
        session.flush()

        session.add(
            QueueEntryTable(
                queue_id=queue.id,
                user_id=user.id,
                position=1,
            )
        )
        session.commit()

        session.delete(queue)
        session.commit()

        count = session.scalar(
            select(func.count()).select_from(QueueEntryTable)
        )

        assert count == 0


def test_queue_entry_persists_across_sessions():
    with database.SessionLocal() as session:
        service = add_service(session)
        user = add_user(session)

        queue = QueueTable(
            service_id=service.id,
            status="open",
        )
        session.add(queue)
        session.flush()

        entry = QueueEntryTable(
            queue_id=queue.id,
            user_id=user.id,
            position=1,
        )

        session.add(entry)
        session.commit()

        entry_id = entry.id

    with database.SessionLocal() as session:
        saved = session.get(QueueEntryTable, entry_id)

        assert saved is not None
        assert saved.user_id == "student-1"
        assert saved.position == 1
        assert saved.status == "waiting"