/* Calendar ranges use local midnights, including days affected by daylight saving. */
(function () {
  'use strict';
  function day(date) {
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
  }
  function preset(name, now = new Date()) {
    if (name === 'all') return { from: '', to: '' };
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    start.setDate(start.getDate() - ({ today: 0, week: 6, month: 29 }[name]));
    return { from: day(start), to: day(now) };
  }
  function range(from, to) {
    const error = Validate.dateRange(from, to);
    if (error) return { error: error.replace('"from"', 'start').replace('"to"', 'end') };
    const start = from ? Validate.parseDay(from) : null;
    const end = to ? Validate.parseDay(to) : null;
    if (end) end.setDate(end.getDate() + 1);
    return { error: '', start: start?.getTime() ?? null, end: end?.getTime() ?? null };
  }
  function includes(record, selected) {
    return !selected.error && (selected.start === null || record.joinedAt >= selected.start) &&
      (selected.end === null || record.joinedAt < selected.end);
  }
  window.HistoryDates = { preset, range, includes };
})();
