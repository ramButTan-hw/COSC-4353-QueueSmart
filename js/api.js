/*
 * QueueSmart – API client (Assignment 3)
 *
 * Every page that talks to the FastAPI back end goes through this file, so the base URL, the
 * bearer token and the error format are handled in one place.
 *
 *   Api.login(email, password)        POST /auth/login; stores the token and session, returns the user
 *   Api.register(name, email, pw)     POST /auth/register; returns the new user (no login)
 *   Api.me()                          GET /auth/me
 *   Api.get/post/patch/del(path, body) any other endpoint; sends the token automatically
 *   Api.homeFor(user)                 page to open after login ('admin.html' or 'user-dashboard.html')
 *   Api.updateUser(user)              refresh the stored user (after GET /auth/me), keeping the token
 *   Api.logout()                      forget the token and session
 */
(function () {
  'use strict';

  var SESSION_KEY = 'queuesmart.session';
  var TOKEN_KEY = 'queuesmart.token';
  var LOGIN_PAGE = 'front%20page.html';

  // FastAPI serves the UI on its own origin; separate static development servers use port 8001.
  var BASE = window.QUEUESMART_API ||
    (['8000', '8080'].includes(location.port) || location.protocol === 'file:'
      ? ((location.protocol === 'https:' ? 'https:' : 'http:') + '//' + (location.hostname || 'localhost') + ':8001')
      : location.origin);

  function ApiError(status, code, message, fields) {
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.message = message;
    this.fields = fields || {};
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  function store(key, value) {
    try {
      if (value == null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, value);
    } catch (e) { /* storage unavailable */ }
  }

  function read(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }

  function getToken() { return read(TOKEN_KEY); }

  function saveSession(token, user) {
    store(TOKEN_KEY, token);
    store(SESSION_KEY, JSON.stringify({ id: user.id, name: user.name, email: user.email, role: user.role }));
  }

  function updateUser(user) {
    store(SESSION_KEY, JSON.stringify({ id: user.id, name: user.name, email: user.email, role: user.role }));
  }

  function logout() {
    store(TOKEN_KEY, null);
    store(SESSION_KEY, null);
  }

  async function request(method, path, opts) {
    opts = opts || {};
    var useToken = opts.auth !== false;
    var token = useToken ? getToken() : null;
    var headers = {};
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers['Authorization'] = 'Bearer ' + token;

    var res;
    try {
      res = await fetch(BASE + path, {
        method: method,
        headers: headers,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined
      });
    } catch (e) {
      throw new ApiError(0, 'network', 'Cannot reach the server. Is the backend running?');
    }

    var text = await res.text();
    var data = null;
    if (text) { try { data = JSON.parse(text); } catch (e) { data = null; } }
    if (res.ok) return data;

    var err = (data && data.error) || {};
    var failure = new ApiError(res.status, err.code || 'error', err.message || 'Request failed (' + res.status + ').', err.fields);
    if (res.status === 401 && token) {
      logout();
      location.replace(LOGIN_PAGE);
    }
    throw failure;
  }

  async function login(email, password) {
    var data = await request('POST', '/auth/login', { body: { email: email, password: password }, auth: false });
    saveSession(data.access_token, data.user);
    return data.user;
  }

  function register(name, email, password) {
    return request('POST', '/auth/register', { body: { name: name, email: email, password: password }, auth: false });
  }

  function homeFor(user) {
    return user && user.role === 'staff' ? 'admin.html' : 'user-dashboard.html';
  }

  window.Api = {
    BASE: BASE,
    ApiError: ApiError,
    login: login,
    register: register,
    me: function () { return request('GET', '/auth/me'); },
    get: function (path) { return request('GET', path); },
    post: function (path, body) { return request('POST', path, { body: body }); },
    patch: function (path, body) { return request('PATCH', path, { body: body }); },
    del: function (path) { return request('DELETE', path); },
    homeFor: homeFor,
    updateUser: updateUser,
    logout: logout,
    getToken: getToken
  };
})();
