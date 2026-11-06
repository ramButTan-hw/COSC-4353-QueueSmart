"""Regression tests for the queue, service and activity database integration."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from unittest.mock import patch

from app import database, queue_database, queue_activity
from app.errors import ApiError
from app.main import create_app
from app.store import db
from app.tables.activity import HistoryRecord, NotificationRecord
from app.tables.queue import QueueEntryTable, QueueTable
from app.tables.service import ServiceTable


def login(client, email):
    response = client.post('/auth/login', json={'email': email, 'password': 'Password1'})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


@pytest.fixture
def disk_db(tmp_path):
    url = f"sqlite:///{(tmp_path / 'merged.db').as_posix()}"
    database.configure(url)
    try:
        yield url
    finally:
        db.reset()
        database.configure('sqlite://')
        database.reset_database()


def test_restart_preserves_services_queue_order_status_and_history(disk_db):
    with TestClient(create_app()) as client:
        student = login(client, 'student@uh.edu')
        staff = login(client, 'admin@uh.edu')
        client.post('/auth/register', json={'name': 'Second Student', 'email': 'second@uh.edu', 'password': 'Password1'})
        second = login(client, 'second@uh.edu')
        service = client.post('/services', headers=staff, json={
            'name': 'Custom Desk', 'description': 'Initial description', 'duration': 20, 'priority': 'medium',
        }).json()
        sid = service['id']
        assert client.patch(f'/services/{sid}', headers=staff, json={'description': 'Updated description', 'duration': 25}).status_code == 200
        assert client.post(f'/queues/{sid}/open', headers=staff).status_code == 200
        first_join = client.post(f'/queues/{sid}/join', headers=student).json()
        second_join = client.post(f'/queues/{sid}/join', headers=second).json()
        assert client.post(f'/queues/{sid}/move', headers=staff, json={'user_id': second_join['user_id'], 'direction': 'up'}).status_code == 200
        assert client.post(f'/queues/{sid}/close', headers=staff).status_code == 200
        before = client.get(f'/queues/{sid}', headers=staff).json()
        history = client.get('/api/history', headers=student).json()
        notices = client.get('/api/notifications', headers=student).json()
    db.reset()
    database.configure(disk_db)
    with TestClient(create_app()) as client:
        assert client.get(f'/queues/{sid}', headers=staff).json() == before
        saved_service = client.get(f'/services/{sid}', headers=staff).json()
        assert saved_service['description'] == 'Updated description' and saved_service['duration'] == 25
        assert client.get('/api/history', headers=student).json() == history
        assert client.get('/api/notifications', headers=student).json() == notices
        assert client.post(f'/queues/{sid}/serve-next', headers=staff).status_code == 409
        client.post(f'/queues/{sid}/open', headers=staff)
        served = client.post(f'/queues/{sid}/serve-next', headers=staff)
        assert served.json()['user_id'] == second_join['user_id']
        assert client.get('/api/history', headers=second).json()[0]['outcome'] == 'Served'
        client.delete(f'/queues/{sid}/leave', headers=student)
        new_join = client.post(f'/queues/{sid}/join', headers=student)
        assert new_join.status_code == 201
        assert new_join.json()['id'] > max(first_join['id'], second_join['id'])


@pytest.mark.parametrize('operation', ['join', 'leave', 'close', 'delete', 'create', 'update'])
def test_commit_failure_rolls_back_every_module(disk_db, operation):
    with TestClient(create_app()) as client:
        student = login(client, 'student@uh.edu')
        staff = login(client, 'admin@uh.edu')
        if operation != 'join':
            assert client.post('/queues/1/join', headers=student).status_code == 201
        def snapshot():
            with database.SessionLocal() as session:
                return [list(session.execute(select(*model.__table__.columns).order_by(model.__table__.primary_key.columns.values()[0])).all())
                        for model in (ServiceTable, QueueTable, QueueEntryTable, HistoryRecord, NotificationRecord)]
        before = snapshot()
        before_api = client.get('/queues', headers=staff).json()
        def fail(session, *args):
            session.flush()
            raise ApiError(409, 'conflict', 'Injected commit failure')
        with patch.object(database, 'commit', fail):
            if operation == 'join':
                result = client.post('/queues/1/join', headers=student)
            elif operation == 'leave':
                result = client.delete('/queues/1/leave', headers=student)
            elif operation == 'close':
                result = client.post('/queues/1/close', headers=staff)
            elif operation == 'delete':
                result = client.delete('/services/1', headers=staff)
            elif operation == 'update':
                result = client.patch('/services/1', headers=staff, json={'name': 'Renamed'})
            else:
                result = client.post('/services', headers=staff, json={'name': 'New Desk', 'description': 'Help', 'duration': 5, 'priority': 'low'})
        assert result.status_code == 409
        assert snapshot() == before
        assert client.get('/queues', headers=staff).json() == before_api


def test_deleted_service_stays_deleted_and_history_survives(disk_db):
    with TestClient(create_app()) as client:
        student = login(client, 'student@uh.edu')
        staff = login(client, 'admin@uh.edu')
        client.post('/queues/1/join', headers=student)
        assert client.delete('/services/1', headers=staff).status_code == 204
        with database.SessionLocal() as session:
            assert session.get(ServiceTable, 1) is None
            assert session.scalar(select(QueueTable)) is None
            assert session.scalar(select(QueueEntryTable)) is None
        assert client.get('/api/history', headers=student).json()[0]['outcome'] == 'Removed'
    db.reset()
    database.configure(disk_db)
    with TestClient(create_app()) as client:
        assert client.get('/services/1', headers=staff).status_code == 404
        assert client.get('/api/history', headers=student).json()[0]['serviceName'] == 'Password Reset'


@pytest.mark.parametrize('outcome', ['Waiting', 'Served', None])
def test_upgrade_preserves_legacy_queue_rows_and_reconciles_history(outcome):
    database.init_db()
    uid = '11111111-1111-4111-8111-111111111111'
    with database.SessionLocal() as session:
        session.add(QueueTable(id=1, service_id=1, status='open'))
        session.flush()
        session.add(QueueEntryTable(id=1, queue_id=1, user_id=uid, position=1, status='waiting'))
        if outcome:
            session.add(HistoryRecord(id='queue-legacy-1', user_id=uid, service_id=1, service_name='Password Reset',
                                      joined_at=1000, completed_at=None if outcome == 'Waiting' else 2000,
                                      outcome=outcome, position=1, queue_open=True, close_notified=True, next_notified=True))
        session.commit()
    with database.engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE queue_entry DROP COLUMN participation_id')
        connection.exec_driver_sql('ALTER TABLE queue_entry DROP COLUMN priority')
    db.reset()
    database.init_db()
    queue_database.restore_store()
    queue_activity.recover_interrupted_visits()
    database.init_db()  # upgrade must also be safe on subsequent starts
    with database.SessionLocal() as session:
        row = session.get(QueueEntryTable, 1)
        assert row is not None
        if outcome == 'Served':
            assert row.status == 'served' and db.get_queue(1) == []
        else:
            assert len(db.get_queue(1)) == 1
            assert row.participation_id
            assert row.priority == 'high'
            if outcome:
                assert row.participation_id == 'queue-legacy-1'
            assert session.scalar(select(HistoryRecord.outcome)) == 'Waiting'
