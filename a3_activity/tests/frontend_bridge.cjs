'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');

const root = path.resolve(__dirname, '../..');
const python = path.join(root, 'a3_activity/.venv/bin/python');

async function startServer(t) {
  const child = spawn(python, ['-u', '-m', 'a3_activity.tests.serve_demo'], {
    cwd: root, stdio: ['ignore', 'pipe', 'pipe']
  });
  let stderr = '';
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', chunk => { stderr += chunk; });
  const base = await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(new Error(`FastAPI startup timed out: ${stderr}`)), 10000);
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => {
      output += chunk;
      const newline = output.indexOf('\n');
      if (newline !== -1) {
        clearTimeout(timer);
        resolve(output.slice(0, newline).trim());
      }
    });
    child.once('exit', code => {
      clearTimeout(timer);
      reject(new Error(`FastAPI exited (${code}): ${stderr}`));
    });
    child.once('error', reject);
  });
  t.after(() => {
    if (child.exitCode === null) child.kill('SIGTERM');
  });
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      if ((await fetch(`${base}/api/session`)).ok) return base;
    } catch (_) { /* wait for the socket to accept requests */ }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(`FastAPI did not become ready: ${stderr}`);
}

async function setup(t, disk = new Map()) {
  const base = await startServer(t);
  function browser() {
    const ctx = {
      console, crypto: { randomUUID }, structuredClone, Event: class {},
      fetch: (url, options) => fetch(base + url, options),
      localStorage: { getItem: k => disk.get(k) || null, setItem: (k, v) => disk.set(k, v) },
      document: { getElementById: () => null }, setTimeout() {}, setInterval() {}
    };
    ctx.window = ctx;
    ctx.addEventListener = () => {};
    ctx.dispatchEvent = () => {};
    ctx.currentUser = { id: 'alice', name: 'Alice', role: 'student' };
    vm.createContext(ctx);
    for (const file of ['backend', 'notifications', 'store']) {
      vm.runInContext(fs.readFileSync(path.join(root, 'js', `${file}.js`), 'utf8'), ctx);
    }
    return ctx;
  }
  const ctx = browser();
  await ctx.QueueStore.ready;
  return { ctx, browser, disk, base };
}

test('A2 browser queue creates FastAPI notifications and history for the right user', async t => {
  const { ctx: alice, browser } = await setup(t);
  await alice.QueueStore.change(1, 'join');
  assert.equal(alice.QueueStore.active().index, 0);
  assert.equal(alice.Notifications.all().length, 2);
  const bob = browser();
  bob.currentUser = { id: 'bob', name: 'Bob', role: 'student' };
  await bob.QueueStore.ready;
  await bob.QueueStore.change(1, 'join');
  assert.equal(bob.Notifications.all().length, 2);
  const staff = browser();
  staff.currentUser = { id: 'staff', role: 'staff' };
  await staff.QueueStore.ready;
  await staff.QueueStore.change(1, 'serve');
  assert.equal((await alice.QueueBackend.history())[0].outcome, 'Served');
  assert.equal((await bob.QueueBackend.history())[0].outcome, 'Waiting');
  await bob.Notifications.refresh();
  assert.equal(bob.Notifications.all().length, 2);
  assert(!alice.Notifications.all().some(n => n.recipientId === 'bob'));
  await alice.Notifications.markAllRead();
  assert((await alice.QueueBackend.notifications()).every(n => n.read));
  await alice.Notifications.clear();
  assert.equal((await alice.QueueBackend.notifications()).length, 0);
  assert.equal((await alice.QueueBackend.history()).length, 1);
});

test('FastAPI failures preserve browser queue; a restart clears in-memory demo data', async t => {
  const first = await setup(t);
  const { ctx } = first;
  await ctx.QueueStore.change(2, 'join');
  const originalFetch = ctx.fetch;
  ctx.fetch = async () => ({ ok: false, json: async () => ({ error: 'Backend unavailable' }) });
  await assert.rejects(ctx.QueueStore.change(2, 'leave', 'alice'), /Backend unavailable/);
  assert(ctx.QueueStore.active());
  ctx.fetch = originalFetch;
  await ctx.QueueStore.change(2, 'leave', 'alice');
  assert.equal((await ctx.QueueBackend.history())[0].outcome, 'Left queue');
  const second = await setup(t, first.disk);
  assert.equal(second.ctx.QueueStore.active(), null);
  assert.equal((await second.ctx.QueueBackend.history()).length, 0);
});
