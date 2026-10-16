(function () {
  'use strict';
  const list = document.getElementById('history-list');
  if (!list || !window.currentUser) return;
  const from = document.getElementById('history-from');
  const to = document.getElementById('history-to');
  const error = document.getElementById('history-filter-error');
  const count = document.getElementById('history-count');
  const label = document.getElementById('history-range-label');
  const presets = document.querySelectorAll('[data-history-range]');
  const esc = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const date = value => new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  const time = value => new Date(value).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  let records = [], selected = HistoryDates.range('', ''), applied = { from: '', to: '' }, loaded = false, problem = '', pending;

  function timestamp(value) {
    return `<time datetime="${new Date(value).toISOString()}"><span>${esc(date(value))}</span><small>${esc(time(value))}</small></time>`;
  }

  function render() {
    list.setAttribute('aria-busy', String(!loaded));
    const visits = records.filter(record => record.userId === currentUser.id && HistoryDates.includes(record, selected));
    count.textContent = loaded && !problem && !selected.error ? visits.length + (visits.length === 1 ? ' visit' : ' visits') : '';
    const dayLabel = value => date(Validate.parseDay(value).getTime());
    label.textContent = selected.error ? 'Fix the date range to see your visits.' :
      (applied.from && applied.to ? dayLabel(applied.from) + (applied.from === applied.to ? '' : ' – ' + dayLabel(applied.to)) :
        applied.from ? 'From ' + dayLabel(applied.from) : applied.to ? 'Through ' + dayLabel(applied.to) : 'All time') + ' · Newest first';
    if (selected.error) { list.innerHTML = '<div class="empty">Choose an end date on or after the start date.</div>'; return; }
    if (problem) { list.innerHTML = `<div class="empty" role="alert">${esc(problem)}<p>Please try again in a moment.</p></div>`; return; }
    if (!loaded) return;
    if (!visits.length) {
      list.innerHTML = `<div class="empty history-empty"><span class="history-empty-icon" aria-hidden="true">◷</span><h3>${records.length ? 'No visits in this range' : 'Your history starts here'}</h3><p>${records.length ? 'Try a wider date range or reset the filters.' : 'After you join a queue, your visit and its outcome will appear here.'}</p>${records.length ? '' : '<a class="btn btn-secondary" href="join-queue.html">Find a queue</a>'}</div>`;
      return;
    }
    const styles = { Waiting: 'warning', Served: 'success', 'Left queue': 'muted', Removed: 'danger' };
    list.innerHTML = '<ol class="history-visits">' + visits.map(record => `<li class="history-visit"><div class="history-service"><span class="history-service-icon" aria-hidden="true">Q</span><div><h3>${esc(record.serviceName)}</h3><span class="small muted">Queue visit</span></div></div><div class="history-timestamp"><span class="history-field-label">Joined</span>${timestamp(record.joinedAt)}</div><div class="history-timestamp"><span class="history-field-label">Completed</span>${record.completedAt === null ? '<span class="small muted">Still in queue</span>' : timestamp(record.completedAt)}</div><span class="badge ${styles[record.outcome] || 'muted'}">${esc(record.outcome)}</span></li>`).join('') + '</ol>';
  }

  function apply() {
    selected = HistoryDates.range(from.value, to.value);
    applied = { from: from.value, to: to.value };
    error.textContent = selected.error;
    error.hidden = !selected.error;
    from.setAttribute('aria-invalid', String(!!selected.error));
    to.setAttribute('aria-invalid', String(!!selected.error));
    render();
  }

  function choose(name) {
    const value = HistoryDates.preset(name);
    from.value = value.from;
    to.value = value.to;
    presets.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.historyRange === name)));
    apply();
  }

  async function refresh() {
    if (pending) return pending;
    pending = (async () => {
      try { records = await QueueBackend.history(); problem = ''; }
      catch (err) { problem = err.message; }
      loaded = true;
      render();
    })().finally(() => { pending = null; });
    return pending;
  }

  document.getElementById('history-filter').addEventListener('submit', event => { event.preventDefault(); apply(); });
  [from, to].forEach(input => input.addEventListener('input', () => { presets.forEach(button => button.setAttribute('aria-pressed', 'false')); }));
  presets.forEach(button => button.addEventListener('click', () => choose(button.dataset.historyRange)));
  document.getElementById('history-clear').addEventListener('click', () => choose('all'));
  window.addEventListener('queue-change', refresh);
  refresh();
  setInterval(refresh, 5000);
})();
