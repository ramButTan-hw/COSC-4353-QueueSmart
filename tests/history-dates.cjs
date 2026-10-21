'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
// Node test files run in separate processes; exercise the same local dates as the user.
process.env.TZ = 'America/Chicago';
const context = { Date };
context.window = context;
vm.createContext(context);
for (const file of ['validation', 'history-dates']) vm.runInContext(fs.readFileSync(`js/${file}.js`, 'utf8'), context);
const { preset, range, includes } = context.HistoryDates;
const plain = value => JSON.parse(JSON.stringify(value));

test('quick ranges include today and cross month/year boundaries correctly', () => {
  const now = new Date(2026, 0, 3, 23, 30);
  assert.deepEqual(plain(preset('all', now)), { from: '', to: '' });
  assert.deepEqual(plain(preset('today', now)), { from: '2026-01-03', to: '2026-01-03' });
  assert.deepEqual(plain(preset('week', now)), { from: '2025-12-28', to: '2026-01-03' });
  assert.deepEqual(plain(preset('month', now)), { from: '2025-12-05', to: '2026-01-03' });
});

test('date filtering includes the entire local end date and excludes the next midnight', () => {
  const selected = range('2026-10-16', '2026-10-16');
  assert(includes({ joinedAt: new Date(2026, 9, 16, 0, 0).getTime() }, selected));
  assert(includes({ joinedAt: new Date(2026, 9, 16, 23, 59, 59, 999).getTime() }, selected));
  assert(!includes({ joinedAt: new Date(2026, 9, 17, 0, 0).getTime() }, selected));
  assert(!includes({ joinedAt: new Date(2026, 9, 15, 23, 59, 59, 999).getTime() }, selected));
});

test('local date ranges handle 23-hour and 25-hour daylight-saving days', () => {
  const spring = range('2026-03-08', '2026-03-08');
  const autumn = range('2026-11-01', '2026-11-01');
  assert.equal(spring.end - spring.start, 23 * 3600000);
  assert.equal(autumn.end - autumn.start, 25 * 3600000);
  assert(includes({ joinedAt: new Date(2026, 10, 1, 23, 59).getTime() }, autumn));
});

test('blank dates allow open ranges; invalid/reversed ranges never match visits', () => {
  const record = { joinedAt: new Date(2026, 9, 16, 15).getTime() };
  assert(includes(record, range('', '')));
  assert(includes(record, range('2026-10-16', '')));
  assert(!includes(record, range('2026-10-17', '')));
  assert(includes(record, range('', '2026-10-16')));
  assert(!includes(record, range('', '2026-10-15')));
  for (const [from, to] of [['2026-10-17', '2026-10-16'], ['2026-02-30', ''], ['bad', '']]) {
    const selected = range(from, to);
    assert(selected.error);
    assert.equal(includes(record, selected), false);
  }
});
