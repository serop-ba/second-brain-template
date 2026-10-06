// The orbit map on the Overview: the brain drawn as a solar system. The company is
// the sun, each department a planet, and everything filed under it (documents,
// log entries, decisions, metrics) its moons. Skills circle the sun,
// automations ride the outer ring with their jobs in tow. Every dot is a real
// row from /api/graph (graph.py). Two views morph into each other: ORBIT (3D,
// moving) and RINGS (the same nodes laid out by layer). Click a planet, a
// document, a decision or a metric to open it.
const Orbit = (() => {
  const PALETTE = ["#b38cff", "#ffc24b", "#3ee0c5", "#5aa9ff", "#5ee38f", "#ff7eb6", "#7ee0ff", "#ffd36e", "#c8ff6e", "#ff9a6e"];
  const SYSTEM_COLOR = "#9aa0ad";
  const COLORS = { system: SYSTEM_COLOR };
  const KINDS = [["skill", "◇", "skill"], ["file", "○", "file"], ["routine", "◎", "routine"], ["app", "⬡", "app"],
    ["run", "•", "run"], ["decision", "◆", "decision"], ["metric", "▲", "metric"]];
  const KIND_NAME = { core: "the company", area: "department", skill: "skill", file: "document", routine: "routine", app: "automation", run: "log entry", decision: "decision", metric: "metric" };
  const MONO = '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace';
  const TAU = Math.PI * 2;
  const ease = (x) => (x >= 1 ? 1 : 1 - Math.pow(1 - x, 3));

  let el, cv, ctx, tip, W = 0, H = 0, DPR = 1;
  let nodes = [], byId = {}, links = [], planets = [], counts = {}, loaded = 0;
  const pref = (k, d) => { try { const v = localStorage.getItem("orbit." + k); return v === null ? d : JSON.parse(v); } catch { return d; } };
  const keep = (k, v) => { try { localStorage.setItem("orbit." + k, JSON.stringify(v)); } catch {} };
  let view = pref("view", "orbit"), names = pref("names", false);
  let motion = pref("motion", !matchMedia("(prefers-reduced-motion: reduce)").matches);
  let focusDept = null, focusKind = null, hover = null, drag = null;
  let yaw = 0, elev = 0.42, zoom = 1, time = 0, last = 0, morph = 1, visible = true, dirty = true;
  let activity = false, pulses = [], nextPulse = 0, maxDate = "";

  // ---------------------------------------------------------------- data
  function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(s) { let a = hash(s); return () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const colorOf = (dept, i = 0) => COLORS[dept] || PALETTE[i % PALETTE.length];

  function prepare(g) {
    const old = byId;
    nodes = g.nodes.map((n) => Object.assign(old[n.id] || {}, n));
    byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    links = g.links.filter(([a, b]) => byId[a] && byId[b]).map(([a, b]) => [byId[a], byId[b]]);
    counts = g.counts;
    maxDate = nodes.reduce((m, n) => (n.date && n.date > m ? n.date : m), "");
    planets = nodes.filter((n) => n.kind === "area");
    const N = planets.length, P = {};
    planets.forEach((p, i) => {
      P[p.dept] = p; p.i = i; p.color = colorOf(p.dept, i);
      p.angle = -Math.PI / 2 + ((i + 0.5) / N) * TAU;  // a gap at 12 o'clock for the ring labels
      p.orb = 0.3 + (N > 1 ? i / (N - 1) : 0) * 0.4;
    });
    for (const n of nodes) {
      const r = rng(n.id); n.r = [r(), r(), r(), r(), r()];
      n.planet = P[n.dept] || P.system || planets[0];
      n.color = n.planet ? n.planet.color : COLORS.system;
      n.recent = n.kind === "run" && n.date && maxDate && (new Date(maxDate) - new Date(n.date)) / 864e5 <= 3;
    }
    const sector = (TAU / Math.max(N, 1)) * 0.8;
    const order = { file: 0, metric: 1, decision: 2, run: 3 };
    for (const p of planets) {
      p.moons = nodes.filter((n) => n.planet === p && (order[n.kind] !== undefined || (n.kind === "routine" && !n.parent)));
      p.moons.forEach((m, j) => { m.j = j; m.of = p.moons.length; });
      p.count = nodes.filter((n) => n.planet === p && n.kind !== "area").length;
      // RINGS: memory fills the department's sector row by row, outward
      const mem = p.moons.filter((m) => m.kind !== "routine").sort((a, b) => order[a.kind] - order[b.kind] || a.id.localeCompare(b.id));
      let k = 0;
      for (let row = 0; k < mem.length; row++) {
        const rad = 0.38 + row * 0.045, cols = Math.max(2, Math.floor((rad * sector) / 0.038));
        for (let c = 0; c < cols && k < mem.length; c++, k++) mem[k].ring = [rad, p.angle - sector / 2 + ((c + 0.5) * sector) / cols];
      }
      const spread = (list, rad) => list.forEach((n, i) => (n.ring = [rad, p.angle - sector / 2 + ((i + 0.5) * sector) / list.length]));
      spread(nodes.filter((n) => n.planet === p && n.kind === "routine"), 0.83);
      spread(nodes.filter((n) => n.planet === p && n.kind === "app"), 0.94);
      p.ring = [0.3, p.angle];
    }
    const skills = nodes.filter((n) => n.kind === "skill"), apps = nodes.filter((n) => n.kind === "app");
    skills.forEach((n, i) => { n.si = i / skills.length; n.ring = [0.18, -Math.PI / 2 + n.si * TAU]; });
    apps.forEach((n, i) => {
      n.ai = i / apps.length;
      const kids = nodes.filter((k) => k.parent === n.id);
      kids.forEach((k, j) => { k.ci = j; k.cn = kids.length; });
    });
    const core = byId.core; if (core) core.ring = [0, 0];
    loaded = Date.now(); dirty = true;
    renderChrome();
  }

  async function load() {
    try { prepare(await api("/api/graph")); } catch (e) { /* the rest of the page still works */ }
  }

  // ---------------------------------------------------------------- layout
  function world(n, t) {
    switch (n.kind) {
      case "core": return [0, 0, 0];
      case "area": { const a = n.angle + t * 0.021 / Math.pow(n.orb, 1.5); return [n.orb * Math.cos(a), 0, n.orb * Math.sin(a)]; }
      case "skill": { const a = n.si * TAU + t * 0.09; return [0.16 * Math.cos(a), 0.015 * Math.sin(a * 3), 0.16 * Math.sin(a)]; }
      case "app": { const a = n.ai * TAU - t * 0.014; return [0.92 * Math.cos(a), 0, 0.92 * Math.sin(a)]; }
    }
    let base, rm, inc, node, phi;
    if (n.kind === "routine" && n.parent && byId[n.parent]) {
      base = byId[n.parent].w; rm = 0.04 + (n.ci % 3) * 0.011;
      inc = 0.9; node = n.r[2] * TAU; phi = (n.ci / n.cn) * TAU + t * 0.45;
    } else {
      base = n.planet ? n.planet.w : [0, 0, 0];
      rm = 0.034 + (0.05 + 0.012 * Math.sqrt(n.of || 1)) * Math.sqrt((n.j + 1) / (n.of || 1)) + n.r[0] * 0.008;
      inc = (n.r[1] - 0.5) * 1.5; node = n.r[2] * TAU;
      phi = n.r[3] * TAU + t * (0.2 / (rm * 10)) * (n.r[4] < 0.15 ? -1 : 1);
    }
    let x = rm * Math.cos(phi), y = 0, z = rm * Math.sin(phi);
    [y, z] = [-z * Math.sin(inc), z * Math.cos(inc)];
    [x, z] = [x * Math.cos(node) - z * Math.sin(node), x * Math.sin(node) + z * Math.cos(node)];
    return [base[0] + x, base[1] + y, base[2] + z];
  }

  function scale() {
    return view === "orbit" ? Math.min(W * 0.46, (H * 0.44) / (Math.sin(elev) + 0.14)) * zoom : Math.min(W * 0.46, (H - 110) * 0.515) * zoom;
  }
  const midY = () => H / 2 + (view === "orbit" ? 24 : 50);
  function project(p, S) {
    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    const x = p[0] * cy - p[2] * sy, z = p[0] * sy + p[2] * cy;
    const ys = p[1] * Math.cos(elev) + z * Math.sin(elev), depth = z * Math.cos(elev) - p[1] * Math.sin(elev);
    const s = 3 / (3 - depth);
    return [W / 2 + x * s * S, midY() + ys * s * S, depth, s];
  }
  function ringPos(n, t, S) {
    const [rad0, ang0] = n.ring || [0.5, 0];
    const rad = rad0 + (motion && n.kind !== "core" ? Math.sin(t * 0.8 + n.r[0] * TAU) * 0.0035 : 0);
    const a = ang0 + yaw + t * 0.006;
    return [W / 2 + Math.cos(a) * rad * S, midY() + Math.sin(a) * rad * S, 0, 1];
  }

  function layout() {
    const S = scale();
    if (view === "orbit") {
      for (const n of nodes) if (["core", "area", "skill", "app"].includes(n.kind)) n.w = world(n, time);
      for (const n of nodes) if (!n.w || !["core", "area", "skill", "app"].includes(n.kind)) n.w = world(n, time);
    }
    const k = ease(morph);
    for (const n of nodes) {
      const [x, y, d, s] = view === "orbit" ? project(n.w, S) : ringPos(n, time, S);
      n.tx = x; n.ty = y; n.d = d; n.s = s;
      n.x = n.fx === undefined || k >= 1 ? x : n.fx + (x - n.fx) * k;
      n.y = n.fy === undefined || k >= 1 ? y : n.fy + (y - n.fy) * k;
    }
    return S;
  }

  // ---------------------------------------------------------------- drawing
  const inFocus = (n) => n.kind === "core" || ((!focusDept || n.dept === focusDept) && (!focusKind || n.kind === focusKind || n.kind === "area"));
  function hexPath(x, y, r) { ctx.beginPath(); for (let i = 0; i < 6; i++) { const a = Math.PI / 6 + (i * TAU) / 6; ctx[i ? "lineTo" : "moveTo"](x + r * Math.cos(a), y + r * Math.sin(a)); } ctx.closePath(); }
  function rgba(hex, a) { const v = parseInt(hex.slice(1), 16); return `rgba(${v >> 16},${(v >> 8) & 255},${v & 255},${a})`; }
  function pill(text, x, y, color, bg = "rgba(8,9,13,.82)", size = 10.5) {
    ctx.font = `600 ${size}px ${MONO}`;
    const w = ctx.measureText(text).width + 12;
    ctx.fillStyle = bg; ctx.beginPath(); ctx.roundRect(x - w / 2, y - 9, w, 18, 4); ctx.fill();
    ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(text, x, y + 0.5);
  }
  function label(text, x, y, color, size = 10, weight = 500) {
    ctx.font = `${weight} ${size}px ${MONO}`; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    ctx.fillStyle = color; ctx.fillText(text.length > 34 ? text.slice(0, 33) + "…" : text, x, y);
  }

  function drawGuides(S) {
    const fade = view === "orbit" ? ease(morph) : 1 - ease(morph);
    ctx.lineWidth = 1;
    if (view === "orbit") {
      ctx.globalAlpha = ease(morph);
      const ring = (r, color, dash) => {
        ctx.beginPath();
        for (let i = 0; i <= 72; i++) { const a = (i / 72) * TAU, [x, y] = project([r * Math.cos(a), 0, r * Math.sin(a)], S); ctx[i ? "lineTo" : "moveTo"](x, y); }
        ctx.setLineDash(dash || []); ctx.strokeStyle = color; ctx.stroke(); ctx.setLineDash([]);
      };
      for (const p of planets) ring(p.orb, rgba(p.color, focusDept && focusDept !== p.dept ? 0.03 : 0.11));
      ring(0.92, "rgba(255,255,255,.13)");
      ring(0.16, "rgba(255,138,61,.16)", [2, 4]);
      // the sphere's rim, for the 3D read
      ctx.beginPath(); ctx.arc(W / 2, midY(), 0.98 * S * Math.min(1, 1.1 * Math.sin(elev) + 0.45), 0, TAU);
      ctx.strokeStyle = "rgba(255,255,255,.04)"; ctx.stroke();
      ctx.globalAlpha = 1;
    } else {
      ctx.globalAlpha = ease(morph);
      const rings = [[0.18, "SKILLS", "#ff9a52"], [0.73, "MEMORY", "#b38cff"], [0.83, "ROUTINES", "#ff9a52"], [0.94, "APPLICATIONS", "#8fb3ff"]];
      for (const [r, , c] of rings) { ctx.beginPath(); ctx.arc(W / 2, midY(), r * S, 0, TAU); ctx.strokeStyle = rgba(c, 0.16); ctx.stroke(); }
      // each department's arc on the routines ring
      const sector = (TAU / Math.max(planets.length, 1)) * 0.8, rot = yaw + time * 0.006;
      for (const p of planets) {
        ctx.beginPath(); ctx.arc(W / 2, midY(), 0.8 * S, p.angle + rot - sector / 2, p.angle + rot + sector / 2);
        ctx.strokeStyle = rgba(p.color, focusDept && focusDept !== p.dept ? 0.06 : 0.45); ctx.lineWidth = 1.5; ctx.stroke(); ctx.lineWidth = 1;
      }
      for (const [r, t, c] of rings) pill(t, W / 2, midY() - r * S, c, "rgba(8,9,13,.9)", 10);
      ctx.globalAlpha = 1;
    }
    return fade;
  }

  function drawNode(n) {
    const focus = inFocus(n), hot = hover && (hover === n || hover.links?.has(n));
    const depthA = view === "orbit" ? Math.max(0.35, Math.min(1, 0.72 + n.d * 0.55)) : 1;
    const a = (focus ? 1 : 0.1) * depthA * (hover && !hot && hover.kind !== "area" ? 0.55 : 1);
    const s = view === "orbit" ? n.s : 1, x = n.x, y = n.y, c = n.color;
    ctx.globalAlpha = a;
    switch (n.kind) {
      case "core": {
        const pulse = 1 + Math.sin(time * (activity ? 6 : 1.6)) * 0.08;
        const g = ctx.createRadialGradient(x, y, 0, x, y, 70 * pulse);
        g.addColorStop(0, "rgba(255,138,61,.45)"); g.addColorStop(1, "rgba(255,138,61,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 70 * pulse, 0, TAU); ctx.fill();
        hexPath(x, y, 19); ctx.fillStyle = "#0b0c10"; ctx.fill(); ctx.lineWidth = 2.2; ctx.strokeStyle = "#ff8a3d"; ctx.stroke();
        hexPath(x, y, 11 * pulse); ctx.fillStyle = "rgba(255,138,61,.25)"; ctx.fill(); ctx.lineWidth = 1;
        pill(String(n.label || "BRAIN").toUpperCase().slice(0, 22), x, y + 36, "#f3f4f7", "rgba(8,9,13,.9)", 11);
        break;
      }
      case "area": {
        const r = 10 * s, g = ctx.createRadialGradient(x, y, 0, x, y, r * 4.5);
        g.addColorStop(0, rgba(c, 0.38)); g.addColorStop(1, rgba(c, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 4.5, 0, TAU); ctx.fill();
        const body = ctx.createRadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r);
        body.addColorStop(0, "#fff"); body.addColorStop(0.25, c); body.addColorStop(1, rgba(c, 0.55));
        ctx.fillStyle = body; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
        ctx.font = `700 ${9.5 * s}px ${MONO}`; ctx.fillStyle = "#0b0c10"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(n.label[0].toUpperCase(), x, y + 0.5);
        label(n.label.toUpperCase(), x + r + 7, y - 4, "rgba(240,241,245,.92)", 11, 600);
        label(String(n.count), x + r + 7, y + 9, rgba(c, 0.9), 10);
        break;
      }
      case "app": {
        const r = 11 * s;
        hexPath(x, y, r); ctx.fillStyle = "rgba(10,11,16,.92)"; ctx.fill();
        ctx.strokeStyle = rgba(c, 0.9); ctx.lineWidth = 1.4; ctx.stroke(); ctx.lineWidth = 1;
        ctx.font = `700 ${9 * s}px ${MONO}`; ctx.fillStyle = c; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(n.label[0].toUpperCase(), x, y + 0.5);
        if (names || hot) label(n.label, x + r + 5, y, "rgba(220,222,230,.85)", 10);
        break;
      }
      case "skill": {
        const r = 4.2 * s; ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath();
        ctx.fillStyle = c; ctx.fill();
        break;
      }
      case "routine": {
        ctx.beginPath(); ctx.arc(x, y, 4 * s, 0, TAU); ctx.strokeStyle = c; ctx.lineWidth = 1.2; ctx.stroke(); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(x, y, 1.4 * s, 0, TAU); ctx.fillStyle = c; ctx.fill();
        break;
      }
      case "decision": {
        const r = 3.4 * s; ctx.save(); ctx.translate(x, y); ctx.rotate(Math.PI / 4); ctx.fillStyle = n.due ? "#ff6b6b" : c; ctx.fillRect(-r / 2, -r / 2, r, r); ctx.restore();
        break;
      }
      case "metric": {
        const r = 4 * s, bad = /bad|watch/i.test(n.verdict || "");
        ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r * 0.9, y + r * 0.6); ctx.lineTo(x - r * 0.9, y + r * 0.6); ctx.closePath();
        ctx.fillStyle = c; ctx.fill();
        if (bad) { ctx.beginPath(); ctx.arc(x, y, r + 3, 0, TAU); ctx.strokeStyle = /bad/i.test(n.verdict) ? "rgba(255,107,107,.7)" : "rgba(255,194,75,.6)"; ctx.stroke(); }
        break;
      }
      case "run": {
        ctx.beginPath(); ctx.arc(x, y, 1.9 * s, 0, TAU); ctx.fillStyle = c; ctx.fill();
        if (n.recent && motion) { const p = (time * 0.7 + n.r[0]) % 1; ctx.globalAlpha = a * (1 - p); ctx.beginPath(); ctx.arc(x, y, 2 + p * 9, 0, TAU); ctx.strokeStyle = c; ctx.stroke(); }
        break;
      }
      default: {
        const r = (n.sub === "state" ? 3.6 : n.sub === "note" ? 3.1 : 2.6) * s;
        ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fillStyle = c; ctx.fill();
        if (n.sub === "state") { ctx.beginPath(); ctx.arc(x, y, r + 2.5, 0, TAU); ctx.strokeStyle = rgba(c, 0.5); ctx.stroke(); }
      }
    }
    if (names && focus && ["file", "skill", "metric"].includes(n.kind) && depthA > 0.6) label(n.label, x + 7, y, "rgba(200,203,214,.6)", 9);
    ctx.globalAlpha = 1;
  }

  function drawPulses(dt) {
    if (motion && time > nextPulse && links.length) {
      const pick = activity && planets.length ? [byId.core, planets[Math.floor(Math.random() * planets.length)]] : links[Math.floor(Math.random() * links.length)];
      if (pick[0] && pick[1]) pulses.push({ a: pick[0], b: pick[1], t: 0, dur: activity ? 0.7 : 1.3 });
      nextPulse = time + (activity ? 0.12 : 0.55 + Math.random() * 0.8);
    }
    pulses = pulses.filter((p) => (p.t += dt / p.dur) < 1);
    for (const p of pulses) {
      const k = ease(p.t), x = p.a.x + (p.b.x - p.a.x) * k, y = p.a.y + (p.b.y - p.a.y) * k;
      const col = p.b.kind === "area" ? p.b.color : "#ffb27a";
      const tx = p.a.x + (p.b.x - p.a.x) * Math.max(0, k - 0.12), ty = p.a.y + (p.b.y - p.a.y) * Math.max(0, k - 0.12);
      const g = ctx.createLinearGradient(tx, ty, x, y); g.addColorStop(0, rgba(col, 0)); g.addColorStop(1, rgba(col, 0.85));
      ctx.strokeStyle = g; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
      ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(x, y, 1.6, 0, TAU); ctx.fill(); ctx.lineWidth = 1;
    }
  }

  function draw(dt) {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const S = layout();
    // nebulae behind each department
    for (const p of planets) {
      const r = (view === "orbit" ? 150 : 190) * zoom, g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
      g.addColorStop(0, rgba(p.color, focusDept && focusDept !== p.dept ? 0.015 : 0.09)); g.addColorStop(1, rgba(p.color, 0));
      ctx.fillStyle = g; ctx.fillRect(p.x - r, p.y - r, r * 2, r * 2);
    }
    drawGuides(S);
    const core = byId.core;
    ctx.lineWidth = 1;
    if (core) for (const p of planets) {
      ctx.strokeStyle = rgba(p.color, focusDept && focusDept !== p.dept ? 0.03 : 0.14);
      ctx.beginPath(); ctx.moveTo(core.x, core.y); ctx.lineTo(p.x, p.y); ctx.stroke();
    }
    for (const [a, b] of links) {
      const hot = hover && (a === hover || b === hover);
      if (!hot && !(inFocus(a) && inFocus(b))) continue;
      ctx.strokeStyle = hot ? rgba(hover.color, 0.75) : "rgba(200,205,225,.075)";
      ctx.lineWidth = hot ? 1.3 : 1;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    ctx.lineWidth = 1;
    drawPulses(dt);
    const sorted = view === "orbit" ? [...nodes].sort((a, b) => a.d - b.d) : nodes;
    for (const n of sorted) if (n.kind !== "core") drawNode(n);
    if (core) drawNode(core);
    if (hover) { ctx.beginPath(); ctx.arc(hover.x, hover.y, hover.kind === "area" ? 16 : hover.kind === "app" ? 16 : 8, 0, TAU); ctx.strokeStyle = rgba(hover.color, 0.9); ctx.stroke(); }
  }

  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    if (!visible || document.hidden || !W || !nodes.length) return;
    if (motion) time += dt * (drag ? 0.25 : 1);
    if (morph < 1) { morph = Math.min(1, morph + dt / 1.1); dirty = true; }
    if (!motion && !dirty && !pulses.length) return;
    draw(dt); dirty = false;
  }

  // ---------------------------------------------------------------- chrome + input
  function renderChrome() {
    el.querySelector("[data-o=stats]").textContent = counts.files ? `${counts.files} files · ${counts.links} links · ${counts.runs} runs` : "";
    el.querySelectorAll("[data-o-view]").forEach((b) => b.classList.toggle("on", b.dataset.oView === view));
    el.querySelector("[data-o=names]").classList.toggle("on", names);
    el.querySelector("[data-o=motion]").classList.toggle("on", motion);
    el.querySelector(".o-depts").innerHTML = `<button class="o-chip ${focusDept ? "" : "on"}" data-o-dept="">all areas</button>` +
      planets.map((p) => `<button class="o-chip ${focusDept === p.dept ? "on" : ""}" data-o-dept="${esc(p.dept)}" style="--c:${p.color}"><i></i>${esc(p.label.toLowerCase())} <span>${p.count}</span></button>`).join("");
    el.querySelector(".o-kinds").innerHTML = KINDS.filter(([k]) => nodes.some((n) => n.kind === k))
      .map(([k, g, t]) => `<button class="o-chip k ${focusKind === k ? "on" : ""}" data-o-kind="${k}"><b>${g}</b> ${t}</button>`).join("");
  }
  function setView(v) {
    if (v === view) return;
    for (const n of nodes) { n.fx = n.x; n.fy = n.y; }
    view = v; morph = 0; keep("view", v); dirty = true; renderChrome();
  }
  function resize() {
    const r = cv.getBoundingClientRect();
    DPR = Math.min(window.devicePixelRatio || 1, 2); W = r.width; H = r.height;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); dirty = true;
  }
  function pick(mx, my) {
    let best = null, bd = Infinity;
    for (const n of nodes) {
      if (!inFocus(n)) continue;
      const r = n.kind === "core" ? 22 : n.kind === "area" ? 16 : n.kind === "app" ? 14 : 8;
      const d = Math.hypot(n.x - mx, n.y - my);
      if (d < r && d - (n.d || 0) * 4 < bd) { bd = d - (n.d || 0) * 4; best = n; }
    }
    return best;
  }
  function target(n) {
    if (!n) return null;
    if (n.kind === "area") return () => showTab(n.dept === "system" ? "automations" : n.dept);
    if (n.kind === "app" || n.kind === "routine") return () => showTab("automations");
    if (n.kind === "metric") return () => openMetric(n.key);
    if (n.kind === "decision") return () => openDecision(n.did);
    if (n.kind === "run") return () => showTab("activity");
    if (n.kind === "file" && n.doc) return () => openDoc(n.doc);
    return null;
  }
  function showTip(n, mx, my) {
    if (!n) { tip.hidden = true; return; }
    const meta = [n.kind === "area" ? `${n.count} nodes` : n.sub, n.date].filter(Boolean).join(" · ");
    tip.innerHTML = `<div class="k" style="color:${n.color}">${esc(KIND_NAME[n.kind] || n.kind)}${n.planet && n.kind !== "area" && n.kind !== "core" ? ` · ${esc(n.planet.label.toLowerCase())}` : ""}</div>
      <div class="t">${esc(n.label)}</div>${meta ? `<div class="m">${esc(meta)}</div>` : ""}${n.path ? `<div class="p">${esc(n.path)}</div>` : ""}
      ${target(n) ? `<div class="m go">click to open →</div>` : ""}`;
    tip.hidden = false;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    tip.style.left = `${Math.min(mx + 16, W - tw - 8)}px`; tip.style.top = `${Math.max(8, Math.min(my + 16, H - th - 8))}px`;
  }
  function bind() {
    const local = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.addEventListener("pointermove", (e) => {
      const [mx, my] = local(e);
      if (drag) {
        yaw = drag.yaw + (mx - drag.x) * 0.006;
        if (view === "orbit") elev = Math.max(0.12, Math.min(1.45, drag.elev + (my - drag.y) * 0.004));
        drag.moved = drag.moved || Math.hypot(mx - drag.x, my - drag.y) > 4;
        dirty = true; tip.hidden = true; return;
      }
      const n = pick(mx, my);
      if (n !== hover) {
        hover = n; dirty = true;
        if (n) n.links = new Set(links.filter(([a, b]) => a === n || b === n).map(([a, b]) => (a === n ? b : a)));
      }
      cv.style.cursor = target(n) ? "pointer" : "grab";
      showTip(n, mx, my);
    });
    cv.addEventListener("pointerleave", () => { hover = null; tip.hidden = true; dirty = true; });
    cv.addEventListener("pointerdown", (e) => { const [x, y] = local(e); drag = { x, y, yaw, elev, moved: false }; cv.setPointerCapture(e.pointerId); cv.style.cursor = "grabbing"; });
    cv.addEventListener("pointerup", (e) => {
      const d = drag; drag = null; cv.style.cursor = "grab";
      if (d && !d.moved) { const go = target(pick(...local(e))); if (go) go(); }
    });
    cv.addEventListener("dblclick", () => { yaw = 0; elev = 0.42; zoom = 1; dirty = true; });
    cv.addEventListener("wheel", (e) => {
      if (!document.fullscreenElement && !e.ctrlKey && !e.metaKey) return;  // let the page scroll
      e.preventDefault(); zoom = Math.max(0.5, Math.min(2.6, zoom * Math.exp(-e.deltaY * 0.0015))); dirty = true;
    }, { passive: false });
    el.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b || !el.contains(b)) return;
      if (b.dataset.oView) return setView(b.dataset.oView);
      if (b.dataset.oDept !== undefined) { focusDept = b.dataset.oDept && focusDept !== b.dataset.oDept ? b.dataset.oDept : null; dirty = true; return renderChrome(); }
      if (b.dataset.oKind) { focusKind = focusKind === b.dataset.oKind ? null : b.dataset.oKind; dirty = true; return renderChrome(); }
      const o = b.dataset.o;
      if (o === "names") { names = !names; keep("names", names); }
      if (o === "motion") { motion = !motion; keep("motion", motion); }
      if (o === "fit") { yaw = 0; elev = 0.42; zoom = 1; }
      if (o === "full") document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen?.();
      dirty = true; renderChrome();
    });
    new ResizeObserver(resize).observe(cv);
    document.addEventListener("fullscreenchange", () => { el.classList.toggle("full", document.fullscreenElement === el); setTimeout(resize, 50); });
    new IntersectionObserver(([en]) => { visible = en.isIntersecting; dirty = true; }).observe(cv);
  }

  function mount(root) {
    el = root; cv = el.querySelector("canvas"); ctx = cv.getContext("2d"); tip = el.querySelector(".o-tip");
    bind(); resize(); load(); requestAnimationFrame(frame);
  }
  // Called on every state reload: a running job speeds the sun up; the graph re-reads at most every 25s.
  function update(state) {
    activity = !!state?.jobs?.recent?.some((j) => j.status === "running");
    if (Date.now() - loaded > 25000) load();
  }
  return { mount, update };
})();
