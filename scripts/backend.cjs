'use strict';
// Node is only a portable command launcher; all backend requests run in Python.
const path = require('node:path');
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const backend = path.resolve(__dirname, '../backend');
const python = path.join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
module.exports = { backend, python };

if (require.main === module) {
  const commands = {
    start: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', process.env.PORT || '8001'],
    test: ['-m', 'pytest', '-q'],
    coverage: ['-m', 'pytest', '-q', '--cov=app', '--cov-report=term-missing', '--cov-report=html'],
    strength: ['check_test_strength.py']
  };
  if (!fs.existsSync(python)) {
    console.error('Set up Python dependencies first: cd backend && uv sync --frozen');
    process.exit(1);
  }
  const args = commands[process.argv[2]];
  if (!args) throw Error('Unknown backend command.');
  const result = spawnSync(python, args, { cwd: backend, stdio: 'inherit' });
  if (result.error) console.error(result.error.message);
  process.exitCode = result.status ?? 1;
}
