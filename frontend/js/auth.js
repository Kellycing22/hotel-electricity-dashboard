// Redirect kalau sudah login
if (isAuthenticated()) {
    window.location.href = 'dashboard.html';
}

// Tunggu DOM selesai sebelum attach event
document.addEventListener('DOMContentLoaded', () => {

    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('errorMessage');
        const loginBtn = document.getElementById('loginBtn');

        errorDiv.classList.add('hidden');
        loginBtn.disabled = true;
        loginBtn.textContent = 'Signing in...';

        try {
            const response = await API.login(username, password);
            if (response.success) {
                saveAuth(response.token, response.user);
                loginBtn.textContent = '✓ Success!';
                setTimeout(() => { window.location.href = 'dashboard.html'; }, 500);
            } else {
                throw new Error(response.error || 'Login failed');
            }
        } catch (error) {
            errorDiv.textContent = error.message || 'Login failed.';
            errorDiv.classList.remove('hidden');
            loginBtn.disabled = false;
            loginBtn.textContent = 'Sign In';
        }
    });

    document.getElementById('password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            document.getElementById('loginForm').dispatchEvent(new Event('submit'));
        }
    });

});