/*
 * QueueSmart – registration form on the login page (Assignment 3)
 *
 * Checks the form with js/validation.js (same rules as the back end), calls POST /auth/register
 * through js/api.js, then logs the new student in and opens their dashboard. Server messages for
 * a field (for example "An account with this email already exists.") appear under that field.
 * Also switches between the login card and the registration card (#login / #register).
 *
 * Load order: js/validation.js, js/api.js, then this file (after the form's markup).
 */
(function () {
  'use strict';

  var FIELD_IDS = { name: 'regName', email: 'regEmail', password: 'regPassword', confirm: 'regConfirm' };

  // Client-side checks. Returns { fieldName: message } for every field that fails.
  function problems(v) {
    var found = {};
    var message;
    if ((message = Validate.text(v.name, 'your name', 100))) found.name = message;
    if ((message = Validate.email(v.email))) found.email = message;
    if ((message = Validate.password(v.password))) found.password = message;
    if ((message = Validate.confirm(v.password, v.confirm))) found.confirm = message;
    return found;
  }

  // Resolves to one of:
  //   { fields: {name: msg, ...} }  something to fix in specific inputs (client or server side)
  //   { message: text }             a problem that is not tied to an input (server down, ...)
  //   { user }                      registered and logged in
  //   { created: true }             registered, but the automatic login failed
  async function submit(v) {
    var found = problems(v);
    if (Object.keys(found).length) return { fields: found };

    var email = v.email.trim();
    try {
      await Api.register(v.name.trim(), email, v.password);
    } catch (err) {
      var fields = {};
      var any = false;
      Object.keys(err.fields || {}).forEach(function (key) {
        if (FIELD_IDS[key]) { fields[key] = err.fields[key]; any = true; }
      });
      return any ? { fields: fields } : { message: err.message };
    }

    try {
      return { user: await Api.login(email, v.password) };
    } catch (err) {
      return { created: true };
    }
  }

  function init() {
    var form = document.getElementById('registerForm');
    if (!form) return;
    var loginCard = document.getElementById('loginCard');
    var registerCard = document.getElementById('registerCard');
    var notice = document.getElementById('loginNotice');
    var formError = document.getElementById('regFormError');
    var button = form.querySelector('button[type="submit"]');

    function input(name) { return document.getElementById(FIELD_IDS[name]); }
    function errorBox(name) { return document.getElementById(FIELD_IDS[name] + 'Error'); }

    function clearErrors() {
      Object.keys(FIELD_IDS).forEach(function (name) {
        errorBox(name).textContent = '';
        errorBox(name).classList.remove('show');
      });
      formError.textContent = '';
      formError.classList.remove('show');
    }

    function showFields(fields) {
      var first = null;
      Object.keys(FIELD_IDS).forEach(function (name) {
        if (!fields[name]) return;
        errorBox(name).textContent = fields[name];
        errorBox(name).classList.add('show');
        if (!first) first = name;
      });
      if (first) input(first).focus();
    }

    function showView(view) {
      loginCard.hidden = view === 'register';
      registerCard.hidden = view !== 'register';
      if (view === 'register') input('name').focus();
    }

    function viewFromHash() { return location.hash === '#register' ? 'register' : 'login'; }

    Object.keys(FIELD_IDS).forEach(function (name) {
      input(name).addEventListener('input', function () {
        errorBox(name).textContent = '';
        errorBox(name).classList.remove('show');
      });
    });

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      clearErrors();
      var values = {};
      Object.keys(FIELD_IDS).forEach(function (name) { values[name] = input(name).value; });

      button.disabled = true;
      var result;
      try { result = await submit(values); }
      finally { button.disabled = false; }

      if (result.user) { location.href = Api.homeFor(result.user); return; }
      if (result.created) {
        notice.textContent = 'Account created. Please log in.';
        notice.hidden = false;
        location.hash = '#login';
        showView('login');
        return;
      }
      if (result.fields) { showFields(result.fields); return; }
      formError.textContent = result.message;
      formError.classList.add('show');
    });

    window.addEventListener('hashchange', function () { showView(viewFromHash()); });
    showView(viewFromHash()); // set both cards explicitly instead of trusting the markup
  }

  window.Register = { submit: submit, problems: problems };
  init();
})();
