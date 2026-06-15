function getToken()        { return localStorage.getItem('token'); }
function getUser()         { const u = localStorage.getItem('user'); return u ? JSON.parse(u) : null; }
function saveAuth(t, u)    { localStorage.setItem('token', t); localStorage.setItem('user', JSON.stringify(u)); }
function clearAuth()       { localStorage.removeItem('token'); localStorage.removeItem('user'); }
function isAuthenticated() { return !!getToken(); }
function requireAuth() {
    if (!isAuthenticated()) { window.location.href = 'index.html'; return false; }
    return true;
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('lastPredictionResult');
    window.location.href = '/';
}