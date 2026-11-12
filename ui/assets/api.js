/*
 * COS3 – client for the ui_server.py API (start/stop NOS3).
 * Adapted from main.js (first launcher prototype).
 *
 *   COS3.api.status()         -> { state, stage, error, containerRunning }
 *   COS3.api.defaultConfig()  -> default NOS3 configuration (see default_config.py), or { error }
 *   COS3.api.components()     -> components enabled in the current simulation (see current_config.py), or { error }
 *   COS3.api.launch(values) / stop() -> start the operation (then call watch)
 *   COS3.api.watch(onUpdate)  -> polls while starting/stopping, calls onUpdate(status) each time
 *
 * state: idle | starting | running | stopping | error
 */
(function() {
  'use strict';

  const POLL_MS = 2000;
  let pollTimer = null;

  async function api(method, path, body) {
    // The server rejects API requests without this header
    const headers = { 'X-COS3': '1' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    return res.json();
  }

  // Like api(), but failures resolve to { error, status } so callers can react to e.g. 401
  async function apiWithStatus(method, path, body) {
    try {
      const headers = { 'X-COS3': '1' };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
      const data = await res.json();
      return res.ok ? data : { error: data.error || `Request failed (${res.status}).`, status: res.status };
    } catch (e) {
      return { error: "Can't reach the UI server.", status: 0 };
    }
  }

  function isBusy(state) {
    return state === 'starting' || state === 'stopping';
  }

  async function status() {
    try {
      return await api('GET', '/api/status');
    } catch (e) {
      return { state: 'error', stage: '', error: "Can't reach the UI server. Is `python3 ui_server.py` running?", containerRunning: false };
    }
  }

  // Polls until the current operation finishes; onUpdate gets every status (including the final one)
  function watch(onUpdate) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(async () => {
      const s = await status();
      onUpdate(s);
      if (isBusy(s.state)) watch(onUpdate);
    }, POLL_MS);
  }

  window.COS3 = window.COS3 || {};
  window.COS3.api = {
    COSMOS_URL: 'http://localhost:2900',
    DESKTOP_URL: 'http://localhost:6080/vnc.html',
    isBusy,
    status,
    watch,
    // Default NOS3 configuration; resolves to { error } if it can't be read
    defaultConfig: () => api('GET', '/api/config/default').catch(() => ({ error: "Can't reach the UI server." })),
    // Components enabled in the current simulation: { spacecraft: [{ name, config, components: [{ key, name }] }] }
    components: () => api('GET', '/api/components').catch(() => ({ error: "Can't reach the UI server." })),
    // Commands for an enabled component: { component, path, commands: [{ target, name, description, hazardous }] }.
    // path: 'DEBUG' or 'RADIO'. Resolves to { error, status } on failure (status 401 = log in to COSMOS).
    commands: (componentKey, path) =>
      apiWithStatus('GET', `/api/components/${encodeURIComponent(componentKey)}/commands?path=${encodeURIComponent(path)}`),
    // Whether the server has a COSMOS session: { loggedIn }, or { error, status }
    session: () => apiWithStatus('GET', '/api/session'),
    // Log in to COSMOS: resolves to { loggedIn: true } or { error, status }
    login: (password) => apiWithStatus('POST', '/api/login', { password }),
    // values: null for the default configuration, or { startUtc, durationS, components }.
    // Resolves to { error } if the server refuses the values.
    launch: (values) => api('POST', '/api/launch', values ? { values } : undefined),
    stop: () => api('POST', '/api/stop')
  };
})();
