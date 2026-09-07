/* One Tap Manager — Smart workspace on top of the shared backend.
   Pivoted from café analytics to a small social-media product seller. */

const state = {
  // SHARED LOGIN + SESSION with the Classic app (both use the cx_* keys in
  // localStorage) — log in once, you're logged in everywhere; data too.
  sessionId: localStorage.getItem("cx_session") || (crypto.randomUUID ? crypto.randomUUID() : String(Math.random())),
  token: localStorage.getItem("cx_token") || null,
  email: localStorage.getItem("cx_email") || null,
  data: { sales: {}, review: {} },
  productType: null,
  productTypes: [],
  lastState: null,
};
localStorage.setItem("cx_session", state.sessionId);

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => n == null ? "—" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const relTime = (iso) => {
  if (!iso) return "";
  const t = new Date(iso).getTime(); if (!t) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  if (s < 86400 * 30) return Math.floor(s / 86400) + "d ago";
  return new Date(iso).toLocaleDateString();
};

// ---------- theme (shared with classic app via localStorage["cx_theme"]) ----------
function currentTheme() { return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"; }
function setTheme(mode) {
  document.documentElement.setAttribute("data-theme", mode);
  try { localStorage.setItem("cx_theme", mode); } catch (e) {}
  syncThemeButtons();
  redrawCharts();
}
function syncThemeButtons() {
  const mode = currentTheme();
  document.querySelectorAll("[data-theme-set]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeSet === mode)));
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-theme-set]");
  if (b) setTheme(b.dataset.themeSet);
});
syncThemeButtons();

function toast(msg, ms = 3200) {
  const t = $("toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(t._t); t._t = setTimeout(() => (t.hidden = true), ms);
}

/* The one stroke icon set, fetched once at boot and shared with every
   storefront this app publishes. Emoji rendered differently on every machine,
   carried no weight or colour, and made the app look like a prototype next to
   the sites it produces. */
const ICONS = Object.create(null);

/* Are uploads actually safe on this deployment? Media used to be written into
   the checked-out repo folder, which every redeploy rebuilds from git — so
   images and clips vanished and nobody found out until they looked at their
   own site. Now the app knows, and says so. */
let _media = null;
async function loadMediaStatus() {
  try { _media = await api("/api/media/status"); }
  catch (e) { _media = null; }
  return _media;
}

/* One banner, rendered wherever a seller is about to upload something. */
function mediaWarning() {
  if (!_media || _media.durable) return "";
  return `<div class="media-warn">${sic("shield")}
    <div><b>Uploads are not safe on this server yet</b>
    <span>${esc(_media.detail)}</span></div></div>`;
}

async function loadIcons() {
  try {
    const d = await fetch("/api/icons").then((r) => r.json());
    Object.assign(ICONS, d.icons || {});
  } catch (e) { /* icons degrade to empty glyphs, never to a broken page */ }
}

/* Undo. Every destructive action routes through here instead of doing the
   thing directly: the change is applied, and the shopper — sorry, the seller —
   gets a few seconds to take it back. Deleting a product used to be one click
   with no way back, which is the main reason people are afraid to touch
   anything in software they are still learning. */
let _undo = null;
function toastUndo(message, undoFn, ms = 7000) {
  const t = $("toast");
  clearTimeout(t._t);
  if (_undo) clearTimeout(_undo.timer);
  t.hidden = false;
  t.innerHTML = "";
  const span = document.createElement("span");
  span.textContent = message;
  const btn = document.createElement("button");
  btn.className = "toast-undo";
  btn.type = "button";
  btn.textContent = "Undo";
  t.appendChild(span);
  t.appendChild(btn);
  const close = () => { t.hidden = true; t.textContent = ""; _undo = null; };
  btn.onclick = async () => {
    btn.disabled = true;
    btn.textContent = "Undoing…";
    try { await undoFn(); toast("Put back."); }
    catch (e) { toast(e.message || "Could not undo that."); }
    finally { _undo = null; }
  };
  _undo = { timer: setTimeout(close, ms) };
}

async function api(path, opts = {}) {
  const headers = { "X-Session-Id": state.sessionId, ...(opts.headers || {}) };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  if (opts.json) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  const res = await fetch(path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error((d && typeof d === "object" ? d.message : d) || res.statusText);
  }
  return data;
}

async function download(url, filename) {
  const res = await fetch(url, { headers: { "X-Session-Id": state.sessionId, "Authorization": "Bearer " + state.token } });
  if (!res.ok) { toast("Download failed"); return; }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = filename || "export.xlsx";
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
}

// ---------- auth ----------
$("loginBtn").onclick = doLogin;
$("password").addEventListener("keydown", (e) => e.key === "Enter" && doLogin());
async function doLogin() {
  const err = $("loginErr"); err.hidden = true;
  try {
    const d = await api("/api/login", { method: "POST", json: { email: $("email").value, password: $("password").value } });
    state.token = d.token; state.email = d.email;
    localStorage.setItem("cx_token", d.token); localStorage.setItem("cx_email", d.email);
    showShell();
  } catch (e) { err.textContent = e.message; err.hidden = false; }
}
$("logoutBtn").onclick = async () => {
  try { await api("/api/logout", { method: "POST" }); } catch {}
  state.token = null; state.email = null;
  localStorage.removeItem("cx_token"); localStorage.removeItem("cx_email");
  $("appShell").hidden = true; $("loginView").hidden = false;
};

function showShell() {
  $("loginView").hidden = true; $("appShell").hidden = false;
  $("tbUser").textContent = state.email || "";
  goHome();
}
$("homeBtn").onclick = goHome;

// ---------- view helpers ----------
function setView(html) { $("view").innerHTML = html; }
function setCrumb(t) { $("crumb").textContent = t || ""; }
function showRail(on) { document.querySelector(".shell-body").classList.toggle("no-rail", !on); }

// ---------- charts: image-like inline, interactive when maximized ----------
// Inline charts render STATIC (like an image). A ⤢ button on each opens it
// full-screen where you can zoom / pan / reset / download — the same
// "expand to analyse" mechanism the Classic app uses.
const _charts = {};
function cssVar(name, fb) { const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim(); return v || fb; }

function _baseLayout() {
  const axisColor = cssVar("--axis", "#47505f");
  const gridColor = cssVar("--grid", "#eef0f3");
  const surface = cssVar("--surface", "#fff");
  const text = cssVar("--text", "#14171d");
  return {
    margin: { l: 58, r: 16, t: 8, b: 42 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, sans-serif", size: 12, color: axisColor }, bargap: 0.4,
    xaxis: { gridcolor: gridColor, zeroline: false, automargin: true, separatethousands: true, tickfont: { color: axisColor } },
    yaxis: { gridcolor: gridColor, zeroline: false, automargin: true, separatethousands: true, griddash: "dot", tickfont: { color: axisColor } },
    hoverlabel: { bgcolor: surface, bordercolor: cssVar("--border", "#e0e4ea"), font: { color: text } },
    legend: { orientation: "h", y: -0.2, font: { color: axisColor } },
    colorway: [cssVar("--primary", "#6d28d9"), "#0ea5e9", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6"],
  };
}

function plot(el, traces, layout = {}, title = "") {
  if (!window.Plotly) { el.innerHTML = "Charts failed to load."; return; }
  if (el.id) _charts[el.id] = { traces, layout, title };
  const base = _baseLayout();
  Plotly.newPlot(el, traces, { ...base, ...layout, xaxis: { ...base.xaxis, ...(layout.xaxis || {}) }, yaxis: { ...base.yaxis, ...(layout.yaxis || {}) } },
    { displayModeBar: false, responsive: true, staticPlot: true });
  _addExpand(el, title);
}

function _addExpand(el, title) {
  const card = el.closest(".chart-card") || el.parentElement;
  if (!card || card.querySelector(".chart-expand")) return;
  card.style.position = card.style.position || "relative";
  const btn = document.createElement("button");
  btn.className = "chart-expand"; btn.title = "Maximize to analyse (zoom, pan, download)";
  btn.textContent = "⤢";
  btn.onclick = (e) => { e.stopPropagation(); openChartModal(el.id, title); };
  card.appendChild(btn);
}

let _modalChart = null, _modalMode = "zoom";
function openChartModal(id, title) {
  const c = _charts[id]; if (!c || !window.Plotly) return;
  _modalChart = id;
  $("chartModal").style.display = "flex";
  $("chartModalTitle").textContent = title || c.title || "Chart";
  const host = $("chartModalPlot");
  const base = _baseLayout();
  const layout = { ...base, ...c.layout, xaxis: { ...base.xaxis, ...(c.layout.xaxis || {}) }, yaxis: { ...base.yaxis, ...(c.layout.yaxis || {}) },
    autosize: true, height: Math.floor(window.innerHeight * 0.66), dragmode: _modalMode };
  Plotly.newPlot(host, c.traces, layout, { displayModeBar: false, responsive: true, staticPlot: false, scrollZoom: false });
  _syncModalBtns();
}
function _syncModalBtns() {
  const z = $("chartZoomBtn"), p = $("chartPanBtn");
  if (z) z.setAttribute("aria-pressed", String(_modalMode === "zoom"));
  if (p) p.setAttribute("aria-pressed", String(_modalMode === "pan"));
}
function setModalMode(m) { _modalMode = m; const h = $("chartModalPlot"); if (h && window.Plotly) Plotly.relayout(h, { dragmode: m }); _syncModalBtns(); }
function resetModal() { const h = $("chartModalPlot"); if (h && window.Plotly) Plotly.relayout(h, { "xaxis.autorange": true, "yaxis.autorange": true }); }
function downloadModal() { const h = $("chartModalPlot"); if (h && window.Plotly) Plotly.downloadImage(h, { format: "png", scale: 2, filename: "chart" }); }
function closeChartModal() { $("chartModal").style.display = "none"; _modalChart = null; const h = $("chartModalPlot"); if (h && window.Plotly) Plotly.purge(h); }
$("chartModalClose").onclick = closeChartModal;
$("chartZoomBtn").onclick = () => setModalMode("zoom");
$("chartPanBtn").onclick = () => setModalMode("pan");
$("chartResetBtn").onclick = resetModal;
$("chartDownloadBtn").onclick = downloadModal;
$("chartModal").addEventListener("click", (e) => { if (e.target === $("chartModal")) closeChartModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && _modalChart) closeChartModal(); });

function redrawCharts() {
  if (!window.Plotly) return;
  Object.entries(_charts).forEach(([id, c]) => { const el = document.getElementById(id); if (el && el.isConnected) plot(el, c.traces, c.layout, c.title); });
  if (_modalChart) openChartModal(_modalChart);
}

// ---------- HOME ----------
const MODULES = [
  { id: "sales",      name: "Sales Analytics",        sub: "KPIs, revenue trends and a 30-day forecast from your order data.",             ico: "chart", cls: "tile-sales",     needs: "sales",  tag: "SALES" },
  { id: "subcategory",name: "Sub-Category Analysis",  sub: "Which categories & sub-categories drive revenue — trends and drill-downs.",   ico: "layers", cls: "tile-sub",       needs: "sales",  tag: "SALES" },
  { id: "supply",     name: "Supply Management",      sub: "Track inventory & suppliers, link products to materials, log waste, and get per-item EOQ/MOQ restock suggestions with PDF purchase orders.", ico: "package", cls: "tile-supply",   needs: null,     tag: "SUPPLY" },
  { id: "products",   name: "Product Management",     sub: "Your catalogue of products, each linked to the names it carries on Amazon, Shopify and other platforms — sales roll up to the product everywhere.", ico: "tag", cls: "tile-supply",   needs: null,     tag: "CATALOG" },
  { id: "site",       name: "Website Builder",        sub: "Build your own selling website — pick a theme for your genre, set fonts, colours and images, then publish. Your listed products become its shop.", ico: "globe", cls: "tile-site",     needs: null,     tag: "SITE" },
  { id: "orders",     name: "Orders",                 sub: "Every order placed on your website — status, customer, address and export. Delivered orders feed straight into your sales analytics.", ico: "bag", cls: "tile-orders",   needs: null,     tag: "ORDERS" },
  { id: "review",     name: "Review Analytics",       sub: "Your brand positioning from your own reviews — what customers come to you for.", ico: "star", cls: "tile-review",    needs: "review", tag: "BRAND" },
  { id: "complaints", name: "Complaint Analysis",     sub: "The fix-first plan for the complaint themes hurting your brand right now.",    ico: "flame", cls: "tile-complaint", needs: "review", tag: "BRAND" },
  { id: "strategy",   name: "Position Strategy + AI", sub: "A levelled checklist to strengthen or reposition your brand, plus the AI Analyst.", ico: "compass", cls: "tile-strategy", needs: "review", tag: "STRATEGY" },
  { id: "content",    name: "Content Creator",        sub: "AI-generated posts (caption, hashtags, image) — edit, then save to your device.", ico: "spark", cls: "tile-content",   needs: null,     tag: "CONTENT" },
  { id: "instagram",  name: "Instagram",              sub: "Your Instagram content manager — plan, generate and schedule posts, then auto-publish. In build.",                                   ico: "instagram", cls: "tile-ig",        needs: null,     tag: "CONNECT", upcoming: true },
  { id: "ads",        name: "Ad Analytics",           sub: "Connect Google, Meta, Instagram and other ad accounts to see your spend.",    ico: "trend", cls: "tile-ads",       needs: null,     tag: "ADS" },
];

async function goHome() {
  _afterUpload = null;
  setCrumb(""); showRail(true);
  setView(`<div class="ap-empty">Loading your workspace…</div>`);
  try {
    const s = await api("/api/smart/state");
    state.lastState = s; state.data = s.data;
    try { const pt = await api("/api/product-type"); state.productType = pt.product_type; state.productTypes = pt.types; } catch (e) {}
    renderHome(s);
    renderApprovals(s.insights);
  } catch (e) {
    setView(`<div class="card">${esc(e.message)}</div>`);
  }
}

function productLabel(id) {
  const t = (state.productTypes || []).find((x) => x.id === id);
  return t ? `${t.icon} ${t.label}` : "Not set";
}

function dataCard(kind, label, icon, hint) {
  const d = state.data[kind] || {};
  const ready = d.ready;
  return `
    <div class="data-card">
      <h4><span class="data-card-ico">${icon}</span>${label}</h4>
      <div class="status">
        <span class="dot ${ready ? "ready" : "empty"}"></span>
        ${ready ? `${fmt(d.rows)} rows loaded${d.updated_at ? ` · saved ${esc(String(d.updated_at).slice(0, 10))}` : ""}` : `No ${label.toLowerCase()} yet — ${hint}`}
      </div>
      <div class="row">
        <button class="btn primary sm" data-up="${kind}">${sic(ready ? "refresh" : "arrow-up-right")}${ready ? "Update" : "Upload"} ${label}</button>
        ${ready ? `<button class="btn ghost sm" data-add="${kind}" title="Add more rows to your saved data">${sic("plus")}Add records</button>` : ""}
        ${ready ? `<button class="btn ghost sm" data-remap="${kind}" title="Adjust which column is which">${sic("compass")}Map</button>` : ""}
        ${ready ? `<button class="btn ghost sm" data-clear="${kind}">Remove</button>` : ""}
      </div>
    </div>`;
}

/* ---- one modal helper, matching the shape openIconPicker already uses ---- */
let _modalEl = null;
function openModal(title, bodyHtml, opts = {}) {
  closeModal();
  const wrap = document.createElement("div");
  wrap.className = "modal-back";
  wrap.innerHTML = `<div class="modal${opts.wide ? " wide" : ""}">
      <div class="modal-head"><b>${esc(title)}</b>
        <button class="btn ghost tiny" data-mclose>${sic("close")}</button></div>
      <div class="modal-body">${bodyHtml}</div>
    </div>`;
  document.body.appendChild(wrap);
  _modalEl = wrap;
  wrap.querySelector("[data-mclose]").onclick = closeModal;
  wrap.onclick = (e) => { if (e.target === wrap) closeModal(); };
  document.addEventListener("keydown", _escClose);
  return wrap;
}
function closeModal() {
  if (_modalEl) { _modalEl.remove(); _modalEl = null; }
  document.removeEventListener("keydown", _escClose);
}
function _escClose(e) { if (e.key === "Escape") closeModal(); }

/* Nobody should have to find a CSV on this laptop to see what the app does. */
async function startDemo() {
  try {
    toast("Loading 90 days of sample data…");
    await api("/api/demo", { method: "POST" });
    await goHome();
    toast("Sample data loaded — every module is live now.");
  } catch (e) { toast(e.message); }
}

/* --------------------------------------------------------------- Today ----
   Twelve tiles is a filing cabinet, not an answer. This is the answer: the
   three things worth doing this morning, each one a click away from the place
   it gets done. The same rows the morning digest sends, so the two can never
   disagree. */
let _digest = null;

async function renderToday() {
  const rows = $("todayRows"), title = $("todayTitle");
  if (!rows) return;
  let d;
  try { d = await api("/api/today"); }
  catch (e) {
    rows.innerHTML = `<div class="ap-empty">Could not read your shop just now.</div>`;
    if (title) title.textContent = "Today";
    return;
  }
  _digest = d.digest || null;
  const items = d.items || [];

  if (!items.length) {
    const e = d.empty || {};
    title.textContent = e.title || "Nothing needs you this morning";
    rows.innerHTML = `<div class="today-empty">
      <span>${esc(e.detail || "")}</span>
      ${e.cta ? `<button class="btn ghost sm" id="todayCta">${esc(e.cta)}</button>` : ""}</div>`;
    const cta = $("todayCta");
    if (cta) cta.onclick = startDemo;
  } else {
    title.textContent = items.length === 1
      ? "One thing worth your time"
      : `${items.length} things worth your time`;
    rows.innerHTML = items.map((it) => `
      <button class="today-row sev-${esc(it.severity)}" data-today="${esc(it.route)}">
        <span class="today-dot"></span>
        <span class="today-txt"><b>${esc(it.title)}</b><span>${esc(it.detail)}</span></span>
        ${sic("arrow-right", "today-arrow")}
      </button>`).join("");
    document.querySelectorAll("[data-today]").forEach((b) => b.onclick = () => {
      const r = b.dataset.today;
      if (r === "rfm") { openModule("sales"); setTimeout(() => toast("Your at-risk customers are in the RFM section."), 400); }
      else openModule(r);
    });
  }
  renderProof();
  const db = $("digestBtn");
  if (db) {
    db.classList.toggle("on", !!(_digest && _digest.enabled));
    db.onclick = openDigest;
  }
}

/* The renewal conversation, in one line, on the home screen. */
async function renderProof() {
  const box = $("proofLine");
  if (!box) return;
  try {
    const p = await api("/api/rfm/winback/proof");
    if (!p.headline || !(p.totals && p.totals.contacted)) { box.hidden = true; return; }
    box.hidden = false;
    box.innerHTML = `${sic("trend")}<span>${esc(p.headline)}</span>
      <button class="btn ghost tiny" id="proofMore">How this is counted</button>`;
    const m = $("proofMore");
    if (m) m.onclick = () => toast(p.method, 7000);
  } catch (e) { box.hidden = true; }
}

/* Low stock, new orders, a theme rising — none of it reaches a seller who has
   to remember to log in. For a tool opened a handful of times a month, this
   IS the retention mechanism. */
function openDigest() {
  const d = _digest || { enabled: false, email: state.email, phone: "", hour: 8 };
  const hours = Array.from({ length: 24 }, (_, h) =>
    `<option value="${h}"${h === d.hour ? " selected" : ""}>${String(h).padStart(2, "0")}:00</option>`).join("");
  openModal("Morning digest", `
    <p class="muted" style="margin-top:0;">One message a day with the same rows you see under
      <b>Today</b> — new orders, items below their reorder point, customers slipping away.
      Nothing else.</p>
    <label class="fld"><span>Send it</span>
      <select id="dgOn">
        <option value="1"${d.enabled ? " selected" : ""}>Every morning</option>
        <option value="0"${d.enabled ? "" : " selected"}>Never — I'll check myself</option>
      </select></label>
    <label class="fld"><span>At</span><select id="dgHour">${hours}</select></label>
    <label class="fld"><span>Email</span><input id="dgEmail" value="${esc(d.email || state.email)}" /></label>
    <label class="fld"><span>WhatsApp number <span class="muted">(optional)</span></span>
      <input id="dgPhone" value="${esc(d.phone || "")}" placeholder="10-digit mobile" inputmode="numeric" /></label>
    <p class="muted tiny">WhatsApp delivery switches on the moment a provider is connected —
      your number is stored ready for it.</p>
    <div class="modal-actions">
      <button class="btn ghost" id="dgTest">Send me one now</button>
      <button class="btn primary" id="dgSave">Save</button>
    </div>`);
  $("dgSave").onclick = async () => {
    try {
      const r = await api("/api/digest", { method: "POST", json: {
        enabled: $("dgOn").value === "1",
        hour: +$("dgHour").value,
        email: $("dgEmail").value.trim(),
        phone: $("dgPhone").value.trim(),
      }});
      _digest = r.digest;
      closeModal();
      toast(r.digest.enabled
        ? `Digest on — every morning at ${String(r.digest.hour).padStart(2, "0")}:00.`
        : "Digest off.");
      const db = $("digestBtn"); if (db) db.classList.toggle("on", !!r.digest.enabled);
    } catch (e) { toast(e.message); }
  };
  $("dgTest").onclick = async () => {
    const b = $("dgTest"); b.disabled = true; b.textContent = "Sending…";
    try {
      const r = await api("/api/digest/test", { method: "POST" });
      toast(r.sent ? "Sent — check your inbox."
                   : (r.reason || "Nothing worth sending right now."), 5000);
    } catch (e) { toast(e.message); }
    b.disabled = false; b.textContent = "Send me one now";
  };
}

function renderHome(s) {
  const tiles = MODULES.map((m) => {
    const locked = m.needs && !(state.data[m.needs] && state.data[m.needs].ready);
    const upcoming = !!m.upcoming;
    return `<div class="app-tile ${m.cls} ${locked || upcoming ? "locked" : ""}" data-mod="${m.id}">
        <div class="app-ico">${sic(m.ico)}</div>
        <div class="name">${esc(m.name)}</div>
        <div class="sub">${esc(m.sub)}</div>
        <div class="meta">
          <span class="badge">${upcoming ? "Planned" : (locked ? "Needs " + m.needs + " data" : m.tag)}</span>
          <span class="go">${upcoming ? "Soon" : (locked ? "Locked" : "Open")}${sic("arrow-right")}</span>
        </div>
      </div>`;
  }).join("");

  const tasks = (s.tasks || []);
  const taskRows = tasks.length ? tasks.map((t) => `
      <div class="task-item ${t.done ? "done" : ""}" data-task="${t.id}">
        <input type="checkbox" ${t.done ? "checked" : ""} />
        <span class="t">${esc(t.text)}</span>
        <button class="task-del" title="Delete">${sic("close")}</button>
      </div>`).join("") : `<div class="ap-empty">No tasks yet. Approving an insight adds one automatically.</div>`;

  setView(`
    <div class="page-head"><h2>Welcome back</h2><span class="muted">${esc(state.email)}</span></div>

    <section class="today" id="todayBox">
      <div class="today-h">
        <div>
          <div class="today-eyebrow">Today</div>
          <h3 id="todayTitle">Looking at your shop…</h3>
        </div>
        <button class="btn ghost tiny" id="digestBtn" title="Get this by email each morning">
          ${sic("bell")}Digest</button>
      </div>
      <div id="todayRows" class="today-rows"><div class="ap-empty">Checking orders, stock and customers…</div></div>
      <div id="proofLine" class="today-proof" hidden></div>
    </section>

    <div class="section-title">Your data
      <button class="btn ghost tiny pt-chip" id="ptChip" title="What you sell — drives keyword tracking">${sic("tag")}${productLabel(state.productType)}</button>
    </div>
    <div class="data-grid">
      ${dataCard("sales", "Sales", sic("receipt"), "upload your orders / sales export")}
      ${dataCard("review", "Review", sic("star"), "upload your reviews (Google / marketplace / Instagram)")}
    </div>

    <div class="section-title">Listed platforms
      <span class="muted tiny" style="font-weight:500;">— every place you sell. The toggle decides whether that channel's sales count in your insights.</span>
    </div>
    <div class="chan-strip" id="chanStrip"><div class="ap-empty">Loading platforms…</div></div>

    <div class="section-title">Apps</div>
    <div class="apps-grid">${tiles}</div>

    <div class="section-title">My tasks</div>
    <div class="card">
      <div class="task-add">
        <input id="taskInput" placeholder="Add a task…" />
        <button class="btn primary sm" id="taskAddBtn">Add</button>
      </div>
      <div id="taskList">${taskRows}</div>
    </div>
  `);

  document.querySelectorAll("[data-mod]").forEach((el) => el.onclick = () => {
    const m = MODULES.find((x) => x.id === el.dataset.mod);
    if (m.upcoming) { toast("The Instagram content manager is being built — it will live right here."); return; }
    if (m.needs && !(state.data[m.needs] && state.data[m.needs].ready)) { toast(`Upload ${m.needs} data first`); return; }
    openModule(m.id);
  });
  renderChannels();
  renderToday();
  document.querySelectorAll("[data-up]").forEach((el) => el.onclick = () => startUpload(el.dataset.up));
  document.querySelectorAll("[data-add]").forEach((el) => el.onclick = () => openAddRecords(el.dataset.add));
  document.querySelectorAll("[data-clear]").forEach((el) => el.onclick = () => clearData(el.dataset.clear));
  document.querySelectorAll("[data-remap]").forEach((el) => el.onclick = () => remap(el.dataset.remap));
  $("ptChip").onclick = () => openProductTypePicker();
  $("taskAddBtn").onclick = addTask;
  $("taskInput").addEventListener("keydown", (e) => e.key === "Enter" && addTask());
  wireTasks();
}

// ---------- product type ----------
function openProductTypePicker(afterSet) {
  const types = state.productTypes && state.productTypes.length ? state.productTypes :
    [{ id: "jewellery", label: "Jewellery", icon: "spark" }, { id: "clothes", label: "Clothes", icon: "scissors" },
     { id: "perfumes", label: "Perfumes", icon: "droplet" }, { id: "generic", label: "Other products", icon: "bag" }];
  $("ptGrid").innerHTML = types.map((t) => `
    <button class="pt-card ${t.id === state.productType ? "selected" : ""}" data-pt="${t.id}">
      <div class="pt-ico">${t.icon}</div><div>${esc(t.label)}</div>
    </button>`).join("");
  $("ptModal").hidden = false;
  $("ptGrid").querySelectorAll("[data-pt]").forEach((b) => b.onclick = () => {
    const pt = b.dataset.pt;
    // Apply optimistically and run afterSet() synchronously so the file dialog
    // opens inside this click gesture — browsers block a file input .click()
    // that happens after an awaited call, which is why the first review upload
    // never showed the mapping popup.
    state.productType = pt;
    $("ptModal").hidden = true;
    toast(`Tracking set to ${productLabel(pt)}`);
    const chip = $("ptChip"); if (chip) chip.innerHTML = `🏷️ ${productLabel(pt)}`;
    api("/api/product-type", { method: "POST", json: { product_type: pt } })
      .then((r) => { state.productType = r.product_type; })
      .catch((e) => toast(e.message));
    if (afterSet) afterSet();
  });
}
$("ptClose").onclick = () => { $("ptModal").hidden = true; };

// ---------- tasks ----------
async function addTask() {
  const inp = $("taskInput"); const text = inp.value.trim(); if (!text) return;
  inp.value = "";
  const r = await api("/api/smart/tasks", { method: "POST", json: { action: "add", text } });
  refreshTaskList(r.tasks);
}
function wireTasks() {
  document.querySelectorAll("#taskList [data-task]").forEach((row) => {
    row.querySelector("input").onchange = async (e) => {
      const r = await api("/api/smart/tasks", { method: "POST", json: { action: "toggle", task_id: row.dataset.task, done: e.target.checked } });
      refreshTaskList(r.tasks);
    };
    row.querySelector(".task-del").onclick = async () => {
      const text = (row.querySelector(".t") || {}).textContent || "";
      const r = await api("/api/smart/tasks", { method: "POST", json: { action: "delete", task_id: row.dataset.task } });
      refreshTaskList(r.tasks);
      toastUndo("Task deleted.", async () => {
        const back = await api("/api/smart/tasks", { method: "POST", json: { action: "add", text } });
        refreshTaskList(back.tasks);
      });
    };
  });
}
function refreshTaskList(tasks) {
  if (state.lastState) state.lastState.tasks = tasks;
  const list = $("taskList"); if (!list) return;
  list.innerHTML = tasks.length ? tasks.map((t) => `
      <div class="task-item ${t.done ? "done" : ""}" data-task="${t.id}">
        <input type="checkbox" ${t.done ? "checked" : ""} />
        <span class="t">${esc(t.text)}</span>
        <button class="task-del" title="Delete">${sic("close")}</button>
      </div>`).join("") : `<div class="ap-empty">No tasks yet.</div>`;
  wireTasks();
}

// ---------- approvals ----------
function renderApprovals(insights) {
  const list = $("approvalList");
  const hist = (state.lastState && state.lastState.history) || { approved: [], dismissed: [] };
  const decidedCount = (hist.approved || []).length + (hist.dismissed || []).length;
  if (!insights || !insights.length) {
    list.innerHTML = `<div class="ap-empty">${decidedCount ? "All caught up — nothing pending. Check <b>History</b> for what you've handled." : "No pending insights. Upload data or check back after new activity."}</div>`;
    return;
  }
  list.innerHTML = insights.map((i) => `
    <div class="ins-card" data-ins="${i.id}">
      <div class="ins-title">${i.icon || "•"} <span>${esc(i.title)}</span></div>
      <div class="ins-detail">${esc(i.detail)}</div>
      <div class="ins-actions">
        <button class="btn approve" data-approve="${i.id}">✓ Approve</button>
        <button class="btn reject" data-reject="${i.id}">Dismiss</button>
        <button class="btn ghost" data-details="${i.id}">Details</button>
      </div>
    </div>`).join("");

  list.querySelectorAll("[data-approve]").forEach((b) => b.onclick = () => decide(b.dataset.approve, "approve"));
  list.querySelectorAll("[data-reject]").forEach((b) => b.onclick = () => decide(b.dataset.reject, "disapprove"));
  list.querySelectorAll("[data-details]").forEach((b) => b.onclick = () => openDetails(b.dataset.details));
}

async function decide(id, decision) {
  // Content-post insights have their own detail popup; the panel actions
  // still go through the normal approve/dismiss flow below except the
  // content case which we route to its dedicated poster.
  if (id && id.startsWith("content_") && decision === "approve") return saveContentToDevice(id);
  try {
    const r = await api(`/api/smart/insight/${id}/decision`, { method: "POST", json: { decision } });
    if (state.lastState) {
      state.lastState.insights = r.insights;
      if (r.history) state.lastState.history = r.history;
      if (r.tasks) state.lastState.tasks = r.tasks;
    }
    renderApprovals(r.insights);
    if (r.tasks) refreshTaskList(r.tasks);
    if (decision === "approve") {
      if (r.download && r.download_url) { await download(r.download_url, `${id}.xlsx`); toast("✅ Approved & executed — Excel downloaded. Moved to History."); }
      else toast("✅ Approved — moved to History.");
    } else {
      toast("✕ Dismissed — you can restore it from History.");
    }
    if (!$("historyDrawer").hidden) renderHistory();
  } catch (e) { toast(e.message); }
}

// ---------- History drawer ----------
let _histTab = "approved";
function openHistory() { $("drawerBack").hidden = false; $("historyDrawer").hidden = false; renderHistory(); }
function closeHistory() { $("drawerBack").hidden = true; $("historyDrawer").hidden = true; }

async function renderHistory() {
  const list = $("historyList");
  list.innerHTML = `<div class="ap-empty">Loading…</div>`;
  let h = (state.lastState && state.lastState.history) || null;
  try { h = await api("/api/smart/history"); if (state.lastState) state.lastState.history = h; } catch (e) { toast(e.message); }
  document.querySelectorAll(".hist-tabs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tab === _histTab)));
  const items = (h && h[_histTab]) || [];
  if (!items.length) {
    list.innerHTML = `<div class="ap-empty">Nothing here yet. ${_histTab === "approved" ? "Insights you approve will appear here." : "Dismissed insights will appear here so you can bring them back."}</div>`;
    return;
  }
  list.innerHTML = items.map((it) => `
    <div class="hist-item ${_histTab === "dismissed" ? "dismissed" : ""}" data-hid="${it.id}">
      <div class="h-title">${it.icon || "•"} <span>${esc(it.title)}</span></div>
      ${it.detail ? `<div class="muted tiny" style="margin-top:4px;">${esc(it.detail)}</div>` : ""}
      <div class="h-meta">${_histTab === "approved" ? "✓ Approved" : "✕ Dismissed"} ${it.at ? "· " + esc(relTime(it.at)) : ""}${it.valid ? "" : " · <span style='color:var(--amber);'>data changed since</span>"}</div>
      <div class="h-actions">
        ${_histTab === "approved" && it.has_download && it.valid ? `<button class="btn ghost tiny" data-hdl="${it.id}">⬇ Download again</button>` : ""}
        <button class="btn ghost tiny" data-undo="${it.id}">↺ Move back to pending</button>
      </div>
    </div>`).join("");
  list.querySelectorAll("[data-hdl]").forEach((b) => b.onclick = () => download(`/api/smart/insight/${b.dataset.hdl}/download`, `${b.dataset.hdl}.xlsx`));
  list.querySelectorAll("[data-undo]").forEach((b) => b.onclick = async () => {
    try {
      const r = await api(`/api/smart/insight/${b.dataset.undo}/decision`, { method: "POST", json: { decision: "reset" } });
      if (state.lastState) { state.lastState.insights = r.insights; if (r.history) state.lastState.history = r.history; }
      renderApprovals(r.insights); renderHistory(); toast("Moved back to pending.");
    } catch (e) { toast(e.message); }
  });
}

document.querySelectorAll(".hist-tabs button").forEach((b) => b.onclick = () => { _histTab = b.dataset.tab; renderHistory(); });
$("historyBtn").onclick = openHistory;
$("historyClose").onclick = closeHistory;
$("drawerBack").onclick = closeHistory;
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("historyDrawer").hidden) closeHistory(); });

function openDetails(id) {
  if (id === "reorder") return openModule("supply");
  if (id === "complaints") return openModule("complaints");
  if (id === "reputation") return openModule("review");
  // Win-back details opens the editable table popup (approve is a direct download now).
  if (id === "winback") return openWinbackEditor();
  if (id && id.startsWith("content_")) return openContentEditor(id);
  return openModule("sales");
}

// ---------- upload + mapping ----------
let _mapCtx = null;
let _pendingMode = null;   // "append" when the user clicked "Add records"; null otherwise
function startUpload(kind, forcedMode) {
  _pendingMode = forcedMode || null;
  // Ask what they sell before their first review upload (drives keyword tracking).
  if (kind === "review" && !state.productType) { openProductTypePicker(() => chooseFiles(kind)); return; }
  chooseFiles(kind);
}
function chooseFiles(kind) {
  const old = document.getElementById("hiddenFileInput");
  if (old) old.remove();
  const inp = document.createElement("input");
  inp.type = "file"; inp.multiple = true; inp.id = "hiddenFileInput";
  inp.accept = ".csv,.tsv,.txt,.xlsx,.xls,.json"; inp.style.display = "none";
  document.body.appendChild(inp);
  inp.onchange = () => uploadFiles(kind, inp.files);
  inp.click();
}
async function uploadFiles(kind, files) {
  if (!files || !files.length) return;
  toast("Uploading…", 8000);
  const fd = new FormData();
  [...files].forEach((f) => fd.append("files", f));
  try {
    const d = await api(`/api/smart/upload?kind=${kind}`, { method: "POST", body: fd });
    openMapModal(d);
  } catch (e) { toast(e.message, 6000); }
}

// Reopen the mapping popup for data already saved to the account, so column
// assignments can be changed later without re-uploading the file.
async function remap(kind) {
  _pendingMode = null;
  try {
    const d = await api(`/api/smart/remap?kind=${kind}`);
    openMapModal(d);
  } catch (e) { toast(e.message, 6000); }
}

function openMapModal(d) {
  _mapCtx = d;
  $("mapTitle").textContent = d.kind === "review" ? "Map your Review columns"
    : (d.kind === "supply_sales" ? "Map your previous-sales columns (for Supply)" : "Map your Sales columns");
  $("mapHint").textContent = d.kind === "review"
    ? "Which column holds the review text? (required). Rating and Date are optional but sharpen the analysis."
    : "Tell us which column is which. Date and Amount are required.";
  const labelFor = { date: "Date", amount: "Amount", customer_id: "Customer ID", customer_name: "Customer Name",
    order_id: "Order ID", product: "Product", category: "Category", subcategory: "Sub-category", quantity: "Quantity",
    review: "Review text", rating: "Rating" };
  const opts = (sel) => `<option value="">—</option>` + d.columns.map((c) => `<option ${c === sel ? "selected" : ""}>${esc(c)}</option>`).join("");
  $("mapGrid").innerHTML = d.roles.map((r) => `
    <label>${labelFor[r] || r}${d.required.includes(r) ? " *" : ""}
      <select data-role="${r}">${opts(d.suggested_mapping[r])}</select>
    </label>`).join("");
  $("mapPreview").innerHTML = `<table><thead><tr>${d.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${d.preview.map((row) => `<tr>${row.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  const existing = Number(d.existing_rows || 0);
  const mm = $("mapMode");
  if (mm) {
    if (existing > 0) {
      $("mapModeHint").textContent = `You already have ${fmt(existing)} rows saved. Add these ${fmt(d.rows || 0)} new rows to them, or replace everything?`;
      const want = _pendingMode === "append" ? "append" : "replace";
      mm.querySelectorAll('input[name="mapMode"]').forEach((r) => { r.checked = (r.value === want); });
      mm.hidden = false;
    } else {
      mm.hidden = true;
    }
  }
  $("mapErr").hidden = true;
  $("mapModal").hidden = false;
}
function closeMap() { $("mapModal").hidden = true; _mapCtx = null; _pendingMode = null; _afterUpload = null; const mm = $("mapMode"); if (mm) mm.hidden = true; }
$("mapClose").onclick = closeMap; $("mapCancel").onclick = closeMap;
$("mapConfirm").onclick = async () => {
  if (!_mapCtx) return;
  const mapping = {};
  document.querySelectorAll("#mapGrid select").forEach((s) => mapping[s.dataset.role] = s.value || null);
  for (const req of _mapCtx.required) {
    if (!mapping[req]) { const e = $("mapErr"); e.textContent = `Please map "${req}".`; e.hidden = false; return; }
  }
  let mode = "replace";
  if (!$("mapMode").hidden) {
    const sel = document.querySelector('input[name="mapMode"]:checked');
    mode = sel ? sel.value : "replace";
  }
  try {
    const res = await api("/api/smart/map", { method: "POST", json: { kind: _mapCtx.kind, mapping, mode } });
    closeMap();
    if (res && res.mode === "append") toast(`✅ Added ${fmt(res.added)} rows — ${fmt(res.rows)} total saved`);
    else toast("✅ Data saved to your account");
    if (_afterUpload) { const f = _afterUpload; _afterUpload = null; f(); } else goHome();
  } catch (e) { const el = $("mapErr"); el.textContent = e.message; el.hidden = false; }
};
/* Clearing an uploaded dataset is the one thing here that cannot be undone —
   the rows are gone from the server. So this keeps the confirm, and says
   plainly what will not come back. */
async function clearData(kind) {
  const label = kind === "sales" ? "sales" : "review";
  if (!confirm(`Remove your uploaded ${label} data?\n\n`
    + `This one cannot be undone — you would need to upload the file again. `
    + `Everything built from it (insights, forecasts, segments) goes with it.`)) return;
  try { await api(`/api/smart/clear?kind=${kind}`, { method: "POST" }); toast("Removed"); goHome(); }
  catch (e) { toast(e.message); }
}

// ---------- manual "Add records" (type new rows into the saved schema) ----------
let _addCtx = null;
async function openAddRecords(kind) {
  try {
    const d = await api(`/api/smart/schema?kind=${kind}`);
    _addCtx = d;
    $("addTitle").textContent = kind === "sales" ? "Add sales records" : "Add review records";
    renderAddGrid();
    $("addErr").hidden = true;
    $("addModal").hidden = false;
  } catch (e) { toast(e.message, 6000); }
}
function _addInputCell(col) {
  const type = col.type === "number" ? "number" : (col.type === "date" ? "date" : "text");
  const req = _addCtx.required.includes(col.name) ? " required" : "";
  return `<td><input data-col="${esc(col.name)}" type="${type}" step="any"${req} placeholder="${esc(col.name)}"></td>`;
}
function _addRowHtml() {
  return `<tr>${_addCtx.columns.map(_addInputCell).join("")}<td><button class="btn ghost tiny" data-delrow title="Remove row">${sic("close")}</button></td></tr>`;
}
function renderAddGrid() {
  const head = `<thead><tr>${_addCtx.columns.map((c) => `<th>${esc(c.name)}${_addCtx.required.includes(c.name) ? " *" : ""}</th>`).join("")}<th></th></tr></thead>`;
  $("addGrid").innerHTML = head + `<tbody>${_addRowHtml()}${_addRowHtml()}${_addRowHtml()}</tbody>`;
  bindAddDelRows();
}
function bindAddDelRows() {
  $("addGrid").querySelectorAll("[data-delrow]").forEach((b) => b.onclick = () => {
    if ($("addGrid").querySelectorAll("tbody tr").length > 1) b.closest("tr").remove();
  });
}
function closeAdd() { $("addModal").hidden = true; _addCtx = null; }
if ($("addRowBtn")) $("addRowBtn").onclick = () => {
  $("addGrid").querySelector("tbody").insertAdjacentHTML("beforeend", _addRowHtml());
  bindAddDelRows();
};
if ($("addClose")) $("addClose").onclick = closeAdd;
if ($("addCancel")) $("addCancel").onclick = closeAdd;
if ($("addSave")) $("addSave").onclick = async () => {
  if (!_addCtx) return;
  const rows = [];
  $("addGrid").querySelectorAll("tbody tr").forEach((tr) => {
    const row = {}; let any = false;
    tr.querySelectorAll("input[data-col]").forEach((inp) => {
      const v = inp.value.trim(); row[inp.dataset.col] = v; if (v) any = true;
    });
    if (any) rows.push(row);
  });
  if (!rows.length) { const e = $("addErr"); e.textContent = "Type at least one row."; e.hidden = false; return; }
  try {
    const res = await api("/api/smart/records/add", { method: "POST", json: { kind: _addCtx.kind, rows } });
    closeAdd(); toast(`✅ Added ${fmt(res.added)} record(s) — ${fmt(res.rows)} total`); goHome();
  } catch (e) { const el = $("addErr"); el.textContent = e.message; el.hidden = false; }
};

// ---------- module shell ----------
function moduleShell(name, bodyHtml) {
  setCrumb(name); showRail(false);
  setView(`<div class="page-head"><h2>${esc(name)}</h2><button class="btn ghost sm" id="backHome">← All apps</button></div>${bodyHtml}`);
  $("backHome").onclick = goHome;
}

async function openModule(id) {
  if (id === "sales") return openSales();
  if (id === "subcategory") return openSubcategory();
  if (id === "products") return openProducts();
  if (id === "site") return openSite();
  if (id === "orders") return openOrders();
  if (id === "supply") return openSupply();
  if (id === "review") return openReview();
  if (id === "complaints") return openComplaints();
  if (id === "strategy") return openStrategy();
  if (id === "content") return openContentModule();
  if (id === "instagram") return openInstagramModule();
  if (id === "ads") return openAdsModule();
}

// ---------- MODULE: Product Management ----------
let _productsData = null;

async function openProducts() {
  moduleShell("Product Management", `<div class="ap-empty">Loading products…</div>`);
  try {
    const d = await api("/api/products/state");
    renderProducts(d);
  } catch (e) { moduleShell("Product Management", `<div class="card">${esc(e.message)}</div>`); }
}

function _prodCard(p) {
  const aliasChips = (p.aliases || []).length
    ? p.aliases.map((a) => `<span class="link-chip">${esc(a.alias)}${a.platform ? ` <i class="al-plat">${esc(a.platform)}</i>` : ""}
        <button class="lc-x" data-delalias="${a.id}" title="Unlink">${sic("close")}</button></span>`).join("")
    : `<span class="muted tiny">No platform names linked yet</span>`;
  const meta = [
    p.category ? esc(p.category) : null,
    p.sku ? "SKU " + esc(p.sku) : null,
    p.price != null ? "₹" + fmt(p.price) : null,
    p.unit_cost != null ? "cost ₹" + fmt(p.unit_cost) : null,
  ].filter(Boolean).join(" · ");
  const img = p.image_url || (p.images || [])[0] || "";
  const stock = p.track_stock === false ? "not tracked"
    : (p.stock > 0 ? `${fmt(p.stock)} in stock` : "out of stock");
  return `
    <div class="prod-card ${p.status === "archived" ? "archived" : ""}">
      <div class="prod-head">
        <div class="prod-id">
          <div class="prod-thumb" style="${img ? `background-image:url('${esc(img)}')` : ""}">${img ? "" : "🛍️"}</div>
          <div>
            <b>${esc(p.name)}</b> ${p.status === "archived" ? `<span class="sup-badge moq">archived</span>` : ""}
            <div class="muted tiny">${meta || "—"}</div>
            <div class="muted tiny ${p.track_stock !== false && !(p.stock > 0) ? "stock-out" : ""}">${stock}</div>
          </div>
        </div>
        <div class="sup-actions">
          <button class="btn ghost tiny" data-editprod="${p.id}" title="Edit">✎</button>
          <button class="btn ghost tiny" data-delprod="${p.id}" title="Delete">${sic("close")}</button>
        </div>
      </div>
      <label class="site-toggle" title="Show this product on your own website">
        <input type="checkbox" data-listprod="${p.id}" ${p.listed && p.status !== "archived" ? "checked" : ""} ${p.status === "archived" ? "disabled" : ""} />
        <span class="tsw"></span>
        <span class="tlbl">Listed on my website</span>
      </label>
      <div class="prod-sub">Platform names (aliases)</div>
      <div class="link-chips">${aliasChips}</div>
      <div class="link-add">
        <input placeholder="Platform name e.g. DRF" data-al-name="${p.id}" />
        <input placeholder="Platform (Amazon…)" data-al-plat="${p.id}" style="width:130px" />
        <button class="btn ghost tiny" data-al-add="${p.id}">＋ Link name</button>
      </div>
    </div>`;
}

function renderProducts(d) {
  _productsData = d;
  const prods = d.products || [];
  const unmatched = d.unmatched || [];

  const prodOpts = prods.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");

  const unmatchedBlock = unmatched.length ? `
    <div class="action-card warning" style="margin:10px 0;">
      <div class="do">🔌 ${unmatched.length} platform name${unmatched.length === 1 ? "" : "s"} in your sales not linked to a product</div>
      <div class="why">These names came from your sales platforms but aren't tied to any product yet, so their sales don't roll up. Link each to a product, or create it as a new one.</div>
    </div>
    <div class="link-list">
      ${unmatched.map((name) => `
        <div class="link-row">
          <div class="link-prod"><b>${esc(name)}</b> <span class="muted tiny">(from your sales)</span></div>
          <div class="link-add">
            ${prods.length ? `<select data-um-sel="${esc(name)}">${prodOpts}</select>
              <button class="btn ghost tiny" data-um-link="${esc(name)}">🔗 Link to product</button>` : ""}
            <button class="btn ghost tiny" data-um-new="${esc(name)}">＋ New product</button>
          </div>
        </div>`).join("")}
    </div>` : "";

  const body = `
    <p class="muted">Manage the products you sell and link each to the names it carries on your sales platforms (Amazon, Shopify…). Sales for every linked name roll up to the product across the app — analytics, forecasts and the Supply module all follow it.</p>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 6px;">
      <button class="btn primary sm" id="prodAdd">＋ Add product</button>
    </div>

    <div id="prodForm" hidden></div>

    ${unmatchedBlock}

    <div class="section-title" style="margin-top:14px;">Products <span class="muted tiny">(${prods.length})</span></div>
    ${prods.length ? `<div class="prod-grid">${prods.map(_prodCard).join("")}</div>`
      : `<div class="ap-empty">No products yet. Add one, then link your platform names to it.</div>`}`;

  moduleShell("Product Management", body);
  $("prodAdd").onclick = () => openProductForm(null);
  document.querySelectorAll("[data-editprod]").forEach((b) => b.onclick = () => openProductForm(b.dataset.editprod));
  document.querySelectorAll("[data-delprod]").forEach((b) => b.onclick = () => productDelete(b.dataset.delprod));
  document.querySelectorAll("[data-delalias]").forEach((b) => b.onclick = () => aliasDelete(b.dataset.delalias));
  document.querySelectorAll("[data-listprod]").forEach((cb) => cb.onchange = async () => {
    try {
      renderProducts(await api("/api/products/listed", { method: "POST", json: { id: cb.dataset.listprod, listed: cb.checked } }));
      toast(cb.checked ? "Listed on your website" : "Hidden from your website");
    } catch (e) { toast(e.message); cb.checked = !cb.checked; }
  });
  document.querySelectorAll("[data-al-add]").forEach((b) => b.onclick = () => {
    const pid = b.dataset.alAdd;
    const nm = document.querySelector(`[data-al-name="${CSS.escape(pid)}"]`).value.trim();
    const pl = document.querySelector(`[data-al-plat="${CSS.escape(pid)}"]`).value.trim();
    aliasAdd(pid, nm, pl);
  });
  document.querySelectorAll("[data-um-link]").forEach((b) => b.onclick = () => {
    const name = b.dataset.umLink;
    const pid = document.querySelector(`[data-um-sel="${CSS.escape(name)}"]`).value;
    aliasAdd(pid, name, "");
  });
  document.querySelectorAll("[data-um-new]").forEach((b) => b.onclick = () => openProductForm(null, b.dataset.umNew));
}

// ---- shared image picker: uploads to /api/site/image and returns the URL ----
function pickImage(onUrl, multiple, accept) {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = accept || "image/*"; inp.multiple = !!multiple;
  inp.onchange = async () => {
    const files = Array.from(inp.files || []);
    if (!files.length) return;
    toast(`Uploading ${files.length} file${files.length === 1 ? "" : "s"}…`);
    let warned = "", failed = 0;
    for (const f of files) {
      const fd = new FormData(); fd.append("files", f);
      try {
        const r = await api("/api/site/image", { method: "POST", body: fd });
        onUrl(r.image_url);
        if (r.warning) warned = r.warning;
      } catch (e) { failed++; toast(e.message, 6000); }
    }
    if (failed) return;
    // Say plainly when the durable copy did not happen, rather than showing a
    // thumbnail that will be a broken slot after the next deploy.
    toast(warned || (_media && !_media.durable
      ? "Uploaded — but this server does not keep uploads. See the warning above."
      : "Uploaded and stored."), warned || (_media && !_media.durable) ? 7000 : 3200);
  };
  inp.click();
}

// A single-image field: thumbnail + upload + paste-a-URL, used for the product
// photo, the logo, the hero and the story image.
const isVid = (u) => /\.(mp4|webm|mov|m4v)(\?|$)/i.test(String(u || ""));

/** A single media slot. `video: true` also accepts MP4/WEBM — used for the
 *  hero, the lookbook and product clips, where a few seconds of motion does
 *  more for a storefront than any amount of styling. */
function imageField(id, url, label, hint, video) {
  const vid = isVid(url);
  // The path is not the picture. Showing `/generated_images/hero.jpg` as an
  // editable string invites a seller to edit it and break their own homepage,
  // and tells them nothing about what is actually there. So: the thumbnail is
  // the control, the filename is a caption, and the raw URL is one click away
  // for the rare seller who genuinely wants to paste one.
  return `
    <div class="img-field${url ? " has-media" : ""}" data-imgfield="${id}">
      <div class="if-preview ${vid ? "is-vid" : ""}" id="${id}Prev"
style="${url && !vid ? `background-image:url('${esc(url)}')` : ""}">${
        url ? (vid ? `<video src="${esc(url)}" muted loop autoplay playsinline></video>` : "")
            : `<span class="if-ph">${sic("image")}</span>`}</div>
      <div class="if-body">
        <label class="if-label">${label}${hint ? ` <span class="muted tiny">${hint}</span>` : ""}</label>
        <div class="if-name" id="${id}Name">${url ? esc(fileLabel(url)) : "Nothing here yet"}</div>
        <div class="if-actions">
          <button type="button" class="btn ghost tiny" data-imgup="${id}">
            ${sic("image")}${url ? "Replace" : "Upload"}${video ? " image" : ""}</button>
          ${video ? `<button type="button" class="btn ghost tiny" data-vidup="${id}">
            ${sic("spark")}${url && vid ? "Replace clip" : "Upload video"}</button>` : ""}
          <button type="button" class="btn ghost tiny" data-imgclear="${id}"${url ? "" : " disabled"}>Remove</button>
          <button type="button" class="btn ghost tiny if-url-toggle" data-imgurl="${id}">Use a URL</button>
        </div>
        <input id="${id}" class="if-url" value="${esc(url || "")}" hidden
               placeholder="${video ? "Paste an image or clip URL" : "Paste an image URL"}" />
      </div>
    </div>`;
}

/** The last meaningful part of a path — what a person would call the file. */
function fileLabel(url) {
  const clean = String(url || "").split(/[?#]/)[0];
  const name = clean.split("/").filter(Boolean).pop() || clean;
  return name.length > 42 ? name.slice(0, 20) + "…" + name.slice(-18) : name;
}

function paintMediaPreview(id, url) {
  const pv = $(id + "Prev");
  if (!pv) return;
  const nm = $(id + "Name");
  const field = pv.closest("[data-imgfield]");
  if (field) field.classList.toggle("has-media", !!url);
  const rm = field && field.querySelector("[data-imgclear]");
  if (rm) rm.disabled = !url;
  if (nm) nm.textContent = url ? fileLabel(url) : "Nothing here yet";
  pv.classList.toggle("is-vid", isVid(url));
  if (!url) { pv.style.backgroundImage = ""; pv.innerHTML = `<span class="if-ph">${sic("image")}</span>`; return; }
  if (isVid(url)) { pv.style.backgroundImage = ""; pv.innerHTML = `<video src="${esc(url)}" muted loop autoplay playsinline></video>`; }
  else { pv.innerHTML = ""; pv.style.backgroundImage = `url('${url}')`; }
}

function wireImageFields(scope) {
  const set = (id, url) => {
    $(id).value = url; paintMediaPreview(id, url);
    $(id).dispatchEvent(new Event("change"));
  };
  (scope || document).querySelectorAll("[data-imgup]").forEach((b) => b.onclick = () =>
    pickImage((url) => set(b.dataset.imgup, url), false, "image/*"));
  (scope || document).querySelectorAll("[data-vidup]").forEach((b) => b.onclick = () =>
    pickImage((url) => set(b.dataset.vidup, url), false, "video/mp4,video/webm,video/quicktime"));
  (scope || document).querySelectorAll("[data-imgclear]").forEach((b) => b.onclick = () => set(b.dataset.imgclear, ""));
  (scope || document).querySelectorAll("[data-imgurl]").forEach((b) => b.onclick = () => {
    const inp = $(b.dataset.imgurl);
    if (!inp) return;
    inp.hidden = !inp.hidden;
    b.classList.toggle("on", !inp.hidden);
    if (!inp.hidden) inp.focus();
  });
  // clicking the thumbnail is the obvious thing to do, so make it work
  (scope || document).querySelectorAll("[data-imgfield] .if-preview").forEach((pv) => {
    const f = pv.closest("[data-imgfield]");
    const id = f && f.getAttribute("data-imgfield");
    if (id) pv.onclick = () => pickImage((url) => set(id, url), false, "image/*");
  });
  (scope || document).querySelectorAll("[data-imgfield] input").forEach((inp) => inp.onblur = () =>
    paintMediaPreview(inp.id, inp.value.trim()));
}

// ---- product form: one field per row, storefront fields included ----------
let _pfGallery = [];

function openProductForm(id, prefillName) {
  const p = $("prodForm");
  const it = id ? (_productsData.products || []).find((x) => x.id === id) : null;
  p.hidden = false;
  const v = (x, dflt = "") => (it && it[x] != null ? it[x] : dflt);
  const num = (x) => (it && it[x] != null && it[x] !== "" ? it[x] : "");
  _pfGallery = (it && it.images ? it.images.slice() : []);
  const listed = it ? it.listed !== false : true;

  p.innerHTML = `
    <div class="card sup-form form-v">
      <h4 style="margin:0 0 4px;">${id ? "Edit product" : "Add product"}</h4>
      <p class="muted tiny" style="margin:0 0 14px;">Everything below the divider is what shoppers see on your own website.</p>

      <div class="sup-form-grid">
        <label>Product name<input id="pfName" value="${it ? esc(it.name) : esc(prefillName || "")}" placeholder="e.g. Midnight Oud 50ml" /></label>
        <label>Category <span class="muted tiny">(groups it on your site)</span><input id="pfCat" value="${esc(v("category"))}" placeholder="Fragrance" /></label>
        <label>Your SKU <span class="muted tiny">(internal, never shown)</span><input id="pfSku" value="${esc(v("sku"))}" /></label>
        <label>Selling price ₹<input id="pfPrice" type="number" min="0" step="any" value="${num("price")}" placeholder="1499" /></label>
        <label>MRP / strike-through price ₹ <span class="muted tiny">(optional — shows a discount badge)</span><input id="pfMrp" type="number" min="0" step="any" value="${num("mrp")}" placeholder="1999" /></label>
        <label>Unit cost ₹ <span class="muted tiny">(COGS, never shown)</span><input id="pfCost" type="number" min="0" step="any" value="${num("unit_cost")}" /></label>
        <label>Status<select id="pfStatus">
          <option value="active" ${v("status", "active") === "active" ? "selected" : ""}>Active</option>
          <option value="archived" ${v("status") === "archived" ? "selected" : ""}>Archived</option>
        </select></label>
      </div>

      <div class="sup-sub">On my website</div>
      ${mediaWarning()}

      <label class="site-toggle big" title="Show this product on your website">
        <input type="checkbox" id="pfListed" ${listed ? "checked" : ""} />
        <span class="tsw"></span>
        <span class="tlbl">List this product on my website<span class="muted tiny"> — on by default</span></span>
      </label>

      ${v("image_url") ? "" : `<div class="nudge">${sic("image")}<div><b>Add a photo</b>
        A product without one is the single biggest reason a storefront looks unfinished.</div></div>`}
      <div class="sup-form-grid">
        ${imageField("pfImg", v("image_url"), "Main photo", "square images look best")}
        ${imageField("pfVid", v("video_url"), "Product clip", "plays when a shopper hovers the card", true)}
        <label>Description<textarea id="pfDesc" rows="4" placeholder="What it is, what it's made of, why someone should buy it.">${esc(v("description"))}</textarea></label>
        <label>Key points <span class="muted tiny">(one per line — shown as ticks on the product page)</span>
          <textarea id="pfHl" rows="3" placeholder="100% cotton&#10;Ships in 24 hours&#10;Free returns">${esc((v("highlights", []) || []).join("\n"))}</textarea></label>
        <label>Sold by <span class="muted tiny">(piece / kg / box — optional)</span><input id="pfUnit" value="${esc(v("unit_label"))}" placeholder="piece" /></label>
      </div>

      <div class="sup-sub">Sizes &amp; colours</div>
      <p class="muted tiny" style="margin:-6px 0 10px;">A shirt in three sizes and two colours is
      six things to count, not one. Name the options and each combination becomes a real record
      with its own stock, its own SKU and — if you want — its own price.</p>
      <div id="pfVarBox"></div>

      <div class="sup-sub">Stock</div>
      <div class="sup-form-grid">
        <label class="inline-check"><input type="checkbox" id="pfTrack" ${v("track_stock", true) === false ? "" : "checked"} /> Track stock for this product <span class="muted tiny">— sells out at zero, and site orders deduct from it</span></label>
        <label id="pfStockRow">Units available<input id="pfStock" type="number" min="0" step="1" value="${it && it.stock != null ? it.stock : 0}" /></label>
      </div>

      <div class="sup-sub">Extra photos</div>
      <div class="gal-wrap" id="pfGal"></div>

      <div class="modal-actions">
        <button class="btn ghost" id="pfCancel">Cancel</button>
        <button class="btn primary" id="pfSave">${id ? "Save changes" : "Add product"}</button>
      </div>
      <div class="err" id="pfErr" hidden></div>
    </div>`;

  p.scrollIntoView({ behavior: "smooth", block: "nearest" });
  wireImageFields(p);
  renderGallery();
  _pfAxes = JSON.parse(JSON.stringify((it && it.options) || []));
  _pfVariants = JSON.parse(JSON.stringify((it && it.variants) || []));
  renderVariants();

  $("pfCancel").onclick = () => { p.hidden = true; p.innerHTML = ""; };
  const numOrNull = (x) => ($(x).value === "" ? null : parseFloat($(x).value));
  $("pfSave").onclick = async () => {
    const payload = {
      id: id || null,
      name: $("pfName").value.trim(),
      category: $("pfCat").value.trim(),
      sku: $("pfSku").value.trim(),
      price: numOrNull("pfPrice"),
      mrp: numOrNull("pfMrp"),
      unit_cost: numOrNull("pfCost"),
      status: $("pfStatus").value,
      listed: $("pfListed").checked,
      image_url: $("pfImg").value.trim(),
      video_url: $("pfVid").value.trim(),
      images: _pfGallery,
      description: $("pfDesc").value.trim(),
      highlights: $("pfHl").value.split("\n").map((x) => x.trim()).filter(Boolean),
      unit_label: $("pfUnit").value.trim(),
      track_stock: $("pfTrack").checked,
      stock: parseInt($("pfStock").value || "0", 10) || 0,
      options: _pfAxes,
      variants: readVariantInputs(),
    };
    if (!payload.name) { const e = $("pfErr"); e.textContent = "Product name is required."; e.hidden = false; return; }
    try { renderProducts(await api("/api/products/item", { method: "POST", json: payload })); toast("Saved"); }
    catch (e) { const el = $("pfErr"); el.textContent = e.message; el.hidden = false; }
  };
}

/* ---------------------------------------------------------- variants ----
   Two axes at most, because "Size" and "Colour" is what apparel actually
   needs and a third axis produces a matrix nobody can fill in. Editing the
   axes rebuilds the grid, carrying over every cell the seller already filled
   — adding XL to a shirt must not wipe the twelve rows underneath. */
let _pfAxes = [];
let _pfVariants = [];

const _vkey = (opts, axes) => axes.map((a) =>
  `${String(a.name).trim().toLowerCase()}=${String(opts[a.name] || "").trim().toLowerCase()}`).join("|");

function buildMatrix() {
  if (!_pfAxes.length) return [];
  const prev = {};
  _pfVariants.forEach((v) => { prev[v.key || _vkey(v.options || {}, _pfAxes)] = v; });
  const rows = [];
  const walk = (i, acc) => {
    if (rows.length >= 120) return;
    if (i === _pfAxes.length) {
      const key = _vkey(acc, _pfAxes);
      const was = prev[key] || {};
      rows.push({
        id: was.id || "", key,
        options: { ...acc },
        label: _pfAxes.map((a) => acc[a.name]).filter(Boolean).join(" / "),
        sku: was.sku || "", price: was.price == null ? "" : was.price,
        mrp: was.mrp == null ? "" : was.mrp,
        stock: was.stock == null ? 0 : was.stock,
        image_url: was.image_url || "",
      });
      return;
    }
    _pfAxes[i].values.forEach((val) => walk(i + 1, { ...acc, [_pfAxes[i].name]: val }));
  };
  walk(0, {});
  return rows;
}

function renderVariants() {
  const box = $("pfVarBox");
  if (!box) return;
  const axisRow = (ax, i) => `
    <div class="vx-axis">
      <input class="vx-name" data-axname="${i}" value="${esc(ax.name)}" placeholder="Size" />
      <input class="vx-vals" data-axvals="${i}" value="${esc((ax.values || []).join(", "))}"
             placeholder="S, M, L, XL" />
      <button type="button" class="btn ghost tiny" data-axrm="${i}" title="Remove this option">
        ${sic("close")}</button>
    </div>`;

  if (!_pfAxes.length) {
    box.innerHTML = `<div class="vx-empty">
      <span>No options — this product is one thing with one stock count.</span>
      <button type="button" class="btn ghost sm" id="vxAdd">${sic("plus")}Add sizes or colours</button>
    </div>`;
    $("vxAdd").onclick = () => {
      _pfAxes = [{ name: "Size", values: ["S", "M", "L"] }];
      _pfVariants = buildMatrix();
      renderVariants();
    };
    const sr = $("pfStockRow"); if (sr) sr.hidden = false;
    return;
  }

  _pfVariants = buildMatrix();
  const total = _pfVariants.reduce((a, v) => a + (parseInt(v.stock, 10) || 0), 0);
  box.innerHTML = `
    <div class="vx">
      ${_pfAxes.map(axisRow).join("")}
      ${_pfAxes.length < 2
        ? `<button type="button" class="btn ghost tiny" id="vxAdd2">${sic("plus")}Add a second option</button>`
        : ""}
    </div>
    <div class="vx-grid-wrap">
      <table class="vx-grid">
        <thead><tr>
          <th>Combination</th><th>SKU</th><th>Price ₹<span class="muted tiny"> (blank = product price)</span></th>
          <th>Stock</th>
        </tr></thead>
        <tbody>${_pfVariants.map((v, i) => `
          <tr>
            <td><b>${esc(v.label)}</b></td>
            <td><input data-vsku="${i}" value="${esc(v.sku)}" placeholder="—" /></td>
            <td><input data-vprice="${i}" type="number" min="0" step="any" value="${v.price === "" ? "" : esc(String(v.price))}" placeholder="—" /></td>
            <td><input data-vstock="${i}" type="number" min="0" step="1" value="${parseInt(v.stock, 10) || 0}" /></td>
          </tr>`).join("")}</tbody>
      </table>
    </div>
    <p class="muted tiny" style="margin:8px 0 0;">${_pfVariants.length} combination${_pfVariants.length === 1 ? "" : "s"}
      · ${total} unit${total === 1 ? "" : "s"} in total. The product's own stock count is this total,
      so everything else in the app keeps reading a correct number.</p>`;

  const sr = $("pfStockRow"); if (sr) sr.hidden = true;
  const sf = $("pfStock"); if (sf) sf.value = total;

  box.querySelectorAll("[data-axname]").forEach((inp) => inp.onchange = () => {
    _pfAxes[+inp.dataset.axname].name = inp.value.trim() || "Option";
    renderVariants();
  });
  box.querySelectorAll("[data-axvals]").forEach((inp) => inp.onchange = () => {
    const seen = new Set();
    _pfAxes[+inp.dataset.axvals].values = inp.value.split(",")
      .map((x) => x.trim()).filter((x) => {
        const k = x.toLowerCase();
        if (!x || seen.has(k)) return false;
        seen.add(k); return true;
      }).slice(0, 24);
    if (!_pfAxes[+inp.dataset.axvals].values.length) _pfAxes.splice(+inp.dataset.axvals, 1);
    renderVariants();
  });
  box.querySelectorAll("[data-axrm]").forEach((b) => b.onclick = () => {
    _pfAxes.splice(+b.dataset.axrm, 1);
    renderVariants();
  });
  const add2 = $("vxAdd2");
  if (add2) add2.onclick = () => {
    _pfAxes.push({ name: "Colour", values: ["Black", "White"] });
    renderVariants();
  };
  // keep typed values without a full repaint, so the seller can tab across the grid
  box.querySelectorAll("[data-vsku],[data-vprice],[data-vstock]").forEach((inp) =>
    inp.oninput = () => {
      const row = readVariantInputs();
      _pfVariants = row;
      const t = row.reduce((a, v) => a + (parseInt(v.stock, 10) || 0), 0);
      const sf2 = $("pfStock"); if (sf2) sf2.value = t;
    });
}

function readVariantInputs() {
  if (!_pfAxes.length) return [];
  const box = $("pfVarBox");
  if (!box) return _pfVariants;
  return _pfVariants.map((v, i) => {
    const g = (sel) => (box.querySelector(`[data-${sel}="${i}"]`) || {}).value;
    const price = g("vprice");
    return {
      ...v,
      sku: (g("vsku") || "").trim(),
      price: price === "" || price == null ? null : parseFloat(price),
      stock: parseInt(g("vstock") || "0", 10) || 0,
    };
  });
}

function renderGallery() {
  const g = $("pfGal");
  if (!g) return;
  g.innerHTML = _pfGallery.map((u, i) => `
      <div class="gal-item" style="background-image:url('${esc(u)}')">
        <button class="gal-x" data-galrm="${i}" title="Remove">${sic("close")}</button>
      </div>`).join("") +
    `<button class="gal-add" id="galAdd">＋<span>Add photos</span></button>`;
  g.querySelectorAll("[data-galrm]").forEach((b) => b.onclick = () => {
    _pfGallery.splice(parseInt(b.dataset.galrm, 10), 1); renderGallery();
  });
  $("galAdd").onclick = () => pickImage((url) => { _pfGallery.push(url); renderGallery(); }, true);
}

/* Delete, then offer it back. A confirm() dialog asks the seller to be certain
   before they can see what happens; an undo lets them find out safely, which
   is the difference between software people poke at and software they are
   afraid of. The product is re-created from the copy we held, aliases and all. */
async function productDelete(id) {
  const it = (_productsData.products || []).find((x) => x.id === id);
  if (!it) return;
  const snapshot = JSON.parse(JSON.stringify(it));
  try {
    renderProducts(await api("/api/products/item/delete", { method: "POST", json: { id } }));
  } catch (e) { toast(e.message); return; }
  toastUndo(`Deleted “${it.name}”.`, async () => {
    await api("/api/products/item", { method: "POST", json: snapshot });
    for (const a of (snapshot.aliases || [])) {
      try {
        await api("/api/products/alias", { method: "POST",
          json: { product_id: snapshot.id, alias: a.alias, platform: a.platform } });
      } catch (e) { /* one lost link should not block the rest */ }
    }
    renderProducts(await api("/api/products/state"));
  });
}

async function aliasAdd(product_id, alias, platform) {
  if (!alias) { toast("Enter the platform name to link."); return; }
  try { renderProducts(await api("/api/products/alias", { method: "POST", json: { product_id, alias, platform } })); toast("Linked"); }
  catch (e) { toast(e.message); }
}

async function aliasDelete(id) {
  let snap = null;
  (_productsData.products || []).forEach((p) =>
    (p.aliases || []).forEach((a) => { if (a.id === id) snap = { ...a, product_id: p.id }; }));
  try { renderProducts(await api("/api/products/alias/delete", { method: "POST", json: { id } })); }
  catch (e) { toast(e.message); return; }
  if (!snap) { toast("Unlinked"); return; }
  toastUndo(`Unlinked “${snap.alias}”.`, async () => {
    await api("/api/products/alias", { method: "POST",
      json: { product_id: snap.product_id, alias: snap.alias, platform: snap.platform } });
    renderProducts(await api("/api/products/state"));
  });
}

// ---------- MODULE: Supply Management ----------
let _supplyData = null;
let _afterUpload = null;   // set to a fn to run after the next Sales upload+map, instead of goHome
const _rupee = (v) => (v == null || v === "" ? "—" : "₹" + fmt(v));
const _eff = (v, auto) => (auto ? fmt(v) + "<span class=\"auto-tag\">auto</span>" : fmt(v));

async function openSupply() {
  moduleShell("Supply Management", `<div class="ap-empty">Loading inventory…</div>`);
  try {
    const d = await api("/api/supply/state");
    renderSupply(d);
  } catch (e) { moduleShell("Supply Management", `<div class="card">${esc(e.message)}</div>`); }
}

function _supBadge(it) {
  return it.below_reorder
    ? `<span class="sup-badge low">● Reorder</span>`
    : `<span class="sup-badge ok">● OK</span>`;
}

function _sugCard(it) {
  const chips = [
    ["Stock", fmt(it.current_stock) + " " + esc(it.unit_label || "")],
    ["Avg/day", it.avg_daily_sales ?? 0],
    ["Reorder pt", fmt(it.reorder_point)],
    ["EOQ", it.eoq == null ? "—" : fmt(it.eoq)],
    ["MOQ", fmt(it.moq)],
    ["Suggested", `<b>${fmt(it.suggested_qty)}</b>`],
    ["Est. cost", it.est_line_cost == null ? "—" : _rupee(it.est_line_cost)],
  ].map(([k, v]) => `<span class="sug-chip"><i>${k}</i>${v}</span>`).join("");
  const sup = it.supplier_name
    ? `${esc(it.supplier_name)}${it.supplier_phone ? " · " + esc(it.supplier_phone) : ""}${it.supplier_email ? " · " + esc(it.supplier_email) : ""}`
    : `No supplier linked`;
  return `
    <div class="sug-card">
      <div class="sug-head">
        <div><b>${esc(it.name)}</b>${it.moq_applied ? ` <span class="sup-badge moq">MOQ applied</span>` : ""}
          <div class="muted tiny">${sup}</div></div>
        <button class="btn approve sm" data-openpo="${it.id}">📄 Open → PO (PDF)</button>
      </div>
      <div class="sug-reason">${esc(it.reason || "")}</div>
      <div class="sug-metrics">${chips}</div>
    </div>`;
}

function renderSupply(d) {
  _supplyData = d;
  const items = d.inventory || [];
  const pos = d.purchase_orders || [];
  const meta = d.meta || {};
  const belowN = d.n_below || 0;
  const suggestions = d.suggestions || [];
  const waste = d.waste || [];

  const salesNote = meta.has_sales
    ? `These calculations run only on the previous-sales history you upload here for Supply (${meta.days_span} day${meta.days_span === 1 ? "" : "s"} loaded) — a separate set from your main Sales Data. Daily usage → product links → reorder point (daily usage × lead time + safety stock); suggested order = EOQ, raised to the supplier MOQ.`
    : `No previous-sales history uploaded for Supply yet. Use “Upload previous sales” to add and map your past sales — the supply-chain math (usage, reorder point, EOQ, safety stock) runs only on that, separate from your main Sales Data. You can still track stock, suppliers, EOQ inputs and MOQ manually meanwhile.`;

  const sugSection = suggestions.length ? `
    <div class="section-title" style="margin-top:8px;">🔔 Restock suggestions <span class="muted tiny">(${suggestions.length}, one per item)</span></div>
    <div class="sug-grid">${suggestions.map(_sugCard).join("")}</div>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px;">
      <button class="btn approve sm" id="supGenPo">📦 Generate PO for all ${belowN} item${belowN === 1 ? "" : "s"}</button>
    </div>` : `
    <div class="action-card ok" style="margin:10px 0;"><div class="do">✓ Everything is above its reorder point</div><div class="why">No restock needed right now. Add items or links, and suggestions will appear here per item.</div></div>`;

  const rows = items.length ? items.map((it) => `
      <tr class="${it.below_reorder ? "sup-below" : ""}">
        <td>${esc(it.name)}${it.category ? `<div class="muted tiny">${esc(it.category)}</div>` : ""}</td>
        <td>${it.supplier_name ? esc(it.supplier_name) : "<span class='muted tiny'>—</span>"}
            ${it.supplier_phone || it.supplier_email ? `<div class="muted tiny">${esc(it.supplier_phone || "")}${it.supplier_phone && it.supplier_email ? " · " : ""}${esc(it.supplier_email || "")}</div>` : ""}</td>
        <td class="num">${fmt(it.current_stock)} <span class="muted tiny">${esc(it.unit_label || "")}</span></td>
        <td class="num">${it.avg_daily_sales ?? 0}</td>
        <td class="num">${_eff(it.effective_lead_time_days, it.lead_is_auto)}</td>
        <td class="num">${_eff(it.effective_safety_stock, it.safety_is_auto)}</td>
        <td class="num">${fmt(it.moq)}</td>
        <td class="num">${it.unit_cost == null ? "—" : _rupee(it.unit_cost)}</td>
        <td class="num">${fmt(it.reorder_point)}</td>
        <td>${_supBadge(it)}</td>
        <td class="sup-actions">
          ${it.suggestions_available ? `<button class="btn ghost tiny" data-apply="${it.id}" title="Apply the values suggested from your sales">✨</button>` : ""}
          <button class="btn ghost tiny" data-edit="${it.id}" title="Edit">✎</button>
          <button class="btn ghost tiny" data-waste="${it.id}" title="Record waste">🗑️</button>
          <button class="btn ghost tiny" data-del="${it.id}" title="Remove item">${sic("close")}</button>
        </td>
      </tr>`).join("")
    : `<tr><td colspan="11" class="ap-empty">No inventory yet. Add an item, or pull products from your sales.</td></tr>`;

  const poRows = pos.length ? pos.slice().reverse().map((p) => `
      <tr>
        <td>${esc(p.po_number)}</td>
        <td>${esc(String(p.created_at || "").slice(0, 16).replace("T", " "))}</td>
        <td class="num">${fmt(p.n_items)}</td>
        <td class="num">${fmt(p.total_qty)}</td>
        <td class="num">${p.total_amount == null ? "—" : _rupee(p.total_amount)}</td>
        <td class="sup-actions">
          <button class="btn approve tiny" data-popdf="${esc(p.po_number)}">📄 Open PDF</button>
          <button class="btn ghost tiny" data-poxls="${esc(p.po_number)}">⬇ Excel</button>
        </td>
      </tr>`).join("")
    : `<tr><td colspan="6" class="ap-empty">No purchase orders yet. Open a suggestion to generate one.</td></tr>`;

  const wasteRows = waste.length ? waste.slice(0, 10).map((w) => `
      <tr>
        <td>${esc(String(w.ts || "").slice(0, 16).replace("T", " "))}</td>
        <td>${esc(w.item_name || "")}</td>
        <td class="num">${fmt(w.qty)}</td>
        <td>${esc(w.reason || "")}</td>
      </tr>`).join("") : "";

  const body = `
    <p class="muted">${esc(salesNote)}</p>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 6px;">
      <button class="btn primary sm" id="supAdd">＋ Add item</button>
      <button class="btn ghost sm" id="supLoadSales" title="Upload &amp; map the past sales history used ONLY for these supply-chain calculations (separate from your main Sales Data)">${sic("receipt")}Upload previous sales</button>
      <button class="btn ghost sm" id="supImport">⤵ Pull products from sales</button>
      <button class="btn ghost sm" id="supLinks">🔗 Product links</button>
      <button class="btn ghost sm" id="supWaste">🗑️ Record waste</button>
    </div>

    <div id="supForm" hidden></div>
    <div id="supPanel" hidden></div>

    ${sugSection}

    <div class="section-title" style="margin-top:18px;">Inventory</div>
    <div class="table-scroll">
      <table class="sup-table">
        <thead><tr>
          <th>Item</th><th>Supplier</th><th class="num">Stock</th><th class="num">Avg/day</th>
          <th class="num">Lead (d)</th><th class="num">Safety</th><th class="num">MOQ</th>
          <th class="num">Unit cost</th><th class="num">Reorder pt</th><th>Status</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>

    <div class="section-title" style="margin-top:20px;">Purchase orders</div>
    <div class="table-scroll">
      <table class="sup-table">
        <thead><tr><th>PO #</th><th>Created</th><th class="num">Items</th><th class="num">Qty</th><th class="num">Amount</th><th></th></tr></thead>
        <tbody>${poRows}</tbody>
      </table>
    </div>

    ${wasteRows ? `
    <div class="section-title" style="margin-top:20px;">Recent waste</div>
    <div class="table-scroll">
      <table class="sup-table">
        <thead><tr><th>When</th><th>Item</th><th class="num">Qty</th><th>Reason</th></tr></thead>
        <tbody>${wasteRows}</tbody>
      </table>
    </div>` : ""}`;

  moduleShell("Supply Management", body);
  $("supAdd").onclick = () => openSupplyForm(null);
  $("supImport").onclick = supplyImport;
  $("supLoadSales").onclick = () => { _afterUpload = () => openSupply(); startUpload("supply_sales", "append"); };
  $("supLinks").onclick = openLinksPanel;
  $("supWaste").onclick = () => openWastePanel(null);
  if ($("supGenPo")) $("supGenPo").onclick = supplyGeneratePo;
  document.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => openSupplyForm(b.dataset.edit));
  document.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => supplyDelete(b.dataset.del));
  document.querySelectorAll("[data-waste]").forEach((b) => b.onclick = () => openWastePanel(b.dataset.waste));
  document.querySelectorAll("[data-apply]").forEach((b) => b.onclick = () => supplyApplySuggested(b.dataset.apply));
  document.querySelectorAll("[data-openpo]").forEach((b) => b.onclick = () => supplyOpenPo([b.dataset.openpo]));
  document.querySelectorAll("[data-popdf]").forEach((b) => b.onclick = () => download(`/api/supply/po/${encodeURIComponent(b.dataset.popdf)}/pdf`, `${b.dataset.popdf}.pdf`));
  document.querySelectorAll("[data-poxls]").forEach((b) => b.onclick = () => download(`/api/supply/po/${encodeURIComponent(b.dataset.poxls)}/download`, `${b.dataset.poxls}.xlsx`));
}

function _supAfter(d) {
  renderSupply(d);
  if (state.lastState) state.lastState.insights = d.insights;
  if (d.insights) renderApprovals(d.insights);
}

function _closePanels() {
  ["supForm", "supPanel"].forEach((id) => { const e = $(id); if (e) { e.hidden = true; e.innerHTML = ""; } });
}

// ---- Add / edit item ----
function openSupplyForm(id) {
  _closePanels();
  const it = id ? (_supplyData.inventory || []).find((x) => x.id === id) : null;
  const f = $("supForm");
  f.hidden = false;
  const v = (x, dflt = "") => (it && it[x] != null ? it[x] : dflt);
  f.innerHTML = `
    <div class="card sup-form">
      <h4 style="margin:0 0 4px;">${id ? "Edit item" : "Add item"}</h4>
      <p class="muted tiny" style="margin:0 0 10px;">Leave lead time, safety stock and the EOQ costs blank &mdash; we suggest them from your sales once there is enough history, then you can apply and edit them.</p>
      <div class="sup-form-grid">
        <label>Item name<input id="sfName" value="${esc(v("name"))}" placeholder="e.g. Paper cup 250ml" /></label>
        <label>Category <span class="muted tiny">(optional)</span><input id="sfCat" value="${esc(v("category"))}" placeholder="Packaging" /></label>
        <label>Unit label<input id="sfUnit" value="${esc(v("unit_label", "unit"))}" placeholder="pcs / kg / box" /></label>
        <label>Current stock<input id="sfStock" type="number" min="0" step="any" value="${v("current_stock", 0)}" /></label>
        <label>Lead time (days) <span class="muted tiny">(blank = auto)</span><input id="sfLead" type="number" min="0" step="any" placeholder="auto (7)" value="${it && it.lead_time_days > 0 ? it.lead_time_days : ''}" /></label>
        <label>Safety stock <span class="muted tiny">(blank = auto from sales)</span><input id="sfSafe" type="number" min="0" step="any" placeholder="auto" value="${it && it.safety_stock > 0 ? it.safety_stock : ''}" /></label>
        <label>MOQ <span class="muted tiny">(min order qty)</span><input id="sfMoq" type="number" min="0" step="any" value="${v("moq", 0)}" /></label>
        <label>Ordering cost ₹ <span class="muted tiny">(per order · blank = auto)</span><input id="sfOrder" type="number" min="0" step="any" value="${it && it.ordering_cost != null ? it.ordering_cost : ""}" /></label>
        <label>Holding cost ₹ <span class="muted tiny">(/unit/yr · blank = auto)</span><input id="sfHold" type="number" min="0" step="any" value="${it && it.holding_cost != null ? it.holding_cost : ""}" /></label>
        <label>Unit cost ₹<input id="sfCost" type="number" min="0" step="any" value="${it && it.unit_cost != null ? it.unit_cost : ""}" /></label>
        <label>Reorder qty <span class="muted tiny">(blank = EOQ auto)</span><input id="sfQty" type="number" min="0" step="any" value="${it && it.reorder_qty != null ? it.reorder_qty : ""}" /></label>
      </div>
      <div class="sup-sub">Supplier</div>
      <div class="sup-form-grid">
        <label>Supplier name<input id="sfSupN" value="${esc(v("supplier_name"))}" /></label>
        <label>Contact number<input id="sfSupP" value="${esc(v("supplier_phone"))}" placeholder="+91 …" /></label>
        <label>Email<input id="sfSupE" type="email" value="${esc(v("supplier_email"))}" placeholder="sales@supplier.com" /></label>
      </div>
      <div class="modal-actions">
        <button class="btn ghost" id="sfCancel">Cancel</button>
        <button class="btn primary" id="sfSave">${id ? "Save changes" : "Add item"}</button>
      </div>
      <div class="err" id="sfErr" hidden></div>
    </div>`;
  f.scrollIntoView({ behavior: "smooth", block: "nearest" });
  $("sfCancel").onclick = () => { f.hidden = true; f.innerHTML = ""; };
  const numOrNull = (id) => ($(id).value === "" ? null : parseFloat($(id).value));
  $("sfSave").onclick = async () => {
    const payload = {
      id: id || null,
      name: $("sfName").value.trim(),
      category: $("sfCat").value.trim(),
      unit_label: $("sfUnit").value.trim() || "unit",
      current_stock: parseFloat($("sfStock").value) || 0,
      lead_time_days: numOrNull("sfLead"),
      safety_stock: numOrNull("sfSafe"),
      moq: parseFloat($("sfMoq").value) || 0,
      ordering_cost: numOrNull("sfOrder"),
      holding_cost: numOrNull("sfHold"),
      unit_cost: numOrNull("sfCost"),
      reorder_qty: numOrNull("sfQty"),
      supplier_name: $("sfSupN").value.trim(),
      supplier_phone: $("sfSupP").value.trim(),
      supplier_email: $("sfSupE").value.trim(),
    };
    if (!payload.name) { const e = $("sfErr"); e.textContent = "Item name is required."; e.hidden = false; return; }
    try { _supAfter(await api("/api/supply/item", { method: "POST", json: payload })); toast("Saved"); }
    catch (e) { const el = $("sfErr"); el.textContent = e.message; el.hidden = false; }
  };
}

async function supplyDelete(id) {
  const it = (_supplyData.inventory || []).find((x) => x.id === id);
  if (!it) return;
  const snapshot = JSON.parse(JSON.stringify(it));
  try { _supAfter(await api("/api/supply/item/delete", { method: "POST", json: { id } })); }
  catch (e) { toast(e.message); return; }
  toastUndo(`Removed “${it.name}” from inventory.`, async () => {
    _supAfter(await api("/api/supply/item", { method: "POST", json: { item: snapshot } }));
  });
}

async function supplyApplySuggested(id) {
  const it = (_supplyData.inventory || []).find((x) => x.id === id);
  if (!it) return;
  const payload = {
    id: it.id, name: it.name, category: it.category, unit_label: it.unit_label,
    current_stock: it.current_stock, moq: it.moq, unit_cost: it.unit_cost,
    reorder_qty: it.reorder_qty,
    supplier_name: it.supplier_name, supplier_phone: it.supplier_phone, supplier_email: it.supplier_email,
    lead_time_days: it.lead_is_auto ? it.effective_lead_time_days : it.lead_time_days,
    safety_stock: it.safety_is_auto ? it.effective_safety_stock : it.safety_stock,
    ordering_cost: it.ordering_is_auto ? it.effective_ordering_cost : it.ordering_cost,
    holding_cost: it.holding_is_auto ? it.effective_holding_cost : it.holding_cost,
  };
  try { _supAfter(await api("/api/supply/item", { method: "POST", json: payload })); toast("Suggested values applied — edit them anytime."); }
  catch (e) { toast(e.message); }
}

async function supplyImport() {
  try { _supAfter(await api("/api/supply/import-products", { method: "POST" })); toast("Products pulled from your sales"); }
  catch (e) { toast(e.message); }
}

// ---- Waste ----
function openWastePanel(preId) {
  _closePanels();
  const items = _supplyData.inventory || [];
  if (!items.length) { toast("Add an inventory item first."); return; }
  const p = $("supPanel");
  p.hidden = false;
  const opts = items.map((it) => `<option value="${it.id}" ${it.id === preId ? "selected" : ""}>${esc(it.name)} (${fmt(it.current_stock)} ${esc(it.unit_label || "")})</option>`).join("");
  p.innerHTML = `
    <div class="card sup-form">
      <h4 style="margin:0 0 4px;">🗑️ Record waste</h4>
      <p class="muted tiny">Logs the loss and reduces stock — e.g. a packing material spoiled by mistake.</p>
      <div class="sup-form-grid">
        <label>Item<select id="wsItem">${opts}</select></label>
        <label>Quantity wasted<input id="wsQty" type="number" min="0" step="any" value="1" /></label>
        <label>Reason <span class="muted tiny">(optional)</span><input id="wsReason" placeholder="Dropped / spoiled / damaged" /></label>
      </div>
      <div class="modal-actions">
        <button class="btn ghost" id="wsCancel">Cancel</button>
        <button class="btn primary" id="wsSave">Record waste</button>
      </div>
      <div class="err" id="wsErr" hidden></div>
    </div>`;
  p.scrollIntoView({ behavior: "smooth", block: "nearest" });
  $("wsCancel").onclick = _closePanels;
  $("wsSave").onclick = async () => {
    const payload = { inventory_id: $("wsItem").value, qty: parseFloat($("wsQty").value) || 0, reason: $("wsReason").value.trim() };
    try { _supAfter(await api("/api/supply/waste", { method: "POST", json: payload })); toast("Waste recorded — stock reduced"); }
    catch (e) { const el = $("wsErr"); el.textContent = e.message; el.hidden = false; }
  };
}

// ---- Product links (recipe map) ----
function openLinksPanel() {
  _closePanels();
  const p = $("supPanel");
  p.hidden = false;
  _renderLinks();
  p.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function _renderLinks() {
  const p = $("supPanel");
  const products = _supplyData.products || [];
  const items = _supplyData.inventory || [];
  const maps = _supplyData.maps || [];
  const byName = {};
  items.forEach((it) => (byName[it.id] = it));
  const itemOpts = items.map((it) => `<option value="${it.id}">${esc(it.name)}</option>`).join("");

  const prodBlocks = products.length ? products.map((prod) => {
    const links = maps.filter((m) => (m.product || "").toLowerCase() === prod.toLowerCase());
    const chips = links.map((m) => {
      const it = byName[m.inventory_id];
      return `<span class="link-chip">${esc(it ? it.name : "?")} × ${fmt(m.qty_per_unit)} ${esc(it ? it.unit_label : "")}
        <button class="lc-x" data-unmap="${m.id}" title="Remove">${sic("close")}</button></span>`;
    }).join("") || `<span class="muted tiny">No items linked yet</span>`;
    return `
      <div class="link-row">
        <div class="link-prod"><b>${esc(prod)}</b></div>
        <div class="link-chips">${chips}</div>
        <div class="link-add">
          <select data-lp-item="${esc(prod)}">${itemOpts}</select>
          <input type="number" min="0" step="any" value="1" data-lp-qty="${esc(prod)}" title="Qty per unit sold" />
          <button class="btn ghost tiny" data-lp-add="${esc(prod)}">＋ Link</button>
        </div>
      </div>`;
  }).join("") : `<p class="muted tiny">No products found. Upload Sales data (home screen) or pull products first.</p>`;

  p.innerHTML = `
    <div class="card sup-form">
      <h4 style="margin:0 0 4px;">🔗 Product links <span class="muted tiny">— how much inventory each product needs</span></h4>
      <p class="muted tiny">For every unit of a product sold, set how many units of each inventory item it consumes. Usage &amp; reorder points then follow your real sales.</p>
      ${!items.length ? `<p class="muted tiny">Add inventory items first, then link them here.</p>` : `<div class="link-list">${prodBlocks}</div>`}
      <div class="modal-actions"><button class="btn ghost" id="lkClose">Close</button></div>
    </div>`;
  $("lkClose").onclick = _closePanels;
  p.querySelectorAll("[data-lp-add]").forEach((b) => b.onclick = () => {
    const prod = b.dataset.lpAdd;
    const sel = p.querySelector(`[data-lp-item="${CSS.escape(prod)}"]`);
    const qin = p.querySelector(`[data-lp-qty="${CSS.escape(prod)}"]`);
    _linkAdd(prod, sel.value, parseFloat(qin.value) || 1);
  });
  p.querySelectorAll("[data-unmap]").forEach((b) => b.onclick = () => _linkRemove(b.dataset.unmap));
}

async function _linkAdd(product, inventory_id, qty_per_unit) {
  try {
    const d = await api("/api/supply/map", { method: "POST", json: { product, inventory_id, qty_per_unit } });
    _supplyData = d; _renderLinks(); if (d.insights) renderApprovals(d.insights); toast("Linked");
  } catch (e) { toast(e.message); }
}

async function _linkRemove(id) {
  const snap = (_supplyData.maps || []).find((m) => m.id === id);
  try {
    const d = await api("/api/supply/map/delete", { method: "POST", json: { id } });
    _supplyData = d; _renderLinks(); if (d.insights) renderApprovals(d.insights);
  } catch (e) { toast(e.message); return; }
  if (!snap) { toast("Removed"); return; }
  toastUndo("Recipe link removed.", async () => {
    const d = await api("/api/supply/map", { method: "POST", json: {
      product: snap.product, inventory_id: snap.inventory_id,
      qty_per_unit: snap.qty_per_unit } });
    _supplyData = d; _renderLinks();
  });
}

// ---- Purchase orders ----
async function supplyOpenPo(itemIds) {
  try {
    const d = await api("/api/supply/po/create", { method: "POST", json: { item_ids: itemIds } });
    if (d.download_url) await download(d.download_url, `${d.po_number}.pdf`);
    _supAfter(d);
    toast(`✅ ${d.po_number} — PDF saved to your device.`);
  } catch (e) { toast(e.message); }
}

async function supplyGeneratePo() {
  try {
    const d = await api("/api/supply/reorder/generate", { method: "POST" });
    if (d.download_url) await download(d.download_url, `${d.po_number}.pdf`);
    _supAfter(d);
    toast(`✅ ${d.po_number} generated — PDF saved to your device.`);
  } catch (e) { toast(e.message); }
}

// ---------- MODULE: Sales Analytics ----------
async function openSales() {
  moduleShell("Sales Analytics", `<div class="ap-empty">Loading analytics…</div>`);
  try {
    await api("/api/smart/state");
    const d = await api("/api/analytics?lang=en");
    const k = d.kpis;
    let html = `
      <div class="kpis">
        <div class="kpi"><div class="label">Revenue</div><div class="value">₹${fmt(k.revenue)}</div></div>
        <div class="kpi"><div class="label">Orders</div><div class="value">${fmt(k.orders)}</div></div>
        <div class="kpi"><div class="label">Customers</div><div class="value">${fmt(k.customers)}</div></div>
        <div class="kpi"><div class="label">Avg Order Value</div><div class="value">₹${fmt(k.avg_order_value)}</div></div>
      </div>
      ${renderActions(d.insights)}
      <div class="chart-card"><h4>Monthly revenue</h4><div class="plot" id="cMonthly"></div></div>
      ${d.forecast ? `<div class="chart-card"><h4>Next 30 days — ≈ ₹${fmt(d.forecast.next_30_total)} (${d.forecast.vs_last_30_pct >= 0 ? "+" : ""}${d.forecast.vs_last_30_pct}% vs last 30)</h4><div class="plot" id="cFcst"></div></div>` : ""}
      <div class="grid-2">
        ${d.by_category ? `<div class="chart-card"><h4>Revenue by category</h4><div class="plot" id="cCat"></div></div>` : ""}
        <div class="chart-card"><h4>Revenue by weekday</h4><div class="plot" id="cWk"></div></div>
      </div>
      ${d.top_products ? `<div class="chart-card"><h4>Top products</h4><div class="plot" id="cTop"></div></div>` : ""}`;
    moduleShell("Sales Analytics", html);
    const primary = cssVar("--primary", "#6d28d9");
    plot($("cMonthly"), [{ x: d.monthly_trend.x, y: d.monthly_trend.y, type: "scatter", mode: "lines+markers", line: { color: primary, width: 2.5, shape: "spline" }, fill: "tozeroy", fillcolor: "rgba(109,40,217,.10)" }], { yaxis: { tickprefix: "₹" } }, "Monthly revenue");
    if (d.forecast) {
      const f = d.forecast;
      plot($("cFcst"), [
        { x: f.hist_x, y: f.hist_y, type: "scatter", mode: "lines", name: "Actual", line: { color: primary, width: 2.5 } },
        { x: f.fcst_x, y: f.fcst_y, type: "scatter", mode: "lines", name: "Forecast", line: { color: cssVar("--green", "#0a7a4d"), width: 2.5, dash: "dash" } },
      ], { yaxis: { tickprefix: "₹" } }, "30-day forecast");
    }
    if (d.by_category) plot($("cCat"), [{ x: d.by_category.x, y: d.by_category.y, type: "bar", marker: { color: primary } }], { yaxis: { tickprefix: "₹" } }, "Revenue by category");
    plot($("cWk"), [{ x: d.weekday_pattern.x, y: d.weekday_pattern.y, type: "bar", marker: { color: "#0ea5e9" } }], { yaxis: { tickprefix: "₹" } }, "Revenue by weekday");
    if (d.top_products) plot($("cTop"), [{ x: d.top_products.x, y: d.top_products.y, type: "bar", orientation: "h", marker: { color: "#10b981" } }], { xaxis: { tickprefix: "₹" }, yaxis: { autorange: "reversed" }, margin: { l: 150, r: 20, t: 8, b: 40 } }, "Top products");
  } catch (e) {
    moduleShell("Sales Analytics", `<div class="card">${esc(e.message)}</div>`);
  }
}

// ---------- MODULE: Sub-Category Analysis ----------
async function openSubcategory() {
  moduleShell("Sub-Category Analysis", `<div class="ap-empty">Loading…</div>`);
  try {
    await api("/api/smart/state");
    const d = await api("/api/subcategory?lang=en");
    if (!d.available) { moduleShell("Sub-Category Analysis", `<div class="card">${esc(d.reason || "Not enough data.")}</div>`); return; }
    const label = d.field === "subcategory" ? "sub-categories" : "categories";
    let html = `
      <div class="row" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px;">
        <span class="muted">Drill into a ${d.field === "subcategory" ? "sub-category" : "category"}:</span>
        <select id="subSel" class="sub-select"><option value="">All (overview)</option>${d.all_values.map((v) => `<option>${esc(v)}</option>`).join("")}</select>
      </div>
      ${renderActions(d.insights)}
      <div class="chart-card"><h4>Monthly trend — top ${label}</h4><div class="plot" id="cSubTrend"></div></div>
      <div class="chart-card"><h4>Total revenue by ${label}</h4><div class="plot" id="cSubTot"></div></div>`;
    moduleShell("Sub-Category Analysis", html);
    $("subSel").onchange = () => $("subSel").value ? renderSubDetail($("subSel").value) : openSubcategory();
    plot($("cSubTrend"), d.series.map((s) => ({ x: s.x, y: s.y, name: s.name, type: "scatter", mode: "lines+markers" })), { yaxis: { tickprefix: "₹" } }, "Monthly trend");
    plot($("cSubTot"), [{ x: d.totals.x, y: d.totals.y, type: "bar", marker: { color: cssVar("--primary", "#6d28d9") } }], { yaxis: { tickprefix: "₹" } }, "Total revenue");
  } catch (e) { moduleShell("Sub-Category Analysis", `<div class="card">${esc(e.message)}</div>`); }
}

async function renderSubDetail(value) {
  const wrap = $("view");
  try {
    const d = await api(`/api/subcategory/detail?value=${encodeURIComponent(value)}&lang=en`);
    if (!d.available) { toast(d.reason || "No detail"); return; }
    const k = d.kpis;
    let html = `
      <div class="row" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px;">
        <button class="btn ghost sm" id="subBack">← All ${d.field === "subcategory" ? "sub-categories" : "categories"}</button>
        <b>${esc(value)}</b>
      </div>
      ${renderActions(d.insights)}
      <div class="kpis">
        <div class="kpi"><div class="label">Revenue</div><div class="value">₹${fmt(k.revenue)}</div></div>
        <div class="kpi"><div class="label">Orders</div><div class="value">${fmt(k.orders)}</div></div>
        <div class="kpi"><div class="label">Avg Order Value</div><div class="value">₹${fmt(k.avg_order_value)}</div></div>
        <div class="kpi"><div class="label">Share of revenue</div><div class="value">${k.share_of_total_pct}%</div></div>
      </div>
      <div class="chart-card"><h4>${esc(value)} — monthly revenue</h4><div class="plot" id="cDT"></div></div>
      <div class="grid-2">
        <div class="chart-card"><h4>Revenue by weekday</h4><div class="plot" id="cDW"></div></div>
        ${d.top_products ? `<div class="chart-card"><h4>Top items</h4><div class="plot" id="cDP"></div></div>` : ""}
      </div>`;
    setView(`<div class="page-head"><h2>Sub-Category Analysis</h2><button class="btn ghost sm" id="backHome">← All apps</button></div>${html}`);
    $("backHome").onclick = goHome; $("subBack").onclick = openSubcategory;
    plot($("cDT"), [{ x: d.monthly_trend.x, y: d.monthly_trend.y, type: "scatter", mode: "lines+markers", fill: "tozeroy", fillcolor: "rgba(109,40,217,.10)", line: { color: cssVar("--primary", "#6d28d9") } }], { yaxis: { tickprefix: "₹" } }, value + " monthly");
    plot($("cDW"), [{ x: d.weekday_pattern.x, y: d.weekday_pattern.y, type: "bar", marker: { color: "#0ea5e9" } }], { yaxis: { tickprefix: "₹" } }, "Weekday");
    if (d.top_products) plot($("cDP"), [{ x: d.top_products.x, y: d.top_products.y, type: "bar", orientation: "h", marker: { color: "#10b981" } }], { xaxis: { tickprefix: "₹" }, yaxis: { autorange: "reversed" }, margin: { l: 150, r: 20, t: 8, b: 40 } }, "Top items");
  } catch (e) { toast(e.message); }
}

// ---------- MODULE: Review Analytics (self positioning, no peer comparison) ----------
async function openReview() {
  moduleShell("Review Analytics", `<div class="ap-empty">Analysing your reviews…</div>`);
  try {
    const d = await api("/api/smart/positioning?lang=en");
    if (!d.available) { moduleShell("Review Analytics", `<div class="card">${esc(d.reason || "Not enough review data.")}</div>`); return; }
    const pos = d.position || {};
    const html = `
      ${renderActions(d.insights)}
      <div class="card pos-banner"><span class="muted tiny">Your position, from your own reviews</span>
        <h3 style="margin:4px 0 0;">📍 ${esc(pos.quadrant || "—")}</h3></div>
      <div class="kpis">
        <div class="kpi"><div class="label">Reviews</div><div class="value">${fmt(d.n_reviews)}</div></div>
        <div class="kpi"><div class="label">Your rating</div><div class="value">${d.avg_rating ?? "—"}</div></div>
        <div class="kpi"><div class="label">Sentiment</div><div class="value">${d.overall_sentiment > 0 ? "+" : ""}${d.overall_sentiment}</div></div>
      </div>
      <div class="chart-card"><h4>What your customers talk about (% of reviews)</h4><div class="plot" id="cShare"></div></div>
      <div class="chart-card"><h4>How positively they talk about it (sentiment)</h4><div class="plot" id="cSent"></div></div>`;
    moduleShell("Review Analytics", html);
    const primary = cssVar("--primary", "#6d28d9");
    plot($("cShare"), [{ x: d.share_chart.themes, y: d.share_chart.yours, type: "bar", marker: { color: primary } }], { margin: { l: 46, r: 16, t: 8, b: 120 }, xaxis: { tickangle: -35 } }, "What customers talk about");
    plot($("cSent"), [{ x: d.sentiment_chart.themes, y: d.sentiment_chart.yours, type: "bar", marker: { color: "#0ea5e9" } }], { margin: { l: 46, r: 16, t: 8, b: 120 }, xaxis: { tickangle: -35 } }, "Sentiment by theme");
  } catch (e) { moduleShell("Review Analytics", `<div class="card">${esc(e.message)}</div>`); }
}

// ---------- MODULE: Complaint Analysis ----------
async function openComplaints() {
  moduleShell("Complaint Analysis", `<div class="ap-empty">Finding complaint patterns…</div>`);
  try {
    const d = await api("/api/smart/complaints");
    const det = d.detected || {};
    let html = `<p class="muted">${fmt(det.n_reviews)} reviews · ${fmt(det.n_complaints)} complaints (${det.complaint_rate ?? 0}% rate)</p>`;
    const focus = (d.focus && d.focus.focus_now) || [];
    if (focus.length) {
      html += `<div class="card"><h4>🎯 Fix these first</h4>${focus.map((x, i) => `
        <div class="action-card negative"><div class="do">${i + 1}. ${esc(x.theme)} — ${esc(x.severity)}</div>
        <div class="why">✅ ${esc(x.action)} · ${x.count} complaints (${x.share_pct}%)</div></div>`).join("")}</div>`;
    } else {
      html += `<div class="card">🎉 No significant complaint patterns found.</div>`;
    }
    if (d.monthly) {
      html += `<div class="chart-card"><h4>📅 Complaints per month (avg ${d.monthly.avg_per_month}/mo)</h4><div class="plot" id="cCompM"></div></div>`;
    }
    if (d.deep && d.deep.length) {
      html += `<div class="card"><h4 style="margin-bottom:8px;">Deep analysis</h4>
        <div class="table-scroll"><table><thead><tr><th>Theme</th><th>Complaints</th><th>Share</th><th>Severity</th><th>Example</th></tr></thead>
        <tbody>${d.deep.map((r) => `<tr><td><b>${esc(r.theme)}</b></td><td>${r.count}</td><td>${r.share_pct}%</td><td>${esc(r.severity)}</td><td class="muted">"${esc(r.example)}…"</td></tr>`).join("")}</tbody></table></div></div>`;
    }
    moduleShell("Complaint Analysis", html);
    if (d.monthly) plot($("cCompM"), [{ x: d.monthly.months, y: d.monthly.counts, type: "bar", marker: { color: "#f97316" } }], {}, "Complaints per month");
  } catch (e) { moduleShell("Complaint Analysis", `<div class="card">${esc(e.message)}</div>`); }
}

// ---------- MODULE: Position Strategy + AI ----------
async function openStrategy() {
  moduleShell("Position Strategy + AI", `<div class="ap-empty">Detecting your position from your saved reviews…</div>`);
  try {
    let d;
    try { d = await api("/api/smart/strategy/detect?lang=en", { method: "POST" }); }
    catch (e) { d = await api("/api/position-strategy"); if (!d.detected) throw e; }
    renderStrategy(d);
  } catch (e) {
    moduleShell("Position Strategy + AI", `<div class="card">${esc(e.message)}<br><br>Upload your reviews in <b>Review Analytics</b> first — the strategy is detected from them.</div>`);
  }
}

function posCard(p, eyebrow) {
  return `<div class="card" style="border-left:4px solid var(--primary);">
    <div class="section-title" style="margin:0;">${esc(eyebrow)}</div>
    <h3 style="margin:2px 0 2px;">${esc(p.name)}</h3>
    <div class="muted" style="font-size:13px;">${esc(p.tagline)}</div>
    <div class="grid-2" style="margin-top:12px;">
      <div><b style="color:var(--green);">✅ Pros</b><ul style="margin:6px 0 0;padding-left:18px;font-size:13px;color:var(--text-2);">${p.pros.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div><b style="color:var(--red);">⚠️ Cons</b><ul style="margin:6px 0 0;padding-left:18px;font-size:13px;color:var(--text-2);">${p.cons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    </div></div>`;
}

function renderStrategy(d) {
  let html = posCard(d.current, `📍 You are here${d.n_reviews ? ` · from ${d.n_reviews} reviews` : ""}`);
  html += `<div class="section-title">Choose a target — or strengthen where you are</div>
    <div class="apps-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));">
    ${d.options.map((o) => `<div class="app-tile opt-tile ${o.id === d.target_id ? "selected" : ""}" data-target="${o.id}" style="text-align:left;">
        <div class="opt-diff ${o.is_current ? "stay" : (o.axes_changing === 1 ? "adj" : "big")}">${esc(o.difficulty)}</div>
        <div class="name" style="margin-top:5px;">${esc(o.name)}${o.is_current ? " ★" : ""}</div>
        <div class="sub">${esc(o.tagline)}</div>
      </div>`).join("")}</div>`;

  if (d.plan) {
    const pl = d.plan; const pct = pl.progress.total ? Math.round(pl.progress.done / pl.progress.total * 100) : 0;
    if (!pl.same_position) html += posCard(pl.target, "🎯 Your target");
    html += `<div class="card" style="border-left:4px solid var(--blue);"><b style="color:var(--blue);">${pl.same_position ? "Plan:" : "The gap:"}</b> ${esc(pl.gap)}</div>`;
    html += `<div class="card" style="border-left:4px solid var(--green);"><h4 style="color:var(--green);">Keep these the same</h4>
      <p class="muted tiny" style="margin:4px 0;">${esc(pl.keep_note)}</p>
      <ul style="margin:8px 0 0;padding-left:18px;font-size:13px;color:var(--text-2);">${pl.keep_same.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    html += `<div class="section-title">Your levelled checklist — ${pl.progress.done}/${pl.progress.total} (${pct}%)</div>
      <p class="muted tiny" style="margin-top:-6px;">Finish a level to unlock the next one.</p>
      <div class="progress-bar" style="height:10px;background:var(--surface-2);border:1px solid var(--border);border-radius:99px;overflow:hidden;margin-bottom:14px;"><div id="pfill" style="height:100%;width:${pct}%;background:var(--primary);"></div></div>`;

    // group by level; a level is locked until the previous level is fully done
    const levels = pl.levels || [...new Set(pl.checklist.map((it) => it.level || 1))].sort();
    const doneByLevel = {}, totByLevel = {};
    pl.checklist.forEach((it) => { const l = it.level || 1; totByLevel[l] = (totByLevel[l] || 0) + 1; if (it.done) doneByLevel[l] = (doneByLevel[l] || 0) + 1; });
    let prevComplete = true;
    levels.forEach((lv) => {
      const items = pl.checklist.filter((it) => (it.level || 1) === lv);
      const phaseName = items[0] ? items[0].phase : `Level ${lv}`;
      const locked = !prevComplete;
      const levelDone = (doneByLevel[lv] || 0) === totByLevel[lv];
      html += `<div class="level-block ${locked ? "locked" : ""}">
        <div class="level-head"><span class="level-badge">Level ${lv}</span> ${esc(phaseName.replace(/^Level \d+ · /, ""))} <span class="muted tiny">${doneByLevel[lv] || 0}/${totByLevel[lv]}</span>${locked ? ` <span class="lock-note">🔒 finish Level ${lv - 1} first</span>` : (levelDone ? ` <span style="color:var(--green);">✓ done</span>` : "")}</div>`;
      items.forEach((it) => {
        html += `<label class="task-item ${it.done ? "done" : ""}" data-item="${it.id}" data-level="${lv}" style="align-items:flex-start;border:1px solid var(--border);border-radius:8px;padding:11px 13px;margin-bottom:8px;background:var(--surface);${locked ? "opacity:.55;pointer-events:none;" : ""}">
          <input type="checkbox" ${it.done ? "checked" : ""} ${locked ? "disabled" : ""} style="margin-top:2px;" />
          <span class="t"><b>${esc(it.text)}</b><div class="muted tiny" style="margin-top:3px;">Why: ${esc(it.why)}</div></span></label>`;
      });
      html += `</div>`;
      prevComplete = prevComplete && levelDone;
    });
  }

  html += `<div class="section-title">AI</div>
    <div class="card"><div class="row" style="display:flex;gap:10px;flex-wrap:wrap;">
      <button class="btn primary sm" id="runAnalyst">🤖 Run AI Analyst</button>
    </div><div id="analystOut" style="margin-top:12px;"></div></div>`;

  moduleShell("Position Strategy + AI", html);

  document.querySelectorAll("[data-target]").forEach((el) => el.onclick = async () => {
    try { const r = await api("/api/position-strategy/target", { method: "POST", json: { target_id: el.dataset.target } }); r.n_reviews = d.n_reviews; renderStrategy(r); }
    catch (e) { toast(e.message); }
  });
  document.querySelectorAll("[data-item] input").forEach((chk) => chk.onchange = async () => {
    const item = chk.closest("[data-item]");
    try {
      await api("/api/position-strategy/check", { method: "POST", json: { item_id: item.dataset.item, done: chk.checked } });
      // re-fetch to recompute level gating cleanly
      const r = await api("/api/position-strategy"); r.n_reviews = d.n_reviews; renderStrategy(r);
    } catch (e) { chk.checked = !chk.checked; toast(e.message); }
  });
  $("runAnalyst").onclick = runAnalyst;
}

async function runAnalyst() {
  const out = $("analystOut"); const btn = $("runAnalyst");
  btn.disabled = true; out.innerHTML = `<div class="ap-empty">Running AI analysis (uses one of your daily AI runs)…</div>`;
  try {
    const d = await api("/api/analyst", { method: "POST" });
    out.innerHTML = d.results.map((file) => `<h4>📄 ${esc(file.file)}</h4>` + file.insights.map((ins) => `
      <div class="action-card"><div class="do">🔎 ${esc(ins.decision || "")}</div>
      <div class="why"><b>Action:</b> ${esc(ins.action || "")}<br><b>Impact:</b> ${esc(ins.impact || "")}</div></div>`).join("")).join("");
    if (!out.innerHTML) out.innerHTML = `<div class="ap-empty">No insights generated.</div>`;
  } catch (e) { out.innerHTML = `<div class="card">${esc(e.message)}</div>`; }
  btn.disabled = false;
}

function renderActions(insights) {
  if (!insights || !insights.length) return "";
  return `<div style="margin-bottom:14px;">${insights.map((ins) => {
    const type = ["positive", "negative", "warning", "neutral"].includes(ins.type) ? ins.type : "neutral";
    return `<div class="action-card ${type}">${ins.action ? `<div class="do">✅ ${esc(ins.action)}</div><div class="why">${esc(ins.text)}</div>` : `<div class="do">${esc(ins.text)}</div>`}</div>`;
  }).join("")}</div>`;
}

// ---------- Win-back — approve = direct Excel download; details = editable popup ----------
let _wbRows = [];
const WB_COLS = [
  { k: "customer_name", label: "Customer" },
  { k: "favorite_item", label: "Favourite" },
  { k: "last_purchase_date", label: "Last order" },
  { k: "monetary", label: "Spend" },
  { k: "coupon_code", label: "Coupon" },
  { k: "message", label: "Message" },
];

// Details → editable popup (edit fields, remove/add rows, export)
async function openWinbackEditor() {
  toast("Loading win-back list…", 4000);
  try {
    const d = await api("/api/rfm/winback", { method: "POST" });
    if (!d.customers || !d.customers.length) { toast("No at-risk customers with enough history."); return; }
    _wbRows = d.customers.map((c) => ({ ...c }));
    renderWinbackTable();
    $("wbModal").hidden = false;
  } catch (e) { toast(e.message, 6000); }
}
function renderWinbackTable() {
  const head = `<tr>${WB_COLS.map((c) => `<th>${c.label}</th>`).join("")}<th></th></tr>`;
  const body = _wbRows.map((r, i) => `<tr data-r="${i}">${WB_COLS.map((c) =>
    `<td><input data-k="${c.k}" value="${esc(r[c.k] == null ? "" : r[c.k])}" /></td>`).join("")}
    <td><button class="btn ghost tiny" data-del="${i}">${sic("close")}</button></td></tr>`).join("");
  $("wbTable").innerHTML = `<table class="wb-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
  $("wbTable").querySelectorAll("input").forEach((inp) => inp.onchange = (e) => {
    const tr = e.target.closest("tr"); _wbRows[+tr.dataset.r][e.target.dataset.k] = e.target.value;
  });
  $("wbTable").querySelectorAll("[data-del]").forEach((b) => b.onclick = () => { _wbRows.splice(+b.dataset.del, 1); renderWinbackTable(); });
}
$("wbAddRow").onclick = () => { _wbRows.push({}); renderWinbackTable(); };
$("wbClose").onclick = () => { $("wbModal").hidden = true; };
$("wbCancel").onclick = () => { $("wbModal").hidden = true; };
$("wbExport").onclick = async () => {
  if (!_wbRows.length) { toast("List is empty."); return; }
  try {
    const res = await fetch("/api/rfm/winback/export", {
      method: "POST", headers: { "Content-Type": "application/json", "Authorization": "Bearer " + state.token, "X-Session-Id": state.sessionId },
      body: JSON.stringify({ rows: _wbRows }),
    });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || "Export failed"); }
    const blob = await res.blob(); const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "winback_messages.xlsx";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
    // mark the insight approved -> History
    const r = await api(`/api/smart/insight/winback/decision`, { method: "POST", json: { decision: "approve" } });
    if (state.lastState) { state.lastState.insights = r.insights; if (r.history) state.lastState.history = r.history; if (r.tasks) state.lastState.tasks = r.tasks; }
    renderApprovals(r.insights); if (r.tasks) refreshTaskList(r.tasks);
    $("wbModal").hidden = true;
    // Closing the loop: the app has just handed over a list it will never hear
    // about again unless we ask. One tick, and every later refresh of the sales
    // data can answer "did it work" — which is the only number that makes the
    // subscription obviously worth keeping.
    askWinbackSent(_wbRows.slice());
  } catch (e) { toast(e.message, 6000); }
};

function askWinbackSent(rows) {
  openModal("Did you send it?", `
    <p class="muted" style="margin-top:0;">Tell us when this campaign actually goes out and we can
    measure it: of the <b>${rows.length}</b> customers on this list, how many come back, and how
    much they spend, in the 30 days after.</p>
    <p class="muted tiny">Nothing is sent from here — you send it your own way. This is just the
    date we measure from. It is not a controlled test; it is what your own sales data says.</p>
    <label class="fld"><span>How are you sending it?</span>
      <select id="wbCh">
        <option value="whatsapp">WhatsApp</option>
        <option value="sms">SMS</option>
        <option value="email">Email</option>
        <option value="call">Phone calls</option>
        <option value="other">Something else</option>
      </select></label>
    <div class="modal-actions">
      <button class="btn ghost" id="wbLater">Not yet — I'll tick it later</button>
      <button class="btn primary" id="wbSent">I've sent it</button>
    </div>`);
  $("wbLater").onclick = () => { closeModal(); toast("Exported & approved — moved to History."); };
  $("wbSent").onclick = async () => {
    try {
      const p = await api("/api/rfm/winback/sent", { method: "POST",
        json: { customers: rows, channel: $("wbCh").value } });
      closeModal();
      toast(p.headline || "Recorded — we'll measure it from today.", 6000);
      renderProof();
    } catch (e) { toast(e.message); }
  };
}

$("refreshApprovals").onclick = async () => {
  try { const s = await api("/api/smart/state"); state.lastState = s; renderApprovals(s.insights); toast("Refreshed"); } catch (e) { toast(e.message); }
};

// ---------- MODULE: Instagram connection ----------
async function openInstagramModule() {
  moduleShell("Instagram", `<div class="ap-empty">Loading…</div>`);
  try {
    const s = await api("/api/instagram/status");
    const oauth = !!s.oauth_available;   // set by the admin via env vars
    const advancedHidden = oauth && !s.connected;  // hide the paste form behind a disclosure

    const connectPanel = oauth ? `
      <div class="row" style="display:flex;gap:10px;flex-wrap:wrap;">
        <button class="btn primary sm" id="igOauth">🔗 Connect Instagram</button>
        <span class="muted tiny" style="align-self:center;">Opens Meta's login in a popup. No tokens to paste.</span>
      </div>
      <details class="ig-advanced" style="margin-top:12px;">
        <summary class="muted tiny" style="cursor:pointer;">Advanced: paste an access token manually instead</summary>
        <div class="ig-form" style="margin-top:10px;">
          <label>Access token <input id="igToken" placeholder="EAAG… (from Graph API Explorer)" /></label>
          <label>Instagram Business account id <input id="igUserId" placeholder="17841400000000000" /></label>
          <div class="row" style="display:flex;gap:10px;margin-top:10px;">
            <button class="btn ghost sm" id="igTest">Test</button>
            <button class="btn ghost sm" id="igSave">Save</button>
          </div>
        </div>
      </details>
      <div id="igMsg" class="muted tiny" style="margin-top:8px;"></div>` : `
      <div class="ig-form" style="margin-top:14px;">
        <div class="focus-box" style="background:var(--amber-soft);border-radius:8px;padding:10px 12px;margin-bottom:10px;">
          <b style="color:var(--amber);">One-click OAuth isn't enabled on this server yet.</b>
          <div class="muted tiny" style="margin-top:3px;">Ask the admin to set <code>META_APP_ID</code> and <code>META_APP_SECRET</code> env vars — then this page becomes a single "Connect Instagram" button. Until then, paste an access token below.</div>
        </div>
        <label>Access token <input id="igToken" placeholder="EAAG… (from Meta Graph API Explorer, instagram_content_publish scope)" /></label>
        <label>Instagram Business account id <input id="igUserId" placeholder="17841400000000000" /></label>
        <div class="row" style="display:flex;gap:10px;margin-top:10px;">
          <button class="btn ghost sm" id="igTest">Test</button>
          <button class="btn primary sm" id="igSave">Connect</button>
        </div>
        <div id="igMsg" class="muted tiny" style="margin-top:8px;"></div>
      </div>`;

    setView(`<div class="page-head"><h2>Instagram</h2><button class="btn ghost sm" id="backHome">← All apps</button></div>
      <div class="card ig-card">
        <div class="row" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          <div style="flex:1;min-width:220px;">
            <h3 style="margin:0;">${s.connected ? "✅ Connected" : "🔌 Not connected yet"}</h3>
            ${s.connected ? `<div class="muted tiny" style="margin-top:4px;">Account: <b>@${esc(s.account_username || "—")}</b> · IG user id: <code>${esc(s.ig_user_id)}</code> · since ${esc(String(s.connected_at || "").slice(0,10))}</div>`
                          : `<div class="muted tiny" style="margin-top:4px;">${oauth ? "Click below to sign in with Meta — we'll never see your password." : "Follow the steps below."}</div>`}
          </div>
          ${s.connected ? `<button class="btn ghost sm" id="igDisconnect">Disconnect</button>` : ""}
        </div>
        ${s.connected ? `<p class="muted tiny" style="margin-top:10px;">Ready. When you approve a Content Creator suggestion, we'll post it on this Instagram account.</p>` : connectPanel}
      </div>
      ${!s.connected ? `
      <div class="card">
        <h4>${oauth ? "What happens when you click Connect Instagram" : "How to set OAuth up (admin)"}</h4>
        ${oauth ? `
        <ol class="muted tiny" style="line-height:1.7;padding-left:18px;">
          <li>An Instagram login popup opens (instagram.com, not us — no Facebook Page needed).</li>
          <li>You approve the permissions with your Instagram Business/Creator account.</li>
          <li>Instagram redirects back and we save your access token to your account — you never see it.</li>
          <li>Done. New Content Creator suggestions can post to your Instagram.</li>
        </ol>
        <p class="muted tiny" style="margin-top:8px;">💡 Your Instagram account must be switched to <b>Business</b> or <b>Creator</b> (Instagram app → Settings → Account type and tools) — a personal account can't connect. During Meta's app review your account also needs to be added as an "Instagram Tester" in the Meta app — otherwise Instagram will refuse the login. After the app is approved, this works for any account, and no Facebook Page is ever required.</p>` : `
        <ol class="muted tiny" style="line-height:1.7;padding-left:18px;">
          <li>Create a Meta app at <a href="https://developers.facebook.com/apps" target="_blank">developers.facebook.com/apps</a>.</li>
          <li>Add the <b>"Instagram"</b> product (not "Facebook Login") and set up Business Login for Instagram, with the OAuth Redirect URI <code>https://YOUR-APP/api/instagram/oauth/callback</code>.</li>
          <li>Add permissions: <code>instagram_business_basic</code>, <code>instagram_business_content_publish</code>.</li>
          <li>Set env vars on the server: <code>META_APP_ID</code>, <code>META_APP_SECRET</code> (the Instagram product's App ID/Secret), optionally <code>META_REDIRECT_URL</code>.</li>
          <li>Reload this page — the "Connect Instagram" button appears.</li>
        </ol>`}
      </div>` : ""}`);
    $("backHome").onclick = goHome;
    if (!s.connected) {
      if (oauth) $("igOauth").onclick = () => startInstagramOauth();
      const testBtn = $("igTest"), saveBtn = $("igSave");
      if (testBtn) testBtn.onclick = async () => {
        const at = $("igToken").value.trim(), ig = $("igUserId").value.trim();
        if (!at || !ig) { $("igMsg").innerHTML = "<span style='color:var(--red)'>Fill both fields first.</span>"; return; }
        $("igMsg").textContent = "Testing…";
        try { const r = await api("/api/instagram/test", { method: "POST", json: { access_token: at, ig_user_id: ig } });
          $("igMsg").innerHTML = r.ok ? `<span style='color:var(--green)'>✓ OK — @${esc(r.username || "—")}</span>` : `<span style='color:var(--red)'>${esc(r.error || "Not OK")}</span>`;
        } catch (e) { $("igMsg").innerHTML = `<span style='color:var(--red)'>${esc(e.message)}</span>`; }
      };
      if (saveBtn) saveBtn.onclick = async () => {
        const at = $("igToken").value.trim(), ig = $("igUserId").value.trim();
        if (!at || !ig) { toast("Fill both fields first."); return; }
        try { await api("/api/instagram/connect", { method: "POST", json: { access_token: at, ig_user_id: ig } });
          toast("✅ Instagram connected"); openInstagramModule();
        } catch (e) { $("igMsg").innerHTML = `<span style='color:var(--red)'>${esc(e.message)}</span>`; }
      };
    } else {
      $("igDisconnect").onclick = async () => {
        if (!confirm("Disconnect Instagram? Scheduled posts will fail until you reconnect.")) return;
        await api("/api/instagram/disconnect", { method: "POST" }); openInstagramModule();
      };
    }
  } catch (e) { moduleShell("Instagram", `<div class="card">${esc(e.message)}</div>`); }
}

// Open Meta's OAuth login in a popup; the callback posts a message back here.
async function startInstagramOauth() {
  try {
    const r = await api("/api/instagram/oauth/start");
    const w = 560, h = 720;
    const y = window.screenY + Math.max(0, (window.innerHeight - h) / 2);
    const x = window.screenX + Math.max(0, (window.innerWidth  - w) / 2);
    const popup = window.open(r.login_url, "ig_oauth",
      `width=${w},height=${h},left=${x},top=${y},resizable=yes,scrollbars=yes`);
    if (!popup) { toast("Popup was blocked — allow popups for this site and try again."); return; }
    const handler = (ev) => {
      if (!ev.data || ev.data.type !== "ig-oauth") return;
      window.removeEventListener("message", handler);
      const p = ev.data.payload || {};
      if (p.ok) toast(`✅ Connected @${p.username || "—"}`);
      else toast("⚠️ " + (p.message || "Login failed"), 7000);
      openInstagramModule();
    };
    window.addEventListener("message", handler);
    // fallback: if the popup closes without messaging, refresh anyway
    const iv = setInterval(() => { if (popup.closed) { clearInterval(iv); setTimeout(openInstagramModule, 400); } }, 700);
  } catch (e) { toast(e.message, 6000); }
}

// ---------- MODULE: Content Creator ----------
async function openContentModule() {
  moduleShell("Content Creator", `<div class="ap-empty">Loading…</div>`);
  try {
    const sug = await api("/api/content/suggestion");
    const s = sug.suggestion || {};
    const openaiNote = sug.openai
      ? `<span class="pill-on">OpenAI on</span>`
      : `<span class="pill-off">OpenAI off — using templates (set OPENAI_API_KEY on the server)</span>`;
    let html = `<div class="card">
      <div class="row" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <h3 style="margin:0;">Current suggestion</h3><span style="flex:1"></span>${openaiNote}
        <button class="btn ghost sm" id="ccRotate">↻ Rotate</button>
      </div>
      ${s.id ? `<p class="muted tiny">Topic: ${esc(s.topic || "—")}${s.generated ? " · generated" : " · not yet generated — open Details to fill in caption + image"}</p>
      <div class="row" style="display:flex;gap:10px;flex-wrap:wrap;">
        <button class="btn primary sm" id="ccOpen">✎ Open editor</button>
      </div>` : `<p class="muted">No suggestion active yet.</p>`}
    </div>`;

    setView(`<div class="page-head"><h2>Content Creator</h2><button class="btn ghost sm" id="backHome">← All apps</button></div>${html}`);
    $("backHome").onclick = goHome;
    $("ccRotate").onclick = async () => {
      await api("/api/smart/state"); // no-op; suggestion regenerates when the current one is cleared
      try { await api(`/api/smart/insight/${s.id}/decision`, { method: "POST", json: { decision: "disapprove" } }); } catch (e) {}
      openContentModule();
    };
    if ($("ccOpen")) $("ccOpen").onclick = () => openContentEditor(s.id);
  } catch (e) { moduleShell("Content Creator", `<div class="card">${esc(e.message)}</div>`); }
}

// Details popup for a content_ insight — editable everything + Post/Schedule
async function openContentEditor(insightId) {
  $("ccModal").hidden = false;
  $("ccBody").innerHTML = `<div class="ap-empty">Generating your post…</div>`;
  let sug;
  try { sug = (await api(`/api/content/suggestion/generate?insight_id=${encodeURIComponent(insightId)}`, { method: "POST" })).suggestion; }
  catch (e) { $("ccBody").innerHTML = `<div class="card">${esc(e.message)}</div>`; return; }
  renderContentEditor(sug);
}

let _ccData = null;
function renderContentEditor(sug) {
  _ccData = { ...sug };
  const tags = (sug.hashtags || []).map((t) => "#" + String(t).replace(/^#/, "")).join(" ");
  $("ccBody").innerHTML = `
    <div class="cc-grid">
      <div class="cc-image-col">
        ${sug.image_url ? `<img src="${esc(sug.image_url)}" alt="post image" class="cc-image" />`
                        : `<div class="cc-image cc-image-empty">No image</div>`}
        <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
          <button class="btn ghost sm" id="ccRegenImg">🎨 Regenerate</button>
          <button class="btn ghost sm" id="ccUploadImg">📁 Upload from device</button>
          <input type="file" id="ccImgFile" accept="image/png,image/jpeg,image/webp" hidden />
        </div>
        <label style="margin-top:10px;">Image URL <span class="muted tiny">(or paste a public URL)</span>
          <input id="ccImgUrl" value="${esc(sug.image_url || "")}" placeholder="https://… or /generated_images/…" />
        </label>
      </div>
      <div class="cc-fields">
        <label>Topic <input id="ccTopic" value="${esc(sug.topic || "")}" /></label>
        <label>Platform
          <select id="ccPlat">
            <option value="instagram" ${sug.platform==="instagram"?"selected":""}>Instagram</option>
            <option value="facebook"  ${sug.platform==="facebook"?"selected":""}>Facebook</option>
          </select>
        </label>
        <label>Caption <textarea id="ccCaption" rows="6">${esc(sug.caption || "")}</textarea></label>
        <label>Hashtags (space-separated) <textarea id="ccTags" rows="2">${esc(tags)}</textarea></label>
        <label>Description <textarea id="ccDesc" rows="3">${esc(sug.description || "")}</textarea></label>
      </div>
    </div>
    <div class="modal-actions cc-actions">
      <button class="btn ghost" id="ccCancel">Close</button>
      <button class="btn primary" id="ccPost">⬇ Save to device</button>
    </div>
    <div id="ccMsg" class="muted tiny" style="margin-top:8px;"></div>`;
  $("ccCancel").onclick = closeContentEditor;
  $("ccRegenImg").onclick = async () => {
    $("ccMsg").textContent = "Regenerating image (this can take a few seconds)…";
    try {
      const r = await api(`/api/content/regenerate-image?insight_id=${encodeURIComponent(sug.id)}`, { method: "POST" });
      _ccData.image_url = r.image_url; renderContentEditor(_ccData);
    } catch (e) { $("ccMsg").innerHTML = `<span style='color:var(--red)'>${esc(e.message)}</span>`; }
  };
  $("ccUploadImg").onclick = () => $("ccImgFile").click();
  $("ccImgFile").onchange = async (e) => {
    const f = e.target.files && e.target.files[0]; if (!f) return;
    $("ccMsg").textContent = `Uploading ${f.name}…`;
    const fd = new FormData(); fd.append("files", f);
    try {
      const r = await fetch(`/api/content/upload-image?insight_id=${encodeURIComponent(sug.id)}`,
        { method: "POST", headers: { "X-Session-Id": state.sessionId, "Authorization": "Bearer " + state.token }, body: fd });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "Upload failed");
      _ccData.image_url = d.image_url; renderContentEditor(_ccData);
      toast("✅ Image uploaded");
    } catch (err) { $("ccMsg").innerHTML = `<span style='color:var(--red)'>${esc(err.message)}</span>`; }
  };
  $("ccPost").onclick = async () => {
    const body = ccCollect();
    $("ccMsg").textContent = "Saving to your device…";
    await saveContentToDevice(body.insight_id);
    closeContentEditor();
  };
  // save edits on blur so the current suggestion always reflects what the user typed
  ["ccCaption","ccTags","ccDesc","ccTopic","ccPlat","ccImgUrl"].forEach((id) => {
    const el = $(id); if (!el) return; el.onchange = () => saveContentEdits(sug.id);
  });
}
function ccCollect() {
  const tagText = ($("ccTags").value || "").trim();
  const tags = tagText.split(/\s+/).filter(Boolean).map((t) => t.replace(/^#/, ""));
  return {
    insight_id: _ccData.id,
    caption: $("ccCaption").value || "",
    hashtags: tags,
    image_url: $("ccImgUrl").value || _ccData.image_url || "",
    platform: $("ccPlat").value || "instagram",
  };
}
async function saveContentEdits(insightId) {
  const body = { caption: $("ccCaption").value, hashtags: ccCollect().hashtags,
                 description: $("ccDesc").value, image_url: $("ccImgUrl").value,
                 platform: $("ccPlat").value, topic: $("ccTopic").value };
  try { await api(`/api/content/suggestion/${insightId}/edit`, { method: "POST", json: body }); } catch (e) {}
}
function closeContentEditor() { $("ccModal").hidden = true; _ccData = null; }
$("ccClose").onclick = closeContentEditor;

// ---------- store connect modal wiring ----------
// Guarded: if an older cached smart.html is ever served without the store-connect
// modal, missing elements must not throw and halt the rest of the script.
if ($("coClose")) $("coClose").onclick = closeCommerce;
if ($("coCancel")) $("coCancel").onclick = closeCommerce;
if ($("coConfirm")) $("coConfirm").onclick = async () => {
  if (!_coCtx) return;
  const creds = {};
  document.querySelectorAll("#coGrid [data-co-field]").forEach((el) => creds[el.dataset.coField] = el.value.trim());
  const el = $("coErr"); el.hidden = true;
  const btn = $("coConfirm"); const label = btn.textContent; btn.disabled = true; btn.textContent = "Connecting…";
  try {
    await api("/api/commerce/connect", { method: "POST", json: { connector: _coCtx.id, credentials: creds } });
    closeCommerce(); toast("✅ Connected — click “Pull orders” to import your sales."); renderChannels();
  } catch (e) { el.textContent = e.message; el.hidden = false; }
  finally { btn.disabled = false; btn.textContent = label; }
};

// Approving a content post saves the image + caption to the seller's device
// (Instagram auto-posting is upcoming), then moves the card to History.
async function saveContentToDevice(insightId) {
  try {
    const sug = (await api(`/api/content/suggestion/generate?insight_id=${encodeURIComponent(insightId)}`, { method: "POST" })).suggestion;
    const topic = (sug.topic || "post").replace(/\s+/g, "_").slice(0, 40) || "post";
    if (sug.image_url) {
      await download(`/api/content/asset?insight_id=${encodeURIComponent(insightId)}&kind=image`, `${topic}.png`);
    } else {
      toast("No image yet — saving the caption only. Open the editor to add an image.", 5000);
    }
    await download(`/api/content/asset?insight_id=${encodeURIComponent(insightId)}&kind=text`, `${topic}.txt`);
    const r = await api(`/api/smart/insight/${insightId}/decision`, { method: "POST", json: { decision: "approve" } });
    if (r && r.insights) {
      if (state.lastState) { state.lastState.insights = r.insights; if (r.history) state.lastState.history = r.history; }
      renderApprovals(r.insights);
    }
    toast("✅ Saved to your device — image + caption downloaded. Moved to History.");
  } catch (e) { toast(e.message, 6000); }
}

// ---------- store connectors (Shopify / Amazon) ----------
let _coCtx = null;

// ---------- Listed platforms strip (home) ----------
// One row for every place the seller's products can sell: their own website
// first, then the live marketplace connectors, then the ones we haven't built
// yet. The switch on each live channel decides whether that channel's sales are
// counted in analytics, forecasts and the approval panel.
async function renderChannels() {
  const strip = $("chanStrip");
  if (!strip) return;
  try {
    const d = await api("/api/channels");
    strip.innerHTML = d.channels.map((c) => {
      const soon = c.status === "soon";
      const live = c.status === "live";
      const connected = c.status === "connected";
      const pill = soon ? `<span class="chan-pill soon">Yet to come</span>`
        : live ? `<span class="chan-pill live">● Live</span>`
        : connected ? `<span class="chan-pill on">● Connected</span>`
        : c.status === "draft" ? `<span class="chan-pill draft">Draft</span>`
        : `<span class="chan-pill">Not connected</span>`;
      const actions = c.id === "site"
        ? `<button class="btn ${live ? "ghost" : "primary"} sm" data-chan-open="site">${c.detail && live ? "Open builder" : "Build my site"}</button>
           ${live ? `<a class="btn ghost sm" href="${esc(c.detail)}" target="_blank" rel="noopener">Visit ↗</a>` : ""}`
        : soon ? `<button class="btn ghost sm" disabled>Coming soon</button>`
        : connected
          ? `<button class="btn primary sm" data-co-pull="${c.id}">⬇ Pull orders</button>
             <button class="btn ghost sm" data-co-connect="${c.id}">Reconnect</button>
             <button class="btn ghost sm" data-co-disc="${c.id}">Disconnect</button>`
          : `<button class="btn primary sm" data-co-connect="${c.id}">🔗 Connect</button>`;
      return `
        <div class="chan-card ${soon ? "soon" : ""} ${c.id === "site" ? "own" : ""}">
          <div class="chan-top">
            <span class="chan-ico">${c.icon}</span>
            <div class="chan-name"><b>${esc(c.label)}</b>${pill}</div>
            <label class="site-toggle sm" title="${c.toggleable ? "Count this channel's sales in your insights" : "Available once this channel is live"}">
              <input type="checkbox" data-chan="${c.id}" ${c.enabled ? "checked" : ""} ${c.toggleable ? "" : "disabled"} />
              <span class="tsw"></span>
            </label>
          </div>
          <div class="chan-detail">${esc(c.detail || "")}${c.orders != null && c.orders > 0 ? ` · ${fmt(c.orders)} order${c.orders === 1 ? "" : "s"}` : ""}</div>
          <div class="chan-actions">${actions}</div>
        </div>`;
    }).join("");

    strip.querySelectorAll("[data-chan]").forEach((cb) => cb.onchange = async () => {
      try {
        await api("/api/channels/toggle", { method: "POST", json: { channel: cb.dataset.chan, enabled: cb.checked } });
        toast(cb.checked ? "Counted in your insights" : "Excluded from your insights");
        if (cb.dataset.chan === "site") goHome();
      } catch (e) { toast(e.message); cb.checked = !cb.checked; }
    });
    strip.querySelectorAll("[data-chan-open]").forEach((b) => b.onclick = () => openSite());
    const cat = await api("/api/commerce/status").catch(() => ({ connectors: [] }));
    strip.querySelectorAll("[data-co-connect]").forEach((b) => b.onclick = () => openCommerceModal(b.dataset.coConnect, cat.connectors));
    strip.querySelectorAll("[data-co-pull]").forEach((b) => b.onclick = () => commercePull(b.dataset.coPull));
    strip.querySelectorAll("[data-co-disc]").forEach((b) => b.onclick = () => commerceDisconnect(b.dataset.coDisc));
  } catch (e) {
    strip.innerHTML = `<div class="card">${esc(e.message)}</div>`;
  }
}

function openCommerceModal(id, connectors) {
  const c = (connectors || []).find((x) => x.id === id);
  if (!c) return;
  _coCtx = c;
  $("coTitle").textContent = `${c.icon} Connect ${c.label}`;
  $("coHelp").textContent = c.help || "";
  $("coGrid").innerHTML = (c.fields || []).map((f) => `
    <label>${esc(f.label)}
      <input data-co-field="${f.key}" type="${f.secret ? "password" : "text"}" placeholder="${esc(f.placeholder || "")}" autocomplete="off" />
    </label>`).join("");
  $("coErr").hidden = true;
  $("coModal").hidden = false;
}
function closeCommerce() { $("coModal").hidden = true; _coCtx = null; }

async function commercePull(id) {
  toast("Pulling orders… this can take a few seconds", 8000);
  try {
    const r = await api("/api/commerce/pull", { method: "POST", json: { connector: id, days: 90 } });
    toast(`✅ Pulled ${fmt(r.rows)} orders from ${id} → saved as Sales.`);
    goHome();
  } catch (e) { toast(e.message, 7000); }
}
async function commerceDisconnect(id) {
  try { await api("/api/commerce/disconnect", { method: "POST", json: { connector: id, credentials: {} } }); toast("Disconnected"); renderChannels(); }
  catch (e) { toast(e.message); }
}

// ---------- MODULE: Ad Analytics ----------
async function openAdsModule() {
  moduleShell("Ad Analytics", `<div class="ap-empty">Loading…</div>`);
  try {
    const d = await api("/api/ads/connectors");
    let html = `<div class="card"><p class="muted tiny">Connect each ad account once — free platforms will start pulling live data in the next update; paid ones show a demo dashboard for now.</p></div>
      <div class="ads-grid">${d.connectors.map((c) => `
        <div class="ads-card ${c.connected ? "connected" : ""}">
          <div class="row" style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:22px;">${c.icon}</span>
            <div style="flex:1;"><b>${esc(c.label)}</b> <span class="pill-${c.tier}">${esc(c.tier)}</span>
              <div class="muted tiny">${esc(c.help)}</div>
            </div>
          </div>
          <div class="row" style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
            ${c.connected ? `<button class="btn ghost sm" data-ads-view="${c.id}">${sic("chart")}View metrics</button>
                              <button class="btn ghost sm" data-ads-dc="${c.id}">Disconnect</button>` :
                              `<button class="btn primary sm" data-ads-conn="${c.id}">Connect</button>`}
          </div>
        </div>`).join("")}</div>
      <div id="adsMetrics"></div>`;
    setView(`<div class="page-head"><h2>Ad Analytics</h2><button class="btn ghost sm" id="backHome">← All apps</button></div>${html}`);
    $("backHome").onclick = goHome;
    document.querySelectorAll("[data-ads-conn]").forEach((b) => b.onclick = () => connectAds(b.dataset.adsConn));
    document.querySelectorAll("[data-ads-dc]").forEach((b) => b.onclick = async () => { await api("/api/ads/disconnect", { method: "POST", json: { connector: b.dataset.adsDc, credentials: {} } }); openAdsModule(); });
    document.querySelectorAll("[data-ads-view]").forEach((b) => b.onclick = () => viewAdsMetrics(b.dataset.adsView));
  } catch (e) { moduleShell("Ad Analytics", `<div class="card">${esc(e.message)}</div>`); }
}

async function connectAds(id) {
  const label = prompt("Paste the credentials for " + id + " as key=value pairs (comma-separated), or hit OK for demo:");
  const creds = {};
  if (label) label.split(",").forEach((p) => { const [k, v] = p.split("="); if (k) creds[k.trim()] = (v || "").trim(); });
  try { await api("/api/ads/connect", { method: "POST", json: { connector: id, credentials: creds } }); toast("✓ Connected"); openAdsModule(); }
  catch (e) { toast(e.message); }
}

async function viewAdsMetrics(id) {
  const m = await api(`/api/ads/metrics?connector=${id}&days=30`);
  const t = m.totals;
  $("adsMetrics").innerHTML = `<div class="card">
    <h3 style="margin:0 0 6px;">${esc(id)} — last ${m.range.days} days ${m.mode === "demo" ? "<span class='pill-off'>demo</span>" : "<span class='pill-on'>live</span>"}</h3>
    <p class="muted tiny">${esc(m.note || "")}</p>
    <div class="kpis" style="margin-top:8px;">
      <div class="kpi"><div class="label">Spend</div><div class="value">₹${fmt(t.spend)}</div></div>
      <div class="kpi"><div class="label">Impressions</div><div class="value">${fmt(t.impressions)}</div></div>
      <div class="kpi"><div class="label">Clicks</div><div class="value">${fmt(t.clicks)}</div></div>
      <div class="kpi"><div class="label">CTR</div><div class="value">${t.ctr_pct}%</div></div>
      <div class="kpi"><div class="label">Conversions</div><div class="value">${fmt(t.conversions)}</div></div>
      <div class="kpi"><div class="label">Revenue</div><div class="value">₹${fmt(t.revenue)}</div></div>
      <div class="kpi"><div class="label">ROAS</div><div class="value">${t.roas}x</div></div>
      <div class="kpi"><div class="label">CPC</div><div class="value">₹${t.cpc}</div></div>
    </div>
    <div class="chart-card" style="margin-top:14px;"><h4>Daily spend vs revenue</h4><div class="plot" id="adsCh"></div></div>
    <div class="card"><h4 style="margin-bottom:6px;">Top campaigns</h4>
      <div class="table-scroll"><table><thead><tr><th>Campaign</th><th>Spend</th><th>Clicks</th><th>Conv.</th><th>Revenue</th><th>ROAS</th></tr></thead>
      <tbody>${m.campaigns.map((r) => `<tr><td><b>${esc(r.name)}</b></td><td>₹${fmt(r.spend)}</td><td>${fmt(r.clicks)}</td><td>${fmt(r.conversions)}</td><td>₹${fmt(r.revenue)}</td><td>${r.roas}x</td></tr>`).join("")}</tbody></table></div>
    </div>
  </div>`;
  const d = m.daily;
  plot($("adsCh"), [
    { x: d.dates, y: d.spend, type: "scatter", mode: "lines", name: "Spend", line: { color: cssVar("--primary", "#6d28d9") } },
    { x: d.dates, y: d.revenue, type: "scatter", mode: "lines", name: "Revenue", line: { color: cssVar("--green", "#0a7a4d") } },
  ], { yaxis: { tickprefix: "₹" } }, "Daily spend vs revenue");
}

// =========================================================================
// MODULE: Website Builder
//
// Five steps, with Back / Next at the bottom of each so the seller is never
// hunting for the tab bar. Step three is the real workbench: the live site on
// the left, an inspector on the right, and a two-way bridge between them —
// click a photo, a headline or the footer on the site and the matching controls
// open beside it; change a control and the site repaints without a reload.
// =========================================================================
let _site = null;        // the working copy the seller is editing
let _siteMeta = null;    // themes, fonts, icons, counts, stats from the server
let _step = "setup";
let _siteDirty = false;
let _pairings = null;      // curated font pairings, fetched once per theme
let _openGroup = "hero";
let _frameReady = false;
let _liveTimer = null;

const STEPS = [
  { id: "setup",    label: "Setup",     hint: "Name, address, contact" },
  { id: "theme",    label: "Theme",     hint: "Pick the look" },
  { id: "editor",   label: "Design",    hint: "Edit on the live site" },
  { id: "checkout", label: "Checkout",  hint: "Shipping, tax, payment" },
  { id: "publish",  label: "Publish",   hint: "Go live" },
];
const stepIndex = () => STEPS.findIndex((s) => s.id === _step);

async function openSite(step) {
  moduleShell("Website Builder", `<div class="ap-empty">Loading your site…</div>`);
  try {
    let d = await api("/api/site/state");
    // The brand, the products, the photos and the copy already exist in Product
    // Management. Opening on five steps of blank fields asks the seller to type
    // things the app already knows — so fill them once, from what is there, and
    // open on a site they edit rather than a form they complete.
    if (!d.site.seeded) {
      try { d = await api("/api/site/seed", { method: "POST" }); }
      catch (e) { /* an unseedable site is still a usable one */ }
    }
    _siteMeta = d;
    _site = JSON.parse(JSON.stringify(d.site));
    if (!_site.handle) _site.handle = d.suggested_handle;
    await loadPairings();
    _siteDirty = false; _frameReady = false;
    _step = step || (_site.handle && _site.brand ? "editor" : "setup");
    renderSite();
    if (d.seeded_now) {
      toast("Started your site from your catalogue — change anything you like.", 6000);
    }
  } catch (e) { moduleShell("Website Builder", `<div class="card">${esc(e.message)}</div>`); }
}

function themeLabel() {
  const t = (_siteMeta && _siteMeta.themes || []).find((x) => x.id === _site.theme);
  return (t && t.label) ? t.label.toLowerCase() : "this theme";
}

async function loadPairings() {
  try {
    const d = await api(`/api/site/pairings?theme=${encodeURIComponent(_site.theme || "")}`);
    _pairings = d.pairings || [];
  } catch (e) { _pairings = []; }
}

/** SVG from the shared icon set (same drawings the storefront uses). */
function sic(name, cls) {
  const path = ICONS[name]
    || (_siteMeta && _siteMeta.icons && _siteMeta.icons[name]) || "";
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round"${cls ? ` class="${cls}"` : ""}>${path}</svg>`;
}

function siteMark() {
  const was = _siteDirty;
  _siteDirty = true;
  const b = $("siteSave");
  if (b) { b.disabled = false; b.textContent = "Save"; }
  const d = $("siteDirty");
  if (d && !was) {
    d.outerHTML = saveState(_site.published && _site.handle);
  }
  pushLive();
}

/* Where this site stands, always on screen.

   Silent autosave is right; invisible autosave is not. Three states, and the
   seller should never have to guess which one they are looking at:
     Unsaved   — edits in the browser that the server has not seen
     Draft     — saved, but no shopper can reach it
     Published — what the world sees right now, and whether the draft is ahead
   The third case is the one that used to be impossible to tell: a saved
   change on a live site is NOT live until Publish is pressed again. */
function saveState(live) {
  if (_siteDirty) {
    return `<span class="save-state unsaved" id="siteDirty" title="Not saved to the server yet">
      <i></i>Unsaved changes</span>`;
  }
  if (!live) {
    return `<span class="save-state draft" id="siteDirty" title="Saved, but nobody can reach it yet">
      <i></i>Draft — saved</span>`;
  }
  const ahead = _siteMeta && _siteMeta.site &&
    _siteMeta.site.updated_at && _site.published_at &&
    _siteMeta.site.updated_at > _site.published_at;
  return ahead
    ? `<span class="save-state ahead" id="siteDirty" title="Saved changes are not live until you publish">
        <i></i>Saved — not live yet</span>`
    : `<span class="save-state live" id="siteDirty" title="This is what shoppers see">
        <i></i>Published</span>`;
}

function renderSite() {
  const live = _site.published && _site.handle;
  const url = _site.handle ? `/s/${_site.handle}` : "";

  const rail = STEPS.map((st, i) => {
    const done = i < stepIndex();
    return `<button class="wz ${_step === st.id ? "on" : ""} ${done ? "done" : ""}" data-step="${st.id}">
        <span class="wz-n">${done ? "✓" : i + 1}</span>
        <span class="wz-t"><b>${st.label}</b><i>${st.hint}</i></span>
      </button>`;
  }).join("");

  const bar = `
    <div class="site-bar">
      <div class="site-bar-l">
        <span class="site-dot ${live ? "live" : ""}"></span>
        <div>
          <b>${esc(_site.brand || "Your website")}</b>
          <div class="muted tiny">${live
            ? `Live at <a href="${esc(url)}" target="_blank" rel="noopener">${esc(location.origin + url)}</a>`
            : "Draft — only you can see it"}</div>
        </div>
      </div>
      <div class="site-bar-r">
        ${saveState(live)}
        <button class="btn ghost sm" id="siteSave" ${_siteDirty ? "" : "disabled"}>${_siteDirty ? "Save" : "Saved"}</button>
        <button class="btn ${live ? "ghost" : "primary"} sm" id="sitePub">${live ? "Unpublish" : "Publish"}</button>
      </div>
    </div>`;

  moduleShell("Website Builder", bar + `<div class="wz-rail">${rail}</div><div id="siteBody"></div>`);
  $("siteSave").onclick = saveSite;
  $("sitePub").onclick = togglePublish;
  document.querySelectorAll("[data-step]").forEach((b) => b.onclick = () => goStep(b.dataset.step));
  renderStep();
}

async function goStep(id) {
  // The live canvas loads the real site, and the site only has an address once
  // it has been saved once. Entering Design saves silently so the seller never
  // has to publish (step 5) just to see step 3.
  if (id === "editor" && (_siteDirty || !_siteMeta.site.handle)) {
    if (!_site.brand) _site.brand = _site.brand || (state.email || "My store").split("@")[0];
    await saveSite({ quiet: true });
  }
  _step = id; _frameReady = false;
  renderSite();
  const main = document.querySelector(".main");
  if (main) main.scrollTo({ top: 0, behavior: "smooth" });
}

function stepNav() {
  const i = stepIndex();
  const prev = i > 0 ? STEPS[i - 1] : null;
  const next = i < STEPS.length - 1 ? STEPS[i + 1] : null;
  return `<div class="wz-nav">
      ${prev ? `<button class="btn ghost" data-step="${prev.id}">← ${esc(prev.label)}</button>` : `<span></span>`}
      <span class="muted tiny">Step ${i + 1} of ${STEPS.length}</span>
      ${next ? `<button class="btn primary" data-step="${next.id}">${esc(next.label)} →</button>`
             : `<button class="btn primary" id="wzFinish">Finish</button>`}
    </div>`;
}

function renderStep() {
  const b = $("siteBody");
  if (_step === "setup") b.innerHTML = stepSetup() + stepNav();
  else if (_step === "theme") b.innerHTML = stepTheme() + stepNav();
  else if (_step === "editor") b.innerHTML = stepEditor() + stepNav();
  else if (_step === "checkout") b.innerHTML = stepCheckout() + stepNav();
  else b.innerHTML = stepPublish() + stepNav();
  wireStep();
  document.querySelectorAll("#siteBody [data-step]").forEach((n) => n.onclick = () => goStep(n.dataset.step));
  const fin = $("wzFinish");
  if (fin) fin.onclick = async () => { if (_siteDirty) await saveSite(); goHome(); };
}

/* ---- bind any [data-bind="a.b"] control straight onto the site document ---- */
function bindPath(path, value) {
  const parts = path.split(".");
  let o = _site;
  for (let i = 0; i < parts.length - 1; i++) o = o[parts[i]];
  o[parts[parts.length - 1]] = value;
  siteMark();
}
function readPath(path) { return path.split(".").reduce((o, k) => (o == null ? o : o[k]), _site); }

function wireBinds(scope) {
  (scope || document).querySelectorAll("[data-bind]").forEach((n) => {
    if (n._bound) return; n._bound = true;
    const path = n.dataset.bind;
    const ev = n.type === "checkbox" || n.tagName === "SELECT" || n.type === "color" ? "change" : "input";
    n.addEventListener(ev, () => {
      let v = n.type === "checkbox" ? n.checked : n.value;
      if (n.dataset.num) v = v === "" ? 0 : parseFloat(v);
      bindPath(path, v);
      if (n.type === "range") { const out = $(n.id + "Out"); if (out) out.textContent = n.value; }
    });
  });
}

function field(label, path, opts = {}) {
  const v = readPath(path);
  const hint = opts.hint ? ` <span class="muted tiny">${opts.hint}</span>` : "";
  if (opts.type === "textarea")
    return `<label>${label}${hint}<textarea rows="${opts.rows || 3}" data-bind="${path}" placeholder="${esc(opts.ph || "")}">${esc(v || "")}</textarea></label>`;
  if (opts.type === "check")
    return `<label class="inline-check"><input type="checkbox" data-bind="${path}" ${v ? "checked" : ""} /> ${label}${hint}</label>`;
  if (opts.type === "select")
    return `<label>${label}${hint}<select data-bind="${path}">${opts.options.map((o) =>
      `<option value="${esc(o[0])}" ${String(v) === String(o[0]) ? "selected" : ""}>${esc(o[1])}</option>`).join("")}</select></label>`;
  if (opts.type === "range") {
    const id = "rng_" + path.replace(/\./g, "_");
    return `<label>${label}
      <span class="rng-val"><b id="${id}Out">${v == null ? opts.def : v}</b>${opts.hint ? ` <span class="muted tiny">${opts.hint}</span>` : ""}</span>
      <input type="range" id="${id}" data-bind="${path}" data-num="1" min="${opts.min}" max="${opts.max}" step="${opts.step || 1}" value="${v == null ? opts.def : v}" /></label>`;
  }
  return `<label>${label}${hint}<input type="${opts.type || "text"}" data-bind="${path}" ${opts.num ? 'data-num="1" min="0" step="any"' : ""} value="${esc(v == null ? "" : v)}" placeholder="${esc(opts.ph || "")}" /></label>`;
}

/* ============================== STEP 1: SETUP ============================ */
function stepSetup() {
  return `
  <div class="card sup-form form-v">
    <div class="sup-sub">Your brand</div>
    <div class="sup-form-grid">
      ${field("Brand name", "brand", { ph: "Aureva" })}
      ${field("Tagline", "tagline", { hint: "(one line, shown under the logo)", ph: "Handmade fragrance, made in Bengaluru" })}
      ${imageField("siteLogo", _site.logo_url, "Logo", "square or wide, transparent PNG works best")}
    </div>

    <div class="sup-sub">Web address</div>
    <p class="muted tiny" style="margin:0 0 10px;">Your site lives here today. A domain of your own can be attached later — this address keeps working either way.</p>
    <div class="handle-row">
      <span class="handle-pre">${esc(location.origin)}/s/</span>
      <input id="siteHandle" value="${esc(_site.handle || "")}" placeholder="your-brand" />
      <span class="handle-state" id="handleState"></span>
    </div>

    <div class="sup-sub">Contact shown on your site</div>
    <div class="sup-form-grid">
      ${field("Email", "contact.email", { type: "email" })}
      ${field("Phone", "contact.phone", { ph: "+91 …" })}
      ${field("WhatsApp number", "contact.whatsapp", { hint: "(digits only)", ph: "919876543210" })}
      ${field("Instagram handle", "contact.instagram", { ph: "@yourbrand" })}
      ${field("Address", "contact.address", { type: "textarea", rows: 2 })}
    </div>
  </div>`;
}

/* ============================== STEP 2: THEME ============================ */
function stepTheme() {
  const cards = _siteMeta.themes.map((t) => {
    const sel = _site.theme === t.id;
    const p = t.light;
    return `
      <div class="theme-card ${sel ? "sel" : ""}" data-theme-pick="${t.id}">
        <div class="tc-mock" style="background:${p.bg};border-color:${p.border}">
          <div class="tc-row"><span class="tc-dot" style="background:${p.accent}"></span>
            <span class="tc-nav" style="background:${p.border}"></span><span class="tc-nav" style="background:${p.border}"></span></div>
          <div class="tc-title" style="color:${p.ink};font-family:${esc(fontStack(t.fonts.heading))};letter-spacing:${(t.layout.track || 0) / 100}em;text-transform:${t.layout.case === "upper" ? "uppercase" : "none"}">${esc(t.label)}</div>
          <div class="tc-lines"><i style="background:${p.muted};opacity:.4"></i><i style="background:${p.muted};opacity:.4;width:52%"></i></div>
          <div class="tc-grid">
            <span style="background:${p.surface};border-color:${p.border};border-radius:${Math.min(8, t.layout.radius)}px"></span>
            <span style="background:${p.surface};border-color:${p.border};border-radius:${Math.min(8, t.layout.radius)}px"></span>
            <span style="background:${p.surface};border-color:${p.border};border-radius:${Math.min(8, t.layout.radius)}px"></span>
          </div>
          <div class="tc-btn" style="background:${p.accent};color:${p.accent_ink};border-radius:${Math.min(8, t.layout.radius)}px">Shop</div>
        </div>
        <div class="tc-body">
          <div class="tc-head"><b>${esc(t.label)}</b>${sel ? `<span class="chan-pill live">Selected</span>` : ""}</div>
          <div class="muted tiny" style="margin:2px 0 7px;">${esc(t.genre)}</div>
          <p class="muted tiny">${esc(t.blurb)}</p>
          <div class="motion-chips">${t.motion.map((m) => `<span>${esc(MOTION_LABEL[m] || m)}</span>`).join("")}</div>
        </div>
      </div>`;
  }).join("");
  return `<p class="muted" style="margin:6px 0 16px;">Each theme is a different website — its own layout, type scale and motion, not a colour swap. Pick the closest one; you can change every detail in the next step.</p>
    <div class="theme-grid">${cards}</div>`;
}

const MOTION_LABEL = {
  reveal: "Fade-up on scroll", parallax: "Parallax", hscroll: "Horizontal rails",
  pin: "Pinned sections", marquee: "Scrolling band", zoom: "Image zoom",
  split: "Headline rise", mask: "Mask reveal", shine: "Shine sweep", drift: "Drifting gradient",
};
function fontStack(id) {
  const f = (_siteMeta.fonts || []).find((x) => x.id === id);
  return f ? f.stack : "system-ui, sans-serif";
}
function fontLabel(id) {
  const f = (_siteMeta.fonts || []).find((x) => x.id === id);
  return f ? f.label : id;
}

/* ====================== STEP 3: SIDE-BY-SIDE EDITOR ====================== */
const GROUPS = [
  { key: "brand",        label: "Brand & logo",     body: gBrand },
  { key: "announcement", label: "Announcement bar", body: gAnnounce },
  { key: "hero",         label: "Hero",             body: gHero },
  { key: "__type",       label: "Typography",       body: gType },
  { key: "__colour",     label: "Colour",           body: gColour },
  { key: "__shape",      label: "Shape & motion",   body: gShape },
  { key: "highlights",   label: "Promise strip",    body: gHighlights },
  { key: "spotlight",    label: "Spotlight product", body: gSpotlight },
  { key: "categories",   label: "Category rail",    body: gCategories },
  { key: "featured",     label: "Featured rail",    body: gFeatured },
  { key: "stats",        label: "Numbers",          body: gStats },
  { key: "products",     label: "Product grid",     body: gProducts },
  { key: "gallery",      label: "Lookbook",         body: gGallery },
  { key: "story",        label: "Our story",        body: gStory },
  { key: "manifesto",    label: "Statement",        body: gManifesto },
  { key: "drop",         label: "Scarcity block",   body: gDrop },
  { key: "testimonials", label: "Reviews",          body: gTestimonials },
  { key: "newsletter",   label: "Newsletter",       body: gNewsletter },
  { key: "footer",       label: "Footer & contact", body: gFooter },
];

function stepEditor() {
  if (!_site.handle) return `<div class="ap-empty">Give your site an address in <b>Setup</b> first.</div>` ;
  const src = `/s/${encodeURIComponent(_site.handle)}?preview=${encodeURIComponent(state.token || "")}&edit=1`;
  const groups = GROUPS.map((g) => `
    <section class="insp-g ${_openGroup === g.key ? "open" : ""}" data-group="${g.key}">
      <button class="insp-h" data-ghead="${g.key}"><span>${esc(g.label)}</span>${sic("chevron-down")}</button>
      <div class="insp-b"><div class="insp-in">${g.body()}</div></div>
    </section>`).join("");

  return `
  <div class="ed-shell">
    <div class="ed-canvas">
      <div class="ed-toolbar">
        <div class="ed-devices">
          <button class="on" data-dev="desktop">Desktop</button>
          <button data-dev="tablet">Tablet</button>
          <button data-dev="phone">Phone</button>
        </div>
        <div class="ed-routes">
          <button class="on" data-route="home">Home</button>
          <button data-route="shop">Shop</button>
          <button data-route="product">Product</button>
        </div>
        <div class="ed-tools">
          <button class="btn ghost tiny" id="edReload">Reload</button>
          <a class="btn ghost tiny" href="${esc(src)}" target="_blank" rel="noopener">Open ↗</a>
        </div>
      </div>
      <div class="ed-stage" id="edStage"><iframe id="edFrame" src="${esc(src)}" title="Live site"></iframe></div>
      <p class="ed-hint muted tiny">Click anything on the site — a photo, a headline, the footer — and its controls open on the right.</p>
    </div>
    <aside class="ed-panel">
      <div class="ed-panel-head">
        <b>Editing</b>
        <span class="muted tiny" id="edSel">Nothing selected</span>
      </div>
      <div class="ed-groups" id="edGroups">${groups}</div>
    </aside>
  </div>`;
}

/* ---- inspector groups ---- */
function gBrand() {
  return `<div class="sup-form-grid">
    ${field("Brand name", "brand", { ph: "Aureva" })}
    ${field("Tagline", "tagline", { ph: "Small-batch perfume" })}
    ${imageField("edLogo", _site.logo_url, "Logo", "")}
  </div>`;
}
function gAnnounce() {
  return `<div class="sup-form-grid">
    ${field("Announcement text", "announcement", { hint: "(leave blank to hide the bar)", ph: "Free shipping over ₹999" })}
  </div>`;
}
function gHero() {
  const hasVid = !!_site.hero.video_url;
  return `
  ${hasVid ? "" : `<div class="nudge">${sic("spark")}<div><b>Add a hero clip</b>
    Eight seconds of your product moving does more than any amount of styling.
    MP4 or WEBM, 1080p, under 48MB.</div></div>`}
  <div class="sup-form-grid">
    ${mediaWarning()}
    ${imageField("edHeroVid", _site.hero.video_url, "Hero video", "plays muted on loop behind the headline", true)}
    ${imageField("edHero", _site.hero.image_url, "Hero image", hasVid ? "used as the video's poster frame" : "wide, at least 1600px")}
    ${field("Headline", "hero.heading", { ph: "Scent that stays with you" })}
    ${field("Sub-headline", "hero.sub", { type: "textarea", rows: 2 })}
    ${field("Button text", "hero.cta_text", { ph: "Shop now" })}
    ${field("Alignment", "hero.align", { type: "select", options: [["left", "Left"], ["center", "Centred"]] })}
    ${field("Image darkening", "hero.overlay", { type: "range", min: 0, max: 90, def: 45, hint: "%" })}
  </div>`;
}
function gType() {
  const t = _siteMeta.themes.find((x) => x.id === _site.theme) || _siteMeta.themes[0];
  const opts = (sel) => _siteMeta.fonts.map((f) =>
    `<option value="${f.id}" ${sel === f.id ? "selected" : ""}>${esc(f.label)} · ${f.kind}</option>`).join("");
  const cur = (id, fallback) => fontStack(id || fallback);
  const chosen = _site.style.pairing || "";
  const hand = !chosen && (_site.style.heading_font || _site.style.body_font || _site.style.accent_font);
  // Three free-choice dropdowns across thirty-five families is forty-two
  // thousand combinations, most of them bad, offered to a seller who never
  // asked to become a typographer. Pairings first; the dropdowns stay, one
  // click away, for the seller who does want them.
  return `
  <p class="muted tiny" style="margin:0 0 12px;">Pick a pairing — a display face, the body face
  that sits under it, and the small face for buttons and prices. All three at once, chosen to
  work together.</p>
  <div class="pairs" id="pairGrid">${(_pairings || []).map((pr) => `
    <button type="button" class="pair${chosen === pr.id ? " on" : ""}" data-pair="${esc(pr.id)}">
      <span class="pair-demo" style="font-family:${esc(pr.heading_stack)}">${esc(_site.brand || "Aa")}</span>
      <span class="pair-body" style="font-family:${esc(pr.body_stack)}">The quick brown fox</span>
      <span class="pair-lbl" style="font-family:${esc(pr.accent_stack)}">Shop the collection</span>
      <span class="pair-meta"><b>${esc(pr.name)}</b>${pr.recommended
        ? `<i class="pair-rec">suits ${esc(themeLabel())}</i>` : ""}</span>
      <span class="pair-note">${esc(pr.note)}</span>
    </button>`).join("") || `<div class="ap-empty">Loading pairings…</div>`}</div>
  <button type="button" class="btn ghost sm" id="pairOwn" style="margin:12px 0 4px;">
    ${hand ? "Hide the individual faces" : "Choose each face myself"}</button>
  <div id="typeManual" ${hand ? "" : "hidden"}>
  <p class="muted tiny" style="margin:10px 0 12px;">Three roles. <b>Display</b> is every headline,
  <b>body</b> is the reading text, and <b>labels</b> is the small uppercase type on eyebrows,
  buttons and prices.</p>
  <div class="sup-form-grid">
    <label>Display<select data-bind="style.heading_font"><option value="">Theme default (${esc(fontLabel(t.fonts.heading))})</option>${opts(_site.style.heading_font)}</select></label>
    <div class="type-prev" style="font-family:${esc(cur(_site.style.heading_font, t.fonts.heading))};font-size:26px;letter-spacing:${(_site.style.heading_track != null ? _site.style.heading_track : (t.layout.track || 0)) / 100}em;${t.layout.case === "upper" ? "text-transform:uppercase;" : ""}">${esc(_site.brand || "Your headline")}</div>

    <label>Body<select data-bind="style.body_font"><option value="">Theme default (${esc(fontLabel(t.fonts.body))})</option>${opts(_site.style.body_font)}</select></label>
    <div class="type-prev sm" style="font-family:${esc(cur(_site.style.body_font, t.fonts.body))}">The quick brown fox jumps over the lazy dog.</div>

    <label>Labels &amp; buttons<select data-bind="style.accent_font"><option value="">Same as body</option>${opts(_site.style.accent_font)}</select></label>
    <div class="type-prev lbl" style="font-family:${esc(cur(_site.style.accent_font, _site.style.body_font || t.fonts.body))}">Shop the collection</div>
  </div>
  </div>
  <div class="sup-sub">Fine tuning</div>
  <div class="sup-form-grid">
    ${field("Display size", "style.heading_scale", { type: "range", min: 75, max: 145, def: 100, hint: "%" })}
    ${field("Display weight", "style.heading_weight", { type: "select", options: [["", "Theme default"], [300, "Light"], [400, "Regular"], [500, "Medium"], [600, "Semibold"], [700, "Bold"], [800, "Extrabold"], [900, "Black"]] })}
    ${field("Display letter-spacing", "style.heading_track", { type: "range", min: -8, max: 30, def: t.layout.track || 0, hint: "/100 em" })}
    ${field("Body size", "style.body_scale", { type: "range", min: 88, max: 118, def: 100, hint: "%" })}
  </div>`;
}
function gColour() {
  const t = _siteMeta.themes.find((x) => x.id === _site.theme) || _siteMeta.themes[0];
  return `<div class="sup-form-grid">
    <label>Accent — light mode
      <span class="colour-row"><input type="color" data-bind="style.accent" value="${esc(_site.style.accent || t.light.accent)}" />
      <button type="button" class="btn ghost tiny" data-reset="style.accent">Theme colour</button></span></label>
    <label>Accent — dark mode
      <span class="colour-row"><input type="color" data-bind="style.accent_dark" value="${esc(_site.style.accent_dark || t.dark.accent)}" />
      <button type="button" class="btn ghost tiny" data-reset="style.accent_dark">Theme colour</button></span></label>
    ${field("Colour mode", "style.mode", { type: "select", options: [["auto", "Follow the visitor's device"], ["light", "Always light"], ["dark", "Always dark"]] })}
  </div>`;
}
function gShape() {
  const t = _siteMeta.themes.find((x) => x.id === _site.theme) || _siteMeta.themes[0];
  return `<div class="sup-form-grid">
    ${field("Corner radius", "style.radius", { type: "range", min: 0, max: 28, def: t.layout.radius, hint: "px" })}
    ${field("Animation", "style.motion", { type: "select", options: [["full", "Full — everything this theme does"], ["subtle", "Subtle — fades and rails only"], ["none", "None — completely static"]] })}
    ${field("Page width", "style.width", { type: "select", options: [["wide", "Wide"], ["compact", "Compact"], ["full", "Edge to edge"]] })}
    ${field("Show a loading screen on first visit", "style.preloader", { type: "check", hint: "— your name, a counter, then the site" })}
  </div>
  <p class="muted tiny">${esc(t.label)} animates with: ${t.motion.map((m) => MOTION_LABEL[m] || m).join(" · ")}.</p>`;
}
function gHighlights() {
  return `${field("Show the promise strip", "sections.highlights", { type: "check" })}
    <div id="hlEditor" class="rep-list"></div>`;
}
function gSpotlight() {
  return `${field("Show the spotlight", "sections.spotlight", { type: "check" })}
    <p class="muted tiny">Puts your first listed product against a sticky photo, with its own copy and
    key points. Everything shown here comes from that product in <b>Product Management</b> —
    give it a clip there and it plays in the spotlight.</p>`;
}

function gCategories() {
  return `${field("Show the category rail", "sections.categories", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Label", "copy.cat_eyebrow", { ph: "Browse" })}
      ${field("Heading", "copy.cat_title", { ph: "Shop by category" })}
    </div>
    <p class="muted tiny">Categories come from the Category field on each product, and each tile uses that category's first photo.</p>`;
}
function gFeatured() {
  return `${field("Show the featured rail", "sections.featured", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Label", "copy.feat_eyebrow", { ph: "Handpicked" })}
      ${field("Heading", "copy.feat_title", { ph: "Featured" })}
    </div>
    <p class="muted tiny">The first ten products you have listed, in name order.</p>`;
}

function gStats() {
  return `${field("Show the numbers band", "sections.stats", { type: "check" })}
    <div class="sup-form-grid">${field("Label", "copy.stats_eyebrow", { ph: "By the numbers" })}</div>
    <p class="muted tiny">Each figure counts itself up the first time a visitor scrolls past it.
    Write it however you like — “2,400+”, “6 weeks”, “4.9”.</p>
    <div id="stEditor" class="rep-list"></div>`;
}

function gGallery() {
  const n = (_site.gallery || []).length;
  return `${field("Show the lookbook", "sections.gallery", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Label", "copy.gallery_eyebrow", { ph: "Lookbook" })}
      ${field("Heading", "copy.gallery_title", { ph: "In the wild" })}
    </div>
    ${n ? "" : `<div class="nudge">${sic("image")}<div><b>Add four or five photos</b>
      Your product being used, held, worn, opened. Clips work here too — they autoplay
      muted in the rail.</div></div>`}
    <div id="glEditor" class="gal-wrap"></div>`;
}

function gManifesto() {
  return `${field("Show the statement", "sections.manifesto", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Statement", "manifesto", { type: "textarea", rows: 3, ph: "We make small batches, rest them properly, and stop when the batch is done." })}
    </div>
    <p class="muted tiny">One sentence, set large. It brightens word by word as the visitor scrolls
    through it — keep it short and it lands.</p>`;
}

function gDrop() {
  return `${field("Show the scarcity block", "sections.drop", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Label", "copy.drop_eyebrow", { ph: "Limited" })}
      ${field("Heading", "copy.drop_title", { ph: "When it's gone, it's gone" })}
    </div>
    <p class="muted tiny">Reads your real stock: whichever listed product has the fewest units left
    is the one it counts down, with a bar that fills as it scrolls into view. It hides itself when
    nothing is running low.</p>`;
}
function gProducts() {
  const t = _siteMeta.themes.find((x) => x.id === _site.theme) || _siteMeta.themes[0];
  return `<div class="sup-form-grid">
      ${field("Label", "copy.all_eyebrow", { ph: "Catalogue" })}
      ${field("Heading", "copy.all_title", { ph: "All products" })}
      ${field("Shop page heading", "copy.shop_title", { ph: "Everything we sell" })}
    </div>
    ${field("Product layout", "style.card_style", { type: "select", options: [["", `Theme default (${t.layout.grid})`], ["cards", "Cards — square photos in a grid"], ["editorial", "Editorial — tall photos, no borders"], ["list", "List — a menu-style row per product"]] })}
    <p class="muted tiny">Photos, prices and stock live in <b>Product Management</b>. ${fmt(_siteMeta.counts.listed)} product${_siteMeta.counts.listed === 1 ? "" : "s"} listed${_siteMeta.counts.no_image ? `, ${fmt(_siteMeta.counts.no_image)} still without a photo` : ""}.</p>
    <button class="btn ghost sm" id="edToProducts">Open Product Management →</button>`;
}
function gStory() {
  return `${field("Show this section", "sections.story", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Label", "copy.story_eyebrow", { ph: "About us" })}
      ${field("Title", "story.title", { ph: "Our story" })}
      ${field("Story", "story.body", { type: "textarea", rows: 5 })}
      ${imageField("edStory", _site.story.image_url, "Image", "")}
    </div>`;
}
function gTestimonials() {
  return `${field("Show customer reviews", "sections.testimonials", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Label", "copy.rev_eyebrow", { ph: "Reviews" })}
      ${field("Heading", "copy.rev_title", { ph: "What buyers say" })}
    </div>
    <div id="tsEditor" class="rep-list"></div>`;
}
function gNewsletter() {
  return `${field("Show the newsletter band", "sections.newsletter", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Heading", "copy.news_title", { ph: "Stay in the loop" })}
      ${field("Sub-line", "copy.news_sub", { ph: "New drops and offers. No spam, ever." })}
      ${field("Button", "copy.news_cta", { ph: "Join" })}
    </div>
    <p class="muted tiny">Sign-ups are collected on the page; wire them to your mailing tool whenever you're ready.</p>`;
}
function gFooter() {
  return `<div class="sup-form-grid">
    ${field("Email", "contact.email", { type: "email" })}
    ${field("Phone", "contact.phone")}
    ${field("WhatsApp number", "contact.whatsapp", { hint: "(digits only)" })}
    ${field("Instagram handle", "contact.instagram")}
    ${field("Address", "contact.address", { type: "textarea", rows: 2 })}
  </div>
  <div class="sup-sub">Policies <span class="muted tiny">(shown as footer links when filled in)</span></div>
  <div class="sup-form-grid">
    ${field("Shipping", "policies.shipping", { type: "textarea", rows: 3 })}
    ${field("Returns &amp; refunds", "policies.returns", { type: "textarea", rows: 3 })}
    ${field("Privacy", "policies.privacy", { type: "textarea", rows: 3 })}
  </div>`;
}

/* ---- repeaters ---- */
function renderRepeaters() {
  const hl = $("hlEditor");
  if (hl) {
    hl.innerHTML = _site.highlights.map((h, i) => `
      <div class="rep-row">
        <button class="icon-pick" data-iconpick="${i}" title="Change icon">${sic(h.icon || "check")}</button>
        <input value="${esc(h.title)}" data-hl="${i}" data-k="title" placeholder="Fast dispatch" />
        <input value="${esc(h.text)}" data-hl="${i}" data-k="text" placeholder="Orders leave within 24 hours." />
        <button class="btn ghost tiny" data-hlrm="${i}">${sic("close")}</button>
      </div>`).join("") +
      `<button class="btn ghost sm" id="hlAdd">＋ Add a promise</button>`;
    hl.querySelectorAll("[data-hl]").forEach((n) => n.oninput = () => { _site.highlights[+n.dataset.hl][n.dataset.k] = n.value; siteMark(); });
    hl.querySelectorAll("[data-hlrm]").forEach((b) => b.onclick = () => { _site.highlights.splice(+b.dataset.hlrm, 1); siteMark(); renderRepeaters(); });
    hl.querySelectorAll("[data-iconpick]").forEach((b) => b.onclick = () => openIconPicker(+b.dataset.iconpick));
    $("hlAdd").onclick = () => {
      if (_site.highlights.length >= 6) { toast("Six is the maximum."); return; }
      _site.highlights.push({ icon: "check", title: "", text: "" }); siteMark(); renderRepeaters();
    };
  }
  const st = $("stEditor");
  if (st) {
    st.innerHTML = (_site.stats || []).map((x, i) => `
      <div class="rep-row">
        <input class="rep-ico" value="${esc(x.value)}" data-st="${i}" data-k="value" placeholder="2,400+" />
        <input value="${esc(x.label)}" data-st="${i}" data-k="label" placeholder="bottles shipped" />
        <button class="btn ghost tiny" data-strm="${i}">${sic("close")}</button>
      </div>`).join("") + `<button class="btn ghost sm" id="stAdd">＋ Add a figure</button>`;
    st.querySelectorAll("[data-st]").forEach((n) => n.oninput = () => {
      _site.stats[+n.dataset.st][n.dataset.k] = n.value; siteMark();
    });
    st.querySelectorAll("[data-strm]").forEach((b) => b.onclick = () => {
      _site.stats.splice(+b.dataset.strm, 1); siteMark(); renderRepeaters();
    });
    $("stAdd").onclick = () => {
      if ((_site.stats || []).length >= 4) { toast("Four figures is the maximum."); return; }
      _site.stats.push({ value: "", label: "" }); siteMark(); renderRepeaters();
    };
  }

  const gl = $("glEditor");
  if (gl) {
    gl.innerHTML = (_site.gallery || []).map((g, i) => `
      <div class="gal-item ${isVid(g.url) ? "is-vid" : ""}" style="${isVid(g.url) ? "" : `background-image:url('${esc(g.url)}')`}">
        ${isVid(g.url) ? `<video src="${esc(g.url)}" muted loop autoplay playsinline></video>` : ""}
        <button class="gal-x" data-glrm="${i}" title="Remove">${sic("close")}</button>
        <input class="gal-cap" value="${esc(g.caption || "")}" data-glcap="${i}" placeholder="Caption" />
      </div>`).join("") +
      `<button class="gal-add" id="glAdd">＋<span>Add photos</span></button>
       <button class="gal-add" id="glAddV">▶<span>Add a clip</span></button>`;
    gl.querySelectorAll("[data-glrm]").forEach((b) => b.onclick = () => {
      _site.gallery.splice(+b.dataset.glrm, 1); siteMark(); renderRepeaters();
    });
    gl.querySelectorAll("[data-glcap]").forEach((n) => n.oninput = () => {
      _site.gallery[+n.dataset.glcap].caption = n.value; siteMark();
    });
    const addMedia = (accept) => pickImage((url) => {
      if ((_site.gallery || []).length >= 12) { toast("Twelve is the maximum."); return; }
      _site.gallery.push({ url, caption: "" }); siteMark(); renderRepeaters();
    }, true, accept);
    $("glAdd").onclick = () => addMedia("image/*");
    $("glAddV").onclick = () => addMedia("video/mp4,video/webm,video/quicktime");
  }

  const ts = $("tsEditor");
  if (ts) {
    ts.innerHTML = (_site.testimonials.length ? _site.testimonials.map((t, i) => `
      <div class="rep-row">
        <select data-ts="${i}" data-k="rating" class="rep-ico">${[5, 4, 3, 2, 1].map((r) => `<option value="${r}" ${t.rating === r ? "selected" : ""}>${"★".repeat(r)}</option>`).join("")}</select>
        <input value="${esc(t.name)}" data-ts="${i}" data-k="name" placeholder="Customer name" />
        <input value="${esc(t.text)}" data-ts="${i}" data-k="text" placeholder="What they said" />
        <button class="btn ghost tiny" data-tsrm="${i}">${sic("close")}</button>
      </div>`).join("") : `<p class="muted tiny">No reviews added yet.</p>`) +
      `<button class="btn ghost sm" id="tsAdd">＋ Add a review</button>`;
    ts.querySelectorAll("[data-ts]").forEach((n) => n.oninput = n.onchange = () => {
      const t = _site.testimonials[+n.dataset.ts];
      t[n.dataset.k] = n.dataset.k === "rating" ? parseInt(n.value, 10) : n.value; siteMark();
    });
    ts.querySelectorAll("[data-tsrm]").forEach((b) => b.onclick = () => { _site.testimonials.splice(+b.dataset.tsrm, 1); siteMark(); renderRepeaters(); });
    $("tsAdd").onclick = () => { _site.testimonials.push({ name: "", text: "", rating: 5 }); siteMark(); renderRepeaters(); };
  }
}

function openIconPicker(index) {
  const names = _siteMeta.promise_icons || Object.keys(_siteMeta.icons || {});
  $("addModal").hidden = true;
  const wrap = document.createElement("div");
  wrap.className = "modal-back";
  wrap.innerHTML = `<div class="modal">
      <div class="modal-head"><b>Pick an icon</b><button class="btn ghost tiny" data-ipclose>${sic("close")}</button></div>
      <div class="icon-grid">${names.map((n) => `<button data-icon="${n}" title="${n}">${sic(n)}</button>`).join("")}</div>
    </div>`;
  document.body.appendChild(wrap);
  const shut = () => wrap.remove();
  wrap.querySelector("[data-ipclose]").onclick = shut;
  wrap.onclick = (e) => { if (e.target === wrap) shut(); };
  wrap.querySelectorAll("[data-icon]").forEach((b) => b.onclick = () => {
    _site.highlights[index].icon = b.dataset.icon; siteMark(); renderRepeaters(); shut();
  });
}

/* ---- the live bridge ---- */
function frame() { return $("edFrame"); }
function sendFrame(msg) {
  const f = frame();
  if (f && f.contentWindow) f.contentWindow.postMessage({ source: "cs-builder", ...msg }, "*");
}
function pushLive() {
  if (_step !== "editor" || !_frameReady) return;
  clearTimeout(_liveTimer);
  _liveTimer = setTimeout(async () => {
    try {
      const r = await api("/api/site/resolve", { method: "POST", json: { site: _site } });
      sendFrame({ type: "apply", site: _site, style: r.style, categories: r.categories });
    } catch (e) { /* the canvas keeps the last good render */ }
  }, 240);
}

function openGroup(key, fromCanvas) {
  _openGroup = key;
  document.querySelectorAll(".insp-g").forEach((g) => g.classList.toggle("open", g.dataset.group === key));
  const g = document.querySelector(`.insp-g[data-group="${CSS.escape(key)}"]`);
  const label = (GROUPS.find((x) => x.key === key) || {}).label || "";
  const sel = $("edSel"); if (sel) sel.textContent = label || "Nothing selected";
  if (g) {
    g.scrollIntoView({ behavior: "smooth", block: "start" });
    g.classList.add("flash"); setTimeout(() => g.classList.remove("flash"), 900);
    const first = g.querySelector("input, textarea, select");
    if (first && !fromCanvas) first.focus();
  }
  if (!fromCanvas) sendFrame({ type: "highlight", key });
  if (["highlights", "testimonials", "stats", "gallery"].includes(key)) renderRepeaters();
}

addEventListener("message", (e) => {
  const m = e.data || {};
  if (m.source !== "cs-store") return;
  if (m.type === "ready") {
    _frameReady = true;
    pushLive();
  } else if (m.type === "select") {
    openGroup(m.key, true);
  }
});

/* ============================ STEP 4: CHECKOUT =========================== */
function stepCheckout() {
  return `
  <div class="card sup-form form-v">
    <p class="muted tiny" style="margin:0 0 12px;">What your checkout charges and collects. Shoppers create an account on your store before ordering, and every order lands in the Orders app.</p>
    <div class="sup-sub">Delivery</div>
    <div class="sup-form-grid">
      ${field("Shipping fee ₹", "commerce.shipping_fee", { type: "number", num: true, ph: "49" })}
      ${field("Free shipping above ₹", "commerce.free_shipping_above", { type: "number", num: true, hint: "(0 = never free)", ph: "999" })}
      ${field("Minimum order value ₹", "commerce.min_order", { type: "number", num: true, hint: "(0 = no minimum)" })}
    </div>
    <div class="sup-sub">Tax</div>
    <div class="sup-form-grid">
      ${field("GST %", "commerce.gst_percent", { type: "number", num: true, hint: "(0 = don't show tax)", ph: "18" })}
      ${field("My prices already include GST", "commerce.gst_inclusive", { type: "check", hint: "— when off, GST is added on top at checkout" })}
    </div>
    <div class="sup-sub">Payment</div>
    <div class="sup-form-grid">
      ${field("Offer cash on delivery", "commerce.cod_enabled", { type: "check" })}
      ${field("Note shown at checkout", "commerce.order_note", { type: "textarea", rows: 2, ph: "We'll call to confirm your order before dispatch." })}
    </div>
  </div>`;
}

/* ============================= STEP 5: PUBLISH =========================== */
function stepPublish() {
  const c = _siteMeta.counts;
  const url = location.origin + "/s/" + (_site.handle || "");
  const checks = [
    [!!_site.brand, "Brand name set"],
    [!!_site.handle, "Web address chosen"],
    [c.listed > 0, `${fmt(c.listed)} product${c.listed === 1 ? "" : "s"} listed on the site`],
    [c.no_price === 0, c.no_price ? `${fmt(c.no_price)} listed product${c.no_price === 1 ? " has" : "s have"} no price` : "Every listed product has a price"],
    [c.no_image === 0, c.no_image ? `${fmt(c.no_image)} listed product${c.no_image === 1 ? " has" : "s have"} no photo` : "Every listed product has a photo"],
    [!!_site.hero.heading, "Hero headline written"],
  ];
  const ready = checks.every(([ok]) => ok);
  return `
  <div class="pub-grid">
    <div class="card">
      <h4 style="margin:0 0 12px;">Before you go live</h4>
      <ul class="check-list">${checks.map(([ok, t]) =>
        `<li class="${ok ? "ok" : "warn"}">${sic(ok ? "check" : "close")}<span>${esc(t)}</span></li>`).join("")}</ul>
      <p class="muted tiny" style="margin-top:14px;">${ready
        ? "Everything's in place. Publishing makes your site reachable by anyone with the link."
        : "You can still publish — the warnings above are things shoppers will notice."}</p>
      <div class="row" style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;">
        <button class="btn ${_site.published ? "ghost" : "primary"}" id="pubBtn">${_site.published ? "Unpublish site" : "Publish my site"}</button>
        ${_site.published ? `<a class="btn ghost" href="/s/${esc(_site.handle)}" target="_blank" rel="noopener">Visit site ↗</a>` : ""}
      </div>
    </div>
    <div class="card">
      <h4 style="margin:0 0 12px;">Your link</h4>
      <div class="share-row"><input id="shareUrl" readonly value="${esc(url)}" /><button class="btn ghost sm" id="copyUrl">Copy</button></div>
      <p class="muted tiny" style="margin-top:10px;">Share this anywhere — Instagram bio, WhatsApp, a QR code on your packaging.</p>
      <div class="sup-sub">Custom domain</div>
      <p class="muted tiny" style="margin:0;">Not set up yet. When you're ready to point your own domain here, say the word and we'll wire it up.</p>
    </div>
  </div>`;
}

/* ------------------------------ wiring ---------------------------------- */
function wireStep() {
  const body = $("siteBody");
  wireBinds(body);
  wireImageFields(body);

  const map = { siteLogo: "logo_url", edLogo: "logo_url", edHero: "hero.image_url",
                edHeroVid: "hero.video_url", edStory: "story.image_url" };
  Object.entries(map).forEach(([id, path]) => {
    const n = $(id);
    if (!n || n._imgBound) return;
    n._imgBound = true;
    const push = () => bindPath(path, n.value.trim());
    n.addEventListener("change", push);
    n.addEventListener("blur", push);
  });

  const h = $("siteHandle");
  if (h) {
    h.addEventListener("input", () => {
      const clean = h.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-{2,}/g, "-");
      if (clean !== h.value) h.value = clean;
      _site.handle = clean; _siteDirty = true;
      const b = $("siteSave"); if (b) { b.disabled = false; b.textContent = "Save"; }
      const d = $("siteDirty"); if (d) d.hidden = false;
      clearTimeout(h._t);
      h._t = setTimeout(async () => {
        const st = $("handleState");
        if (!clean || clean.length < 3) { st.textContent = "at least 3 letters"; st.className = "handle-state bad"; return; }
        try {
          const r = await api(`/api/site/handle-check?handle=${encodeURIComponent(clean)}`);
          st.textContent = r.available ? "✓ available" : "✕ taken";
          st.className = "handle-state " + (r.available ? "good" : "bad");
        } catch (e) { st.textContent = ""; }
      }, 400);
    });
  }

  document.querySelectorAll("[data-theme-pick]").forEach((c) => c.onclick = () => {
    _site.theme = c.dataset.themePick;
    // a new theme resets the per-theme overrides so the seller actually sees it
    _site.style.accent = ""; _site.style.accent_dark = "";
    _site.style.heading_font = ""; _site.style.body_font = "";
    _site.style.radius = null; _site.style.card_style = "";
    siteMark();
    // the recommended pairings depend on the theme, so re-rank them
    loadPairings().then(() => { if (_step === "editor") renderStep(); });
    renderSite();
    toast(`Theme set to ${c.querySelector("b").textContent.trim()}`);
  });

  document.querySelectorAll('[data-bind^="style.heading_font"], [data-bind^="style.body_font"], [data-bind^="style.accent_font"]')
    .forEach((sel) => sel.addEventListener("change", () => { _site.style.pairing = ""; }));

  document.querySelectorAll("[data-reset]").forEach((b) => b.onclick = () => {
    bindPath(b.dataset.reset, ""); renderStep(); openGroup("__colour");
  });

  // editor step
  document.querySelectorAll("[data-ghead]").forEach((b) => b.onclick = () => openGroup(b.dataset.ghead));
  document.querySelectorAll("[data-pair]").forEach((b) => b.onclick = () => {
    const pr = (_pairings || []).find((x) => x.id === b.dataset.pair);
    if (!pr) return;
    _site.style.pairing = pr.id;
    _site.style.heading_font = pr.heading;
    _site.style.body_font = pr.body;
    _site.style.accent_font = pr.accent;
    siteMark(); renderStep(); openGroup("__type");
    toast(`Type set to ${pr.name}`);
  });
  const po = $("pairOwn");
  if (po) po.onclick = () => {
    const box = $("typeManual");
    if (!box) return;
    box.hidden = !box.hidden;
    po.textContent = box.hidden ? "Choose each face myself" : "Hide the individual faces";
  };
  const rl = $("edReload"); if (rl) rl.onclick = () => { _frameReady = false; frame().src = frame().src; };
  document.querySelectorAll("[data-dev]").forEach((b) => b.onclick = () => {
    document.querySelectorAll("[data-dev]").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    $("edStage").className = "ed-stage dev-" + b.dataset.dev;
  });
  document.querySelectorAll("[data-route]").forEach((b) => b.onclick = () => {
    document.querySelectorAll("[data-route]").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    sendFrame({ type: "route", name: b.dataset.route });
  });
  const tp = $("edToProducts"); if (tp) tp.onclick = () => openProducts();
  if (_step === "editor") renderRepeaters();

  // publish step
  const pb = $("pubBtn"); if (pb) pb.onclick = togglePublish;
  const cu = $("copyUrl");
  if (cu) cu.onclick = async () => {
    const inp = $("shareUrl"); inp.select();
    try { await navigator.clipboard.writeText(inp.value); toast("Link copied"); }
    catch (e) { document.execCommand("copy"); toast("Link copied"); }
  };
}

async function saveSite(opts) {
  const quiet = !!(opts && opts.quiet);
  const btn = $("siteSave"); if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
  try {
    const d = await api("/api/site/save", { method: "POST", json: { site: _site } });
    _siteMeta = d; _site = JSON.parse(JSON.stringify(d.site)); _siteDirty = false;
    if (!quiet) {
      const keep = _step;
      renderSite();
      _step = keep;
      toast(_site.published ? "Saved — press Publish to make it live" : "Saved as a draft");
    } else {
      const badge = $("siteDirty");
      if (badge) badge.outerHTML = saveState(_site.published && _site.handle);
      const b2 = $("siteSave"); if (b2) { b2.disabled = true; b2.textContent = "Saved"; }
    }
  } catch (e) {
    toast(e.message, 5000);
    if (btn) { btn.disabled = false; btn.textContent = "Save"; }
    throw e;
  }
}

async function togglePublish() {
  const want = !_site.published;
  if (want && _siteDirty) await saveSite({ quiet: true });
  try {
    const d = await api("/api/site/publish", { method: "POST", json: { published: want } });
    _siteMeta = d; _site = JSON.parse(JSON.stringify(d.site)); _siteDirty = false;
    renderSite();
    toast(want ? `Live at ${location.origin}/s/${_site.handle}` : "Site unpublished");
  } catch (e) { toast(e.message, 5000); }
}


// =========================================================================
// MODULE: Orders
// =========================================================================
let _ordersData = null;
let _ordersFilter = "";
let _ordersTab = "orders";

async function openOrders() {
  moduleShell("Orders", `<div class="ap-empty">Loading orders…</div>`);
  try {
    _ordersData = await api("/api/store/orders");
    renderOrders();
  } catch (e) { moduleShell("Orders", `<div class="card">${esc(e.message)}</div>`); }
}

function renderOrders() {
  const d = _ordersData, st = d.stats;
  const rows = _ordersFilter ? d.orders.filter((o) => o.status === _ordersFilter) : d.orders;

  const kpis = `
    <div class="site-health">
      <div class="sh"><b>${fmt(st.orders)}</b><span>orders</span></div>
      <div class="sh"><b>₹${fmt(st.revenue)}</b><span>revenue</span></div>
      <div class="sh"><b>₹${fmt(st.aov)}</b><span>average order</span></div>
      <div class="sh"><b>${fmt(st.units)}</b><span>units sold</span></div>
      <div class="sh"><b>${fmt(st.customers)}</b><span>customers</span></div>
    </div>`;

  const tabs = `<div class="site-tabs">
      <button class="${_ordersTab === "orders" ? "on" : ""}" data-otab="orders">🧺 Orders</button>
      <button class="${_ordersTab === "customers" ? "on" : ""}" data-otab="customers">👥 Customers</button>
    </div>`;

  let body;
  if (_ordersTab === "customers") {
    body = `<div id="custBody"><div class="ap-empty">Loading customers…</div></div>`;
  } else if (!d.orders.length) {
    body = `<div class="ap-empty">No orders yet.${d.site.published ? "" : " Publish your website from the Website Builder to start taking them."}</div>`;
  } else {
    const chips = [["", "All", d.orders.length]].concat(d.statuses.map((s) =>
      [s.id, s.label, st.by_status[s.id] || 0])).map(([id, label, n]) =>
      `<button class="chip ${_ordersFilter === id ? "on" : ""}" data-ofil="${id}">${esc(label)} <b>${n}</b></button>`).join("");
    body = `
      <div class="ord-toolbar">
        <div class="ord-chips">${chips}</div>
        <button class="btn ghost sm" id="ordExport">⬇ Export CSV</button>
      </div>
      <div class="ord-list">${rows.map(orderCard).join("") || `<div class="ap-empty">Nothing with that status.</div>`}</div>`;
  }

  moduleShell("Orders", kpis + tabs + body);
  document.querySelectorAll("[data-otab]").forEach((b) => b.onclick = () => { _ordersTab = b.dataset.otab; renderOrders(); if (_ordersTab === "customers") loadCustomers(); });
  document.querySelectorAll("[data-ofil]").forEach((b) => b.onclick = () => { _ordersFilter = b.dataset.ofil; renderOrders(); });
  const ex = $("ordExport");
  if (ex) ex.onclick = () => download("/api/store/orders/export", "site_orders.csv");
  document.querySelectorAll("[data-ostat]").forEach((sel) => sel.onchange = async () => {
    try {
      _ordersData = await api("/api/store/orders/status", { method: "POST", json: { order_id: sel.dataset.ostat, status: sel.value } });
      toast("Order updated — sales figures refreshed");
      renderOrders();
    } catch (e) { toast(e.message); }
  });
  if (_ordersTab === "customers") loadCustomers();
}

function orderCard(o) {
  const a = o.address || {};
  const items = (o.items || []).map((i) =>
    `<div class="oi"><span>${esc(i.name)} <span class="muted tiny">× ${i.qty}</span></span><b>₹${fmt(i.line_total)}</b></div>`).join("");
  const opts = _ordersData.statuses.map((s) =>
    `<option value="${s.id}" ${o.status === s.id ? "selected" : ""}>${esc(s.label)}</option>`).join("");
  return `
    <div class="ord-card ${esc(o.status)}">
      <div class="ord-card-h">
        <div>
          <b>${esc(o.order_no)}</b>
          <span class="chan-pill ${esc(o.status)}">${esc(o.status)}</span>
          <div class="muted tiny">${esc(String(o.created_at).replace("T", " ").slice(0, 16))} · ${esc(o.payment === "cod" ? "Cash on delivery" : "Pay online")}</div>
        </div>
        <div class="ord-total">₹${fmt(o.total)}</div>
      </div>
      <div class="ord-grid">
        <div>
          <div class="ord-lbl">Customer</div>
          <div><b>${esc(o.customer_name || "—")}</b></div>
          <div class="muted tiny">${esc(o.customer_email || "")}</div>
          <div class="muted tiny">${esc(o.phone || "")}</div>
        </div>
        <div>
          <div class="ord-lbl">Deliver to</div>
          <div class="muted tiny">${esc([a.line1, a.line2, a.landmark].filter(Boolean).join(", "))}</div>
          <div class="muted tiny">${esc([a.city, a.state, a.pincode].filter(Boolean).join(" · "))}</div>
        </div>
        <div>
          <div class="ord-lbl">Items</div>
          ${items}
          <div class="oi muted tiny"><span>Shipping</span><span>${o.shipping ? "₹" + fmt(o.shipping) : "Free"}</span></div>
          ${o.gst_percent ? `<div class="oi muted tiny"><span>GST ${o.gst_percent}%${o.gst_inclusive ? " incl." : ""}</span><span>₹${fmt(o.tax)}</span></div>` : ""}
        </div>
      </div>
      ${o.note ? `<div class="ord-note">${sic("edit")}${esc(o.note)}</div>` : ""}
      <div class="ord-card-f">
        <label class="muted tiny">Status <select data-ostat="${esc(o.id)}">${opts}</select></label>
        ${o.phone ? `<a class="btn ghost tiny" href="https://wa.me/${esc(String(o.phone).replace(/\D/g, ""))}" target="_blank" rel="noopener">${sic("whatsapp")}WhatsApp</a>` : ""}
      </div>
    </div>`;
}

async function loadCustomers() {
  const box = $("custBody");
  if (!box) return;
  try {
    const d = await api("/api/store/customers");
    box.innerHTML = d.customers.length ? `
      <div class="table-scroll"><table>
        <thead><tr><th>Customer</th><th>Email</th><th>Phone</th><th>Orders</th><th>Spend</th><th>Last order</th></tr></thead>
        <tbody>${d.customers.map((c) => `<tr>
          <td><b>${esc(c.name || "—")}</b></td><td>${esc(c.email)}</td><td>${esc(c.phone || "—")}</td>
          <td>${fmt(c.orders)}</td><td>₹${fmt(c.spend)}</td>
          <td class="muted tiny">${esc(String(c.last || "").replace("T", " ").slice(0, 16) || "—")}</td>
        </tr>`).join("")}</tbody>
      </table></div>
      <p class="muted tiny" style="margin-top:10px;">These shoppers are yours alone — they also appear in RFM and Win-Back once their orders are counted in your sales.</p>`
      : `<div class="ap-empty">No one has signed up on your site yet.</div>`;
  } catch (e) { box.innerHTML = `<div class="card">${esc(e.message)}</div>`; }
}

// ---------- boot ----------
(async function init() {
  await loadIcons();
  if (state.token) {
    try { await api("/api/me"); loadMediaStatus(); showShell(); }
    catch { state.token = null; localStorage.removeItem("cx_token"); $("loginView").hidden = false; }
  } else { $("loginView").hidden = false; }
})();
