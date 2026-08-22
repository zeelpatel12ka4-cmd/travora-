/**
 * api.js — Thin fetch wrapper for all backend calls.
 * All functions throw an Error with a .message on failure.
 */

const API_BASE = 'http://localhost:8000/api';

/**
 * Core request helper.
 * @param {string} path    - API path, e.g. '/auth/login'
 * @param {object} options - fetch options
 * @returns {Promise<any>} - Parsed JSON response
 */
async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('travora_token');

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });
  } catch (networkErr) {
    // fetch itself failed — backend is down or CORS preflight failed
    throw new Error(
      'Cannot reach the server. Make sure the backend is running on port 8000.'
    );
  }

  // Handle 401 — clear stale auth
  if (response.status === 401) {
    localStorage.removeItem('travora_token');
    localStorage.removeItem('travora_user');
    const err = new Error('Session expired. Please sign in again.');
    err.status = 401;
    throw err;
  }

  // 204 No Content
  if (response.status === 204) return null;

  let data;
  try {
    data = await response.json();
  } catch {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return null;
  }

  if (!response.ok) {
    let msg = `Request failed (${response.status})`;
    if (data?.detail) {
      msg = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg || d).join(', ')
        : String(data.detail);
    }
    const err = new Error(msg);
    err.status = response.status;
    err.data = data;
    throw err;
  }

  return data;
}

// Convenience methods
function apiGet(path)              { return apiFetch(path, { method: 'GET' }); }
function apiPost(path, body)       { return apiFetch(path, { method: 'POST',   body: JSON.stringify(body) }); }
function apiPut(path, body)        { return apiFetch(path, { method: 'PUT',    body: JSON.stringify(body) }); }
function apiPatch(path, body)      { return apiFetch(path, { method: 'PATCH',  body: JSON.stringify(body) }); }
function apiDelete(path)           { return apiFetch(path, { method: 'DELETE' }); }

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'success'|'error'|'info'} type
 * @param {number} duration - ms
 */
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span> ${escapeHtml(message)}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideIn 0.3s ease reverse';
    setTimeout(() => toast.remove(), 280);
  }, duration);
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Format a number as currency.
 * @param {number} amount
 * @param {string} currency - ISO currency code
 */
function formatCurrency(amount, currency = 'INR') {
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${Number(amount).toLocaleString()}`;
  }
}

/**
 * Format an ISO date string to a readable form.
 * @param {string} dateStr
 */
function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

/**
 * Calculate trip duration in days (inclusive).
 */
function tripDays(start, end) {
  try {
    const s = new Date(start);
    const e = new Date(end);
    return Math.max(1, Math.round((e - s) / 86400000) + 1);
  } catch {
    return 1;
  }
}
