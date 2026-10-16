'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('../backend/server.cjs');

async function setup(t) {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  const request = (route, options = {}) => fetch(base + route, { ...options, headers: { 'X-QueueSmart-User': 'alice', ...options.headers } });
  return { base, request };
}
const event = { type: 'joined', participationId: 'a', userId: 'alice', serviceId: 1, serviceName: 'Help Desk', position: 1, queueOpen: true };

test('REST notification/history lifecycle and recipient isolation', async t => {
  const { request } = await setup(t);
  const post = await request('/api/queue-events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ events: [event] }) });
  assert.equal(post.status, 200);
  assert.equal((await post.json()).processed, 1);
  const items = await (await request('/api/notifications')).json();
  assert.equal(items.length, 2);
  assert.equal((await (await request('/api/history')).json())[0].outcome, 'Waiting');
  assert.deepEqual(await (await request('/api/history', { headers: { 'X-QueueSmart-User': 'bob' } })).json(), []);
  assert.equal((await request(`/api/notifications/${items[0].id}/read`, { method: 'PATCH', headers: { 'X-QueueSmart-User': 'bob' } })).status, 404);
  assert.equal((await (await request(`/api/notifications/${items[0].id}/read`, { method: 'PATCH' })).json()).read, true);
  assert.equal((await request('/api/notifications/read-all', { method: 'POST' })).status, 200);
  assert((await (await request('/api/notifications')).json()).every(n => n.read));
  assert.equal((await request('/api/notifications', { method: 'DELETE' })).status, 200);
  assert.deepEqual(await (await request('/api/notifications')).json(), []);
  assert.equal((await (await request('/api/history')).json()).length, 1);
});

test('HTTP validation returns appropriate JSON errors', async t => {
  const { base, request } = await setup(t);
  for (const [body, status] of [['{', 400], ['[]', 400], ['{}', 400], [JSON.stringify({ events: [{}] }), 400], [JSON.stringify({ events: [{ type: 'left', participationId: 'missing' }] }), 404], [JSON.stringify({ padding: 'a'.repeat(66000) }), 413]]) {
    const response = await request('/api/queue-events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
    assert.equal(response.status, status);
    assert.equal(typeof (await response.json()).error, 'string');
  }
  assert.equal((await request('/api/queue-events', { method: 'POST', body: '{}' })).status, 415);
  assert.equal((await fetch(base + '/api/history')).status, 400);
  assert.equal((await request('/api/history?from=bad')).status, 400);
  assert.equal((await request('/api/unknown')).status, 404);
});

test('server hosts the A2 pages without exposing server files, and resets data per instance', async t => {
  const { request } = await setup(t);
  for (const route of ['/', '/front%20page.html', '/history.html', '/js/backend.js', '/css/user.css']) {
    const response = await request(route);
    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /text\//);
  }
  const head = await request('/history.html', { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
  for (const route of ['/backend/server.cjs', '/.git/config', '/package.json', '/missing.html']) assert.equal((await request(route)).status, 404);
  assert.equal((await request('/history.html', { method: 'POST' })).status, 405);
  assert.equal((await request('/%FF.html')).status, 400);
  const first = await (await request('/api/session')).json();
  const other = await setup(t);
  assert.notEqual((await (await other.request('/api/session')).json()).id, first.id);
  assert.deepEqual(await (await other.request('/api/history')).json(), []);
});
