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
    const error = document.getElementById('loginFormError');
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
      const user = await Api.login(email.value, password.value);
      location.href = Api.homeFor(user);
    } catch (problem) {
      error.textContent = problem.message;
      error.classList.add('show');
    } finally {
      button.disabled = false;
    }
  });
})();
