'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { randomUUID } = require('node:crypto');
const { spawn } = require('node:child_process');
const path = require('node:path');
const { backend, python } = require('../scripts/backend.cjs');

async function startServer(t) {
  const child = spawn(python, ['-u', '-m', 'tests.serve_app'], { cwd: backend, stdio: ['ignore', 'pipe', 'pipe'] });
  t.after(() => new Promise(resolve => {
    if (child.exitCode !== null) return resolve();
    child.once('exit', resolve);
    child.kill('SIGTERM');
  }));
  let errors = '';
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', chunk => { errors += chunk; });
  const base = await new Promise((resolve, reject) => {
    let output = '';
    const timeout = setTimeout(() => reject(Error('FastAPI startup timed out: ' + errors)), 10000);
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => {
      output += chunk;
      if (output.includes('\n')) { clearTimeout(timeout); resolve(output.split('\n')[0].trim()); }
    });
    child.once('exit', code => { clearTimeout(timeout); reject(Error(`FastAPI exited (${code}): ${errors}`)); });
    child.once('error', error => { clearTimeout(timeout); reject(error); });
  });
  for (let attempt = 0; attempt < 100; attempt++) {
    try { if ((await fetch(base + '/health')).ok) return base; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw Error('FastAPI did not become ready: ' + errors);
}

async function setup(t, disk = new Map()) {
  const base = await startServer(t);
  const accounts = new Map();
  async function browser(name = 'alice', browserDisk = disk) {
    const storage = new Map();
    const ctx = { console, crypto: { randomUUID }, structuredClone, Event: class {},
      QUEUESMART_API: base, fetch,
      location: { replace(value) { ctx.redirected = value; } },
      sessionStorage: { getItem: k => storage.get(k) || null, setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
      localStorage: { getItem: k => browserDisk.get(k) || null, setItem: (k, v) => browserDisk.set(k, v) },
      document: { getElementById: () => null }, setTimeout() {}, setInterval() {} };
    ctx.window = ctx; ctx.addEventListener = () => {}; ctx.dispatchEvent = () => {};
    vm.createContext(ctx);
    const load = file => vm.runInContext(fs.readFileSync(path.join(__dirname, '../js', file + '.js'), 'utf8'), ctx);
    load('api');
    load('backend');
    const email = name === 'staff' ? 'admin@uh.edu' : name + '@uh.edu';
    if (name !== 'staff' && !accounts.has(name)) {
      const registered = await fetch(base + '/auth/register', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password: 'Password1' }) });
      assert.equal(registered.status, 201);
      accounts.set(name, true);
    }
    ctx.currentUser = await ctx.Api.login(email, 'Password1');
    for (const file of ['notifications', 'store']) load(file);
    await ctx.QueueStore.ready;
    return ctx;
  }
  const ctx = await browser();
  return { ctx, browser, disk, base };
}

test('A2 queue hooks generate backend notifications and history across separate student/staff views', async t => {
  const { ctx: alice, browser } = await setup(t);
  await alice.QueueStore.change(1, 'join');
  assert.equal(alice.QueueStore.active().index, 0);
  assert.equal(alice.QueueStore.active().user.estimatedWait, 10);
  assert.equal(alice.QueueStore.read().services[0].estimatedWait, 20);
  assert.equal(alice.Notifications.all().length, 2);
  await assert.rejects(alice.QueueStore.change(2, 'join'));
  const bob = await browser('bob', new Map());
  await bob.QueueStore.ready;
  assert.equal(bob.QueueStore.read().services[0].estimatedWait, 20);
  await bob.QueueStore.change(1, 'join');
  assert.equal(bob.QueueStore.active().user.estimatedWait, 20);
  assert.equal(bob.Notifications.all().length, 2);
  const staff = await browser('staff');
  await staff.QueueStore.ready;
  await staff.Notifications.refresh();  // staff alerts now come from the server, one per student who joined
  assert.deepEqual([...staff.Notifications.all().map(n => n.message)], ['New student in Password Reset', 'New student in Password Reset']);
  await staff.QueueStore.change(1, 'down', alice.currentUser.id);
  await bob.QueueStore.refresh();
  assert.equal(bob.QueueStore.active().user.estimatedWait, 10);
  await staff.QueueStore.change(1, 'toggle');
  await assert.rejects(staff.QueueStore.change(1, 'serve'));
  await staff.QueueStore.change(1, 'toggle');
  await staff.QueueStore.change(1, 'serve');
  await bob.QueueStore.refresh();
  assert.equal(bob.QueueStore.active(), null);
  assert.equal((await bob.QueueBackend.history())[0].outcome, 'Served');
  await bob.Notifications.refresh();
  assert(bob.Notifications.all().some(n => n.message.includes("You've been served")));
  await alice.Notifications.refresh();
  assert(!alice.Notifications.all().some(n => n.message.includes("You've been served")));
  await alice.QueueStore.change(1, 'leave', alice.currentUser.id);
  assert.equal((await alice.QueueBackend.history())[0].outcome, 'Left queue');
  await staff.Notifications.refresh();
  assert(staff.Notifications.all().some(n => n.message === 'A student left the Password Reset queue'));
  await alice.Notifications.markAllRead();
  assert((await alice.QueueBackend.notifications()).every(n => n.read));
  await alice.Notifications.clear();
  assert.equal(alice.Notifications.all().length, 0);
  // newest first: served, queue reopened, queue closed, reached position 1 (second reminder), position 2 (first reminder), joined
  assert.deepEqual([...(await bob.QueueBackend.notifications()).map(n => n.message)], [
    "You've been served for Password Reset",
    'Password Reset queue is now open.',
    'Password Reset queue is now closed.',
    "You're next for Password Reset. Please head to the help desk.",
    "You're nearly next for Password Reset. Please head to the help desk.",
    'You joined Password Reset at position 2.'
  ]);
  assert.equal((await alice.QueueBackend.history()).length, 1);
});

test('closed joins and backend errors preserve the queue; removed visits and reloads retain history', async t => {
  const { ctx, browser } = await setup(t);
  await assert.rejects(ctx.QueueStore.change(3, 'join'));
  await ctx.QueueStore.change(2, 'join');
  const originalFetch = ctx.fetch;
  ctx.fetch = async () => ({ ok: false, status: 503, text: async () => JSON.stringify({ error: { message: 'Backend unavailable' } }) });
  await assert.rejects(ctx.QueueStore.change(2, 'leave', ctx.currentUser.id), /Backend unavailable/);
  assert(ctx.QueueStore.active());
  ctx.fetch = originalFetch;
  const staff = await browser('staff');
  await staff.QueueStore.change(2, 'remove', ctx.currentUser.id);
  const reloaded = await browser();
  await reloaded.QueueStore.ready;
  assert.equal(reloaded.QueueStore.active(), null);
  assert.equal((await reloaded.QueueBackend.history())[0].outcome, 'Removed');
  const unrelated = await browser('unrelated');
  await unrelated.Notifications.refresh();
  assert.equal(unrelated.Notifications.all().length, 0);
});

test('restarting backend resets queues together with in-memory activity', async t => {
  const first = await setup(t);
  await first.ctx.QueueStore.change(1, 'join');
  const second = await setup(t, first.disk);
  assert.equal(second.ctx.QueueStore.active(), null);
  assert.equal((await second.ctx.QueueBackend.history()).length, 0);
});

test('login errors are readable and invalid tokens clear the browser session', async t => {
  const { ctx } = await setup(t);
  await assert.rejects(ctx.Api.login('alice@uh.edu', 'WrongPassword1'), /Incorrect email or password/);
  assert.equal(ctx.redirected, undefined);
  ctx.sessionStorage.setItem('queuesmart.token', 'invalid-token');
  await assert.rejects(ctx.QueueBackend.history(), /Invalid authentication token/);
  assert.equal(ctx.sessionStorage.getItem('queuesmart.token'), null);
  assert.equal(ctx.sessionStorage.getItem('queuesmart.session'), null);
  assert.equal(ctx.redirected, 'front%20page.html');
});
