/* Adapter for A3 modules 5 and 6. Queue/authentication remain the A2 demo. */
(function () {
  'use strict';
  async function request(path, method = 'GET', body) {
    const response = await fetch('/api/' + path, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-QueueSmart-User': window.currentUser?.id || '' },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Unable to contact QueueSmart.');
    return value;
  }
  window.QueueBackend = {
    session: () => request('session'),
    events: events => request('queue-events', 'POST', { events }),
    notifications: () => request('notifications'),
    markRead: id => request('notifications/' + encodeURIComponent(id) + '/read', 'PATCH'),
    markAllRead: () => request('notifications/read-all', 'POST'),
    clearNotifications: () => request('notifications', 'DELETE'),
    history: () => request('history')
  };
})();
