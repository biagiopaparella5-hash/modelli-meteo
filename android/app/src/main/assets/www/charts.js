// Grafici leggeri disegnati su <canvas>, senza librerie esterne.
(function () {
  const GG = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"];

  function niceTicks(min, max, n) {
    if (!isFinite(min) || !isFinite(max)) { min = 0; max = 1; }
    if (min === max) { min -= 1; max += 1; }
    const raw = (max - min) / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(s => s >= raw) || raw;
    const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
    const t = [];
    for (let v = lo; v <= hi + step / 2; v += step) t.push(+v.toFixed(6));
    return t;
  }

  class LineChart {
    constructor(container, opts) {
      this.o = Object.assign({ unit: "", zeroBased: false, decimals: 1, height: 190 }, opts);
      this.wrap = document.createElement("div");
      this.wrap.className = "wrap";
      this.cv = document.createElement("canvas");
      this.tip = document.createElement("div");
      this.tip.className = "tip hidden";
      this.wrap.append(this.cv, this.tip);
      container.appendChild(this.wrap);
      this.idx = -1;
      const move = e => {
        const r = this.cv.getBoundingClientRect();
        const x = e.clientX - r.left;
        this.setCursor(this.xToIdx(x));
      };
      this.cv.addEventListener("pointerdown", move);
      this.cv.addEventListener("pointermove", e => { if (e.pointerType === "mouse" || e.buttons) move(e); });
      this.cv.addEventListener("pointerleave", () => this.setCursor(-1));
      this.cv.addEventListener("pointerup", e => { if (e.pointerType !== "mouse") setTimeout(() => this.setCursor(-1), 2200); });
      new ResizeObserver(() => this.draw()).observe(this.wrap);
    }

    setData(times, series) { this.times = times; this.series = series; this.draw(); }

    layout() {
      const w = this.wrap.clientWidth, h = this.o.height;
      return { w, h, l: 34, r: 8, t: 20, b: 22 };
    }

    xToIdx(x) {
      const L = this.layout(), n = this.times.length;
      const i = Math.round(((x - L.l) / (L.w - L.l - L.r)) * (n - 1));
      return Math.max(0, Math.min(n - 1, i));
    }

    setCursor(i) {
      if (i === this.idx) return;
      this.idx = i;
      this.draw();
    }

    draw() {
      if (!this.times) return;
      const L = this.layout(), dpr = window.devicePixelRatio || 1;
      if (!L.w) return;
      this.cv.width = L.w * dpr; this.cv.height = L.h * dpr;
      this.cv.style.height = L.h + "px";
      const c = this.cv.getContext("2d");
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, L.w, L.h);
      const vis = this.series.filter(s => !s.hidden);
      let mn = Infinity, mx = -Infinity;
      vis.forEach(s => s.values.forEach(v => { if (v != null) { mn = Math.min(mn, v); mx = Math.max(mx, v); } }));
      if (this.o.zeroBased) mn = Math.min(0, mn);
      if (this.o.minSpan && mx - mn < this.o.minSpan) mx = mn + this.o.minSpan;
      const ticks = niceTicks(mn, mx, 4);
      const y0 = ticks[0], y1 = ticks[ticks.length - 1];
      const n = this.times.length;
      const X = i => L.l + (i / (n - 1)) * (L.w - L.l - L.r);
      const Y = v => L.t + (1 - (v - y0) / (y1 - y0 || 1)) * (L.h - L.t - L.b);

      // griglia orizzontale
      c.font = "11px Roboto, sans-serif";
      c.textAlign = "right"; c.textBaseline = "middle";
      ticks.forEach(t => {
        c.strokeStyle = "rgba(255,255,255,.07)"; c.lineWidth = 1;
        c.beginPath(); c.moveTo(L.l, Y(t)); c.lineTo(L.w - L.r, Y(t)); c.stroke();
        c.fillStyle = "#8b9ab3"; c.fillText(String(+t.toFixed(1)), L.l - 6, Y(t));
      });
      // separatori dei giorni
      c.textAlign = "left"; c.textBaseline = "top";
      this.times.forEach((t, i) => {
        if (t.getHours() === 0 && i > 0) {
          c.strokeStyle = "rgba(255,255,255,.10)";
          c.beginPath(); c.moveTo(X(i), L.t - 14); c.lineTo(X(i), L.h - L.b); c.stroke();
        }
        if (t.getHours() === 12) {
          c.fillStyle = "#8b9ab3"; c.textAlign = "center";
          c.fillText(GG[t.getDay()] + " " + t.getDate(), X(i), 2);
        }
      });
      // linea "adesso"
      const now = Date.now();
      const ni = this.times.findIndex(t => t.getTime() > now);
      if (ni > 0) {
        c.strokeStyle = "rgba(34,211,238,.55)"; c.setLineDash([3, 4]);
        c.beginPath(); c.moveTo(X(ni - 1), L.t); c.lineTo(X(ni - 1), L.h - L.b); c.stroke();
        c.setLineDash([]);
      }
      // serie
      vis.forEach(s => {
        c.strokeStyle = s.color; c.lineWidth = 2; c.lineJoin = "round";
        c.beginPath();
        let pen = false;
        s.values.forEach((v, i) => {
          if (v == null) { pen = false; return; }
          pen ? c.lineTo(X(i), Y(v)) : c.moveTo(X(i), Y(v));
          pen = true;
        });
        c.stroke();
      });
      // cursore + tooltip
      if (this.idx >= 0) {
        const i = this.idx, x = X(i);
        c.strokeStyle = "rgba(255,255,255,.5)"; c.lineWidth = 1;
        c.beginPath(); c.moveTo(x, L.t); c.lineTo(x, L.h - L.b); c.stroke();
        vis.forEach(s => {
          const v = s.values[i]; if (v == null) return;
          c.fillStyle = s.color; c.beginPath(); c.arc(x, Y(v), 3.5, 0, 7); c.fill();
        });
        const t = this.times[i];
        const rows = vis.filter(s => s.values[i] != null)
          .map(s => `<div><span><i style="--c:${s.color}"></i>${s.label}</span><span>${s.values[i].toFixed(this.o.decimals)} ${this.o.unit}</span></div>`).join("");
        this.tip.innerHTML = `<b>${GG[t.getDay()]} ${t.getDate()} · ${String(t.getHours()).padStart(2, "0")}:00</b>${rows}`;
        this.tip.classList.remove("hidden");
        const tw = this.tip.offsetWidth;
        this.tip.style.left = (x + 12 + tw > L.w ? Math.max(0, x - tw - 12) : x + 12) + "px";
      } else {
        this.tip.classList.add("hidden");
      }
    }
  }

  window.LineChart = LineChart;
})();
