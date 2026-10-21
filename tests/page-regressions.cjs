'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const source = file => fs.readFileSync(path.join(root, file), 'utf8');

function element() {
  const handlers = {}, classes = new Set();
  return { handlers, value: '', textContent: '', style: {}, disabled: false,
    classList: { add: c => classes.add(c), remove: c => classes.delete(c),
      toggle: (c, yes) => yes ? classes.add(c) : classes.delete(c), contains: c => classes.has(c) },
    addEventListener(type, fn) { (handlers[type] ||= []).push(fn); },
    async fire(type, event = {}) { for (const fn of handlers[type] || []) await fn(event); },
    focus() {}, querySelectorAll: () => [], setAttribute() {}, removeAttribute() {} };
}
function page(file, extra = {}) {
  // Use the real page's IDs: a renamed error element must fail the test.
  const html = source(file), elements = new Map();
  for (const match of html.matchAll(/\bid="([^"]+)"/g)) elements.set(match[1], element());
  for (const el of elements.values()) { el.button = element(); el.querySelector = () => el.button; }
  const doc = Object.assign(element(), { getElementById: id => elements.get(id) || null,
    querySelectorAll: () => [], documentElement: element() });
  const ctx = { console, document: doc, location: { hash: '', origin: 'http://localhost:8001', pathname: '/' + file },
    setTimeout() {}, clearTimeout() {}, ...extra };
  Object.assign(ctx, element()); ctx.window = ctx;
  vm.createContext(ctx);
  const run = file => vm.runInContext(source(file), ctx, { filename: file });
  const runPage = () => { for (const script of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    const src = script[1].match(/src="([^"]+)"/);
    if (src) run(src[1]); else vm.runInContext(script[2], ctx);
  } };
  return { ctx, elements, run, runPage };
}

test('every shipped page and JavaScript file parses after merging', () => {
  for (const file of fs.readdirSync(path.join(root, 'js')).filter(f => f.endsWith('.js'))) {
    assert.doesNotThrow(() => new vm.Script(source('js/' + file), { filename: file }));
  }
  for (const file of fs.readdirSync(root).filter(f => f.endsWith('.html'))) {
    for (const script of source(file).matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
      assert.doesNotThrow(() => new vm.Script(script[1], { filename: file }));
    }
  }
});

test('actual login page submits once, uses server role, and displays API errors', async () => {
  const calls = [], storage = new Map();
  let failed = false;
  const { ctx, elements, runPage } = page('front page.html', {
    sessionStorage: { getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
    fetch: async (url, opts) => {
      calls.push({ url, opts });
      return { ok: !failed, status: failed ? 401 : 200, text: async () => JSON.stringify(failed
        ? { error: { message: 'Incorrect email or password' } }
        : { access_token: 'token', user: { id: 'admin', name: 'Staff', role: 'staff' } }) };
    }
  });
  runPage();
  const form = elements.get('loginForm');
  elements.get('loginEmail').value = '  admin@uh.edu  ';
  elements.get('loginPassword').value = 'Password1';
  await form.fire('submit', { preventDefault() {} });
  assert.equal(calls.length, 1);
  assert.equal(JSON.parse(calls[0].opts.body).email, 'admin@uh.edu');
  assert.equal(ctx.location.href, 'admin.html');
  assert.equal(storage.get('queuesmart.token'), 'token');
  failed = true; ctx.location.href = '';
  await form.fire('submit', { preventDefault() {} });
  assert.equal(calls.length, 2);
  assert.equal(ctx.location.href, '');
  assert.equal(elements.get('loginFormError').textContent, 'Incorrect email or password');
  assert(elements.get('loginFormError').classList.contains('show'));
  assert.equal(form.button.disabled, false);
});

test('one admin click serves only one student and waits for the result', async () => {
  const calls = []; let finish;
  const service = { id: 1, name: 'Help', description: 'Help desk', open: true, duration: 10, priority: 'medium', queue: [] };
  const { elements, run } = page('admin.html', {
    currentUser: { id: 'admin', role: 'staff' }, initNotifications() {},
    Services: { load: async () => [service] },
    QueueStore: { ready: Promise.resolve(), read: () => ({ services: [service] }),
      change: (...args) => { calls.push(args); return new Promise(resolve => { finish = resolve; }); } }
  });
  await run('js/admin.js');
  const button = { dataset: { action: 'serve', id: '1' }, disabled: false };
  const pending = elements.get('main').fire('click', { target: { closest: () => button } });
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].slice(0, 2), [1, 'serve']);
  assert.equal(button.disabled, true);
  assert.notEqual(elements.get('feedback').textContent, 'Queue updated.');
  finish(); await pending;
  assert.equal(button.disabled, false);
  assert.equal(elements.get('feedback').textContent, 'Queue updated.');
});

test('session guard validates the user, reveals the page, and installs one logout', async () => {
  const user = { id: 'alice', role: 'student', name: 'Cached' };
  const links = []; let loggedOut = 0;
  const { ctx, run } = page('user-dashboard.html', {
    sessionStorage: { getItem: () => JSON.stringify(user) },
    Api: { getToken: () => 'token', me: async () => ({ ...user, name: 'Alice' }),
      updateUser() {}, logout: () => loggedOut++ }
  });
  ctx.document.createElement = () => element();
  ctx.document.querySelector = () => ({ appendChild: link => links.push(link) });
  run('js/session.js');
  await Promise.resolve();
  assert.equal(ctx.currentUser.name, 'Alice');
  assert.equal(ctx.document.documentElement.style.visibility, '');
  await ctx.document.fire('DOMContentLoaded');
  assert.equal(links.length, 1);
  await links[0].fire('click');
  assert.equal(loggedOut, 1);
});

for (const file of ['user-dashboard.html', 'join-queue.html', 'queue-status.html']) {
  test(file + ' displays API estimates without recalculating them', async () => {
    // Deliberately differ from the old browser formula to catch a frontend fallback.
    const service = { id: 1, name: 'Help', open: true, duration: 10, count: 2, estimatedWait: 37 };
    const { ctx, elements, run } = page(file, {
      currentUser: { id: 'alice', role: 'student' }, URLSearchParams,
      Notifications: { all: () => [] },
      QueueStore: { ready: Promise.resolve(), read: () => ({ services: [service] }),
        active: () => ({ service, index: 1, user: { estimatedWait: 23 } }) }
    });
    if (elements.has('service-select')) elements.get('service-select').value = '1';
    run('js/user.js');
    await ctx.document.fire('DOMContentLoaded');
    if (file === 'user-dashboard.html') {
      assert.equal(elements.get('current-wait').textContent, '23 min');
      assert.match(elements.get('dashboard-services').innerHTML, /about 37 min/);
    } else if (file === 'join-queue.html') {
      assert.equal(elements.get('estimated-wait').textContent, '37 minutes');
    } else {
      assert.match(elements.get('queue-status-content').innerHTML, />23 min</);
    }
  });
}
