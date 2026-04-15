document.addEventListener('DOMContentLoaded', function () {
    const registerForm = document.getElementById('registerForm');
    const loginForm = document.getElementById('loginForm');
    const messageDiv = document.getElementById('message');

    // Clear chat session state when loading auth pages (login/register).
    // This ensures that after logout and re-login, the main app starts on a fresh chat
    // and the last session is only accessible from the history sidebar.
    try {
        sessionStorage.removeItem('sessionId');
        sessionStorage.removeItem('temporaryChat');
    } catch (e) {
        console.warn('Could not clear sessionStorage on auth page load:', e);
    }

    function showMessage(msg, type) {
        messageDiv.textContent = msg;
        messageDiv.className = type === 'success' ? 'mt-3 text-success' : 'mt-3 text-danger';
    }

    if (registerForm) {
        registerForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (response.ok) {
                    showMessage('Registration successful! Logging you in...', 'success');

                    // Auto-login
                    try {
                        const loginResp = await fetch('/api/auth/login', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ email, password })
                        });

                        if (loginResp.ok) {
                            // New user flow: after register + auto-login, always show welcome/consent page
                            await loginResp.json().catch(() => null);
                            window.location.href = '/onboarding/welcome';
                        } else {
                            // Fallback if auto-login fails
                            setTimeout(() => {
                                window.location.href = '/api/auth/login';
                            }, 1000);
                        }
                    } catch (err) {
                        setTimeout(() => {
                            window.location.href = '/api/auth/login';
                        }, 1000);
                    }
                } else {
                    showMessage(data.detail || 'Registration failed', 'error');
                }
            } catch (error) {
                showMessage('An error occurred. Please try again.', 'error');
            }
        });
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (response.ok) {
                    // Store token if needed, or just rely on session/cookie if implemented
                    // For now checking token response
                    if (data.access_token) {
                        localStorage.setItem('token', data.access_token);
                    }

                    // Send user to consent page if not completed yet
                    window.location.href = data.redirect_to || '/chat';
                } else {
                    showMessage(data.detail || 'Login failed', 'error');
                }
            } catch (error) {
                showMessage('An error occurred. Please try again.', 'error');
            }
        });
    }
});
