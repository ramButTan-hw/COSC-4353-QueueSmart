'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { randomUUID } = require('node:crypto');
const { createServer } = require('../backend/server.cjs');

async function setup(t, disk = new Map()) {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  function browser() {
    const ctx = { console, crypto: { randomUUID }, structuredClone, Event: class {},
      fetch: (url, options) => fetch(base + url, options),
      localStorage: { getItem: k => disk.get(k) || null, setItem: (k, v) => disk.set(k, v) },
      document: { getElementById: () => null }, setTimeout() {}, setInterval() {} };
    ctx.window = ctx; ctx.addEventListener = () => {}; ctx.dispatchEvent = () => {};
    ctx.currentUser = { id: 'alice', name: 'Alice', role: 'student' };
    vm.createContext(ctx);
    for (const file of ['backend', 'notifications', 'store']) vm.runInContext(fs.readFileSync(`js/${file}.js`, 'utf8'), ctx);
    return ctx;
  }
  const ctx = browser();
  await ctx.QueueStore.ready;
  return { ctx, browser, disk };
}

test('A2 queue hooks generate backend notifications and history across separate student/staff views', async t => {
  const { ctx: alice, browser } = await setup(t);
  await alice.QueueStore.change(1, 'join');
  assert.equal(alice.QueueStore.active().index, 0);
  assert.equal(alice.Notifications.all().length, 2);
  await assert.rejects(alice.QueueStore.change(2, 'join'));
  const bob = browser();
  bob.currentUser = { id: 'bob', name: 'Bob', role: 'student' };
  await bob.QueueStore.ready;
  await bob.QueueStore.change(1, 'join');
  assert.equal(bob.Notifications.all().length, 2);
  const staff = browser();
  staff.currentUser = { id: 'staff', role: 'staff' };
  await staff.QueueStore.ready;
  assert.equal(staff.Notifications.all().length, 2);
  await staff.QueueStore.change(1, 'down', 'alice');
  await staff.QueueStore.change(1, 'toggle');
  await assert.rejects(staff.QueueStore.change(1, 'serve'));
  await staff.QueueStore.change(1, 'toggle');
  await staff.QueueStore.change(1, 'serve');
  assert.equal(bob.QueueStore.active(), null);
  assert.equal((await bob.QueueBackend.history())[0].outcome, 'Served');
  await bob.Notifications.refresh();
  assert(bob.Notifications.all().some(n => n.message.includes("You've been served")));
  await alice.Notifications.refresh();
  assert(!alice.Notifications.all().some(n => n.message.includes("You've been served")));
  await alice.QueueStore.change(1, 'leave', 'alice');
  assert.equal((await alice.QueueBackend.history())[0].outcome, 'Left queue');
  assert(staff.Notifications.all().some(n => n.message === 'A student left the Password Reset queue'));
  await alice.Notifications.markAllRead();
  assert((await alice.QueueBackend.notifications()).every(n => n.read));
  await alice.Notifications.clear();
  assert.equal(alice.Notifications.all().length, 0);
  assert.equal((await bob.QueueBackend.notifications()).length, 2);
  assert.equal((await alice.QueueBackend.history()).length, 1);
});

test('closed joins and backend errors preserve the queue; removed visits and reloads retain history', async t => {
  const { ctx, browser } = await setup(t);
  await assert.rejects(ctx.QueueStore.change(3, 'join'));
  await ctx.QueueStore.change(2, 'join');
  const originalFetch = ctx.fetch;
  ctx.fetch = async () => ({ ok: false, json: async () => ({ error: 'Backend unavailable' }) });
  await assert.rejects(ctx.QueueStore.change(2, 'leave', 'alice'), /Backend unavailable/);
  assert(ctx.QueueStore.active());
  ctx.fetch = originalFetch;
  ctx.currentUser = { id: 'staff', role: 'staff' };
  await ctx.QueueStore.change(2, 'remove', 'alice');
  const reloaded = browser();
  await reloaded.QueueStore.ready;
  assert.equal(reloaded.QueueStore.active(), null);
  assert.equal((await reloaded.QueueBackend.history())[0].outcome, 'Removed');
  reloaded.currentUser = { id: 'unrelated', role: 'student' };
  await reloaded.Notifications.refresh();
  assert.equal(reloaded.Notifications.all().length, 0);
});

test('restarting backend resets browser demo queues together with in-memory activity', async t => {
  const first = await setup(t);
  await first.ctx.QueueStore.change(1, 'join');
  const second = await setup(t, first.disk);
  assert.equal(second.ctx.QueueStore.active(), null);
  assert.equal((await second.ctx.QueueBackend.history()).length, 0);
});
