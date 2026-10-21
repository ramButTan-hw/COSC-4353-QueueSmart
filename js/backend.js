/* Modules 5/6 use the team's shared API client for tokens, origins, and errors. */
(function () {
  'use strict';
  window.QueueBackend = {
    notifications: () => Api.get('/api/notifications'),
    markRead: id => Api.patch('/api/notifications/' + encodeURIComponent(id) + '/read'),
    markAllRead: () => Api.post('/api/notifications/read-all'),
    clearNotifications: () => Api.del('/api/notifications'),
    history: () => Api.get('/api/history')
  };
})();
