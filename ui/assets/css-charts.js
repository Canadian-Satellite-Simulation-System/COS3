/* CSS charts for the Telemetry page.
 * Two live line charts (raw counts, converted volts) of the selected CSS item,
 * with an Expand view and a hover tracker. The item is chosen by clicking a table row.
 *
 * Use from a page:
 *   <script src="assets/css-charts.js"></script>
 *   CssCharts.init()            once, after COS3.mount(...)
 *   CssCharts.addSample(data)   for each /api/telemetry/css reply (or streamed packet)
 *   CssCharts.select(name)      when the user clicks a row, e.g. 'RAW_CSS_2'
 * The page must contain <div id="css-chart-raw"> and <div id="css-chart-value">.
 */
(function () {
  const MAX_POINTS = 600;   // About 10 minutes at 1 packet/s
  const history = [];       // [{ t: ms, raw: {RAW_CSS_0: 845, ...}, value: {RAW_CSS_0: 0.845, ...} }]
  let charts = [];
  let selected = 'RAW_CSS_0';
  let overlay = null;

  const hms = (t) => new Date(t).toISOString().slice(11, 19);   // UTC hh:mm:ss

  // Styles live here so the page doesn't need them
  const style = document.createElement('style');
  style.textContent = `
    .chart{flex:1;min-width:0;min-height:0}
    .chart-head{display:flex;align-items:center;gap:8px;flex:none}
    .chart-head .h{flex:1;min-width:0}
    .chart .plot{flex:1;min-height:120px;position:relative;overflow:hidden}
    .chart canvas{position:absolute;inset:0;display:block;cursor:crosshair}
    .chart-overlay{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.45);padding:40px;box-sizing:border-box;display:none}
    .chart-overlay.on{display:flex}
    .chart-overlay .chart{flex:1}`;
  document.head.appendChild(style);

  class LiveChart {
    constructor({ slotId, title, field, units, digits }) {
      Object.assign(this, { slotId, title, field, units, digits, hoverX: null, expanded: false });

      this.root = document.createElement('section');
      this.root.className = 'pnl chart';
      this.root.innerHTML = `
        <div class="chart-head">
          <span class="h"></span>
          <button class="btn sm" type="button">Expand</button>
        </div>
        <div class="plot"><canvas></canvas></div>`;

      this.titleEl = this.root.querySelector('.h');
      this.btn = this.root.querySelector('button');
      this.canvas = this.root.querySelector('canvas');

      this.btn.addEventListener('click', () => (this.expanded ? this.collapse() : this.expand()));
      this.canvas.addEventListener('mousemove', (e) => { this.hoverX = e.offsetX; this.draw(); });
      this.canvas.addEventListener('mouseleave', () => { this.hoverX = null; this.draw(); });
      new ResizeObserver(() => this.draw()).observe(this.root.querySelector('.plot'));
      this.updateTitle();
    }

    updateTitle() { this.titleEl.textContent = `${this.title}: ${selected}`; }

    // Expanded view: the chart moves into an overlay outside the page, so page re-renders don't affect it
    expand() {
      charts.forEach((c) => c.expanded && c.collapse());
      this.expanded = true;
      overlay.appendChild(this.root);
      overlay.classList.add('on');
      this.btn.textContent = 'Close';
      this.draw();
    }

    collapse() {
      this.expanded = false;
      overlay.classList.remove('on');
      this.btn.textContent = 'Expand';
      attach();
    }

    draw() {
      const c = this.canvas, box = c.parentElement;
      const w = box.clientWidth, h = box.clientHeight;
      if (!w || !h) return;                                   // Hidden (other tab)
      const dpr = window.devicePixelRatio || 1;
      if (c.width !== w * dpr || c.height !== h * dpr) {
        c.width = w * dpr; c.height = h * dpr; c.style.width = w + 'px'; c.style.height = h + 'px';
      }
      const g = c.getContext('2d');
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, w, h);
      g.font = '11px "IBM Plex Mono", monospace';
      g.fillStyle = '#555';

      const pts = history.map((s) => ({ t: s.t, v: s[this.field][selected] })).filter((p) => p.v != null);
      const L = 56, R = 12, T = 8, B = 22, pw = w - L - R, ph = h - T - B;
      if (pts.length < 2) { g.textAlign = 'left'; g.fillText('Waiting for data…', L, T + ph / 2); return; }

      // Scales
      let lo = Math.min(...pts.map((p) => p.v)), hi = Math.max(...pts.map((p) => p.v));
      if (lo === hi) { lo -= 1; hi += 1; }
      const pad = (hi - lo) * 0.1; lo -= pad; hi += pad;
      const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
      const X = (t) => L + (t - t0) / (t1 - t0 || 1) * pw;
      const Y = (v) => T + (1 - (v - lo) / (hi - lo)) * ph;

      // Grid and axis labels
      g.strokeStyle = '#E2E2E2'; g.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const v = lo + (hi - lo) * i / 4, y = Y(v);
        g.beginPath(); g.moveTo(L, y); g.lineTo(L + pw, y); g.stroke();
        g.textAlign = 'right'; g.fillText(v.toFixed(this.digits), L - 6, y + 4);
      }
      g.textAlign = 'left'; g.fillText(hms(t0), L, h - 6);
      g.textAlign = 'right'; g.fillText(`${hms(t1)} UTC`, L + pw, h - 6);

      // Line
      g.strokeStyle = '#222'; g.lineWidth = 1.5; g.beginPath();
      pts.forEach((p, i) => (i ? g.lineTo(X(p.t), Y(p.v)) : g.moveTo(X(p.t), Y(p.v))));
      g.stroke();

      // Tracker: nearest point to the mouse
      if (this.hoverX != null && this.hoverX >= L && this.hoverX <= L + pw) {
        const tm = t0 + (this.hoverX - L) / pw * (t1 - t0);
        const p = pts.reduce((a, b) => (Math.abs(b.t - tm) < Math.abs(a.t - tm) ? b : a));
        const x = X(p.t), y = Y(p.v);
        g.strokeStyle = '#999'; g.setLineDash([3, 3]);
        g.beginPath(); g.moveTo(x, T); g.lineTo(x, T + ph); g.stroke(); g.setLineDash([]);
        g.fillStyle = '#222'; g.beginPath(); g.arc(x, y, 3.5, 0, 2 * Math.PI); g.fill();

        const label = `${hms(p.t)}  ${p.v.toFixed(this.digits)} ${this.units}`;
        g.font = '12px "IBM Plex Mono", monospace';
        const tw = g.measureText(label).width + 12;
        const bx = x + 8 + tw > L + pw ? x - 8 - tw : x + 8;
        const by = Math.max(T, y - 28);
        g.fillStyle = '#222'; g.fillRect(bx, by, tw, 20);
        g.fillStyle = '#fff'; g.textAlign = 'left'; g.fillText(label, bx + 6, by + 14);
      }
    }
  }

  // The page re-renders, which recreates the chart slots. Move the same chart
  // elements back in (except an expanded one, which stays in the overlay).
  function attach() {
    charts.forEach((c) => {
      if (c.expanded) return;
      const slot = document.getElementById(c.slotId);
      if (slot && c.root.parentNode !== slot) { slot.appendChild(c.root); c.draw(); }
    });
  }

  window.CssCharts = {
    init() {
      overlay = document.createElement('div');
      overlay.className = 'chart-overlay';
      overlay.addEventListener('click', (e) => {   // Click on the dark background closes it
        if (e.target === overlay) charts.forEach((c) => c.expanded && c.collapse());
      });
      document.body.appendChild(overlay);
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') charts.forEach((c) => c.expanded && c.collapse());
      });

      charts = [
        new LiveChart({ slotId: 'css-chart-raw', title: 'Raw value', field: 'raw', units: 'counts', digits: 0 }),
        new LiveChart({ slotId: 'css-chart-value', title: 'Converted value', field: 'value', units: 'V', digits: 3 })
      ];
      attach();
      new MutationObserver(attach).observe(document.getElementById('app'), { childList: true, subtree: true });
    },

    // Choose which item both charts plot
    select(name) {
      selected = name;
      charts.forEach((c) => { c.updateTitle(); c.draw(); });
    },

    // Add one backend reply (skips a packet that was already added)
    addSample(d) {
      if (!d.last_update) return;
      const t = Date.parse(d.last_update.replace(/\//g, '-').replace(' ', 'T') + 'Z');   // UTC
      if (history.length && history[history.length - 1].t >= t) return;
      const raw = {}, value = {};
      d.rows.forEach((r) => { raw[r.name] = r.raw; value[r.name] = r.value; });
      history.push({ t, raw, value });
      if (history.length > MAX_POINTS) history.shift();
      charts.forEach((c) => c.draw());
    }
  };
})();