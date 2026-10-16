'use strict';
// Each mutation is a plausible business-rule regression. The real source is never edited.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'queuesmart-test-strength-'));
const mutations = [
  ['remind users too early', 'notifications.cjs', 'position <= 2', 'position <= 3'],
  ['remind while queue is closed', 'notifications.cjs', 'queueOpen && position', 'position'],
  ['repeat near-front reminders', 'notifications.cjs', ' && !record.closeNotified', ''],
  ['mix recipient notifications', 'notifications.cjs', 'n.recipientId === userId));', 'true));'],
  ['clear the wrong recipient', 'notifications.cjs', 'n.recipientId !== userId', 'n.recipientId === userId'],
  ['record served users as removed', 'history.cjs', "served: 'Served'", "served: 'Removed'"],
  ['lose original join timestamp', 'history.cjs', 'record.completedAt = Date.now();', 'record.joinedAt = Date.now(); record.completedAt = Date.now();'],
  ['exclude start-date midnight', 'history.cjs', 'r.joinedAt >= start', 'r.joinedAt > start'],
  ['include the next midnight', 'history.cjs', 'r.joinedAt < end', 'r.joinedAt <= end'],
  ['filter by completion instead of join', 'history.cjs', 'r.joinedAt >= start', 'r.completedAt >= start'],
  ['keep partial history after batch failure', 'activity.cjs', 'this.history.records = previous.records;', '/* no rollback */'],
  ['reject valid maximum field lengths', 'validation.cjs', 'value.trim().length > max', 'value.trim().length >= max']
];
let caught = 0;
try {
  fs.mkdirSync(path.join(temporary, 'tests'));
  fs.copyFileSync(path.join(root, 'tests/backend.cjs'), path.join(temporary, 'tests/backend.cjs'));
  const baseline = spawnSync(process.execPath, ['--test', 'tests/backend.cjs'], { cwd: root, encoding: 'utf8' });
  if (baseline.status !== 0) throw Error('Baseline tests must pass before mutation checks.\n' + baseline.stdout + baseline.stderr);
  for (const [name, file, before, after] of mutations) {
    fs.cpSync(path.join(root, 'backend'), path.join(temporary, 'backend'), { recursive: true });
    const target = path.join(temporary, 'backend', file), source = fs.readFileSync(target, 'utf8');
    if (!source.includes(before)) throw Error('Mutation no longer matches: ' + name);
    fs.writeFileSync(target, source.replace(before, after));
    const syntax = spawnSync(process.execPath, ['--check', target], { encoding: 'utf8' });
    if (syntax.status !== 0) throw Error('Invalid mutation syntax: ' + name);
    const result = spawnSync(process.execPath, ['--test', 'tests/backend.cjs'], { cwd: temporary, encoding: 'utf8' });
    if (result.error || result.signal) throw result.error || Error('Test process interrupted.');
    if (result.status === 1) { caught++; console.log('Caught: ' + name); }
    else { console.error('MISSED: ' + name); process.exitCode = 1; }
  }
  console.log(`\n${caught}/${mutations.length} deliberate business-rule regressions caught.`);
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
