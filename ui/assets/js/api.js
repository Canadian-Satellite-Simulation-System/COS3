/*
 * COS3 – client for the server/app.py API (start/stop NOS3).
 * Adapted from main.js (first launcher prototype).
 *
 *   COS3.api.status()         -> { state, stage, error, containerRunning }
 *   COS3.api.defaultConfig()  -> default NOS3 configuration (see server/mission_config/default.py), or { error }
 *   COS3.api.components()     -> components enabled in the current simulation (see server/mission_config/current.py), or { error }
 *   COS3.api.launch(values) / stop() -> start the operation (then call watch)
 *   COS3.api.watch(onUpdate)  -> polls while starting/stopping, calls onUpdate(status) each time
 *
 * state: idle | starting | running | stopping | error
 */
(function() {
  'use strict';

  const POLL_MS = 2000;
  let pollTimer = null;

  // Every /api/ call goes through here. Resolves to the JSON body, or on failure to
  // { ...body, error, status } (status 0 = server unreachable), so callers can react to e.g. 401.
  async function request(method, path, body) {
    try {
      // The server rejects API requests without this header
      const headers = { 'X-COS3': '1' };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
      const data = await res.json();
      // No COSMOS session (a wrong password on /api/login is also 401): layout.js asks to log in
      if (res.status === 401 && path !== '/api/login') window.dispatchEvent(new Event('cos3:login-required'));
      // Keep any extra fields (e.g. errors, confirm) so callers can act on them
      return res.ok ? data : { ...data, error: data.error || `Request failed (${res.status}).`, status: res.status };
    } catch (e) {
      return { error: "Can't reach the UI server.", status: 0 };
    }
  }

  function isBusy(state) {
    return state === 'starting' || state === 'stopping';
  }

  async function status() {
    const res = await request('GET', '/api/status');
    if (res.status === 0) {
      return { state: 'error', stage: '', error: "Can't reach the UI server. Is `python3 main.py` running?", containerRunning: false };
    }
    return res;
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
    request,
    isBusy,
    status,
    watch,
    // Default NOS3 configuration; resolves to { error } if it can't be read
    defaultConfig: () => request('GET', '/api/config/default'),
    // Components enabled in the current simulation: { spacecraft: [{ name, config, components: [{ key, name }] }] }
    components: () => request('GET', '/api/components'),
    // Commands for an enabled component: { component, path, commands: [{ target, name, description, hazardous }] }.
    // path: 'DEBUG' or 'RADIO'. Resolves to { error, status } on failure (status 401 = log in to COSMOS).
    commands: (componentKey, path) =>
      request('GET', `/api/components/${encodeURIComponent(componentKey)}/commands?path=${encodeURIComponent(path)}`),
    // One command: { target, name, description, hazardous, hazardousDescription, parameters: [{ name,
    // dataType, bitSize, minimum, maximum, default, units, description, states, hazardousStates,
    // required, conversion }] }, or { error, status }
    command: (target, name) =>
      request('GET', `/api/commands/${encodeURIComponent(target)}/${encodeURIComponent(name)}`),
    // Check parameter values on the server (server/commands/validation.py) without sending:
    // { errors: { name: message } } ({} = all valid), or { error, status }
    validateCommand: (target, name, values) =>
      request('POST', `/api/commands/${encodeURIComponent(target)}/${encodeURIComponent(name)}/validate`, { values }),
    // Send a command: { record } (record.status: sent | rejected | failed), or on failure
    // { error, status, errors } (400: invalid values) / { error, status, confirm } (409: hazardous,
    // send again with confirmHazardous = true)
    sendCommand: (target, name, values, confirmHazardous = false) =>
      request('POST', `/api/commands/${encodeURIComponent(target)}/${encodeURIComponent(name)}`,
        { values, confirmHazardous }),
    // Sent commands, newest first: { commands: [record] }, or { error, status }
    history: () => request('GET', '/api/history'),
    // Send a recorded command again: same answers as sendCommand
    resend: (id, confirmHazardous = false) =>
      request('POST', `/api/history/${encodeURIComponent(id)}/resend`, { confirmHazardous }),
    // Whether the server has a COSMOS session: { loggedIn }, or { error, status }
    session: () => request('GET', '/api/session'),
    // Log in to COSMOS: resolves to { loggedIn: true } or { error, status }
    // Pages listen for 'cos3:logged-in' to reload what needed a session.
    login: async (password) => {
      const res = await request('POST', '/api/login', { password });
      if (!res.error) window.dispatchEvent(new Event('cos3:logged-in'));
      return res;
    },
    // values: null for the default configuration, or { startUtc, durationS, components }.
    // missionName: shown in the header while the mission runs. Resolves to { error } if the server refuses the values.
    launch: (values, missionName) => request('POST', '/api/launch', { values: values || undefined, missionName }),
    stop: () => request('POST', '/api/stop'),
    // Pause / resume / speed (one of 0.25 … 32) of the running simulation: resolve to the new status, or { error }
    pause: () => request('POST', '/api/pause'),
    resume: () => request('POST', '/api/resume'),
    setSpeed: (speed) => request('POST', '/api/speed', { speed }),
    // Saved configurations (configs/ in the repo): { configs: [{ file, missionName, savedAt, components, groundStations }] }
    configs: () => request('GET', '/api/configs'),
    // One saved configuration: { missionName, savedAt, values }
    config: (file) => request('GET', `/api/configs/${encodeURIComponent(file)}`),
    // Save to configs/: { file, config }, or { error }
    saveConfig: (missionName, values) => request('POST', '/api/configs', { missionName, values }),
    // Makes the browser download obj as a JSON file
    download: (filename, obj) => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2) + '\n'], { type: 'application/json' }));
      const a = Object.assign(document.createElement('a'), { href: url, download: filename });
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
    // Latest values of a component's telemetry packet ('data' or 'hk'): { component, target, packet,
    // receivedCount, spacecraftTime, lastUpdate, rows, allItems }, or { error, status } (401 = log in to COSMOS)
    telemetry: (componentKey, packet = 'data', path = 'DEBUG') =>
      request('GET', `/api/telemetry/${encodeURIComponent(componentKey)}?packet=${encodeURIComponent(packet)}&path=${encodeURIComponent(path)}`)
  };
})();
