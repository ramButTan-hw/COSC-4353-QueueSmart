'use strict';
const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs/promises');
const { Activity } = require('./activity.cjs');
const { ApiError, text, object } = require('./validation.cjs');
const ROOT = path.resolve(__dirname, '..');

async function body(req) {
  if (!/^application\/json(?:;|$)/i.test(req.headers['content-type'] || '')) throw new ApiError(415, 'Use Content-Type: application/json.');
  let raw = '';
  for await (const chunk of req) {
    raw += chunk;
    if (Buffer.byteLength(raw) > 65536) throw new ApiError(413, 'Request body is too large.');
  }
  let value;
  try { value = JSON.parse(raw); } catch { throw new ApiError(400, 'Invalid JSON body.'); }
  object(value);
  return value;
}

function json(res, status, value) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(value));
}

function createServer(activity = new Activity()) {
  return http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      const route = url.pathname;
      if (route.startsWith('/api/')) {
        if (route === '/api/session' && req.method === 'GET') return json(res, 200, { id: activity.id });
        if (route === '/api/queue-events' && req.method === 'POST') {
          const value = await body(req);
          return json(res, 200, activity.apply(value.events));
        }
        // A2 supplies a demo identity. Replace this header with module 1's authenticated user later.
        const userId = text(req.headers['x-queuesmart-user'], 'X-QueueSmart-User', 254);
        if (route === '/api/history' && req.method === 'GET') return json(res, 200, activity.history.list(userId, url.searchParams.get('from'), url.searchParams.get('to')));
        if (route === '/api/notifications' && req.method === 'GET') return json(res, 200, activity.notifications.list(userId));
        if (route === '/api/notifications' && req.method === 'DELETE') {
          activity.notifications.clear(userId);
          return json(res, 200, { cleared: true });
        }
        if (route === '/api/notifications/read-all' && req.method === 'POST') {
          activity.notifications.markAllRead(userId);
          return json(res, 200, { read: true });
        }
        const match = /^\/api\/notifications\/([^/]+)\/read$/.exec(route);
        if (match && req.method === 'PATCH') return json(res, 200, activity.notifications.markRead(userId, text(match[1], 'id')));
        throw new ApiError(404, 'API endpoint not found.');
      }
      if (req.method !== 'GET' && req.method !== 'HEAD') throw new ApiError(405, 'Method not allowed.');
      const file = route === '/' ? 'index.html' : decodeURIComponent(route.slice(1));
      // Serve only the existing public UI; backend code and repository metadata stay private.
      if (!/^(?:[^/.]+\.html|(?:js|css)\/[a-zA-Z0-9_-]+\.(?:js|css))$/.test(file)) throw new ApiError(404, 'Page not found.');
      const data = await fs.readFile(path.join(ROOT, file));
      const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)];
      res.writeHead(200, { 'Content-Type': mime + '; charset=utf-8' });
      res.end(req.method === 'HEAD' ? undefined : data);
    } catch (error) {
      const status = error.status || (error.code === 'ENOENT' ? 404 : error instanceof URIError ? 400 : 500);
      if (status === 500) console.error(error);
      json(res, status, { error: status === 500 ? 'Internal server error.' : error.message });
    }
  });
}

if (require.main === module) {
  const port = Number(process.env.PORT || 3000);
  createServer().listen(port, '127.0.0.1', () => console.log(`QueueSmart: http://localhost:${port}`));
}
module.exports = { createServer };
