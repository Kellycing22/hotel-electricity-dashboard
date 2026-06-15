// API Configuration
const API_BASE_URL = 'http://localhost:5001/api';

// Get auth token from localStorage
function getToken() {
    return localStorage.getItem('token');
}

// Get user data from localStorage
function getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
}

// Save auth data
function saveAuth(token, user) {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
}

// Clear auth data
function clearAuth() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
}

// Check if user is authenticated
function isAuthenticated() {
    return !!getToken();
}

// Redirect to login if not authenticated
function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = 'index.html';
        return false;
    }
    return true;
}

// API Request Helper
async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` })
        }
    };

    const config = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        
        // Handle 401 Unauthorized
        if (response.status === 401) {
            clearAuth();
            window.location.href = 'index.html';
            throw new Error('Unauthorized');
        }

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Request failed');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// API Methods
const API = {
    // Auth
    login: async (username, password) => {
        return apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    },

    verifyToken: async () => {
        return apiRequest('/auth/verify');
    },

    logout: async () => {
        return apiRequest('/auth/logout', { method: 'POST' });
    },

    // Dashboard
    getDashboardToday: async (date = null) => {
        const query = date ? `?date=${date}` : '';
        return apiRequest(`/dashboard/today${query}`);
    },

    getDashboardMonth: async (month = null, year = null) => {
        const params = new URLSearchParams();
        if (month) params.append('month', month);
        if (year) params.append('year', year);
        const query = params.toString() ? `?${params.toString()}` : '';
        return apiRequest(`/dashboard/month${query}`);
    },

    getDashboardYear: async (year = null) => {
        const query = year ? `?year=${year}` : '';
        return apiRequest(`/dashboard/year${query}`);
    },
    
        // Forecast 10 hari + alokasi GSO
    getForecast: async () => {
        return apiRequest('/dashboard/forecast');
    },

    // Upload
    uploadDataset: async (file) => {
        const formData = new FormData();
        formData.append('file', file);

        const token = getToken();
        
        // Manual fetch (bypass apiRequest)
        const response = await fetch(`${API_BASE_URL}/datasets/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
                // Don't add Content-Type - browser will set it automatically with boundary
            },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Upload failed');
        }

        return await response.json();
    },

    getDatasets: async (limit = 10) => {
        return apiRequest(`/datasets?limit=${limit}`);
    },

    getDatasetDetail: async (datasetId) => {
        return apiRequest(`/datasets/${datasetId}`);
    },

    deleteDataset: async (datasetId) => {
        return apiRequest(`/datasets/${datasetId}`, {
            method: 'DELETE'
        });
    }
};

// Logout function
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        clearAuth();
        window.location.href = 'index.html';
    }
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0
    }).format(amount);
}

// Format number
function formatNumber(num, decimals = 2) {
    return new Intl.NumberFormat('id-ID', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(num);
}

// Format date
function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).format(new Date(date));
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Show loading overlay
function showLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('hidden');
}

// Hide loading overlay
function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.add('hidden');
}