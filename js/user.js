
(function () {
  'use strict';

  const SERVICES = [
    { id: 'advising', name: 'Academic Advising', wait: 18, people: 4 },
    { id: 'financial', name: 'Financial Aid', wait: 32, people: 7 },
    { id: 'registrar', name: 'Registrar Services', wait: 12, people: 3 },
    { id: 'it', name: 'IT Help Desk', wait: 8, people: 2 }
  ];

  const ACTIVE_KEY = 'queuesmart.activeQueue';
  const HISTORY_KEY = 'queuesmart.history';

  function getActiveQueue() {
    try { return JSON.parse(localStorage.getItem(ACTIVE_KEY)); }
    catch (_) { return null; }
  }

  function setActiveQueue(queue) {
    if (queue) localStorage.setItem(ACTIVE_KEY, JSON.stringify(queue));
    else localStorage.removeItem(ACTIVE_KEY);
  }

  function getHistory() {
    try {
      const value = JSON.parse(localStorage.getItem(HISTORY_KEY));
      return Array.isArray(value) ? value : [];
    } catch (_) { return []; }
  }

  function addHistory(item) {
    const history = getHistory();
    history.unshift(item);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 20)));
  }

  function formatDate(ts) {
    return new Date(ts).toLocaleString([], {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit'
    });
  }

  function renderNotificationSummary() {
    const el = document.getElementById('notification-summary');
    if (!el || !window.Notifications) return;
    const items = Notifications.all()
      .filter(n => n.role === 'student')
      .slice(0, 3);

    if (!items.length) {
      el.innerHTML = '<div class="empty">No notifications yet.</div>';
      return;
    }
    el.innerHTML = '<ul class="notification-preview">' +
      items.map(n => `<li><strong>${escapeHtml(n.message)}</strong><div class="small muted">${formatDate(n.ts)}</div></li>`).join('') +
      '</ul>';
  }

  function renderDashboard() {
    const active = getActiveQueue();
    const status = document.getElementById('current-queue-status');
    const position = document.getElementById('current-position');
    const wait = document.getElementById('current-wait');
    if (status) status.textContent = active ? active.serviceName : 'Not in a queue';
    if (position) position.textContent = active ? `#${active.position}` : '—';
    if (wait) wait.textContent = active ? `${active.wait} min` : '—';

    const list = document.getElementById('dashboard-services');
    if (list) {
      list.innerHTML = SERVICES.map(s => `
        <div class="service-row">
          <div>
            <div class="service-name">${escapeHtml(s.name)}</div>
            <div class="small muted">${s.people} waiting • about ${s.wait} min</div>
          </div>
          <a class="btn btn-secondary" href="join-queue.html?service=${encodeURIComponent(s.id)}">Join</a>
        </div>`).join('');
    }
    renderNotificationSummary();
  }

  function renderJoinPage() {
    const select = document.getElementById('service-select');
    if (!select) return;

    select.innerHTML = '<option value="">Choose a service</option>' +
      SERVICES.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');

    const params = new URLSearchParams(location.search);
    if (params.get('service')) select.value = params.get('service');

    const waitText = document.getElementById('estimated-wait');
    const peopleText = document.getElementById('people-ahead');
    const joinBtn = document.getElementById('join-btn');
    const leaveBtn = document.getElementById('leave-btn');

    function updateDetails() {
      const service = SERVICES.find(s => s.id === select.value);
      waitText.textContent = service ? `${service.wait} minutes` : 'Select a service';
      peopleText.textContent = service ? `${service.people} people currently waiting` : '';
      joinBtn.disabled = !service;

      const active = getActiveQueue();
      leaveBtn.hidden = !active;
      if (active) {
        joinBtn.textContent = active.serviceId === select.value ? 'Already Joined' : 'Join Selected Queue';
        joinBtn.disabled = active.serviceId === select.value || !service;
      } else {
        joinBtn.textContent = 'Join Queue';
      }
    }

    select.addEventListener('change', updateDetails);
    updateDetails();

    joinBtn.addEventListener('click', function () {
      const service = SERVICES.find(s => s.id === select.value);
      if (!service) return;

      const active = {
        serviceId: service.id,
        serviceName: service.name,
        position: service.people + 1,
        wait: service.wait,
        status: 'waiting',
        joinedAt: Date.now()
      };
      setActiveQueue(active);
      notify('student', `You joined ${service.name} at position ${active.position}`, 'success');
      setTimeout(() => location.href = 'queue-status.html', 300);
    });

    leaveBtn.addEventListener('click', function () {
      const active = getActiveQueue();
      if (!active) return;
      addHistory({
        date: Date.now(),
        serviceName: active.serviceName,
        outcome: 'Left queue'
      });
      setActiveQueue(null);
      notify('student', `You left the ${active.serviceName} queue`, 'info');
      updateDetails();
    });
  }

  function renderStatusPage() {
    const wrap = document.getElementById('queue-status-content');
    if (!wrap) return;
    const active = getActiveQueue();

    if (!active) {
      wrap.innerHTML = `
        <div class="card empty">
          <h2>No active queue</h2>
          <p>You are not currently waiting for a service.</p>
          <a class="btn btn-primary" href="join-queue.html">Join a Queue</a>
        </div>`;
      return;
    }

    const percent = Math.max(10, Math.min(100, (1 - (active.position - 1) / 10) * 100));
    const statusLabel = active.status === 'almost-ready' ? 'Almost Ready'
      : active.status === 'served' ? 'Served' : 'Waiting';

    wrap.innerHTML = `
      <div class="card queue-hero">
        <span class="badge ${active.status === 'almost-ready' ? 'warning' : 'info'}">${statusLabel}</span>
        <h2>${escapeHtml(active.serviceName)}</h2>
        <div class="muted">Your current position</div>
        <div class="position">#${active.position}</div>
        <div class="stat-value">${active.wait} min</div>
        <div class="muted">estimated wait time</div>
        <div class="progress" aria-label="Queue progress"><span style="width:${percent}%"></span></div>
        <div class="actions" style="justify-content:center">
          <button class="btn btn-secondary" id="advance-demo">Move Forward (Demo)</button>
          <button class="btn btn-primary" id="served-demo">Mark Served (Demo)</button>
          <button class="btn btn-danger" id="leave-status">Leave Queue</button>
        </div>
      </div>`;

    document.getElementById('advance-demo').addEventListener('click', function () {
      const q = getActiveQueue();
      if (!q) return;
      q.position = Math.max(1, q.position - 1);
      q.wait = Math.max(2, q.wait - 5);

      if (q.position <= 2 && q.status !== 'almost-ready') {
        q.status = 'almost-ready';
        notify('student', `You are almost ready for ${q.serviceName}. You are #${q.position} in line.`, 'warning');
      } else {
        notify('student', `Queue update: you are now #${q.position} for ${q.serviceName}.`, 'info');
      }
      setActiveQueue(q);
      renderStatusPage();
    });

    document.getElementById('served-demo').addEventListener('click', function () {
      const q = getActiveQueue();
      if (!q) return;
      addHistory({ date: Date.now(), serviceName: q.serviceName, outcome: 'Served' });
      setActiveQueue(null);
      notify('student', `You have been served by ${q.serviceName}.`, 'success');
      renderStatusPage();
    });

    document.getElementById('leave-status').addEventListener('click', function () {
      const q = getActiveQueue();
      if (!q) return;
      addHistory({ date: Date.now(), serviceName: q.serviceName, outcome: 'Left queue' });
      setActiveQueue(null);
      notify('student', `You left the ${q.serviceName} queue.`, 'info');
      renderStatusPage();
    });
  }

  function renderHistoryPage() {
    const el = document.getElementById('history-list');
    if (!el) return;

    let history = getHistory();
    if (!history.length) {
      history = [
        { date: Date.now() - 86400000 * 2, serviceName: 'Registrar Services', outcome: 'Served' },
        { date: Date.now() - 86400000 * 8, serviceName: 'IT Help Desk', outcome: 'Served' }
      ];
    }

    el.innerHTML = history.map(item => `
      <div class="history-row">
        <div>
          <div class="service-name">${escapeHtml(item.serviceName)}</div>
          <div class="small muted">${formatDate(item.date)}</div>
        </div>
        <span class="badge ${item.outcome === 'Served' ? 'success' : 'muted'}">${escapeHtml(item.outcome)}</span>
      </div>`).join('');
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    })[c]);
  }

  document.addEventListener('DOMContentLoaded', function () {
    renderDashboard();
    renderJoinPage();
    renderStatusPage();
    renderHistoryPage();
  });
})();
