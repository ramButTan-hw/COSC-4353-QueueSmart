/* Shared FastAPI adapter: authenticated identity comes from the login token. */
(function () {
  'use strict';
  async function request(path, method = 'GET', body, authenticated = true) {
    const headers = { 'Content-Type': 'application/json' };
    const token = sessionStorage.getItem('queuesmart.token');
    if (authenticated && token) headers.Authorization = 'Bearer ' + token;
    const response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    const value = await response.json();
    if (!response.ok) {
      if (response.status === 401 && authenticated) {
        sessionStorage.removeItem('queuesmart.token');
        sessionStorage.removeItem('queuesmart.session');
        location.replace('front%20page.html');
      }
      throw new Error(value.error?.message || 'Unable to contact QueueSmart.');
    }
    return value;
  }
  window.QueueBackend = {
    login: (email, password) => request('/auth/login', 'POST', { email, password }, false),
    session: () => request('/api/session'),
    events: events => request('/api/queue-events', 'POST', { events }),
    notifications: () => request('/api/notifications'),
    markRead: id => request('/api/notifications/' + encodeURIComponent(id) + '/read', 'PATCH'),
    markAllRead: () => request('/api/notifications/read-all', 'POST'),
    clearNotifications: () => request('/api/notifications', 'DELETE'),
    history: () => request('/api/history')
  };
})();
