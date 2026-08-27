/* Cafe_X frontend — replaces Streamlit's rerun model with a small SPA. */

// ---------- state ----------
// SHARED LOGIN + SESSION with the Smart app: both read/write the same cx_*
// keys in localStorage, so logging in (and uploaded data) carry across
// /app and /smart with no second login.
const state = {
  sessionId: localStorage.getItem("cx_session") || crypto.randomUUID(),
  token: localStorage.getItem("cx_token") || null,
  email: localStorage.getItem("cx_email") || null,
  files: [],
  mapped: false,
  plan: "free",
  lang: localStorage.getItem("cx_lang") || "en",
  productType: null,
  pendingPage: null,
  pricing: null,
  launchMode: true,
};
localStorage.setItem("cx_session", state.sessionId);

const $ = (id) => document.getElementById(id);
// Null-safe wiring: a missing element (e.g. stale cached HTML) must never
// kill the whole script and take every other button down with it.
const on = (id, fn) => { const e = $(id); if (e) e.onclick = fn; return e; };

// ---------- api helper ----------
async function api(path, opts = {}) {
  const headers = { "X-Session-Id": state.sessionId, ...(opts.headers || {}) };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  if (opts.json) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.json);
  }
  const res = await fetch(path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 404 && /\/api\/(pricing|demo|feedback|complaints|report)/.test(path)) {
      throw new Error("The server is running an older version — restart the backend (uvicorn backend.main:app) to load the new features.");
    }
    // Paywall responses carry a structured detail: {code:"paywall", product, message}
    if (data.detail && typeof data.detail === "object") {
      const err = new Error(data.detail.message || res.statusText);
      err.code = data.detail.code;
      err.product = data.detail.product;
      throw err;
    }
    throw new Error(data.detail || res.statusText);
  }
  return data;
}

/* Wrap a call so paywall errors open the pricing modal instead of a plain toast. */
async function apiOrPaywall(path, opts) {
  try { return await api(path, opts); }
  catch (e) {
    if (e.code === "paywall") { openPricing(e.product, e.message); throw e; }
    throw e;
  }
}

function toast(msg, ms = 3200) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.hidden = true), ms);
}

// ---------- theme ----------
// One source of truth: the CSS custom properties. Charts read the same tokens
// the rest of the UI uses, so a theme switch restyles everything consistently
// instead of leaving Plotly stuck on hardcoded dark colours.
function cssVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function setTheme(mode) {
  document.documentElement.setAttribute("data-theme", mode);
  try { localStorage.setItem("cx_theme", mode); } catch (e) {}
  const lightBtn = $("themeLight"), darkBtn = $("themeDark");
  if (lightBtn) lightBtn.setAttribute("aria-pressed", String(mode === "light"));
  if (darkBtn) darkBtn.setAttribute("aria-pressed", String(mode === "dark"));
  redrawAllCharts();
}

// ---------- plotly ----------
// IMPORTANT: Plotly MUTATES the layout object it's given (it writes axis types,
// ranges, etc. back into it). A single shared layout object caused the date
// axis from the monthly-trend chart to leak into every categorical chart after
// it — "Monday" and product names got parsed as dates, rendering empty charts.
// Every plot must therefore get a FRESH layout object.
//
// Readability choices (the "make it like a business dashboard, not a Python
// plot" brief): horizontal gridlines only — vertical ones add noise without
// adding information; no zero lines or axis spines; tick labels at a real
// reading size instead of 6-7px; thousands separators on every number; and
// generous margins so long café item names never clip.
function baseLayout() {
  const text = cssVar("--text", "#14171d");
  const axis = cssVar("--axis", "#6b7280");
  const grid = cssVar("--grid", "#e6e9ee");
  const surface = cssVar("--surface", "#ffffff");
  const border = cssVar("--border", "#e0e4ea");
  const axisCommon = {
    gridcolor: grid,
    zeroline: false,
    showline: false,
    automargin: true,
    separatethousands: true,
    tickfont: { size: 11.5, color: axis },
    title: { font: { size: 12, color: axis } },
  };
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: axis, family: "Inter, sans-serif", size: 12 },
    // no top margin reserved for a title — the heading is HTML above the canvas
    margin: { l: 58, r: 18, t: 8, b: 40 },
    xaxis: { ...axisCommon, showgrid: false },
    yaxis: { ...axisCommon, showgrid: true, griddash: "dot" },
    bargap: 0.42,
    hoverlabel: {
      bgcolor: surface,
      bordercolor: border,
      font: { color: text, family: "Inter, sans-serif", size: 12.5 },
    },
    legend: {
      orientation: "h", y: -0.22, x: 0, xanchor: "left",
      font: { size: 11.5, color: axis },
      bgcolor: "rgba(0,0,0,0)",
    },
    colorway: [
      cssVar("--accent", "#6d28d9"), "#0ea5e9", "#10b981", "#f59e0b",
      "#ec4899", "#8b5cf6", "#14b8a6", "#ef4444",
    ],
  };
}

// Chart titles read as section headings — left-aligned, in body text colour,
// the way a dashboard labels a panel rather than the way a plot captions itself.
// Translucent version of the accent for area fills — hex tokens don't carry
// alpha, so convert rather than hardcoding a second colour that would drift.
function accentFill(alpha) {
  const hex = cssVar("--accent", "#6d28d9").replace("#", "");
  const n = hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex;
  const r = parseInt(n.slice(0, 2), 16), g = parseInt(n.slice(2, 4), 16), b = parseInt(n.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function chartTitle(text) {
  return {
    text,
    x: 0, xanchor: "left", y: 0.97, yanchor: "top",
    font: { family: "Sora, Inter, sans-serif", size: 14.5, color: cssVar("--text", "#14171d") },
  };
}

// Inline charts are STATIC on purpose: on a dashboard you scroll past, an
// accidental scroll-zoom or drag-pan is only ever a mistake. Interaction is
// available deliberately, by expanding a chart.
const PLOT_CFG = { staticPlot: true, responsive: true, displayModeBar: false };
// Full analysis toolbar for the expanded (fullscreen) view — zoom, pan,
// box-select, and PNG download, so a café owner can actually dig into a chart.
// Expanded view: fully interactive, but Plotly's own icon strip is hidden —
// we drive it from labelled buttons instead, because a row of unlabelled
// glyphs is not something a café owner should have to decode.
const PLOT_CFG_FULL = {
  responsive: true, displayModeBar: false, scrollZoom: false, doubleClick: "reset",
};

// registry of every chart currently on screen, so "expand" can redraw any one
// of them large in the modal with the same data
const _charts = {};

function _registerChart(el, traces, title, extra) {
  if (!el || !el.id) return;
  _charts[el.id] = { traces, title, extra: extra || {} };
  addExpandButton(el);
}

function addExpandButton(el) {
  const card = el.closest(".chart") || el;
  if (!card || card.querySelector(".chart-expand")) return;
  card.style.position = card.style.position || "relative";
  const btn = document.createElement("button");
  btn.className = "chart-expand";
  btn.title = "Open this chart full-screen for analysis";
  btn.innerHTML = "⤢";
  btn.onclick = (e) => { e.stopPropagation(); openChartModal(el.id); };
  card.appendChild(btn);
}

let _currentModalChart = null;

function openChartModal(chartId) {
  const c = _charts[chartId];
  if (!c || typeof Plotly === "undefined") return;
  _currentModalChart = chartId;
  $("chartModal").style.display = "flex";
  const host = $("chartModalPlot");
  const layout = { ...baseLayout(), ...c.extra };
  delete layout.title;
  layout.autosize = true;
  layout.height = Math.floor(window.innerHeight * 0.66);
  layout.dragmode = _modalMode === "pan" ? "pan" : "zoom";
  const head = $("chartModalTitle");
  if (head) {
    const parts = String(c.title || "").split(" — ");
    head.innerHTML = `<div class="chart-title">${escapeHtml(parts.shift() || "")}</div>` +
      (parts.length ? `<div class="chart-sub">${escapeHtml(parts.join(" — "))}</div>` : "");
  }
  Plotly.newPlot(host, styleTraces(c.traces), layout, PLOT_CFG_FULL);
  syncModalButtons();
}

// which drag tool the expanded view is in
let _modalMode = "zoom";

function setModalMode(mode) {
  _modalMode = mode;
  const host = $("chartModalPlot");
  if (host && typeof Plotly !== "undefined") {
    Plotly.relayout(host, { dragmode: mode === "pan" ? "pan" : "zoom" });
  }
  syncModalButtons();
}

function syncModalButtons() {
  const z = $("chartZoomBtn"), p = $("chartPanBtn");
  if (z) z.setAttribute("aria-pressed", String(_modalMode === "zoom"));
  if (p) p.setAttribute("aria-pressed", String(_modalMode === "pan"));
}

function resetModalView() {
  const host = $("chartModalPlot");
  if (host && typeof Plotly !== "undefined") {
    Plotly.relayout(host, { "xaxis.autorange": true, "yaxis.autorange": true });
  }
}

function downloadModalChart() {
  const host = $("chartModalPlot");
  if (!host || typeof Plotly === "undefined") return;
  Plotly.downloadImage(host, { format: "png", scale: 2, filename: "content_seller_chart" });
}

function closeChartModal() {
  $("chartModal").style.display = "none";
  _currentModalChart = null;
  const host = $("chartModalPlot");
  if (host && typeof Plotly !== "undefined") Plotly.purge(host);
}

const DO_THIS = { en: "DO THIS", hi: "यह कीजिए", ta: "இதைச் செய்யுங்கள்", kn: "ಇದನ್ನು ಮಾಡಿ" };

// ---------- structured insight cards (colored by sentiment, key figure highlighted) ----------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderInsights(insights, emptyText) {
  if (!insights || !insights.length) {
    return `<div class="card empty">${emptyText || "Not enough data for insights yet."}</div>`;
  }
  const icons = { positive: "▲", negative: "▼", warning: "⚠", neutral: "●" };
  const cards = insights.map((ins) => {
    const type = ["positive", "negative", "warning", "neutral"].includes(ins.type) ? ins.type : "neutral";
    let text = escapeHtml(ins.text);
    if (ins.highlight) {
      const esc = escapeHtml(ins.highlight);
      text = text.split(esc).join(`<span class="hl">${esc}</span>`);
    }
    const action = ins.action ? `<div class="ins-action lead"><span class="ins-action-label">✅ ${DO_THIS[state.lang] || "DO THIS"}</span><b>${escapeHtml(ins.action)}</b></div>` : "";
    return `<div class="insight-card ${type}">
        <span class="tag">${icons[type]} ${type}</span>
        ${action}
        <div class="ins-why">${action ? "Why: " : ""}${text}</div>
      </div>`;
  }).join("");
  return `<div class="insights-strip">${cards}</div>`;
}

function plotlyReady(el) {
  if (typeof Plotly !== "undefined") return true;
  el.innerHTML = '<div class="chart-missing">Chart library failed to load — check your internet connection and refresh the page.</div>';
  return false;
}

// A chart card is HTML chrome + a bare plot canvas. Titles, subtitles and
// legends live in the DOM as real text, and Plotly only ever draws the data.
// That separation is what stops a chart reading as a plotting-library output:
// the type is the app's type, it selects and wraps like text, and the canvas
// holds nothing but the marks.
function chartShell(el, title) {
  let canvas = el.querySelector(":scope > .chart-canvas");
  let head = el.querySelector(":scope > .chart-head");
  if (!canvas) {
    el.innerHTML = "";
    head = document.createElement("div");
    head.className = "chart-head";
    canvas = document.createElement("div");
    canvas.className = "chart-canvas";
    el.appendChild(head);
    el.appendChild(canvas);
  }
  // "Heading — supporting detail" splits into a heading and a quieter subline
  const parts = String(title || "").split(" — ");
  const heading = parts.shift() || "";
  const sub = parts.join(" — ");
  head.innerHTML =
    `<div class="chart-title">${escapeHtml(heading)}</div>` +
    (sub ? `<div class="chart-sub">${escapeHtml(sub)}</div>` : "");
  return canvas;
}

function plot(el, traces, title, extra = {}) {
  if (!plotlyReady(el)) return;
  const canvas = chartShell(el, title);
  const layout = { ...baseLayout(), ...extra };
  delete layout.title;                       // the heading is HTML now
  Plotly.newPlot(canvas, styleTraces(traces), layout, PLOT_CFG);
  _registerChart(el, traces, title, extra);
}

// House style applied to every trace so individual call sites don't repeat it:
// bars get rounded caps and breathing room, lines get round joins.
function styleTraces(traces) {
  return (traces || []).map((t) => {
    const out = { ...t };
    if (out.type === "bar") {
      out.marker = { cornerradius: 6, ...(out.marker || {}) };
    }
    if (out.type === "scatter" && (out.mode || "").includes("lines")) {
      out.line = { shape: "spline", smoothing: 0.35, ...(out.line || {}) };
    }
    return out;
  });
}

// Re-plot every chart currently on screen using the new theme's tokens.
// Charts hold their traces in the registry, so this is a restyle, not a refetch.
function redrawAllCharts() {
  if (typeof Plotly === "undefined") return;
  Object.keys(_charts).forEach((id) => {
    const el = $(id);
    const c = _charts[id];
    if (!el || !c || !el.isConnected) return;
    const canvas = el.querySelector(":scope > .chart-canvas") || el;
    const layout = { ...baseLayout(), ...c.extra };
    delete layout.title;
    Plotly.react(canvas, styleTraces(c.traces), layout, PLOT_CFG);
  });
  if (_currentModalChart) openChartModal(_currentModalChart);
}

function renderChartSpec(el, chart) {
  if (!plotlyReady(el)) return;
  // chart = {chart_type, title, series:[{name,x,y}]}
  const type = chart.chart_type;
  let traces;
  if (type === "pie") {
    const s = chart.series[0];
    traces = [{ type: "pie", labels: s.x, values: s.y, hole: 0.45 }];
  } else {
    traces = chart.series.map((s) => ({
      x: s.x, y: s.y, name: s.name,
      type: type === "line" ? "scatter" : type,
      mode: type === "line" ? "lines+markers" : type === "scatter" ? "markers" : undefined,
    }));
  }
  plot(el, traces, chart.title);
}

// ---------- keep charts sized to their container on any layout change ----------
let _resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(() => {
    document.querySelectorAll(".chart").forEach((el) => {
      if (el.data) { try { Plotly.Plots.resize(el); } catch {} }
    });
  }, 120);
});

// ---------- navigation ----------
const AI_PAGES = ["analyst", "chatbot"];
document.querySelectorAll(".nav-item").forEach((btn) =>
  btn.addEventListener("click", () => go(btn.dataset.page))
);

function go(page) {
  // Guests can VIEW the AI pages (blurred preview shows what they get);
  // actually running anything still requires the free login.
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + page));
  syncLockedPreviews();
  closeDrawer();               // on mobile, picking a page closes the menu
  if (page === "mapping") renderMapping();
  if (page === "analytics") loadAnalytics();
  if (page === "subcategory") loadSubcategory();
  if (page === "rfm") loadRFM();
  if (page === "strategy") loadStrategy();
  // positioning page is upload-driven — nothing to preload
}

// ---------- mobile drawer ----------
function openDrawer() {
  const s = $("sidebar"), b = $("sidebarBackdrop"), t = $("menuToggle");
  if (s) s.classList.add("open");
  if (b) b.hidden = false;
  if (t) t.setAttribute("aria-expanded", "true");
}
function closeDrawer() {
  const s = $("sidebar"), b = $("sidebarBackdrop"), t = $("menuToggle");
  if (s) s.classList.remove("open");
  if (b) b.hidden = true;
  if (t) t.setAttribute("aria-expanded", "false");
}
on("menuToggle", () => {
  const s = $("sidebar");
  (s && s.classList.contains("open")) ? closeDrawer() : openDrawer();
});
on("sidebarBackdrop", closeDrawer);
on("mobileThemeToggle", () => setTheme(currentTheme() === "dark" ? "light" : "dark"));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

// ---------- auth ----------
let authMode = "login";
function setAuthMode(mode) {
  authMode = mode;
  const signup = mode === "signup";
  $("authTitle").textContent = signup ? "🛍️ Create your free account" : "👋 Welcome back";
  $("authSub").textContent = signup
    ? "Free during launch — no card needed. Your data and insights stay private to you."
    : "Log in to your Content Seller account — your data and insights stay private to you.";
  $("pw2Row").hidden = !signup;
  $("authSecurityNote").hidden = !signup;
  $("loginSubmit").textContent = signup ? "Create account" : "Log in";
  $("authToggleText").textContent = signup ? "Already have an account?" : "New to Content Seller?";
  $("authToggle").textContent = signup ? "Log in instead" : "Create a free account";
  $("loginError").hidden = true;
}
if ($("authToggle")) $("authToggle").onclick = (e) => { e.preventDefault(); setAuthMode(authMode === "login" ? "signup" : "login"); };

function openLogin() {
  const m = $("loginModal");
  m.hidden = false; m.style.display = "grid";
  setAuthMode("login");
  $("loginEmail").focus();
}
function closeLogin() {
  const m = $("loginModal");
  m.hidden = true; m.style.display = "none";
}
$("loginCancel").onclick = closeLogin;
$("loginSubmit").onclick = doLogin;
$("loginPassword").addEventListener("keydown", (e) => e.key === "Enter" && doLogin());
if ($("loginPassword2")) $("loginPassword2").addEventListener("keydown", (e) => e.key === "Enter" && doLogin());

async function doLogin() {
  try {
    if (authMode === "signup" && $("loginPassword").value !== $("loginPassword2").value) {
      $("loginError").textContent = "Passwords don't match — please type the same password in both boxes.";
      $("loginError").hidden = false;
      return;
    }
    const endpoint = authMode === "signup" ? "/api/register" : "/api/login";
    const data = await api(endpoint, { method: "POST", json: { email: $("loginEmail").value, password: $("loginPassword").value } });
    state.token = data.token;
    state.email = data.email;
    localStorage.setItem("cx_token", data.token);
    localStorage.setItem("cx_email", data.email);
    closeLogin();
    refreshUserUI(data.usage, data.plan);
    syncLockedPreviews();
    toast(authMode === "signup" ? "🎉 Account created — welcome to Content Seller!" : "Welcome back 👋");
    if (state.pendingPage) { const p = state.pendingPage; state.pendingPage = null; go(p); }
  } catch (e) {
    $("loginError").textContent = e.message;
    $("loginError").hidden = false;
  }
}

$("logoutBtn").onclick = async () => {
  try { await api("/api/logout", { method: "POST" }); } catch {}
  state.token = null; state.email = null;
  localStorage.removeItem("cx_token"); localStorage.removeItem("cx_email");
  refreshUserUI(null);
  syncLockedPreviews();
  go("instructions");
  toast("Logged out");
};

function refreshUserUI(usage, plan) {
  if (usage === undefined) usage = state.lastUsage; else state.lastUsage = usage;
  if (usage && usage.plan) state.plan = usage.plan;
  else if (plan !== undefined) state.plan = plan === "pro" ? "chain" : plan;
  if (usage && usage.launch_mode !== undefined) state.launchMode = usage.launch_mode;
  if (state.email) {
    $("userLabel").textContent = state.email;
    $("userHint").textContent =
      state.plan === "chain" ? "🏢 Chain plan — unlimited" :
      state.launchMode ? "Launch access — everything free" : "Free plan · 5 AI uses/day";
    $("logoutBtn").hidden = false;
  } else {
    $("userLabel").textContent = "Guest";
    $("userHint").innerHTML = `<span class="link">Tap to log in — it's free</span>`;
    $("logoutBtn").hidden = true;
  }
  const uc = $("userCard");
  if (uc) uc.classList.toggle("clickable", !state.email);
  $("upgradeBtn").hidden = false; // pricing is always viewable
  const credits = usage && usage.ai_credits ? ` +${usage.ai_credits}` : "";
  $("usageAnalyst").textContent = usage ? usage.analyst_ai + credits : "";
  $("usageChatbot").textContent = usage ? usage.chatbot + credits : "";
}

on("userCard", () => { if (!state.token) openLogin(); });

// ---------- locked previews (guest view of AI features) ----------
function syncLockedPreviews() {
  const guest = !state.token;
  const aLock = $("analystLock"), cLock = $("chatbotLock");
  if (aLock) { aLock.hidden = !guest; $("analystArea").hidden = guest; $("runAnalystBtn").hidden = guest; }
  if (cLock) { cLock.hidden = !guest; $("chatWindow").hidden = guest;
               document.querySelector(".chat-input-row").hidden = guest; }
}
["analystLockLogin", "chatbotLockLogin"].forEach((id) => {
  const b = $(id);
  if (b) b.onclick = () => { state.pendingPage = id.startsWith("analyst") ? "analyst" : "chatbot"; openLogin(); };
});

// ---------- upload ----------
const zone = $("uploadZone");
zone.onclick = () => $("fileInput").click();
["dragover", "dragleave", "drop"].forEach((ev) =>
  zone.addEventListener(ev, (e) => {
    e.preventDefault();
    zone.classList.toggle("drag", ev === "dragover");
    if (ev === "drop") uploadFiles(e.dataTransfer.files);
  })
);
$("fileInput").onchange = (e) => uploadFiles(e.target.files);

async function uploadFiles(fileList) {
  if (!fileList.length) return;
  const fd = new FormData();
  [...fileList].forEach((f) => fd.append("files", f));
  try {
    const data = await api("/api/upload", { method: "POST", body: fd });
    state.files.push(...data.files);
    if (data.join) {
      // multiple files -> backend auto-detected the keys and joined them
      state.files = state.files.filter((f) => f.id !== "joined_auto");
      state.files.unshift(data.join.file);
      const keys = data.join.joins.map((j) => `${j.base_key}↔${j.other_key}`).join(", ");
      toast(`🔗 Auto-joined your files on ${keys} — map the "Joined dataset" for combined insights`, 8000);
    } else {
      toast(`Uploaded ${data.files.length} file(s) — now confirm the mapping`);
    }
    renderFileList();
    go("mapping");
  } catch (e) { toast("Upload failed: " + e.message); }
}

function renderFileList() {
  $("fileCount").textContent = state.files.length ? `${state.files.length} file(s) loaded` : "";
  const list = $("fileList");
  list.innerHTML = "";
  state.files.forEach((f) => {
    const item = document.createElement("div");
    item.className = "file-item";
    item.innerHTML = `<span class="fname" title="${f.name}">📄 ${f.name}</span>
      <span class="frows">${f.rows.toLocaleString()}</span>
      <button class="file-del" title="Delete file" aria-label="Delete ${f.name}">✕</button>`;
    item.querySelector(".file-del").onclick = async () => {
      try {
        const res = await api(`/api/files/${f.id}`, { method: "DELETE" });
        state.files = state.files.filter((x) => x.id !== f.id);
        state.mapped = res.mapped;
        renderFileList();
        if (document.querySelector("#page-mapping.active")) renderMapping();
        toast(`Deleted ${res.deleted}` + (res.mapped ? "" : state.files.length ? " — re-confirm mapping" : ""));
      } catch (e) { toast(e.message); }
    };
    list.appendChild(item);
  });
}

// ---------- sample data (one-click demo) ----------
on("demoBtn", async () => {
  $("demoBtn").disabled = true;
  $("demoBtn").textContent = "Loading sample data…";
  try {
    const d = await api("/api/demo", { method: "POST" });
    state.files.push(...d.files);
    state.mapped = d.mapped;
    renderFileList();
    toast("🛍️ Sample data loaded — 90 days of orders. Explore the Analytics tab!");
    go("analytics");
  } catch (e) { toast(e.message); }
  $("demoBtn").disabled = false;
  $("demoBtn").textContent = "✨ No file handy? Try with sample data";
});

// ---------- mapping ----------
const ROLES = ["date", "customer_id", "customer_name", "order_id", "product", "category", "subcategory", "quantity", "amount"];

function renderMapping() {
  const area = $("mappingArea");
  if (!state.files.length) {
    area.innerHTML = `<div class="card empty">Upload files first — use the panel on the left.</div>`;
    return;
  }
  area.innerHTML = "";
  state.files.forEach((f) => {
    const card = document.createElement("div");
    card.className = "card";
    const opts = (sel) => `<option value="">—</option>` + f.columns.map((c) => `<option ${c === sel ? "selected" : ""}>${c}</option>`).join("");
    card.innerHTML = `
      <h4>📄 ${f.name} <span class="subtle">· ${f.rows.toLocaleString()} rows · detected: ${f.kind}</span></h4>
      <div class="map-grid">
        ${ROLES.map((r) => `<label>${r}${["date","amount"].includes(r) ? " *" : ""}<select data-role="${r}">${opts(f.suggested_mapping[r])}</select></label>`).join("")}
      </div>
      <button class="primary-btn">Confirm mapping</button>
      <div class="table-wrap" style="margin-top:12px">
        <table><thead><tr>${f.columns.map((c) => `<th>${c}</th>`).join("")}</tr></thead>
        <tbody>${f.preview.map((row) => `<tr>${row.map((v) => `<td>${v}</td>`).join("")}</tr>`).join("")}</tbody></table>
      </div>`;
    card.querySelector("button").onclick = async () => {
      const mapping = {};
      card.querySelectorAll("select").forEach((s) => (mapping[s.dataset.role] = s.value || null));
      try {
        const res = await api("/api/mapping", { method: "POST", json: { file_id: f.id, mapping } });
        state.mapped = true;
        if (res.warning) {
          toast(`⚠️ ${res.warning}`, 8000);
        } else {
          toast(`Mapping done — ${res.rows.toLocaleString()} transactions ready`);
        }
        go("analytics");
      } catch (e) { toast(e.message); }
    };
    area.appendChild(card);
  });
}

// ---------- positioning (brand perception vs benchmark cafés) ----------
const posZone = $("posZone");
if (posZone) {
  posZone.onclick = () => $("posFileInput").click();
  ["dragover", "dragleave", "drop"].forEach((ev) =>
    posZone.addEventListener(ev, (e) => {
      e.preventDefault();
      posZone.classList.toggle("drag", ev === "dragover");
      if (ev === "drop") uploadPositioning(e.dataTransfer.files);
    })
  );
  $("posFileInput").onchange = (e) => uploadPositioning(e.target.files);
}

async function uploadPositioning(fileList) {
  if (!fileList || !fileList.length) return;
  window._lastPosFile = fileList[0];
  const area = $("posArea");
  area.innerHTML = `<div class="card empty">Reading your reviews and mapping your brand position…</div>`;
  const fd = new FormData();
  fd.append("files", fileList[0]);
  const ptq = state.productType ? `&product_type=${encodeURIComponent(state.productType)}` : "";
  try {
    const d = await apiOrPaywall(`/api/positioning?lang=${state.lang}${ptq}`, { method: "POST", body: fd });
    if (!d.available) { area.innerHTML = `<div class="card empty">${d.reason}</div>`; return; }
    renderPositioning(d);
  } catch (e) {
    area.innerHTML = `<div class="card empty">${e.message}</div>`;
  }
}

function renderPositioning(d) {
  const area = $("posArea");
  const pos = d.position || {};
  area.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
      <h3 style="margin:0;">✅ What to do about your positioning</h3>
      <button class="ghost-btn" id="posPdfBtn" style="font-size:12.5px;">📄 Download PDF report</button>
    </div>
    ${renderInsights(d.insights)}
    <div class="card" style="border-left:4px solid var(--accent);">
      <div class="subtle" style="font-size:12px;">Your position, read from your own reviews</div>
      <h3 style="margin:2px 0 0;">📍 ${escapeHtml(pos.quadrant || "—")}</h3>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="label">Reviews Analyzed</div><div class="value">${d.n_reviews.toLocaleString()}</div></div>
      <div class="kpi"><div class="label">Your Avg Rating</div><div class="value">${d.avg_rating ?? "—"}</div></div>
      <div class="kpi"><div class="label">Overall Sentiment</div><div class="value">${d.overall_sentiment > 0 ? "+" : ""}${d.overall_sentiment}</div></div>
    </div>
    <div class="card chart" id="chPosMap" style="min-height:480px;"></div>
    <div class="card chart" id="chPosShare"></div>
    <div class="card chart" id="chPosSent"></div>
    <p class="subtle" style="font-size:12px;">⚠️ ${escapeHtml(d.methodology_note || "")}</p>`;
  renderPositionMap(d.perceptual_map);
  plot($("chPosShare"), [
    { x: d.share_chart.themes, y: d.share_chart.yours, type: "bar", marker: { color: cssVar("--accent", "#6d28d9") } },
  ], "What your customers talk about (% of reviews)", { margin: { l: 52, r: 18, t: 8, b: 128 }, xaxis: { ...baseLayout().xaxis, tickangle: -35 } });
  plot($("chPosSent"), [
    { x: d.sentiment_chart.themes, y: d.sentiment_chart.yours, type: "bar", marker: { color: "#0ea5e9" } },
  ], "How positively they talk about it (sentiment)", { margin: { l: 52, r: 18, t: 8, b: 128 }, xaxis: { ...baseLayout().xaxis, tickangle: -35 } });
  on("posPdfBtn", () => downloadPagePdf("positioning", window._lastPosFile));
}

// Single-point positioning map: just YOU on the value↔premium × brand↔product 2x2.
function renderPositionMap(mp) {
  const el = $("chPosMap");
  if (!el || !mp || !plotlyReady(el)) return;
  const ax = mp.axis, ql = mp.quadrant_labels, you = mp.you;
  const canvas = chartShell(el, "Positioning map — where your brand sits on the two axes buyers judge you by");
  const accent = cssVar("--accent", "#6d28d9");
  const muted = cssVar("--muted", "#626b78");

  const traces = [{
    x: [you.x], y: [you.y], mode: "markers+text", type: "scatter",
    text: ["YOUR BRAND"], textposition: "middle right",
    textfont: { color: accent, size: 12.5, family: "Sora, Inter, sans-serif" },
    marker: { size: 22, color: accent, line: { color: cssVar("--surface", "#fff"), width: 3 } },
    cliponaxis: false,
    hovertemplate: `<b>Your brand</b><br>${escapeHtml(you.quadrant)}<extra></extra>`,
  }];
  const R = 1;
  const quadFill = (x0, x1, y0, y1, colour) => ({ type: "rect", xref: "x", yref: "y", x0, x1, y0, y1, fillcolor: colour, line: { width: 0 }, layer: "below" });
  const label = (x, y, txt, anchor) => ({ x, y, xref: "x", yref: "y", text: txt, showarrow: false,
    font: { size: 11, color: muted, family: "Sora, Inter, sans-serif" }, xanchor: anchor, yanchor: y > 0 ? "top" : "bottom",
    opacity: 0.9, xshift: anchor === "right" ? -8 : 8, yshift: y > 0 ? -6 : 6 });
  const layout = {
    ...baseLayout(), height: 440, margin: { l: 96, r: 40, t: 22, b: 78 }, showlegend: false, hovermode: "closest",
    xaxis: { range: [-R, R], zeroline: true, zerolinecolor: cssVar("--border-strong", "#cdd3dc"), zerolinewidth: 1.5, showgrid: false, showticklabels: false, ticks: "",
      title: { text: `← ${ax.x_neg}          ${ax.x_pos} →`, font: { size: 12, color: cssVar("--text-2", "#3d4450"), family: "Sora, Inter, sans-serif" } } },
    yaxis: { range: [-R, R], zeroline: true, zerolinecolor: cssVar("--border-strong", "#cdd3dc"), zerolinewidth: 1.5, showgrid: false, showticklabels: false, ticks: "",
      title: { text: `← ${ax.y_neg}          ${ax.y_pos} →`, font: { size: 12, color: cssVar("--text-2", "#3d4450"), family: "Sora, Inter, sans-serif" } } },
    shapes: [
      quadFill(0, R, 0, R, "rgba(16,185,129,.06)"), quadFill(-R, 0, 0, R, "rgba(14,165,233,.06)"),
      quadFill(0, R, -R, 0, "rgba(168,85,247,.06)"), quadFill(-R, 0, -R, 0, "rgba(245,158,11,.06)"),
    ],
    annotations: [ label(R, R, ql.tr, "right"), label(-R, R, ql.tl, "left"), label(R, -R, ql.br, "right"), label(-R, -R, ql.bl, "left") ],
  };
  Plotly.newPlot(canvas, traces, layout, PLOT_CFG);
  _registerChart(el, traces, "Positioning map — where your brand sits", layout);

  const readout = document.createElement("div");
  readout.className = "map-readout";
  readout.innerHTML = `<b>You sit in "${escapeHtml(you.quadrant)}."</b> Head to Position Strategy to strengthen this position or plan a move.`;
  el.appendChild(readout);
}

// ---------- position strategy (login-gated, saved per account) ----------
if ($("strategyLockLogin")) $("strategyLockLogin").onclick = () => { state.pendingPage = "strategy"; openLogin(); };

async function loadStrategy() {
  const lock = $("strategyLock"), app = $("strategyApp");
  if (!state.token) { if (lock) lock.hidden = false; if (app) app.hidden = true; return; }
  if (lock) lock.hidden = true;
  if (app) app.hidden = false;
  const area = $("strategyArea");
  area.innerHTML = `<div class="card empty">Loading your saved strategy…</div>`;
  try {
    const d = await api("/api/position-strategy");
    renderStrategy(d);
  } catch (e) {
    area.innerHTML = `<div class="card empty">${escapeHtml(e.message)}</div>`;
  }
}

function stratUploadZone(label) {
  return `
    <div class="upload-zone" id="stratZone" style="max-width:560px; margin:8px 0 4px;">
      <input type="file" id="stratFileInput" accept=".csv,.tsv,.txt,.xlsx,.xls,.json" hidden />
      <div class="upload-icon">⇪</div>
      <div>${label} — drop your reviews file or <span class="link">browse</span></div>
      <div class="subtle" style="font-size:11px;">Same Google/Zomato reviews file you'd use for Positioning</div>
      <div class="subtle" style="font-size:10.5px;">🔒 Private to your account.</div>
    </div>`;
}

function wireStratZone() {
  const z = $("stratZone");
  if (!z) return;
  z.onclick = () => $("stratFileInput").click();
  ["dragover", "dragleave", "drop"].forEach((ev) =>
    z.addEventListener(ev, (e) => {
      e.preventDefault();
      z.classList.toggle("drag", ev === "dragover");
      if (ev === "drop") detectStrategy(e.dataTransfer.files);
    })
  );
  $("stratFileInput").onchange = (e) => detectStrategy(e.target.files);
}

async function detectStrategy(fileList) {
  if (!fileList || !fileList.length) return;
  const area = $("strategyArea");
  const keep = area.innerHTML;
  area.querySelector("#stratZone") && (area.querySelector("#stratZone").outerHTML =
    `<div class="card empty">Reading your reviews and detecting your current position…</div>`);
  const fd = new FormData();
  fd.append("files", fileList[0]);
  try {
    const d = await api(`/api/position-strategy/detect?lang=${state.lang}`, { method: "POST", body: fd });
    toast("📍 Current position detected — now pick where you want to go");
    renderStrategy(d);
  } catch (e) {
    toast(e.message, 6000);
    area.innerHTML = keep;
    wireStratZone();
  }
}

function positionCardHtml(p, eyebrow) {
  return `
    <div class="strat-current">
      <div class="strat-eyebrow">${escapeHtml(eyebrow)}</div>
      <div class="strat-title">${escapeHtml(p.name)}</div>
      <div class="strat-tagline">${escapeHtml(p.tagline)}</div>
      <div class="proscons">
        <div class="col pros"><h5>✅ Pros</h5><ul>${p.pros.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>
        <div class="col cons"><h5>⚠️ Cons</h5><ul>${p.cons.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>
      </div>
    </div>`;
}

function renderStrategy(d) {
  const area = $("strategyArea");
  if (!d.detected) {
    area.innerHTML = `
      <div class="card">
        <h3 style="margin-top:0;">Step 1 · Where are you today?</h3>
        <p class="subtle">Upload your reviews. We'll place your brand on the positioning map and read back your current position — the same engine as the Positioning page.</p>
        ${stratUploadZone("Detect my current position")}
      </div>`;
    wireStratZone();
    return;
  }

  let html = positionCardHtml(d.current, `📍 You are here${d.n_reviews ? ` · from ${d.n_reviews} reviews` : ""}`);
  html += `<div style="display:flex; gap:10px; flex-wrap:wrap; margin:-4px 0 16px;">
      <button class="ghost-btn" id="stratRedetect" style="font-size:12.5px;">↻ Re-detect from new reviews</button>
      <button class="ghost-btn" id="stratReset" style="font-size:12.5px;">Start over</button>
    </div>`;

  html += `<div class="strat-section-head">Step 2 · Where do you want to go?</div>
    <p class="subtle" style="margin-top:2px;">Pick your current position to <b>strengthen where you are</b>, or a different one to reposition. "Adjacent move" changes one thing; "Big repositioning" changes both.</p>
    <div class="opt-grid">
      ${d.options.map((o) => `
        <div class="opt-card ${o.id === d.target_id ? "selected" : ""}" data-target="${o.id}">
          <span class="opt-diff ${o.is_current ? "stay" : (o.axes_changing === 1 ? "adjacent" : "big")}">${escapeHtml(o.difficulty)}</span>
          <h4>${escapeHtml(o.name)}${o.is_current ? " ★" : ""}</h4>
          <div class="mini">${escapeHtml(o.tagline)}</div>
        </div>`).join("")}
    </div>`;

  if (d.plan) {
    const pl = d.plan;
    const pct = pl.progress.total ? Math.round(pl.progress.done / pl.progress.total * 100) : 0;
    if (!pl.same_position) html += positionCardHtml(pl.target, "🎯 Your target");
    html += `<div class="gap-banner"><b>${pl.same_position ? "Plan:" : "The gap:"}</b> ${escapeHtml(pl.gap)}</div>`;
    html += `<div class="keep-box">
        <h4>Keep these the same</h4>
        <p class="subtle" style="margin:0;">${escapeHtml(pl.keep_note)}</p>
        <ul>${pl.keep_same.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>
      </div>`;
    html += `<div class="strat-section-head">Step 3 · Your levelled checklist</div>
      <p class="subtle" style="margin-top:2px;">Finish a level to unlock the next one.</p>
      <div class="progress-wrap">
        <div class="progress-bar"><div class="progress-fill" id="stratFill" style="width:${pct}%;"></div></div>
        <div class="progress-label" id="stratProgLabel">${pl.progress.done} of ${pl.progress.total} done (${pct}%)</div>
      </div>`;
    const levels = pl.levels || [...new Set(pl.checklist.map((it) => it.level || 1))].sort();
    const doneByLevel = {}, totByLevel = {};
    pl.checklist.forEach((it) => { const l = it.level || 1; totByLevel[l] = (totByLevel[l] || 0) + 1; if (it.done) doneByLevel[l] = (doneByLevel[l] || 0) + 1; });
    let prevComplete = true;
    levels.forEach((lv) => {
      const items = pl.checklist.filter((it) => (it.level || 1) === lv);
      const phaseName = (items[0] ? items[0].phase : `Level ${lv}`).replace(/^Level \d+ · /, "");
      const locked = !prevComplete;
      const levelDone = (doneByLevel[lv] || 0) === totByLevel[lv];
      html += `<div class="phase-head">🏁 Level ${lv} · ${escapeHtml(phaseName)} <span class="subtle" style="font-weight:400;">${doneByLevel[lv] || 0}/${totByLevel[lv]}</span>${locked ? ` <span style="color:var(--amber);">🔒 finish Level ${lv - 1} first</span>` : (levelDone ? ` <span style="color:var(--green);">✓ done</span>` : "")}</div>`;
      items.forEach((it) => {
        html += `<label class="check-item ${it.done ? "done" : ""}" data-item="${it.id}" style="${locked ? "opacity:.55;pointer-events:none;" : ""}">
            <input type="checkbox" ${it.done ? "checked" : ""} ${locked ? "disabled" : ""} />
            <div><div class="ctext">${escapeHtml(it.text)}</div><div class="cwhy">Why: ${escapeHtml(it.why)}</div></div>
          </label>`;
      });
      prevComplete = prevComplete && levelDone;
    });
  } else {
    html += `<div class="card empty" style="margin-top:14px;">Choose an option above to get your keep-list and levelled checklist.</div>`;
  }

  area.innerHTML = html;

  on("stratRedetect", () => {
    area.innerHTML = `<div class="card"><h3 style="margin-top:0;">Re-detect your position</h3>${stratUploadZone("Upload newer reviews")}</div>`;
    wireStratZone();
  });
  on("stratReset", async () => {
    try { await api("/api/position-strategy/reset", { method: "POST" }); toast("Reset — start fresh"); loadStrategy(); }
    catch (e) { toast(e.message); }
  });
  area.querySelectorAll(".opt-card").forEach((c) => c.onclick = () => selectTarget(c.dataset.target));
  area.querySelectorAll(".check-item input").forEach((chk) => chk.onchange = async () => {
    const item = chk.closest(".check-item");
    try {
      await api("/api/position-strategy/check", { method: "POST", json: { item_id: item.dataset.item, done: chk.checked } });
      // refetch so level-unlock gating is recomputed correctly
      const d = await api("/api/position-strategy");
      renderStrategy(d);
    } catch (e) { chk.checked = !chk.checked; toast(e.message); }
  });
}

async function selectTarget(targetId) {
  try {
    const d = await api("/api/position-strategy/target", { method: "POST", json: { target_id: targetId } });
    renderStrategy(d);
  } catch (e) { toast(e.message, 5000); }
}

async function toggleCheck(itemId, done, itemEl) {
  itemEl.classList.toggle("done", done);
  try {
    await api("/api/position-strategy/check", { method: "POST", json: { item_id: itemId, done } });
    // recompute progress from the DOM (cheap, avoids a refetch)
    const items = document.querySelectorAll("#strategyArea .check-item input");
    const total = items.length;
    const doneCount = [...items].filter((i) => i.checked).length;
    const pct = total ? Math.round(doneCount / total * 100) : 0;
    const fill = $("stratFill"), label = $("stratProgLabel");
    if (fill) fill.style.width = pct + "%";
    if (label) label.textContent = `${doneCount} of ${total} done (${pct}%)`;
  } catch (e) {
    itemEl.classList.toggle("done", !done);
    if (itemEl.querySelector("input")) itemEl.querySelector("input").checked = !done;
    toast(e.message);
  }
}

// ---------- analytics ----------
async function loadAnalytics() {
  const area = $("analyticsArea");
  try {
    const d = await api(`/api/analytics?lang=${state.lang}`);
    const k = d.kpis;
    const fmt = (n) => n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
    area.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
        <h3 style="margin:0;">✅ What to do next</h3>
        <button class="ghost-btn" id="pdfBtn" style="font-size:12.5px;">📄 Download PDF report</button>
      </div>
      ${renderInsights(d.insights)}
      <p class="subtle">${k.date_from} → ${k.date_to}</p>
      <div class="kpis">
        <div class="kpi"><div class="label">Revenue</div><div class="value">${fmt(k.revenue)}</div></div>
        <div class="kpi"><div class="label">Orders</div><div class="value">${fmt(k.orders)}</div></div>
        <div class="kpi"><div class="label">Customers</div><div class="value">${fmt(k.customers)}</div></div>
        <div class="kpi"><div class="label">Avg Order Value</div><div class="value">${fmt(k.avg_order_value)}</div></div>
      </div>
      <div class="card chart" id="chMonthly"></div>
      ${d.forecast ? `<div class="card chart" id="chForecast"></div>` : ""}
      <div class="grid-2">
        ${d.by_category ? `<div class="card chart" id="chCategory"></div>` : ""}
        <div class="card chart" id="chWeekday"></div>
        ${d.top_products ? `<div class="card chart" id="chProducts"></div>` : ""}
      </div>`;
    plot($("chMonthly"), [{
      x: d.monthly_trend.x, y: d.monthly_trend.y, type: "scatter", mode: "lines+markers",
      line: { width: 2.5, shape: "spline", smoothing: 0.4 }, marker: { size: 6 },
      fill: "tozeroy", fillcolor: accentFill(0.10),
      hovertemplate: "%{x}<br><b>₹%{y:,.0f}</b><extra></extra>",
    }], "Monthly revenue", { yaxis: { ...baseLayout().yaxis, tickprefix: "₹" }, hovermode: "x unified" });
    if (d.forecast) {
      const f = d.forecast;
      plot($("chForecast"), [
        { x: f.hist_x, y: f.hist_y, type: "scatter", mode: "lines", name: "Actual (last 60 days)",
          line: { color: cssVar("--accent", "#6d28d9"), width: 2.5 },
          hovertemplate: "%{x}<br><b>₹%{y:,.0f}</b><extra>Actual</extra>" },
        { x: f.fcst_x, y: f.fcst_y, type: "scatter", mode: "lines", name: "Forecast (next 30 days)",
          line: { color: cssVar("--green", "#0a7a4d"), width: 2.5, dash: "dash" },
          hovertemplate: "%{x}<br><b>₹%{y:,.0f}</b><extra>Forecast</extra>" },
      ], `Next 30 days — about ₹${Number(f.next_30_total).toLocaleString("en-IN")} (${f.vs_last_30_pct >= 0 ? "+" : ""}${f.vs_last_30_pct}% vs last 30 days)`,
         { yaxis: { ...baseLayout().yaxis, tickprefix: "₹" }, margin: { l: 62, r: 18, t: 8, b: 58 } });
    }
    on("pdfBtn", downloadPdfReport);
    if (d.by_category) plot($("chCategory"), [{
      x: d.by_category.x, y: d.by_category.y, type: "bar",
      marker: { color: cssVar("--accent", "#6d28d9") },
      hovertemplate: "%{x}<br><b>₹%{y:,.0f}</b><extra></extra>",
    }], "Revenue by category", { yaxis: { ...baseLayout().yaxis, tickprefix: "₹" }, bargap: 0.45 });
    plot($("chWeekday"), [{
      x: d.weekday_pattern.x, y: d.weekday_pattern.y, type: "bar",
      marker: { color: "#0ea5e9" },
      hovertemplate: "%{x}<br><b>₹%{y:,.0f}</b><extra></extra>",
    }], "Revenue by weekday", { yaxis: { ...baseLayout().yaxis, tickprefix: "₹" }, bargap: 0.45 });
    if (d.top_products) plot($("chProducts"), [{
      x: d.top_products.x, y: d.top_products.y, type: "bar", orientation: "h",
      marker: { color: "#10b981" },
      text: d.top_products.x.map((v) => "₹" + Number(v).toLocaleString("en-IN")),
      textposition: "outside", cliponaxis: false,
      textfont: { size: 11, color: cssVar("--muted", "#626b78") },
      hovertemplate: "%{y}<br><b>₹%{x:,.0f}</b><extra></extra>",
    }], "Top products", {
      xaxis: { ...baseLayout().xaxis, showgrid: true, tickprefix: "₹" },
      yaxis: { ...baseLayout().yaxis, showgrid: false, autorange: "reversed" },
      margin: { l: 172, r: 46, t: 8, b: 34 }, bargap: 0.42,
    });
  } catch (e) {
    area.innerHTML = `<div class="card empty">${e.message}</div>`;
  }
}

// ---------- subcategory ----------
async function loadSubcategory() {
  const area = $("subcatArea");
  const filterRow = $("subcatFilterRow");
  const select = $("subcatFilterSelect");
  try {
    const d = await api(`/api/subcategory?lang=${state.lang}`);
    if (!d.available) {
      area.innerHTML = `<div class="card empty">${d.reason}</div>`;
      filterRow.hidden = true;
      return;
    }
    filterRow.hidden = false;
    select.innerHTML = `<option value="">All (overview)</option>` +
      d.all_values.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
    select.onchange = () => (select.value ? renderSubcatDetail(select.value) : renderSubcatOverview(d));
    renderSubcatOverview(d);
  } catch (e) {
    area.innerHTML = `<div class="card empty">${e.message}</div>`;
    filterRow.hidden = true;
  }
}

function renderSubcatOverview(d) {
  const area = $("subcatArea");
  area.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
      <h3 style="margin:0;">✅ What to do across ${d.field === "subcategory" ? "sub-categories" : "categories"}</h3>
      <button class="ghost-btn" id="subPdfBtn" style="font-size:12.5px;">📄 Download PDF report</button>
    </div>
    ${renderInsights(d.insights)}
    <div class="card chart" id="chSubTrend"></div>
    <div class="card chart" id="chSubTotals"></div>`;
  on("subPdfBtn", downloadPdfReport);
  plot($("chSubTrend"), d.series.map((s) => ({ x: s.x, y: s.y, name: s.name, type: "scatter", mode: "lines+markers" })), "Monthly trend — top 8");
  plot($("chSubTotals"), [{ x: d.totals.x, y: d.totals.y, type: "bar" }], "Total revenue");
}

async function renderSubcatDetail(value) {
  const area = $("subcatArea");
  area.innerHTML = `<div class="card empty">Loading ${value}…</div>`;
  try {
    const d = await api(`/api/subcategory/detail?value=${encodeURIComponent(value)}&lang=${state.lang}`);
    if (!d.available) { area.innerHTML = `<div class="card empty">${d.reason}</div>`; return; }
    const k = d.kpis;
    const fmt = (n) => n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
    area.innerHTML = `
      <h3 style="margin-top:0;">✅ ${escapeHtml(value)} — what to do, ranked by impact</h3>
      ${renderInsights(d.insights)}
      <div class="kpis">
        <div class="kpi"><div class="label">Revenue</div><div class="value">₹${fmt(k.revenue)}</div></div>
        <div class="kpi"><div class="label">Orders</div><div class="value">${fmt(k.orders)}</div></div>
        <div class="kpi"><div class="label">Avg Order Value</div><div class="value">₹${fmt(k.avg_order_value)}</div></div>
        <div class="kpi"><div class="label">Share of Total Revenue</div><div class="value">${k.share_of_total_pct}%</div></div>
      </div>
      <div class="card chart" id="chDetailTrend"></div>
      <div class="grid-2">
        <div class="card chart" id="chDetailWeekday"></div>
        ${d.top_products ? `<div class="card chart" id="chDetailProducts"></div>` : ""}
      </div>`;
    plot($("chDetailTrend"), [{ x: d.monthly_trend.x, y: d.monthly_trend.y, type: "scatter", mode: "lines+markers", fill: "tozeroy", fillcolor: accentFill(0.10), hovertemplate: "%{x}<br><b>₹%{y:,.0f}</b><extra></extra>" }], `${value} — monthly revenue`, { yaxis: { ...baseLayout().yaxis, tickprefix: "₹" } });
    plot($("chDetailWeekday"), [{ x: d.weekday_pattern.x, y: d.weekday_pattern.y, type: "bar", marker: { color: "#0ea5e9" }, hovertemplate: "%{x}<br><b>₹%{y:,.0f}</b><extra></extra>" }], `${value} — revenue by weekday`, { yaxis: { ...baseLayout().yaxis, tickprefix: "₹" } });
    if (d.top_products) plot($("chDetailProducts"), [{ x: d.top_products.x, y: d.top_products.y, type: "bar", orientation: "h", marker: { color: "#10b981" }, hovertemplate: "%{y}<br><b>₹%{x:,.0f}</b><extra></extra>" }], `Top items in ${value}`, { xaxis: { ...baseLayout().xaxis, showgrid: true, tickprefix: "₹" }, yaxis: { ...baseLayout().yaxis, showgrid: false }, margin: { l: 172, r: 46, t: 8, b: 34 } });
  } catch (e) {
    area.innerHTML = `<div class="card empty">${e.message}</div>`;
  }
}

// ---------- rfm ----------
async function loadRFM() {
  const area = $("rfmArea");
  const winbackCard = $("winbackCard");
  try {
    const d = await api("/api/rfm");
    if (!d.available) {
      area.innerHTML = `<div class="card empty">${d.reason}</div>`;
      winbackCard.hidden = true;
      return;
    }
    area.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:6px;">
      <p class="subtle" style="margin:0;">${d.customer_count.toLocaleString()} customers scored (R·F·M quintiles, 5 = best). Showing top 500 by spend.</p>
      <button class="ghost-btn" id="rfmPdfBtn" style="font-size:12.5px;">📄 Download PDF report</button>
      </div>
      <div class="card chart" id="chSegments"></div>
      <div class="table-wrap"><table><thead><tr>${d.columns.map((c) => `<th>${c}</th>`).join("")}</tr></thead>
      <tbody>${d.rows.map((r) => `<tr>${r.map((v) => `<td>${v}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    on("rfmPdfBtn", downloadPdfReport);
    plot($("chSegments"), [{ type: "pie", labels: d.segments.labels, values: d.segments.values, hole: 0.45 }], "Customer segments");
    const hasAtRisk = d.segments.labels.includes("At Risk");
    winbackCard.hidden = !hasAtRisk;
    if (hasAtRisk && $("winbackArea")) $("winbackArea").innerHTML = "";
  } catch (e) {
    area.innerHTML = `<div class="card empty">${e.message}</div>`;
    winbackCard.hidden = true;
  }
}

// ---------- win-back messages (editable popup) ----------
let _wbRows = [];
const WB_COLS = [
  { k: "customer_name", label: "Customer" },
  { k: "favorite_item", label: "Favourite" },
  { k: "last_purchase_date", label: "Last order" },
  { k: "monetary", label: "Spend" },
  { k: "coupon_code", label: "Coupon" },
  { k: "discount_pct", label: "Disc %" },
  { k: "message", label: "Message" },
];
$("genWinbackBtn").onclick = async () => {
  if (!state.token) { state.pendingPage = "rfm"; openLogin(); return; }
  const btn = $("genWinbackBtn");
  btn.disabled = true; btn.textContent = "Building offers…";
  try {
    const d = await apiOrPaywall("/api/rfm/winback", { method: "POST" });
    refreshUserUI(d.usage);
    if (!d.customers.length) { toast("No at-risk customers with enough history to message.", 5000); }
    else { _wbRows = d.customers.map((c) => ({ ...c })); openWinbackModal(); }
  } catch (e) { if (e.code !== "paywall") toast(e.message, 6000); }
  btn.disabled = false; btn.textContent = "Generate messages";
};

function openWinbackModal() {
  renderWinbackTable();
  const m = $("winbackModal"); if (m) { m.hidden = false; m.style.display = "flex"; }
}
function closeWinbackModal() { const m = $("winbackModal"); if (m) { m.hidden = true; m.style.display = "none"; } }
function renderWinbackTable() {
  const head = `<tr>${WB_COLS.map((c) => `<th>${c.label}</th>`).join("")}<th></th></tr>`;
  const body = _wbRows.map((r, i) => `<tr data-r="${i}">${WB_COLS.map((c) =>
    `<td><input data-k="${c.k}" value="${escapeHtml(r[c.k] == null ? "" : r[c.k])}" /></td>`).join("")}
    <td><button class="ghost-btn wb-del" data-del="${i}" title="Remove row">✕</button></td></tr>`).join("");
  $("winbackTable").innerHTML = `<table class="wb-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
  $("winbackTable").querySelectorAll("input").forEach((inp) => inp.onchange = (e) => {
    const tr = e.target.closest("tr"); _wbRows[+tr.dataset.r][e.target.dataset.k] = e.target.value;
  });
  $("winbackTable").querySelectorAll("[data-del]").forEach((b) => b.onclick = () => { _wbRows.splice(+b.dataset.del, 1); renderWinbackTable(); });
}
on("winbackAddRow", () => { _wbRows.push({}); renderWinbackTable(); });
on("winbackClose", closeWinbackModal);
on("winbackCancel", closeWinbackModal);
on("winbackExport", async () => {
  if (!_wbRows.length) { toast("List is empty."); return; }
  try {
    const res = await fetch("/api/rfm/winback/export", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-Id": state.sessionId, "Authorization": "Bearer " + state.token },
      body: JSON.stringify({ rows: _wbRows }),
    });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || "Export failed"); }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "winback_messages.xlsx";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
    toast("📄 Win-back list exported!");
    closeWinbackModal();
  } catch (e) { toast(e.message, 6000); }
});
(function () {
  const wm = $("winbackModal");
  if (wm) wm.addEventListener("click", (e) => { if (e.target === wm) closeWinbackModal(); });
})();

// ---------- analyst AI ----------
$("runAnalystBtn").onclick = async () => {
  const btn = $("runAnalystBtn");
  const area = $("analystArea");
  btn.disabled = true;
  area.innerHTML = `<div class="card empty">Analyzing your data with GPT — this can take up to a minute…</div>`;
  try {
    const d = await apiOrPaywall("/api/analyst", { method: "POST" });
    refreshUserUI(d.usage);
    area.innerHTML = "";
    d.results.forEach((file, fi) => {
      const h = document.createElement("h3");
      h.textContent = "📄 " + file.file;
      area.appendChild(h);
      if (!file.insights.length) {
        area.insertAdjacentHTML("beforeend", `<div class="card empty">No insights generated for this file.</div>`);
        return;
      }
      file.insights.forEach((ins, ii) => {
        const card = document.createElement("div");
        card.className = "card insight";
        card.innerHTML = `
          <h4>🔎 ${ins.decision || ""}</h4>
          <div class="row"><span class="k">OBSERVATION</span>${ins.observation || ""}</div>
          <div class="row"><span class="k">WHY</span>${ins.why_it_matters || ""}</div>
          <div class="row"><span class="k">ACTION</span>${ins.action || ""}</div>
          <div class="row"><span class="k">IMPACT</span>${ins.impact || ""}</div>
          ${ins.chart ? `<div class="chart" id="insChart-${fi}-${ii}"></div>` : `<p class="subtle">No chart for this insight.</p>`}`;
        area.appendChild(card);
        if (ins.chart) renderChartSpec($(`insChart-${fi}-${ii}`), ins.chart);
      });
    });
  } catch (e) {
    area.innerHTML = `<div class="card empty">${e.message}</div>`;
  }
  btn.disabled = false;
};

// ---------- chatbot ----------
$("chatSendBtn").onclick = sendChat;
$("chatInput").addEventListener("keydown", (e) => e.key === "Enter" && sendChat());

function addMsg(role, text, cls = "") {
  const win = $("chatWindow");
  win.querySelector(".chat-empty")?.remove();
  const div = document.createElement("div");
  div.className = `msg ${role} ${cls}`;
  div.textContent = text;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
  return div;
}

async function sendChat() {
  const input = $("chatInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  addMsg("user", text);
  const thinking = addMsg("assistant", "Thinking…", "thinking");
  try {
    const d = await apiOrPaywall("/api/chat", { method: "POST", json: { message: text } });
    refreshUserUI(d.usage);
    thinking.classList.remove("thinking");
    thinking.textContent = d.reply;
    if (d.chart) {
      const holder = document.createElement("div");
      holder.className = "msg assistant chart";
      holder.style.maxWidth = "95%";
      $("chatWindow").appendChild(holder);
      renderChartSpec(holder, d.chart);
      $("chatWindow").scrollTop = $("chatWindow").scrollHeight;
    }
  } catch (e) {
    thinking.classList.remove("thinking");
    thinking.textContent = "⚠️ " + e.message;
  }
}

// ---------- complaints intelligence (premium: Complaint Trends Report) ----------
const compZone = $("compZone");
if (compZone) {
  compZone.onclick = () => $("compFileInput").click();
  compZone.ondragover = (e) => { e.preventDefault(); compZone.classList.add("drag"); };
  compZone.ondragleave = () => compZone.classList.remove("drag");
  compZone.ondrop = (e) => { e.preventDefault(); compZone.classList.remove("drag"); uploadComplaints(e.dataTransfer.files); };
  $("compFileInput").onchange = (e) => uploadComplaints(e.target.files);
}

async function uploadComplaints(fileList) {
  if (!fileList.length) return;
  window._lastCompFile = fileList[0];
  const area = $("compArea");
  area.innerHTML = `<div class="card empty">Reading your reviews and finding complaint patterns…</div>`;
  const fd = new FormData();
  fd.append("files", fileList[0]);
  const ptq = state.productType ? `?product_type=${encodeURIComponent(state.productType)}` : "";
  try {
    const d = await apiOrPaywall("/api/complaints" + ptq, { method: "POST", body: fd });
    renderComplaints(d);
  } catch (e) {
    if (e.code !== "paywall") area.innerHTML = `<div class="card empty">⚠️ ${escapeHtml(e.message)}</div>`;
    else area.innerHTML = "";
  }
}

function renderComplaints(d) {
  const area = $("compArea");
  const det = d.detected;
  if (!d.actions.length) {
    area.innerHTML = `<div class="card empty">🎉 Good news — out of ${det.n_reviews} reviews we found almost no complaints. Keep doing what you're doing.</div>`;
    return;
  }
  const sevColor = {
    "Critical": cssVar("--red", "#c02626"),
    "High Priority": "#e06a1b",
    "Medium Priority": cssVar("--amber", "#a8620a"),
    "Low Priority": cssVar("--muted", "#626b78"),
  };

  // ---- THE FOCUS FRAMEWORK: where to concentrate (leads the page) ----
  const f = d.focus;
  const focusBlock = f && f.focus_now.length ? `
    <div class="focus-box">
      <div class="focus-head">🎯 Focus here first — don't fix everything at once</div>
      <p class="subtle" style="margin:2px 0 12px;">${escapeHtml(f.principle)}</p>
      ${f.focus_now.map((x, i) => `
        <div class="focus-item">
          <div class="focus-rank">${i + 1}</div>
          <div style="flex:1;">
            <div style="font-weight:700; font-size:15px;">${escapeHtml(x.theme)}
              <span class="focus-badge" style="background:${sevColor[x.severity]}22; color:${sevColor[x.severity]};">${escapeHtml(x.severity)}</span>
              ${x.growth_pct != null && x.growth_pct > 20 ? `<span class="focus-badge" style="background:var(--red-soft); color:var(--red);">rising ↗ ${x.growth_pct}%</span>` : ""}
            </div>
            <div class="focus-action">✅ ${escapeHtml(x.action)}</div>
            <div class="subtle" style="font-size:12px; margin-top:4px;">${x.count} complaints · ${x.share_pct}% of all · focus score ${x.focus_score}</div>
          </div>
        </div>`).join("")}
      ${f.watch.length ? `<div class="focus-watch">👁️ Watch (fix only after the above): ${f.watch.map((w) => `${escapeHtml(w.theme)} (${w.count})`).join(" · ")}</div>` : ""}
    </div>` : "";

  // ---- monthly complaint volume (the "how many per month" ask) ----
  const m = d.monthly;
  const monthlyBlock = m ? `
    <div class="card" style="margin:14px 0;">
      <div style="display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px;">
        <h4 style="margin:0;">📅 Complaints per month</h4>
        <div class="subtle" style="font-size:13px;">Averaging <b style="color:var(--text);">${m.avg_per_month}/month</b> · latest (${m.latest_month}): <b style="color:var(--text);">${m.latest_count}</b> · ${m.mom_change_pct >= 0 ? `<span style="color:var(--red);">up ${m.mom_change_pct}% vs earlier</span>` : `<span style="color:var(--green);">down ${Math.abs(m.mom_change_pct)}% vs earlier</span>`}</div>
      </div>
      <div class="card chart" id="chCompMonthly" style="margin-top:10px; border:none; padding:0;"></div>
    </div>` : "";

  const ig = d.ignored;
  const ignoredNote = ig && ig.themes ? `<p class="subtle" style="font-size:11.5px;">Set aside ${ig.complaints} one-off complaints across ${ig.themes} minor theme(s) (${ig.examples.join(", ")}) — too few to be a pattern worth chasing.</p>` : "";

  area.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
      <h3 style="margin:0;">✅ What to do first</h3>
      <button class="ghost-btn" id="compPdfBtn" style="font-size:12.5px;">📄 Download PDF report</button>
    </div>
    ${focusBlock}
    <p class="subtle">${det.n_reviews} reviews analysed · ${det.n_complaints} complaints found (${det.complaint_rate}% complaint rate)</p>
    ${ignoredNote}
    ${monthlyBlock}
    ${d.trend ? `<div class="card chart" id="chCompTrend"></div>` : `<div class="card empty">No usable dates found in the file — trend needs a date column.</div>`}
    <div class="card chart" id="chCompQuad"></div>
    <h3>🔎 Deep analysis</h3>
    <div class="table-wrap"><table>
      <thead><tr><th>Theme</th><th>Complaints</th><th>Share</th><th>Severity</th><th>Avg rating</th><th>Trend</th><th>Example (from your reviews)</th></tr></thead>
      <tbody>${d.deep.map((r) => `<tr>
        <td><b>${escapeHtml(r.theme)}</b></td><td>${r.count}</td><td>${r.share_pct}%</td>
        <td style="color:${sevColor[r.severity] || "#64748b"};">${r.severity}</td>
        <td>${r.avg_rating ?? "—"}</td>
        <td>${r.growth_pct == null ? "—" : (r.growth_pct >= 0 ? "+" : "") + r.growth_pct + "%"}</td>
        <td class="subtle" style="max-width:280px;">"${escapeHtml(r.example)}…"</td></tr>`).join("")}
      </tbody></table></div>`;

  on("compPdfBtn", () => downloadPagePdf("complaints", window._lastCompFile));

  // monthly complaint volume bars
  if (m) {
    plot($("chCompMonthly"),
      [{ x: m.months, y: m.counts, type: "bar", marker: { color: "#f97316" }, name: "Complaints" }],
      "Complaints per month", { yaxis: { title: "Complaints" } });
  }

  // 2) complaint TREND — monthly rolling complaint rate per theme (notebook engine)
  if (d.trend) {
    plot($("chCompTrend"),
      d.trend.series.map((sr) => ({ x: d.trend.months, y: sr.rolling_rate, type: "scatter", mode: "lines+markers", name: sr.name })),
      "Complaint trends — 3-month rolling complaint rate (% of reviews)");
  }

  // 3) complaint QUADRANT — frequency share x severity
  const q = d.quadrant;
  const qColors = { "Fix First": "#ef4444", "Contain Risk": "#f97316", "Streamline Ops": "#eab308", "Monitor": "#64748b" };
  const traces = Object.keys(qColors).map((quad) => {
    const pts = q.points.filter((p) => p.quadrant === quad);
    return { x: pts.map((p) => p.share_pct), y: pts.map((p) => p.severity_num), text: pts.map((p) => p.theme),
             mode: "markers+text", textposition: "top center", type: "scatter", name: quad,
             marker: { size: pts.map((p) => Math.max(10, Math.min(26, p.count))), color: qColors[quad] } };
  }).filter((t) => t.x.length);
  plot($("chCompQuad"), traces, "Complaint quadrant — share of complaints × business severity", {
    xaxis: { title: "Share of all complaints (%)" },
    yaxis: { title: "Severity", tickvals: [1, 2, 3, 4], ticktext: ["Low", "Medium", "High", "Critical"], range: [0.5, 4.6] },
    shapes: [
      { type: "line", x0: q.share_median, x1: q.share_median, y0: 0.5, y1: 4.6, line: { color: cssVar("--muted", "#626b78"), dash: "dot", width: 1 } },
      { type: "line", x0: 0, x1: Math.max(...q.points.map((p) => p.share_pct)) * 1.15, y0: q.severity_line, y1: q.severity_line, line: { color: cssVar("--muted", "#626b78"), dash: "dot", width: 1 } },
    ],
  });
}

// ---------- menu engineering (slow-item beverage bundles + quadrant) ----------
function renderMenuEngineering(me) {
  const c = me.counts || {};
  const bundleRows = (me.bundles || []).map((b) => `
    <tr>
      <td><b>${escapeHtml(b.item)}</b><div class="subtle" style="font-size:11px;">${escapeHtml(b.quadrant)} · ${b.units} units</div></td>
      <td style="font-size:18px; color:var(--accent); text-align:center;">+</td>
      <td><b>🥤 ${escapeHtml(b.pair_with)}</b><div class="subtle" style="font-size:11px;">${escapeHtml(b.reason)}</div></td>
    </tr>`).join("");

  return `
    <h3 style="margin-top:22px;">🍽️ Menu engineering — move your slow items</h3>
    <p class="subtle" style="margin-top:-4px;">Every item scored on how much it sells (popularity) vs its price (profit proxy). Your slow food items, each paired with the drink most likely to pull it along.</p>
    <div class="card chart" id="chMenuQuad"></div>
    ${bundleRows ? `
      <div class="card" style="margin-top:14px;">
        <h4 style="margin:0 0 4px;">✅ Do this: put these combos on your board</h4>
        <p class="subtle" style="margin:0 0 10px; font-size:12px;">Slow food moves fastest riding on a drink customers already want. Price each combo just below buying the two separately.</p>
        <div class="table-wrap"><table>
          <thead><tr><th>Slow item</th><th></th><th>Sell it with</th></tr></thead>
          <tbody>${bundleRows}</tbody>
        </table></div>
      </div>` : ""}
    <p class="subtle" style="font-size:11px; margin-top:8px;">${escapeHtml(me.method_note || "")}</p>`;
}

function plotMenuQuadrant(me) {
  const el = $("chMenuQuad");
  if (!el || !me.points) return;
  const colors = { Star: "#22c55e", Plowhorse: "#3b82f6", Puzzle: "#f59e0b", Dog: "#ef4444" };
  const traces = ["Star", "Puzzle", "Plowhorse", "Dog"].map((q) => {
    const pts = me.points.filter((p) => p.quadrant === q);
    return {
      x: pts.map((p) => p.units), y: pts.map((p) => p.avg_price), text: pts.map((p) => p.product),
      mode: "markers+text", textposition: "top center", textfont: { size: 9 }, type: "scatter",
      name: `${q} (${pts.length})`,
      marker: { size: pts.map((p) => Math.max(9, Math.min(30, Math.sqrt(p.revenue) / 6))), color: colors[q], opacity: 0.8 },
    };
  }).filter((t) => t.x.length);
  plot(el, traces, "Menu quadrant — popularity × price (bubble = revenue)", {
    xaxis: { title: "Units sold →" },
    yaxis: { title: "Avg price (₹) →" },
    shapes: [
      { type: "line", x0: me.medians.units, x1: me.medians.units, y0: 0, y1: Math.max(...me.points.map((p) => p.avg_price)) * 1.1, line: { color: cssVar("--muted", "#626b78"), dash: "dot", width: 1 } },
      { type: "line", x0: 0, x1: Math.max(...me.points.map((p) => p.units)) * 1.1, y0: me.medians.avg_price, y1: me.medians.avg_price, line: { color: cssVar("--muted", "#626b78"), dash: "dot", width: 1 } },
    ],
  });
}

// ---------- PDF report download ----------
async function downloadPdfReport() {
  const btn = $("pdfBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Building your report…"; }
  try {
    const res = await fetch(`/api/report/pdf?lang=${state.lang}`, { headers: { "X-Session-Id": state.sessionId } });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : "Could not build the report — confirm a mapping first");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "content_seller_sales_report.pdf";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast("📄 Report downloaded!");
  } catch (e) { toast(e.message, 6000); }
  if (btn) { btn.disabled = false; btn.textContent = "📄 Download PDF report"; }
}

// ---------- connect your POS ----------
on("posConnectBtn", openPosModal);
on("posModalClose", () => { $("posModal").style.display = "none"; });

async function openPosModal() {
  const modal = $("posModal");
  const body = $("posModalBody");
  modal.style.display = "flex";
  body.innerHTML = `<p class="subtle">Loading…</p>`;
  try {
    const d = await api("/api/connectors");
    const live = d.connectors.filter((c) => !c.id.startsWith("mock_"));
    const demos = d.connectors.filter((c) => c.id.startsWith("mock_"));
    body.innerHTML = `
      <div class="focus-box" style="border-left-color:var(--green);">
        <div class="focus-head" style="font-size:14.5px;">📧 Set it once, forget it forever</div>
        <p class="subtle" style="margin:4px 0 8px;">Your POS can already email your sales report on a schedule — most owners set this up for their accountant. Add one more address and Content Seller updates itself. No login, no file, no website.</p>
        <ol class="steps" style="margin:0 0 4px 18px; font-size:12.5px;">
          <li>In your POS (PetPooja: Reports → Automate report alerts), turn on scheduled email reports</li>
          <li>Add <b>reports@cafex.app</b> as a recipient (or CC)</li>
          <li>That's it — your next scheduled report becomes your next Content Seller dashboard, automatically</li>
        </ol>
      </div>
      <p class="subtle" style="margin:12px 0 4px;">Prefer to do it right now instead? These formats are recognised automatically — no mapping screen:</p>
      <ul class="steps" style="margin-bottom:14px;">
        ${d.supported_exports.map((s) => `<li>${escapeHtml(s.report)}</li>`).join("")}
      </ul>
      <h4 style="margin:14px 0 6px;">Try a live pull (demo feed)</h4>
      <p class="subtle" style="font-size:12px; margin:0 0 8px;">Runs the real connector code against a simulated POS feed — useful to see how a connected store's dashboard would look.</p>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        ${demos.map((c) => `<button class="ghost-btn" data-pull="${c.id}" style="font-size:12.5px;">▶ ${escapeHtml(c.label)}</button>`).join("")}
      </div>
      <h4 style="margin:16px 0 6px;">Direct API connections</h4>
      ${live.map((c) => `
        <div class="price-item" style="margin-bottom:8px;">
          <div><b>${escapeHtml(c.label)}</b>
            <span class="focus-badge" style="background:var(--amber-soft); color:var(--amber);">${c.verified ? "ready" : "not yet live"}</span>
          </div>
          <div class="subtle" style="font-size:11.5px;">Needs: ${c.needs.join(", ")}</div>
        </div>`).join("")}
      <p class="subtle" style="font-size:11.5px;">Direct API access is issued by each POS vendor per integration. The auto-email route above gives an equivalent hands-off experience today.</p>`;
    body.querySelectorAll("[data-pull]").forEach((b) => {
      b.onclick = () => pullFromPos(b.getAttribute("data-pull"));
    });
  } catch (e) {
    body.innerHTML = `<p class="subtle">${escapeHtml(e.message)}</p>`;
  }
}

async function pullFromPos(connectorId) {
  const body = $("posModalBody");
  body.innerHTML = `<p class="subtle">Pulling orders from ${escapeHtml(connectorId)}…</p>`;
  try {
    const d = await api("/api/connectors/pull", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connector: connectorId, credentials: {}, days: 90 }),
    });
    state.files.push(d.file);
    renderFileList();
    $("posModal").style.display = "none";
    toast(`🔌 Pulled ${d.rows.toLocaleString()} rows (${d.from} → ${d.to}) — already mapped`, 6000);
    go("analytics");
  } catch (e) {
    body.innerHTML = `<p class="subtle">⚠️ ${escapeHtml(e.message)}</p>`;
  }
}

// ---------- generic per-page PDF (file-based pages: complaints, positioning) ----------
async function downloadPagePdf(page, file, btnId) {
  const endpoints = { complaints: "/api/complaints/pdf", positioning: `/api/positioning/pdf?lang=${state.lang}` };
  const names = { complaints: "content_seller_complaint_report.pdf", positioning: "content_seller_positioning_report.pdf" };
  if (!file) { toast("Upload a file on this page first, then download the report.", 5000); return; }
  const btn = btnId ? $(btnId) : (page === "complaints" ? $("compPdfBtn") : $("posPdfBtn"));
  if (btn) { btn.disabled = true; btn.textContent = "Building report…"; }
  try {
    const fd = new FormData();
    fd.append("files", file);
    const res = await fetch(endpoints[page], { method: "POST", headers: { "X-Session-Id": state.sessionId }, body: fd });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : "Could not build the report");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = names[page];
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast("📄 Report downloaded!");
  } catch (e) { toast(e.message, 6000); }
  if (btn) { btn.disabled = false; btn.textContent = "📄 Download PDF report"; }
}

// ---------- pricing & payments (à-la-carte, Razorpay) ----------
// ---------- theme toggle ----------
on("themeLight", () => setTheme("light"));
on("themeDark", () => setTheme("dark"));
// The inline <head> script already applied the theme before first paint;
// this just syncs the buttons' pressed state to whatever it picked.
(function syncThemeButtons() {
  const mode = currentTheme();
  const l = $("themeLight"), d = $("themeDark");
  if (l) l.setAttribute("aria-pressed", String(mode === "light"));
  if (d) d.setAttribute("aria-pressed", String(mode === "dark"));
})();

on("upgradeBtn", () => openPricing());
on("chartModalClose", closeChartModal);
on("chartResetBtn", resetModalView);
on("chartZoomBtn", () => setModalMode("zoom"));
on("chartPanBtn", () => setModalMode("pan"));
on("chartDownloadBtn", downloadModalChart);
(function () {
  const cm = $("chartModal");
  if (cm) cm.addEventListener("click", (e) => { if (e.target === cm) closeChartModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && _currentModalChart) closeChartModal(); });
})();

const PRODUCT_ICONS = { winback_campaign: "💌", positioning_report: "📍", ai_topup: "⚡", chain_monthly: "🏢" };

async function loadPricing() {
  if (state.pricing) return state.pricing;
  state.pricing = await api("/api/pricing");
  state.launchMode = state.pricing.launch_mode;
  return state.pricing;
}

async function openPricing(highlightProduct, message) {
  let p;
  try { p = await loadPricing(); } catch (e) { toast(e.message); return; }
  const m = $("pricingModal");
  $("pricingIntro").textContent = message ||
    (p.launch_mode
      ? "Everything is free during launch — this is what pricing will look like later."
      : "Analytics, category trends and your at-risk list are free forever. Pay only for the actions below, when you need them.");
  const list = $("pricingList");
  list.innerHTML = "";
  p.products.forEach((prod) => {
    const div = document.createElement("div");
    div.className = "price-item" + (prod.id === highlightProduct ? " highlight" : "");
    const per = prod.kind === "subscription" ? "/month" : "";
    const owned = prod.id === "chain_monthly" && state.plan === "chain";
    div.innerHTML = `
      <div class="price-item-head">
        <span>${PRODUCT_ICONS[prod.id] || "•"} <b>${prod.name}</b></span>
        <span class="price-tag">₹${prod.price_inr}${per}</span>
      </div>
      <p class="subtle" style="margin:6px 0 10px; font-size:13px;">${prod.description}</p>`;
    const btn = document.createElement("button");
    if (p.launch_mode) {
      btn.className = "ghost-btn"; btn.disabled = true;
      btn.textContent = "✓ Free during launch";
    } else if (owned) {
      btn.className = "ghost-btn"; btn.disabled = true;
      btn.textContent = "✓ Active";
    } else {
      btn.className = "primary-btn";
      btn.textContent = prod.kind === "subscription" ? `Subscribe — ₹${prod.price_inr}/mo` : `Buy — ₹${prod.price_inr}`;
      btn.onclick = () => buyProduct(prod.id);
    }
    div.appendChild(btn);
    // Pricing validation: one-tap "would you pay this?" — logged server-side.
    const fb = document.createElement("div");
    fb.className = "subtle price-feedback";
    fb.innerHTML = `Would you pay this? <a href="#" data-vote="yes">👍</a> <a href="#" data-vote="no">👎</a>`;
    fb.querySelectorAll("a").forEach((a) => a.onclick = async (e) => {
      e.preventDefault();
      try {
        await api("/api/feedback", { method: "POST", json: { product: prod.id, vote: a.dataset.vote } });
        fb.textContent = "Thanks — this genuinely helps us price fairly 🙏";
      } catch { fb.textContent = "Thanks!"; }
    });
    div.appendChild(fb);
    list.appendChild(div);
  });
  m.hidden = false; m.style.display = "grid";
}
function closePricing() { const m = $("pricingModal"); m.hidden = true; m.style.display = "none"; }
on("pricingClose", closePricing);

function loadRazorpayScript() {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = resolve;
    s.onerror = () => reject(new Error("Could not load the payment window — check your connection."));
    document.head.appendChild(s);
  });
}

async function buyProduct(productId) {
  if (!state.token) { closePricing(); state.pendingPage = null; openLogin(); toast("Log in first, then reopen pricing"); return; }
  try {
    const order = await api("/api/pay/create-order", { method: "POST", json: { product: productId } });
    if (order.launch_free) { toast("It's free during launch — just use it! 🎉"); closePricing(); return; }
    await loadRazorpayScript();
    const rzp = new Razorpay({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount,
      currency: order.currency,
      name: order.name,
      description: order.description,
      prefill: { email: state.email || "" },
      handler: async (resp) => {
        try {
          const v = await api("/api/pay/verify", { method: "POST", json: {
            razorpay_order_id: resp.razorpay_order_id,
            razorpay_payment_id: resp.razorpay_payment_id,
            razorpay_signature: resp.razorpay_signature,
            product: productId,
          }});
          refreshUserUI(v.usage);
          closePricing();
          toast("🎉 Payment successful — " + (productId === "chain_monthly" ? "Chain plan active!" : "unlocked and ready to use!"), 5000);
        } catch (e) { toast(e.message, 6000); }
      },
    });
    rzp.open();
  } catch (e) { toast(e.message, 6000); }
}

// ---------- language ----------
const langSelect = $("langSelect");
if (langSelect) {
  langSelect.value = state.lang;
  langSelect.onchange = () => {
    state.lang = langSelect.value;
    localStorage.setItem("cx_lang", state.lang);
    // re-render whatever page is open so insights switch language immediately
    const active = document.querySelector(".page.active");
    if (!active) return;
    const id = active.id.replace("page-", "");
    if (id === "analytics") loadAnalytics();
    else if (id === "subcategory") loadSubcategory();
    else if (id === "rfm") loadRFM();
    else if (id === "positioning" && window._lastPosFile) uploadPositioning([window._lastPosFile]);
  };
}

// ---------- product type selectors (positioning / complaints pages) ----------
function syncProductTypeSelects() {
  document.querySelectorAll(".pt-select").forEach((sel) => { if (state.productType) sel.value = state.productType; });
}
document.querySelectorAll(".pt-select").forEach((sel) => sel.onchange = async () => {
  const v = sel.value || null;
  state.productType = v;
  document.querySelectorAll(".pt-select").forEach((s) => { if (s !== sel) s.value = sel.value; });
  if (v && state.token) { try { await api("/api/product-type", { method: "POST", json: { product_type: v } }); } catch (e) {} }
});

// ---------- boot ----------
(async function init() {
  if (state.token) {
    try {
      const me = await api("/api/me");
      state.email = me.email;
      state.productType = me.product_type || null;
      refreshUserUI(me.usage, me.plan);
      syncProductTypeSelects();
    } catch { state.token = null; localStorage.removeItem("cx_token"); refreshUserUI(null); }
  } else refreshUserUI(null);
  syncLockedPreviews();
  if (new URLSearchParams(location.search).get("upgrade") === "1" ||
      new URLSearchParams(location.search).get("pricing") === "1") {
    history.replaceState({}, "", "/app");
    setTimeout(() => openPricing(), 400);
  }
  loadPricing().then(() => refreshUserUI()).catch(() => {});
  try {
    const f = await api("/api/files");
    state.files = f.files;
    state.mapped = f.mapped;
    renderFileList();
  } catch {}
})();
