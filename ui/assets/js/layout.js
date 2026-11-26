/*
 * COS3 wireframes – shared header and sidebar.
 * Edit this file once and every page updates.
 *
 * A page asks for them with placeholders inside its <template id="page">:
 *   <div data-cos3="header" data-status="running"></div>      (or data-status="not-started")
 *   <div data-cos3="nav" data-active="dashboard"></div>
 *
 * Both follow the live simulation state from server/app.py (/api/status):
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

  const ICONS = {
    wizard: '<path d="M4 6h3M11 6h9M4 12h9M17 12h3M4 18h1M9 18h11"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="7" cy="18" r="2"/>',
    dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    orbit: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    telemetry: '<path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/>',
    commands: '<path d="M4 17l6-6-6-6M12 19h8"/>',
    events: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    training: '<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M8.5 11.5l1 1 2-2M14 11.5h2M8.5 16.5l1 1 2-2M14 16.5h2"/>',
    hardware: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>'
  };

  function icon(key) {
    return `<svg class="nav-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[key] || ''}</svg>`;
  }

  // Header states. The keys match the server's /api/status `state` (plus "not-started",
  // an alias of "idle"). A page's data-status is only shown until the server answers.
  const STATUS = {
    'running': { dot: 'dot', label: 'RUNNING', start: false, pause: true, stop: true },
    'starting': { dot: 'dot off', label: 'STARTING…', start: false, pause: false, stop: false },
    'stopping': { dot: 'dot off', label: 'STOPPING…', start: false, pause: false, stop: false },
    'error': { dot: 'dot off', label: 'ERROR', start: false, pause: false, stop: false },
    'idle': { dot: 'dot off', label: 'NOT STARTED', start: false, pause: false, stop: false }
  };
  STATUS['not-started'] = STATUS.idle;

  // States in which the simulation pages are available (otherwise only the wizard)
  const SIM_STATES = new Set(['running', 'stopping']);

  // Live simulation state from server/app.py; null until the first answer (or when the
  // page is opened without the server, e.g. as a file), so the page's data-status shows.
  const STATUS_POLL_MS = 3000;
  let liveState = null;
  // Last /api/status answer (missionName, paused, speed)
  let liveStatus = {};
  // Simulation speeds, as in server/simulation.py (the NOS3 time driver doubles or halves its rate)
  const SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16, 32];
  // Key of the current page (the nav's data-active), set when the page's nav is built
  let currentPage = null;

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
    }
    for (const [name, on] of [['start', s.start], ['pause', s.pause], ['stop', s.stop]]) {
      for (const b of root.querySelectorAll('[data-cos3-btn="' + name + '"]')) b.disabled = !on;
    }

    const running = liveState === 'running';
    const paused = running && liveStatus.paused;
    for (const el of root.querySelectorAll('[data-cos3-mission]')) el.textContent = liveStatus.missionName || '—';
    if (paused) for (const el of root.querySelectorAll('[data-cos3-label]')) el.textContent = 'PAUSED';
    for (const b of root.querySelectorAll('[data-cos3-btn="pause"]')) b.textContent = paused ? '▶ Resume' : '❚❚ Pause';
    for (const sel of root.querySelectorAll('[data-cos3-speed]')) {
      sel.disabled = !running;
      sel.value = String(liveStatus.speed || 1);
    }
  }

  function setStatus(res) {
    liveStatus = res;
    setState(res.state);
    applyStatus(document);
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
    checkSession();
  }

  // COSMOS login prompt.
  let sessionChecked = false;
  let loginDialog = null;

  function onSimPage() {
    return liveState === 'running' && currentPage !== null && currentPage !== 'wizard';
  }

  async function checkSession() {
    if (sessionChecked || !onSimPage()) return;
    sessionChecked = true;
    const res = await COS3.api.session();
    if (res.loggedIn === false) showLogin();
  }

  function showLogin() {
    if (!onSimPage()) return;
    loginDialog = loginDialog || createLoginDialog();
    if (!loginDialog.open) loginDialog.showModal();
  }

  function createLoginDialog() {
    const dialog = document.createElement('dialog');
    dialog.className = 'wf login';
    dialog.setAttribute('aria-labelledby', 'cos3-login-title');
    dialog.innerHTML = `
<form>
  <div id="cos3-login-title" class="login-title">Log in to COSMOS</div>
  <p class="login-hint">Telemetry and commands need a COSMOS session.</p>
  <label for="cos3-cosmos-password">COSMOS password</label>
  <input id="cos3-cosmos-password" type="password" autocomplete="current-password" required>
  <p role="alert" class="login-err" data-login-error></p>
  <p class="login-hint">First time? <a href="${COS3.api.COSMOS_URL}" target="_blank" rel="noopener">Open COSMOS</a>
    to create your account, then come back and log in with that password.</p>
  <div class="row" style="justify-content:flex-end">
    <button type="submit" class="btn primary" data-login-submit>Log in</button>
  </div>
</form>`;
    const form = dialog.querySelector('form');
    const input = dialog.querySelector('input');
    const error = dialog.querySelector('[data-login-error]');
    const submit = dialog.querySelector('[data-login-submit]');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      submit.disabled = true;
      error.textContent = '';
      const res = await COS3.api.login(input.value);
      submit.disabled = false;
      if (res.error) {
        error.textContent = res.error;
        input.select();
        return;
      }
      input.value = '';
      dialog.close();
    });
    // Esc would close the dialog: keep it open until the operator logs in
    dialog.addEventListener('cancel', (e) => e.preventDefault());
    document.body.appendChild(dialog);
    return dialog;
  }

  window.addEventListener('cos3:login-required', showLogin);

  // In-page confirmation popup (instead of the browser's confirm()). Resolves to true if confirmed.
  function confirmDialog(title, message, okLabel) {
    return new Promise((resolve) => {
      const dialog = document.createElement('dialog');
      dialog.className = 'wf login';
      dialog.setAttribute('aria-labelledby', 'cos3-confirm-title');
      dialog.innerHTML = `
<form method="dialog">
  <div id="cos3-confirm-title" class="login-title"></div>
  <p class="login-hint"></p>
  <div class="row" style="justify-content:flex-end;gap:8px">
    <button class="btn" value="cancel" autofocus>Cancel</button>
    <button class="btn primary" value="ok"></button>
  </div>
</form>`;
      dialog.querySelector('.login-title').textContent = title;
      dialog.querySelector('.login-hint').textContent = message;
      dialog.querySelector('[value="ok"]').textContent = okLabel;
      // Esc or Cancel closes with returnValue "cancel" (or ""), the OK button with "ok"
      dialog.addEventListener('close', () => {
        resolve(dialog.returnValue === 'ok');
        dialog.remove();
      });
      document.body.appendChild(dialog);
      dialog.showModal();
    });
  }

  window.COS3 = window.COS3 || {};
  window.COS3.confirm = confirmDialog;

  function confirmStop() {
    return confirmDialog('Stop the simulation?', 'NOS3 and COSMOS will shut down. Unsaved simulation progress is lost.', '■ Stop simulation');
  }
  window.COS3.confirmStop = confirmStop;

  async function pollStatus() {
    // Server not reachable (no state): keep showing the last known state
    const res = await COS3.api.request('GET', '/api/status');
    if (res.state) setStatus(res);
    setTimeout(pollStatus, STATUS_POLL_MS);
  }
  // Header Pause/Resume button and Speed select
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest && e.target.closest('[data-cos3-btn="pause"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    const res = await (liveStatus.paused ? COS3.api.resume() : COS3.api.pause());
    if (res.error) alert(res.error);
    else setStatus(res);
    btn.disabled = false;
  });

  document.addEventListener('change', async (e) => {
    const sel = e.target.closest && e.target.closest('[data-cos3-speed]');
    if (!sel) return;
    const res = await COS3.api.setSpeed(Number(sel.value));
    if (res.error) alert(res.error);
    else setStatus(res);
    applyStatus(document);
  });

  // Header Stop button (the wizard isn't reachable while a simulation runs)
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest && e.target.closest('[data-cos3-btn="stop"]');
    if (!btn || btn.disabled || !(await confirmStop())) return;
    setState('stopping');
    // The next status poll shows the real state
    await COS3.api.stop();
  });

  function themeBtn() {
    const dark = COS3.theme.get() === 'dark';
    return { dark, text: dark ? 'Dark mode' : 'Light mode', label: dark ? 'Switch to light mode' : 'Switch to dark mode' };
  }

  document.addEventListener('click', (e) => {
    if (e.target.closest && e.target.closest('[data-cos3-btn="theme"]')) COS3.theme.toggle();
  });

  window.addEventListener('cos3:theme', () => {
    const t = themeBtn();
    for (const b of document.querySelectorAll('[data-cos3-btn="theme"]')) {
      b.lastChild.textContent = t.text;
      b.setAttribute('aria-checked', t.dark);
      b.title = t.label;
    }
  });

  function header(opts) {
    const s = STATUS[opts.status] || STATUS.running;
    const t = themeBtn();
    const dis = (enabled) => (enabled ? '' : ' disabled');
    return `
<header class="hdr" style="height:60px;flex:none;display:flex;align-items:center;gap:14px;padding:0 20px;box-sizing:border-box">
<div style="display:flex;align-items:center;gap:10px"><div class="hdr-logo"></div><span style="font-weight:700;font-size:20px;letter-spacing:.04em">COS3</span></div>
<div class="hdr-sep"></div>
<div style="display:flex;flex-direction:column;line-height:1.25"><span class="hdr-sub">Mission</span><span data-cos3-mission style="font-size:14px;font-weight:600">—</span></div>
<div style="flex:1"></div>
<div class="box" data-cos3-status style="display:flex;align-items:center;gap:8px;height:36px;padding:0 12px"><span data-cos3-dot class="${s.dot}"></span><span data-cos3-label style="font-weight:600;font-size:13px">${s.label}</span></div>
<div style="display:flex;gap:6px"><button class="btn" data-cos3-btn="start"${dis(s.start)}>▶ Start</button><button class="btn" data-cos3-btn="pause"${dis(s.pause)}>❚❚ Pause</button><button class="btn" data-cos3-btn="stop"${dis(s.stop)}>■ Stop</button></div>
<div style="display:flex;align-items:center;gap:8px"><label for="spd">Speed</label><select id="spd" data-cos3-speed style="width:76px;height:36px" disabled>${SPEEDS.map((v) => `<option value="${v}"${v === 1 ? ' selected' : ''}>${v}×</option>`).join('')}</select></div>
<div style="display:flex;flex-direction:column;line-height:1.25;border-left:1px solid var(--line);padding-left:12px"><span class="hdr-sub">[USER]</span><span style="font-size:13px;font-weight:600">Operator</span></div>
<button class="theme-switch" type="button" role="switch" aria-checked="${t.dark}" data-cos3-btn="theme" title="${t.label}"><span class="theme-track"></span><span>${t.text}</span></button>
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
        return `<div${group(g)}><div class="nav-sep"></div></div>`;
      }
      const [key, label, file] = item;
      const on = key === opts.active ? ' class="on" aria-current="page"' : '';
      return `<a href="${file}"${on}${group(key === 'wizard' ? 'setup' : 'sim')}>${icon(key)}${label}</a>`;
    }).join('\n');
    return `
<nav class="nav" aria-label="Main navigation" style="width:220px;flex:none;padding:16px 12px;box-sizing:border-box;display:flex;flex-direction:column;gap:4px">
${links}
<div class="slot" data-cos3-group="sim" style="height:40px;margin-top:4px${sim ? '' : ';display:none'}" aria-label="Placeholder for a future page"></div>
<div style="flex:1"></div>
<a href="#help">${icon('help')}Help &amp; documentation</a>
</nav>`;
  }

  window.COS3 = window.COS3 || {};
  window.COS3.layouts = Object.assign(window.COS3.layouts || {}, { header, nav });
  // After each render: the status may have arrived before the page built its sidebar
  window.COS3.onRender = (window.COS3.onRender || []).concat((root) => {
    applyStatus(root);
    redirectIfNeeded();
    checkSession();
  });
  pollStatus();
})();
