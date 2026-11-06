/*
 * COS3 wireframes – shared header and sidebar.
 * Edit this file once and every page updates.
 *
 * A page asks for them with placeholders inside its <template id="page">:
 *   <div data-cos3="header" data-status="running"></div>      (or data-status="not-started")
 *   <div data-cos3="nav" data-active="dashboard"></div>
 *
 * Both follow the live simulation state from ui_server.py (/api/status):
 *   - not running: the sidebar shows only the Setup Wizard, and the other pages send you to it
 *   - running:     the sidebar shows the simulation pages, and the wizard sends you to the Dashboard
 */
(function () {
  'use strict';

  const WIZARD_PAGE = 'index.html';
  const RUNNING_HOME = 'dashboard.html';

  // Sidebar items: [page key, label, file]. A "divider" entry draws a separator line.
  // The wizard is shown only while no simulation runs; everything else only while one does.
  const NAV_ITEMS = [
    ['wizard', 'Setup Wizard', WIZARD_PAGE],
    'divider',
    ['dashboard', 'Dashboard', RUNNING_HOME],
    ['orbit', 'Orbit &amp; Ground Track', 'orbit.html'],
    ['telemetry', 'Telemetry', 'telemetry.html'],
    ['commands', 'Commands', 'commands.html'],
    ['events', 'Events &amp; Logs', 'events.html'],
    'divider',
    ['training', 'Training Scenarios', 'training.html'],
    ['hardware', 'Hardware (HIL)', 'hardware.html']
  ];

  // Header states. The keys match the server's /api/status `state` (plus "not-started",
  // an alias of "idle"). A page's data-status is only shown until the server answers.
  const STATUS = {
    'running': { dot: 'dot', label: 'RUNNING', time: '[hh:mm:ss]', start: false, pause: true, stop: true },
    'starting': { dot: 'dot off', label: 'STARTING…', time: '--:--:--', start: false, pause: false, stop: false },
    'stopping': { dot: 'dot off', label: 'STOPPING…', time: '--:--:--', start: false, pause: false, stop: false },
    'error': { dot: 'dot off', label: 'ERROR', time: '--:--:--', start: false, pause: false, stop: false },
    'idle': { dot: 'dot off', label: 'NOT STARTED', time: '--:--:--', start: false, pause: false, stop: false }
  };
  STATUS['not-started'] = STATUS.idle;

  // States in which the simulation pages are available (otherwise only the wizard)
  const SIM_STATES = new Set(['running', 'stopping']);

  // Live simulation state from ui_server.py; null until the first answer (or when the
  // page is opened without the server, e.g. as a file), so the page's data-status shows.
  const STATUS_POLL_MS = 3000;
  let liveState = null;
  // Key of the current page (the nav's data-active), set when the page's nav is built
  let currentPage = null;

  async function api(method, path) {
    // The server rejects API requests without the X-COS3 header
    const res = await fetch(path, { method, headers: { 'X-COS3': '1' } });
    return res.json();
  }

  // Simulation pages visible while one runs, only the wizard otherwise.
  // Before the server answers, the current page decides (the wizard assumes "not running").
  function simMode() {
    return liveState ? SIM_STATES.has(liveState) : currentPage !== 'wizard';
  }

  // Updates every header and sidebar under root to the live state. Called after each poll
  // and after each page render (the runtime re-creates the header and sidebar on every render).
  function applyStatus(root) {
    const sim = simMode();
    for (const el of root.querySelectorAll('[data-cos3-group]')) {
      el.style.display = (el.getAttribute('data-cos3-group') === 'sim') === sim ? '' : 'none';
    }

    const s = liveState && STATUS[liveState];
    if (!s) return;
    for (const el of root.querySelectorAll('[data-cos3-status]')) {
      el.querySelector('[data-cos3-dot]').className = s.dot;
      el.querySelector('[data-cos3-label]').textContent = s.label;
      el.querySelector('[data-cos3-time]').textContent = '· ' + s.time + ' UTC';
    }
    for (const [name, on] of [['start', s.start], ['pause', s.pause], ['stop', s.stop]]) {
      for (const b of root.querySelectorAll('[data-cos3-btn="' + name + '"]')) b.disabled = !on;
    }
  }

  // Sends you to the page that matches the live state (no redirect before the server answers)
  function redirectIfNeeded() {
    if (!liveState || !currentPage) return;
    if (SIM_STATES.has(liveState) && currentPage === 'wizard') window.location.replace(RUNNING_HOME);
    else if (!SIM_STATES.has(liveState) && currentPage !== 'wizard') window.location.replace(WIZARD_PAGE);
  }

  function setState(st) {
    if (!STATUS[st] || st === liveState) return;
    liveState = st;
    applyStatus(document);
    redirectIfNeeded();
  }

  async function pollStatus() {
    try {
      setState((await api('GET', '/api/status')).state);
    } catch (e) {
      // Server not reachable: keep showing the last known state
    }
    setTimeout(pollStatus, STATUS_POLL_MS);
  }

  // Header Stop button (the wizard isn't reachable while a simulation runs)
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest && e.target.closest('[data-cos3-btn="stop"]');
    if (!btn || btn.disabled || !confirm('Stop the simulation?')) return;
    setState('stopping');
    try {
      await api('POST', '/api/stop');
    } catch (err) {
      // The next status poll shows the real state
    }
  });

  function header(opts) {
    const s = STATUS[opts.status] || STATUS.running;
    const dis = (enabled) => (enabled ? '' : ' disabled');
    return `
<header style="height:60px;flex:none;display:flex;align-items:center;gap:14px;padding:0 20px;background:#fff;border-bottom:1.5px solid #999;box-sizing:border-box">
<div style="display:flex;align-items:center;gap:10px"><div style="width:28px;height:28px;border:2px solid #222;border-radius:50%;box-sizing:border-box"></div><span style="font-weight:700;font-size:20px;letter-spacing:.04em">COS3</span></div>
<div style="width:1px;height:28px;background:#DDD"></div>
<div style="display:flex;flex-direction:column;line-height:1.25"><span style="font-size:11px;color:#555">Mission</span><span style="font-size:14px;font-weight:600">[MISSION NAME]</span></div>
<div style="display:flex;align-items:center;gap:8px"><label for="sat">Satellite</label><select id="sat" style="width:120px;height:36px"><option>SAT-1</option><option>SAT-2</option></select></div>
<div style="flex:1"></div>
<div class="box" data-cos3-status style="display:flex;align-items:center;gap:8px;height:36px;padding:0 12px"><span data-cos3-dot class="${s.dot}"></span><span data-cos3-label style="font-weight:600;font-size:13px">${s.label}</span><span data-cos3-time class="mono" style="font-size:12px;color:#444">· ${s.time} UTC</span></div>
<div style="display:flex;gap:6px"><button class="btn" data-cos3-btn="start"${dis(s.start)}>▶ Start</button><button class="btn" data-cos3-btn="pause"${dis(s.pause)}>❚❚ Pause</button><button class="btn" data-cos3-btn="stop"${dis(s.stop)}>■ Stop</button></div>
<div style="display:flex;align-items:center;gap:8px"><label for="spd">Speed</label><select id="spd" style="width:76px;height:36px"><option>0.5×</option><option selected>1×</option><option>2×</option><option>5×</option><option>10×</option></select></div>
<div style="display:flex;flex-direction:column;line-height:1.25;border-left:1px solid #DDD;padding-left:12px"><span style="font-size:11px;color:#555">[USER]</span><span style="font-size:13px;font-weight:600">Operator</span></div>
</header>`;
  }

  function nav(opts) {
    currentPage = opts.active;
    const sim = simMode();
    const group = (g) => ` data-cos3-group="${g}"${(g === 'sim') === sim ? '' : ' style="display:none"'}`;
    // The first divider separates the wizard from the simulation pages: hide it with the wizard
    let firstDivider = true;
    const links = NAV_ITEMS.map((item) => {
      if (item === 'divider') {
        const g = firstDivider ? 'setup' : 'sim';
        firstDivider = false;
        return `<div${group(g)}><div style="height:1px;background:#DDD;margin:8px 0"></div></div>`;
      }
      const [key, label, file] = item;
      const on = key === opts.active ? ' class="on" aria-current="page"' : '';
      return `<a href="${file}"${on}${group(key === 'wizard' ? 'setup' : 'sim')}><span class="ico"></span>${label}</a>`;
    }).join('\n');
    return `
<nav class="nav" aria-label="Main navigation" style="width:220px;flex:none;background:#fff;border-right:1.5px solid #999;padding:16px 12px;box-sizing:border-box;display:flex;flex-direction:column;gap:4px">
${links}
<div class="slot" data-cos3-group="sim" style="height:40px;margin-top:4px${sim ? '' : ';display:none'}" aria-label="Placeholder for a future page"></div>
<div style="flex:1"></div>
<a href="#help"><span class="ico" style="border-radius:50%"></span>Help &amp; documentation</a>
</nav>`;
  }

  window.COS3 = window.COS3 || {};
  window.COS3.layouts = Object.assign(window.COS3.layouts || {}, { header, nav });
  // After each render: the status may have arrived before the page built its sidebar
  window.COS3.onRender = (window.COS3.onRender || []).concat((root) => { applyStatus(root); redirectIfNeeded(); });
  pollStatus();
})();
