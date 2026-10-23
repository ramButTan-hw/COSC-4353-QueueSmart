"""Real queues, notifications, and history must agree and enforce the same identity."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.errors import ApiError
from app.main import app
from app.models import User
from app.security import create_access_token
from app.store import db, seed_demo_services


@pytest.fixture
def users():
    seed_demo_services()
    result = {}
    for name in ('alice', 'bob', 'charlie', 'staff'):
        user = User(name, name.title(), name + '@uh.edu', 'unused', 'staff' if name == 'staff' else 'student')
        db.add_user(user)
        token, _ = create_access_token(user)
        result[name] = {'Authorization': 'Bearer ' + token}
    return result


def join(client, users, name='alice', service=1):
    r = client.post(f'/queues/{service}/join', headers=users[name])
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize(('method', 'path'), [('get', '/queues'), ('get', '/api/history'),
    ('get', '/api/notifications'), ('delete', '/api/notifications'),
    ('post', '/api/notifications/read-all'), ('patch', '/api/notifications/x/read'), ('post', '/queues/1/join')])
def test_real_authentication_required(client, method, path):
    r = getattr(client, method)(path, headers={'X-QueueSmart-User': 'alice'})
    assert r.status_code == 401 and r.json()['error']['code'] == 'unauthorized'


def test_join_leave_private_history_and_near_front_reminders(client, users):
    first = join(client, users)
    join(client, users, 'bob')
    join(client, users, 'charlie')
    assert len(client.get('/api/notifications', headers=users['charlie']).json()) == 1
    summary = client.get('/queues', headers=users['charlie']).json()[0]
    assert summary['count'] == 3 and len(summary['entries']) == 1
    assert summary['entries'][0]['user_id'] == 'charlie' and summary['entries'][0]['position'] == 3
    assert client.delete('/queues/1/leave', headers=users['alice']).status_code == 204
    notices = client.get('/api/notifications', headers=users['charlie'])
    assert notices.headers['cache-control'] == 'no-store'
    assert [n['kind'] for n in notices.json()] == ['close', 'joined']
    history = client.get('/api/history?userId=bob', headers={**users['alice'], 'X-QueueSmart-User': 'bob'}).json()
    assert len(history) == 1 and history[0]['userId'] == 'alice'
    assert history[0]['outcome'] == 'Left queue' and history[0]['joinedAt'] == int(first['joined_at'] * 1000)
    assert 'closeNotified' not in history[0] and 'position' not in history[0]


def test_read_clear_isolation_and_rejoin(client, users):
    join(client, users)
    join(client, users, 'bob')
    notice = client.get('/api/notifications', headers=users['alice']).json()[0]
    path = f"/api/notifications/{notice['id']}/read"
    assert client.patch(path, headers=users['bob']).status_code == 404
    assert client.patch(path, headers=users['alice']).json()['read'] is True
    client.post('/api/notifications/read-all', headers=users['alice'])
    assert all(n['read'] for n in client.get('/api/notifications', headers=users['alice']).json())
    client.delete('/api/notifications', headers=users['alice'])
    assert client.get('/api/notifications', headers=users['alice']).json() == []
    assert len(client.get('/api/notifications', headers=users['bob']).json()) == 2
    assert client.post('/queues/2/join', headers=users['alice']).status_code == 409
    assert db.get_queue(2) == []
    client.delete('/queues/1/leave', headers=users['alice'])
    join(client, users)
    visits = client.get('/api/history', headers=users['alice']).json()
    assert [v['outcome'] for v in visits] == ['Waiting', 'Left queue']
    assert visits[0]['id'] != visits[1]['id']


def test_serve_remove_delete_complete_history(client, users):
    for name in ('alice', 'bob', 'charlie'):
        join(client, users, name)
    served = client.post('/queues/1/serve-next', headers=users['staff'])
    assert served.status_code == 200 and served.json()['user_id'] == 'alice'
    assert len(db.get_queue(1)) == 2
    assert client.delete('/queues/1/members/bob', headers=users['staff']).status_code == 204
    assert client.delete('/services/1', headers=users['staff']).status_code == 204
    assert db.get_queue(1) == []
    for name, outcome in (('alice', 'Served'), ('bob', 'Removed'), ('charlie', 'Removed')):
        visit = client.get('/api/history', headers=users[name]).json()[0]
        assert visit['outcome'] == outcome and visit['completedAt'] >= visit['joinedAt']
        notices = client.get('/api/notifications', headers=users[name]).json()
        assert notices[0]['kind'] == ('served' if name == 'alice' else 'removed')
        assert all(n['recipientId'] == name for n in notices)


def test_pause_move_and_priority_preserve_timestamps_and_single_reminder(client, users):
    first = join(client, users)
    join(client, users, 'bob')
    join(client, users, 'charlie')
    client.post('/queues/1/close', headers=users['staff'])
    assert client.post('/queues/1/serve-next', headers=users['staff']).status_code == 409
    client.delete('/queues/1/leave', headers=users['bob'])
    # while paused charlie hears the queue closed and that he moved up, but the "head to the help desk" reminder waits
    assert [n['kind'] for n in client.get('/api/notifications', headers=users['charlie']).json()] == ['moved', 'queue_closed', 'joined']
    client.post('/queues/1/open', headers=users['staff'])
    assert len([n for n in client.get('/api/notifications', headers=users['charlie']).json() if n['kind'] == 'close']) == 1
    moved = client.post('/queues/1/move', headers=users['staff'], json={'user_id': 'alice', 'direction': 'down'})
    assert moved.status_code == 200
    assert [e['user_id'] for e in moved.json()['entries']] == ['charlie', 'alice']
    assert moved.json()['entries'][1]['joined_at'] == first['joined_at']
    # one reminder per level: "nearly next" at position 2 (sent on opening), then "next" when he reaches position 1
    assert len([n for n in client.get('/api/notifications', headers=users['charlie']).json() if n['kind'] == 'close']) == 2
    db.find_queue_entry(1, 'alice').priority = 'high'
    db.find_queue_entry(1, 'charlie').priority = 'low'
    assert client.post('/queues/1/move', headers=users['staff'], json={'user_id': 'alice', 'direction': 'down'}).status_code == 409


@pytest.mark.parametrize(('method', 'path', 'body'), [('post', '/queues/1/serve-next', None),
    ('post', '/queues/1/close', None), ('delete', '/queues/1/members/bob', None),
    ('post', '/queues/1/move', {'user_id': 'bob', 'direction': 'up'})])
def test_students_cannot_mutate_other_participants(client, users, method, path, body):
    join(client, users, 'bob')
    r = client.request(method.upper(), path, headers=users['alice'], json=body)
    assert r.status_code == 403
    assert db.get_queue(1)[0].user_id == 'bob'
    assert client.get('/api/history', headers=users['bob']).json()[0]['outcome'] == 'Waiting'


@pytest.mark.parametrize('body', [{}, {'user_id': 5, 'direction': 'up'},
    {'user_id': 'x' * 255, 'direction': 'up'}, {'user_id': 'alice', 'direction': 'sideways'},
    {'user_id': 'alice', 'direction': 'up', 'extra': True}])
def test_move_validation(client, users, body):
    r = client.post('/queues/1/move', headers=users['staff'], json=body)
    assert r.status_code == 422 and r.json()['error']['code'] == 'validation_error'


@pytest.mark.parametrize(('method', 'path', 'actor'), [('post', '/queues/2/join', 'bob'),
    ('post', '/queues/1/serve-next', 'staff'), ('post', '/queues/1/close', 'staff'), ('delete', '/services/1', 'staff')])
def test_failure_rolls_back_all_modules(client, users, monkeypatch, method, path, actor):
    join(client, users)
    before = deepcopy((db.queues, db.services, db._next_queue_entry_id, db.activity.history.records, db.activity.notifications.items))
    original = db.activity.apply
    def fail_after_write(events):
        original(events)
        raise ApiError(409, 'conflict', 'Injected failure')
    monkeypatch.setattr(db.activity, 'apply', fail_after_write)
    assert client.request(method.upper(), path, headers=users[actor]).status_code == 409
    assert (db.queues, db.services, db._next_queue_entry_id, db.activity.history.records, db.activity.notifications.items) == before


def test_legacy_bridge_cannot_create_fake_activity(client, users):
    assert client.post('/api/queue-events', headers=users['alice'], json={'events': []}).status_code == 404
    assert db.activity.history.records == {}


def test_invalid_dates_and_reset(client, users):
    join(client, users)
    for query in ('from=bad', 'from=2026-02-30', 'from=2026-10-17&to=2026-10-16'):
        assert client.get('/api/history?' + query, headers=users['alice']).status_code == 422
    db.reset()
    assert db.activity.history.records == {} and db.queues == {}
    assert client.get('/api/history', headers=users['alice']).status_code == 401


def test_actual_login_and_public_ui():
    with TestClient(app) as client:
        login = client.post('/auth/login', json={'email': 'student@uh.edu', 'password': 'Password1'}).json()
        headers = {'Authorization': 'Bearer ' + login['access_token']}
        assert client.post('/queues/1/join', headers=headers).status_code == 201
        assert len(client.get('/api/history', headers=headers).json()) == 1
        for path in ('/', '/front%20page.html', '/history.html', '/js/backend.js', '/css/user.css'):
            assert client.get(path).status_code == 200
        for path in ('/backend/app/security.py', '/.git/config', '/missing.html'):
            assert client.get(path).status_code == 404
