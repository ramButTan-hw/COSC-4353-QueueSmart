"""Estimates use the shared queue's current ordering and service duration."""
import pytest

from app.models import User
from app.security import create_access_token
from app.store import db
from app.wait_time import estimate_wait_minutes


@pytest.mark.parametrize(('position', 'duration', 'expected'), [
    (0, 10, 0), (-1, 10, 0), (1, 10, 10), (3, 10, 30), (2, 15, 30), (4, 480, 1920),
])
def test_basic_estimate(position, duration, expected):
    assert estimate_wait_minutes(position, duration) == expected


@pytest.fixture
def queue_users():
    db.add_service('Help', 'Help desk', 10, 'medium', open=True)
    headers = {}
    for name in ('alice', 'bob', 'charlie', 'staff'):
        user = User(name, name, name + '@uh.edu', 'unused', 'staff' if name == 'staff' else 'student')
        db.add_user(user)
        token, _ = create_access_token(user)
        headers[name] = {'Authorization': 'Bearer ' + token}
    return headers


def join(client, users, name):
    result = client.post('/queues/1/join', headers=users[name])
    assert result.status_code == 201
    return result.json()


def summary(client, users, name):
    result = client.get('/queues', headers=users[name])
    assert result.status_code == 200
    return result.json()[0]


def test_empty_preview_join_and_private_position_estimate(client, queue_users):
    users = queue_users
    assert summary(client, users, 'alice')['estimated_wait_minutes'] == 10
    assert join(client, users, 'alice')['estimated_wait_minutes'] == 10
    assert summary(client, users, 'bob')['estimated_wait_minutes'] == 20
    assert join(client, users, 'bob')['estimated_wait_minutes'] == 20
    private = summary(client, users, 'bob')
    assert len(private['entries']) == 1
    assert private['entries'][0]['estimated_wait_minutes'] == 20
    staff = client.get('/queues/1', headers=users['staff']).json()
    assert [e['estimated_wait_minutes'] for e in staff['entries']] == [10, 20]
    assert staff['estimated_wait_minutes'] == 30


@pytest.mark.parametrize('action', ['leave', 'serve', 'remove'])
def test_departures_reduce_remaining_estimates(client, queue_users, action):
    users = queue_users
    for name in ('alice', 'bob', 'charlie'):
        join(client, users, name)
    if action == 'leave':
        result = client.delete('/queues/1/leave', headers=users['alice'])
    elif action == 'serve':
        result = client.post('/queues/1/serve-next', headers=users['staff'])
    else:
        result = client.delete('/queues/1/members/alice', headers=users['staff'])
    assert result.status_code in (200, 204)
    assert summary(client, users, 'bob')['entries'][0]['estimated_wait_minutes'] == 10
    assert summary(client, users, 'charlie')['entries'][0]['estimated_wait_minutes'] == 20
    assert summary(client, users, 'staff')['estimated_wait_minutes'] == 30


def test_move_and_duration_update_recompute_estimates(client, queue_users):
    users = queue_users
    join(client, users, 'alice')
    join(client, users, 'bob')
    moved = client.post('/queues/1/move', headers=users['staff'], json={'user_id': 'bob', 'direction': 'up'})
    assert moved.status_code == 200
    assert [(e['user_id'], e['estimated_wait_minutes']) for e in moved.json()['entries']] == [('bob', 10), ('alice', 20)]
    assert client.patch('/services/1', headers=users['staff'], json={'duration': 7}).status_code == 200
    assert summary(client, users, 'alice')['entries'][0]['estimated_wait_minutes'] == 14
    assert summary(client, users, 'staff')['estimated_wait_minutes'] == 21
    # Existing backend validation protects the calculation from invalid durations.
    assert client.patch('/services/1', headers=users['staff'], json={'duration': 0}).status_code == 422
    assert summary(client, users, 'alice')['entries'][0]['estimated_wait_minutes'] == 14


def test_preview_accounts_for_priority_changes_before_joining(client, queue_users):
    users = queue_users
    join(client, users, 'alice')
    assert client.patch('/services/1', headers=users['staff'], json={'priority': 'high'}).status_code == 200
    assert summary(client, users, 'bob')['estimated_wait_minutes'] == 10
    assert join(client, users, 'bob')['estimated_wait_minutes'] == 10
    assert summary(client, users, 'alice')['entries'][0]['estimated_wait_minutes'] == 20
    # Equal-priority arrivals stay behind Bob but ahead of Alice.
    assert summary(client, users, 'charlie')['estimated_wait_minutes'] == 20
    assert join(client, users, 'charlie')['estimated_wait_minutes'] == 20
    assert summary(client, users, 'alice')['entries'][0]['estimated_wait_minutes'] == 30
