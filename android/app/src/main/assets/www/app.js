(function () {
  "use strict";
  const $ = s => document.querySelector(s);
  const BASE = window.DATA_URL.replace(/\/?$/, "/");
  const MODEL_COLORS = { gfs: "#4f8cff", ecmwf: "#22c55e", icon: "#f59e0b" };
  const ORDER = ["gfs", "ecmwf", "icon"];
  const fmtValid = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" });
  const fmtRun = new Intl.DateTimeFormat("it-IT", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", timeZone: "UTC" });
  const fmtShort = new Intl.DateTimeFormat("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" });

  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage non disponibile */ } },
  };

  const S = Object.assign({ model: "gfs", map: "z500", area: "it", step: 24, compare: false }, store.get("mapState", {}));
  let manifest = null, playing = null;

  // ================================================================ NAVIGAZIONE
  document.querySelectorAll("nav.bottom button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
  function showTab(id) {
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + id));
    document.querySelectorAll("nav.bottom button").forEach(b => b.classList.toggle("active", b.dataset.tab === id));
    window.scrollTo(0, 0);
    if (id === "local") Local.init();
    if (id === "info") renderInfo();
    if (id !== "mappe") stopPlay();
  }
  // chiamata dal pulsante "indietro" di Android: true = gestito dall'app
  window.handleBack = function () {
    if (!$("#searchResults").classList.contains("hidden")) { $("#searchResults").classList.add("hidden"); return true; }
    if (!$("#tab-mappe").classList.contains("active")) { showTab("mappe"); return true; }
    if (Zoom.scale > 1) { Zoom.reset(); return true; }
    return false;
  };

  // ================================================================ MANIFEST
  async function loadManifest() {
    $("#runInfo").textContent = "Caricamento…";
    try {
      const r = await fetch(BASE + "manifest.json?t=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      manifest = await r.json();
      store.set("manifest", manifest);
    } catch (e) {
      manifest = store.get("manifest", null);
      if (!manifest) {
        $("#runInfo").textContent = "Dati non disponibili";
        showMsg("Non riesco a scaricare le mappe.<br>Controlla la connessione o che GitHub Pages sia attivo.");
        return;
      }
    }
    if (!manifest.models[S.model]) S.model = ORDER.find(m => manifest.models[m]) || Object.keys(manifest.models)[0];
    buildControls();
    update();
  }

  function stepsFor(model, map = S.map, area = S.area) {
    const m = manifest && manifest.models[model];
    return (m && m.maps[map] && m.maps[map][area]) || [];
  }
  const imgUrl = (model, step, map = S.map, area = S.area) =>
    `${BASE}maps/${model}/${area}/${map}/${String(step).padStart(3, "0")}.png?r=${encodeURIComponent(manifest.models[model].run)}`;

  // ================================================================ CONTROLLI
  function buildControls() {
    const seg = $("#modelSeg"); seg.innerHTML = "";
    ORDER.filter(m => manifest.models[m]).forEach(m => {
      const b = document.createElement("button");
      b.textContent = manifest.models[m].label; b.dataset.m = m;
      b.style.setProperty("--c", MODEL_COLORS[m]);
      b.onclick = () => { S.model = m; if (S.compare) toggleCompare(false); update(); };
      seg.appendChild(b);
    });
    const chips = $("#mapChips"); chips.innerHTML = "";
    Object.entries(manifest.maps).forEach(([id, spec]) => {
      const b = document.createElement("button");
      b.className = "chip"; b.textContent = spec.short; b.dataset.map = id; b.title = spec.label;
      b.onclick = () => { S.map = id; update(); };
      chips.appendChild(b);
    });
    const as = $("#areaSeg"); as.innerHTML = "";
    Object.entries(manifest.areas).forEach(([id, label]) => {
      const b = document.createElement("button");
      b.textContent = label; b.dataset.a = id;
      b.onclick = () => { S.area = id; Zoom.reset(); update(); };
      as.appendChild(b);
    });
  }

  function currentSteps() {
    if (!S.compare) return stepsFor(S.model);
    // in confronto: unione delle scadenze dei modelli che hanno la mappa
    const set = new Set();
    ORDER.forEach(m => stepsFor(m).forEach(s => set.add(s)));
    return [...set].sort((a, b) => a - b);
  }

  function nearest(arr, v) {
    return arr.reduce((best, x) => Math.abs(x - v) < Math.abs(best - v) ? x : best, arr[0]);
  }

  function update() {
    if (!manifest) return;
    // se il modello non ha questa mappa (es. CAPE su ECMWF) scegline un altro
    if (!S.compare && !stepsFor(S.model).length) {
      const alt = ORDER.find(m => stepsFor(m).length);
      if (alt) S.model = alt; else S.map = Object.keys(manifest.maps)[0];
    }
    document.querySelectorAll("#modelSeg button").forEach(b => {
      b.classList.toggle("on", !S.compare && b.dataset.m === S.model);
      b.disabled = !stepsFor(b.dataset.m).length;
    });
    document.querySelectorAll("#mapChips .chip").forEach(b => {
      b.classList.toggle("on", b.dataset.map === S.map);
      b.disabled = S.compare ? false : !stepsFor(S.model, b.dataset.map).length;
    });
    document.querySelectorAll("#areaSeg button").forEach(b => b.classList.toggle("on", b.dataset.a === S.area));
    $("#btnCompare").setAttribute("aria-pressed", S.compare);

    const steps = currentSteps();
    if (!steps.length) { showMsg("Mappa non disponibile per questo modello."); return; }
    if (!steps.includes(S.step)) S.step = nearest(steps, S.step);
    const sl = $("#slider");
    sl.max = steps.length - 1; sl.value = steps.indexOf(S.step);
    sl.style.setProperty("--p", (steps.length > 1 ? (sl.value / (steps.length - 1)) * 100 : 0) + "%");
    const tk = $("#ticks");
    tk.innerHTML = [steps[0], steps[Math.floor(steps.length / 2)], steps[steps.length - 1]].map(s => `<span>+${s}h</span>`).join("");

    const m = manifest.models[S.compare ? (ORDER.find(x => manifest.models[x]) || S.model) : S.model];
    const run = new Date(m.run);
    const valid = new Date(run.getTime() + S.step * 3600e3);
    $("#validLabel").textContent = cap(fmtValid.format(valid));
    $("#stepLabel").textContent = S.compare ? `+${S.step}h · confronto modelli` : `+${S.step}h · corsa ${fmtRun.format(run)} UTC`;
    $("#runInfo").textContent = S.compare ? "Confronto GFS · ECMWF · ICON" : `${m.label} · corsa ${fmtRun.format(run)} UTC`;
    store.set("mapState", S);
    renderViewer();
    preload(steps);
  }

  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

  function showMsg(html) {
    $("#viewerInner").innerHTML = "";
    const el = $("#viewerMsg"); el.innerHTML = html; el.classList.remove("hidden");
  }

  function renderViewer() {
    const v = $("#viewer"), inner = $("#viewerInner");
    $("#viewerMsg").classList.add("hidden");
    v.classList.toggle("compare", S.compare);
    if (S.compare) {
      Zoom.reset();
      inner.innerHTML = "";
      ORDER.filter(m => stepsFor(m).length).forEach(m => {
        const box = document.createElement("div"); box.className = "cmp";
        if (stepsFor(m).includes(S.step)) {
          const img = new Image(); img.src = imgUrl(m, S.step); img.alt = m; box.appendChild(img);
        } else {
          box.innerHTML = `<div class="empty">${manifest.models[m].label}: scadenza +${S.step}h non disponibile</div>`;
        }
        inner.appendChild(box);
      });
      return;
    }
    let img = inner.querySelector("img");
    if (!img) { inner.innerHTML = ""; img = new Image(); img.alt = "mappa"; inner.appendChild(img); }
    const url = imgUrl(S.model, S.step);
    if (img.dataset.url === url) return;
    img.dataset.url = url;
    v.classList.add("loading");
    const pre = cache.get(url) || new Image();
    pre.onload = () => { if (img.dataset.url === url) { img.src = url; v.classList.remove("loading"); } };
    pre.onerror = () => { if (img.dataset.url === url) { v.classList.remove("loading"); showMsg("Immagine non disponibile"); } };
    if (!pre.src) pre.src = url; else if (pre.complete) pre.onload();
  }

  const cache = new Map();
  function preload(steps) {
    if (S.compare) return;
    const i = steps.indexOf(S.step);
    const order = steps.slice(i + 1).concat(steps.slice(0, i));
    order.slice(0, 40).forEach((s, k) => setTimeout(() => {
      const url = imgUrl(S.model, s);
      if (!cache.has(url)) { const im = new Image(); im.src = url; cache.set(url, im); }
    }, k * 60));
  }

  function go(delta) {
    const steps = currentSteps(); if (!steps.length) return;
    let i = steps.indexOf(S.step) + delta;
    if (i < 0) i = steps.length - 1; if (i >= steps.length) i = 0;
    S.step = steps[i]; update();
  }
  $("#btnPrev").onclick = () => { stopPlay(); go(-1); };
  $("#btnNext").onclick = () => { stopPlay(); go(1); };
  $("#slider").oninput = e => { stopPlay(); S.step = currentSteps()[+e.target.value]; update(); };
  $("#btnPlay").onclick = () => playing ? stopPlay() : startPlay();
  function startPlay() {
    playing = setInterval(() => go(1), 700);
    $("#playIcon").innerHTML = '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>';
  }
  function stopPlay() {
    if (playing) clearInterval(playing); playing = null;
    $("#playIcon").innerHTML = '<path d="M8 5v14l11-7z"/>';
  }
  function toggleCompare(on) { S.compare = on; update(); }
  $("#btnCompare").onclick = () => toggleCompare(!S.compare);

  // scorrimento orizzontale sulla mappa = cambio scadenza (solo senza zoom)
  // ================================================================ ZOOM
  const Zoom = {
    scale: 1, x: 0, y: 0,
    apply() { $("#viewerInner").style.transform = `translate(${this.x}px,${this.y}px) scale(${this.scale})`; },
    reset() { this.scale = 1; this.x = 0; this.y = 0; this.apply(); },
    clamp() {
      const v = $("#viewer"), w = v.clientWidth, h = v.clientHeight;
      this.scale = Math.min(Math.max(this.scale, 1), 5);
      this.x = Math.min(0, Math.max(w - w * this.scale, this.x));
      this.y = Math.min(0, Math.max(h - h * this.scale, this.y));
    },
  };
  (function setupZoom() {
    const v = $("#viewer");
    const pts = new Map();
    let start = null, lastTap = 0, swipe = null;
    const rel = e => { const r = v.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    v.addEventListener("pointerdown", e => {
      if (S.compare) return;
      v.setPointerCapture(e.pointerId);
      pts.set(e.pointerId, rel(e));
      if (pts.size === 1) {
        const now = Date.now();
        if (now - lastTap < 280) {      // doppio tocco
          const p = rel(e);
          if (Zoom.scale > 1) Zoom.reset();
          else { Zoom.scale = 2.5; Zoom.x = p.x - p.x * 2.5; Zoom.y = p.y - p.y * 2.5; Zoom.clamp(); Zoom.apply(); }
          lastTap = 0; return;
        }
        lastTap = now;
        swipe = { ...rel(e), t: now };
      }
      start = snapshot();
    });
    v.addEventListener("pointermove", e => {
      if (!pts.has(e.pointerId) || S.compare) return;
      pts.set(e.pointerId, rel(e));
      const cur = snapshot();
      if (pts.size >= 2 && start && start.d) {
        const k = cur.d / start.d;
        const ns = Math.min(Math.max(start.s * k, 1), 5);
        Zoom.x = cur.cx - (start.cx - start.x) * (ns / start.s);
        Zoom.y = cur.cy - (start.cy - start.y) * (ns / start.s);
        Zoom.scale = ns; Zoom.clamp(); Zoom.apply();
      } else if (pts.size === 1 && Zoom.scale > 1 && start) {
        Zoom.x = start.x + (cur.cx - start.cx); Zoom.y = start.y + (cur.cy - start.cy);
        Zoom.clamp(); Zoom.apply();
      }
    });
    const end = e => {
      const p = pts.get(e.pointerId);
      pts.delete(e.pointerId);
      if (pts.size === 0 && swipe && p && Zoom.scale === 1) {
        const dx = p.x - swipe.x, dy = p.y - swipe.y;
        if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5 && Date.now() - swipe.t < 600) { stopPlay(); go(dx < 0 ? 1 : -1); }
      }
      if (pts.size < 2) swipe = pts.size ? swipe : null;
      start = snapshot();
    };
    v.addEventListener("pointerup", end);
    v.addEventListener("pointercancel", end);
    function snapshot() {
      const a = [...pts.values()];
      if (!a.length) return null;
      const cx = a.reduce((s, p) => s + p.x, 0) / a.length, cy = a.reduce((s, p) => s + p.y, 0) / a.length;
      const d = a.length >= 2 ? Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y) : 0;
      return { cx, cy, d, s: Zoom.scale, x: Zoom.x, y: Zoom.y };
    }
  })();

  // ================================================================ LOCALITÀ
  const Local = {
    ready: false, place: null, hidden: store.get("hiddenModels", []), charts: [],
    init() {
      if (this.ready) return;
      this.ready = true;
      this.renderFavs();
      const last = store.get("lastPlace", null);
      this.open(last || { name: "Roma", admin1: "Lazio", latitude: 41.89, longitude: 12.48 });
    },
    favs() { return store.get("favs", [{ name: "Roma", admin1: "Lazio", latitude: 41.89, longitude: 12.48 }, { name: "Milano", admin1: "Lombardia", latitude: 45.46, longitude: 9.19 }, { name: "Napoli", admin1: "Campania", latitude: 40.85, longitude: 14.27 }]); },
    renderFavs() {
      const box = $("#favs"); box.innerHTML = "";
      this.favs().forEach(p => {
        const b = document.createElement("button");
        b.className = "chip" + (this.place && same(p, this.place) ? " on" : "");
        b.textContent = p.name;
        b.onclick = () => this.open(p);
        box.appendChild(b);
      });
    },
    toggleFav() {
      let f = this.favs();
      if (f.some(p => same(p, this.place))) f = f.filter(p => !same(p, this.place));
      else f.push(this.place);
      store.set("favs", f); this.renderFavs(); this.renderHeroStar();
    },
    renderHeroStar() {
      const s = $("#star"); if (!s) return;
      const on = this.favs().some(p => same(p, this.place));
      s.classList.toggle("on", on); s.textContent = on ? "★" : "☆";
    },
    async open(p) {
      this.place = p; store.set("lastPlace", p); this.renderFavs();
      $("#searchResults").classList.add("hidden");
      const body = $("#localBody");
      body.innerHTML = `<div class="empty">Carico le previsioni per ${esc(p.name)}…</div>`;
      try {
        const data = await fetchPoint(p);
        this.render(data);
      } catch (e) {
        body.innerHTML = `<div class="empty">Impossibile scaricare le previsioni.<br><small>${esc(String(e.message || e))}</small></div>`;
      }
    },
    render(d) {
      const p = this.place, body = $("#localBody");
      const times = d.hourly.time.map(t => new Date(t));
      const models = window.POINT_MODELS.filter(m => d.hourly["temperature_2m_" + m.id] && d.hourly["temperature_2m_" + m.id].some(v => v != null));
      const get = (v, m) => d.hourly[v + "_" + m.id] || [];
      const nowI = Math.max(0, times.findIndex(t => t.getTime() > Date.now()) - 1);
      const first = models[0];
      const tNow = first ? get("temperature_2m", first)[nowI] : null;
      body.innerHTML = `
        <div class="hero">
          <div><h2>${esc(p.name)}</h2><div class="muted small-txt">${esc([p.admin1, p.country].filter(Boolean).join(", "))}</div></div>
          <div style="text-align:right"><button id="star" class="star">☆</button><div class="temp">${tNow != null ? Math.round(tNow) + "°" : "–"}</div></div>
        </div>
        <div class="days" id="days"></div>
        <div class="legend" id="legend"></div>
        <div class="card chart" id="cT"><h3>Temperatura 2 m <span>°C</span></h3></div>
        <div class="card chart" id="cP"><h3>Pioggia cumulata <span>mm</span></h3></div>
        <div class="card chart" id="cW"><h3>Raffiche di vento <span>km/h</span></h3></div>
        <div class="card chart" id="cM"><h3>Pressione al suolo <span>hPa</span></h3></div>`;
      $("#star").onclick = () => this.toggleFav();
      this.renderHeroStar();
      this.renderDays(times, models, get);

      const mk = (fn) => models.map(m => ({ id: m.id, label: m.label, color: m.color, values: fn(m), hidden: this.hidden.includes(m.id) }));
      const cum = arr => { let s = 0; return arr.map(v => v == null ? null : (s += v)); };
      this.charts = [
        [new LineChart($("#cT"), { unit: "°C", minSpan: 6 }), mk(m => get("temperature_2m", m))],
        [new LineChart($("#cP"), { unit: "mm", zeroBased: true, minSpan: 5 }), mk(m => cum(get("precipitation", m)))],
        [new LineChart($("#cW"), { unit: "km/h", zeroBased: true, decimals: 0, minSpan: 20 }), mk(m => get("wind_gusts_10m", m).some(v => v != null) ? get("wind_gusts_10m", m) : get("wind_speed_10m", m))],
        [new LineChart($("#cM"), { unit: "hPa", decimals: 0, minSpan: 10 }), mk(m => get("pressure_msl", m))],
      ];
      this.charts.forEach(([c, s]) => c.setData(times, s));

      const lg = $("#legend");
      models.forEach(m => {
        const b = document.createElement("button");
        b.innerHTML = `<i style="--c:${m.color}"></i>${m.label}`;
        b.classList.toggle("off", this.hidden.includes(m.id));
        b.onclick = () => {
          const h = this.hidden.includes(m.id);
          this.hidden = h ? this.hidden.filter(x => x !== m.id) : this.hidden.concat(m.id);
          store.set("hiddenModels", this.hidden);
          b.classList.toggle("off", !h);
          this.charts.forEach(([c, s]) => { s.forEach(x => x.hidden = this.hidden.includes(x.id)); c.draw(); });
        };
        lg.appendChild(b);
      });
    },
    renderDays(times, models, get) {
      const box = $("#days"), days = new Map();
      times.forEach((t, i) => {
        const k = t.toDateString();
        if (!days.has(k)) days.set(k, { date: t, idx: [] });
        days.get(k).idx.push(i);
      });
      const G = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"];
      [...days.values()].slice(0, 7).forEach(({ date, idx }) => {
        // media tra i modelli disponibili
        const per = models.map(m => {
          const t = idx.map(i => get("temperature_2m", m)[i]).filter(v => v != null);
          const r = idx.map(i => get("precipitation", m)[i]).filter(v => v != null);
          const cc = idx.map(i => get("cloud_cover", m)[i]).filter(v => v != null);
          return t.length ? { mx: Math.max(...t), mn: Math.min(...t), rr: r.reduce((a, b) => a + b, 0), cc: cc.length ? cc.reduce((a, b) => a + b, 0) / cc.length : null } : null;
        }).filter(Boolean);
        if (!per.length) return;
        const avg = k => per.reduce((s, x) => s + (x[k] ?? 0), 0) / per.length;
        const rr = avg("rr"), cc = per.some(x => x.cc != null) ? avg("cc") : 50;
        const el = document.createElement("div"); el.className = "day";
        el.innerHTML = `<div class="d">${G[date.getDay()]} ${date.getDate()}</div>${icon(rr, cc, avg("mx"))}
          <div class="mx">${Math.round(avg("mx"))}°</div><div class="mn">${Math.round(avg("mn"))}°</div>
          <div class="rr">${rr >= 0.5 ? rr.toFixed(rr < 10 ? 1 : 0) + " mm" : "&nbsp;"}</div>`;
        box.appendChild(el);
      });
    },
  };

  function icon(rr, cc, tmax) {
    const sun = '<circle cx="12" cy="12" r="4.2" fill="#fbbf24" stroke="#fbbf24"/><g stroke="#fbbf24"><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></g>';
    const cloud = (f) => `<path d="M7 18h10a4 4 0 0 0 .4-8A5.5 5.5 0 0 0 6.8 11 3.5 3.5 0 0 0 7 18z" fill="${f}" stroke="${f}"/>`;
    const drops = (c) => `<g stroke="${c}"><path d="M9 20.5l-1 2M13 20.5l-1 2M17 20.5l-1 2"/></g>`;
    const flakes = '<g fill="#e0f2fe" stroke="none"><circle cx="9" cy="21.5" r="1"/><circle cx="13" cy="22" r="1"/><circle cx="16.5" cy="21.5" r="1"/></g>';
    let g;
    if (rr >= 1) g = `<g transform="translate(0,-2)">${cloud("#9fb3d1")}</g>` + (tmax < 2 ? flakes : drops("#60a5fa"));
    else if (cc > 70) g = cloud("#9fb3d1");
    else if (cc > 30) g = `<g transform="translate(-3,-3) scale(.8)">${sun}</g><g transform="translate(2,2) scale(.85)">${cloud("#cbd5e1")}</g>`;
    else g = sun;
    return `<svg viewBox="0 0 24 24" stroke-width="1.6">${g}</svg>`;
  }

  async function fetchPoint(p) {
    const hourly = "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m,pressure_msl,cloud_cover";
    const q = (models) => `https://api.open-meteo.com/v1/forecast?latitude=${p.latitude}&longitude=${p.longitude}` +
      `&hourly=${hourly}&models=${models.map(m => m.id).join(",")}&forecast_days=7&timezone=auto&wind_speed_unit=kmh`;
    let r = await fetch(q(window.POINT_MODELS));
    if (!r.ok) r = await fetch(q(window.POINT_MODELS.slice(0, 3)));   // se un modello non è supportato
    if (!r.ok) throw new Error("Errore " + r.status);
    return r.json();
  }

  const same = (a, b) => a && b && Math.abs(a.latitude - b.latitude) < 0.01 && Math.abs(a.longitude - b.longitude) < 0.01;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let searchT = null;
  $("#searchInput").addEventListener("input", e => {
    clearTimeout(searchT);
    const q = e.target.value.trim();
    if (q.length < 2) { $("#searchResults").classList.add("hidden"); return; }
    searchT = setTimeout(async () => {
      try {
        const r = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(q)}&count=6&language=it&format=json`);
        const d = await r.json();
        const box = $("#searchResults"); box.innerHTML = "";
        (d.results || []).forEach(p => {
          const b = document.createElement("button");
          b.innerHTML = `${esc(p.name)} <small>${esc([p.admin1, p.country].filter(Boolean).join(", "))}</small>`;
          b.onclick = () => { $("#searchInput").value = ""; $("#searchInput").blur(); Local.open({ name: p.name, admin1: p.admin1, country: p.country, latitude: p.latitude, longitude: p.longitude }); };
          box.appendChild(b);
        });
        if (!d.results) box.innerHTML = '<div class="empty">Nessun risultato</div>';
        box.classList.remove("hidden");
      } catch (err) { /* offline */ }
    }, 300);
  });

  $("#btnGps").onclick = () => {
    if (!navigator.geolocation) return;
    $("#btnGps").textContent = "📍 …";
    navigator.geolocation.getCurrentPosition(async pos => {
      $("#btnGps").textContent = "📍 Posizione";
      const { latitude, longitude } = pos.coords;
      Local.open({ name: "La mia posizione", admin1: `${latitude.toFixed(2)}, ${longitude.toFixed(2)}`, latitude, longitude });
    }, () => { $("#btnGps").textContent = "📍 Posizione"; alertMsg("Posizione non disponibile: controlla i permessi."); },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
  };
  function alertMsg(t) { $("#localBody").insertAdjacentHTML("afterbegin", `<div class="empty">${esc(t)}</div>`); }

  // ================================================================ INFO
  function renderInfo() {
    const box = $("#infoBody");
    const rows = manifest ? ORDER.filter(m => manifest.models[m]).map(m => {
      const x = manifest.models[m];
      return `<div class="info-model"><span class="badge" style="--c:${MODEL_COLORS[m]}">${x.label}</span>
        <div class="meta"><b>${x.org}</b> · risoluzione ${x.res}<br><span class="muted">Corsa ${fmtRun.format(new Date(x.run))} UTC</span></div></div>`;
    }).join("") : '<div class="empty">Nessun dato caricato</div>';
    box.innerHTML = `
      <div class="card">${rows}</div>
      <div class="info">
        <p class="muted small-txt">Mappe generate: ${manifest ? fmtShort.format(new Date(manifest.generated)) : "–"}</p>
        <h3>Come si aggiorna</h3>
        <p>Le mappe vengono scaricate e disegnate automaticamente quattro volte al giorno, appena escono le nuove corse dei modelli. Apri l'app o premi “Aggiorna” per vedere l'ultima corsa.</p>
        <h3>Fonti dei dati</h3>
        <p>GFS: NOAA/NCEP · ECMWF: ECMWF Open Data, licenza CC BY 4.0 · ICON-EU: Deutscher Wetterdienst.<br>Previsioni per località: Open-Meteo.com (CC BY 4.0).</p>
        <p class="muted small-txt">Modelli Meteo v1.1</p>
      </div>`;
  }
  $("#btnReload").onclick = async () => { cache.clear(); await loadManifest(); renderInfo(); };

  document.addEventListener("visibilitychange", () => { if (document.hidden) stopPlay(); });
  loadManifest();
})();
