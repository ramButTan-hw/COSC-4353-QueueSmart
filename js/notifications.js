/*
 * QueueSmart – in-app notifications (Assignment 2, part 4)
 *
 * Public API (everything else is private):
 *   initNotifications({ getRole })  Render the bell into #bell-mount. getRole() must return
 *                                   'student' or 'staff'. Defaults to window.currentUser.role.
 *   notify(role, message, type)     Add a notification for a role and show a toast if that role
 *                                   is the one currently signed in.
 *                                   type: 'info' | 'success' | 'warning' | 'error'
 *   Notifications.refresh()         Re-render after login/logout or a role change.
 *   Notifications.clear()           Remove every stored notification (used by the test page).
 */
(function () {
  'use strict';

  var ROLES = ['student', 'staff'];
  var TYPES = ['info', 'success', 'warning', 'error'];
  var STORAGE_KEY = 'queuesmart.notifications';
  var MAX_STORED = 50;
  var TOAST_MS = 4500;

  var ICONS = {
    info: 'M12 8h.01M11 12h1v5h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
    success: 'M8 12.5l2.7 2.7L16 9.5M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
    warning: 'M12 9v4m0 3.5h.01M10.3 4.2L2.9 17.5A2 2 0 0 0 4.6 20.5h14.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z',
    error: 'M9 9l6 6m0-6l-6 6M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z'
  };

  var items = load();
  var nextId = items.reduce(function (m, n) { return Math.max(m, n.id); }, 0) + 1;
  var getRole = function () { return window.currentUser && window.currentUser.role; };
  var els = {};
  var mounted = false;

  /* ---------- storage ---------- */

  function load() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORAGE_KEY));
      return Array.isArray(raw) ? raw : [];
    } catch (e) { return []; }
  }

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch (e) { /* storage unavailable */ }
  }

  /* ---------- data ---------- */

  function forRole(role) {
    return items.filter(function (n) { return n.role === role; });
  }

  function unreadCount(role) {
    return forRole(role).filter(function (n) { return !n.read; }).length;
  }

  function notify(role, message, type) {
    if (ROLES.indexOf(role) === -1) { console.warn('notify: unknown role', role); return null; }
    if (typeof message !== 'string' || !message.trim()) { console.warn('notify: message is required'); return null; }
    if (TYPES.indexOf(type) === -1) type = 'info';

    var n = { id: nextId++, role: role, message: message.trim(), type: type, ts: Date.now(), read: false };
    items.unshift(n);
    // keep only the newest MAX_STORED per role
    ROLES.forEach(function (r) {
      var own = forRole(r);
      if (own.length > MAX_STORED) {
        var drop = own.slice(MAX_STORED).map(function (x) { return x.id; });
        items = items.filter(function (x) { return drop.indexOf(x.id) === -1; });
      }
    });
    save();
    render();
    if (role === getRole()) toast(n);
    return n;
  }

  function markRead(id) {
    items.forEach(function (n) { if (n.id === id) n.read = true; });
    save(); render();
  }

  function markAllRead() {
    var role = getRole();
    items.forEach(function (n) { if (n.role === role) n.read = true; });
    save(); render();
  }

  function clear(all) {
    var role = getRole();
    items = all ? [] : items.filter(function (n) { return n.role !== role; });
    save(); render();
  }

  /* ---------- helpers ---------- */

  function timeAgo(ts) {
    var s = Math.max(0, Math.round((Date.now() - ts) / 1000));
    if (s < 45) return 'Just now';
    var m = Math.round(s / 60);
    if (m < 60) return m + ' min ago';
    var h = Math.round(m / 60);
    if (h < 24) return h + ' hr ago';
    return new Date(ts).toLocaleDateString();
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function icon(type) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', '20');
    svg.setAttribute('height', '20');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', ICONS[type] || ICONS.info);
    svg.appendChild(p);
    return svg;
  }

  /* ---------- toasts ---------- */

  function toast(n) {
    if (!els.toasts) return;
    var t = el('div', 'qs-toast qs-' + n.type);
    t.setAttribute('role', n.type === 'error' ? 'alert' : 'status');
    t.appendChild(icon(n.type));
    t.appendChild(el('span', 'qs-toast-msg', n.message));
    var x = el('button', 'qs-toast-x', '×');
    x.type = 'button';
    x.setAttribute('aria-label', 'Dismiss notification');
    x.addEventListener('click', function () { t.remove(); });
    t.appendChild(x);
    els.toasts.appendChild(t);
    setTimeout(function () { t.remove(); }, TOAST_MS);
  }

  /* ---------- bell + panel ---------- */

  function build() {
    var mount = document.getElementById('bell-mount');
    if (!mount) { console.warn('initNotifications: no #bell-mount element found'); return false; }

    var wrap = el('div', 'qs-bellwrap');

    els.bell = el('button', 'qs-bell');
    els.bell.type = 'button';
    els.bell.setAttribute('aria-haspopup', 'true');
    els.bell.setAttribute('aria-expanded', 'false');
    els.bell.setAttribute('aria-controls', 'qs-panel');
    var bellSvg = icon('info');
    bellSvg.replaceChildren();
    var bp = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    bp.setAttribute('d', 'M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9zM10 19a2 2 0 0 0 4 0');
    bellSvg.appendChild(bp);
    bellSvg.setAttribute('width', '22');
    bellSvg.setAttribute('height', '22');
    els.bell.appendChild(bellSvg);
    els.badge = el('span', 'qs-badge');
    els.badge.hidden = true;
    els.bell.appendChild(els.badge);

    els.panel = el('div', 'qs-panel');
    els.panel.id = 'qs-panel';
    els.panel.hidden = true;
    els.panel.setAttribute('role', 'region');
    els.panel.setAttribute('aria-label', 'Notifications');

    var head = el('div', 'qs-panel-h');
    head.appendChild(el('h2', 'qs-panel-title', 'Notifications'));
    var actions = el('div', 'qs-panel-actions');
    els.markAll = el('button', 'qs-link', 'Mark all read');
    els.markAll.type = 'button';
    els.markAll.addEventListener('click', markAllRead);
    els.clearBtn = el('button', 'qs-link', 'Clear');
    els.clearBtn.type = 'button';
    els.clearBtn.addEventListener('click', function () { clear(false); });
    actions.appendChild(els.markAll);
    actions.appendChild(els.clearBtn);
    head.appendChild(actions);

    els.list = el('ul', 'qs-list');
    els.panel.appendChild(head);
    els.panel.appendChild(els.list);

    wrap.appendChild(els.bell);
    wrap.appendChild(els.panel);
    mount.appendChild(wrap);
    els.wrap = wrap;

    els.toasts = el('div', 'qs-toasts');
    els.toasts.setAttribute('aria-live', 'polite');
    document.body.appendChild(els.toasts);

    els.bell.addEventListener('click', function () { setOpen(els.panel.hidden); });
    document.addEventListener('click', function (e) {
      if (!els.panel.hidden && !wrap.contains(e.target)) setOpen(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !els.panel.hidden) { setOpen(false); els.bell.focus(); }
    });
    return true;
  }

  function setOpen(open) {
    els.panel.hidden = !open;
    els.bell.setAttribute('aria-expanded', String(open));
    if (open) render();
  }

  function render() {
    if (!mounted) return;
    var role = getRole();
    var mine = role ? forRole(role) : [];
    var unread = role ? unreadCount(role) : 0;

    els.badge.hidden = unread === 0;
    els.badge.textContent = unread > 9 ? '9+' : String(unread);
    els.bell.setAttribute('aria-label', unread ? 'Notifications, ' + unread + ' unread' : 'Notifications');
    els.markAll.disabled = unread === 0;
    els.clearBtn.disabled = mine.length === 0;

    els.list.replaceChildren();
    if (!mine.length) {
      els.list.appendChild(el('li', 'qs-empty', 'No notifications yet.'));
      return;
    }
    mine.forEach(function (n) {
      var li = el('li', 'qs-item qs-' + n.type + (n.read ? '' : ' qs-unread'));
      var btn = el('button', 'qs-item-btn');
      btn.type = 'button';
      btn.appendChild(icon(n.type));
      var body = el('span', 'qs-item-body');
      body.appendChild(el('span', 'qs-item-msg', n.message));
      body.appendChild(el('span', 'qs-item-time', timeAgo(n.ts)));
      btn.appendChild(body);
      if (!n.read) btn.appendChild(el('span', 'qs-dot'));
      btn.addEventListener('click', function () { markRead(n.id); });
      li.appendChild(btn);
      els.list.appendChild(li);
    });
  }

  function init(opts) {
    if (opts && typeof opts.getRole === 'function') getRole = opts.getRole;
    if (!mounted) mounted = build();
    render();
    // keep "2 min ago" labels fresh while the panel is open
    setInterval(function () { if (mounted && !els.panel.hidden) render(); }, 30000);
  }

  window.notify = notify;
  window.initNotifications = init;
  window.Notifications = { refresh: render, markAllRead: markAllRead, clear: function () { clear(true); }, all: function () { return items.slice(); } };
})();
