"""Tests for the Assignment 4 Queue database table."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import database
from app.tables.queue import QueueTable
from app.tables.service import ServiceTable


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