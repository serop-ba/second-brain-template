// Brain OS console. TOKEN is set by an inline script in index.html. Everything the page
// changes goes through rpc() into the same functions the CLI uses, so every edit lands
// in the change history.
let S = null, activeJob = null, jobCursor = 0, polling = null, ROUTE = "dashboard";
const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
const rpc = (fn, args = {}) => api("/api/rpc", { fn, args });
function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 2800); }
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function md(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s).,;:]|$)/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) => /^https?:/.test(u) ? `<a href="${u}" target="_blank" rel="noopener">${t}</a>` : t);
}
const plain = (s) => String(s ?? "").replace(/\*\*/g, "");
function mdBlock(text) {
  const out = [];
  let para = [], list = null, table = [];
  const flushP = () => { if (para.length) { out.push(`<p>${md(para.join("\n")).replace(/\n/g, "<br>")}</p>`); para = []; } };
  const flushL = () => { if (list) { out.push(`<${list.tag}>${list.items.map((t) => `<li>${md(t)}</li>`).join("")}</${list.tag}>`); list = null; } };
  const flushT = () => {
    if (!table.length) return;
    const rows = table.map((l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim())).filter((r) => !r.every((c) => /^:?-+:?$/.test(c)));
    const [head, ...body] = rows;
    out.push(`<div class="vscroll"><table class="mdt"><tr>${head.map((c) => `<th>${md(c)}</th>`).join("")}</tr>${body.map((r) => `<tr>${r.map((c) => `<td>${md(c)}</td>`).join("")}</tr>`).join("")}</table></div>`);
    table = [];
  };
  for (const raw of String(text || "").split("\n")) {
    const line = raw.replace(/\s+$/, "");
    if (/^\s*\|/.test(line)) { flushP(); flushL(); table.push(line); continue; }
    flushT();
    const m = line.match(/^\s*([-*]|\d+\.) (.*)$/);
    if (m) { flushP(); const tag = /\d/.test(m[1]) ? "ol" : "ul"; if (list && list.tag !== tag) flushL(); if (!list) list = { tag, items: [] }; list.items.push(m[2]); continue; }
    if (!line.trim()) { flushP(); flushL(); continue; }
    flushL();
    if (/^#{1,4} /.test(line)) { flushP(); out.push(`<h4>${md(line.replace(/^#+ /, ""))}</h4>`); }
    else if (/^\*\*[^*]+\*\*:?$/.test(line.trim())) { flushP(); out.push(`<h4>${md(line.trim().replace(/:$/, ""))}</h4>`); }
    else para.push(line.trim());
  }
  flushP(); flushL(); flushT();
  return out.join("");
}
const daysSince = (iso) => iso ? Math.round((new Date(S.today) - new Date(iso)) / 864e5) : null;
const ago = (iso) => { const d = daysSince(iso); return d === null ? "never" : d === 0 ? "today" : d === 1 ? "yesterday" : `${d}d ago`; };
const isRunning = (key) => S.jobs.recent.some((j) => j.key === key && j.status === "running");
const when = (ts) => String(ts || "").replace("T", " ").slice(0, 16);

// ------------------------------------------------------------------ routing
const TABS = ["dashboard", "company", "library", "activity", "automations"];
const TITLES = { dashboard: "Overview", company: "Company", library: "Library", activity: "Activity", automations: "Automations" };
const areaOf = (slug) => (S?.departments || []).find((d) => d.slug === slug);
function showTab(name) {
  if (!TABS.includes(name) && S && !areaOf(name)) name = "dashboard";
  ROUTE = name;
  const isArea = !TABS.includes(name);
  document.querySelectorAll(".nav-i[data-tab]").forEach((t) => t.classList.toggle("on", t.dataset.tab === name));
  document.querySelectorAll("main[id^=tab-]").forEach((m) => (m.hidden = m.id !== "tab-" + (isArea ? "area" : name)));
  if (location.hash.slice(1) !== name) history.replaceState(null, "", "#" + name);
  $("page-title").textContent = isArea ? (areaOf(name)?.name || "") : TITLES[name];
  if (isArea && S) renderArea();
  window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ render
function render() {
  $("company").textContent = S.company;
  const d = new Date(S.today + "T12:00");
  $("when").textContent = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) + " · " + S.tasks.week.slice(5);
  const lw = daysSince(S.log.last_weekly), due = S.decisions.filter((x) => x.due).length;
  $("chips").innerHTML = [
    [lw === null ? "bad" : lw > 7 ? "watch" : "good", `Weekly loop ${ago(S.log.last_weekly)}`],
    due ? ["bad", `${due} review${due > 1 ? "s" : ""} due`] : null,
    S.inbox.length ? [S.inbox.length > 10 ? "watch" : "", `Inbox ${S.inbox.length}`] : null,
  ].filter(Boolean).map(([c, t]) => `<span class="chip ${c}">${esc(t)}</span>`).join("");
  $("nav-inbox").textContent = S.inbox.length || "";
  renderBanners(); renderSidebar(); renderStar(); renderDepts(); renderWeek(); renderBets(); renderNumbers(); renderDecisions();
  renderCompany(); renderLibrary(); renderActivity(); renderAutomations();
  if (!TABS.includes(ROUTE)) { areaOf(ROUTE) ? (renderArea(), $("page-title").textContent = areaOf(ROUTE).name) : showTab("dashboard"); }
  const opts = `<option value="">No bet</option>` + S.bets.map((b) => `<option value="${b.n}">Bet ${b.n}</option>`).join("");
  document.querySelectorAll("form.add[data-kind] select").forEach((s) => { const v = s.value; s.innerHTML = opts; if (s.dataset.touched) s.value = v; });
  Orbit.update(S);
}

function renderBanners() {
  const empty = !Object.keys(S.profile).length && !S.departments.length;
  let h = "";
  if (S.demo) h += `<div class="banner watch demo"><b>You're looking at demo data.</b> It's all fictional and removing it takes one click.
    <span class="sp"></span><button class="b" data-term="init">Set up my business with Claude ↗</button><button class="b" data-act="demo-clear">Clear the demo</button></div>`;
  if (empty) h += `<div class="banner good demo"><b>This brain is empty.</b> Open Claude Code in this folder and run <code>/init</code>: a ten-minute interview, then Claude files your business here.
    <span class="sp"></span><button class="b" data-term="init">Run /init ↗</button><button class="b" data-act="demo-load">Load demo data instead</button></div>`;
  const todo = S.attention.filter((t) => !/^\d+ item\(s\) in the inbox/.test(t));
  if (todo.length && !S.demo && !empty) h += `<div class="banner watch"><b>Needs attention:</b> ${todo.slice(0, 4).map(esc).join(" · ")}</div>`;
  $("top-banners").innerHTML = h;
}

function renderStar() {
  const g = S.goals;
  $("star").innerHTML = g.north_star ? md(g.north_star.text) : `<span class="faint">No north star yet. One sentence that tells you what you're building toward.</span>`;
  $("year").innerHTML = g.year.length ? `<span>${esc(g.year_label)}:</span>` + g.year.map((y) => `<span><b>${esc(plain(y.text).replace(/\.$/, ""))}</b></span>`).join("") : "";
}

function checkItem(item) {
  const tag = item.bet ? ` <span class="tag">Bet ${item.bet}</span>` : ' <span class="tag none" title="Serves no bet: is it busywork?">no bet</span>';
  const stamps = [];
  if (item.carried) stamps.push(`<span class="small stamp" style="color:var(--${item.carried > 1 ? "bad" : "watch"})">carried ${item.carried}w</span>`);
  if (item.from_day) stamps.push(`<span class="small stamp" style="color:var(--watch)">from ${esc(item.from_day.slice(5))}</span>`);
  if (item.done && item.kind === "priority") stamps.push(`<span class="faint small stamp">${esc(item.done_at.slice(5, 10))}</span>`);
  return `<li class="hov ${item.done ? "done" : ""}"><input type="checkbox" ${item.done ? "checked" : ""} data-op="toggle" data-id="${item.id}">
    <span class="t">${md(item.text)}${tag} ${stamps.join(" ")}</span>
    <button class="ic" title="Edit" data-taskedit="${item.id}">✎</button><button class="x" title="Delete" data-op="remove" data-id="${item.id}">×</button></li>`;
}
function renderWeek() {
  const T = S.tasks, today = T.today_items, goals = T.goals, done = T.done;
  $("today-date").textContent = T.today.slice(5);
  $("today-banner").innerHTML = today.length > 3 ? `<div class="banner watch">${today.length} priorities is a to-do list. Three is the most that all get done.</div>` : "";
  $("today").innerHTML = today.length ? today.map(checkItem).join("") : `<li class="empty">Pick up to three that move a bet.</li>`;
  $("done").innerHTML = done.length ? done.slice().reverse().map(checkItem).join("") : `<li class="empty small">Nothing yet.</li>`;
  $("history").innerHTML = T.history.length ? `<details style="margin-top:10px"><summary>Past weeks</summary><table class="hist"><tr><th>Week</th><th>Goals</th><th>Priorities</th></tr>${T.history.map((h) =>
    `<tr><td>${esc(h.week.slice(5))}</td><td>${h.goals_done}/${h.goals}</td><td>${h.priorities_done}/${h.priorities}</td></tr>`).join("")}</table></details>` : "";
  const f = { month: "short", day: "numeric" };
  $("week-label").textContent = `${new Date(T.start + "T12:00").toLocaleDateString(undefined, f)} – ${new Date(T.end + "T12:00").toLocaleDateString(undefined, f)}`;
  const stuck = goals.filter((x) => !x.done && x.carried > 1).length;
  $("week-banner").innerHTML = stuck ? `<div class="banner bad">${stuck} goal${stuck > 1 ? "s" : ""} carried 2+ weeks. Cut or commit.</div>` : "";
  const n = goals.length, k = goals.filter((x) => x.done).length, onBet = goals.filter((x) => x.bet).length;
  $("week-progress").textContent = n ? `${k} of ${n} done · ${Math.round((onBet / n) * 100)}% on a bet` : "";
  $("week-bar").parentElement.hidden = !n;
  $("week-bar").style.width = n ? `${(k / n) * 100}%` : "0";
  $("goals").innerHTML = n ? goals.map(checkItem).join("") : `<li class="empty">Set 3–5 outcomes for the week.</li>`;
}

const STATUSES = ["not started", "on track", "at risk", "stalled", "done", "dropped"];
function statusChip(s) {
  const t = (s || "").toLowerCase();
  const c = /on.?track|done|won/.test(t) ? "good" : /not started/.test(t) ? "watch" : /at.?risk|stalled|blocked/.test(t) ? "bad" : "";
  return `<span class="chip ${c}">${esc(s || "no status")}</span>`;
}
function renderBets() {
  const T = S.tasks, touches = (n) => [...T.goals, ...T.today_items, ...T.done].filter((x) => x.bet === n).length;
  $("bets").innerHTML = S.bets.length ? S.bets.map((b) => {
    const t = touches(b.n);
    return `<div class="bet hov">
      <div class="title"><span class="tag">Bet ${b.n}</span> ${md(b.title)} <button class="ic" data-act="bet-edit" data-key="${b.n}" title="Edit or delete this bet">✎</button></div>
      <div class="meta">${statusChip(b.status)}<span style="${t ? "" : "color:var(--watch)"}">${t ? `${t} item${t > 1 ? "s" : ""} this week` : "nothing scheduled this week"}</span></div>
      ${b.success ? `<div class="success"><span class="lbl">Wins if</span>${md(b.success)}</div>` : ""}
      <details><summary>Details</summary>
        ${b.status_note ? `<div class="muted">${md(b.status_note)}</div>` : ""}
        ${b.next.length ? `<div><span class="lbl">Next steps</span><ol>${b.next.map((x) => `<li>${md(x)}</li>`).join("")}</ol></div>` : ""}
        ${b.why ? `<div><span class="lbl">Why</span>${md(b.why)}</div>` : ""}</details></div>`;
  }).join("") : `<div class="empty">No bets yet. A bet is something you're wagering this quarter, with a number that says it worked.</div>`;
}

// ------------------------------------------------------------------ numbers
const verdictClass = (v) => ({ healthy: "good", watch: "watch", bad: "bad" }[v] || "");
const fmtN = (v) => v == null ? "—" : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : (+(+v).toFixed(2)).toLocaleString();
function renderNumbers() {
  $("num-updated").textContent = S.refresh.last ? `refreshed ${ago(S.refresh.last.at.slice(0, 10))}${S.refresh.last.ok ? "" : " · " + S.refresh.last.failed.length + " failed"}` : "";
  const missing = S.metrics.filter((m) => m.now == null);
  $("num-banner").innerHTML = missing.length ? `<div class="banner watch">No data: ${missing.map((m) => esc(m.name)).join(", ")}. Log a value or connect an automation.</div>` : "";
  $("numbers").innerHTML = S.metrics.map(metricCard).join("") || `<div class="empty">No metrics yet. Add the 3–5 numbers that tell you if this is working.</div>`;
}
function metricCard(m) {
  const pts = m.points || [];
  return `<button class="metric" data-metric="${esc(m.key)}" title="See how ${esc(m.name)} has moved"><div class="n">${esc(m.name)}</div>
    <div class="v ${m.now == null ? "nodata" : ""}">${m.now == null ? "—" : fmtN(m.now)}<small class="unit"> ${esc(m.unit)}</small></div>
    ${spark(pts)}<div class="deltas">${deltas(pts)}</div>
    <div class="foot"><span>${m.healthy ? "target " + esc(m.healthy.replace(">=", "≥").replace("<=", "≤")) : ""}</span><span class="chip ${verdictClass(m.verdict)}">${esc(m.verdict)}</span></div></button>`;
}
const dayLabel = (iso) => new Date(iso + "T12:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
function shiftDay(iso, days) { const d = new Date(iso + "T12:00"); d.setDate(d.getDate() - days); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
function atOrBefore(pts, iso) { let hit = null; for (const p of pts) { if (p.as_of <= iso) hit = p; else break; } return hit; }
function isoWeek(iso) {
  const d = new Date(iso + "T12:00"), t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  const y = t.getUTCFullYear(), w = Math.ceil(((t - Date.UTC(y, 0, 1)) / 864e5 + 1) / 7);
  return `${y}-W${String(w).padStart(2, "0")}`;
}
function bucket(pts, period) {
  const m = new Map();
  for (const p of pts) m.set(period === "day" ? p.as_of : period === "week" ? isoWeek(p.as_of) : p.as_of.slice(0, 7), p);
  return [...m.entries()].map(([key, p]) => ({ ...p, key }));
}
function periodLabel(key, period) {
  if (period === "day") return dayLabel(key);
  if (period === "week") return key.slice(5);
  return new Date(key + "-15T12:00").toLocaleDateString(undefined, { month: "short", year: "numeric" });
}
function change(now, prev) {
  if (prev == null) return "";
  const d = now - prev, pct = prev ? ` (${d > 0 ? "+" : ""}${((d / Math.abs(prev)) * 100).toFixed(1)}%)` : "";
  return d === 0 ? "flat" : `${d > 0 ? "▲ +" : "▼ "}${fmtN(d)}${pct}`;
}
function spark(pts) {
  if (pts.length < 2) return `<div class="spark"></div>`;
  const v = pts.slice(-30).map((p) => p.value), mn = Math.min(...v), r = Math.max(...v) - mn || 1;
  const d = v.map((y, i) => `${((i / (v.length - 1)) * 100).toFixed(1)},${(24 - ((y - mn) / r) * 21).toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true"><polyline points="${d}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}
function deltas(pts) {
  if (pts.length < 2) return pts.length ? `<span class="faint">1 day on record</span>` : "";
  const last = pts[pts.length - 1];
  const refs = [atOrBefore(pts, shiftDay(last.as_of, 7)), atOrBefore(pts, shiftDay(last.as_of, 30))];
  if (!refs[0]) refs[0] = pts[0];
  const seen = new Set();
  return refs.filter((r) => r && r.as_of !== last.as_of && !seen.has(r.as_of) && seen.add(r.as_of))
    .map((r) => `${change(last.value, r.value).replace(/ \(.*\)/, "")} since ${dayLabel(r.as_of)}`).join("<br>");
}

let MP = { key: null, period: "day" };
function openMetric(key, period) {
  const m = S.metrics.find((x) => x.key === key || x.name === key);
  if (!m) return;
  MP.key = m.key; MP.period = period || MP.period;
  const rows = bucket(m.points || [], MP.period);
  const seg = ["day", "week", "month"].map((p) => `<button data-period="${p}" class="${p === MP.period ? "on" : ""}">${{ day: "Daily", week: "Weekly", month: "Monthly" }[p]}</button>`).join("");
  const table = rows.length ? `<table class="ptable"><tr><th>${{ day: "Day", week: "Week", month: "Month" }[MP.period]}</th><th class="r">Value</th><th class="r">Change</th><th>From</th><th></th></tr>${
    rows.map((r, i) => ({ r, i })).reverse().slice(0, 60).map(({ r, i }) => `<tr><td>${esc(periodLabel(r.key, MP.period))}</td><td class="r">${fmtN(r.value)}</td>
      <td class="r muted">${i ? change(r.value, rows[i - 1].value) : ""}</td><td class="faint small">${esc(r.origin)}</td>
      <td class="r" style="width:56px">${MP.period === "day" ? `<button class="ic" data-pedit="${r.as_of}" title="Edit">✎</button><button class="ic" data-pdel="${r.as_of}" title="Delete this day">×</button>` : ""}</td></tr>`).join("")}</table>`
    : `<div class="empty small">No values yet. Log one below, or connect an automation.</div>`;
  modal(m.name, `<p class="small muted" style="margin-top:0">${md(m.definition || "No definition yet. Write one so Claude and future you read this number the same way.")}</p>
    <div class="facts" style="margin-bottom:8px"><span><span class="lbl">Now</span>${fmtN(m.now)} ${esc(m.unit)} <span class="chip ${verdictClass(m.verdict)}">${esc(m.verdict)}</span></span>
      <span><span class="lbl">Healthy</span>${esc(m.healthy || "—")}</span><span><span class="lbl">Watch</span>${esc(m.watch || "—")}</span><span><span class="lbl">Bad</span>${esc(m.bad || "—")}</span>
      <span><span class="lbl">Source</span>${esc(m.source)}</span></div>
    <div class="seg">${seg}</div>${chartSVG(rows)}${table}<p class="small faint">One value per day, kept for good. Hand-entered values are in the change history too.</p>`,
    [{ label: "Edit metric", left: true, fn: () => metricForm(m) }, { label: "+ Log a value", left: true, fn: () => pointForm(m.key) }, { label: "Close", fn: closeModal }]);
  bindChart(rows);
}
const CH = { W: 640, H: 220, L: 54, R: 14, T: 12, B: 24 };
function chartScale(rows) {
  const vs = rows.map((r) => r.value);
  let lo = Math.min(...vs), hi = Math.max(...vs);
  if (lo === hi) { lo -= Math.abs(lo) * 0.05 || 1; hi += Math.abs(hi) * 0.05 || 1; }
  const pad = (hi - lo) * 0.1, mn = lo - pad, mx = hi + pad, { W, H, L, R, T, B } = CH;
  return { lo, hi, x: (i) => L + (i * (W - L - R)) / (rows.length - 1), y: (v) => T + ((mx - v) / (mx - mn)) * (H - T - B) };
}
function chartSVG(rows) {
  if (rows.length < 2) return `<div class="empty small" style="margin:14px 0">${rows.length ? "One point so far. The line starts with the second." : ""}</div>`;
  const { W, H, L, R, T, B } = CH, { lo, hi, x, y } = chartScale(rows);
  const grid = [lo, (lo + hi) / 2, hi].map((t) => `<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}" stroke="var(--line)"/><text x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${fmtN(t)}</text>`).join("");
  const xl = [...new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1])].map((i) => `<text x="${x(i)}" y="${H - 6}" text-anchor="${i === 0 ? "start" : i === rows.length - 1 ? "end" : "middle"}">${esc(periodLabel(rows[i].key, MP.period))}</text>`).join("");
  const d = rows.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(r.value).toFixed(1)}`).join(""), n = rows.length - 1;
  return `<div class="chart" id="chart"><svg viewBox="0 0 ${W} ${H}" role="img">${grid}${xl}
    <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${x(n)}" cy="${y(rows[n].value)}" r="4" fill="var(--accent)" stroke="var(--card-solid)" stroke-width="2"/>
    <line id="hx" y1="${T}" y2="${H - B}" stroke="var(--faint)" visibility="hidden"/><circle id="hd" r="4" fill="var(--accent)" visibility="hidden"/></svg><div class="tip" id="tip" hidden></div></div>`;
}
function bindChart(rows) {
  const box = $("chart");
  if (!box) return;
  const svg = box.querySelector("svg"), { W, H, L, R } = CH, { x, y } = chartScale(rows);
  const hx = svg.querySelector("#hx"), hd = svg.querySelector("#hd"), tip = $("tip");
  svg.addEventListener("mousemove", (e) => {
    const rect = svg.getBoundingClientRect(), vx = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.max(0, Math.min(rows.length - 1, Math.round(((vx - L) / (W - L - R)) * (rows.length - 1))));
    hx.setAttribute("x1", x(i)); hx.setAttribute("x2", x(i)); hx.setAttribute("visibility", "visible");
    hd.setAttribute("cx", x(i)); hd.setAttribute("cy", y(rows[i].value)); hd.setAttribute("visibility", "visible");
    tip.hidden = false; tip.textContent = `${periodLabel(rows[i].key, MP.period)} · ${fmtN(rows[i].value)}`;
    tip.style.left = `${(x(i) / W) * rect.width}px`; tip.style.top = `${(y(rows[i].value) / H) * rect.height}px`;
  });
  svg.addEventListener("mouseleave", () => { hx.setAttribute("visibility", "hidden"); hd.setAttribute("visibility", "hidden"); tip.hidden = true; });
}

// ------------------------------------------------------------------ departments
const deptMetrics = (d) => S.metrics.filter((m) => m.department === d.slug);
function deptStatus(d) {
  const v = deptMetrics(d).map((m) => verdictClass(m.verdict));
  return v.includes("bad") ? "bad" : v.includes("watch") ? "watch" : v.includes("good") ? "good" : "";
}
const noHours = (d) => /^(~?0|negligible)\b/i.test((d.hours || "").trim());
const hoursShort = (h) => /\d/.test(h || "") ? `${String(h).replace(/\s*\(.*\)/, "")} h/wk` : (h || "");
function renderSidebar() {
  $("nav-depts").innerHTML = S.departments.map((d) =>
    `<button class="nav-i" data-tab="${esc(d.slug)}"><span class="vd ${deptStatus(d)}"></span>${esc(d.name)}${noHours(d) ? `<span class="nh">0h</span>` : ""}</button>`).join("");
  document.querySelectorAll(".nav-i[data-tab]").forEach((t) => t.classList.toggle("on", t.dataset.tab === ROUTE));
}
function renderDepts() {
  $("depts").innerHTML = S.departments.map((d) => {
    const ms = deptMetrics(d), nd = ms.filter((m) => m.now == null).length;
    const foot = [d.briefed_at ? `briefed ${ago(d.briefed_at)}` : "not briefed", ms.length ? `${ms.length} metric${ms.length > 1 ? "s" : ""}${nd ? `, ${nd} with no data` : ""}` : "no metrics"];
    const headline = (d.brief.match(/\*\*Headline:\*\*\s*(.+)/) || [])[1];
    return `<button class="dept" data-tab="${esc(d.slug)}">
      <div class="dh"><span class="vd ${deptStatus(d)}"></span><b>${esc(d.name)}</b><span class="sp" style="flex:1"></span><span class="small ${noHours(d) ? "warn" : "muted"}">${esc(hoursShort(d.hours))}</span></div>
      <div class="hl">${headline ? md(headline) : `<span class="faint">${md((d.intro || d.owns || "").split(/(?<=\.)\s/)[0])}</span>`}</div>
      <div class="small faint">${d.owner ? `Lead: ${esc(d.owner)} · ` : ""}${esc(foot.join(" · "))}</div></button>`;
  }).join("") || `<div class="empty">No departments yet. A department is a function you run as if it had its own lead: marketing, sales, delivery, finance.</div>`;
}
function renderArea() {
  const d = areaOf(ROUTE);
  if (!d) return;
  const ms = deptMetrics(d), key = "brief:" + d.slug, running = isRunning(key);
  const bets = S.bets.filter((b) => b.department === d.slug);
  const T = S.tasks, open = [...T.goals, ...T.today_items].filter((x) => !x.done && bets.some((b) => b.n === x.bet));
  const notes = S.documents.filter((x) => x.department === d.slug && x.kind !== "section");
  const section = (s) => `<section class="card ${/^\s*\|/m.test(s.body) || s.body.length > 1100 ? "s12" : "s6"} hov"><h2>${esc(s.title)}<span class="sp"></span>
      <button class="ic" data-doc="${esc(s.slug)}" title="Edit this section">✎</button></h2>
      <div class="read">${s.body ? mdBlock(s.body) : `<div class="empty small">Empty. Click ✎ to write it.</div>`}</div></section>`;
  $("tab-area").innerHTML = `
    <section class="card s12"><div class="ahead">
      <div class="ainfo"><p class="lead">${md(d.intro || "No description yet.")}</p>
        <div class="facts"><span><span class="lbl">Lead</span>${esc(d.owner || "—")}</span>
          <span><span class="lbl">Hours / week</span><span class="${noHours(d) ? "warn" : ""}">${esc(d.hours || "—")}</span></span>
          ${d.owns ? `<span style="flex:1;min-width:220px"><span class="lbl">Owns</span>${md(d.owns)}</span>` : ""}</div></div>
      <div class="aact"><button class="b" data-act="dept-edit" data-key="${esc(d.slug)}">Edit department</button></div></div>
      ${noHours(d) ? `<div class="banner watch" style="margin:12px 0 0">No hours go to ${esc(d.name)}. Anything this page says is running is running on its own, or not at all.</div>` : ""}</section>
    <section class="card s7"><h2>Brief <span class="sub">${d.briefed_at ? `briefed ${ago(d.briefed_at)}` : ""}</span><span class="sp"></span>
        <button class="b" data-run="${esc(key)}" ${running ? "disabled" : ""}>${running ? '<span class="spin"></span>Briefing' : `✦ Brief ${esc(d.name)}`}</button></h2>
      <div class="read">${d.brief ? mdBlock(d.brief) : `<div class="empty">No brief yet. Claude reads this page, the bets, the numbers and the last 30 days of the log, then writes what ${esc(d.name)} is doing, what's stuck and on whom, and what's next.</div>`}</div></section>
    <section class="card s5"><h2>Numbers <span class="sp"></span><button class="b ghost" data-act="metric-add" data-key="${esc(d.slug)}">+ Metric</button></h2>
      ${ms.length ? `<div class="metrics">${ms.map(metricCard).join("")}</div>` : `<div class="empty small">No metrics for ${esc(d.name)}. Leave it empty while nothing measurable runs here, or add one.</div>`}
      ${bets.length ? `<h3>Bets it serves</h3>${bets.map((b) => `<div class="dec"><span class="tag">Bet ${b.n}</span> ${md(b.title)} ${statusChip(b.status)}</div>`).join("")}
        <div class="small ${open.length ? "muted" : "warn"}" style="margin-top:6px">${open.length ? `This week: ${open.map((x) => esc(plain(x.text))).join(" · ")}` : "Nothing on this week's list serves it."}</div>` : ""}</section>
    ${d.sections.map(section).join("")}
    <section class="card s12"><h2>Notes in ${esc(d.name)} <span class="sp"></span>
      <button class="b ghost" data-act="section-add" data-key="${esc(d.slug)}">+ Add a section</button><button class="b ghost" data-act="doc-add" data-key="${esc(d.slug)}">+ Add a note</button></h2>
      ${notes.length ? `<ul class="notes-list">${notes.map((n) => `<li><a href="#" data-doc="${esc(n.slug)}" style="flex:1">${esc(n.title)}</a><span class="tag">${esc(n.kind)}</span><span class="faint small">${esc(n.updated_at.slice(0, 10))}</span></li>`).join("")}</ul>` : `<div class="empty small">None. Add a note, or ask Claude to file one here.</div>`}</section>`;
}

// ------------------------------------------------------------------ decisions
function renderDecisions() {
  const ds = S.decisions, due = ds.filter((d) => d.due), open = ds.filter((d) => !d.due && d.pending), closed = ds.filter((d) => !d.pending);
  const item = (d, body) => `<div class="dec hov"><div class="q"><a href="#" data-decision="${d.id}" style="color:inherit;text-decoration:none">${md(d.title)}</a></div>${body}</div>`;
  let h = due.map((d) => item(d, `<div class="small" style="color:var(--bad)">Review was due ${esc(d.review_on)}. Right or wrong?</div><button class="b" style="margin-top:6px" data-outcome="${d.id}">Fill in outcome</button>`)).join("");
  h += open.map((d) => item(d, `<div class="c">${md(d.expect)}</div><div class="small faint">Review ${esc(d.review_on)} · <a href="#" data-outcome="${d.id}">outcome</a></div>`)).join("");
  if (closed.length) h += `<details style="margin-top:8px"><summary>${closed.length} reviewed</summary>${closed.map((d) => item(d, `<div class="c">${md(d.outcome)}</div>`)).join("")}</details>`;
  $("decisions").innerHTML = h || `<div class="empty">No decisions logged. Log the next real call, with what you expect and when you'll check.</div>`;
}
function decisionDetail(d) {
  return `<div class="facts" style="margin-bottom:10px"><span><span class="lbl">Decided</span>${esc(d.date)}</span><span><span class="lbl">Review on</span>${esc(d.review_on)}</span><span><span class="lbl">Department</span>${esc(d.department || "—")}</span></div>
    <h4>Decided</h4><div class="read">${mdBlock(d.decided)}</div>${d.why ? `<h4>Why</h4><div class="read">${mdBlock(d.why)}</div>` : ""}
    <h4>Expect</h4><div class="read">${mdBlock(d.expect)}</div>${d.outcome ? `<h4>Outcome</h4><div class="read">${mdBlock(d.outcome)}</div>` : ""}`;
}
function openDecision(id) {
  const d = S.decisions.find((x) => x.id === id);
  if (!d) return;
  const buttons = [];
  if (d.today) buttons.push({ label: "Edit", left: true, fn: () => decisionForm(d) }, { label: "Delete", cls: "danger", left: true, fn: async () => { if (confirm("Delete this decision? Only possible on the day it was logged.")) { await rpc("decision_remove", { decision_id: id }); await saved("Deleted"); } } });
  buttons.push({ label: "Close", fn: closeModal }, { label: d.outcome ? "Edit outcome" : "Fill in outcome", cls: "primary", fn: () => outcomeForm(id) });
  modal(d.title, decisionDetail(d) + (d.today ? "" : `<p class="small faint">Past decisions are append-only. To change course, log a new decision that supersedes this one.</p>`), buttons);
}

// ------------------------------------------------------------------ company
function renderCompany() {
  const p = S.profile, keys = Object.keys(p), g = S.goals;
  $("profile").innerHTML = keys.length ? `<table class="ptable">${keys.map((k) => `<tr class="hov"><td class="faint small" style="width:34%">${esc(k.replace(/_/g, " "))}</td><td>${md(p[k])}</td>
    <td class="r" style="width:56px"><button class="ic" data-act="fact-edit" data-key="${esc(k)}">✎</button><button class="ic" data-act="fact-del" data-key="${esc(k)}">×</button></td></tr>`).join("")}</table>`
    : `<div class="empty">Nothing yet: name, stage, hours per week, runway, what would make you quit. <code>/init</code> asks for these.</div>`;
  $("direction").innerHTML = `<div class="hov"><span class="lbl">North star</span><div class="read">${g.north_star ? mdBlock(g.north_star.text + (g.north_star.detail ? "\n\n" + g.north_star.detail : "")) : `<span class="faint">Not set.</span>`}</div></div>
    <h3>${esc(g.year_label)}</h3>${g.year.map((y) => `<div class="dec hov"><div class="q">${md(y.text)} <button class="ic" data-act="year-edit" data-key="${y.id}">✎</button></div>${y.detail ? `<div class="c">${md(y.detail)}</div>` : ""}</div>`).join("") || `<div class="empty small">No goals for this year yet.</div>`}`;
  $("calls").innerHTML = S.calls.map((c) => `<div class="dec hov"><div class="q">${md(c.question)}<button class="ic" data-act="call-edit" data-key="${c.id}">✎</button></div>${c.context ? `<div class="c">${md(c.context)}</div>` : ""}
    <button class="b ghost" data-act="call-resolve" data-key="${c.id}">Resolve</button></div>`).join("") || `<div class="empty">None. Write down what you haven't decided yet, so it stops living in your head.</div>`;
}

// ------------------------------------------------------------------ library
let LIB = { kind: "", q: "", hits: null };
const KIND_LABEL = { "": "All", note: "Notes", source: "Sources", playbook: "Playbooks" };
function renderLibrary() {
  $("lib-kind").innerHTML = Object.keys(KIND_LABEL).map((k) => `<button data-libkind="${k}" class="${LIB.kind === k ? "on" : ""}">${KIND_LABEL[k]}</button>`).join("");
  const docs = S.documents.filter((d) => d.kind !== "section" && (!LIB.kind || d.kind === LIB.kind));
  $("lib-results").innerHTML = LIB.hits ? `<h3>Search results</h3>` + (LIB.hits.map((h) => `<div class="dec"><span class="tag">${esc(h.kind)}</span> <a href="#" data-hit="${esc(h.kind)}:${esc(h.id)}">${esc(h.title)}</a><div class="small faint">${esc(h.snippet)}</div></div>`).join("") || `<div class="empty small">No match.</div>`) : "";
  $("lib-list").innerHTML = LIB.hits ? "" : docs.map((d) => `<li><a href="#" data-doc="${esc(d.slug)}" style="flex:1">${esc(d.title)}</a>${d.kind === "source" ? `<span class="tag ${d.ingested ? "" : "none"}">${d.ingested ? "ingested" : "not ingested"}</span>` : ""}
    <span class="tag">${esc(d.kind)}</span>${d.department ? `<span class="faint small">${esc(d.department)}</span>` : ""}<span class="faint small">${esc(d.updated_at.slice(0, 10))}</span></li>`).join("")
    || `<li class="empty">No documents yet. Paste a transcript, a competitor teardown or a playbook, or ask Claude to ingest one.</li>`;
}
async function openDoc(slug) {
  let d;
  try { d = await api(`/api/doc?ref=${encodeURIComponent(slug)}`); } catch (e) { return toast(e.message); }
  const edits = d.history.filter((h) => h.action === "update");
  modal(d.title, `<div class="facts" style="margin-bottom:10px"><span><span class="lbl">Kind</span>${esc(d.kind)}</span><span><span class="lbl">Department</span>${esc(d.department || "—")}</span>
      <span><span class="lbl">Tags</span>${esc(d.tags || "—")}</span><span><span class="lbl">Updated</span>${esc(when(d.updated_at))}</span><span><span class="lbl">Versions</span>${edits.length + 1}</span></div>
    ${d.source_ref ? `<p class="small muted">Source: ${md(d.source_ref)}</p>` : ""}<div class="read">${d.body ? mdBlock(d.body) : `<div class="empty">Empty.</div>`}</div>`,
    [{ label: "History", left: true, fn: () => docHistory(d) }, { label: "Close", fn: closeModal }, { label: "Edit", cls: "primary", fn: () => docForm(d) }]);
}
function docHistory(d) {
  const rows = d.history;
  modal(`History: ${d.title}`, rows.length ? `<table class="ptable"><tr><th>When</th><th>Who</th><th>What</th><th>Why</th><th></th></tr>${rows.map((h) => {
    const was = h.before ? (h.before.body || "").length : 0, now = h.after ? (h.after.body || "").length : 0;
    return `<tr><td class="small">${esc(when(h.ts))}</td><td><span class="chip">${esc(h.actor)}</span></td><td class="small">${esc(h.action)}${h.action === "update" ? ` (${esc(h.summary.replace(/^.*\(/, "").replace(/\)$/, ""))}, ${now - was >= 0 ? "+" : ""}${now - was} chars)` : ""}</td>
      <td class="small faint">${esc(h.reason || "")}</td><td class="r">${h.action === "update" ? `<button class="b ghost" data-revert="${h.id}">Restore the version before this</button>` : ""}</td></tr>`;
  }).join("")}</table>` : `<div class="empty">No history.</div>`, [{ label: "Back", fn: () => openDoc(d.slug) }]);
}
let searchTimer = null;
function librarySearch(q) {
  clearTimeout(searchTimer);
  LIB.q = q;
  if (q.trim().length < 2) { LIB.hits = null; return renderLibrary(); }
  searchTimer = setTimeout(async () => { try { LIB.hits = await api(`/api/search?q=${encodeURIComponent(q.trim())}`); renderLibrary(); } catch (e) { toast(e.message); } }, 220);
}

// ------------------------------------------------------------------ activity
let CH_ACTOR = "";
function renderActivity() {
  $("inbox-count").textContent = S.inbox.length ? `${S.inbox.length} open` : "";
  $("inbox").innerHTML = S.inbox.length ? S.inbox.map((x) => `<li class="hov"><span class="t">${md(x.text)}</span><button class="ic" data-act="inbox-file" data-key="${x.id}" title="Mark filed">✓</button><button class="x" data-act="inbox-del" data-key="${x.id}" title="Delete">×</button></li>`).join("") : `<li class="empty">Empty.</li>`;
  $("log-count").textContent = `${S.log.count} entries · append-only`;
  $("feed").innerHTML = S.log.recent.map((e) => `<li><span class="faint">${esc(e.date)}</span><span class="ty">${esc(e.type)}</span><span>${md(e.title)}${e.body ? `<div class="small faint">${esc(e.body)}</div>` : ""}</span></li>`).join("") || `<li class="empty">Nothing logged.</li>`;
  const actors = ["", ...new Set(S.changes.map((c) => c.actor.split(":")[0]))];
  $("chg-actor").innerHTML = actors.map((a) => `<button data-actor="${esc(a)}" class="${a === CH_ACTOR ? "on" : ""}">${a ? esc(a) : "Everyone"}</button>`).join("");
  const rows = S.changes.filter((c) => !CH_ACTOR || c.actor.split(":")[0] === CH_ACTOR);
  $("changes").innerHTML = rows.length ? `<table class="ptable"><tr><th>When</th><th>Who</th><th>What</th><th>Detail</th><th>Why</th><th></th></tr>${rows.map((c) =>
    `<tr class="hov"><td class="small">${esc(when(c.ts))}</td><td><span class="chip">${esc(c.actor)}</span></td><td class="small">${esc(c.action)} ${esc(c.entity)}</td><td>${esc(c.summary)}</td><td class="faint small">${esc(c.reason || "")}</td>
      <td class="r"><button class="ic" data-revert="${c.id}" title="Undo this change">↶</button></td></tr>`).join("")}</table>` : `<div class="empty">No changes yet.</div>`;
}

// ------------------------------------------------------------------ automations
function jobRow(j, attr) {
  const running = attr === "data-run" && isRunning(j.key);
  return `<div class="jobrow"><div class="info"><div class="name">${esc(j.label)}</div><div class="note">${esc(j.note)}</div></div>
    <button class="b" ${attr}="${esc(j.key)}" ${running ? "disabled" : ""}>${running ? '<span class="spin"></span>Running' : attr === "data-term" ? "Open ↗" : "Run"}</button></div>`;
}
function renderAutomations() {
  const J = S.jobs;
  $("run-claude").innerHTML = J.claude_found ? J.claude.map((j) => jobRow(j, "data-run")).join("") : `<div class="small" style="color:var(--bad)">Claude Code isn't on PATH. Install it, or start the console from a shell that has it.</div>`;
  $("run-scripts").innerHTML = J.scripts.map((j) => jobRow(j, "data-run")).join("");
  $("run-term").innerHTML = J.terminal.map((j) => jobRow(j, "data-term")).join("");
  $("schedule").innerHTML = `<div class="jobrow"><div class="info"><div class="name">Daily refresh ${S.refresh.at ? `at ${esc(S.refresh.at)}` : "is off"}</div>
    <div class="note">${S.refresh.last ? `Last run ${ago(S.refresh.last.at.slice(0, 10))}: ${S.refresh.last.ok ? "all ok" : "failed: " + esc(S.refresh.last.failed.join(", "))}.` : "Never run."} Runs while this console is open; a missed run happens when you next open it.</div></div>
    <input type="time" id="sched-time" value="${esc(S.refresh.at || "07:30")}"><button class="b" data-sched="on">${S.refresh.at ? "Update" : "Turn on"}</button>${S.refresh.at ? `<button class="b" data-sched="off">Off</button>` : ""}</div>`;
  $("auto-cards").innerHTML = J.automations.map(autoCard).join("") || `<section class="card"><div class="empty">Nothing installed yet. Install a use-case pack below, or ask Claude to build one with <code>/connect</code>.</div></section>`;
  $("catalog").innerHTML = S.catalog.map((c) => `<div class="jobrow"><div class="info"><div class="name">${esc(c.label)}</div><div class="note">${esc(c.description)}${c.env.length ? ` Needs <code>${c.env.map(esc).join("</code>, <code>")}</code>.` : ""}</div></div>
    ${c.installed ? `<span class="chip good">installed</span>` : `<button class="b" data-install="${esc(c.name)}">Install</button>`}</div>`).join("")
    + `<h3>Start from a profile</h3>` + S.profiles.map((p) => `<div class="jobrow"><div class="info"><div class="name">${esc(p.label)}</div><div class="note">${esc(p.description)}</div></div><button class="b" data-profile="${esc(p.name)}">Add its departments &amp; metrics</button></div>`).join("");
  $("data").innerHTML = `<div class="jobrow"><div class="info"><div class="name">Back up now</div><div class="note">A copy of the whole database in <code>data/backups/</code>. The console also keeps one a day.</div></div><button class="b" data-act="backup">Back up</button></div>
    <div class="jobrow"><div class="info"><div class="name">${S.demo ? "Demo data is loaded" : "Demo data"}</div><div class="note">${S.demo ? "Fictional. Clearing removes exactly what the demo created and nothing you added." : "Load a fictional business to see the console full."}</div></div>
      <button class="b" data-act="${S.demo ? "demo-clear" : "demo-load"}">${S.demo ? "Clear it" : "Load it"}</button></div>`;
  document.querySelectorAll("main:not(#tab-automations) [data-run]").forEach((b) => (b.disabled = isRunning(b.dataset.run)));
  $("run-history").innerHTML = J.history.length ? J.history.map((r) => `<div class="jobrow"><span class="dot ${r.status === "ok" ? "ok" : r.status === "failed" ? "failed" : ""}"></span><div class="info"><div class="name">${esc(r.label)}</div><div class="note">${esc(when(r.started_at))} · ${esc(r.status)}</div></div></div>`).join("") : `<div class="empty small">No runs yet.</div>`;
  renderPills();
}
function autoCard(c) {
  const rows = c.jobs.map((j) => j.kind === "claude" && !S.jobs.claude_found ? "" : jobRow(j, j.kind === "terminal" ? "data-term" : "data-run")).join("");
  return `<section class="card"><h2>${esc(c.label)} <span class="sub"><code>${esc(c.folder)}/</code></span><span class="sp"></span><button class="b ghost" data-act="auto-remove" data-key="${esc(c.name)}">Remove</button></h2>
    <p class="small muted" style="margin:-4px 0 6px">${md(c.description)}</p>
    ${c.missing_env.length ? `<div class="banner watch">Missing in automations/.env: <code>${c.missing_env.map(esc).join("</code>, <code>")}</code></div>` : ""}
    ${c.metrics.length ? `<p class="small faint" style="margin:0 0 4px">Feeds: ${c.metrics.map(esc).join(", ")}</p>` : ""}${rows}</section>`;
}
function renderPills() {
  const recent = S.jobs.recent;
  $("pills").innerHTML = recent.map((j) => `<span class="pill ${j.id === activeJob ? "on" : ""}" data-job="${j.id}"><span class="dot ${j.status}"></span>${esc(j.label)}</span>`).join("");
  const cur = recent.find((j) => j.id === activeJob);
  $("stop").hidden = !(cur && cur.status === "running");
  $("live").hidden = !recent.some((j) => j.status === "running");
}
const lineClass = (l) => l.startsWith("→") ? "tool" : /^\s*(✗|⛔)|^error|Traceback|failed/i.test(l) ? "err" : /^— done|ok$/.test(l) ? "ok" : l.startsWith("$ ") ? "dim" : "";
function appendLines(lines) {
  const c = $("console"), atBottom = c.scrollHeight - c.scrollTop - c.clientHeight < 40;
  c.insertAdjacentHTML("beforeend", lines.map((l) => `<span class="${lineClass(l)}">${esc(l)}</span>\n`).join(""));
  if (atBottom) c.scrollTop = c.scrollHeight;
}
async function showJob(id) {
  activeJob = id; jobCursor = 0; $("console").innerHTML = ""; clearInterval(polling);
  const tick = async () => {
    try {
      const j = await api(`/api/jobs/${id}?since=${jobCursor}`);
      if (id !== activeJob) return;
      appendLines(j.lines); jobCursor = j.total;
      const known = S.jobs.recent.find((x) => x.id === id);
      if (known) known.status = j.status; else S.jobs.recent.unshift(j);
      renderPills();
      if (j.status !== "running") { clearInterval(polling); await refresh(); toast(`${j.label}: ${j.status}`); }
    } catch (e) { clearInterval(polling); }
  };
  await tick();
  polling = setInterval(tick, 900);
}
async function run(key, prompt) {
  try {
    const j = await api("/api/run", { key, prompt });
    S.jobs.recent = [j, ...S.jobs.recent.filter((x) => x.id !== j.id)];
    renderAutomations(); showJob(j.id);
    if ($("tab-automations").hidden) toast(`${j.label} started. Watch it in Automations`);
  } catch (e) { toast(e.message); }
}
async function openTerminal(key) {
  try {
    const r = await api("/api/terminal", { key });
    if (r.opened) return toast("Opened in Terminal");
    modal("Run this in a terminal", `<p class="small muted" style="margin-top:0">Open a terminal and paste:</p><textarea class="code" readonly style="min-height:70px" onclick="this.select()">${esc(r.command)}</textarea>`, [{ label: "Close", fn: closeModal }]);
  } catch (e) { toast(e.message); }
}

// ------------------------------------------------------------------ modal + forms
function modal(title, body, buttons) {
  $("mtitle").textContent = title; $("mbody").innerHTML = body; $("merr").textContent = "";
  const foot = $("mfoot"); foot.innerHTML = "";
  const add = (b) => {
    const el = document.createElement("button");
    el.type = "button"; el.className = "b " + (b.cls || ""); el.textContent = b.label;
    el.onclick = async () => { el.disabled = true; $("merr").textContent = ""; try { await b.fn(); } catch (err) { $("merr").textContent = err.message; } finally { el.disabled = false; } };
    foot.appendChild(el);
  };
  buttons.filter((b) => b.left).forEach(add);
  foot.appendChild(Object.assign(document.createElement("span"), { className: "sp" }));
  buttons.filter((b) => !b.left).forEach(add);
  if (!$("modal").open) $("modal").showModal();
  const first = $("mbody").querySelector("textarea:not([readonly]), input:not([readonly])");
  if (first) first.focus();
}
const closeModal = () => $("modal").close();
const val = (id) => $(id).value.trim();
async function saved(msg) { closeModal(); await refresh(); toast(msg); }
function field(f) {
  const id = "f-" + f.id, v = f.value ?? "", ph = f.placeholder ? ` placeholder="${esc(f.placeholder)}"` : "";
  const input = f.type === "textarea" ? `<textarea id="${id}" rows="${f.rows || 3}"${ph}>${esc(v)}</textarea>`
    : f.type === "select" ? `<select id="${id}">${f.options.map((o) => { const [ov, ol] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(ov)}" ${String(ov) === String(v) ? "selected" : ""}>${esc(ol)}</option>`; }).join("")}</select>`
    : `<input type="${f.type || "text"}" id="${id}" value="${esc(v)}"${ph}${f.readonly ? " readonly" : ""}>`;
  return `<label class="field"><span>${esc(f.label)}</span>${input}${f.hint ? `<div class="small faint">${esc(f.hint)}</div>` : ""}</label>`;
}
const fields = (list) => list.map(field).join("");
const read = (list) => Object.fromEntries(list.map((f) => [f.id, $("f-" + f.id).value.trim()]));
const deptOptions = () => [["", "No department"], ...S.departments.map((d) => [d.slug, d.name])];
const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");

function simpleForm(title, list, submitLabel, onSubmit, extra = []) {
  modal(title, fields(list), [...extra, { label: "Cancel", fn: closeModal }, { label: submitLabel, cls: "primary", fn: async () => { await onSubmit(read(list)); } }]);
}
function northStarForm() {
  const g = S.goals.north_star, f = [{ id: "text", label: "North star", type: "textarea", value: g?.text, rows: 2, placeholder: "One sentence: what you're building toward" }, { id: "detail", label: "What it means (optional)", type: "textarea", value: g?.detail }];
  simpleForm("North star", f, "Save", async (v) => { await rpc("north_star_set", { text: v.text, detail: v.detail }); await saved("North star saved"); });
}
function yearGoalForm(g) {
  const f = [{ id: "text", label: "Goal for this year", value: g?.text }, { id: "detail", label: "Detail (optional)", type: "textarea", value: g?.detail }];
  simpleForm(g ? "Edit goal" : "Add a goal for this year", f, "Save", async (v) => { g ? await rpc("goal_update", { goal_id: g.id, text: v.text, detail: v.detail }) : await rpc("year_add", { text: v.text, detail: v.detail }); await saved("Saved"); },
    g ? [{ label: "Delete", cls: "danger", left: true, fn: async () => { if (confirm("Delete this goal?")) { await rpc("goal_remove", { goal_id: g.id }); await saved("Deleted"); } } }] : []);
}
function deptForm(d) {
  const f = [{ id: "name", label: "Name", value: d?.name, placeholder: "e.g. Marketing" }, { id: "owner", label: "Lead", value: d?.owner, placeholder: "You, or a name" }, { id: "hours", label: "Hours per week", value: d?.hours, placeholder: "e.g. 5" },
    { id: "owns", label: "What it owns", type: "textarea", value: d?.owns, rows: 2 }, { id: "intro", label: "What it's trying to do", type: "textarea", value: d?.intro, rows: 2 }];
  simpleForm(d ? `Edit ${d.name}` : "Add a department", f, "Save", async (v) => {
    if (d) await rpc("dept_update", { ref: d.slug, ...v }); else await rpc("dept_add", v);
    await saved("Saved"); if (!d) { const slug = (S.departments.slice(-1)[0] || {}).slug; if (slug) showTab(slug); }
  }, d ? [{ label: "Delete", cls: "danger", left: true, fn: async () => { if (confirm(`Delete ${d.name}? Its notes and metrics are kept, unassigned. Its page sections are deleted (restorable from history).`)) { await rpc("dept_remove", { ref: d.slug }); showTab("dashboard"); await saved("Deleted"); } } }] : []);
}
function betForm(b) {
  const f = [{ id: "title", label: "The bet", value: b?.title, placeholder: "What you're wagering this quarter" }, { id: "department", label: "Department that carries it", type: "select", options: deptOptions(), value: b?.department || "" },
    { id: "success", label: "Wins if (a number)", value: b?.success }, { id: "why", label: "Why", type: "textarea", value: b?.why, rows: 2 },
    { id: "status", label: "Status", type: "select", options: STATUSES, value: b?.status || "not started" }, { id: "status_note", label: "Status note", value: b?.status_note },
    { id: "next_steps", label: "Next steps (one per line)", type: "textarea", value: b?.next_steps, rows: 3 }];
  simpleForm(b ? `Edit Bet ${b.n}` : "New bet", f, "Save", async (v) => { b ? await rpc("bet_update", { n: b.n, ...v }) : await rpc("bet_add", v); await saved("Saved"); },
    b ? [{ label: "Delete", cls: "danger", left: true, fn: async () => { if (confirm("Delete this bet? Items that served it become 'no bet'.")) { await rpc("bet_remove", { n: b.n }); await saved("Deleted"); } } }] : []);
}
function metricForm(m) {
  const f = [...(m ? [] : [{ id: "key", label: "Key", placeholder: "lowercase_with_underscores, e.g. mrr", hint: "Automations use this to send values. Can't change later." }]),
    { id: "name", label: "Name", value: m?.name, placeholder: "e.g. Monthly recurring revenue" }, { id: "department", label: "Department", type: "select", options: deptOptions(), value: m?.department || "" },
    { id: "unit", label: "Unit", value: m?.unit, placeholder: "EUR, %, users…" }, { id: "definition", label: "Definition", type: "textarea", value: m?.definition, rows: 2, placeholder: "What exactly is counted, and what isn't" },
    { id: "healthy", label: "Healthy", value: m?.healthy, placeholder: ">= 3000" }, { id: "watch", label: "Watch", value: m?.watch, placeholder: "1000-2999" }, { id: "bad", label: "Bad", value: m?.bad, placeholder: "< 1000", hint: "Bands look like >= 3000, <= 3, 1000-2999. Leave blank until you know." }];
  simpleForm(m ? `Edit ${m.name}` : "New metric", f, "Save", async (v) => {
    if (m) await rpc("metric_update", { key: m.key, ...v }); else await rpc("metric_add", { ...v, key: v.key || slugify(v.name) });
    await saved("Saved");
  }, m ? [{ label: "Delete", cls: "danger", left: true, fn: async () => { if (confirm(`Delete ${m.name} and its whole history? It stays in the change log.`)) { await rpc("metric_remove", { key: m.key }); await saved("Deleted"); } } }] : []);
}
function pointForm(key, day, value) {
  if (!S.metrics.length) return toast("Add a metric first.");
  const f = [{ id: "key", label: "Metric", type: "select", options: S.metrics.map((m) => [m.key, m.name]), value: key || S.metrics[0].key }, { id: "date", label: "Date", type: "date", value: day || S.today },
    { id: "value", label: "Value", value: value ?? "" }, { id: "note", label: "Note (optional)", placeholder: "Where the number came from" }];
  simpleForm(day ? "Edit value" : "Log a value", f, "Save", async (v) => { await rpc("point_set", v); await saved("Saved"); });
}
function decisionForm(d) {
  const f = [{ id: "title", label: "Decision", value: d?.title, placeholder: "e.g. Audits are a fixed fee" }, { id: "decided", label: "Decided: what we're doing", type: "textarea", value: d?.decided, rows: 2 },
    { id: "why", label: "Why: the reasoning and the number that prompted it", type: "textarea", value: d?.why, rows: 2 }, { id: "expect", label: "Expect: what should be true by the review if this was right", type: "textarea", value: d?.expect, rows: 2, placeholder: "Something you can check, ideally a number" },
    { id: "review_on", label: "Review on", type: "date", value: d?.review_on || shiftDay(S.today, -30) }, ...(d ? [] : [{ id: "department", label: "Department", type: "select", options: deptOptions() }])];
  simpleForm(d ? "Edit decision" : "Log a decision", f, d ? "Save" : "Log decision", async (v) => {
    if (d) await rpc("decision_update", { decision_id: d.id, title: v.title, decided: v.decided, why: v.why, expect: v.expect, review_on: v.review_on });
    else { await rpc("decision_add", v); await rpc("log_add", { type: "decision", title: v.title, body: `Expect: ${v.expect} (review ${v.review_on})`, department: v.department || null }); }
    await saved("Saved");
  }, d ? [] : [{ label: "Talk it through with Claude ↗", left: true, fn: async () => { await openTerminal("record"); closeModal(); } }]);
}
function outcomeForm(id) {
  const d = S.decisions.find((x) => x.id === id);
  modal("Outcome: " + plain(d.title), `<p class="small muted" style="margin-top:0"><b>Expected:</b> ${md(d.expect)}</p>
    <label class="field"><span>What happened: right, wrong or mixed, and what it taught</span><textarea id="m-text" rows="4">${esc(d.outcome)}</textarea></label>`, [
    { label: "Cancel", fn: closeModal }, { label: "Save outcome", cls: "primary", fn: async () => { await rpc("decision_outcome", { decision_id: id, text: val("m-text") }); await saved("Outcome saved"); } }]);
}
function docForm(d, preset) {
  const kinds = ["note", "source", "playbook"].concat(d && d.kind === "section" ? ["section"] : []);
  const f = [{ id: "title", label: "Title", value: d?.title }, ...(d?.kind === "section" ? [] : [{ id: "kind", label: "Kind", type: "select", options: kinds, value: d?.kind || preset?.kind || "note" }, { id: "department", label: "Department", type: "select", options: deptOptions(), value: d?.department || preset?.department || "" }, { id: "tags", label: "Tags (comma separated)", value: d?.tags }]),
    { id: "body", label: "Text (markdown)", type: "textarea", value: d?.body, rows: 12 }];
  modal(d ? `Edit: ${d.title}` : preset?.kind === "section" ? "New section" : "New document", fields(f).replace("<textarea id=\"f-body\"", "<textarea class=\"code\" id=\"f-body\""), [
    ...(d ? [{ label: "Delete", cls: "danger", left: true, fn: async () => { if (confirm("Delete this? It stays restorable from the change history.")) { await rpc("doc_remove", { ref: d.slug }); await saved("Deleted"); } } }] : []),
    { label: "Cancel", fn: closeModal },
    { label: "Save", cls: "primary", fn: async () => {
      const v = read(f);
      if (d) await rpc("doc_update", { ref: d.slug, ...v });
      else await rpc("doc_add", { ...v, kind: preset?.kind || v.kind, department: preset?.department ?? v.department });
      await saved("Saved, with history");
    } }]);
}
function factForm(key) {
  const f = [{ id: "key", label: "Fact", value: key || "", placeholder: "e.g. runway", readonly: !!key }, { id: "value", label: "Value", type: "textarea", value: key ? S.profile[key] : "", rows: 2 }];
  simpleForm(key ? "Edit fact" : "Add a fact about the business", f, "Save", async (v) => { await rpc("profile_set", v); await saved("Saved"); });
}
function callForm(c) {
  const f = [{ id: "question", label: "The question", value: c?.question }, { id: "context", label: "What makes it hard, and what deciding it unlocks", type: "textarea", value: c?.context, rows: 3 }];
  simpleForm(c ? "Edit open call" : "New open call", f, "Save", async (v) => { c ? await rpc("call_update", { call_id: c.id, ...v }) : await rpc("call_add", v); await saved("Saved"); },
    c ? [{ label: "Delete", cls: "danger", left: true, fn: async () => { await rpc("call_remove", { call_id: c.id }); await saved("Deleted"); } }] : []);
}
function logForm() {
  const f = [{ id: "type", label: "Type", type: "select", options: ["capture", "change", "report", "ingest", "weekly", "decision", "experiment", "lint", "note"] }, { id: "title", label: "Title" }, { id: "body", label: "Detail (optional)", type: "textarea", rows: 3 }];
  simpleForm("Add a log entry", f, "Add", async (v) => { await rpc("log_add", v); await saved("Logged"); });
}
function editTask(id) {
  const T = S.tasks, item = [...T.goals, ...T.today_items, ...T.done].find((x) => x.id === id);
  if (!item) return;
  const opts = `<option value="">No bet</option>` + S.bets.map((b) => `<option value="${b.n}" ${item.bet === b.n ? "selected" : ""}>Bet ${b.n}: ${esc(plain(b.title))}</option>`).join("");
  modal(item.kind === "goal" ? "Edit weekly goal" : "Edit priority", `<label class="field"><span>Text</span><input type="text" id="m-text" value="${esc(item.text)}"></label><label class="field"><span>Serves</span><select id="m-bet">${opts}</select></label>`, [
    { label: "Delete", cls: "danger", left: true, fn: async () => { await rpc("task_remove", { item_id: id }); await saved("Deleted"); } }, { label: "Cancel", fn: closeModal },
    { label: "Save", cls: "primary", fn: async () => { await rpc("task_update", { item_id: id, text: val("m-text"), bet: val("m-bet") || null }); await saved("Saved"); } }]);
}

// ------------------------------------------------------------------ events
const ACTIONS = {
  "north-star": () => northStarForm(), "year-goal": () => yearGoalForm(), "year-edit": (k) => yearGoalForm(S.goals.year.find((g) => g.id === Number(k))),
  "dept-add": () => deptForm(), "dept-edit": (k) => deptForm(areaOf(k)),
  "bet-add": () => betForm(), "bet-edit": (k) => betForm(S.bets.find((b) => b.n === Number(k))),
  "metric-add": (k) => { metricForm(); if (k) setTimeout(() => { $("f-department").value = k; }, 0); }, "point-add": () => pointForm(),
  "decision-add": () => decisionForm(), "fact-add": () => factForm(), "fact-edit": (k) => factForm(k),
  "fact-del": async (k) => { if (confirm(`Remove "${k}"?`)) { await rpc("profile_unset", { key: k }); await saved("Removed"); } },
  "call-add": () => callForm(), "call-edit": (k) => callForm(S.calls.find((c) => c.id === Number(k))),
  "call-resolve": (k) => modal("Resolve open call", `<label class="field"><span>How it was resolved (if it became a real choice, also log a decision)</span><textarea id="m-text" rows="3"></textarea></label>`,
    [{ label: "Cancel", fn: closeModal }, { label: "Resolve", cls: "primary", fn: async () => { await rpc("call_resolve", { call_id: Number(k), resolution: val("m-text") }); await saved("Resolved"); } }]),
  "doc-add": (k) => docForm(null, k ? { department: k } : null), "section-add": (k) => docForm(null, { kind: "section", department: k }),
  "log-add": () => logForm(),
  "inbox-file": async (k) => { await rpc("inbox_file", { item_id: Number(k), to: "manually" }); await refresh(); },
  "inbox-del": async (k) => { await rpc("inbox_remove", { item_id: Number(k) }); await refresh(); },
  "backup": async () => { const r = await api("/api/backup", {}); toast("Backed up: " + r.path.split("/").slice(-2).join("/")); },
  "demo-clear": async () => { if (confirm("Remove the demo data? Anything you added or edited is kept.")) { const r = await rpc("clear"); await refresh(); toast(`Demo cleared (${r.result.removed} rows)`); } },
  "demo-load": async () => { await rpc("load"); await refresh(); toast("Demo loaded"); },
  "auto-remove": async (k) => { if (confirm(`Remove automations/${k}? Your metrics and their history stay.`)) { await rpc("remove_automation", { name: k }); await refresh(); } },
};
document.addEventListener("click", async (e) => {
  const t = e.target.closest("[data-tab],[data-run],[data-term],[data-op],[data-job],#stop,[data-act],[data-taskedit],[data-outcome],[data-decision],[data-metric],[data-doc],[data-hit],[data-libkind],[data-actor],[data-revert],[data-install],[data-profile],[data-sched]");
  if (!t || t.closest("#modal") && !t.dataset.revert && !t.dataset.doc) return;
  try {
    if (t.dataset.act) { e.preventDefault(); return await ACTIONS[t.dataset.act](t.dataset.key); }
    if (t.dataset.taskedit) return editTask(Number(t.dataset.taskedit));
    if (t.dataset.outcome) { e.preventDefault(); return outcomeForm(Number(t.dataset.outcome)); }
    if (t.dataset.decision) { e.preventDefault(); return openDecision(Number(t.dataset.decision)); }
    if (t.dataset.metric) return openMetric(t.dataset.metric, "day");
    if (t.dataset.doc) { e.preventDefault(); return openDoc(t.dataset.doc); }
    if (t.dataset.hit) { e.preventDefault(); const [kind, id] = [t.dataset.hit.split(":")[0], t.dataset.hit.split(":").slice(1).join(":")]; return kind === "document" ? openDoc(id) : kind === "decision" ? openDecision(Number(id)) : kind === "metric" ? openMetric(id) : showTab("activity"); }
    if ("libkind" in t.dataset) { LIB.kind = t.dataset.libkind; return renderLibrary(); }
    if ("actor" in t.dataset) { CH_ACTOR = t.dataset.actor; return renderActivity(); }
    if (t.dataset.revert) {
      if (!confirm("Undo this change? The undo is recorded too.")) return;
      const r = await rpc("revert", { change_id: Number(t.dataset.revert) }); await refresh(); closeModal(); return toast(r.result);
    }
    if (t.dataset.install) { const r = await rpc("install_automation", { name: t.dataset.install }); await refresh(); return modal("Installed " + r.result.name, `<p>${md(r.result.next)}</p>${r.result.metrics_created.length ? `<p class="small muted">Metrics created: ${r.result.metrics_created.map(esc).join(", ")}</p>` : ""}`, [{ label: "Done", cls: "primary", fn: closeModal }]); }
    if (t.dataset.profile) { const r = await rpc("apply_profile", { name: t.dataset.profile }); await refresh(); return toast(`Added ${r.result.departments.length} departments and ${r.result.metrics.length} metrics`); }
    if (t.dataset.sched) { await api("/api/refresh_at", { time: t.dataset.sched === "on" ? val("sched-time") : "" }); await refresh(); return toast(t.dataset.sched === "on" ? "Daily refresh on" : "Daily refresh off"); }
    if (t.dataset.tab) return showTab(t.dataset.tab);
    if (t.dataset.run) return run(t.dataset.run);
    if (t.dataset.job) return showJob(t.dataset.job);
    if (t.id === "stop") return api(`/api/jobs/${activeJob}/stop`, {});
    if (t.dataset.term) return openTerminal(t.dataset.term);
    if (t.dataset.op) {
      if (t.tagName === "INPUT") e.preventDefault();
      const id = Number(t.dataset.id);
      await (t.dataset.op === "toggle" ? rpc("task_toggle", { item_id: id }) : rpc("task_remove", { item_id: id }));
      await refresh();
    }
  } catch (err) { toast(err.message); }
});
$("mclose").onclick = closeModal;
$("mbody").addEventListener("click", async (e) => {
  const t = e.target.closest("[data-period],[data-pdel],[data-pedit]");
  if (!t) return;
  const m = S.metrics.find((x) => x.key === MP.key);
  if (t.dataset.period) return openMetric(MP.key, t.dataset.period);
  if (t.dataset.pedit) return pointForm(m.key, t.dataset.pedit, m.points.find((p) => p.as_of === t.dataset.pedit)?.value);
  if (!confirm(`Delete ${m.name} on ${dayLabel(t.dataset.pdel)}?`)) return;
  try { await rpc("point_delete", { key: m.key, date: t.dataset.pdel }); await refresh(); openMetric(MP.key); toast("Deleted"); } catch (err) { $("merr").textContent = err.message; }
});
$("mbody").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.matches("input[type=text], input[type=date]")) { e.preventDefault(); $("mfoot").querySelector(".primary")?.click(); }
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("mfoot").querySelector(".primary")?.click();
});
document.querySelectorAll("form.add[data-kind]").forEach((f) => {
  f.querySelector("select").addEventListener("change", (e) => (e.target.dataset.touched = "1"));
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = f.querySelector("input"), bet = f.querySelector("select").value, text = input.value.trim();
    if (!text) return;
    try { await rpc("task_add", { kind: f.dataset.kind, text, bet: bet ? Number(bet) : null }); input.value = ""; await refresh(); } catch (err) { toast(err.message); }
  });
});
$("capture").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = e.target.querySelector("input");
  if (!input.value.trim()) return;
  try { await rpc("inbox_add", { text: input.value }); input.value = ""; toast("Captured"); await refresh(); } catch (err) { toast(err.message); }
});
$("ask").addEventListener("submit", (e) => { e.preventDefault(); const ta = e.target.querySelector("textarea"); if (ta.value.trim()) { run("ask", ta.value.trim()); ta.value = ""; } });
$("ask").querySelector("textarea").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("ask").requestSubmit(); });
$("lib-q").addEventListener("input", (e) => librarySearch(e.target.value));
const tabFromHash = () => location.hash.slice(1) || "dashboard";
window.addEventListener("hashchange", () => showTab(tabFromHash()));

async function refresh() {
  try { S = await api("/api/state"); render(); }
  catch (e) { toast("Console server unreachable. Is it running?"); }
}
function boot() {
  showTab(tabFromHash());
  refresh().then(() => { const r = S?.jobs.recent.find((j) => j.status === "running"); if (r) showJob(r.id); });
  setInterval(() => { if (!document.hidden && !$("modal").open) refresh(); }, 30000);
}
