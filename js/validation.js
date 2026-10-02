
(function () {
  'use strict';

  var EMAIL_MAX = 254;
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function email(value) {
    var v = String(value == null ? '' : value).trim();
    if (!v) return 'Enter your email address.';
    if (v.length > EMAIL_MAX) return 'Email must be ' + EMAIL_MAX + ' characters or fewer.';
    if (!EMAIL_RE.test(v)) return 'Please enter a valid email address.';
    return '';
  }

  function text(value, label, max) {
    var v = String(value == null ? '' : value).trim();
    if (!v) return 'Enter ' + label + '.';
    if (max && v.length > max) return label.charAt(0).toUpperCase() + label.slice(1) + ' must be ' + max + ' characters or fewer.';
    return '';
  }

  function wholeNumber(value, label, min, max) {
    var raw = String(value == null ? '' : value).trim();
    var n = Number(raw);
    if (!raw || !Number.isSafeInteger(n)) return 'Enter a whole number of ' + label + '.';
    if (n < min) return label.charAt(0).toUpperCase() + label.slice(1) + ' must be at least ' + min + '.';
    if (max != null && n > max) return label.charAt(0).toUpperCase() + label.slice(1) + ' must be ' + max + ' or fewer.';
    return '';
  }

  function uniqueName(name, services, exceptId) {
    var key = String(name || '').trim().toLowerCase();
    var clash = (services || []).some(function (s) {
      return s.id !== exceptId && String(s.name).trim().toLowerCase() === key;
    });
    return clash ? 'A service with this name already exists.' : '';
  }

  function parseDay(v) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
    var y = +v.slice(0, 4), m = +v.slice(5, 7), day = +v.slice(8, 10);
    var d = new Date(y, m - 1, day);
    // reject dates the engine would silently roll over (month 13, Feb 30, ...)
    return d.getFullYear() === y && d.getMonth() === m - 1 && d.getDate() === day ? d : null;
  }

  function dateRange(from, to) {
    var f = from ? parseDay(from) : null;
    var t = to ? parseDay(to) : null;
    if (from && !f) return 'Enter a valid "from" date.';
    if (to && !t) return 'Enter a valid "to" date.';
    if (f && t && f > t) return 'The "from" date cannot be after the "to" date.';
    return '';
  }

  window.Validate = {
    email: email,
    text: text,
    wholeNumber: wholeNumber,
    uniqueName: uniqueName,
    dateRange: dateRange,
    parseDay: parseDay,
    EMAIL_MAX: EMAIL_MAX
  };
})();
