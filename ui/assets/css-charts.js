/* CSS charts for the Telemetry page.
 * Two live line charts (raw counts, converted volts), each with an item dropdown,
 * a full screen button and a hover tracker.
 *
 * Use from a page:
 *   <script src="assets/css-charts.js"></script>
 *   CssCharts.init()            once, after COS3.mount(...)
 *   CssCharts.addSample(data)   for each /api/telemetry/css reply (or streamed packet)
 * The page must contain <div id="css-chart-raw"> and <div id="css-chart-value">.
 */
(function () {
  const ITEMS = ['RAW_CSS_0', 'RAW_CSS_1', 'RAW_CSS_2', 'RAW_CSS_3', 'RAW_CSS_4', 'RAW_CSS_5'];
  const MAX_POINTS = 600;   // About 10 minutes at 1 packet/s
  const history = [];       // [{ t: ms, raw: {RAW_CSS_0: 845, ...}, value: {RAW_CSS_0: 0.845, ...} }]
  let charts = [];

  const hms = (t) => new Date(t).toISOString().slice(11, 19);   // UTC hh:mm:ss

  // Styles live here so the page doesn't need them
  const style = document.createElement('style');
  style.textContent = `
    .chart{flex:1;min-width:0}
    .chart .plot{flex:1;min-height:0;position:relative}
    .chart canvas{display:block;cursor:crosshair}
    .chart:fullscreen{width:100vw;height:100vh;padding:24px;background:#fff}`;
  document.head.appendChild(style);

  class LiveChart {
    constructor({ slotId, title, field, units, digits }) {
      Object.assign(this, { slotId, field, units, digits, item: ITEMS[0], hoverX: null });

      this.root = document.createElement('section');
      this.root.className = 'pnl chart';
      this.root.innerHTML = `
        <div class="row" style="gap:8px">
          <span class="h" style="flex:1">${title}</span>
          <select aria-label="${title}: item" style="width:130px;height:28px">
            ${ITEMS.map((n) => `<option>${n}</option>`).join('')}
          </select>
          <button class="btn sm" type="button">Full screen</button>
        </div>
        <div class="plot"><canvas></canvas></div>`;

      this.canvas = this.root.querySelector('canvas');
      const select = this.root.querySelector('select');
      const fsBtn = this.root.querySelector('button');

      select.addEventListener('change', () => { this.item = select.value; this.draw(); });
      fsBtn.addEventListener('click', () => {
        if (document.fullscreenElement === this.root) document.exitFullscreen();
        else this.root.requestFullscreen();
      });
      document.addEventListener('fullscreenchange', () => {
        fsBtn.textContent = document.fullscreenElement === this.root ? 'Exit full screen' : 'Full screen';
      });
      this.canvas.addEventListener('mousemove', (e) => { this.hoverX = e.offsetX; this.draw(); });
      this.canvas.addEventListener('mouseleave', () => { this.hoverX = null; this.draw(); });
      new ResizeObserver(() => this.draw()).observe(this.root.querySelector('.plot'));
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

      const pts = history.map((s) => ({ t: s.t, v: s[this.field][this.item] })).filter((p) => p.v != null);
      const L = 56, R = 12, T = 8, B = 22, pw = w - L - R, ph = h - T - B;
      if (pts.length < 2) { g.fillText('Waiting for data…', L, T + ph / 2); return; }

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
  // elements back in, so the selection, hover and canvas are kept.
  function attach() {
    charts.forEach((c) => {
      const slot = document.getElementById(c.slotId);
      if (slot && c.root.parentNode !== slot) { slot.appendChild(c.root); c.draw(); }
    });
  }

  window.CssCharts = {
    init() {
      charts = [
        new LiveChart({ slotId: 'css-chart-raw', title: 'Raw value', field: 'raw', units: 'counts', digits: 0 }),
        new LiveChart({ slotId: 'css-chart-value', title: 'Converted value', field: 'value', units: 'V', digits: 3 })
      ];
      attach();
      new MutationObserver(attach).observe(document.getElementById('app'), { childList: true, subtree: true });
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