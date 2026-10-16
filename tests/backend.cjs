'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { Activity } = require('../backend/activity.cjs');
const { dateRange } = require('../backend/validation.cjs');
const join = (overrides = {}) => ({ type: 'joined', participationId: 'visit-a', userId: 'alice', serviceId: 1, serviceName: 'Help Desk', position: 4, queueOpen: true, ...overrides });
const position = (value, queueOpen = true) => ({ type: 'position', participationId: 'visit-a', position: value, queueOpen });

test('join creates targeted notification and active history with server timestamps', t => {
  const joinedAt = Date.parse('2026-10-16T15:00:00Z');
  t.mock.method(Date, 'now', () => joinedAt);
  const activity = new Activity();
  activity.apply([join()]);
  const [notice] = activity.notifications.list('alice');
  assert.equal(notice.kind, 'joined');
  assert.match(notice.message, /position 4/);
  assert.equal(notice.read, false);
  assert.equal(activity.notifications.list('bob').length, 0);
  const [record] = activity.history.list('alice');
  assert.equal(record.outcome, 'Waiting');
  assert.equal(record.completedAt, null);
  assert.equal(record.joinedAt, joinedAt);
  assert.equal(notice.ts, joinedAt);
  assert.equal(record.serviceName, 'Help Desk');
  assert.equal(activity.history.list('bob').length, 0);
  record.outcome = 'Tampered'; notice.read = true;
  assert.equal(activity.history.list('alice')[0].outcome, 'Waiting');
  assert.equal(activity.notifications.list('alice')[0].read, false);
});

test('near-front notification fires once, waits for an open queue, and supports first-position joins', () => {
  const activity = new Activity();
  activity.apply([join(), position(3), position(2, false)]);
  assert.equal(activity.notifications.list('alice').length, 1);
  activity.apply([position(2), position(1), position(4), position(2)]);
  const reminders = activity.notifications.list('alice').filter(n => n.kind === 'close');
  assert.equal(reminders.length, 1);
  assert.match(reminders[0].message, /nearly next/);
  activity.apply([join({ participationId: 'visit-b', userId: 'bob', position: 1 })]);
  assert.match(activity.notifications.list('bob')[0].message, /You're next/);
});

for (const [type, outcome] of [['served', 'Served'], ['left', 'Left queue'], ['removed', 'Removed']]) {
  test(`${type} completes history, prevents double completion and permits a new visit`, () => {
    const activity = new Activity();
    activity.apply([join(), { type, participationId: 'visit-a' }]);
    const [record] = activity.history.list('alice');
    assert.equal(record.outcome, outcome);
    assert(record.completedAt >= record.joinedAt);
    assert.throws(() => activity.apply([{ type, participationId: 'visit-a' }]), { status: 409 });
    activity.apply([join({ participationId: 'visit-new', position: 1 })]);
    assert.equal(activity.history.list('alice').length, 2);
    assert.equal(activity.history.list('alice')[0].id, 'visit-new');
    assert.equal(activity.notifications.list('alice').filter(n => n.kind === 'close').length, 1);
  });
}

test('duplicate joins, overlapping visits and missing participations do not corrupt state', () => {
  const activity = new Activity();
  activity.apply([join()]);
  assert.throws(() => activity.apply([join()]), { status: 409 });
  assert.throws(() => activity.apply([join({ participationId: 'other' })]), { status: 409 });
  assert.throws(() => activity.apply([{ type: 'left', participationId: 'missing' }]), { status: 404 });
  assert.equal(activity.history.list('alice').length, 1);
});

test('failed batches roll back notifications, history and close-reminder state', () => {
  const activity = new Activity();
  activity.apply([join()]);
  assert.throws(() => activity.apply([position(2), { type: 'left', participationId: 'missing' }]), { status: 404 });
  assert.equal(activity.notifications.list('alice').length, 1);
  activity.apply([position(2)]);
  assert.equal(activity.notifications.list('alice').length, 2);
  assert.throws(() => activity.apply([join({ userId: 'bob', participationId: 'b' }), { type: 'served', participationId: 'missing' }]), { status: 404 });
  assert.equal(activity.history.list('bob').length, 0);
});

test('notification read/clear operations are limited to the requested recipient', () => {
  const activity = new Activity();
  activity.apply([join(), join({ participationId: 'b', userId: 'bob' })]);
  const id = activity.notifications.list('alice')[0].id;
  assert.throws(() => activity.notifications.markRead('bob', id), { status: 404 });
  assert.equal(activity.notifications.markRead('alice', id).read, true);
  activity.apply([position(2)]);
  activity.notifications.markAllRead('alice');
  assert(activity.notifications.list('alice').every(n => n.read));
  assert(activity.notifications.list('bob').every(n => !n.read));
  activity.notifications.clear('alice');
  assert.equal(activity.notifications.list('alice').length, 0);
  assert.equal(activity.notifications.list('bob').length, 1);
  assert.equal(activity.history.list('alice').length, 1);
});

test('required fields, types, limits, event names and batch sizes are validated', () => {
  const invalid = [null, [], 'event', {}, join({ type: 'unknown' }), join({ type: 'x'.repeat(21) }),
    join({ participationId: '' }), join({ participationId: 'x'.repeat(101) }), join({ userId: 8 }), join({ userId: 'x'.repeat(255) }),
    join({ serviceName: ' ' }), join({ serviceName: 'x'.repeat(101) }), join({ serviceId: '1' }), join({ serviceId: 0 }),
    join({ position: 1.2 }), join({ position: -1 }), join({ position: Number.MAX_SAFE_INTEGER + 1 }), join({ queueOpen: 'true' })];
  for (const value of invalid) assert.throws(() => new Activity().apply([value]), { status: 400 });
  for (const batch of [undefined, {}, [], Array(1001).fill(join())]) assert.throws(() => new Activity().apply(batch), { status: 400 });
  const activity = new Activity();
  activity.apply([join({ userId: ' x ', serviceName: ' Help ' })]);
  assert.equal(activity.history.list('x')[0].serviceName, 'Help');
});

test('history date filters include both day boundaries and filter by join time, not completion time', t => {
  let now = Date.parse('2026-10-15T23:59:59.999Z');
  t.mock.method(Date, 'now', () => now);
  const activity = new Activity();
  for (const [id, timestamp] of [
    ['before', '2026-10-15T23:59:59.999Z'],
    ['start', '2026-10-16T00:00:00.000Z'],
    ['end', '2026-10-16T23:59:59.999Z'],
    ['after', '2026-10-17T00:00:00.000Z']
  ]) {
    now = Date.parse(timestamp);
    activity.apply([join({ participationId: id })]);
    now = Date.parse('2026-10-18T12:00:00Z');
    activity.apply([{ type: 'served', participationId: id }]);
  }
  const ids = (from, to) => activity.history.list('alice', from, to).map(record => record.id);
  assert.deepEqual(ids('2026-10-16', '2026-10-16'), ['end', 'start']);
  assert.deepEqual(ids('2026-10-17', null), ['after']);
  assert.deepEqual(ids(null, '2026-10-15'), ['before']);
  assert.deepEqual(ids('2026-10-18', '2026-10-18'), []);
  assert.equal(dateRange(null, null).start, null);
  for (const [from, to] of [['2026-02-30', null], ['2026-13-01', null], ['', null], ['today', null], ['2026-10-17', '2026-10-16']]) {
    assert.throws(() => activity.history.list('alice', from, to), { status: 400 });
  }
});

test('completion preserves the original visit details and records the exact completion time', t => {
  const joinedAt = Date.parse('2026-10-16T15:00:00Z');
  const completedAt = joinedAt + 10 * 60 * 1000;
  let now = joinedAt;
  t.mock.method(Date, 'now', () => now);
  const activity = new Activity();
  activity.apply([join()]);
  now = completedAt;
  activity.apply([{ type: 'served', participationId: 'visit-a' }]);
  const [record] = activity.history.list('alice');
  assert.deepEqual(record, { id: 'visit-a', userId: 'alice', serviceId: 1, serviceName: 'Help Desk',
    joinedAt, completedAt, date: completedAt, outcome: 'Served' });
  assert.throws(() => activity.apply([position(1)]), { status: 409 });
  assert.equal(activity.notifications.list('alice').length, 1);
});

test('valid maximum lengths are accepted and one extra character is rejected', () => {
  const activity = new Activity();
  const valid = join({ participationId: 'p'.repeat(100), userId: 'u'.repeat(254), serviceName: 's'.repeat(100) });
  activity.apply([valid]);
  assert.equal(activity.history.list(valid.userId)[0].serviceName, valid.serviceName);
  for (const field of ['participationId', 'userId', 'serviceName']) {
    assert.throws(() => new Activity().apply([{ ...valid, [field]: valid[field] + 'x' }]), { status: 400 });
  }
});

test('clearing messages does not retrigger a near-front reminder, but a new visit can', () => {
  const activity = new Activity();
  activity.apply([join({ position: 1 })]);
  activity.notifications.clear('alice');
  activity.apply([position(4), position(1)]);
  assert.deepEqual(activity.notifications.list('alice'), []);
  activity.apply([{ type: 'left', participationId: 'visit-a' }, join({ participationId: 'next-visit', position: 2 })]);
  assert.deepEqual(activity.notifications.list('alice').map(n => n.kind).sort(), ['close', 'joined']);
});

test('a failed mixed batch restores already-completed visits and all recipient messages', () => {
  const activity = new Activity();
  activity.apply([join(), join({ participationId: 'b', userId: 'bob', position: 2 })]);
  const before = { history: activity.history.list('alice'), alice: activity.notifications.list('alice'), bob: activity.notifications.list('bob') };
  assert.throws(() => activity.apply([
    { type: 'served', participationId: 'visit-a' },
    join({ participationId: 'second', position: 1 }),
    { type: 'left', participationId: 'missing' }
  ]), { status: 404 });
  assert.deepEqual(activity.history.list('alice'), before.history);
  assert.deepEqual(activity.notifications.list('alice'), before.alice);
  assert.deepEqual(activity.notifications.list('bob'), before.bob);
});
