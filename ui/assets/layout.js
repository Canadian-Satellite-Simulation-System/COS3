/*
 * COS3 wireframes – shared header and sidebar.
 * Edit this file once and every page updates.
 *
 * A page asks for them with placeholders inside its <template id="page">:
 *   <div data-cos3="header" data-status="running"></div>      (or data-status="not-started")
 *   <div data-cos3="nav" data-active="dashboard"></div>
 */
(function () {
  'use strict';

  // Sidebar items: [page key, label, file]. A "divider" entry draws a separator line.
  const NAV_ITEMS = [
    ['wizard', 'Setup Wizard', 'index.html'],
    'divider',
    ['dashboard', 'Dashboard', 'dashboard.html'],
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

  // Live simulation state from ui_server.py; null until the first answer (or when the
  // page is opened without the server, e.g. as a file), so the page's data-status shows.
  const STATUS_POLL_MS = 3000;
  let liveState = null;

  // Updates every header under root to the live state. Called after each poll and
  // after each page render (the runtime re-creates the header on every render).
  function applyStatus(root) {
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

  async function pollStatus() {
    try {
      // The server rejects API requests without the X-COS3 header
      const res = await fetch('/api/status', { headers: { 'X-COS3': '1' } });
      const st = (await res.json()).state;
      if (STATUS[st] && st !== liveState) {
        liveState = st;
        applyStatus(document);
      }
    } catch (e) {
      // Server not reachable: keep showing the last known state
    }
    setTimeout(pollStatus, STATUS_POLL_MS);
  }

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
    const links = NAV_ITEMS.map((item) => {
      if (item === 'divider') return '<div style="height:1px;background:#DDD;margin:8px 0"></div>';
      const [key, label, file] = item;
      const on = key === opts.active ? ' class="on" aria-current="page"' : '';
      return `<a href="${file}"${on}><span class="ico"></span>${label}</a>`;
    }).join('\n');
    return `
<nav class="nav" aria-label="Main navigation" style="width:220px;flex:none;background:#fff;border-right:1.5px solid #999;padding:16px 12px;box-sizing:border-box;display:flex;flex-direction:column;gap:4px">
${links}
<div class="slot" style="height:40px;margin-top:4px" aria-label="Placeholder for a future page"></div>
<div style="flex:1"></div>
<a href="#help"><span class="ico" style="border-radius:50%"></span>Help &amp; documentation</a>
</nav>`;
  }

  window.COS3 = window.COS3 || {};
  window.COS3.layouts = Object.assign(window.COS3.layouts || {}, { header, nav });
  window.COS3.onRender = (window.COS3.onRender || []).concat(applyStatus);
  pollStatus();
})();
