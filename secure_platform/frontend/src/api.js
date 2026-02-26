/*
  api.js — API client for the QKD Secure Platform backend.
*/

const BASE = '';  // proxy in dev

async function request(path, options = {}) {
  const token = localStorage.getItem('qkd_token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Auth ──
export const login = (username, display_name = '') =>
  request('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, display_name }) });

export const getMe = () => request('/api/auth/me');
export const getUsers = () => request('/api/users');

// ── Chat ──
export const getMessages = (channel = 'general', limit = 100) =>
  request(`/api/messages?channel=${channel}&limit=${limit}`);

export const sendMessage = (plaintext, channel = 'general', encryption_method = 'otp') =>
  request('/api/messages/send', {
    method: 'POST',
    body: JSON.stringify({ plaintext, channel, encryption_method }),
  });

export const clearMessages = (channel = 'general') =>
  request(`/api/messages?channel=${channel}`, { method: 'DELETE' });

export const decryptMessage = (ciphertext, key_id, method = 'otp', nonce = null) =>
  request('/api/messages/decrypt', {
    method: 'POST',
    body: JSON.stringify({ ciphertext, key_id, method, nonce }),
  });

// ── Keys ──
export const generateKey = (config = {}) =>
  request('/api/keys/generate', {
    method: 'POST',
    body: JSON.stringify({
      key_length: 512, noise_depol: 0.02, noise_loss: 0.05,
      eve_active: false, eve_intercept_rate: 1.0,
      attack_type: 'intercept_resend', ...config,
    }),
  });

export const getKeyPool = (user_pair = 'alice:bob') =>
  request(`/api/keys/pool?user_pair=${user_pair}`);

export const listKeys = (user_pair = 'alice:bob') =>
  request(`/api/keys/list?user_pair=${user_pair}`);

export const requestKey = (user_pair = 'alice:bob') =>
  request('/api/keys/request', { method: 'POST', body: JSON.stringify({ user_pair, key_length: 512 }) });

export const consumeKey = (key_id) =>
  request(`/api/keys/${key_id}/consume`, { method: 'POST' });

export const listSessions = () => request('/api/keys/sessions/list');
export const clearKeyPool = () => request('/api/keys/pool', { method: 'DELETE' });

// ── Network ──
export const getTopology = () => request('/api/network/topology');
export const getRoute = (src = 'A', dst = 'B') => request(`/api/network/route?src=${src}&dst=${dst}`);
export const setSmartRouting = (enabled) =>
  request(`/api/network/smart-routing?enabled=${enabled}`, { method: 'POST' });
export const getNetworkAlerts = () => request('/api/network/alerts');
export const getLinks = () => request('/api/network/links');

// ── Eve / Attack ──
export const getEveStatus = () => request('/api/eve/status');
export const activateEve = (config) =>
  request('/api/eve/activate', { method: 'POST', body: JSON.stringify(config) });
export const deactivateEve = (link_id = null) =>
  request(`/api/eve/deactivate${link_id ? `?link_id=${link_id}` : ''}`, { method: 'POST' });
export const getEveIntercepts = (qubitLimit = 128, msgLimit = 50) =>
  request(`/api/eve/intercepts?qubit_limit=${qubitLimit}&msg_limit=${msgLimit}`);

// ── Alerts ──
export const getAlerts = () => request('/api/alerts');
export const clearAlerts = () => request('/api/alerts', { method: 'DELETE' });

// ── Demo ──
export const getDemoState = () => request('/api/demo/state');
export const startDemo = () => request('/api/demo/start', { method: 'POST' });
export const advanceDemo = () => request('/api/demo/advance', { method: 'POST' });
export const resetDemo = () => request('/api/demo/reset', { method: 'POST' });

// ── Health ──
export const getHealth = () => request('/api/health');
