/* Use the team's authentication API; the server assigns the user's role. */
(function () {
  'use strict';
  const form = document.getElementById('loginForm');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const email = document.getElementById('loginEmail');
    const password = document.getElementById('loginPassword');
    const emailError = document.getElementById('loginEmailError');
    const passwordError = document.getElementById('loginPasswordError');
    const error = document.getElementById('loginError');
    const button = form.querySelector('button[type="submit"]');
    email.value = email.value.trim();
    emailError.textContent = Validate.email(email.value);
    emailError.classList.toggle('show', !!emailError.textContent);
    const invalidPassword = !password.value || password.value.length > 128;
    passwordError.classList.toggle('show', invalidPassword);
    error.classList.remove('show');
    if (emailError.textContent || invalidPassword) return;
    button.disabled = true;
    try {
      const result = await QueueBackend.login(email.value, password.value);
      sessionStorage.setItem('queuesmart.token', result.access_token);
      sessionStorage.setItem('queuesmart.session', JSON.stringify(result.user));
      location.href = result.user.role === 'staff' ? 'admin.html' : 'user-dashboard.html';
    } catch (problem) {
      error.textContent = problem.message;
      error.classList.add('show');
    } finally {
      button.disabled = false;
    }
  });
})();
