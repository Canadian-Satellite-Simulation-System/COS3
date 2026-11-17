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

  // Sidebar icons, by page key. Line drawings that take the color of the text around them
  // (stroke="currentColor"), so they follow the light / dark theme and the active item.
  const ICONS = {
    wizard: '<path d="M4 6h3M11 6h9M4 12h9M17 12h3M4 18h1M9 18h11"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="7" cy="18" r="2"/>',
    dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    orbit: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    telemetry: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    commands: '<path d="M4 17l6-6-6-6M12 19h8"/>',
    events: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    training: '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5M22 9v6"/>',
    hardware: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>'
  };

  function icon(key) {
    return `<svg class="nav-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[key] || ''}</svg>`;
  }

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

  // Live simulation state from server/app.py; null until the first answer (or when the
  // page is opened without the server, e.g. as a file), so the page's data-status shows.
  const STATUS_POLL_MS = 3000;
  let liveState = null;
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

  async function pollStatus() {
    // Server not reachable (no state): keep showing the last known state
    const res = await COS3.api.request('GET', '/api/status');
    if (res.state) setState(res.state);
    setTimeout(pollStatus, STATUS_POLL_MS);
  }

  // Header Stop button (the wizard isn't reachable while a simulation runs)
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest && e.target.closest('[data-cos3-btn="stop"]');
    if (!btn || btn.disabled || !confirm('Stop the simulation?')) return;
    setState('stopping');
    // The next status poll shows the real state
    await COS3.api.stop();
  });

  // Light / dark switch (assets/js/theme.js): on = dark mode, the text names the current theme
  function themeBtn() {
    const dark = !!COS3.theme && COS3.theme.get() === 'dark';
    return dark ? { dark, text: 'Dark mode', label: 'Switch to light mode' } : { dark, text: 'Light mode', label: 'Switch to dark mode' };
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest && e.target.closest('[data-cos3-btn="theme"]');
    if (btn && COS3.theme) COS3.theme.toggle();
  });

  // Also runs when the theme follows an OS change
  window.addEventListener('cos3:theme', () => {
    const t = themeBtn();
    for (const b of document.querySelectorAll('[data-cos3-btn="theme"]')) {
      b.querySelector('[data-cos3-theme-text]').textContent = t.text;
      b.setAttribute('aria-checked', String(t.dark));
      b.title = t.label;
    }
  });

  function header(opts) {
    const s = STATUS[opts.status] || STATUS.running;
    const dis = (enabled) => (enabled ? '' : ' disabled');
    return `
<header class="hdr" style="height:60px;flex:none;display:flex;align-items:center;gap:14px;padding:0 20px;box-sizing:border-box">
<div style="display:flex;align-items:center;gap:10px"><div class="hdr-logo"></div><span style="font-weight:700;font-size:20px;letter-spacing:.04em">COS3</span></div>
<div class="hdr-sep"></div>
<div style="display:flex;flex-direction:column;line-height:1.25"><span class="hdr-sub">Mission</span><span style="font-size:14px;font-weight:600">[MISSION NAME]</span></div>
<div style="display:flex;align-items:center;gap:8px"><label for="sat">Satellite</label><select id="sat" style="width:120px;height:36px"><option>SAT-1</option><option>SAT-2</option></select></div>
<div style="flex:1"></div>
<div class="box" data-cos3-status style="display:flex;align-items:center;gap:8px;height:36px;padding:0 12px"><span data-cos3-dot class="${s.dot}"></span><span data-cos3-label style="font-weight:600;font-size:13px">${s.label}</span><span data-cos3-time class="mono" style="font-size:12px;color:var(--txt-2)">· ${s.time} UTC</span></div>
<div style="display:flex;gap:6px"><button class="btn" data-cos3-btn="start"${dis(s.start)}>▶ Start</button><button class="btn" data-cos3-btn="pause"${dis(s.pause)}>❚❚ Pause</button><button class="btn" data-cos3-btn="stop"${dis(s.stop)}>■ Stop</button></div>
<div style="display:flex;align-items:center;gap:8px"><label for="spd">Speed</label><select id="spd" style="width:76px;height:36px"><option>0.5×</option><option selected>1×</option><option>2×</option><option>5×</option><option>10×</option></select></div>
<div style="display:flex;flex-direction:column;line-height:1.25;border-left:1px solid var(--line);padding-left:12px"><span class="hdr-sub">[USER]</span><span style="font-size:13px;font-weight:600">Operator</span></div>
<button class="theme-switch" type="button" role="switch" aria-checked="${themeBtn().dark}" data-cos3-btn="theme" title="${themeBtn().label}"><span class="theme-track"></span><span data-cos3-theme-text>${themeBtn().text}</span></button>
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
