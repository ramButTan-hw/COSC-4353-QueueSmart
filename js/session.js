/*
 * Session guard. Every signed-in page loads this (after js/api.js, before the other scripts).
 *
 * Right away (so the scripts after it can use window.currentUser):
 *   - no token, or no stored user      -> clear everything and go to the login page
 *   - signed in with the wrong role    -> go to that user's own home page (a student opening
 *                                          admin.html, or staff opening a student page)
 *   - otherwise                        -> window.currentUser = the stored user
 * Then it asks the server who the token belongs to (GET /auth/me):
 *   - rejected (401)                   -> api.js clears the session and returns to the login page
 *   - role differs from the stored one -> refresh the stored user and go to the right home page
 *   - server unreachable               -> keep working with the stored user
 * The page stays hidden until the server has answered, so a stale session never flashes content.
 */
(function () {
  'use strict';

  var LOGIN = 'front%20page.html';
  var Api = window.Api;
  var wanted = location.pathname.endsWith('/admin.html') ? 'staff' : 'student';
  var root = document.documentElement;

  function reveal() { root.style.visibility = ''; }

  function toLogin() {
    if (Api) Api.logout();
    location.replace(LOGIN);
  }

  var user = null;
  try { user = JSON.parse(sessionStorage.getItem('queuesmart.session')); } catch (_) { /* no stored session */ }

  if (!Api || !Api.getToken() || !user) { toLogin(); return; }
  if (user.role !== wanted) { location.replace(Api.homeFor(user)); return; }

  root.style.visibility = 'hidden';
  window.currentUser = user;

  Api.me().then(function (fresh) {
    if (fresh.role !== wanted) {
      Api.updateUser(fresh);
      location.replace(Api.homeFor(fresh));
      return;
    }
    Api.updateUser(fresh);
    Object.assign(window.currentUser, fresh); // same object the other scripts already hold
    reveal();
  }).catch(function (err) {
    if (err && err.status === 401) return; // api.js is already sending the user back to the login page
    reveal(); // server unreachable: carry on with the stored session
  });

  // Coming back with the browser's Back button after logging out
  window.addEventListener('pageshow', function (e) {
    if (e.persisted && !Api.getToken()) toLogin();
  });

  document.addEventListener('DOMContentLoaded', function () {
    var link = document.createElement('a');
    link.href = LOGIN;
    link.textContent = 'Log out';
    link.style.cssText = 'font-size:14px;white-space:nowrap';
    link.addEventListener('click', function () { Api.logout(); });
    (document.querySelector('.header-actions') || document.querySelector('.user-area')).appendChild(link);
  });
})();
