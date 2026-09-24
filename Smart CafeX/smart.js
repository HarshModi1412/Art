/* One Tap Manager — Smart workspace on top of the shared backend.
   Pivoted from café analytics to a small social-media product seller. */

const state = {
  // Login + session live in localStorage under the cx_* keys.
  sessionId: localStorage.getItem("cx_session") || (crypto.randomUUID ? crypto.randomUUID() : String(Math.random())),
  token: localStorage.getItem("cx_token") || null,
  email: localStorage.getItem("cx_email") || null,
  data: { sales: {}, review: {} },
  productType: null,
  productLabel: "",          // the seller's own words for what they sell
  productTypes: [],
  lastState: null,
};
localStorage.setItem("cx_session", state.sessionId);

/* Mint a brand-new browser session id and forget the old one.
   ------------------------------------------------------------------
   The server binds a session id to the first account that uses it while
   signed in, and never lets a second account reuse it — that is what keeps a
   leaked session id from reading someone else's data. The flip side is that a
   session id which outlives a logout is poison: the next person to sign in on
   this browser (or the same person switching accounts) inherits a session the
   server already owns for the previous email, and every data call comes back
   "This browser session belongs to another account."
   So whenever the identity at this browser changes — a logout, an account
   deletion, or the server telling us the id is bound to someone else — we drop
   the id and start clean. */
function resetSessionId() {
  state.sessionId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
  try { localStorage.setItem("cx_session", state.sessionId); } catch (e) {}
  return state.sessionId;
}

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => n == null ? "–" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
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

// ---------- theme (persisted in localStorage["cx_theme"]) ----------
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

/* The icon set is the same for everyone and only changes when the app is
   redeployed, so it is stored against the asset version in the page URL. That
   removes one blocking round trip from every single cold start — and a cold
   start is what a seller gets every time the browser reclaims the tab. */
const ICON_KEY = "cx_icons";

function assetVersion() {
  const s = document.querySelector('script[src*="smart.js"]');
  const m = s && /[?&]v=([\w.-]+)/.exec(s.getAttribute("src") || "");
  return m ? m[1] : "0";
}

async function loadIcons() {
  const v = assetVersion();
  try {
    const raw = localStorage.getItem(ICON_KEY);
    if (raw) {
      const c = JSON.parse(raw);
      if (c.v === v && c.icons && Object.keys(c.icons).length) {
        Object.assign(ICONS, c.icons);
        return;                         // painted from cache, no request at all
      }
    }
  } catch (e) { /* fall through to the network */ }
  try {
    const d = await fetch("/api/icons").then((r) => r.json());
    Object.assign(ICONS, d.icons || {});
    try {
      localStorage.setItem(ICON_KEY, JSON.stringify({ v, icons: d.icons || {} }));
    } catch (e) { /* quota — harmless, we just fetch again next time */ }
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

/* A toast that offers a next step instead of interrupting with one.
   Approving a reel used to throw the step-by-step popup open over whatever
   the seller was doing — fine if they approved one, an ambush if they were
   working down a list of six. The offer sits there for seven seconds and
   costs nothing to ignore. */
function toastAction(message, actionLabel, fn, ms = 7000) {
  const t = $("toast");
  clearTimeout(t._t);
  if (_undo) { clearTimeout(_undo.timer); _undo = null; }
  t.hidden = false;
  t.innerHTML = "";
  const span = document.createElement("span");
  span.textContent = message;
  const btn = document.createElement("button");
  btn.className = "toast-undo";
  btn.type = "button";
  btn.textContent = actionLabel;
  t.appendChild(span);
  t.appendChild(btn);
  const close = () => { t.hidden = true; t.textContent = ""; };
  btn.onclick = () => { close(); try { fn(); } catch (e) {} };
  t._t = setTimeout(close, ms);
}

/* Every one of these had to be written out, because `res.statusText` - which
   this function used to fall back on - is ALWAYS an empty string over HTTP/2,
   and HTTP/2 is what Render serves. Any error whose body was not JSON with a
   `detail` therefore reached the UI as `new Error("")`, and every catch block
   in this file renders that message into a card. That is where the empty
   bordered boxes came from: not a missing section, an error with nothing to
   say. */
const HTTP_MSG = {
  400: "That request was not something the server could use.",
  401: "Your session has expired - please log in again.",
  403: "You do not have access to that.",
  404: "That is not available.",
  409: "Something changed while you were working - reload and try again.",
  413: "That file is too large.",
  429: "Too many requests just now - wait a few seconds.",
  500: "Something went wrong on our side. Try that again in a moment.",
  502: "The server did not answer, it may be starting up. Try again in a few seconds.",
  503: "The server did not answer, it may be starting up. Try again in a few seconds.",
  504: "The server took too long to answer. Try again in a moment.",
};

/* Retried only for reads. A GET can be repeated safely; a POST cannot, and
   silently repeating one is how a seller ends up with two purchase orders.
   502/503/504 are what a host returns while a sleeping instance wakes, and
   they used to surface as a permanently broken-looking panel that a manual
   reload would have fixed. */
const RETRY_STATUS = new Set([429, 502, 503, 504]);
const RETRY_MAX = 2;
const nap = (ms) => new Promise((r) => setTimeout(r, ms));

/* =========================================================================
   UPLOADS, WITH A BAR THAT MEANS SOMETHING
   =========================================================================
   `fetch()` cannot tell you how much of a request body has gone out. That is
   not a small gap here: a seller uploading a 40MB reel over Indian mobile data
   waits the better part of a minute, and all they had was a spinner, which is
   the same thing the app shows for a 200ms save. An indeterminate spinner over
   a long upload is a lie of omission — it says "wait" without saying "for how
   long", so the only rational reading is "this has hung".

   XMLHttpRequest still reports upload progress, so uploads use it. The bar is
   real: it is bytes actually sent, not a timer pretending.

   Past 100% the bytes are gone but the server is still working — burning the
   AI label into a clip takes real seconds — so the bar switches to an
   indeterminate state and says what is happening rather than sitting at 100%
   looking stuck.
   ========================================================================= */
function apiUpload(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path, true);
    xhr.setRequestHeader("X-Session-Id", state.sessionId);
    if (state.token) xhr.setRequestHeader("Authorization", "Bearer " + state.token);
    xhr.upload.onprogress = (e) => {
      if (!onProgress) return;
      onProgress(e.lengthComputable ? e.loaded / e.total : null, e.loaded, e.total);
    };
    // Everything is on the wire; whatever happens now is the server's time.
    xhr.upload.onload = () => { if (onProgress) onProgress(1, 1, 1); };
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText || "{}"); } catch (e) {}
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data);
      const d = data.detail;
      const msg = (d && typeof d === "object" ? d.message : d)
        || HTTP_MSG[xhr.status] || `The server returned ${xhr.status}.`;
      const err = new Error(msg);
      err.status = xhr.status;
      reject(err);
    };
    xhr.onerror = () => {
      const e = new Error("Could not reach the server. Check your connection and try again.");
      e.status = 0;
      reject(e);
    };
    xhr.onabort = () => reject(Object.assign(new Error("Upload cancelled."), { aborted: true }));
    xhr.send(formData);
    if (onProgress) onProgress(0, 0, 0);
    return xhr;
  });
}

/* The bar itself. Lives where the file is going — in the clip slot, in the
   picture frame — never in a modal over the top of it, because the thing the
   seller wants to look at while it uploads is the place it is going. */
function progressBar(host, label) {
  if (!host) return { set() {}, done() {}, fail() {} };
  const box = document.createElement("div");
  box.className = "up-prog";
  box.innerHTML = `<div class="up-prog-h"><span class="up-prog-l">${esc(label || "Uploading")}</span>
      <span class="up-prog-p">0%</span></div>
    <div class="up-prog-track"><div class="up-prog-fill" style="width:0%"></div></div>`;
  host.appendChild(box);
  const fill = box.querySelector(".up-prog-fill");
  const pct = box.querySelector(".up-prog-p");
  const lbl = box.querySelector(".up-prog-l");
  return {
    set(frac) {
      if (frac == null) { box.classList.add("indet"); pct.textContent = ""; return; }
      box.classList.remove("indet");
      const p = Math.max(0, Math.min(100, Math.round(frac * 100)));
      fill.style.width = p + "%";
      pct.textContent = p + "%";
      if (p >= 100) { box.classList.add("indet"); pct.textContent = ""; }
    },
    /* 100% is not "finished" — it is "your phone is done, ours is not". */
    working(text) { box.classList.add("indet"); pct.textContent = ""; lbl.textContent = text; },
    done(text) {
      box.classList.remove("indet");
      box.classList.add("ok");
      fill.style.width = "100%";
      lbl.textContent = text || "Done";
      pct.textContent = "";
      setTimeout(() => { if (box.isConnected) box.remove(); }, 1100);
    },
    fail(text) {
      box.classList.remove("indet");
      box.classList.add("bad");
      lbl.textContent = text || "That did not upload";
      pct.textContent = "";
      setTimeout(() => { if (box.isConnected) box.remove(); }, 4200);
    },
    remove() { if (box.isConnected) box.remove(); },
  };
}

async function api(path, opts = {}, attempt = 0) {
  const headers = { "X-Session-Id": state.sessionId, ...(opts.headers || {}) };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  if (opts.json) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  const retryable = !opts.method || opts.method.toUpperCase() === "GET";

  let res;
  try {
    res = await fetch(path, { ...opts, headers });
  } catch (netErr) {
    // fetch() only rejects on a genuine transport failure - DNS, a dropped
    // connection, a tunnel closing mid-request. On a phone moving between
    // wifi and mobile data that is common and almost always transient.
    if (retryable && attempt < RETRY_MAX) { await nap(400 * (attempt + 1)); return api(path, opts, attempt + 1); }
    const e = new Error("Could not reach the server. Check your connection and try again.");
    e.status = 0;
    throw e;
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // A session id that is still bound to a previous account (e.g. one created
    // before logout learned to rotate it, so already sitting in this browser)
    // fails EVERY data call with this 403. Mint a fresh id and replay the call
    // once. bind_session raises before the endpoint does any work, so replaying
    // is safe even for a POST — the first attempt changed nothing. Gated on
    // being signed in and tried only once, so a genuinely forbidden call still
    // surfaces its error.
    const boundElsewhere = res.status === 403
      && /belongs to another account/i.test(
        (data.detail && typeof data.detail === "object" ? data.detail.message : data.detail) || "");
    if (boundElsewhere && state.token && !opts._rebound) {
      resetSessionId();
      return api(path, { ...opts, _rebound: true }, attempt);
    }
    if (retryable && attempt < RETRY_MAX && RETRY_STATUS.has(res.status)) {
      await nap(600 * (attempt + 1));
      return api(path, opts, attempt + 1);
    }
    const d = data.detail;
    const fromServer = (d && typeof d === "object" ? d.message : d) || "";
    const err = new Error(
      fromServer || res.statusText || HTTP_MSG[res.status] || `The server returned ${res.status}.`
    );
    // Callers need to tell "you are logged out" (401) apart from "the server
    // hiccuped" (500, timeout, cold start). Without this every blip looked
    // like an expired session and threw the seller back to the login screen.
    err.status = res.status;
    err.detail = d;
    // The machine-readable reason, when the server sends one (e.g.
    // "monthly_image_cap" vs "daily_cap" on a 429), so a caller can react
    // without string-matching the human message.
    err.code = data.code || "";
    throw err;
  }
  // Any successful write can change what several modules would show — adding a
  // product moves Products, the Studio catalogue AND the Social planner. Rather
  // than track which write touches which screen and get it wrong once, the
  // cached copies are dropped here, at the single point every write passes
  // through. Reads are unaffected, so the instant-paint still works; the cost
  // is one refetch after a change, which is what used to happen every time.
  if (!retryable) { warmClear(); warmModClearAll(); }
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

/* =====================================================================
   AI writing help — on every field where a seller has to type.

   One content writer on the server (backend/core/writer.py) with one set of
   rules and the brand's own voice. It runs on Puter's AI gateway when the
   server has a PUTER_AUTH_TOKEN; with no AI on the server at all, the same
   brief is handed to puter.js in the browser (the seller's own Puter
   account, which asks them to sign in once).

   Any <textarea data-ai="kind"> or <input data-ai="kind"> anywhere in the app
   gets a small "Write" button — a MutationObserver wires new ones as
   screens render, so a new form only has to add the attribute.
   ===================================================================== */
let _puterLoading = null;
function loadPuter() {
  if (window.puter && window.puter.ai) return Promise.resolve(window.puter);
  if (_puterLoading) return _puterLoading;
  _puterLoading = new Promise((resolve, reject) => {
    const sc = document.createElement("script");
    sc.src = "https://js.puter.com/v2/";
    sc.onload = () => (window.puter && window.puter.ai ? resolve(window.puter) : reject(new Error("Puter did not load")));
    sc.onerror = () => { _puterLoading = null; reject(new Error("Could not reach Puter")); };
    document.head.appendChild(sc);
  });
  return _puterLoading;
}

/* The server's result, or — when the server had no AI and the browser may
   use Puter — the same brief sent through puter.js. Returns {text, via}. */
async function puterFallback(res) {
  const meta = res.meta || {};
  if (res.ai || res.provider !== "template" || !meta.browser_puter || !res.prompt) return null;
  try {
    const p = await loadPuter();
    const out = await Promise.race([
      p.ai.chat([{ role: "system", content: res.prompt.system },
                 { role: "user", content: res.prompt.user }]),
      new Promise((_, rej) => setTimeout(() => rej(new Error("Puter took too long")), 45000)),
    ]);
    const msg = out && out.message ? out.message.content : out;
    const text = Array.isArray(msg) ? msg.map((x) => x.text || "").join("") : String(msg || "");
    return text.trim() ? { text: text.trim(), via: "puter" } : null;
  } catch (e) { return null; }
}
function _stripAi(t) {
  let x = String(t || "").trim().replace(/^```[a-z]*\s*|\s*```$/gi, "").trim();
  x = x.replace(/^here(?: is|'s)[^:\n]*:\s*/i, "").trim();
  if (x.length > 1 && /["'“”]/.test(x[0]) && /["'“”]/.test(x[x.length - 1])) x = x.slice(1, -1).trim();
  return x;
}
function _aiJson(t) {
  const m = String(t || "").match(/\{[\s\S]*\}/);
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch (e) { return null; }
}

/* What the writer should know about the item this field belongs to. */
function aiContextFor(el) {
  const v = (id) => { const n = $(id); return n ? String(n.value || "").trim() : ""; };
  const ctx = {};
  const where = el.dataset.aiCtx || "";
  if (where === "product") {
    Object.assign(ctx, { name: v("pfName"), category: v("pfCat"), price: v("pfPrice"),
      mrp: v("pfMrp"), unit: v("pfUnit"),
      key_points: v("pfHl") ? v("pfHl").split("\n").filter(Boolean) : [],
      description: el.id === "pfDesc" ? "" : v("pfDesc") });
  } else if (where === "studio-product" && _studioProduct) {
    const pr = _studioProduct.product || {};
    Object.assign(ctx, { name: pr.name, category: pr.category, price: pr.price,
      story: v("stStory"), materials: v("stMat"), different: v("stDiff") });
  } else if (where === "brand") {
    Object.assign(ctx, { name: v("sbName"), about: v("sbAbout"), audience: v("sbAud") });
  } else if (where === "site" && typeof _site !== "undefined" && _site) {
    Object.assign(ctx, { brand: _site.brand, tagline: _site.tagline, brief: _site.brief,
      hero: (_site.hero || {}).heading });
  } else if (where === "post") {
    Object.assign(ctx, { product: (document.querySelector(".modal-head b") || {}).textContent || "" });
  } else if (where === "po") {
    Object.assign(ctx, { supplier: v("poSupName") });
  } else if (where === "reel" && typeof _smScript !== "undefined" && _smScript) {
    Object.assign(ctx, { shots: (_smScript.beats || []).map((b) =>
      [b.sec, b.shot, b.on_screen_text].filter(Boolean).join(" · ")).filter(Boolean) });
  }
  if (where === "brand") Object.assign(ctx, { look: v("sbLook"), voice: v("sbVoice"), colours: v("sbPal") });
  if (where === "post") Object.assign(ctx, { caption: v("ccCaption") });
  if (el._aiContext) Object.assign(ctx, el._aiContext());
  return ctx;
}

async function aiWriteField(el, instruction) {
  const label = el.dataset.aiLabel || ((el.closest("label") || {}).firstChild || {}).textContent || "";
  const r = await api("/api/ai/write", { method: "POST", json: {
    kind: el.dataset.ai || "general", label: String(label).trim().slice(0, 80),
    current: el.value || "", context: aiContextFor(el), instruction: instruction || "" } });
  const fb = await puterFallback(r);
  if (fb) return { text: _stripAi(fb.text), via: "Puter (your account)", ai: true };
  return { text: r.text || "", via: r.ai ? `AI · ${r.provider}` : "template, no AI connected", ai: !!r.ai };
}

function aiAssist(el) {
  const holder = el.closest("label") || el.parentElement;
  let pop = holder.querySelector(":scope > .ai-pop");
  if (pop) pop.remove();
  pop = document.createElement("div");
  pop.className = "ai-pop";
  pop.innerHTML = `<div class="ai-pop-h">${sic("spark")}<b>Writing…</b></div>`;
  el.insertAdjacentElement("afterend", pop);
  const run = async (instruction) => {
    pop.innerHTML = `<div class="ai-pop-h">${sic("spark")}<b>Writing…</b><span class="muted tiny">in your brand's voice, from what you have told us</span></div>`;
    try {
      const r = await aiWriteField(el, instruction);
      pop.innerHTML = `
        <div class="ai-pop-h">${sic("spark")}<b>Suggestion</b><span class="muted tiny">${esc(r.via)}</span></div>
        <textarea class="ai-pop-t" rows="${Math.min(10, Math.max(2, Math.ceil((r.text || "").length / 70)))}">${esc(r.text)}</textarea>
        <div class="ai-pop-a">
          <button type="button" class="btn primary tiny" data-aiuse>Use this</button>
          <button type="button" class="btn ghost tiny" data-aiagain>Try again</button>
          <button type="button" class="btn ghost tiny" data-aishort>Shorter</button>
          <button type="button" class="btn ghost tiny" data-ailong>More detail</button>
          <button type="button" class="btn ghost tiny" data-aiclose>Close</button>
        </div>`;
      pop.querySelector("[data-aiuse]").onclick = () => {
        el.value = pop.querySelector(".ai-pop-t").value;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        pop.remove();
        paintAiBtn(el);
      };
      pop.querySelector("[data-aiagain]").onclick = () => run("Write a different version.");
      pop.querySelector("[data-aishort]").onclick = () => run("Make it noticeably shorter.");
      pop.querySelector("[data-ailong]").onclick = () => run("Add one more concrete detail from the facts given, do not invent any.");
      pop.querySelector("[data-aiclose]").onclick = () => pop.remove();
    } catch (e) {
      pop.innerHTML = `<div class="ai-pop-h">${sic("alert")}<b>${esc(e.message)}</b></div>
        <div class="ai-pop-a"><button type="button" class="btn ghost tiny" data-aiclose>Close</button></div>`;
      pop.querySelector("[data-aiclose]").onclick = () => pop.remove();
    }
  };
  run("");
}

function paintAiBtn(el) {
  const b = el._aiBtn;
  if (b) b.innerHTML = `${sic("spark")}${(el.value || "").trim() ? "Improve" : "Write"} with AI`;
}
function wireAi(scope) {
  (scope || document).querySelectorAll("textarea[data-ai], input[data-ai]").forEach((el) => {
    if (el._aiWired) return;
    el._aiWired = true;
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ai-btn";
    b.title = "Let the AI content writer draft or polish this";
    el._aiBtn = b;
    paintAiBtn(el);
    el.addEventListener("input", () => paintAiBtn(el));
    b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); aiAssist(el); };
    el.insertAdjacentElement("afterend", b);
  });
}
new MutationObserver((muts) => {
  for (const m of muts) for (const n of m.addedNodes) {
    if (n.nodeType !== 1) continue;
    if (n.matches && n.matches("textarea[data-ai], input[data-ai]")) wireAi(n.parentElement);
    else if (n.querySelector && n.querySelector("[data-ai]")) wireAi(n);
  }
}).observe(document.documentElement, { childList: true, subtree: true });

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
/* ------------------------------------------------- continue with Google ----
   Most Indian D2C sellers are on Gmail already. Asking them to invent and
   remember a password before they have seen anything is the highest-friction
   moment in the whole product, and it is the one that happens first.

   Google Identity Services is loaded only if the server actually has a client
   id — a dead button is worse than no button — and only on the login screen,
   so the script is never fetched for a seller who is already signed in.

   `use_fedcm_for_button` is on: Safari, Firefox and Brave already block the
   third-party cookies the old flow depends on, and roughly a fifth of traffic
   would otherwise get a button that silently does nothing. */
let _gsiNonce = "";

async function setupGoogleSignIn() {
  let cfg;
  try { cfg = await api("/api/auth/providers"); } catch (e) { return; }
  const g = cfg && cfg.google;
  if (!g || !g.enabled || !g.client_id) return;

  await new Promise((resolve, reject) => {
    if (window.google && google.accounts) return resolve();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true; s.defer = true;
    s.onload = resolve; s.onerror = reject;
    document.head.appendChild(s);
  }).catch(() => null);
  if (!(window.google && google.accounts && google.accounts.id)) return;

  // Replay protection: the server is told what nonce to expect, and a token
  // captured from one browser cannot be posted from another.
  _gsiNonce = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()));
  google.accounts.id.initialize({
    client_id: g.client_id,
    callback: onGoogleCredential,
    nonce: _gsiNonce,
    use_fedcm_for_button: true,
    auto_select: false,
    itp_support: true,
  });
  const box = $("gsiBox"), btn = $("gsiBtn");
  if (!box || !btn) return;
  google.accounts.id.renderButton(btn, {
    type: "standard", theme: document.documentElement.dataset.theme === "dark" ? "filled_black" : "outline",
    size: "large", text: "continue_with", shape: "rectangular", width: 320,
  });
  box.hidden = false;
}

async function onGoogleCredential(resp) {
  const err = $("loginErr"), note = $("loginNote");
  err.hidden = true; if (note) note.hidden = true;
  await googleFinish({ credential: resp.credential, nonce: _gsiNonce });
}

/* Split out because the link case comes back through here a second time, with
   the password the seller typed. */
async function googleFinish(payload) {
  const err = $("loginErr");
  try {
    const d = await api("/api/auth/google", { method: "POST", json: payload });
    state.token = d.token; state.email = d.email;
    localStorage.setItem("cx_token", d.token); localStorage.setItem("cx_email", d.email);
    showShell();
  } catch (e) {
    // 409: an account with this address already exists and was made with a
    // password. We ask for it once rather than silently joining the two, which
    // is how one person's account ends up attached to another's Google login.
    if (/already uses this email/i.test(e.message || "")) {
      const pw = await askPassword();
      if (pw) return googleFinish({ ...payload, password: pw });
      return;
    }
    err.textContent = e.message; err.hidden = false;
  }
}

function askPassword() {
  return new Promise((resolve) => {
    openModal("Connect Google to your existing account", `
      <p class="muted">You already have an account with this email. Type its
        password once and the two are joined, after that, one tap signs you in.</p>
      <label>Your current password
        <input type="password" id="gLinkPw" autocomplete="current-password" /></label>
      <div class="row" style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px;">
        <button class="btn ghost" id="gLinkNo">Cancel</button>
        <button class="btn primary" id="gLinkGo">Connect</button>
      </div>`);
    const done = (v) => { closeModal(); resolve(v); };
    $("gLinkNo").onclick = () => done(null);
    $("gLinkGo").onclick = () => done(($("gLinkPw").value || "").trim() || null);
    $("gLinkPw").addEventListener("keydown", (e) => {
      if (e.key === "Enter") done(($("gLinkPw").value || "").trim() || null);
    });
    $("gLinkPw").focus();
  });
}

// A seller locked out of their account is locked out of their whole catalogue,
// so this has to either work or say honestly that it cannot. It used to do
// neither: there was no link here at all, and the endpoint behind it promised
// an email that a server without SMTP silently threw away.
$("forgotLink").onclick = async (e) => {
  e.preventDefault();
  const err = $("loginErr"), note = $("loginNote");
  err.hidden = true; note.hidden = true;
  const addr = ($("email").value || "").trim();
  if (!addr) { err.textContent = "Type your email above first."; err.hidden = false; $("email").focus(); return; }
  try {
    const r = await api("/api/forgot", { method: "POST", json: { email: addr } });
    note.textContent = r.message || "Check your email.";
    note.className = r.email_ready === false ? "err" : "ok-note";
    note.hidden = false;
  } catch (e2) { err.textContent = e2.message; err.hidden = false; }
};

if ($("accountBtn")) $("accountBtn").onclick = () => openAccount();

$("logoutBtn").onclick = async () => {
  try { await api("/api/logout", { method: "POST" }); } catch {}
  state.token = null; state.email = null;
  localStorage.removeItem("cx_token"); localStorage.removeItem("cx_email");
  // Abandon the server-side session too. Keeping the old id here is what made a
  // different account fail to sign in afterwards with "belongs to another
  // account" — the id was still bound to the seller who just left.
  resetSessionId();
  // The cached screens hold this seller's figures. Signing out has to take
  // them with it, or the next person at this browser sees them.
  warmClear(); warmModClearAll();
  $("appShell").hidden = true; $("loginView").hidden = false;
  // Google remembers the last account and would sign them straight back in on
  // the next tap, which is not what "log out" means to anyone.
  try { if (window.google && google.accounts) google.accounts.id.disableAutoSelect(); } catch (e) {}
  setupGoogleSignIn();
};

function showShell() {
  $("loginView").hidden = true; $("appShell").hidden = false;
  $("tbUser").textContent = state.email || "";
  const deep = deepLinkModule();
  if (deep) openModule(deep);
  else goHome();
}
$("homeBtn").onclick = goHome;

/* Not a general router -- just enough to reach a module that isn't on the
   Home grid by URL, e.g. #/module/ads for Ad Analytics while ad-account
   connections aren't built out yet. Anyone can still type the hash; the
   module itself is what decides whether there's anything to show. */
function deepLinkModule() {
  const m = /^#\/module\/([a-z]+)$/.exec(location.hash);
  return m ? m[1] : null;
}
/* Back and forward. `openModule`/`goHome` call routeTo, which writes the hash,
   which would fire this again and re-fetch — so a navigation that merely
   reflects where we already are is ignored. */
function _syncRoute() {
  if (!state.token || $("appShell").hidden) return;
  const deep = deepLinkModule();
  if (deep === _currentModule) return;
  if (deep) openModule(deep);
  else if (_currentModule) goHome();
}
window.addEventListener("popstate", _syncRoute);
window.addEventListener("hashchange", _syncRoute);

// ---------- view helpers ----------
function setView(html) {
  const v = $("view");
  v.innerHTML = html;
  // Screen change: restart the short rise-in so navigation reads as movement
  // rather than a swap. Skipped when the seller asked for less motion.
  v.classList.remove("enter"); void v.offsetWidth; v.classList.add("enter");
}
function setCrumb(t) { $("crumb").textContent = t || ""; }

/* ---------- tables that survive a phone ----------

   The Inventory table has eleven columns. On a 390px phone that is 774px of
   table inside a 390px box, so the seller sees "Item, Supplier, Left" and has
   to drag sideways for the rest — and dragging sideways takes the item name
   off screen, so by the time they can read the reorder point they no longer
   know which item it belongs to. The numbers are there and unusable.

   Below tablet width the same markup is laid out as one card per row, each
   line reading "Lead time    15". Nothing is hidden, nothing is cut off, and
   the item name stays at the top of its own card.

   The label has to come from somewhere: CSS cannot read the <th> above a
   cell. So each cell is stamped with the text of its column heading, once,
   here — rather than by hand at fifteen different render sites, where the
   next person to add a table would forget. A MutationObserver catches every
   table the app draws, including the ones that arrive later from a fetch. */
function labelTableCells(table) {
  /* A column heading has two jobs and they pull in opposite directions. In the
     desktop table it has to fit a narrow column, so it gets abbreviated: DOS,
     MOQ, DOQ. On a phone the same heading becomes a full-width label with a
     value beside it, and there "DOS" is a word from our side of the screen
     that a seller has no reason to know — the tooltip that explains it needs a
     mouse, and a phone has no mouse. `data-card-label` lets a column keep its
     short name in the table and say what it means in the card. */
  const cols = [...table.querySelectorAll("thead th")].map((th) => {
    const t = (th.dataset.cardLabel || th.textContent || "").trim();
    return {
      label: t.length > 26 ? t.slice(0, 25) + "…" : t,
      hide: th.hasAttribute("data-card-hide"),
      first: th.hasAttribute("data-card-first"),
    };
  });
  const heads = cols.map((c) => c.label);
  if (!heads.length) return;
  table.querySelectorAll("tbody > tr").forEach((tr) => {
    [...tr.children].forEach((td, i) => {
      if (td.tagName !== "TD") return;
      // A spanning cell is an empty state or a sub-header, not a field.
      if (td.colSpan > 1) { td.setAttribute("data-full", "1"); return; }
      const col = cols[i] || { label: "", hide: false, first: false };
      /* Secondary on a phone, ordinary in the table. Eleven fields stacked
         vertically is a screen and a half per item; the five that answer
         "have I got enough, and who do I ring" stay, and the arithmetic
         behind them is one tap away for whoever wants it. */
      if (col.hide) td.setAttribute("data-secondary", "1");
      else td.removeAttribute("data-secondary");
      if (col.first) td.setAttribute("data-first", "1");
      else td.removeAttribute("data-first");
      const label = heads[i] || "";
      const text = (td.textContent || "").trim();
      // A cell holding only a button (the row's action) reads better as a
      // full-width row of its own than as "  [Order]" against a blank label.
      const onlyControl = !text && td.querySelector("button, a, input, select");
      if (!label || onlyControl) { td.setAttribute("data-full", "1"); td.removeAttribute("data-label"); return; }
      td.removeAttribute("data-full");
      td.setAttribute("data-label", label);
      if (i === 0) td.setAttribute("data-primary", "1");
      if (!text && !td.querySelector("*")) td.setAttribute("data-blank", "1");
      else td.removeAttribute("data-blank");
      /* The value goes in a box of its own. Without it a cell like
         "Harsh <div>harsh@…</div>" becomes two separate flex items sitting
         beside the label, which squeezed the label until it wrapped inside
         the word: "Supplie / r". One wrapper, and the label keeps its width
         while the value stacks and wraps on its own side. Inline by default,
         so nothing about the desktop table changes. */
      if (!td.firstElementChild || !td.firstElementChild.classList.contains("td-v")
          || td.childNodes.length > 1) {
        const box = document.createElement("span");
        box.className = "td-v";
        while (td.firstChild) box.appendChild(td.firstChild);
        td.appendChild(box);
      }
    });
  });
}
function labelTablesIn(root) {
  if (!root || !root.querySelectorAll) return;
  root.querySelectorAll(".table-scroll table").forEach(labelTableCells);
  if (root.matches && root.matches(".table-scroll table")) labelTableCells(root);
}
function watchTables() {
  labelTablesIn(document.body);
  const obs = new MutationObserver((batch) => {
    for (const m of batch) {
      for (const node of m.addedNodes) {
        if (node.nodeType === 1) labelTablesIn(node);
      }
    }
  });
  obs.observe(document.body, { childList: true, subtree: true });
}
function showRail(on) { document.querySelector(".shell-body").classList.toggle("no-rail", !on); }

// ---------- charts: image-like inline, interactive when maximized ----------
// Inline charts render STATIC (like an image). A ⤢ button on each opens it
// full-screen where you can zoom / pan / reset / download — the same
// "expand to analyse" pattern.
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
    // Series colours come from the theme, not from hard-coded hexes. The old
    // list was a light-mode palette used in both themes: on the dark ground
    // those saturated blues and greens dropped to 2-3:1, and the mid-green sat
    // close enough to the pink that a red-green colour-blind seller could not
    // tell two lines apart. Both themes now define eight tokens whose lightness
    // is staggered, so hue is never the only thing carrying the difference.
    colorway: SERIES(),
  };
}

/* The theme's categorical series, in order. Read live so the toggle repaints. */
/* A translucent wash under a line, taken from the accent so it works in both
   themes. The old value was a hard-coded purple from a palette this app has not
   used for months. */
function softFill() { return cssVar("--primary-soft", "rgba(92,103,144,.10)"); }

function SERIES() {
  const fb = ["#3f6bb5", "#b5711f", "#2f7d54", "#b0577a", "#6b5aa6", "#2b7f8c", "#8a7a2c", "#a8663f"];
  return fb.map((f, i) => cssVar(`--chart-${i + 1}`, f));
}
function series(i) { return SERIES()[i % 8]; }

/* ------------------------------------------------ the chart library, late ---
   Plotly is about 3.5 MB. It used to load in the <head> of every page, with no
   `defer`, so nothing painted until it arrived — on the login screen, on Home,
   on Suppliers, on all eleven screens that have no chart at all.

   Now it is fetched the first time a chart is actually drawn, and warmed in
   the background a moment after the app is usable, so the seller who does open
   Sales Analytics almost never waits for it either. One promise, so ten charts
   on one screen share a single download. */
let _plotlyPromise = null;

function ensurePlotly() {
  if (window.Plotly) return Promise.resolve(true);
  if (_plotlyPromise) return _plotlyPromise;
  _plotlyPromise = new Promise((resolve) => {
    const s = document.createElement("script");
    s.src = "https://cdn.plot.ly/plotly-2.35.2.min.js";
    s.async = true;
    s.onload = () => resolve(true);
    // One outage of the primary CDN must not lose every chart: try a second
    // host, and only if that fails too forget the promise so a later chart retries.
    s.onerror = () => {
      const alt = document.createElement("script");
      alt.src = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js";
      alt.async = true;
      alt.onload = () => resolve(true);
      alt.onerror = () => { _plotlyPromise = null; resolve(false); };
      document.head.appendChild(alt);
    };
    document.head.appendChild(s);
  });
  return _plotlyPromise;
}

/* Once the app is up and idle, pull it down so the first chart is instant.
   requestIdleCallback keeps it off the critical path entirely; the timeout
   fallback covers Safari, which still has not shipped it. */
function warmPlotly() {
  const go = () => ensurePlotly();
  if (window.requestIdleCallback) requestIdleCallback(go, { timeout: 4000 });
  else setTimeout(go, 2500);
}

function plot(el, traces, layout = {}, title = "") {
  if (!el) return;
  if (el.id) _charts[el.id] = { traces, layout, title };
  if (window.Plotly) return _drawPlot(el, traces, layout, title);
  // The card keeps its height so the page does not jump when the chart lands.
  el.innerHTML = `<div class="plot-wait">${skeletonBar()}</div>`;
  const id = el.id;
  ensurePlotly().then((ok) => {
    // The seller may have navigated away while it downloaded. Re-find by id
    // rather than drawing into a node that is no longer on the page.
    const live = id ? $(id) : el;
    if (!live) return;
    if (!ok) { live.innerHTML = `<div class="ap-empty">Charts could not load. Check your connection and press Refresh.</div>`; return; }
    _drawPlot(live, traces, layout, title);
  });
}

function skeletonBar() {
  return `<div class="sk-plot"><i></i><i></i><i></i><i></i><i></i><i></i></div>`;
}

function _drawPlot(el, traces, layout, title) {
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
async function openChartModal(id, title) {
  const c = _charts[id]; if (!c) return;
  if (!window.Plotly && !(await ensurePlotly())) return;
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
// Ad Analytics is deliberately NOT in this list -- connecting Google/Meta ad
// accounts isn't built out yet, so it stays off the grid rather than sitting
// there as a dead end. The route is still fully wired (openModule("ads")
// works) so it's reachable directly at #/module/ads while that work
// continues -- see the hash-route handler near DOMContentLoaded.
//
// Content Creator and Instagram (the "in build" placeholder) were removed
// outright, not just hidden: nothing routes to them from anywhere.
/* The order here is the order on screen, and it follows the day rather than the
   codebase: first what happened (numbers), then what to do about it today
   (orders, stock), then how to bring more people in (content, website), then
   the deeper reads that need review data.

   `group` puts a plain-language heading above each run of tiles. Twelve
   unlabelled squares is the thing that makes a first-time seller close the tab:
   they cannot tell which one is for them right now. Four short headings turn the
   same twelve into "oh, that section is where I look in the morning".

   `offGrid` keeps a module off the home screen without unwiring it. Marketing
   and Billing & GST are off-grid for now — both work, both are reachable
   directly by URL (#/module/marketing and #/module/gst) — because a seller who
   has not sent a single order does not need a GST filing tool competing for
   attention with "look at your sales". */
const MODULE_GROUPS = [
  { id: "know",  title: "Know what is happening",
    hint: "Straight from your order data. Start here." },
  { id: "run",   title: "Run the day",
    hint: "Orders to pack, stock to reorder, products to keep tidy." },
  { id: "grow",  title: "Bring in more customers",
    hint: "Your photos and words, turned into posts and your own shop." },
  { id: "deep",  title: "Go deeper",
    hint: "Needs your customer reviews. Optional." },
];

const MODULES = [
  // --- know what is happening ------------------------------------------------
  { id: "sales",      name: "Sales Analytics",        sub: "What sold, what it earned you, and what next month looks like.", ico: "chart", cls: "tile-sales", needs: "sales", tag: "SALES", group: "know" },
  { id: "subcategory",name: "Sub-Category Analysis",  sub: "Which kinds of products bring the money in, and which quietly do not.", ico: "layers", cls: "tile-sub", needs: "sales", tag: "SALES", group: "know" },
  // --- run the day -----------------------------------------------------------
  { id: "orders",     name: "Orders",                 sub: "Every order from your website, pack it, ship it, mark it done.", ico: "bag", cls: "tile-orders", needs: null, tag: "ORDERS", group: "run" },
  { id: "products",   name: "Product Management",     sub: "Your product list, with the different names each one has on Amazon, Shopify and the rest.", ico: "tag", cls: "tile-supply", needs: null, tag: "CATALOG", group: "run" },
  { id: "inventory",  name: "Inventory Management",   sub: "How much you have left. It goes down on its own as orders come in.", ico: "package", cls: "tile-supply", needs: null, tag: "STOCK", group: "run" },
  { id: "supply",     name: "Suppliers & Orders to Send", sub: "Who you buy from, when to buy again, and a ready order form to send them.", ico: "truck", cls: "tile-supply", needs: null, tag: "SUPPLY", group: "run" },
  // --- bring in more customers ----------------------------------------------
  { id: "studio",     name: "Product Studio",         sub: "Upload your photos once. We learn your look and use it in everything we make.", ico: "spark", cls: "tile-content", needs: null, tag: "STUDIO", group: "grow" },
  { id: "social",     name: "Social Media Manager",   sub: "A week of Instagram posts planned, written and scheduled for you.", ico: "spark", cls: "tile-content", needs: null, tag: "SOCIAL", group: "grow" },
  { id: "site",       name: "Website Builder",        sub: "Your own selling website. Pick a look, publish, start taking orders.", ico: "globe", cls: "tile-site", needs: null, tag: "SITE", group: "grow" },
  // --- go deeper -------------------------------------------------------------
  { id: "review",     name: "Review Analytics",       sub: "What customers actually praise you for, in their words.", ico: "star", cls: "tile-review", needs: "review", tag: "BRAND", group: "deep" },
  { id: "complaints", name: "Complaint Analysis",     sub: "The complaints costing you the most, in the order worth fixing.", ico: "flame", cls: "tile-complaint", needs: "review", tag: "BRAND", group: "deep" },
  { id: "strategy",   name: "Position Strategy + AI", sub: "A step-by-step plan to stand for something, plus an AI you can ask anything.", ico: "compass", cls: "tile-strategy", needs: "review", tag: "STRATEGY", group: "deep" },
  // --- off the grid, still reachable by URL ---------------------------------
  { id: "marketing",  name: "Marketing",              sub: "Win-back messages for customers who have gone quiet, and what they brought back.", ico: "mail", cls: "tile-marketing", needs: null, tag: "MARKETING", group: "run", offGrid: true },
  { id: "gst",        name: "Billing & GST",          sub: "Tax invoices, HSN codes and a GSTR-1 file your accountant can file from.", ico: "receipt", cls: "tile-orders", needs: null, tag: "BILLING", group: "run", offGrid: true },
];


/* ------------------------------------------------------- the warm cache ----
   THE PROBLEM: switch to another app and come back, and the browser has
   often thrown the whole page away to reclaim memory — normal behaviour on a
   phone, and nothing the page can prevent. What it CAN control is what the
   seller sees on the way back: a skeleton and four sequential round trips
   before the first pixel, which is why returning to the app felt like a full
   reload every time.

   So the last home screen is kept in localStorage and painted immediately on
   return, before the network is touched at all. The server is then asked
   whether anything actually changed — /api/smart/state answers 304 with no
   body when it has not — and the screen is only repainted when the answer is
   different. Coming back to the app now shows the home screen at once and
   quietly corrects itself if something moved.

   Rules that keep this honest:
     * keyed to the signed-in account, so switching login never shows the
       previous seller's figures;
     * dropped after MAX_AGE, so nothing genuinely old is ever painted;
     * cleared on sign-out;
     * every read and write wrapped — Safari private mode throws on
       localStorage, and a cache that breaks the app is worse than no cache. */
const WARM_KEY = "cx_home_cache";
const WARM_VERSION = 2;                 // bump to invalidate every stored copy
const WARM_MAX_AGE = 6 * 60 * 60 * 1000;   // 6 hours

function warmRead() {
  try {
    const raw = localStorage.getItem(WARM_KEY);
    if (!raw) return null;
    const c = JSON.parse(raw);
    if (c.v !== WARM_VERSION) return null;
    if (c.email !== state.email) return null;          // different account
    if (Date.now() - c.at > WARM_MAX_AGE) return null;  // too old to trust
    return c;
  } catch (e) { return null; }
}

function warmWrite(s, pt) {
  try {
    localStorage.setItem(WARM_KEY, JSON.stringify({
      v: WARM_VERSION, email: state.email, at: Date.now(), state: s, pt,
    }));
  } catch (e) { /* quota or private mode — the app works without it */ }
}

function warmClear() {
  try { localStorage.removeItem(WARM_KEY); } catch (e) { /* nothing to do */ }
}

/* The same warm-cache idea, per module.
   ------------------------------------------------------------------
   Home was cached but every module still started from a skeleton and a fetch,
   so moving between Social, Products and Orders showed a loading screen every
   single time even though the data had usually not changed since the last
   look. Each module's last payload is kept under its own key and painted
   immediately on reopen, then revalidated in the background exactly like
   Home.

   Shares the account key, the age limit and the sign-out clearing with the
   home cache, so there is ONE rule about whose data may sit on disk and for
   how long — two different answers to that question is how a stale-data bug
   gets in. */
function modKey(mod) { return `${WARM_KEY}_m_${mod}`; }

function warmModRead(mod) {
  try {
    const raw = localStorage.getItem(modKey(mod));
    if (!raw) return null;
    const c = JSON.parse(raw);
    if (c.v !== WARM_VERSION || c.email !== state.email) return null;
    if (Date.now() - c.at > WARM_MAX_AGE) return null;
    return c.payload;
  } catch (e) { return null; }
}

function warmModWrite(mod, payload) {
  try {
    localStorage.setItem(modKey(mod), JSON.stringify({
      v: WARM_VERSION, email: state.email, at: Date.now(), payload,
    }));
  } catch (e) { /* quota or private mode — the module still works without it */ }
}

/* Every module's cached copy. Used on sign-out, and after any write big
   enough to make several modules' views stale at once. */
function warmModClearAll() {
  try {
    Object.keys(localStorage)
      .filter((k) => k.indexOf(`${WARM_KEY}_m_`) === 0)
      .forEach((k) => localStorage.removeItem(k));
  } catch (e) { /* nothing to do */ }
}

/* One shape for every module: paint what we had, fetch, repaint only if it
   actually changed. `render` must be safe to call twice with equal data —
   every caller below re-renders from scratch, so it is. */
/* The three modules that read customer reviews, before any reviews exist.
   This used to arrive as an HTTP 400 and render as "Could not load this", which
   told a seller the app was broken when all that was missing was one file. */
function needsReviewsHtml(d) {
  return `<div class="card">
    <h3 style="margin:0 0 6px;">This one reads your customer reviews</h3>
    <p class="muted" style="margin:0 0 8px;">${esc(d.message || "Upload your customer reviews once, and the review modules fill in from them.")}</p>
    <p class="muted tiny" style="margin:0 0 12px;">A CSV or Excel export of your Google, marketplace or Instagram reviews works. Each row needs the review text; a rating and a date help.</p>
    <button type="button" class="btn primary" data-needs-reviews>${sic("plus")}Upload reviews</button></div>`;
}
function bindNeedsReviews() {
  const b = document.querySelector("[data-needs-reviews]");
  if (b) b.onclick = () => startUpload("review");
}

async function openCached(mod, title, fetcher, render, emptyHtml) {
  // THE BUG THIS GUARDS AGAINST: the fetch below takes a second or two, and a
  // seller does not wait. Open Suppliers, tap Home before it lands, and the
  // reply arrives to a screen that has moved on — and paints Suppliers over
  // the home page. Every await here is followed by a check that this is still
  // the screen the seller is looking at.
  const openedAs = _currentModule;
  const stillHere = () => _currentModule === openedAs;

  const warm = warmModRead(mod);
  let painted = false;
  if (warm) {
    // await: some renders are async (Social fetches its calendar). Without it
    // the fresh fetch below would race the warm paint and they would land in
    // whichever order the network decided.
    try { await render(warm); painted = true; } catch (e) { painted = false; }
    if (!stillHere()) return;
  }
  if (!painted) moduleShell(title, skeleton("cards"));
  else restoreScroll(mod);
  try {
    const fresh = await fetcher();
    const empty = !!(fresh && fresh.needs === "review");
    if (!stillHere()) { if (!empty) warmModWrite(mod, fresh); return; }   // cache it, don't draw it
    // Nothing to read yet is an empty state, not an error, and it is never
    // cached, so the real screen appears the moment the data exists.
    if (empty) { moduleShell(title, needsReviewsHtml(fresh)); bindNeedsReviews(); return; }
    if (!painted || JSON.stringify(warm) !== JSON.stringify(fresh)) {
      // A repaint under someone's finger loses their place. The scroll position
      // is put back after the new screen exists, so a background refresh is
      // something the seller notices only if the numbers changed.
      const y = window.scrollY;
      await render(fresh);
      if (!stillHere()) return;
      if (painted && y) window.scrollTo(0, y);
    }
    warmModWrite(mod, fresh);
  } catch (e) {
    if (!stillHere()) return;
    // Keep a usable screen rather than swapping it for an error card.
    if (painted) toast("Showing your last saved view. Could not reach the "
                       + "server just now.", 5000);
    else if (emptyHtml) moduleShell(title, emptyHtml(e.message));
    else moduleShell(title, failed(e.message, () => openModule(_currentModule)));
  }
}

/* Where the seller was on each screen.
   ------------------------------------------------------------------
   Kept in memory only, on purpose: a scroll position from yesterday is
   meaningless, and restoring one is more disorienting than starting at the
   top. Within a session, though, going Products → a product → back and
   landing at the top of a 60-item list is the single most irritating thing
   this app did. */
const _scrollAt = {};
function rememberScroll(mod) { if (mod) _scrollAt[mod] = window.scrollY || 0; }
function restoreScroll(mod) {
  const y = _scrollAt[mod];
  if (!y) return;
  // After paint, or the document is not yet tall enough to scroll to it.
  requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, y)));
}

function paintHome(s, pt) {
  state.lastState = s;
  state.data = s.data;
  if (pt) {
    state.productType = pt.product_type;
    state.productLabel = pt.label || "";
    state.productTypes = pt.types;
  }
  renderHome(s);
  renderApprovals(s.insights);
}

async function goHome() {
  _afterUpload = null;
  rememberScroll(_currentModule);
  _currentModule = null;
  routeTo(null);
  setCrumb(""); showRail(true);

  // Paint the last known home screen first. The seller is looking at their
  // app within a frame instead of at a loading skeleton.
  const warm = warmRead();
  if (warm) paintHome(warm.state, warm.pt);
  else setView(skeleton("tiles"));

  try {
    const [s, pt] = await Promise.all([
      api("/api/smart/state"),
      api("/api/product-type").catch(() => null),
    ]);
    // Only repaint when something actually moved. Re-rendering identical HTML
    // is what made the return feel like a reload even once it was fast.
    // Same race as openCached: the seller may have opened a module while this
    // was in flight, and painting Home over it now would be the app undoing
    // their tap. The data is still worth keeping for next time.
    const left = _currentModule !== null;
    const changed = !warm || JSON.stringify(warm.state) !== JSON.stringify(s);
    if (!left && (changed || !warm)) paintHome(s, pt);
    warmWrite(s, pt);
  } catch (e) {
    // A warm screen already on-screen is far better than throwing it away for
    // an error card — the seller keeps working and the next action retries.
    if (warm) toast("Showing your last saved view. Could not reach the server "
                    + "just now.", 5000);
    else setView(failed(e.message, goHome));
  }
}

function productLabel(id) {
  // Their own words win over the preset's name wherever this is shown, because
  // this is the app telling them what it thinks they sell.
  if (state.productLabel && (id === undefined || id === state.productType)) {
    return state.productLabel;
  }
  const t = (state.productTypes || []).find((x) => x.id === id);
  // Text only: callers escape this, and the chip it sits in has its own icon.
  return t ? t.label : "Not set";
}

function dataCard(kind, label, icon, hint) {
  const d = state.data[kind] || {};
  const ready = d.ready;
  return `
    <div class="data-card">
      <h4><span class="data-card-ico">${icon}</span>${label}</h4>
      <div class="status">
        <span class="dot ${ready ? "ready" : "empty"}"></span>
        ${ready ? `${fmt(d.rows)} rows loaded${d.updated_at ? ` · saved ${esc(String(d.updated_at).slice(0, 10))}` : ""}` : `No ${label.toLowerCase()} yet, ${hint}`}
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
  /* `opts.owner` stamps the popup with the thing it is about — a post id, say.
     Slow work started in one popup finishes after the seller has opened
     another, and a handler that looks up ".modal-actions" finds whichever
     popup is open now, not the one it came from. The stamp lets a late
     arrival check that it is still writing into its own popup. */
  const _mid = "mtitle-" + Math.random().toString(36).slice(2, 9);
  wrap.innerHTML = `<div class="modal${opts.wide ? " wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="${_mid}"${
      opts.owner ? ` data-post="${esc(String(opts.owner))}"` : ""}>
      <div class="modal-head"><b id="${_mid}">${esc(title)}</b>
        <button class="btn ghost tiny" data-mclose title="Close" aria-label="Close this popup">${sic("close")}</button></div>
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
    // Sample data is sales only. Saying "every module is live" sent sellers
    // into three review modules that then had nothing to show.
    toast("Sample data loaded. Everything but the review modules is live now.", 6000);
  } catch (e) { toast(e.message); }
}

/* --------------------------------------------------------------- Today ----
   Twelve tiles is a filing cabinet, not an answer. This is the answer: the
   three things worth doing this morning, each one a click away from the place
   it gets done. The same rows the morning digest sends, so the two can never
   disagree. */
let _digest = null;
/* What the shop needs, as of the last read. Kept because ticking a task off
   now has to re-count the whole card, not just the task half of it. */
let _todayItems = [];

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
  _todayItems = items;
  const tasks = (state.lastState && state.lastState.tasks) || [];
  const openTasks = tasks.filter((t) => !t.done).length;
  renderProof();          // independent request — do not make it wait for this one

  title.textContent = todayHeadline(items, tasks);
  paintTasks(tasks);      // the list under the rows, now that we know what is above it

  if (!items.length) {
    const e = d.empty || {};
    /* When the seller has their own tasks listed below, the "upload a sales
       file and this fills up" nudge is wrong twice over: the card is not
       empty, and it talks past the work they can see sitting right there. */
    rows.innerHTML = openTasks ? "" : `<div class="today-empty">
      <span>${esc(e.detail || "")}</span>
      ${e.cta ? `<button class="btn ghost sm" id="todayCta">${esc(e.cta)}</button>` : ""}</div>`;
    const cta = $("todayCta");
    if (cta) cta.onclick = startDemo;
  } else {
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
      <b>Today</b> (new orders, things running low, customers slipping away.
      Nothing else.)</p>
    <label class="fld"><span>Send it</span>
      <select id="dgOn">
        <option value="1"${d.enabled ? " selected" : ""}>Every morning</option>
        <option value="0"${d.enabled ? "" : " selected"}>Never: I'll check myself</option>
      </select></label>
    <label class="fld"><span>At</span><select id="dgHour">${hours}</select></label>
    <label class="fld"><span>Email</span><input id="dgEmail" value="${esc(d.email || state.email)}" /></label>
    <label class="fld"><span>WhatsApp number <span class="muted">(optional)</span></span>
      <input id="dgPhone" value="${esc(d.phone || "")}" placeholder="10-digit mobile" inputmode="numeric" /></label>
    <p class="muted tiny">WhatsApp delivery switches on the moment a provider is connected,
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
        ? `Digest on: every morning at ${String(r.digest.hour).padStart(2, "0")}:00.`
        : "Digest off.");
      const db = $("digestBtn"); if (db) db.classList.toggle("on", !!r.digest.enabled);
    } catch (e) { toast(e.message); }
  };
  $("dgTest").onclick = async () => {
    const b = $("dgTest"); b.disabled = true; b.textContent = "Sending…";
    try {
      const r = await api("/api/digest/test", { method: "POST" });
      toast(r.sent ? "Sent: check your inbox."
                   : (r.reason || "Nothing worth sending right now."), 5000);
    } catch (e) { toast(e.message); }
    b.disabled = false; b.textContent = "Send me one now";
  };
}

/* ONE next step, for a seller who has just signed up.
   ------------------------------------------------------------------
   The home screen is right for someone who already has data in it and wrong for
   someone on their first morning: the thing they need to do (upload a sales
   file) has exactly the same weight as "Position Strategy + AI". This leads with
   the next step, keeps the rest of the screen available but quiet, and removes
   itself the moment the last step is done. Nothing here blocks anything — a
   seller who wants to go straight to the website builder still can. */
/* ------------------------------------------------------- the guide card ----
   THE PROBLEM: a seller who signs up sees fifteen app tiles and a task box,
   and no sentence anywhere saying what this thing is or what it will do for
   them. The setup card below tells them the NEXT step, which is useless if you
   do not yet know what you are setting up. People who do not understand a tool
   in the first thirty seconds do not come back to it on day two.

   So: one short panel, at the top, in plain words — what it does, what it
   needs from them, and what it does on its own. It disappears once setup is
   finished, and "How this works" in the header brings it back for anyone who
   wants it later. No carousel, no tour, nothing that has to be clicked
   through before the app can be used. */
const GUIDE_KEY = "cx_guide_hidden";

function guideHidden() {
  try { return localStorage.getItem(GUIDE_KEY) === "1"; } catch (e) { return false; }
}
function setGuideHidden(v) {
  try { v ? localStorage.setItem(GUIDE_KEY, "1") : localStorage.removeItem(GUIDE_KEY); }
  catch (e) { /* private mode — it just shows again next time */ }
}

function guideCard(s) {
  const setup = s.setup || {};
  // Finished sellers have earned their screen back. They can still reopen it.
  if (setup.complete && guideHidden()) return "";
  if (guideHidden()) return "";
  const salesReady = !!(state.data && state.data.sales && state.data.sales.ready);
  const step = (n, done, title, body) => `
    <li class="${done ? "done" : ""}">
      <span class="gd-n">${done ? sic("check") : n}</span>
      <div><b>${esc(title)}</b><span>${esc(body)}</span></div>
    </li>`;
  const steps = `
      <ol class="guide-steps">
        ${step(1, salesReady, "Give it your sales once",
               "Any export from your marketplace, your billing app or a spreadsheet. It reads the columns for you.")}
        ${step(2, salesReady, "It watches while you work",
               "Stock cover, reorder points, what to post next week, who has stopped buying, all recalculated as orders come in.")}
        ${step(3, false, "You approve, it acts",
               "Purchase orders to your suppliers, posts to your calendar, win-back messages. Every one waits for your yes.")}
      </ol>`;

  /* Once the sales file is in, the seller has done the two things this card
     explains, and it has stopped being an explanation — it is 590px of text
     standing between them and their shop, every single morning, on a screen
     844px tall. It folds itself away and stays one tap from being read again.
     Before that it stays open, because someone who has uploaded nothing yet
     genuinely does not know what this app is for. */
  if (salesReady) {
    return `
    <details class="fold guide-fold" id="guideCard">
      <summary>How this works
        <span class="muted tiny">(give it your sales, it watches, you approve)</span></summary>
      ${steps}
      <div class="guide-foot">
        <span class="muted tiny">The apps below are grouped by what they are for:
          <b>Know what is happening</b>, <b>Run the day</b>, <b>Bring in more customers</b> and <b>Go deeper</b>.</span>
      </div>
    </details>`;
  }

  return `
    <section class="guide-card" id="guideCard">
      <div class="guide-head">
        <div>
          <div class="today-eyebrow">How this works</div>
          <h3>One place to run the shop, not fifteen apps to learn</h3>
          <p>You give it your sales. It works out what is selling, what is about
             to run out, and what to post, then asks you to approve. Nothing is
             sent, ordered or published without you saying yes.</p>
        </div>
        <button class="btn ghost tiny" id="guideHide" title="Hide this" aria-label="Hide this explanation">${sic("close")}</button>
      </div>
      ${steps}
      <div class="guide-foot">
        <span class="muted tiny">Start anywhere. The apps below are grouped by
          what they are for: <b>Know what is happening</b>, <b>Run the day</b>, <b>Bring in more customers</b> and <b>Go deeper</b>.</span>
      </div>
    </section>`;
}

function wireGuide() {
  const hide = $("guideHide");
  if (hide) hide.onclick = () => {
    setGuideHidden(true);
    const el = $("guideCard");
    if (el) { el.style.height = `${el.offsetHeight}px`; el.classList.add("gone"); }
  };
  const show = $("guideShow");
  if (show) show.onclick = () => { setGuideHidden(false); goHome(); };
}

function setupCard(setup) {
  if (!setup || setup.complete || !setup.next) return "";
  const n = setup.next;
  const pct = Math.round(setup.done / setup.total * 100);
  const rest = (setup.steps || []).filter((s) => !s.done && s.id !== n.id);
  return `
    <section class="setup-card">
      <div class="setup-top">
        <div>
          <div class="setup-eyebrow">Next step ${setup.done + 1} of ${setup.total}</div>
          <h3>${esc(n.title)}</h3>
          <p>${esc(n.why)}</p>
        </div>
        <div class="setup-ring" style="--pct:${pct}"><span>${setup.done}/${setup.total}</span></div>
      </div>
      <div class="setup-acts">
        <button class="btn primary" data-setup="${esc(n.action)}">${esc(n.action_label)}</button>
        <span class="muted tiny">about ${n.minutes} minute${n.minutes === 1 ? "" : "s"}</span>
      </div>
      ${rest.length ? `<details class="setup-rest">
        <summary>${rest.length} more after that</summary>
        <ul>${rest.map((r) => `<li><b>${esc(r.title)}</b>, ${esc(r.why)}</li>`).join("")}</ul>
      </details>` : ""}
    </section>`;
}

function wireSetupCard() {
  document.querySelectorAll("[data-setup]").forEach((b) => b.onclick = () => {
    const a = b.dataset.setup;
    if (a === "upload_sales") return startUpload("sales");
    if (a === "set_brand") return openModule("studio");
    if (a === "open_products") return openModule("products");
    if (a === "open_studio") return openModule("studio");
    if (a === "open_site") return openModule("site");
  });
}

function moduleTile(m) {
  const locked = m.needs && !(state.data[m.needs] && state.data[m.needs].ready);
  const upcoming = !!m.upcoming;
  /* "Needs sales data" beats "Locked": one tells you what to do, the other
     tells you off.
     Shortened from "Add your reviews first" because on a phone the tile is a
     row, and four words in a badge wrapped to three shouting lines that pushed
     the module's own name into two. The group heading above it already carries
     the instruction ("Needs your customer reviews. Optional."), so the badge
     only has to name the missing thing. */
  const why = m.needs === "review" ? "Needs reviews" : "Needs sales";
  return `<div class="app-tile ${m.cls} ${locked || upcoming ? "locked" : ""}" data-mod="${m.id}">
      <div class="app-ico">${sic(m.ico)}</div>
      <div class="name">${esc(m.name)}</div>
      <div class="sub">${esc(m.sub)}</div>
      <div class="meta">
        <span class="badge">${upcoming ? "Planned" : (locked ? why : m.tag)}</span>
        <span class="go">${upcoming ? "Soon" : (locked ? "" : "Open")}${locked ? "" : sic("arrow-right")}</span>
      </div>
    </div>`;
}

/* The setup card on home. The first-run journey (journey.js) replaces the old
   five-step card for every account on it. An existing account that never
   opened the journey is offered it only if the old card would still have had
   something to say; a shop that is already set up is not nagged. */
function homeSetupCard(s) {
  const ob = s.onboarding;
  if (typeof journeyCardHtml !== "function" || !ob) return setupCard(s.setup);
  if (!ob.has_record && s.setup && s.setup.complete) return "";
  return journeyCardHtml(ob);
}

function renderHome(s) {
  const tiles = MODULE_GROUPS.map((g) => {
    const inGroup = MODULES.filter((m) => m.group === g.id && !m.offGrid);
    if (!inGroup.length) return "";
    return `<div class="app-group">
        <div class="app-group-head"><h4>${esc(g.title)}</h4><span class="muted tiny">${esc(g.hint)}</span></div>
        <div class="app-grid">${inGroup.map(moduleTile).join("")}</div>
      </div>`;
  }).join("");

  const tasks = (s.tasks || []);
  // A seller with no data yet came for one thing: the first action. On a phone
  // the explainer filled the whole first screen and pushed "Load sample data"
  // and "Upload" below the fold, so until there is data, Today goes first. They
  // are also not "back": they signed up a moment ago.
  const hasData = !!((s.data && s.data.sales && s.data.sales.ready)
                     || (s.data && s.data.review && s.data.review.ready));
  const guide = guideCard(s);
  // The setup journey leads the page while it has something to say: for a
  // seller who just signed up it is the answer to "what do I do now?".
  const journeyOn = typeof journeyCardHtml === "function" && !!s.onboarding;
  const journey = journeyOn ? homeSetupCard(s) : "";

  setView(`
    <!-- The greeting used to take three rows on a phone: "Welcome back", then
         a Refresh button alone, then the account address alone. Three rows of
         chrome before the first useful pixel. The address belongs under the
         greeting as a subtitle, not on a line of its own below the buttons. -->
    <div class="page-head">
      <div class="ph-title">
        <h2>${hasData ? "Welcome back" : "Welcome"}</h2>
        <span class="ph-sub">${esc(state.email)}</span>
      </div>
      <div class="page-actions">
        ${guideHidden() ? `<button class="btn ghost sm" id="guideShow" title="What this app does and how to use it">
          ${sic("compass")}How this works</button>` : ""}
        ${s.onboarding && (!s.onboarding.finished || (s.onboarding.skipped_left || []).length)
            && typeof openJourney === "function"
          ? `<button class="btn ghost sm" id="journeyShow" title="Set up your shop, one step at a time">
          ${sic("check")}${s.onboarding.lang === "hi" ? "सेटअप गाइड" : "Setup guide"}</button>` : ""}
        <button class="btn ghost sm" id="refreshPage" title="Pull the latest numbers without reloading the page">
          ${sic("refresh")}Refresh</button>
      </div>
    </div>

    ${journey}
    ${hasData ? guide : ""}

    <!-- ONE card, not two.
         This used to be two stacked sections: "Your tasks: Nothing waiting on
         you", and under it "Today: Nothing to act on yet". On a phone that is
         two screenfuls of the app telling the seller that nothing is happening
         before they reach anything they can act on, and neither card could
         answer the only question they open the app with: what do I do now?
         The answer is one list. What the shop needs (read from the data) and
         what the seller wrote down for themselves are the same kind of thing,
         both are "do this today", so they live in the same card, under one
         headline that counts both. -->
    <section class="today" id="todayBox">
      <div class="today-h">
        <div>
          <div class="today-eyebrow">Today</div>
          <h3 id="todayTitle">Looking at your shop…</h3>
        </div>
      </div>
      <div id="todayRows" class="today-rows"><div class="ap-empty">Checking orders, stock and customers…</div></div>
      <div id="proofLine" class="today-proof" hidden></div>
      <!-- One list, not a list and then a widget.
           The seller's own tasks used to sit below a rule, under a standing
           "Add your own task…" input, which made the card read as two things
           stacked, "Today", and then a little to-do app. They are the same
           kind of thing: work to do this morning. So the rows now run
           straight on from the ones above with no divider and the same
           shape, and adding one is a quiet line at the end of the list
           rather than a permanent form sitting there asking to be filled. -->
      <div class="today-tasks" id="taskBox">
        <div id="taskList">${taskRowsHtml(tasks)}</div>
        <div class="task-add" id="taskAdd" hidden>
          <input id="taskInput" placeholder="What else needs doing today?" aria-label="Add your own task" />
          <button class="btn primary sm" id="taskAddBtn">Add</button>
        </div>
        <button type="button" class="task-open" id="taskOpen">
          ${sic("plus")}<span>Add something of your own</span></button>
      </div>
      <!-- Moved out of the card's header. "Digest" was also a word from our
           side of the screen; what the button does is email them this list,
           so that is what it says. Up in the header it squeezed the headline
           into three lines on a phone and read like the card's main action,
           which it is not: it is a setting, and settings belong at the end. -->
      <div class="today-foot">
        <button class="btn ghost tiny" id="digestBtn" title="Get this list by email every morning">
          ${sic("bell")}Email me this every morning</button>
      </div>
    </section>

    ${hasData ? "" : guide}

    <section class="up-strip" id="upStrip" hidden></section>

    ${journeyOn ? "" : setupCard(s.setup)}

    <div class="section-title">Your data
      <button class="btn ghost tiny pt-chip" id="ptChip" title="What you sell, in your own words, your captions, hashtags and photo prompts all use this">${sic("tag")}${esc(productLabel(state.productType))}</button>
    </div>
    <div class="data-grid">
      ${dataCard("sales", "Sales", sic("receipt"), "upload your orders / sales export")}
      ${dataCard("review", "Review", sic("star"), "upload your reviews (Google / marketplace / Instagram)")}
    </div>

    <div class="apps-grid">${tiles}</div>

    <!-- Folded away on purpose. This matters to a seller running four channels
         and means nothing to one running none, and it used to sit above the apps
         competing for the same attention. -->
    <details class="fold" id="chanFold">
      <summary>Where you sell <span class="muted tiny">(choose which channels count in your numbers)</span></summary>
      <div class="chan-strip" id="chanStrip"><div class="ap-empty">Loading platforms…</div></div>
    </details>

  `);

  document.querySelectorAll("[data-mod]").forEach((el) => el.onclick = () => {
    const m = MODULES.find((x) => x.id === el.dataset.mod);
    if (m.upcoming) { toast("The Instagram content manager is being built. It will live right here."); return; }
    if (m.needs && !(state.data[m.needs] && state.data[m.needs].ready)) { toast(`Upload ${m.needs} data first`); return; }
    openModule(m.id);
  });
  // three independent reads; firing them together rather than in sequence is
  // the difference between one round-trip and three on a slow connection
  const rp = $("refreshPage");
  if (rp) rp.onclick = refreshCurrent;
  wireGuide();
  wireSetupCard();
  if (typeof wireJourneyCard === "function") wireJourneyCard(s.onboarding);
  const js = $("journeyShow");
  if (js) js.onclick = () => openJourney();
  if (typeof journeyAfterHome === "function") journeyAfterHome(s.onboarding);
  // Inside a folded section now: fetched when it is opened, not on every home
  // paint. One fewer round trip on the load that matters most.
  const chanFold = $("chanFold");
  if (chanFold) chanFold.addEventListener("toggle", () => {
    if (chanFold.open && !chanFold.dataset.loaded) { chanFold.dataset.loaded = "1"; renderChannels(); }
  }, { once: false });
  renderToday();
  renderUpcomingSocial();
  warmOnIntent();
  warmPlotly();     // idle-time, so the first chart does not wait for 3.5 MB
  warmModules();
  document.querySelectorAll("[data-up]").forEach((el) => el.onclick = () => startUpload(el.dataset.up));
  document.querySelectorAll("[data-add]").forEach((el) => el.onclick = () => openAddRecords(el.dataset.add));
  document.querySelectorAll("[data-clear]").forEach((el) => el.onclick = () => clearData(el.dataset.clear));
  document.querySelectorAll("[data-remap]").forEach((el) => el.onclick = () => remap(el.dataset.remap));
  $("ptChip").onclick = () => openProductTypePicker();
  $("taskAddBtn").onclick = addTask;
  $("taskInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") addTask();
    // Escape puts the line back the way it was, rather than leaving an open
    // form behind for a seller who changed their mind.
    if (e.key === "Escape") closeTaskAdd();
  });
  /* An empty box that has been tapped away from is the form still sitting
     there. Typed-in text is never thrown away this way — only a blank one
     folds itself back up. */
  $("taskInput").addEventListener("blur", () => {
    if (!$("taskInput").value.trim()) closeTaskAdd();
  });
  $("taskOpen").onclick = openTaskAdd;
  wireTasks();
}

/* The add-a-task line, open and shut. A standing input box at the bottom of
   the Today card read as a second widget — a little to-do app bolted under
   the list. As one quiet line it reads as what it is: the end of the list,
   with room to add to it. */
function openTaskAdd() {
  const add = $("taskAdd"), open = $("taskOpen");
  if (!add || !open) return;
  add.hidden = false; open.hidden = true;
  const inp = $("taskInput");
  if (inp) inp.focus();
}
function closeTaskAdd() {
  const add = $("taskAdd"), open = $("taskOpen");
  if (!add || !open) return;
  const inp = $("taskInput");
  if (inp) inp.value = "";
  add.hidden = true; open.hidden = false;
}

// ---------- product type ----------
function openProductTypePicker(afterSet) {
  const types = state.productTypes && state.productTypes.length ? state.productTypes :
    [{ id: "jewellery", label: "Jewellery", icon: "spark" }, { id: "clothes", label: "Clothes", icon: "scissors" },
     { id: "perfumes", label: "Perfumes", icon: "droplet" }, { id: "generic", label: "Other products", icon: "bag" }];
  /* THE FOUR PRESETS WERE NOT ENOUGH. Everything outside jewellery, clothes
     and perfumes landed in "Other products", and every caption written for
     those sellers said "product", because that is the only noun the generic
     type carries. A candle maker reading "Check out this product" knows
     immediately that the app does not know what shop it is in.

     So the seller types it. The presets stay — each carries a real positioning
     and complaint lexicon — but the words are theirs, and the words are what
     reach every caption, hashtag and image prompt. */
  $("ptGrid").innerHTML = types.map((t) => `
    <button class="pt-card ${t.id === state.productType ? "selected" : ""}" data-pt="${t.id}">
      <div class="pt-ico">${ico(t.icon)}</div><div>${esc(t.label)}</div>
    </button>`).join("") + `
    <div class="pt-own">
      <label>Or tell us in your own words
        <input id="ptOwn" maxlength="40" placeholder="e.g. Soy wax candles, Blue pottery, Kundan jewellery"
               value="${esc(state.productLabel || "")}" /></label>
      <p class="muted tiny">This is what your captions will call what you sell, so
        "${esc(state.productLabel || "Soy wax candles")}" beats "products". Leave it
        blank to use the choice above.</p>
      <button class="btn primary sm" id="ptOwnGo">Use my words</button>
    </div>`;
  $("ptModal").hidden = false;

  const apply = (pt, label) => {
    // Applied optimistically, and afterSet() runs synchronously, so a file
    // dialog opens inside this click gesture — browsers block a file input
    // .click() that happens after an awaited call, which is why the first
    // review upload never showed the mapping popup.
    state.productType = pt;
    if (label !== undefined) state.productLabel = label;
    $("ptModal").hidden = true;
    const shown = label || productLabel(pt);
    toast(`Set to ${shown}`);
    const chip = $("ptChip"); if (chip) chip.innerHTML = `${esc(shown)}`;
    const body = { product_type: pt };
    if (label !== undefined) body.label = label;
    api("/api/product-type", { method: "POST", json: body })
      .then((r) => { state.productType = r.product_type; state.productLabel = r.label || ""; })
      .catch((e) => toast(e.message));
    if (afterSet) afterSet();
  };

  $("ptGrid").querySelectorAll("[data-pt]").forEach((b) => b.onclick = () => apply(b.dataset.pt));
  const own = $("ptOwn"), ownGo = $("ptOwnGo");
  const useOwn = () => {
    const text = (own.value || "").trim();
    if (!text) { own.focus(); return; }
    // Their words refine whichever preset is selected, so a jeweller typing
    // "Kundan jewellery" keeps the jewellery lexicon AND gets their own noun.
    apply(state.productType || "generic", text);
  };
  if (ownGo) ownGo.onclick = useOwn;
  if (own) own.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); useOwn(); } });
}
$("ptClose").onclick = () => { $("ptModal").hidden = true; };

// ---------- tasks ----------
async function addTask() {
  const inp = $("taskInput"); const text = inp.value.trim(); if (!text) return;
  inp.value = "";
  const r = await api("/api/smart/tasks", { method: "POST", json: { action: "add", text } });
  refreshTaskList(r.tasks);
  // Morning tasks arrive in threes, not ones. The line stays open and focused
  // so the second and third do not each cost another tap to get back here.
  if (inp.isConnected) inp.focus();
}
/* Post tasks first (the ones with a posting time on them, soonest first), then
   the seller's own, then a few recently finished ones so a tick is visible. */
function orderTasks(tasks) {
  const open = (tasks || []).filter((t) => !t.done);
  const post = open.filter((t) => t.post_id).sort((a, b) => String(a.due || "").localeCompare(String(b.due || "")));
  const own = open.filter((t) => !t.post_id);
  const done = (tasks || []).filter((t) => t.done).slice(-4).reverse();
  return [...post, ...own, ...done];
}
/* One headline over both lists.
   The seller does not sort their morning into "things the software noticed"
   and "things I wrote down" — it is all just today. So the count is the sum,
   and reels get called out by name because a reel is the one task that takes
   real time and is easy to leave until it is too late. */
function todayHeadline(items, tasks) {
  const open = (tasks || []).filter((t) => !t.done);
  const reels = open.filter((t) => t.kind === "video").length;
  const n = (items || []).length + open.length;
  if (!n) return "Nothing needs you this morning";
  const head = n === 1 ? "1 thing to do today" : `${n} things to do today`;
  return reels ? `${head} · ${reels} reel${reels === 1 ? "" : "s"} to film` : head;
}
/* An empty task list says nothing at all. The card already has one message
   when there is nothing to do, and a paragraph explaining that tasks would
   appear here if there were any is the second empty state that made the home
   screen feel like it was apologising twice. The "Add your own task…" box
   sitting right underneath is the explanation. */
/* HOW MANY THINGS A MORNING LIST CAN BE.
   Measured on an account that had let work pile up: twenty-one tasks, and the
   Today card came to 3,412px — four phone screens of list, on the card whose
   entire job is answering "what do I do now". Past about six rows a list stops
   being an answer and becomes a backlog, and a backlog is exactly the thing a
   seller opens this app to avoid looking at.
   The first six, in the order they already come in (posts by their time, then
   the seller's own), and the rest one tap away. The headline still counts all
   of them, because the count is the honest number — it is the reading that is
   capped, not the truth. */
const TASKS_SHOWN = 6;
let _tasksExpanded = false;

function taskRowsHtml(tasks) {
  const all = orderTasks(tasks);
  if (!all.length) return "";
  const hidden = _tasksExpanded ? 0 : Math.max(0, all.length - TASKS_SHOWN);
  const rows = hidden ? all.slice(0, TASKS_SHOWN) : all;
  const more = hidden
    ? `<button type="button" class="task-more" id="taskMore">${sic("chevron-down")}
         <span>${hidden} more waiting</span></button>`
    : (_tasksExpanded && all.length > TASKS_SHOWN
       ? `<button type="button" class="task-more" id="taskMore">${sic("chevron-down")}
            <span>Show fewer</span></button>` : "");
  return rows.map((t) => {
    if (t.post_id && !t.done) {
      const steps = t.steps || [];
      const doneSteps = new Set(t.steps_done || []);
      const n = steps.filter((x) => doneSteps.has(x.id)).length;
      const next = steps.find((x) => !doneSteps.has(x.id));
      /* The task's own text carries its deadline inline — "Make the reel for
         Linen Dupatta — goes out Mon 14 Sep, 7:00 PM" — which is right in an
         email digest and wrong in a list, where it wrapped to three bold lines
         and made a 200px row out of a one-line job. The deadline is context,
         not the instruction, so it joins the other context underneath. The
         server's wording is untouched: this is a display decision, and the
         digest still reads as one sentence. */
      // A delimiter, not copy: it matches the em dash the SERVER writes in task
      // titles ("Make the reel for X, em dash, goes out Mon"). It must stay an em
      // dash for as long as the server writes one; see TODOS.md before changing
      // either side. The launch copy sweep leaves .split() arguments alone.
      const cut = String(t.text || "").split(" — ");
      const title = cut[0];
      const when = cut.length > 1 ? cut.slice(1).join(" – ") : "";
      return `
      <div class="task-item task-post" data-task="${esc(t.id)}">
        <span class="task-ico ${t.kind === "video" ? "reel" : "photo"}">${sic(t.kind === "video" ? "play" : "image")}</span>
        <div class="t">
          <b>${esc(title)}</b>
          <span class="task-sub">${when ? esc(when.charAt(0).toUpperCase() + when.slice(1)) + " · " : ""}${n} of ${steps.length} steps done${next ? ` · next: ${esc(next.label)}` : ""}${t.reason ? ` · ${esc(t.reason.length > 90 ? t.reason.slice(0, 88) + "…" : t.reason)}` : ""}</span>
          <span class="task-dots">${steps.map((x) => `<i class="${doneSteps.has(x.id) ? "on" : ""}" title="${esc(x.label)}"></i>`).join("")}</span>
        </div>
        <button class="btn primary sm" data-vtask="${esc(t.id)}">${t.kind === "video" ? "Open task" : "Add picture"}</button>
      </div>`;
    }
    return `
      <div class="task-item ${t.done ? "done" : ""}" data-task="${esc(t.id)}">
        <input type="checkbox"${t.done ? "checked" : ""} ${t.post_id ? "disabled" : ""} />
        <span class="t">${esc(t.text)}</span>
        ${t.ob && !t.done && typeof openJourney === "function"
          ? `<button class="btn ghost tiny" data-obopen="${esc(t.ob)}">Open</button>` : ""}
        <button class="task-del" title="Delete this task" aria-label="Delete this task">${sic("close")}</button>
      </div>`;
  }).join("") + more;
}
function wireTasks() {
  const more = $("taskMore");
  if (more) more.onclick = () => {
    _tasksExpanded = !_tasksExpanded;
    paintTasks(((state.lastState || {}).tasks) || []);
  };
  document.querySelectorAll("#taskList [data-vtask]").forEach((b) => b.onclick = () => openVideoTask(b.dataset.vtask));
  // A setup task opens the journey at its own step or part.
  document.querySelectorAll("#taskList [data-obopen]").forEach((b) => b.onclick = () => {
    const [kind, val] = b.dataset.obopen.split(":");
    openJourney(kind === "part" ? { part: parseInt(val, 10) } : { step: val });
  });
  document.querySelectorAll("#taskList [data-task]").forEach((row) => {
    const box = row.querySelector("input[type=checkbox]");
    if (box) box.onchange = async (e) => {
      const r = await api("/api/smart/tasks", { method: "POST", json: { action: "toggle", task_id: row.dataset.task, done: e.target.checked } });
      refreshTaskList(r.tasks);
    };
    const del = row.querySelector(".task-del");
    if (del) del.onclick = async () => {
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
function paintTasks(tasks) {
  const list = $("taskList"); if (!list) return;
  list.innerHTML = taskRowsHtml(tasks || []);
  wireTasks();
}
function refreshTaskList(tasks) {
  if (state.lastState) state.lastState.tasks = tasks;
  paintTasks(tasks);
  /* Ticking something off changes the count in the card's headline, and a
     headline that still says "3 things to do today" over two rows is the kind
     of small wrongness that makes people stop trusting the number. */
  const head = $("todayTitle");
  if (head) head.textContent = todayHeadline(_todayItems, tasks || []);
}

/* =========================================================================
   ONE TAP, AND THE TAP IS THE WHOLE WAIT
   =========================================================================
   Approving used to mean: open a blocking overlay, hold the seller there for
   the entire server round trip — which for a photo post includes drawing the
   picture with an AI, on half a CPU — then refetch the whole app state, then
   refetch the social plan, then repaint. The seller taps "Approve" and watches
   a spinner for several seconds, having already made the only decision that
   needed them.

   The decision is the seller's part. The work is ours. So the tap now does
   what the seller means by it: the card leaves, immediately, and the work
   carries on behind them. Nothing blocks.

   The honest part is what happens when the work fails. A card that vanished on
   a promise and never came back is worse than a spinner, because the seller
   believes a thing happened that did not. So a failed job puts its card back,
   at the top, wearing what went wrong and when — "Tried 4 minutes ago: the
   picture could not be drawn."The record survives a reload, because the
   failure outlives the page that saw it.

   This is the machinery. Every approve, dismiss and cancel goes through it.
   ========================================================================= */

const QUEUE_LANES = 2;          // two at once: enough to feel parallel,
                                // few enough not to stampede a small dyno
const FAIL_KEY = "cx_failed_jobs";
/* Three days, not fourteen. Insight ids repeat — "winback" is a fixed string
   and a weekly plan can rehash a post to the same id — so a record that
   outlives its own card attaches itself to a different one. Pruning catches
   the ids that disappear; this catches the ids that come back. Three days
   covers a seller who left it on Friday and returns on Monday. */
const FAIL_TTL_DAYS = 3;

let _jobs = [];                 // {id, label, run, card, state}
let _lanes = 0;
let _failed = loadFailures();

function loadFailures() {
  try {
    const raw = JSON.parse(localStorage.getItem(FAIL_KEY) || "{}");
    const cut = Date.now() - FAIL_TTL_DAYS * 864e5;
    const keep = {};
    for (const [k, v] of Object.entries(raw)) if (v && v.at > cut) keep[k] = v;
    return keep;
  } catch (e) { return {}; }
}
function saveFailures() {
  try { localStorage.setItem(FAIL_KEY, JSON.stringify(_failed)); } catch (e) {}
}
function clearFailure(id) {
  if (!_failed[id]) return;
  delete _failed[id]; saveFailures();
}
function noteFailure(id, reason, unsure) {
  _failed[id] = { reason: String(reason || "It did not go through."),
                  at: Date.now(), unsure: !!unsure };
  saveFailures();
}
/* "4 minutes ago" beats a timestamp on a card a seller is scanning. */
function ago(ts) {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 90) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} minute${m === 1 ? "" : "s"} ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.round(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

/* The card goes before the request does.
   id     the insight id, so a failure can put the right card back
   label  what to say in the working strip ("Making the picture")
   run    the actual work; resolve = done, throw = put the card back
   onDone optional, given the resolved value  */
function runInBackground(id, { label, run, onDone, card } = {}) {
  /* ONE JOB PER CARD, EVER.
     The bulk bar holds the list of cards as it was when the panel last
     painted, and approving a single card does not repaint it — so "Approve all
     9" could re-send a post the seller had already approved a moment earlier.
     Two lanes means those two requests are genuinely concurrent: two AI
     pictures billed, or the same purchase order emailed to a supplier twice.
     A second job for an id already working is not a retry, it is a duplicate. */
  if (_jobs.some((j) => j.id === id)) return;

  const insights = ((state.lastState || {}).insights) || [];
  // The caller may have read the card already (approveWeek has to, because it
  // removes the whole week's worth before queueing any of them).
  const keep = card || insights.find((x) => x.id === id) || null;

  clearFailure(id);
  animateCardOut(id);
  if (state.lastState) state.lastState.insights = insights.filter((x) => x.id !== id);
  paintApprovalCount((((state.lastState || {}).insights) || []).filter((i) => !i.summary).length);
  _jobs.push({ id, label: label || "Working", run, card: keep, onDone, state: "waiting" });
  syncBulkBar();
  paintWorkStrip();
  pumpQueue();
}

/* "Approve all 9" over a list that is down to two is a lie about how much the
   tap is agreeing to. The bar counts what is actually left, and goes entirely
   when there is nothing left to do in bulk. Repainting the whole panel would
   be simpler and would also cancel the exit animation of the card that just
   left, which is the one thing on screen the seller is looking at. */
function syncBulkBar() {
  const bar = document.querySelector(".ap-bulk");
  if (!bar) return;
  const left = (((state.lastState || {}).insights) || []).filter((i) => !i.summary).length;
  if (left < 2) { bar.remove(); return; }
  const all = $("apAll");
  if (all && !all.disabled) all.textContent = `✓ Approve all ${left}`;
}

function pumpQueue() {
  while (_lanes < QUEUE_LANES) {
    const job = _jobs.find((j) => j.state === "waiting");
    if (!job) break;
    job.state = "running";
    _lanes++;
    paintWorkStrip();
    Promise.resolve()
      .then(job.run)
      .then((r) => {
        _jobs = _jobs.filter((j) => j !== job);
        clearFailure(job.id);
        if (job.onDone) { try { job.onDone(r); } catch (e) {} }
      })
      .catch((e) => {
        _jobs = _jobs.filter((j) => j !== job);
        /* THERE ARE TWO KINDS OF FAILURE AND ONLY ONE OF THEM IS CERTAIN.
           A 4xx/5xx is the server saying no: the work did not happen. But
           `status: 0` is the connection dropping, and that can happen AFTER
           the request landed — the purchase order is already in the
           supplier's inbox and only the reply was lost. Telling that seller
           "This did not go through" and offering "Try again" is how a
           supplier receives the same order twice. None of these endpoints is
           idempotent, so the honest word is that we do not know. */
        const unsure = e && e.status === 0;
        noteFailure(job.id, unsure
          ? "The connection dropped before we heard back, so we cannot tell "
            + "whether it went through. Check before sending it again."
          : (e && e.message), unsure);
        /* Back where it was, so the seller can see it and try again. At the
           top, because a thing that failed is more urgent than a thing that
           has not been looked at yet. */
        if (job.card && state.lastState) {
          const ins = state.lastState.insights || [];
          if (!ins.some((x) => x.id === job.id)) state.lastState.insights = [job.card, ...ins];
          renderApprovals(state.lastState.insights);
        }
        toast(`${job.label} did not go through. It is back in your approvals.`, 6000);
      })
      .finally(() => {
        _lanes--;
        paintWorkStrip();
        if (!_jobs.length) settleAfterQueue();
        pumpQueue();
      });
  }
}

/* THE ONE PROMISE THIS QUEUE CANNOT KEEP.
   "Carry on, they finish by themselves" is true of moving around the app —
   the panel lives outside the view that modules repaint, so jobs survive
   navigation. It is NOT true of closing the tab: the work is driven from here,
   and a request that has not gone out yet dies with the page, silently, with
   no failure record written because the catch never runs.
   So the one moment it matters, the browser asks. Nothing else in the app does
   this, and it is deliberately the only thing that does. */
window.addEventListener("beforeunload", (e) => {
  if (!_jobs.length) return;
  e.preventDefault();
  e.returnValue = "";           // the wording is the browser's, not ours
  return "";
});

/* One refresh after the queue drains, not one per job. Approving six posts
   used to mean six full state refetches racing each other, each repainting
   the list under the seller's thumb. */
let _settleTimer = null;
function settleAfterQueue() {
  clearTimeout(_settleTimer);
  _settleTimer = setTimeout(async () => {
    if (_jobs.length) return;                  // more arrived; that run settles
    try { await afterPostChange(); } catch (e) {}
  }, 400);
}

/* The card's exit. 180ms, inside the window where a person reads movement as
   their own doing rather than as the app responding to them. */
function animateCardOut(id) {
  const sel = window.CSS && CSS.escape ? CSS.escape(String(id)) : String(id);
  const el = document.querySelector(`.ins-card[data-ins="${sel}"]`);
  if (!el) return;
  el.style.setProperty("--h", el.offsetHeight + "px");
  el.classList.add("ins-leaving");
  setTimeout(() => { if (el.isConnected) el.remove(); }, 190);
}

/* The working strip: ambient, never blocking, never in the way. iOS shows
   background work at the edge of the screen and lets you carry on; it does not
   put a modal over the thing you were doing. */
function paintWorkStrip() {
  let el = $("workStrip");
  const active = _jobs.length;
  if (!active) {
    if (el) { el.classList.remove("on"); setTimeout(() => { if (el.isConnected) el.remove(); }, 260); }
    return;
  }
  if (!el) {
    el = document.createElement("div");
    el.id = "workStrip";
    el.className = "work-strip";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add("on"));
  }
  const running = _jobs.filter((j) => j.state === "running");
  const first = running[0] || _jobs[0];
  el.innerHTML = `<span class="ws-spin" aria-hidden="true"></span>
    <span class="ws-txt">${esc(first.label)}${active > 1 ? ` · ${active - 1} more` : ""}</span>`;
}

/* ---------- the panel, on a phone ----------
   Beside the workspace this is a column that costs no vertical space, so it
   shows everything. Stacked under a phone screen the same panel measured
   2,261px — nine cards below four groups of tiles, which is past where
   anybody scrolls. So on a phone it arrives shut, showing the one number that
   matters: how many decisions are waiting. Tapping it opens the list.

   Shut once, per session: a seller who opens it has said they want it open,
   and having it snap shut again on the next repaint would be the app arguing
   with them. */
let _apShut = null;
function paintApprovalCount(n) {
  const panel = $("approvalPanel"), chip = $("apCount");
  if (!panel || !chip) return;
  chip.textContent = n ? `${n} waiting` : "all clear";
  chip.hidden = false;
  const tb = $("tabBadge"); if (tb) tb.textContent = n ? String(n > 99 ? "99+" : n) : "";
  if (_apShut === null) _apShut = true;      // first paint of the session
  panel.classList.toggle("shut", _apShut);
  const head = $("apHead");
  if (head && !head.dataset.wired) {
    head.dataset.wired = "1";
    /* Beside the workspace this header is a heading, not a control — there is
       nothing to fold. Announcing it as a button on a desktop would promise a
       press that does nothing, so the role follows the layout and is kept in
       step when the window is resized across the breakpoint. */
    const narrow = window.matchMedia("(max-width: 900px)");
    const syncRole = () => {
      if (narrow.matches) {
        head.setAttribute("role", "button");
        head.setAttribute("tabindex", "0");
        head.setAttribute("aria-expanded", String(!_apShut));
      } else {
        head.removeAttribute("role");
        head.removeAttribute("tabindex");
        head.removeAttribute("aria-expanded");
      }
    };
    if (narrow.addEventListener) narrow.addEventListener("change", syncRole);
    syncRole();
    const flip = (e) => {
      if (!narrow.matches) return;
      // The History and Refresh buttons live in this header too.
      if (e.target.closest(".ap-head-actions")) return;
      _apShut = !_apShut;
      panel.classList.toggle("shut", _apShut);
      head.setAttribute("aria-expanded", String(!_apShut));
    };
    head.onclick = flip;
    head.onkeydown = (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      if (e.target.closest(".ap-head-actions")) return;   // let the real buttons work
      e.preventDefault(); flip(e);
    };
  }
}

// ---------- approvals ----------
function renderApprovals(insights) {
  const list = $("approvalList");
  // Eleven places paint this panel, and any of them could be holding a list
  // fetched before the seller's last tap. Filtering here rather than at each
  // call site means a card can never flicker back for work already in flight.
  insights = withoutInFlight(insights);
  /* Anything that failed comes first. A card the seller already decided and
     which then went wrong is more urgent than one they have not looked at, and
     it is the one thing in this panel they might otherwise never notice —
     they believe it is done. Summary cards (the weekly plan header) keep their
     place at the top; the sort is stable, so everything else holds its order. */
  if (Object.keys(_failed).length) {
    const rank = (i) => (i.summary ? 0 : _failed[i.id] ? 1 : 2);
    insights = (insights || []).map((i, n) => [i, n])
      .sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1])
      .map((p) => p[0]);
  }
  const hist = (state.lastState && state.lastState.history) || { approved: [], dismissed: [] };
  const decidedCount = (hist.approved || []).length + (hist.dismissed || []).length;
  paintApprovalCount((insights || []).filter((i) => !i.summary).length);
  if (!insights || !insights.length) {
    list.innerHTML = `<div class="ap-empty">${decidedCount ? "All caught up: nothing pending. Check <b>History</b> for what you've handled." : "No pending insights. Upload data or check back after new activity."}</div>`;
    return;
  }
  /* One tap for the whole panel.

     Odoo's list views have a two-tier selection model — select what is on the
     page, then escalate to "everything matching". The same idea applies here:
     a seller with nine pending insights should not have to press Approve nine
     times to agree with all of them. The count is in the label so the tap is
     never ambiguous about how much it is agreeing to. The weekly plan's header
     card is not counted: its posts are already in the list. */
  const actionable = insights.filter((i) => !i.summary);
  const bulk = actionable.length > 1 ? `
    <div class="ap-bulk">
      <button class="btn approve sm" id="apAll">✓ Approve all ${actionable.length}</button>
      <button class="btn ghost sm" id="apNone">Dismiss all</button>
    </div>` : "";

  /* Cards are grouped by desk, so the panel reads as five managers reporting
     in rather than a shuffled queue. The manager's name is the first thing on
     the card because it tells the seller which part of the business this is
     about before they have read a word of the content. */
  let lastMgr = null;
  const cards = insights.map((i) => {
    const head = i.manager_name && i.manager !== lastMgr
      ? `<div class="mgr-head" style="--mgr:${esc(i.manager_colour || "#5c6790")}">
           ${sic(i.manager_icon || "spark")}
           <b>${esc(i.manager_name)}</b>
           <span>${esc(i.manager_remit || "")}</span>
         </div>` : "";
    lastMgr = i.manager || lastMgr;

    // The week the Social Media Manager planned on its own: what it found and
    // one decision for all of it, above the posts themselves.
    if (i.summary) {
      const chips = [
        i.occasion ? `<span class="wk-chip fest">${esc(i.occasion)}</span>` : "",
        ...(i.winners || []).map((w) => `<span class="wk-chip win" title="Selling well">${sic("trend")}${esc(w)}</span>`),
        ...(i.strugglers || []).map((w) => `<span class="wk-chip slow" title="Struggling">${esc(w)}</span>`),
      ].join("");
      return head + `
      <div class="ins-card mgr-card wk-card" data-ins="${esc(i.id)}" style="--mgr:${esc(i.manager_colour || "#5c6790")}">
        <span class="ins-kind plan">WEEKLY PLAN · ${esc(i.week_label || "")}</span>
        <div class="ins-title"><span>${esc(i.headline || i.title)}</span></div>
        <div class="ins-detail">${esc(i.body || i.detail)}</div>
        ${chips ? `<div class="wk-chips">${chips}</div>` : ""}
        <div class="ins-actions">
          <button class="btn approve" data-apweek="${esc(i.id)}">${esc(i.cta || "Approve all")}</button>
          <button class="btn ghost" data-details="${esc(i.id)}">Details</button>
          <button class="btn reject" data-cancel="${esc(i.id)}">Cancel</button>
        </div>
      </div>`;
    }

    // A reel and a photo post ask completely different things of the seller, so
    // the card says which it is BEFORE they tap, and the button says what will
    // actually happen.
    const kind = i.kind_label ? `<span class="ins-kind ${i.kind === "reel" ? "reel" : "photo"}">${esc(i.kind_label)}</span>` : "";
    const need = i.needs_from_you ? `<div class="ins-need">${sic(i.kind === "reel" ? "play" : "image")}<span>${esc(i.needs_from_you)}</span></div>` : "";
    const isPost = String(i.id).startsWith("post_") || String(i.id).startsWith("po_");
    // Why THIS product, this week — the sales signal or festival behind it.
    const why = isPost && i.plan_reason
      ? `<div class="ins-why ${esc(i.signal || "")}">${esc(i.plan_reason)}</div>`
      : i.purchase_order && i.reason ? `<div class="ins-why struggling">${esc(i.reason)}</div>` : "";
    /* A card that came back. It left on a tap, the work failed behind the
       seller's back, and it returned — so it has to say so itself, on the
       card, not in a toast that has long since gone. */
    const f = _failed[i.id];
    const failBar = f ? `<div class="ins-failed${f.unsure ? " unsure" : ""}">${sic("alert")}
        <span><b>${f.unsure
          ? `We could not confirm this, ${esc(ago(f.at))}.`
          : `This did not go through ${esc(ago(f.at))}.`}</b>
        ${esc(f.reason)}</span></div>` : "";
    return head + `
    <div class="ins-card mgr-card${f ? " has-failed" : ""}" data-ins="${esc(i.id)}" style="--mgr:${esc(i.manager_colour || "#5c6790")}">
      ${kind}
      ${failBar}
      <div class="ins-title"><span>${esc(i.headline || i.title)}</span></div>
      <div class="ins-detail">${esc(i.body || i.detail)}</div>
      ${why}
      ${need}
      <div class="ins-actions">
        <button class="btn approve" data-approve="${esc(i.id)}">${f ? (f.unsure ? "Check, then try again" : "Try again") : esc(i.cta || "Approve")}</button>
        <button class="btn ghost" data-details="${esc(i.id)}">Details</button>
        ${isPost
          ? `<button class="btn reject" data-cancel="${esc(i.id)}">Cancel</button>`
          : `<button class="btn reject" data-reject="${esc(i.id)}">Not now</button>`}
      </div>
    </div>`;
  }).join("");

  list.innerHTML = bulk + cards;

  list.querySelectorAll("[data-approve]").forEach((b) => b.onclick = () => decide(b.dataset.approve, "approve"));
  list.querySelectorAll("[data-reject]").forEach((b) => b.onclick = () => decide(b.dataset.reject, "disapprove"));
  list.querySelectorAll("[data-cancel]").forEach((b) => b.onclick = () => decide(b.dataset.cancel, "cancel"));
  list.querySelectorAll("[data-details]").forEach((b) => b.onclick = () => openDetails(b.dataset.details));
  list.querySelectorAll("[data-apweek]").forEach((b) => b.onclick = () => {
    const card = insights.find((x) => x.id === b.dataset.apweek);
    if (card) approveWeek(card);
  });

  /* "Approve all nine" is the tap that most deserves not to be waited on.
     It used to run nine requests one after another behind a blocking overlay
     counting "3/9" — the better part of a minute on a small dyno, with the
     seller pinned to the screen watching a number go up.
     Now the whole list empties at once and the nine jobs run two at a time
     behind them. Whichever ones fail come back, individually, each saying what
     went wrong — which is strictly better than the old behaviour of swallowing
     every failure and reporting "7 of 9 handled" without ever saying which two
     or why. */
  const runAll = (decision, label) => {
    /* BOTH buttons, not just the one that was pressed.
       "Dismiss all" stayed live above an emptied list, still wired to the
       nine insights captured when the bar was drawn — and for posts and
       purchase orders its branch sends `cancel` with no confirmation. A
       mis-tap four seconds after "Approve all" cancelled the nine posts the
       seller had just approved. The bar describes a list that no longer
       exists; it goes as a whole. */
    const bar = document.querySelector(".ap-bulk");
    if (bar) bar.remove();
    const btn = $(decision === "approve" ? "apAll" : "apNone");
    if (btn) { btn.disabled = true; btn.textContent = label + "…"; }
    for (const i of actionable) {
      const id = String(i.id);
      const jobLabel = i.cta || label;
      if (id.startsWith("post_") && decision === "approve") {
        approvePostReady(id.slice(5));
      } else if (id.startsWith("po_") && decision === "approve") {
        // Through the same function as its own button, so a PO the server
        // could not email still opens the "send it yourself" handover here.
        approvePo(id.slice(3));
      } else if (id.startsWith("post_") || id.startsWith("po_")) {
        runInBackground(id, { label: "Cancelling",
          run: () => api(`/api/smart/insight/${id}/decision`, { method: "POST", json: { decision: "cancel" } }) });
      } else {
        runInBackground(id, { label: jobLabel,
          run: () => api(`/api/smart/insight/${id}/decision`, { method: "POST", json: { decision } }) });
      }
    }
    toast(`${actionable.length} sent. Carry on, they finish by themselves.`, 4000);
  };
  if ($("apAll")) $("apAll").onclick = () => runAll("approve", "Approving");
  if ($("apNone")) $("apNone").onclick = () => runAll("disapprove", "Dismissing");
}

/* Approve every post in an auto-planned week, one at a time so each picture is
   drawn and each reel gets its task, with progress on screen. */
async function approveWeek(card) {
  const ids = card.post_ids || [];
  if (!ids.length) return;

  /* Approving a week is a single decision about six or seven posts, and it was
     the longest wait in the app: a blocking overlay counting "Post 4 of 7"
     while every picture was drawn in turn. A minute, sometimes more, with the
     seller unable to do anything but watch.
     The week's card goes on the tap. Each post becomes its own job, so each
     one can succeed or fail on its own terms — and a post whose picture cannot
     be drawn comes back as its own card saying so, rather than being summed
     into "2 could not be approved" with no way to tell which two. */
  /* READ THE CARDS BEFORE REMOVING THEM.
     This used to filter the week's posts out of the list first and then look
     each one up to find out whether it was a reel — by which point the lookup
     could only ever return undefined. Every job was labelled "Making a
     picture" even for reels, and, far worse, every job carried a null card, so
     `pumpQueue`'s failure path had nothing to put back. On a dropped
     connection the seller got seven toasts saying the posts were "back in your
     approvals" over an empty panel, and believed a week of posts was
     scheduled. Nothing but a reload recovered it. */
  const ins = ((state.lastState || {}).insights) || [];
  const cards = ids.map((pid) => ins.find((x) => x.id === "post_" + pid) || null);

  animateCardOut(card.id);
  if (state.lastState) {
    state.lastState.insights = ins.filter((x) => x.id !== card.id);
  }
  ids.forEach((pid, n) => {
    const isReel = !!(cards[n] && cards[n].kind === "reel");
    runInBackground("post_" + pid, {
      card: cards[n],
      label: isReel ? "Setting up a video task" : "Making a picture",
      run: () => api("/api/social/approve-ready", { method: "POST", json: { post_id: pid } }),
      onDone: (r) => { if (r && r.tasks) refreshTaskList(r.tasks); },
    });
  });
  const reels = cards.filter((c) => c && c.kind === "reel").length;
  const pics = ids.length - reels;
  const bits = [];
  if (pics) bits.push(`${pics} picture${pics === 1 ? "" : "s"} being drawn`);
  if (reels) bits.push(`${reels} reel${reels === 1 ? "" : "s"} going on your task list`);
  toast(`${ids.length} post${ids.length === 1 ? "" : "s"} approved, ${bits.join(", ")}. `
        + `You can carry on.`, 6000);
}

/* Everything that shows a post's state, repainted after one changes. */
async function afterPostChange() {
  await refreshApprovals(true);
  if (state.lastState && state.lastState.tasks) refreshTaskList(state.lastState.tasks);
  if (_currentModule === "social" && _socialData) {
    try { _socialData = await api("/api/social"); await renderSocial(); } catch (e) { /* next open repaints */ }
  }
  if (!_currentModule && $("upStrip")) renderUpcomingSocial();
}

/* Approve, and make the post actually postable.
   ------------------------------------------------------------------
   An image post gets its picture drawn and is then scheduled. A reel cannot —
   there is no single photograph that IS a video — so it gets its shot list and
   the paste-ready prompt instead, and is scheduled as ready-to-film with the
   clip still to come.

   A generation failure never blocks the approval: the seller's decision is the
   valuable part and the server honours it either way. The panel just says what
   is still outstanding. */
/* Which AI makes the clip, and what it costs, decided by the seller before
   anything is spent. Rendered as cards rather than a confirm() because the two
   engines differ by 6x in price and by a lot in quality, and that is a real
   decision a confirm box cannot present. */
function pickVideoEngine(opts) {
  return new Promise((resolve) => {
    if (!opts || !opts.length) { resolve(null); return; }
    if (opts.length === 1) {
      const o = opts[0];
      resolve(confirm(`Make a clip with ${o.label}?\n\nCost: ${o.cost}\n\n${o.note}\n\nContinue?`)
        ? o : null);
      return;
    }
    const rows = opts.map((o, n) => `
      <label class="eng-card">
        <input type="radio" name="vengine" value="${esc(o.id)}"${n === 0 ? "checked" : ""} />
        <div><b>${esc(o.label)}</b> <span class="eng-cost">${esc(o.cost || "")}</span>
          <div class="muted tiny">${esc(o.note || "")}</div></div>
      </label>`).join("");
    openModal("Which AI should make the clip?", `
      <p class="muted">Both animate your own photograph, so the product in the clip
        is the product you sell. You are charged by the AI you pick, so the price
        is here before you choose.</p>
      <div class="eng-list">${rows}</div>
      <div class="row" style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px;">
        <button class="btn ghost" id="vengCancel">Cancel</button>
        <button class="btn primary" id="vengGo">Make the clip</button>
      </div>`, { wide: true });
    let done = false;
    const finish = (v) => { if (done) return; done = true; closeModal(); resolve(v); };
    $("vengCancel").onclick = () => finish(null);
    $("vengGo").onclick = () => {
      const sel = document.querySelector('input[name="vengine"]:checked');
      finish(opts.find((o) => o.id === (sel || {}).value) || opts[0]);
    };
  });
}

/* Approve one post and make it ready — see _approve_post_ready in main.py.
   A photo post gets its picture drawn (and labelled "AI generated", which the
   IT Rules have required since February 2026) and is scheduled. A reel is approved and gets a task at the top of Home, and the
   step-by-step popup opens straight away because that is what they need next.
   `batch` keeps it quiet for Approve-all loops, which report once at the end. */
async function approvePostReady(postId, opts = {}) {
  const id = "post_" + postId;
  const card = (((state.lastState || {}).insights) || []).find((x) => x.id === id);
  const isReel = !!(card && card.kind === "reel");
  const run = () => api("/api/social/approve-ready", { method: "POST", json: { post_id: postId } });
  if (opts.batch) return run();

  /* WHY THIS NO LONGER WAITS.
     Drawing the picture is the slow part — an AI call on a small server — and
     the seller has nothing to add to it. They said yes. Holding them in front
     of a spinner until the drawing finishes is asking them to supervise work
     they already delegated.
     The card goes now. If the drawing fails, the card comes back saying so. */
  runInBackground(id, {
    label: isReel ? "Setting up the video task" : "Making the picture",
    run,
    onDone: (r) => {
      if (r.tasks) refreshTaskList(r.tasks);
      if (r.is_reel) {
        /* The one case worth interrupting for: a reel needs the seller to go
           and film or generate something, and the steps are the whole point.
           Offered, not forced — they may be halfway through approving six. */
        toastAction("Reel approved: it needs a clip.", "Open the steps", () => {
          if (r.task) openVideoTask(r.task.id, r.post);
        }, 7000);
      } else if (r.media_error) {
        /* Not a failure of the approval — the post IS approved — so the card
           does not come back. But the picture is missing and the seller must
           know, because the post cannot go out empty. */
        toast("Approved, but the picture could not be drawn: " + r.media_error
              + " It is on your task list.", 9000);
      } else if (r.image) {
        const lab = (r.image && r.image.ai_label) || {};
        toast("Picture made" + (lab.labelled ? ", labelled \u201cAI generated\u201d" : "")
              + ". Scheduled.");
      }
    },
  });
  return null;
}

/* The reel task, step by step: copy the prompt → open Google Flow → paste,
   generate and download → upload the clip here (the "AI generated" label goes
   on it on the way in) → save & schedule. Progress is saved on the task, so it reopens
   where the seller left off — on their phone too. */
async function openVideoTask(taskId, postHint) {
  const tasks = ((state.lastState || {}).tasks) || [];
  let task = tasks.find((t) => t.id === taskId);
  if (!task && postHint) task = { id: taskId, post_id: postHint.id, kind: "video", steps_done: [] };
  if (!task) { toast("That task is no longer open."); return; }
  let post;
  try { post = await api(`/api/social/post/${encodeURIComponent(task.post_id)}`); }
  catch (e) { toast(e.message); return; }
  // A photo task created because the month's pictures ran out carries the shot
  // to take (ai_prompt) and its own upload walkthrough — open that, the twin of
  // this reel one. A plain photo task (no engine, say) has no shot to copy, so
  // the post editor is the right place for it, as before.
  if (post.format !== "reel") {
    if ((task.ai_prompt || "").trim()) { openPhotoTask(post, task); }
    else { openSocialEditor(post); }
    return;
  }
  if (task.kind === "photo") { openSocialEditor(post); return; }

  if (!_vidTools) { try { _vidTools = await api("/api/studio/video-tools"); } catch (e) { _vidTools = null; } }
  const flow = ((_vidTools || {}).primary) || {};
  const flowUrl = flow.url || "https://labs.google/fx/tools/flow";
  const prompt = ((post.script || {}).ai_prompt || "").trim();
  const beats = (post.script || {}).beats || [];
  const done = new Set(task.steps_done || []);
  // A clip on the post means everything before it happened, whatever was
  // (or was not) ticked on the way.
  if (post.video_url) ["copy", "flow", "make", "upload"].forEach((x) => done.add(x));
  const photo = post.reference_photo || "";

  // Progress writes go one after another: two taps in quick succession would
  // otherwise race each other on the server and one tick would be lost.
  let chain = Promise.resolve();
  const mark = (step) => {
    if (done.has(step)) return chain;
    done.add(step);
    paintSteps();
    chain = chain.then(async () => {
      try {
        const r = await api("/api/smart/tasks", { method: "POST", json: { action: "progress", task_id: task.id, step } });
        refreshTaskList(r.tasks);
      } catch (e) { /* the popup still works; progress just is not saved */ }
    });
    return chain;
  };
  const copyPrompt = async () => {
    try { await navigator.clipboard.writeText(prompt); return true; }
    catch (e) {
      const rg = document.createRange(); rg.selectNodeContents($("vtPrompt"));
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rg);
      return false;
    }
  };

  openModal(`Make the reel: ${post.product_name || "your post"}`, `
    <p class="sm-hint" style="margin-top:0;">Goes out <b>${esc(shortWhen(post.scheduled_at))}</b>${post.occasion ? ` · ${esc(post.occasion)}` : ""}${(post.script || {}).style_label ? ` · <b>${esc(post.script.style_label)}</b>` : ""}.
      Five steps; each one ticks itself off as you go.</p>
    <ol class="vt-steps2" id="vtSteps">
      <li data-step="copy">
        <div class="vs-h"><i></i><b>Copy the video prompt</b></div>
        <div class="vs-b">
          <pre class="sm-prompt-body" id="vtPrompt">${esc(prompt || "No prompt yet: regenerate the script from the post editor.")}</pre>
          <button class="btn primary sm" id="vtCopy">${sic("layers")}Copy prompt</button>
        </div>
      </li>
      <li data-step="flow">
        <div class="vs-h"><i></i><b>Open Google Flow</b></div>
        <div class="vs-b">
          <p class="muted tiny" style="margin:0 0 8px;">Sign in, then in the prompt box choose <b>Video → Frames</b> and add
            ${photo ? `<a href="${esc(photo)}" target="_blank" rel="noopener" download>this product photo</a>` : "your product photo"}
            as the <b>start frame</b> (that keeps the product in the clip your real product. Set) <b>9:16</b> and <b>8 seconds</b>.</p>
          <a class="btn primary sm" id="vtFlow" href="${esc(flowUrl)}" target="_blank" rel="noopener">${sic("arrow-up-right")}Open Google Flow</a>
          ${flow.free ? `<span class="muted tiny" style="margin-left:8px;">${esc(flow.free)}</span>` : ""}
        </div>
      </li>
      <li data-step="make">
        <div class="vs-h"><i></i><b>Paste the prompt, generate, download the clip</b></div>
        <div class="vs-b">
          <p class="muted tiny" style="margin:0 0 8px;">Paste (Ctrl+V), press Generate, pick the take you like and download it as MP4.
            Flow puts its mark in a corner, leave it, we remove it when you upload.</p>
          <button class="btn ghost sm" id="vtMade">${sic("check")}I have the clip</button>
        </div>
      </li>
      <li data-step="upload" class="${post.video_url ? "open" : ""}">
        <div class="vs-h"><i></i><b>Upload the clip here</b></div>
        <div class="vs-b">
          <div class="sm-vid-slot" id="vtSlot">${post.video_url
            ? `<video src="${esc(post.video_url)}" controls playsinline preload="metadata"></video>`
            : `<div class="sm-vid-empty">${sic("play")}<b>No clip yet</b><span>MP4 or WEBM, up to 48MB.</span></div>`}</div>
          <div id="vtWm" class="muted tiny" style="margin:6px 0;">${post.video_url ? esc(clipNote({ ai_label: post.video_ai_label, watermark: post.video_watermark })) : ""}</div>
          ${wmFixRow("vtWmFix")}
          <button class="btn ${post.video_url ? "ghost" : "primary"} sm" id="vtPick">${sic("arrow-up-right")}${post.video_url ? "Replace clip" : "Choose the clip"}</button>
          <input type="file" id="vtFile" accept="video/mp4,video/webm,video/quicktime" hidden />
        </div>
      </li>
      <li data-step="schedule">
        <div class="vs-h"><i></i><b>Save &amp; schedule</b></div>
        <div class="vs-b">
          <label class="fld" style="margin:0 0 8px;"><span>Goes out</span>
            <input id="vtWhen" type="datetime-local" value="${esc(post.scheduled_at || "")}" /></label>
          <button class="btn approve" id="vtSchedule">Save &amp; schedule</button>
        </div>
      </li>
    </ol>
    ${beats.length ? `<details class="sm-vid-opt"><summary>Rather film it yourself? The shot list</summary>
      <div class="sm-script-rows">${beats.map((b) => `
        <div class="sm-beat-row" style="grid-template-columns:64px 1fr 1fr;">
          <input value="${esc(b.sec || "")}" readonly /><input value="${esc(b.shot || "")}" readonly />
          <input value="${esc(b.on_screen_text || "")}" readonly /></div>`).join("")}</div></details>` : ""}
    <div class="modal-actions">
      <button class="btn ghost" data-vtclose>Later</button>
      <button class="btn ghost" id="vtEditor">Open the post</button>
    </div>`, { wide: true });

  function paintSteps() {
    const order = ["copy", "flow", "make", "upload", "schedule"];
    const firstOpen = order.find((x) => !done.has(x));
    document.querySelectorAll("#vtSteps [data-step]").forEach((li) => {
      li.classList.toggle("done", done.has(li.dataset.step));
      li.classList.toggle("current", li.dataset.step === firstOpen);
    });
    const sch = $("vtSchedule");
    if (sch) sch.disabled = !done.has("upload");
  }
  paintSteps();
  // Any step can be reopened by tapping its title — copying the prompt again
  // is the usual reason, and a phone has no hover.
  document.querySelectorAll("#vtSteps .vs-h").forEach((h) => h.onclick = () =>
    h.parentElement.classList.toggle("open"));

  document.querySelector("[data-vtclose]").onclick = closeModal;
  $("vtEditor").onclick = () => { closeModal(); openSocialEditor(post); };
  $("vtCopy").onclick = async () => {
    const ok = await copyPrompt();
    $("vtCopy").innerHTML = sic("check") + (ok ? "Copied" : "Selected: press Ctrl+C");
    mark("copy");
  };
  // Copy again on the way out, so the paste on the other side always works.
  $("vtFlow").onclick = () => { copyPrompt(); mark("copy"); mark("flow"); };
  $("vtMade").onclick = () => mark("make");
  wireWmFix("vtWmFix", post);
  $("vtPick").onclick = () => $("vtFile").click();
  $("vtFile").onchange = async () => {
    const f = $("vtFile").files[0];
    if (!f) return;
    if (f.size > 48 * 1024 * 1024) {
      return toast("That clip is over 48MB. Export it at 1080p, a reel rarely needs more.", 7000);
    }
    try {
      await chain;                 // let any step tick land first
      var vtBar = progressBar($("vtSlot") && $("vtSlot").parentElement,
                              `Uploading ${Math.round(f.size / 1048576)}MB clip`);
      const fd = new FormData(); fd.append("files", f);
      const up = await apiUpload("/api/site/image", fd, (frac) => vtBar.set(frac));
      const u = up.url || up.image_url;
      if (!u) throw new Error("The upload did not come back with a file.");
      // This clip came out of Google Flow two steps ago, so it is AI made and
      // gets the label the law requires without asking the seller again.
      vtBar.working("Adding the \u201cAI generated\u201d label\u2026");
      const att = await attachClip(post.id, u, true);
      vtBar.done("Clip attached");
      post.video_url = att.video_url;
      $("vtSlot").innerHTML = `<video src="${esc(att.video_url)}" controls playsinline preload="metadata"></video>`;
      $("vtWm").textContent = clipNote(att);
      if ($("vtWmFix")) $("vtWmFix").hidden = false;
      $("vtPick").innerHTML = sic("arrow-up-right") + "Replace clip";
      $("vtPick").className = "btn ghost sm";
      ["copy", "flow", "make"].forEach((x) => done.add(x));
      done.add("upload");
      paintSteps();
      // stays open once there is a clip: it holds the clip, what the label step
      // did, and what to do if Flow's own mark is still on it. Painting the
      // steps moves "current" on to scheduling, which would fold them away
      const upStep = document.querySelector('#vtSteps li[data-step="upload"]');
      if (upStep) upStep.classList.add("open");
      if (att.tasks) refreshTaskList(att.tasks);
    } catch (e) {
      if (typeof vtBar !== "undefined" && vtBar) vtBar.fail(e.message);
      toast(e.message, 7000);
    }
    $("vtFile").value = "";
  };
  $("vtSchedule").onclick = async () => {
    try {
      await chain;
      const r = await api("/api/social/schedule-ready", { method: "POST",
        json: { post_id: post.id, scheduled_at: ($("vtWhen") || {}).value || "" } });
      if (r.tasks) refreshTaskList(r.tasks);
      closeModal();
      await afterPostChange();
      toast("Reel scheduled. Task done.");
    } catch (e) { toast(e.message, 6000); }
  };
}

/* Open the "add your own photo" flow for a post whose picture could not be made
   because the month's AI pictures are used up. Prefers the real task the server
   put on the list (it holds the shot prompt and remembers progress); if there
   is not one yet, it fetches the shot itself so the modal still has something to
   show. Called from the editor's generate button and after a monthly-cap 429. */
async function openPhotoUploadForPost(post) {
  let task = null, prompt = "";
  // An empty "add" is a no-op that just returns the current task list, so this
  // pulls the freshly-created upload task without a side effect.
  try {
    const r = await api("/api/smart/tasks", { method: "POST", json: { action: "add", text: "" } });
    if (r && r.tasks) {
      refreshTaskList(r.tasks);
      task = r.tasks.find((t) => t.post_id === post.id && !t.done && t.kind !== "video");
    }
  } catch (_) { /* fall back to a prompt-only modal below */ }
  prompt = (task && task.ai_prompt) || "";
  if (!prompt) {
    try {
      const d = await api("/api/studio/prompt-preview", { method: "POST", json: {
        product_id: post.product_id, pillar: post.pillar || "", format: post.format || "",
        post_id: post.id, use_reference: true, shot_type: post.shot_type || "" } });
      prompt = (d && d.prompt) || "";
    } catch (_) { prompt = ""; }
  }
  openPhotoTask(post, task || { post_id: post.id, kind: "photo", ai_prompt: prompt, steps_done: [] });
}

/* The photo-upload task, the twin of the reel one: copy the shot we would have
   drawn → take or make a photo → upload it here → save & schedule. It exists so
   that running out of the month's pictures is not a dead end — the seller still
   ships the post, with a real photo, and knows exactly what to shoot. Progress
   is saved on the task when it is a real one, so it reopens where they left
   off, on their phone too. */
async function openPhotoTask(post, task) {
  const prompt = ((task && task.ai_prompt) || "").trim();
  const done = new Set((task && task.steps_done) || []);
  // A photo already on the post means the earlier steps happened.
  if (post.image_url) ["copy", "shoot", "upload"].forEach((x) => done.add(x));
  const realTask = !!(task && task.id && (((state.lastState || {}).tasks) || [])
    .some((t) => t.id === task.id));

  let chain = Promise.resolve();
  const mark = (step) => {
    if (done.has(step)) return chain;
    done.add(step); paintSteps();
    if (realTask) chain = chain.then(async () => {
      try {
        const r = await api("/api/smart/tasks", { method: "POST",
          json: { action: "progress", task_id: task.id, step } });
        refreshTaskList(r.tasks);
      } catch (e) { /* the popup still works; progress just is not saved */ }
    });
    return chain;
  };
  const copyShot = async () => {
    try { await navigator.clipboard.writeText(prompt); return true; }
    catch (e) {
      const rg = document.createRange(); rg.selectNodeContents($("ptxPrompt"));
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rg);
      return false;
    }
  };

  openModal(`Add your own photo, ${post.product_name || "your post"}`, `
    <p class="sm-hint" style="margin-top:0;">You have used this month's AI pictures, so
      this one is a photo of your own, which for a real product usually looks better anyway.
      Goes out <b>${esc(shortWhen(post.scheduled_at))}</b>${post.occasion ? ` · ${esc(post.occasion)}` : ""}.
      Four steps; each ticks itself off as you go.</p>
    <ol class="vt-steps2" id="ptxSteps">
      <li data-step="copy">
        <div class="vs-h"><i></i><b>Copy the shot idea</b></div>
        <div class="vs-b">
          <p class="muted tiny" style="margin:0 0 8px;">This is the picture we would have
            made. Shoot something close to it, or paste it into any image tool you already use.</p>
          <pre class="sm-prompt-body" id="ptxPrompt">${esc(prompt || "A clean, well-lit photo of the product on a plain, uncluttered background.")}</pre>
          <button class="btn primary sm" id="ptxCopy">${sic("layers")}Copy shot idea</button>
        </div>
      </li>
      <li data-step="shoot">
        <div class="vs-h"><i></i><b>Take or make the photo</b></div>
        <div class="vs-b">
          <p class="muted tiny" style="margin:0;">Use your phone, natural light, a plain
            background. One clear photo of the real product is all this needs.</p>
          <button class="btn ghost sm" id="ptxShot" style="margin-top:8px;">${sic("check")}I have a photo</button>
        </div>
      </li>
      <li data-step="upload" class="${post.image_url ? "open" : ""}">
        <div class="vs-h"><i></i><b>Upload the photo here</b></div>
        <div class="vs-b">
          <div class="sm-vid-slot" id="ptxSlot">${post.image_url
            ? `<img src="${esc(post.image_url)}" alt="" style="max-width:100%;border-radius:8px;" />`
            : `<div class="sm-vid-empty">${sic("image")}<b>No photo yet</b><span>PNG or JPG.</span></div>`}</div>
          <button class="btn ${post.image_url ? "ghost" : "primary"} sm" id="ptxPick">${sic("arrow-up-right")}${post.image_url ? "Replace photo" : "Choose a photo"}</button>
        </div>
      </li>
      <li data-step="schedule">
        <div class="vs-h"><i></i><b>Save &amp; schedule</b></div>
        <div class="vs-b">
          <label class="fld" style="margin:0 0 8px;"><span>Goes out</span>
            <input id="ptxWhen" type="datetime-local" value="${esc(post.scheduled_at || "")}" /></label>
          <button class="btn approve" id="ptxSchedule">Save &amp; schedule</button>
        </div>
      </li>
    </ol>
    <div class="modal-actions">
      <button class="btn ghost" data-ptxclose>Later</button>
      <button class="btn ghost" id="ptxEditor">Open the post</button>
    </div>`, { wide: true });

  function paintSteps() {
    const order = ["copy", "shoot", "upload", "schedule"];
    const firstOpen = order.find((x) => !done.has(x));
    document.querySelectorAll("#ptxSteps [data-step]").forEach((li) => {
      li.classList.toggle("done", done.has(li.dataset.step));
      li.classList.toggle("current", li.dataset.step === firstOpen);
    });
    const sch = $("ptxSchedule");
    if (sch) sch.disabled = !done.has("upload");
  }
  paintSteps();
  document.querySelectorAll("#ptxSteps .vs-h").forEach((h) => h.onclick = () =>
    h.parentElement.classList.toggle("open"));

  document.querySelector("[data-ptxclose]").onclick = closeModal;
  $("ptxEditor").onclick = () => { closeModal(); openSocialEditor(post); };
  $("ptxCopy").onclick = async () => {
    const ok = await copyShot();
    $("ptxCopy").innerHTML = sic("check") + (ok ? "Copied" : "Selected: press Ctrl+C");
    mark("copy");
  };
  $("ptxShot").onclick = () => mark("shoot");
  $("ptxPick").onclick = () => pickImage(async (url) => {
    try {
      await api("/api/social/attach-image", { method: "POST", json: { post_id: post.id, url } });
      post.image_url = url;
      const slot = $("ptxSlot");
      if (slot) slot.innerHTML = `<img src="${esc(url)}" alt="" style="max-width:100%;border-radius:8px;" />`;
      const pick = $("ptxPick");
      if (pick) { pick.innerHTML = sic("arrow-up-right") + "Replace photo"; pick.className = "btn ghost sm"; }
      ["copy", "shoot"].forEach((x) => done.add(x));
      done.add("upload");
      paintSteps();
    } catch (e) { toast(e.message, 6000); }
  });
  $("ptxSchedule").onclick = async () => {
    try {
      await chain;
      const r = await api("/api/social/schedule-ready", { method: "POST",
        json: { post_id: post.id, scheduled_at: ($("ptxWhen") || {}).value || "" } });
      if (r.tasks) refreshTaskList(r.tasks);
      closeModal();
      await afterPostChange();
      toast("Photo added and post scheduled. Task done.");
    } catch (e) { toast(e.message, 6000); }
  };
}

/* What the planner found for one week, and what it did about it. */
async function openWeekBrief(card) {
  let b;
  try { b = await api(`/api/social/autoplan/brief?week=${encodeURIComponent(card.week || "")}`); }
  catch (e) { return toast(e.message); }
  const list = (rows, cls) => rows.length ? `<ul class="wk-list ${cls || ""}">${rows.join("")}</ul>` : `<p class="muted tiny">None.</p>`;
  const sig = { winner: "Selling well", struggling: "Needs a push", festival: "Festival", steady: "In rotation" };
  openModal(`Week of ${b.week_label || card.week}`, `
    <p class="sm-hint" style="margin-top:0;">${esc(b.note || "")}</p>
    <div class="wk-grid">
      <div><h4>What is happening that week</h4>
        ${list((b.opportunities || []).map((o) => `<li><b>${esc(o.name)}</b>, ${esc(o.text)}</li>`))}</div>
      <div><h4>Sales${b.sales_anchor ? ` <span class="muted tiny">(data to ${esc(b.sales_anchor)})</span>` : ""}</h4>
        ${b.sales_data ? "" : `<p class="muted tiny">No sales data yet, stock levels were used instead.</p>`}
        ${list([...(b.winners || []).map((w) => `<li class="win"><b>${esc(w.name)}</b> · ${esc(w.label)} – ${esc(w.why)}</li>`),
                ...(b.strugglers || []).map((w) => `<li class="slow"><b>${esc(w.name)}</b> · ${esc(w.label)} – ${esc(w.why)}</li>`)])}</div>
    </div>
    <h4 style="margin:14px 0 6px;">The posts (${b.added} added, ${b.existing} already planned, ${b.target} a week)</h4>
    ${list((b.posts || []).map((p) => `<li><b>${esc(shortWhen(p.scheduled_at))}</b> · ${esc(p.product_name)} · ${esc(p.format)}
        <span class="wk-sig ${esc(p.signal)}">${esc(sig[p.signal] || "")}</span><br><span class="muted tiny">${esc(p.plan_reason)}</span></li>`))}
    <div class="modal-actions">
      <button class="btn ghost" data-wkclose>Close</button>
      <button class="btn ghost" id="wkCal">Open the calendar</button>
      <button class="btn reject" id="wkCancel">Cancel all</button>
      <button class="btn approve" id="wkApprove">Approve all</button>
    </div>`, { wide: true });
  document.querySelector("[data-wkclose]").onclick = closeModal;
  $("wkCal").onclick = () => { closeModal(); openModule("social"); };
  $("wkCancel").onclick = () => { closeModal(); decide(card.id, "cancel"); };
  $("wkApprove").onclick = () => { closeModal(); approveWeek(card); };
}

/* What a reel needs the moment it is approved: the beats to film, and a prompt
   that can be pasted straight into a video AI. Shown here rather than buried
   in the editor because this is the moment the seller is thinking about it. */
function openReelPrompt(post, script) {
  const beats = script.beats || [];
  openModal(`Ready to film: ${esc((post && post.product_name) || "your reel")}`, `
    <p class="sm-hint" style="margin-top:0;">Scheduled. A reel is filmed, not
      drawn, so here is what to shoot. Film it yourself, or paste the prompt
      into a video AI, or let us make it, then the clip goes on this post.</p>

    ${beats.length ? `<div class="sm-script-rows">
      ${beats.map((b) => `
        <div class="sm-beat-row" style="grid-template-columns:64px 1fr 1fr;">
          <input value="${esc(b.sec || "")}" readonly />
          <input value="${esc(b.shot || "")}" readonly />
          <input value="${esc(b.on_screen_text || "")}" readonly />
        </div>`).join("")}
    </div>` : ""}

    ${script.ai_prompt ? `
      <div class="sm-prompt">
        <div class="sm-prompt-head">
          <div><b>Prompt for a video AI</b></div>
          <button class="btn ghost tiny" id="rpCopy">${sic("layers")}Copy</button>
        </div>
        <pre class="sm-prompt-body" id="rpBody">${esc(script.ai_prompt)}</pre>
      </div>` : ""}

    <div class="rp-next">
      <b>Three ways to get the clip. Pick one.</b>
      <ol>
        <li><b>Film it yourself</b> on your phone from the shots above. 15 to 30
          seconds. This usually beats anything an AI makes.</li>
        <li><b>Let Google Flow make it free</b> (we copy the prompt and open it
          for you. About five clips a day cost nothing there, and you see the
          result before you commit to anything.)</li>
        <li><b>Have us make it</b> if you would rather not leave. This one costs
          money per clip and you pay before you see it.</li>
      </ol>
      <p class="muted tiny" style="margin:8px 0 0;">Whichever you choose, the clip
        comes back here. Until one is on it, this reel will not go out.</p>
    </div>

    <div id="rpTools"></div>

    <div class="modal-actions">
      <button class="btn ghost" data-rpx>I will do it later</button>
      <button class="btn ghost" id="rpMake">Have us make it (paid)</button>
      <button class="btn primary" id="rpFlow">${sic("arrow-up-right")}Copy prompt &amp; open Google Flow</button>
      <button class="btn primary" id="rpUpload">${sic("arrow-up-right")}Upload the clip</button>
    </div>
    <input type="file" id="rpFile" accept="video/mp4,video/webm,video/quicktime" hidden />`,
    { wide: true });

  document.querySelector("[data-rpx]").onclick = closeModal;
  if ($("rpCopy")) $("rpCopy").onclick = async () => {
    const b = $("rpCopy"), was = b.innerHTML;
    try {
      await navigator.clipboard.writeText(script.ai_prompt || "");
      b.innerHTML = sic("check") + "Copied";
    } catch (e) {
      const rg = document.createRange();
      rg.selectNodeContents($("rpBody"));
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rg);
      b.innerHTML = sic("check") + "Selected: press Ctrl+C";
    }
    setTimeout(() => { b.innerHTML = was; }, 2500);
  };
  /* The clip is the ONE thing standing between this reel and going out, so the
     upload is a button here rather than a route into an editor the seller then
     has to read. Straight to the file picker. */
  const reopen = async () => {
    const fresh = (post && post.id) ? await api(`/api/social/post/${post.id}`).catch(() => post) : post;
    if (fresh) openSocialEditor(fresh);
  };
  $("rpUpload").onclick = () => $("rpFile").click();
  $("rpFile").onchange = async () => {
    const f = $("rpFile").files[0];
    if (!f) return;
    try {
      if (f.size > 48 * 1024 * 1024) {
        return toast("That clip is over 48MB. Export it at 1080p, a reel rarely "
                     + "needs more.", 7000);
      }
      var rpBar = progressBar(document.querySelector(".modal-body") || document.querySelector(".modal"),
                              `Uploading ${Math.round(f.size / 1048576)}MB clip`);
      const fd = new FormData(); fd.append("files", f);
      const up = await apiUpload("/api/site/image", fd, (frac) => rpBar.set(frac));
      const u = up.url || up.image_url;
      if (!u) throw new Error("The upload did not come back with a file.");
      rpBar.working("Adding the \u201cAI generated\u201d label\u2026");
      const att = await attachClip(post.id, u, true);
      rpBar.done("Clip attached");
      closeModal();
      if (_currentModule === "social") { _socialData = await api("/api/social"); await renderSocial(); }
      refreshApprovals(true);
      toast(`Clip attached. This reel is ready to go out.${clipNote(att) ? " " + clipNote(att) : ""}`, att.fallback ? 9000 : 5000);
    } catch (e) {
      if (typeof rpBar !== "undefined" && rpBar) rpBar.fail(e.message);
      toast(e.message, 7000);
    }
  };
  $("rpMake").onclick = async () => { closeModal(); await reopen(); };

  /* The Google Flow handoff.
     Flow publishes no URL parameter that pre-fills a prompt, and shipping an
     undocumented ?prompt= that silently does nothing would look broken. So the
     prompt goes to the clipboard at the moment of the click — one paste on the
     other side — and the steps that matter (Video → Frames → add YOUR photo as
     the start frame) are spelled out here, because that is the step that makes
     the clip show the seller's real product rather than a plausible invention. */
  $("rpFlow").onclick = async () => {
    const text = script.ai_prompt || "";
    let copied = false;
    try { await navigator.clipboard.writeText(text); copied = true; } catch (e) { copied = false; }
    await showVideoTools(text, copied);
  };
}

/* Today's remaining generations, rendered quietly next to the engine picker. */
let _aiLeft = null;
async function showAiLeft(force) {
  const box = $("smEngineNote");
  if (!box) return;
  try {
    if (!_aiLeft || force) _aiLeft = await api("/api/studio/ai-usage");
    // The monthly allowance is the one a seller actually meets (about one a day
    // against 30), so it is what we show here. The daily figure is a spend guard
    // they rarely touch, so it stays out of the way unless it is the tighter of
    // the two right now.
    const mon = _aiLeft.month || {};
    const img = (_aiLeft.kinds || {}).image || {};
    let tail = "";
    if (mon.enabled) tail = ` · ${mon.left} of ${mon.cap} pictures left this month`;
    else if (img.cap) tail = ` · ${img.left} of ${img.cap} pictures left today`;
    if (tail && !box.textContent.includes("pictures left")) box.textContent += tail;
  } catch (e) { /* a missing count is not worth an error */ }
}

/* The monthly picture allowance from the last /api/social load, so the warning
   before a generation and the "used up" check can read it without a round trip.
   Refreshed whenever Social is rendered and after every generation. */
function _imgQuota() {
  return (_socialData && _socialData.image_quota) || (_aiLeft && _aiLeft.month) || null;
}

const IMG_LOW_LEFT = 5;    // "you may run out" starts here

/* The live tracker at the top of the Social Media Manager: how many of the
   month's AI pictures are used, out of the cap, with a bar and a plain line
   about what happens when they run out (posts ask for your own photo). Hidden
   when no monthly limit is configured. No pills, no emoji — a labelled bar. */
function imageQuotaTracker(q) {
  if (!q || !q.enabled) return "";
  const cap = q.cap || 0;
  const used = q.used || 0;
  const left = q.left != null ? q.left : Math.max(0, cap - used);
  const pct = cap ? Math.min(100, Math.round((used / cap) * 100)) : 0;
  const spent = left <= 0, low = !spent && left <= IMG_LOW_LEFT;
  const fill = spent || low ? "var(--amber,#8b672b)" : "var(--green,#3d785f)";
  const line = spent
    ? `All ${cap} used. New posts now ask you to add your own photo, resets ${esc(q.resets || "on the 1st")}.`
    : low
      ? `${left} left. When they run out, posts ask you to upload your own photo instead.`
      : `Resets ${esc(q.resets || "on the 1st")}.`;
  return `
    <div class="muted tiny" id="smImgQuota" style="margin-top:8px;max-width:320px;">
      <div style="display:flex;align-items:center;gap:6px;">
        ${sic("image")}<b>Pictures this month</b>
        <span class="${spent || low ? "sm-warn2" : ""}" style="margin-left:auto;">${used} of ${cap} used</span>
      </div>
      <div style="height:6px;border-radius:3px;background:var(--border,#d7dae1);overflow:hidden;margin:5px 0 3px;">
        <div style="height:100%;width:${pct}%;background:${fill};transition:width .3s ease;"></div>
      </div>
      <div>${line}</div>
    </div>`;
}

/* Repaint just the tracker in place after a generation, so the count moves
   without waiting for the whole screen to re-render. */
function refreshImgQuota(q) {
  if (q && _socialData) _socialData.image_quota = q;
  const el = document.getElementById("smImgQuota");
  if (el) {
    const html = imageQuotaTracker(_imgQuota());
    if (html) el.outerHTML = html;
  }
}

let _vidTools = null;
async function showVideoTools(promptText, copied) {
  const box = $("rpTools");
  if (!_vidTools) {
    try { _vidTools = await api("/api/studio/video-tools"); }
    catch (e) { toast(e.message); return; }
  }
  const d = _vidTools;
  const card = (t) => `
    <div class="vt-card ${t.primary ? "on" : ""}">
      <div class="vt-head">
        <div><b>${esc(t.name)}</b>${t.primary ? ` <span class="vt-pick">start here</span>` : ""}
          <div class="muted tiny">${esc(t.best_for)}</div></div>
        <a class="btn ${t.primary ? "primary" : "ghost"} sm" target="_blank" rel="noopener"
           href="${esc(t.url)}">Open</a>
      </div>
      <div class="vt-free">${esc(t.free)}</div>
      ${t.primary ? `<ol class="vt-steps">${t.how.map((h) => `<li>${esc(h)}</li>`).join("")}</ol>` : ""}
      ${(t.watch_out || []).length ? `<details class="vt-warn"><summary>Things to know</summary>
        <ul>${t.watch_out.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></details>` : ""}
    </div>`;
  box.innerHTML = `
    <div class="vt-wrap">
      <div class="vt-top">
        ${copied
          ? `<b>${sic("check")}Prompt copied.</b> Open Google Flow below and paste it in.`
          : `<b>Copy the prompt first</b>, your browser blocked the automatic copy,
             so use the Copy button above, then open Flow.`}
      </div>
      ${d.tools.map(card).join("")}
      <p class="muted tiny" style="margin:10px 0 0;">${esc(d.note)}</p>
    </div>`;
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function decide(id, decision) {
  // Content-post insights have their own detail popup; the panel actions
  // still go through the normal approve/dismiss flow below except the
  // content case which we route to its dedicated poster.
  if (id && id.startsWith("content_") && decision === "approve") return saveContentToDevice(id);
  // Approving a planned post means "yes, and make it ready" — not just "set a
  // flag". It used to schedule a post with no picture on it, leaving the
  // seller to find that post again in the calendar, open it, generate the
  // image and save: three steps after they had already said yes.
  if (id && id.startsWith("post_") && decision === "approve") {
    return approvePostReady(id.slice(5));
  }
  // The weekly plan's header: Approve walks every post through the same
  // make-it-ready path, one at a time, with progress on screen.
  if (id && id.startsWith("autoplan_") && decision === "approve") {
    const card = (((state.lastState || {}).insights) || []).find((x) => x.id === id);
    if (card) return approveWeek(card);
  }
  if (id && id.startsWith("po_") && decision === "approve") return approvePo(id.slice(3));
  if (id && id.startsWith("po_") && decision === "cancel") {
    // The confirm stays: cancelling an order is not something to do by
    // accident. Everything after the seller says yes is background work.
    if (!confirm("Cancel this purchase order? Nothing has been sent to the supplier yet.")) return;
    runInBackground(id, {
      label: "Cancelling the order",
      run: () => api(`/api/smart/insight/${id}/decision`, { method: "POST", json: { decision: "cancel" } }),
      onDone: () => {
        if (_currentModule === "supply" || _currentModule === "inventory") openSupply();
        toast("Purchase order cancelled.");
      },
    });
    return;
  }
  // Cancel on a planned post, or on the whole week. Undecided posts only —
  // anything already approved keeps its decision.
  if (id && (id.startsWith("post_") || id.startsWith("autoplan_")) && decision === "cancel") {
    const whole = id.startsWith("autoplan_");
    if (whole && !confirm("Cancel every post in this week's plan that you have not approved yet?")) return;
    try {
      await api(`/api/smart/insight/${id}/decision`, { method: "POST", json: { decision: "cancel" } });
      await afterPostChange();
      if (whole) toast("Week's plan cancelled. Posts you already approved are untouched.");
      else toastUndo("Post cancelled: it will not go out.", async () => {
        await api("/api/social/state", { method: "POST", json: { post_id: id.slice(5), state: "draft" } });
        await afterPostChange();
      });
    } catch (e) { toast(e.message); }
    return;
  }
  /* Everything else: approve, dismiss, "not now". All of it goes through the
     queue, so the card leaves on the tap and the request happens behind it.
     A dismissal that fails is put back exactly like an approval that fails —
     the seller is never left believing they cleared something they did not. */
  const card = (((state.lastState || {}).insights) || []).find((x) => x.id === id);
  runInBackground(id, {
    label: decision === "approve" ? (card && card.cta ? card.cta : "Approving") : "Dismissing",
    run: () => api(`/api/smart/insight/${id}/decision`, { method: "POST", json: { decision } }),
    onDone: async (r) => {
      /* The server's view wins once it arrives, but only for the parts the
         queue is not still changing: replacing `insights` wholesale here would
         resurrect cards for jobs that are mid-flight. */
      if (state.lastState) {
        if (r.history) state.lastState.history = r.history;
        if (r.tasks) state.lastState.tasks = r.tasks;
      }
      if (r.tasks) refreshTaskList(r.tasks);
      if (decision === "approve" && r.download && r.download_url) {
        await download(r.download_url, `${id}.xlsx`);
        toast("Done, the Excel file is in your downloads.");
      }
      if (!$("historyDrawer").hidden) renderHistory();
    },
  });
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
      <div class="h-title">${ico(it.icon || "•")} <span>${esc(it.title)}</span></div>
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
  // A planned post's details ARE the post: caption, picture prompt, why this
  // product — all in the editor. The week header opens what the planner found.
  if (id && id.startsWith("post_")) return openSocialPostDetails(id.slice(5));
  if (id && id.startsWith("po_")) return openPoDetail(id.slice(3));
  if (id && id.startsWith("autoplan_")) {
    const card = (((state.lastState || {}).insights) || []).find((x) => x.id === id);
    if (card) return openWeekBrief(card);
  }
  /* The panel body is one line by design — it has to fit a narrow column.
     The manager's full reasoning lives here, so a seller who wants to know
     WHY before pressing the button can read it without the panel becoming a
     wall of text for everyone who does not. */
  const card = ((state.lastState || {}).insights || []).find((x) => x.id === id);
  if (card && card.why && card.why !== card.body) {
    openModal(card.manager_name || "Details", `
      <div class="det-why">
        <div class="det-h" style="--mgr:${esc(card.manager_colour || "#5c6790")}">
          ${sic(card.manager_icon || "spark")}<b>${esc(card.manager_name || "")}</b></div>
        <h4>${esc(card.headline || card.title || "")}</h4>
        <p>${esc(card.why)}</p>
      </div>
      <div class="modal-actions">
        <button class="btn ghost" data-detclose>Close</button>
        <button class="btn ghost" id="detOpen">Open the module</button>
        <button class="btn primary" id="detGo">${esc(card.cta || "Approve")}</button>
      </div>`);
    document.querySelector("[data-detclose]").onclick = closeModal;
    $("detOpen").onclick = () => { closeModal(); openDetailsModule(id); };
    $("detGo").onclick = () => { closeModal(); decide(id, "approve"); };
    return;
  }
  return openDetailsModule(id);
}

function openDetailsModule(id) {
  if (id === "reorder") return openModule("supply");
  if (id === "complaints") return openModule("complaints");
  if (id === "reputation") return openModule("review");
  // Win-back details opens the editable table popup (approve is a direct download now).
  if (id === "winback") return openWinbackEditor();
  if (id && id.startsWith("content_")) return openContentEditor(id);
  if (id && id.startsWith("post_")) return openSocialPostDetails(id.slice("post_".length));
  return openModule("sales");
}

// Reached from the Approval panel's "Details" button for a post more than
// 7 days out (inside the window it already gets a one-tap card there; this
// is the same editor the calendar opens, just fetched by id instead of found
// in an already-loaded month).
async function openSocialPostDetails(postId) {
  try {
    const p = await api(`/api/social/post/${encodeURIComponent(postId)}`);
    openSocialEditor(p);
  } catch (e) { toast(e.message); }
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
  // If we recognised the export outright, say so and stop asking. If we had to
  // guess Date or Amount from the numbers rather than the headers, say THAT —
  // a wrong guess presented confidently is how a seller ends up trusting a
  // dashboard built on the wrong two columns.
  const confirm = (d.suggested_mapping || {})._needs_confirmation || [];
  $("mapHint").textContent = d.kind === "review"
    ? "Which column holds the review text? (required). Rating and Date are optional but sharpen the analysis."
    : d.preset
      ? `This looks like a ${d.preset}. We have filled it in, have a quick look and press Continue.`
      : confirm.length
        ? "We could not tell which columns these are from their names, so please check the "
          + "highlighted ones against the preview below. Getting these two right is what "
          + "makes every number afterwards correct."
        : "Tell us which column is which. Date and Amount are required.";
  const labelFor = { date: "Date", amount: "Amount", customer_id: "Customer ID", customer_name: "Customer Name",
    order_id: "Order ID", product: "Product", category: "Category", subcategory: "Sub-category", quantity: "Quantity",
    review: "Review text", rating: "Rating" };
  const opts = (sel) => `<option value="">–</option>` + d.columns.map((c) => `<option ${c === sel ? "selected" : ""}>${esc(c)}</option>`).join("");
  $("mapGrid").innerHTML = d.roles.map((r) => `
    <label class="${confirm.includes(r) ? "map-check" : ""}">${labelFor[r] || r}${d.required.includes(r) ? " *" : ""}
      ${confirm.includes(r) ? `<span class="map-flag">please check</span>` : ""}
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
    if (res && res.mode === "append") toast(`Added ${fmt(res.added)} rows, ${fmt(res.rows)} total saved`);
    else toast("Data saved to your account");
    if (_afterUpload) { const f = _afterUpload; _afterUpload = null; f(); } else goHome();
  } catch (e) { const el = $("mapErr"); el.textContent = e.message; el.hidden = false; }
};
/* Clearing an uploaded dataset is the one thing here that cannot be undone —
   the rows are gone from the server. So this keeps the confirm, and says
   plainly what will not come back. */
async function clearData(kind) {
  const label = kind === "sales" ? "sales" : "review";
  if (!confirm(`Remove your uploaded ${label} data?\n\n`
    + `This one cannot be undone, you would need to upload the file again. `
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
  return `<tr>${_addCtx.columns.map(_addInputCell).join("")}<td><button class="btn ghost tiny" data-delrow title="Remove row" aria-label="Remove this row">${sic("close")}</button></td></tr>`;
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
    closeAdd(); toast(`Added ${fmt(res.added)} record(s), ${fmt(res.rows)} total`); goHome();
  } catch (e) { const el = $("addErr"); el.textContent = e.message; el.hidden = false; }
};

// ---------- module shell ----------
/* Which module is on screen, so Refresh knows what to re-open. Reloading the
   browser was the only way to pull fresh numbers, and a reload used to cost a
   login — so "refresh my data" and "sign in again" had become the same action. */
let _currentModule = null;


/* ---------------------------------------------------------------------
   Loading and failure states.

   Every module used to open with `<div class="ap-empty">Loading…</div>` —
   one small line of grey text in the middle of an empty page. On a slow
   connection that reads as a broken app rather than a loading one, which
   is exactly what "many things don't load, just a small box comes in"
   describes.

   A skeleton in the SHAPE of what is coming does two things a spinner
   cannot: it tells the seller the page is working, and it stops the
   layout jumping when the real content lands.
   --------------------------------------------------------------------- */
function skeleton(kind = "rows") {
  const bar = (w) => `<span class="sk-bar" style="width:${w}"></span>`;
  if (kind === "tiles") {
    return `<div class="sk sk-tiles">${Array.from({ length: 6 }, () =>
      `<div class="sk-tile">${bar("42%")}${bar("88%")}${bar("64%")}</div>`).join("")}</div>`;
  }
  if (kind === "cards") {
    return `<div class="sk sk-cards">${Array.from({ length: 4 }, () =>
      `<div class="sk-card"><span class="sk-thumb"></span>
        <div>${bar("64%")}${bar("90%")}${bar("40%")}</div></div>`).join("")}</div>`;
  }
  if (kind === "table") {
    return `<div class="sk sk-table">${Array.from({ length: 7 }, () =>
      `<div class="sk-row">${bar("22%")}${bar("34%")}${bar("18%")}${bar("14%")}</div>`).join("")}</div>`;
  }
  if (kind === "form") {
    return `<div class="sk sk-form">${Array.from({ length: 5 }, () =>
      `<div>${bar("28%")}<span class="sk-box"></span></div>`).join("")}</div>`;
  }
  return `<div class="sk">${Array.from({ length: 5 }, (_, i) =>
    `<div class="sk-row">${bar(`${90 - i * 9}%`)}</div>`).join("")}</div>`;
}

/* A failure the seller can act on, rather than a dead end.

   The old behaviour printed the raw exception into a card and stopped. On a
   cold server the message was a timeout string, which tells a seller nothing
   and offers them nothing. */
function failed(message, retry) {
  const id = "rt" + Math.random().toString(36).slice(2, 8);
  setTimeout(() => { const b = $(id); if (b && retry) b.onclick = retry; }, 0);
  const cold = /timeout|network|fetch|failed|502|503|504/i.test(message || "");
  return `
    <div class="load-fail">
      ${sic("alert")}
      <div>
        <b>${cold ? "That took too long" : "Could not load this"}</b>
        <p>${cold
          ? "The server may have been asleep. It wakes on the first request, so trying again usually works."
          : esc(message || "Something went wrong.")}</p>
        <button class="btn primary sm" id="${id}">${sic("refresh")}Try again</button>
      </div>
    </div>`;
}

/* Long jobs, with something moving on the screen.
   ------------------------------------------------------------------
   Planning a week writes a caption AND a shot list for every slot, each one a
   call to an AI provider. Generating a picture is a model round trip. On a
   free tier over a phone connection that is tens of seconds, and a toast that
   fades after four leaves the seller staring at a still screen with no idea
   whether it is working or wedged — so they press the button again, which
   starts the whole thing a second time.

   This puts a moving indicator on the screen for the whole job, says what is
   being done, and tells them plainly they can walk away and come back. It is
   deliberately NOT cancellable: the work continues on the server whatever the
   browser does, so offering a Cancel that only closes a dialog would be a lie.

   The dots animate via CSS, so nothing here depends on a timer that a
   backgrounded tab would freeze. */
let _busyDepth = 0;

function busyStart(title, detail) {
  _busyDepth += 1;
  let el = $("busyOverlay");
  if (!el) {
    el = document.createElement("div");
    el.id = "busyOverlay";
    el.className = "busy-back";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    document.body.appendChild(el);
  }
  el.innerHTML = `
    <div class="busy-box">
      <div class="busy-dots" aria-hidden="true"><i></i><i></i><i></i></div>
      <b id="busyTitle">${esc(title || "Working…")}</b>
      <p id="busyDetail">${esc(detail || "")}</p>
      <p class="busy-leave">Carry on using the app, this runs on the server, so
        it finishes whether you wait here or not.</p>
    </div>`;
  el.hidden = false;
  return el;
}

/* Update the line without restarting the animation — used when one job moves
   through stages ("writing captions" -> "writing shot lists"). */
function busyStep(detail) {
  const d = $("busyDetail");
  if (d) d.textContent = detail || "";
}

function busyEnd() {
  _busyDepth = Math.max(0, _busyDepth - 1);
  if (_busyDepth === 0) {
    const el = $("busyOverlay");
    if (el) el.hidden = true;
  }
}

/* Wrap any slow call. Guarantees the overlay is taken down on success, on
   failure and on an exception — a stuck overlay would be worse than none. */
async function withBusy(title, detail, fn) {
  busyStart(title, detail);
  try { return await fn(); }
  finally { busyEnd(); }
}

/* Not enough data yet, shown as the shape of what is coming.
   ------------------------------------------------------------------
   A bare "Not enough data." sentence tells a seller nothing about what they
   are working towards, and an empty screen reads as a broken module. This
   draws the LAYOUT they will get — KPI tiles, a trend line, category bars —
   blurred out, with the reason on top.

   The bars are deliberately drawn in CSS rather than shipped as an image: it
   theme-switches for free, needs no asset, and cannot be mistaken for real
   figures. Nothing in here carries a number, precisely so it can never be
   read as the seller's own data. */
/* Below this many rows, a trend line and a forecast are noise wearing the
   costume of an insight. Same spirit as the cancellations module's
   MIN_DENOMINATOR: say so plainly instead of drawing a confident chart of
   nothing. */
const THIN_DATA_ROWS = 30;

function thinData(rows, need, what, withKpis = true) {
  const bars = [38, 62, 45, 80, 55, 71, 48, 66, 90, 58, 74, 63];
  return `
    <div class="thin-wrap">
      <div class="thin-ghost" aria-hidden="true">
        ${withKpis ? `<div class="thin-kpis">${[0, 1, 2, 3].map(() => `
          <div class="thin-kpi"><i></i><b></b></div>`).join("")}</div>` : ""}
        <div class="thin-card">
          <div class="thin-line">
            <svg viewBox="0 0 300 90" preserveAspectRatio="none">
              <polyline points="0,70 30,58 60,63 90,42 120,48 150,30 180,36 210,20 240,26 270,12 300,16"
                fill="none" stroke="currentColor" stroke-width="3" />
            </svg>
          </div>
        </div>
        <div class="thin-card">
          <div class="thin-bars">${bars.map((h) => `<i style="height:${h}%"></i>`).join("")}</div>
        </div>
      </div>
      <div class="thin-over">
        ${sic("chart")}
        <b>Not enough data yet</b>
        <p>As we collect more data, ${esc(what)} will be visible here.</p>
        ${rows != null && need ? `
          <div class="thin-meter"><i style="width:${Math.max(4, Math.min(100, rows / need * 100))}%"></i></div>
          <p class="thin-count">${fmt(rows)} of about ${fmt(need)} orders needed for
             the trends to mean anything.</p>` : ""}
      </div>
    </div>`;
}

function moduleShell(name, bodyHtml) {
  setCrumb(name); showRail(false);
  setView(`
    <div class="page-head">
      <h2>${esc(name)}</h2>
      <div class="page-actions">
        <button class="btn ghost sm" id="refreshPage" title="Pull the latest numbers without reloading the page">
          ${sic("refresh")}Refresh</button>
        <button class="btn ghost sm" id="backHome">${sic("grid")}All apps</button>
      </div>
    </div>${bodyHtml}`);
  $("backHome").onclick = goHome;
  $("refreshPage").onclick = refreshCurrent;
}

/* Re-run whatever is on screen against fresh server data. Clears this account's
   cached computations first so Refresh means refresh, not "show me the cache
   again". */
async function refreshCurrent() {
  const btn = $("refreshPage");
  if (btn) { btn.disabled = true; btn.innerHTML = sic("refresh") + "Refreshing…"; }
  try {
    await api("/api/cache/clear", { method: "POST" });
  } catch (e) { /* the reopen below still fetches fresh */ }
  // Pressing Refresh means "I want to see the real numbers now", so the warm
  // copies are dropped rather than painted first. The reopen writes new ones.
  warmClear(); warmModClearAll();
  try {
    if (_currentModule) await openModule(_currentModule);
    else await goHome();
    toast("Up to date.");
  } catch (e) {
    toast(e.message || "Could not refresh just now.");
    if (btn) { btn.disabled = false; btn.innerHTML = sic("refresh") + "Refresh"; }
  }
}

/* ------------------------------------------------------------- the route ---
   THE PROBLEM: the app never told the browser where it was. Open Suppliers,
   pull to refresh on a phone (or let iOS discard the tab, or hit back), and
   you were on Home again — every time, from the top. The seller reads that as
   "it lost my place", and they are right.

   Now every module writes itself into the URL. Reload lands where you were,
   Back goes to Home instead of leaving the app, and the address bar says what
   screen you are on. `replaceState` is used when the hash already matches so
   re-opening the same module does not stack history entries a seller would
   have to press Back through twice. */
function routeTo(id) {
  const want = id ? `#/module/${id}` : "#/";
  if (location.hash === want) return;
  if (id) history.pushState({ mod: id }, "", want);
  else history.replaceState({ mod: null }, "", want);
}

async function openModule(id) {
  rememberScroll(_currentModule);
  _currentModule = id;
  routeTo(id);
  if (id === "sales") return openSales();
  if (id === "inventory") return openInventory();
  if (id === "studio") return openStudio();
  if (id === "subcategory") return openSubcategory();
  if (id === "products") return openProducts();
  if (id === "site") return openSite();
  if (id === "orders") return openOrders();
  if (id === "supply") return openSupply();
  if (id === "review") return openReview();
  if (id === "complaints") return openComplaints();
  if (id === "strategy") return openStrategy();
  if (id === "social") return openSocial();
  if (id === "marketing") return openMarketing();
  if (id === "gst") return openGst();
  if (id === "ads") return openAdsModule();
  // Reachable at #/module/instagram, and from the Social Media Manager. It has
  // no tile of its own on purpose: connecting Instagram is a step inside
  // planning posts, not a fifteenth app to choose between.
  if (id === "instagram") return openInstagramModule();
}

// ---------- MODULE: Product Management ----------
let _productsData = null;

async function openProducts() {
  await openCached("products", "Product Management",
    () => api("/api/products/state"), renderProducts);
}

function _prodCard(p) {
  const aliasChips = (p.aliases || []).length
    ? p.aliases.map((a) => `<span class="link-chip">${esc(a.alias)}${a.platform ? ` <i class="al-plat">${esc(a.platform)}</i>` : ""}
        <button class="lc-x" data-delalias="${a.id}" title="Unlink" aria-label="Unlink this name">${sic("close")}</button></span>`).join("")
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
          <div class="prod-thumb" style="${img ? `background-image:url('${esc(img)}')` : ""}">${img ? "" : ""}</div>
          <div>
            <b>${esc(p.name)}</b> ${p.status === "archived" ? `<span class="sup-badge moq">archived</span>` : ""}
            <div class="muted tiny">${meta || "–"}</div>
            <div class="muted tiny ${p.track_stock !== false && !(p.stock > 0) ? "stock-out" : ""}">${stock}</div>
          </div>
        </div>
        <div class="sup-actions">
          <button class="btn ghost tiny" data-editprod="${p.id}" title="Edit">${sic("edit")}<span class="btn-lbl">Edit</span></button>
          <button class="btn ghost tiny danger" data-delprod="${p.id}" title="Delete">${sic("close")}<span class="btn-lbl">Delete this product</span></button>
        </div>
      </div>
      <label class="site-toggle" title="Show this product on your own website">
        <input type="checkbox" data-listprod="${p.id}"${p.listed && p.status !== "archived" ? "checked" : ""} ${p.status === "archived" ? "disabled" : ""} />
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
      <div class="do"> ${unmatched.length} platform name${unmatched.length === 1 ? "" : "s"} in your sales not linked to a product</div>
      <div class="why">These names came from your sales platforms but aren't tied to any product yet, so their sales don't roll up. Link each to a product, or create it as a new one.</div>
    </div>
    <div class="link-list">
      ${unmatched.map((name) => `
        <div class="link-row">
          <div class="link-prod"><b>${esc(name)}</b> <span class="muted tiny">(from your sales)</span></div>
          <div class="link-add">
            ${prods.length ? `<select data-um-sel="${esc(name)}">${prodOpts}</select>
              <button class="btn ghost tiny" data-um-link="${esc(name)}"> Link to product</button>` : ""}
            <button class="btn ghost tiny" data-um-new="${esc(name)}">＋ New product</button>
          </div>
        </div>`).join("")}
    </div>` : "";

  const body = `
    <p class="muted">Manage the products you sell and link each to the names it carries on your sales platforms (Amazon, Shopify…). Sales for every linked name roll up to the product across the app, analytics, forecasts and the Supply module all follow it.</p>
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

/* Attach an uploaded clip to a post.
   `aiMade` is the seller's own answer to "was this made by an AI tool?". True
   for anything out of Google Flow, Veo or Kling, which is most reels, because
   that is where our own shot list sends them. When it is true we stamp the
   "AI generated" label on the clip, which Indian law has required of us since
   20 February 2026. When it is false the clip is stored exactly as filmed,
   because stamping real footage as AI would be its own kind of lie.
   If the labelling step cannot finish (the server is short of memory,
   restarting, or too slow) the clip is attached as uploaded rather than lost,
   and the seller is told the label did not go on. Returns the attach result
   plus `fallback`. */
async function attachClip(postId, url, aiMade) {
  const body = { post_id: postId, url };
  if (aiMade !== undefined) body.ai_generated = !!aiMade;
  try {
    return { ...(await api("/api/social/attach-video", { method: "POST", json: body })),
      fallback: false };
  } catch (e) {
    if (e.status && e.status < 500 && e.status !== 408) throw e;   // a real "no", e.g. post gone
    await nap(1500);            // give a restarting server a moment
    const r = await api("/api/social/attach-video", { method: "POST",
      json: { post_id: postId, url, ai_generated: false, clean: false } });
    return { ...r, fallback: true,
      ai_label: { labelled: false,
        reason: "The AI label could not be added this time, so the clip is attached as you uploaded it. Add the label in Instagram before you post." } };
  }
}

/* "Still see Flow's watermark?"
   This used to be four buttons that rubbed the other tool's mark out of the
   corner. It is now an instruction, because the IT Rules as amended on
   20 February 2026 forbid a platform that offers AI generation from letting an
   AI label be removed, and the price of breaking that is our safe harbour under
   section 79 of the IT Act. The seller still gets the clean frame they wanted,
   one step earlier and legitimately: Flow has a switch for its own mark.
   `slot` is the element holding the <video>, `note` the line that reports what
   happened. */
function wmFixRow(id) {
  return `<div class="wm-fix" id="${id}">
    <span class="muted tiny"><b>Still see Google Flow's mark on the clip?</b>
    Turn it off in Flow and generate again: open Flow, go to Settings, switch
    <b>Media Watermark</b> off. Free accounts have that switch. We cannot take
    another tool's mark off a clip here, because Indian law treats that as
    removing an AI label. Our own "AI generated" label still goes on, and that
    one is required.</span>
  </div>`;
}
/* Kept as a function so every caller keeps working. There is nothing to wire
   any more: the row is now text, shown only once a clip exists. */
function wireWmFix(id, post) {
  const row = $(id);
  if (!row) return;
  row.hidden = !post.video_url;
}

function clipNote(att) {
  const lab = (att && att.ai_label) || {};
  if (lab.labelled) {
    return "Labelled \u201cAI generated\u201d, as the law requires, and saved.";
  }
  if (lab.reason) return lab.reason.charAt(0).toUpperCase() + lab.reason.slice(1);
  const wm = (att && att.watermark) || {};
  if (wm.reason) return wm.reason.charAt(0).toUpperCase() + wm.reason.slice(1);
  return "Clip saved.";
}

/* ---- shared image picker: uploads to /api/site/image and returns the URL ----
   Every photo in the app goes through here — product shots, gallery images,
   the brand's own pictures — so the progress bar belongs here rather than at
   each of the dozen call sites. With several files it counts them off, because
   "3 of 8" is the number a seller waiting on a batch actually wants. */
function pickImage(onUrl, multiple, accept) {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = accept || "image/*"; inp.multiple = !!multiple;
  inp.onchange = async () => {
    const files = Array.from(inp.files || []);
    if (!files.length) return;
    const host = document.querySelector(".modal-back:not([hidden]) .modal-body")
      || document.querySelector(".modal-back:not([hidden]) .modal")
      || $("view");
    const bar = progressBar(host, files.length === 1
      ? "Uploading your picture"
      : `Uploading 1 of ${files.length}`);
    let warned = "", failed = 0, n = 0;
    for (const f of files) {
      n++;
      const fd = new FormData(); fd.append("files", f);
      try {
        const r = await apiUpload("/api/site/image", fd, (frac) => {
          // One bar across the batch: each file owns its slice of the width,
          // so it only ever moves forwards.
          bar.set(((n - 1) + (frac == null ? 0 : frac)) / files.length);
        });
        if (files.length > 1 && n < files.length) bar.working(`Uploading ${n + 1} of ${files.length}`);
        onUrl(r.image_url);
        if (r.warning) warned = r.warning;
      } catch (e) { failed++; toast(e.message, 6000); }
    }
    if (failed) { bar.fail(`${failed} of ${files.length} did not upload`); return; }
    bar.done(files.length === 1 ? "Uploaded" : `${files.length} uploaded`);
    // Say plainly when the durable copy did not happen, rather than showing a
    // thumbnail that will be a broken slot after the next deploy.
    toast(warned || (_media && !_media.durable
      ? "Uploaded: but this server does not keep uploads. See the warning above."
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

/* Step-through forms: Back / Next, and the submit button only on the last
   step. The step titles stay on top as a progress line — a finished step can
   be revisited with a tap, but moving forward always passes the checks for
   the steps in between, so nobody reaches "Add" with a nameless product. */
function wizardify(root, { tabSel, panelSel, key, submitId, validate }) {
  const tabs = [...root.querySelectorAll(tabSel)];
  const panels = [...root.querySelectorAll(panelSel)];
  const keys = tabs.map((t) => t.dataset[key]);
  const submit = root.querySelector("#" + submitId);
  const foot = submit.parentElement;
  const back = document.createElement("button");
  back.type = "button"; back.className = "btn ghost"; back.textContent = "Back";
  const next = document.createElement("button");
  next.type = "button"; next.className = "btn primary";
  foot.insertBefore(back, submit); foot.insertBefore(next, submit);
  const count = document.createElement("span");
  count.className = "wz-count muted tiny";
  foot.insertBefore(count, foot.firstChild);
  const errEl = root.querySelector(".pf-foot .err");
  const err = (m) => { if (errEl) { errEl.textContent = m || ""; errEl.hidden = !m; } };
  let i = 0;
  const show = (n) => {
    i = Math.max(0, Math.min(keys.length - 1, n));
    tabs.forEach((t, k) => { t.classList.toggle("on", k === i); t.classList.toggle("done", k < i); });
    panels.forEach((pn) => pn.classList.toggle("on", pn.dataset[key] === keys[i]));
    back.hidden = i === 0;
    next.hidden = i === keys.length - 1;
    submit.hidden = i !== keys.length - 1;
    if (tabs[i + 1]) next.textContent = `Next: ${tabs[i + 1].textContent.trim()}`;
    count.textContent = `Step ${i + 1} of ${keys.length}`;
    const first = panels.find((pn) => pn.dataset[key] === keys[i]);
    if (first) { const f = first.querySelector("input:not([type=checkbox]), textarea, select"); if (f && n !== 0) f.focus({ preventScroll: true }); }
  };
  const passes = (upto) => {
    for (let j = 0; j < upto; j++) {
      const m = validate ? validate(j) : null;
      if (m) { err(m); show(j); return false; }
    }
    err(""); return true;
  };
  next.onclick = () => { if (passes(i + 1)) show(i + 1); };
  back.onclick = () => { err(""); show(i - 1); };
  tabs.forEach((t, k) => { t.onclick = () => { if (k <= i || passes(k)) show(k); }; });
  // Enter in a single-line field moves forward instead of submitting half a form
  root.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.tagName === "INPUT" && !next.hidden) { e.preventDefault(); next.click(); }
  });
  show(0);
  return { show, passes: () => passes(keys.length) };
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

  // Four short steps instead of one twenty-five-field wall. A seller adding
  // their first product should be able to finish the first panel and stop —
  // name, price, photo — and come back for sizes and site placement later.
  p.innerHTML = `
    <div class="card sup-form form-v pf">
      <div class="pf-head">
        <h4>${id ? "Edit product" : "Add product"}</h4>
        <p class="muted tiny">${id ? esc(it.name) : "Only the name and price are required, everything else can wait."}</p>
      </div>

      <div class="pf-tabs" role="tablist">
        <button type="button" class="pf-tab on" data-pf="basics">Basics</button>
        <button type="button" class="pf-tab" data-pf="media">Photos &amp; copy</button>
        <button type="button" class="pf-tab" data-pf="stock">Sizes &amp; stock</button>
        <button type="button" class="pf-tab" data-pf="site">On my site</button>
      </div>

      <div class="pf-panel on" data-pf="basics">
        <div class="sup-form-grid">
          <label>Product name <span class="req">required</span>
            <input id="pfName" value="${it ? esc(it.name) : esc(prefillName || "")}" placeholder="e.g. Midnight Oud 50ml" /></label>
          <label>Selling price ₹ <span class="req">required</span>
            <input id="pfPrice" type="number" min="0" step="any" value="${num("price")}" placeholder="1499" /></label>
          <label>Category <span class="muted tiny">groups it on your site, and tells the caption writer what this is</span>
            <input id="pfCat" value="${esc(v("category"))}" placeholder="${esc(state.productLabel || "e.g. Soy wax candles")}" list="pfCatList" />
            <datalist id="pfCatList">${[...new Set((_productsData.products || [])
              .map((x) => x.category).filter(Boolean))].map((c2) => `<option value="${esc(c2)}">`).join("")}</datalist></label>
          <label>MRP ₹ <span class="muted tiny">optional, shows a struck-through price and a discount badge</span>
            <input id="pfMrp" type="number" min="0" step="any" value="${num("mrp")}" placeholder="1999" /></label>
          <label>What it costs you ₹ <span class="muted tiny">never shown to shoppers, used for your margins</span>
            <input id="pfCost" type="number" min="0" step="any" value="${num("unit_cost")}" /></label>
          <label>Your SKU <span class="muted tiny">internal code, optional</span>
            <input id="pfSku" value="${esc(v("sku"))}" /></label>
          <label>Status<select id="pfStatus">
            <option value="active"${v("status", "active") === "active" ? "selected" : ""}>Active: on sale</option>
            <option value="archived"${v("status") === "archived" ? "selected" : ""}>Archived: hidden everywhere</option>
          </select></label>
        </div>
      </div>

      <div class="pf-panel" data-pf="media">
        ${mediaWarning()}
        ${v("image_url") ? "" : `<div class="nudge">${sic("image")}<div><b>Add a photo</b>
          A product without one is the single biggest reason a storefront looks unfinished.</div></div>`}
        <div class="ai-strip">
          <div>${sic("spark")}<b>Let the AI write it</b>
            <span class="muted tiny">Description and key points from the name, category, price and anything you add here, nothing invented.</span></div>
          <input id="pfAiNotes" placeholder="Optional: fabric, fit, who it's for, how it's made…" />
          <button type="button" class="btn primary sm" id="pfAiCopy">${sic("spark")}Write description &amp; key points</button>
        </div>
        <div class="sup-form-grid">
          ${imageField("pfImg", v("image_url"), "Main photo", "square images look best")}
          ${imageField("pfVid", v("video_url"), "Product clip", "plays when a shopper hovers the card", true)}
          <label>Description<textarea id="pfDesc" data-ai="product_description" data-ai-ctx="product" data-ai-label="Product description" rows="4" placeholder="What it is, what it's made of, why someone should buy it.">${esc(v("description"))}</textarea></label>
          <label>Key points <span class="muted tiny">one per line, shown as ticks on the product page</span>
            <textarea id="pfHl" data-ai="product_highlights" data-ai-ctx="product" data-ai-label="Key points" rows="3" placeholder="100% cotton&#10;Ships in 24 hours&#10;Free returns">${esc((v("highlights", []) || []).join("\n"))}</textarea></label>
          <label>Sold by <span class="muted tiny">piece / kg / box, optional</span>
            <input id="pfUnit" value="${esc(v("unit_label"))}" placeholder="piece" /></label>
        </div>
        <div class="sup-sub">More photos</div>
        <div class="gal-wrap" id="pfGal"></div>
      </div>

      <div class="pf-panel" data-pf="stock">
        <div class="sup-sub">Sizes &amp; colours</div>
        <p class="muted tiny" style="margin:-6px 0 10px;">A shirt in three sizes and two colours is
        six things to count, not one. Name the options and each combination becomes a real record
        with its own stock, its own code and, if you want, its own price.</p>
        <div id="pfVarBox"></div>

        <div class="sup-sub">Stock</div>
        <div class="sup-form-grid">
          <label class="inline-check"><input type="checkbox" id="pfTrack"${v("track_stock", true) === false ? "" : "checked"} />
            Track stock for this product <span class="muted tiny">(sells out at zero, and site orders deduct from it)</span></label>
          <label id="pfStockRow">Units available<input id="pfStock" type="number" min="0" step="1" value="${it && it.stock != null ? it.stock : 0}" /></label>
        </div>
      </div>

      <div class="pf-panel" data-pf="site">
        <label class="site-toggle big" title="Show this product on your website">
          <input type="checkbox" id="pfListed"${listed ? "checked" : ""} />
          <span class="tsw"></span>
          <span class="tlbl">List this product on my website<span class="muted tiny"> (on by default)</span></span>
        </label>

        <div class="place-note">Every listed product appears in <b>Shop</b>. These two decide whether
          it <em>also</em> gets a place higher up the home page, leave both off and the site picks
          for you.</div>
        <div class="place-grid">
          <label class="place">
            <input type="checkbox" id="pfFeatured"${v("featured") ? "checked" : ""} />
            <span class="place-b"><b>Featured rail</b>
              <span>The horizontal row near the top. Pick your best sellers.</span></span>
          </label>
          <label class="place">
            <input type="checkbox" id="pfSpotlight"${v("spotlight") ? "checked" : ""} />
            <span class="place-b"><b>Spotlight</b>
              <span>The big single-product block with its photo held still. One product only.</span></span>
          </label>
        </div>
      </div>

      <div class="pf-foot">
        <div class="err" id="pfErr" hidden></div>
        <div class="pf-foot-b">
          <button class="btn ghost" id="pfCancel">Cancel</button>
          <button class="btn primary" id="pfSave">${id ? "Save changes" : "Add product"}</button>
        </div>
      </div>
    </div>`;

  // Next / Back through the four steps; Add only on the last one.
  wizardify(p, { tabSel: ".pf-tab", panelSel: ".pf-panel", key: "pf", submitId: "pfSave",
    validate: (step) => {
      if (step !== 0) return null;
      if (!$("pfName").value.trim()) return "Give the product a name first.";
      if ($("pfPrice").value === "") return "Add the selling price, shoppers need to see one.";
      return null;
    } });
  $("pfAiCopy").onclick = async () => {
    const b = $("pfAiCopy");
    const product = {
      id: id || "", name: $("pfName").value.trim(), category: $("pfCat").value.trim(),
      price: $("pfPrice").value, mrp: $("pfMrp").value, unit_label: $("pfUnit").value.trim(),
      description: $("pfDesc").value.trim(),
      highlights: $("pfHl").value.split("\n").map((x) => x.trim()).filter(Boolean) };
    b.disabled = true; b.innerHTML = sic("spark") + "Writing…";
    try {
      const r = await api("/api/ai/product-copy", { method: "POST",
        json: { product, notes: $("pfAiNotes").value.trim() } });
      let out = r;
      const fb = await puterFallback(r);
      if (fb) { const j = _aiJson(fb.text); if (j && j.description) out = { ...j, ai: true, provider: "puter" }; }
      $("pfDesc").value = out.description || $("pfDesc").value;
      if ((out.highlights || []).length) $("pfHl").value = out.highlights.join("\n");
      ["pfDesc", "pfHl"].forEach((x) => $(x).dispatchEvent(new Event("input", { bubbles: true })));
      toast(out.ai ? "Written: read it over and change anything that is not quite right."
                   : "No AI connected, so this is a starting draft from your details. Edit freely.", 6000);
    } catch (e) { toast(e.message, 6000); }
    b.disabled = false; b.innerHTML = sic("spark") + "Write description &amp; key points";
  };
  p.querySelectorAll(".place input").forEach((cb) => {
    const paint = () => cb.closest(".place").classList.toggle("on", cb.checked);
    cb.onchange = paint; paint();
  });

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
      featured: $("pfFeatured").checked,
      spotlight: $("pfSpotlight").checked,
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
      <button type="button" class="btn ghost tiny" data-axrm="${i}" title="Remove this option" aria-label="Remove this option">
        ${sic("close")}</button>
    </div>`;

  if (!_pfAxes.length) {
    box.innerHTML = `<div class="vx-empty">
      <span>No options: this product is one thing with one stock count.</span>
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
            <td><input data-vsku="${i}" value="${esc(v.sku)}" placeholder="–" /></td>
            <td><input data-vprice="${i}" type="number" min="0" step="any" value="${v.price === "" ? "" : esc(String(v.price))}" placeholder="–" /></td>
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
        <button class="gal-x" data-galrm="${i}" title="Remove" aria-label="Remove this photo">${sic("close")}</button>
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

// ---------- MODULE: Product Studio ----------
/* The Content Creator makes a post from a topic and a product *type*, which
   produces a stock-looking picture of "a perfume" rather than of THEIR perfume.
   Studio starts from what the seller actually has — their photographs, their
   words — plus a brand profile filled in once, so twenty posts feel like one
   brand instead of twenty templates. */
let _studio = null;
let _studioProduct = null;

async function openStudio() {
  await openCached("studio", "Product Studio",
    () => api("/api/studio/state"),
    (d) => { _studio = d; renderStudio(); });
}

function renderStudio() {
  const d = _studio;
  const b = d.brand;
  const ready = d.brand_ready;

  const cards = (d.products || []).map((p) => {
    const c = p.completeness;
    const band = c.score >= 80 ? "hi" : c.score >= 40 ? "mid" : "lo";
    return `
      <button class="st-card" data-stp="${esc(p.id)}">
        <span class="st-thumb" style="${p.image_url ? `background-image:url('${esc(p.image_url)}')` : ""}">
          ${p.image_url ? "" : sic("image")}</span>
        <span class="st-body">
          <b>${esc(p.name)}</b>
          <span class="st-meta">${p.category ? esc(p.category) + " · " : ""}${c.done} of ${c.total} ready</span>
          <span class="st-meter band-${band}"><i style="width:${c.score}%"></i></span>
          <span class="st-next">${c.next ? "Next: " + esc(c.next.label) : "Everything's here"}</span>
        </span>
      </button>`;
  }).join("");

  moduleShell("Product Studio", `
    ${!ready ? `<div class="nudge">${sic("spark")}<div><b>Start with your brand</b>
      Two or three lines about what you make and who buys it. Everything Studio
      writes and every image it generates is built against this, it is the
      difference between posts that look like yours and posts that look like
      anyone's.</div></div>` : ""}

    <div class="card st-brand">
      <div class="pf-head" style="padding:0 0 12px;">
        <h4>Your brand</h4>
        <p class="muted tiny">Filled in once. Used by every post.</p>
      </div>
      <div class="sup-form-grid">
        <label>Brand name <span class="req">required</span>
          <input id="sbName" value="${esc(b.name)}" placeholder="Aureva" /></label>
        <label>What you make, and why <span class="req">required</span>
          <textarea id="sbAbout" data-ai="brand_about" data-ai-ctx="brand" data-ai-label="What you make and why" rows="3" placeholder="Small-batch perfumes, rested six months before bottling. Made in Bengaluru.">${esc(b.about)}</textarea></label>
        <label>Who buys it <span class="muted tiny">the person you picture</span>
          <textarea id="sbAud" data-ai="brand_audience" data-ai-ctx="brand" data-ai-label="Who buys it" rows="2" placeholder="People who wear one scent, not ten.">${esc(b.audience)}</textarea></label>
        <label>The look<select id="sbLook">${(d.looks || []).map((l) =>
          `<option value="${esc(l.id)}"${b.look === l.id ? "selected" : ""}>${esc(l.label)}</option>`).join("")}</select></label>
        <label>How you sound<select id="sbVoice">${(d.voices || []).map((v) =>
          `<option value="${esc(v.id)}"${b.voice === v.id ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select></label>
        <label>Your colours <span class="muted tiny">in words, generated images follow these</span>
          <input id="sbPal" data-ai="brand_palette" data-ai-ctx="brand" data-ai-label="Your colours" value="${esc(b.palette)}" placeholder="amber, deep brown, brass" /></label>
        <label>Never say <span class="muted tiny">words or looks to stay away from</span>
          <input id="sbAvoid" data-ai="brand_avoid" data-ai-ctx="brand" data-ai-label="Never say" value="${esc(b.avoid)}" placeholder="cheap, discount, sale" /></label>
        <label>Hashtags you always use<input id="sbTags" data-ai="hashtags" data-ai-ctx="brand" data-ai-label="Hashtags you always use" value="${esc(b.hashtags)}" placeholder="#madeinindia #smallbatch" /></label>
      </div>
      <button class="btn primary sm" id="sbSave">Save brand</button>
    </div>

    <!-- Design language.

         A seller can rarely write "soft north light, warm sand, generous
         negative space", but every one of them can point at five pictures
         and say "like this". This bucket takes the pointing and turns it
         into the words the image model needs. -->
    <div class="card dl-card">
      <div class="pf-head" style="padding:0 0 12px;">
        <h4>Your design language</h4>
        <p class="muted tiny">Pictures whose <em>look</em> you want, not your products.
          Your packaging, your shop, shots you admire, a mood board. Four is plenty.</p>
      </div>
      <div class="dl-refs" id="dlRefs"></div>
      <div class="dl-actions">
        <button class="btn ghost sm" id="dlAdd">${sic("image")}Add references</button>
        <button class="btn primary sm" id="dlRead">${sic("spark")}Read my aesthetic</button>
      </div>
      <div id="dlOut"></div>
    </div>

    ${!d.ai_ready ? `<p class="muted tiny" style="margin:12px 0 0;">No AI key is set on this
      server, so captions come from a template and image generation is off. Your own
      photos still work everywhere.</p>` : ""}

    <div class="section-title" style="margin-top:20px;">Your products
      <span class="muted tiny" style="font-weight:500;">(the fuller the material, the better the posts. Ordered by what's ready.)</span></div>
    ${cards ? `<div class="st-grid">${cards}</div>`
            : `<div class="ap-empty">No products yet. Add them in Product Management first.</div>`}
    <div id="stPanel"></div>
  `);

  $("sbSave").onclick = async () => {
    try {
      const r = await api("/api/studio/brand", { method: "POST", json: { patch: {
        name: $("sbName").value.trim(), about: $("sbAbout").value.trim(),
        audience: $("sbAud").value.trim(), look: $("sbLook").value,
        voice: $("sbVoice").value, palette: $("sbPal").value.trim(),
        avoid: $("sbAvoid").value.trim(), hashtags: $("sbTags").value.trim(),
      }}});
      _studio.brand = r.brand; _studio.brand_ready = !!(r.brand.name && r.brand.about);
      toast("Brand saved, every post from here on follows it.");
      renderStudio();
    } catch (e) { toast(e.message); }
  };
  renderDesignLanguage();
  document.querySelectorAll("[data-stp]").forEach((n) =>
    n.onclick = () => openStudioProduct(n.dataset.stp));
}

function renderDesignLanguage() {
  const b = (_studio && _studio.brand) || {};
  const refs = b.refs || [];
  const box = $("dlRefs");
  if (box) {
    box.innerHTML = refs.length ? refs.map((u) => `
      <div class="dl-ref" style="background-image:url('${esc(u)}')">
        <button class="dl-x" data-dlx="${esc(u)}" title="Remove" aria-label="Remove this download">✕</button>
      </div>`).join("")
      : `<div class="dl-blank">Nothing here yet. Add four pictures whose look you want to copy.</div>`;
    box.querySelectorAll("[data-dlx]").forEach((n) => n.onclick = async () => {
      try {
        const r = await api("/api/studio/design-language/remove",
                            { method: "POST", json: { url: n.dataset.dlx } });
        _studio.brand = r; renderDesignLanguage();
      } catch (e) { toast(e.message); }
    });
  }

  const out = $("dlOut");
  if (out) {
    out.innerHTML = b.aesthetic ? `
      <div class="dl-read">
        <div class="dl-read-h">${sic("check")}<b>What I see in your references</b>
          <span class="muted tiny">read from ${esc(String(b.aesthetic_from || 0))} image${b.aesthetic_from === 1 ? "" : "s"}</span></div>
        <p>${esc(b.aesthetic)}</p>
        <p class="muted tiny">Every image generated from here on is shot in this
          language instead of the preset look. Change the references and read again
          to change it.</p>
      </div>` : "";
  }

  const add = $("dlAdd");
  if (add) add.onclick = () => pickImage(async (url) => {
    try {
      const r = await api("/api/studio/design-language/add",
                          { method: "POST", json: { url } });
      _studio.brand = r; renderDesignLanguage();
    } catch (e) { toast(e.message); }
  }, true);

  const read = $("dlRead");
  if (read) read.onclick = async () => {
    read.disabled = true; read.innerHTML = sic("spark") + "Looking…";
    try {
      // Reads up to twelve references, one model call each, then writes the
      // brand signature over the top of them — the slowest thing in Studio.
      const r = await withBusy(
        "Reading your reference images…",
        "Looking at each picture on its own, then working out what they share.",
        () => api("/api/studio/design-language/read", { method: "POST" }));
      _studio.brand = r.brand;
      renderDesignLanguage();
      toast(`Read ${r.read} reference${r.read === 1 ? "" : "s"}.`);
    } catch (e) {
      toast(e.message, 6000);
      read.disabled = false; read.innerHTML = sic("spark") + "Read my aesthetic";
    }
  };
}

async function openStudioProduct(pid) {
  const panel = $("stPanel");
  panel.innerHTML = `<div class="ap-empty">Loading…</div>`;
  try { _studioProduct = await api(`/api/studio/product?product_id=${encodeURIComponent(pid)}`); }
  catch (e) { panel.innerHTML = `<div class="card">${esc(e.message)}</div>`; return; }
  renderStudioProduct();
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderStudioProduct() {
  const { product: p, material: m, completeness: c, angles: ang } = _studioProduct;
  const shots = (m.shots || []);
  const clips = (m.clips || []);

  $("stPanel").innerHTML = `
    <div class="card pf" style="margin-top:16px;">
      <div class="pf-head">
        <h4>${esc(p.name)}</h4>
        <p class="muted tiny">${c.next
          ? `${esc(c.next.want)} – ${esc(c.next.why)}`
          : "Everything's here. Make a post."}</p>
      </div>
      <div class="pf-tabs">
        <button type="button" class="pf-tab on" data-st="material">Material</button>
        <button type="button" class="pf-tab" data-st="make">Make a post</button>
      </div>

      <div class="pf-panel on" data-st="material">
        <div class="st-checks">${(c.checks || []).map((k) =>
          `<span class="st-check ${k.ok ? "on" : ""}">${k.ok ? sic("check") : sic("plus")}${esc(k.label)}</span>`).join("")}</div>

        <div class="sup-sub">Photos</div>
        <p class="muted tiny" style="margin:-6px 0 10px;">Three or more, from different angles.
          One photo makes one post; three makes a week of them.</p>
        <div class="gal-wrap" id="stShots"></div>
        <div class="st-seen">
          <button class="btn ghost sm" id="stReadShots">${sic("spark")}Read my photos</button>
          ${m.seen ? `<div class="st-seen-out">
            <b>What I see in this product</b>
            <p>${esc(m.seen)}</p>
            <span class="muted tiny">This goes into every image generated for this
              product, so the picture resembles the item you actually ship.</span>
          </div>` : `<span class="muted tiny">Turn your photos into a written
            description, so generated images look like <em>this</em> product rather
            than a generic one.</span>`}
        </div>

        <div class="sup-sub">Clips</div>
        <p class="muted tiny" style="margin:-6px 0 10px;">Even five seconds. Reels reach people
          your photos won't.</p>
        <div class="gal-wrap" id="stClips"></div>

        <div class="sup-sub">In your words</div>
        <div class="sup-form-grid">
          <label>The story behind it <span class="muted tiny">this is what captions are actually made of</span>
            <textarea id="stStory" data-ai="product_story" data-ai-ctx="studio-product" data-ai-label="The story behind it" rows="3" placeholder="Rested six months before it ever met a bottle.">${esc(m.story)}</textarea></label>
          <label>What it's made of<textarea id="stMat" data-ai="product_materials" data-ai-ctx="studio-product" data-ai-label="What it's made of" rows="2" placeholder="Oud, amber, a little smoke">${esc(m.materials)}</textarea></label>
          <label>What makes it different <span class="muted tiny">the line that makes someone stop scrolling</span>
            <textarea id="stDiff" data-ai="product_different" data-ai-ctx="studio-product" data-ai-label="What makes it different" rows="2" placeholder="No alcohol burn: it opens soft.">${esc(m.different)}</textarea></label>
          <label>Who it's for<input id="stWho" data-ai="product_for" data-ai-ctx="studio-product" data-ai-label="Who it's for" value="${esc(m.for_who)}" placeholder="Someone who wears one scent, not ten" /></label>
          <label>Where you'd wear or use it<input id="stOcc" data-ai="product_occasions" data-ai-ctx="studio-product" data-ai-label="Where you'd wear or use it" value="${esc(m.occasions)}" placeholder="Evenings, weddings, gifting" /></label>
        </div>
        <button class="btn primary sm" id="stSave">Save material</button>
      </div>

      <div class="pf-panel" data-st="make">
        <div class="sup-form-grid">
          <label>What should this post be about?<select id="stAngle">
            ${(ang || []).map((a) => `<option value="${esc(a.label)}">${esc(a.label)} – ${esc(a.why)}</option>`).join("")}
          </select></label>
        </div>
        <div class="st-make">
          <button class="btn primary sm" id="stMakeOwn">${sic("image")}Use my photo + write the caption</button>
          <button class="btn ghost sm" id="stMakeAi"${_studio.ai_ready ? "" : "disabled"}>
            ${sic("spark")}Generate an image too</button>
          <button class="btn ghost sm" id="stImageOnly">${sic("image")}Image only</button>
        </div>
        <p class="muted tiny" style="margin:10px 0 0;">${_studio.ai_ready
          ? "A generated image is built from your brand's look and colours, and is always labelled as generated, so you know which of your pictures is a real photograph."
          : "Image generation needs an AI key on the server. Your own photos work regardless."}</p>
        <div id="stOut"></div>
      </div>
    </div>`;

  $("stPanel").querySelectorAll(".pf-tab").forEach((n) => n.onclick = () => {
    $("stPanel").querySelectorAll(".pf-tab").forEach((x) => x.classList.toggle("on", x === n));
    $("stPanel").querySelectorAll(".pf-panel").forEach((x) =>
      x.classList.toggle("on", x.dataset.st === n.dataset.st));
  });

  const paintMedia = () => {
    $("stShots").innerHTML = shots.map((u, i) => `
      <div class="gal-item" style="background-image:url('${esc(u)}')">
        <button class="gal-x" data-shotrm="${i}" title="Remove" aria-label="Remove this shot">${sic("close")}</button>
      </div>`).join("") + `<button class="gal-add" id="stShotAdd">＋<span>Add photos</span></button>`;
    $("stClips").innerHTML = clips.map((u, i) => `
      <div class="gal-item is-vid"><video src="${esc(u)}" muted loop autoplay playsinline></video>
        <button class="gal-x" data-cliprm="${i}" title="Remove" aria-label="Remove this clip">${sic("close")}</button>
      </div>`).join("") + `<button class="gal-add" id="stClipAdd">＋<span>Add a clip</span></button>`;
    $("stShotAdd").onclick = () => pickImage((u) => { shots.push(u); paintMedia(); }, true, "image/*");
    $("stClipAdd").onclick = () => pickImage((u) => { clips.push(u); paintMedia(); }, false,
      "video/mp4,video/webm,video/quicktime");
    $("stPanel").querySelectorAll("[data-shotrm]").forEach((x) =>
      x.onclick = () => { shots.splice(+x.dataset.shotrm, 1); paintMedia(); });
    $("stPanel").querySelectorAll("[data-cliprm]").forEach((x) =>
      x.onclick = () => { clips.splice(+x.dataset.cliprm, 1); paintMedia(); });
  };
  paintMedia();

  $("stSave").onclick = async () => {
    try {
      _studioProduct = { ..._studioProduct, ...(await api("/api/studio/product", {
        method: "POST", json: { product_id: p.id, patch: {
          story: $("stStory").value, materials: $("stMat").value,
          different: $("stDiff").value, for_who: $("stWho").value,
          occasions: $("stOcc").value, shots, clips,
        }}})) };
      toast("Saved.");
      _studio = await api("/api/studio/state");
      renderStudioProduct();
    } catch (e) { toast(e.message); }
  };

  const make = async (withImage) => {
    const out = $("stOut");
    out.innerHTML = `<div class="ap-empty">${withImage
      ? "Writing the caption and generating an image, this takes a few seconds…"
      : "Writing the caption…"}</div>`;
    try {
      const post = await api("/api/studio/post", { method: "POST", json: {
        product_id: p.id, angle: $("stAngle").value, generate_image: withImage } });
      renderStudioPost(post);
    } catch (e) { out.innerHTML = `<div class="card">${esc(e.message)}</div>`; }
  };
  $("stMakeOwn").onclick = () => make(false);
  const ai = $("stMakeAi"); if (ai && !ai.disabled) ai.onclick = () => make(true);

  /* Read the product's own photographs into words.

     This is the step that decides whether a generated image resembles the
     actual item or a plausible invention of it. Without it the model is told
     "a silk lehenga" and draws one; with it the model is told the maroon, the
     zari butis and the scalloped hem, and draws that. */
  const rs = $("stReadShots");
  if (rs) rs.onclick = async () => {
    if (!shots.length) return toast("Add a photo of the product first.");
    rs.disabled = true; rs.innerHTML = sic("spark") + "Looking…";
    try {
      const r = await withBusy(
        "Reading this product's photos…",
        "Describing what the item actually is, so generated pictures match it.",
        () => api("/api/studio/read-shots", { method: "POST",
          json: { product_id: p.id } }));
      _studioProduct.material.seen = r.seen;
      renderStudioProduct();
      toast(`Read ${r.read} photo${r.read === 1 ? "" : "s"}.`);
    } catch (e) {
      toast(e.message, 6000);
      rs.disabled = false; rs.innerHTML = sic("spark") + "Read my photos";
    }
  };

  const io = $("stImageOnly");
  if (io) io.onclick = async () => {
    io.disabled = true; io.innerHTML = sic("image") + "Drawing…";
    try {
      const img = await api("/api/studio/image", { method: "POST",
        json: { product_id: p.id, angle: $("stAngle").value } });
      $("stOut").innerHTML = `
        <div class="card st-imgonly">
          <img src="${esc(img.url)}" alt="" />
          <div class="st-imgmeta">
            <b>Image only: no caption written.</b>
            <span class="muted tiny">${img.used_seen ? "Built from your photos" : "No photo reading yet"}
              · ${img.used_aesthetic ? "your design language" : "the preset look"}
              · ${esc(img.engine)}${img.free ? " (free)" : ""}</span>
            <details><summary class="muted tiny">The prompt used</summary>
              <p class="muted tiny">${esc(img.prompt)}</p></details>
          </div>
        </div>`;
    } catch (e) { toast(e.message, 6000); }
    io.disabled = false; io.innerHTML = sic("image") + "Image only";
  };
}

function renderStudioPost(post) {
  const tags = (post.hashtags || []).map((h) => "#" + h).join(" ");
  const full = post.caption + (tags ? "\n\n" + tags : "");
  $("stOut").innerHTML = `
    <div class="st-post">
      <div class="st-post-img" style="${post.image_url ? `background-image:url('${esc(post.image_url)}')` : ""}">
        ${post.image_url ? "" : `<span class="muted tiny">No photo yet</span>`}
        ${post.image_is_generated ? `<span class="st-gen">${sic("spark")}Generated</span>` : ""}
      </div>
      <div class="st-post-b">
        ${post.image_error ? `<div class="media-warn">${sic("shield")}<div><b>Image not generated</b>
          <span>${esc(post.image_error)}</span></div></div>` : ""}
        ${post.note ? `<p class="muted tiny" style="margin:0 0 8px;">${esc(post.note)}</p>` : ""}
        <textarea id="stCaption" data-ai="caption" data-ai-ctx="studio-product" data-ai-label="Caption" rows="7">${esc(full)}</textarea>
        ${post.first_comment ? `<p class="muted tiny" style="margin:8px 0 0;">
          First comment: ${esc(post.first_comment)}</p>` : ""}
        <div class="st-post-a">
          <button class="btn primary sm" id="stCopy">${sic("check")}Copy caption</button>
          ${post.image_url ? `<button class="btn ghost sm" id="stDl">${sic("image")}Download image</button>` : ""}
          <button class="btn ghost sm" id="stAgain">${sic("refresh")}Write another</button>
        </div>
        ${post.image_is_generated ? `<p class="muted tiny" style="margin:10px 0 0;">
          This image was generated, not photographed. Say so if your followers would
          want to know.</p>` : ""}
      </div>
    </div>`;
  $("stCopy").onclick = async () => {
    try { await navigator.clipboard.writeText($("stCaption").value); toast("Caption copied."); }
    catch (e) { $("stCaption").select(); document.execCommand("copy"); toast("Caption copied."); }
  };
  const dl = $("stDl");
  if (dl) dl.onclick = () => download(post.image_url, `${post.product_name || "post"}.png`);
  $("stAgain").onclick = () => $("stMakeOwn").click();
}

// ---------- MODULES: Inventory Management / Suppliers ----------
/* One loader, two screens. Inventory owns what you hold, what each sold product
   uses up, and what gets wasted. Suppliers owns who you buy from, when to
   reorder and the purchase order. They used to be one module, which meant
   changing a supplier's phone number required opening every item they stock. */
let _supplyView = "inventory";

async function openInventory() { _supplyView = "inventory"; return openSupply(); }


let _supplyData = null;
let _afterUpload = null;   // set to a fn to run after the next Sales upload+map, instead of goHome
const _rupee = (v) => (v == null || v === "" ? "–" : "₹" + fmt(v));
const _eff = (v, auto) => (auto ? fmt(v) + "<span class=\"auto-tag\">auto</span>" : fmt(v));

async function openSupply() {
  if (_currentModule === "supply") _supplyView = "suppliers";
  // Two views share one endpoint but paint differently, so they cache apart —
  // otherwise opening Inventory would flash the Suppliers screen first.
  await openCached(`supply_${_supplyView}`, _supplyView === "inventory"
    ? "Inventory Management" : "Suppliers & Purchase Orders",
    () => api("/api/supply/state"), renderSupply);
}

function _supBadge(it) {
  if (it.on_order) return `<span class="sup-badge moq">● On order</span>`;
  if (it.dos == null) return `<span class="sup-badge">● No sales yet</span>`;
  return it.below_reorder
    ? `<span class="sup-badge low">● Order now</span>`
    : `<span class="sup-badge ok">● Fine</span>`;
}
const DOQ_BASIS = { eoq: "EOQ", moq: "MOQ", yours: "yours", cover: "cover" };

function _sugCard(it) {
  // Plain words only. A seller who has never heard "EOQ" or "reorder point"
  // still knows exactly what "you have 8 left", "you sell 3 a day" and "buy 60"
  // mean — and those are the same three numbers.
  const chips = [
    ["You have left", fmt(it.current_stock) + " " + esc(it.unit_label || "")],
    ["Used per day", it.avg_daily_consumption ?? 0],
    ["Lasts (DOS)", it.dos == null ? "–" : `${it.dos} days`],
    ["Need at least", `${it.dos_threshold} days`],
    ["Order (DOQ)", `<b>${fmt(it.doq)}</b> <span class="muted tiny">${DOQ_BASIS[it.doq_basis] || ""}</span>`],
    ["Will cost about", it.est_line_cost == null ? "–" : _rupee(it.est_line_cost)],
  ].map(([k, v]) => `<span class="sug-chip"><i>${k}</i>${v}</span>`).join("");
  const sup = it.supplier_name
    ? `${esc(it.supplier_name)}${it.supplier_phone ? " · " + esc(it.supplier_phone) : ""}${it.supplier_email ? " · " + esc(it.supplier_email) : ""}`
    : `No supplier linked`;
  return `
    <div class="sug-card">
      <div class="sug-head">
        <div><b>${esc(it.name)}</b>${it.moq_applied ? ` <span class="sup-badge moq">raised to supplier minimum</span>` : ""}
          <div class="muted tiny">${sup}</div></div>
        ${it.on_order ? `<span class="sup-badge moq">On order</span>`
          : `<button class="btn approve sm" data-draftpo="${it.id}">Draft the purchase order</button>`}
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
  const suggestions = d.suggestions || [];
  const belowN = suggestions.length;
  const onOrderN = d.n_on_order || 0;
  const waste = d.waste || [];

  const rule = d.rule || { dos_multiple: 1.2, eoq_min_days: 30, window_days: 30 };
  const salesNote = meta.has_sales
    ? `Days of supply (DOS) = what you have ÷ what you use a day, read from the last ${meta.window_days || rule.window_days} days of ${meta.source === "supply_sales" ? "the past sales you uploaded here" : "your sales, website orders included"}${meta.data_to ? ` (to ${meta.data_to})` : ""}. Every order placed re-checks the materials it used, and when DOS falls below ${rule.dos_multiple} × the supplier's lead time we draft a purchase order at the DOQ for you to approve.`
    : `Once there are sales, website orders count, we work out how many days each raw material lasts, and draft a purchase order when that falls below ${rule.dos_multiple} × the supplier's lead time. Link each item to the products that use it so product sales turn into material usage.`;

  const sugSection = suggestions.length ? `
    <div class="section-title" style="margin-top:8px;">Time to buy more <span class="muted tiny">(${suggestions.length} item${suggestions.length === 1 ? "" : "s"} running low)</span></div>
    <div class="sug-grid">${suggestions.map(_sugCard).join("")}</div>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px;">
      <button class="btn approve sm" id="supGenPo">Draft purchase order${belowN === 1 ? "" : "s"} for ${belowN === 1 ? "this item" : `these ${belowN} items`}</button>
    </div>` : `
    <div class="action-card ok" style="margin:10px 0;"><div class="do">${onOrderN ? "Everything running low is already on order" : "Nothing is running low"}</div><div class="why">${onOrderN
      ? `${onOrderN} item${onOrderN === 1 ? " is" : "s are"} below the reorder line with a purchase order already out, see Purchase orders below. Anything else that gets close to running out will appear here.`
      : "You have enough of everything for now. When something gets close to running out it will appear here with a ready order form for that supplier."}</div></div>`;

  const rows = items.length ? items.map((it) => `
      <tr class="${it.below_reorder && !it.on_order ? "sup-below" : ""}">
        <td>${esc(it.name)}${(it.linked_products || []).length
            ? `<div class="muted tiny">in ${it.linked_products.map(esc).join(", ")}</div>`
            : `<div class="muted tiny warn-t">not linked to a product</div>`}</td>
        <td>${it.supplier_name ? esc(it.supplier_name) : "<span class='muted tiny'>–</span>"}
            ${it.supplier_email ? `<div class="muted tiny">${esc(it.supplier_email)}</div>` : it.supplier_name ? `<div class="muted tiny warn-t">no email</div>` : ""}</td>
        <td class="num">${fmt(it.current_stock)} <span class="muted tiny">${esc(it.unit_label || "")}</span></td>
        <td class="num">${it.avg_daily_consumption ?? 0}</td>
        <td class="num"><b>${it.dos == null ? "–" : it.dos}</b></td>
        <td class="num">${_eff(it.effective_lead_time_days, it.lead_is_auto)}</td>
        <td class="num">${it.dos_threshold}</td>
        <td class="num">${fmt(it.moq)}</td>
        <td class="num doq-cell">
          <input class="doq-in" type="number" min="0" step="any" data-doq="${it.id}" value="${it.doq_override ?? ""}"
                 placeholder="${fmt(it.doq)}" title="Type your own DOQ, or leave blank for the worked-out one" />
          <span class="muted tiny" title="${esc((it.eoq_missing || []).length ? "EOQ needs: " + it.eoq_missing.join(", ") : "")}">${DOQ_BASIS[it.doq_basis] || ""}${it.eoq && it.doq_basis !== "eoq" ? ` · EOQ ${fmt(it.eoq)}` : ""}</span></td>
        <td>${_supBadge(it)}</td>
        <!-- WHY EVERY ONE OF THESE NOW CARRIES A WORD.
             These were four icon-only buttons explained by title tooltips.
             A tooltip needs a hover and a phone has no hover, so on a phone
             the card ended in four identical full-width empty boxes with a
             tiny mark in the middle of each, one of which deletes the item.
             The label is hidden again above tablet width, so the desktop row
             keeps its compact icons. -->
        <td class="sup-actions">
          ${it.suggestions_available ? `<button class="btn ghost tiny" data-apply="${it.id}" title="Apply the values suggested from your sales">${sic("check")}<span class="btn-lbl">Use the suggested numbers</span></button>` : ""}
          <button class="btn ghost tiny" data-edit="${it.id}" title="Edit">${sic("edit")}<span class="btn-lbl">Edit</span></button>
          <button class="btn ghost tiny" data-waste="${it.id}" title="Record waste">${sic("droplet")}<span class="btn-lbl">Record waste</span></button>
          <button class="btn ghost tiny sup-more" data-more="${it.id}">${sic("chevron-down")}<span class="btn-lbl">The numbers, and what you can do</span></button>
          <button class="btn ghost tiny danger" data-del="${it.id}" title="Remove item">${sic("close")}<span class="btn-lbl">Remove from stock list</span></button>
        </td>
      </tr>`).join("")
    : `<tr><td colspan="11" class="ap-empty">No inventory yet. Add an item in Inventory Management.</td></tr>`;

  // Every purchase order, one row each, gathered under where it has got to —
  // waiting on you, out with the supplier, arrived. A seller's question is
  // almost always "what is still open?", and a single list sorted by date
  // answered it only by reading every row.
  const flow = d.po_flow || { labels: {}, next: {} };
  const PO_STEP = { mailed: "Mailed", replied: "Replied", confirmed: "Confirmed",
                    received: "Received", cancelled: "Cancel" };
  const PO_STEP_WHY = { mailed: "I sent this myself", replied: "The supplier has written back",
                        confirmed: "The supplier has accepted the order",
                        received: "It arrived: put the quantities back into stock" };
  const poActions = (p) => {
    const st = p.status || "open";
    const nexts = (flow.next || {})[st] || [];
    const send = st === "draft" || st === "open";
    return `
      ${send ? `<button class="btn approve tiny" data-posend="${esc(p.po_number)}" title="Emails the PO to the supplier with the PDF attached">${sic("mail")}${st === "draft" ? "Approve &amp; send" : "Send again"}</button>` : ""}
      <button class="btn ghost tiny" data-podetail="${esc(p.po_number)}">Details</button>
      ${nexts.filter((x) => x !== "cancelled" && !(send && x === "mailed")).map((x) =>
        `<button class="btn ghost tiny" data-pomove="${esc(p.po_number)}" data-postatus="${x}"
                 title="${esc(PO_STEP_WHY[x] || "")}">${PO_STEP[x] || x}</button>`).join("")}
      <button class="btn ghost tiny sup-more" data-more="${esc(p.po_number)}">${sic("chevron-down")}<span class="btn-lbl">More</span></button>
      <button class="btn ghost tiny" data-popdf="${esc(p.po_number)}" title="Download the PDF">${sic("receipt")}<span class="btn-lbl">PDF</span></button>
      <button class="btn ghost tiny" data-poxls="${esc(p.po_number)}" title="Download as Excel">⬇<span class="btn-lbl">Excel</span></button>
      ${nexts.includes("cancelled") ? `<button class="btn ghost tiny danger" data-pomove="${esc(p.po_number)}" data-postatus="cancelled" title="Cancel this order">${sic("close")}<span class="btn-lbl">Cancel this order</span></button>` : ""}`;
  };
  const poRow = (p) => `
      <tr>
        <td>${esc(p.po_number)}${p.source === "auto" ? ` <span class="muted tiny">auto</span>` : ""}</td>
        <td>${esc(((p.supplier || {}).name) || (p.suppliers || []).join(", ") || "–")}</td>
        <td>${esc(String(p.created_at || "").slice(0, 16).replace("T", " "))}</td>
        <td><span class="po-st st-${esc(p.status || "open")}">${esc((flow.labels || {})[p.status] || p.status || "open")}</span></td>
        <td class="num">${fmt(p.n_items)}</td>
        <td class="num">${fmt(p.total_qty)}</td>
        <td class="num">${p.total_amount == null ? "–" : _rupee(p.total_amount)}</td>
        <td class="sup-actions">${poActions(p)}</td>
      </tr>`;
  const PO_GROUPS = [
    ["draft", "Waiting for you"], ["open", "Approved: not sent"], ["mailed", "With the supplier"],
    ["replied", "They have replied"], ["confirmed", "Confirmed, on the way"],
    ["received", "Received"], ["cancelled", "Cancelled"],
  ];
  const byStatus = {};
  pos.slice().reverse().forEach((p) => (byStatus[p.status || "open"] ||= []).push(p));
  const poRows = pos.length
    ? PO_GROUPS.filter(([k]) => (byStatus[k] || []).length).map(([k, label]) => `
        <tr class="po-grp"><td colspan="8">${esc(label)}
          <span class="muted tiny">${byStatus[k].length}</span></td></tr>
        ${byStatus[k].map(poRow).join("")}`).join("")
    : `<tr><td colspan="8" class="ap-empty">No purchase orders yet. They are drafted automatically when an order leaves a raw material short.</td></tr>`;

  const wasteRows = waste.length ? waste.slice(0, 10).map((w) => `
      <tr>
        <td>${esc(String(w.ts || "").slice(0, 16).replace("T", " "))}</td>
        <td>${esc(w.item_name || "")}</td>
        <td class="num">${fmt(w.qty)}</td>
        <td>${esc(w.reason || "")}</td>
      </tr>`).join("") : "";

  const inv = _supplyView === "inventory";
  const head = inv ? `
    <p class="muted">What you hold, what each sold product uses up, and what gets
      wasted. Stock falls automatically as orders come in.</p>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 6px;">
      <button class="btn primary sm" id="supAdd">${sic("plus")}Add item</button>
      <button class="btn ghost sm" id="supCheck">${sic("refresh")}Check stock now</button>
      <button class="btn ghost sm" id="supImport">${sic("arrow-right")}Pull items from my sales</button>
      <button class="btn ghost sm" id="supLinks">${sic("layers")}What each product uses</button>
      <button class="btn ghost sm" id="supWaste">${sic("close")}Record waste</button>
    </div>
    <!-- Four sentences of arithmetic, above the list, every single visit.
         It is true and it is worth having, but it answers a question a seller
         asks once, "where does 'days left' come from?", and then never
         again, while costing a third of a phone screen before the first item
         appears. Folded, with the question as the summary. -->
    <details class="fold quiet">
      <summary>How "days left" is worked out</summary>
      <p class="muted tiny" style="margin:8px 0 0;">${esc(salesNote)}</p>
    </details>

    <div id="supForm" hidden></div>
    <div id="supPanel" hidden></div>

    <div class="section-title" style="margin-top:18px;">What you hold</div>` : `
    <!-- Folded here for the same reason it is folded on the Inventory screen:
         four sentences of arithmetic, above everything, on every single visit,
         answering a question a seller asks once. Measured at 147px: a fifth
         of a phone screen before the first useful pixel. -->
    <details class="fold quiet">
      <summary>How "days left" is worked out</summary>
      <p class="muted tiny" style="margin:8px 0 0;">${esc(salesNote)}</p>
    </details>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 6px;">
      <button class="btn ghost sm" id="supLoadSales" title="Upload &amp; map the past sales history used ONLY for these supply-chain calculations (separate from your main Sales Data)">${sic("receipt")}Upload previous sales</button>
      <button class="btn ghost sm" id="supCheck">${sic("refresh")}Check stock now</button>
      <button class="btn ghost sm" id="supSign">${sic("plus")}${(d.signature || {}).url ? "Replace signature" : "Add signature"}</button>
      ${(d.signature || {}).url ? `<img class="po-sign-pv" src="${esc(d.signature.url)}" alt="Your signature" />
        <button class="btn ghost tiny" id="supSignClear">Remove</button>` : ""}
      <button class="btn ${(d.mail_account || {}).connected ? "ghost" : "primary"} sm" id="supMail">${sic("mail")}${(d.mail_account || {}).connected ? "Sending from " + esc((d.mail_account || {}).address) : "Send orders from my email"}</button>
    </div>
    ${(d.mail_account || {}).connected
      ? ((d.mail_account || {}).error ? `<div class="action-card warn" style="margin:8px 0;">
          <div class="do">Your email stopped accepting the password</div>
          <div class="why">${esc(d.mail_account.error)}</div></div>` : "")
      : `<div class="action-card warn" style="margin:8px 0;">
      <div class="do">Purchase orders will not come from your address yet</div>
      <div class="why">Connect your own email and every order goes out from it, so your
        supplier recognises it and their reply lands in your inbox.${d.email_ready
          ? "Until then this server's mailbox sends them."
          : "Until then nothing can be emailed from here at all, Approve just gives you the PDF."}</div></div>`}

    <div id="supForm" hidden></div>
    <div id="supPanel" hidden></div>
    <div id="supSuppliers"></div>

    ${sugSection}

    <div class="section-title" style="margin-top:18px;">Every item, and when to reorder</div>`;
  const body = head + `
    <div class="table-scroll">
      <table class="sup-table">
        <thead><tr>
          <th>Item</th>
          <th data-card-label="Buy it from">Supplier</th>
          <th class="num" data-card-label="In stock">Left</th>
          <th class="num" data-card-hide data-card-label="Used each day">Used/day</th>
          <th class="num" data-card-label="Days left"
              title="Days of supply: what you have ÷ what you use a day">DOS</th>
          <th class="num" data-card-hide data-card-label="Delivery takes"
              title="Days the supplier takes to deliver">Lead time</th>
          <th class="num" data-card-hide data-card-label="Reorder at"
              title="Order when DOS falls below this: ${rule.dos_multiple} × lead time">Order below</th>
          <th class="num" data-card-hide data-card-label="Smallest order">MOQ</th>
          <th class="num" data-card-hide data-card-label="Order this many"
              title="Default order quantity: type your own to override">DOQ</th>
          <th data-card-first>Status</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>

    ${inv ? "" : `<div class="section-title" style="margin-top:20px;">Purchase orders</div>
    <div class="table-scroll">
      <table class="sup-table">
        <!-- Seven fields per order, and on a phone each one is a full-width
             line: the purchase-order list measured 1,521px. What a seller
             scanning this list wants is which supplier, what it is worth, and
             where it has got to. When it was raised and how many lines it has
             are on the order itself, one tap away under "More", along with
             every action beyond the primary one. -->
        <thead><tr>
          <th>PO #</th>
          <th data-card-label="Supplier">Supplier</th>
          <th data-card-hide data-card-label="Raised">Created</th>
          <th data-card-first>Status</th>
          <th class="num" data-card-hide data-card-label="Lines">Items</th>
          <th class="num" data-card-hide data-card-label="Total quantity">Qty</th>
          <th class="num" data-card-label="Worth">Amount</th>
          <th></th>
        </tr></thead>
        <tbody>${poRows}</tbody>
      </table>
    </div>`}

    ${inv && wasteRows ? `
    <div class="section-title" style="margin-top:20px;">Recent waste</div>
    <div class="table-scroll">
      <table class="sup-table">
        <thead><tr><th>When</th><th>Item</th><th class="num">Qty</th><th>Reason</th></tr></thead>
        <tbody>${wasteRows}</tbody>
      </table>
    </div>` : ""}`;

  moduleShell(_supplyView === "inventory"
    ? "Inventory Management" : "Suppliers & Purchase Orders", body);
  const on = (id, fn) => { const n = $(id); if (n) n.onclick = fn; };
  on("supAdd", () => openSupplyForm(null));
  on("supImport", supplyImport);
  on("supLoadSales", () => { _afterUpload = () => openSupply(); startUpload("supply_sales", "append"); });
  on("supLinks", openLinksPanel);
  on("supWaste", () => openWastePanel(null));
  if (!inv) renderSuppliers();
  // same path as an order being placed: one draft PO per supplier at the DOQ,
  // waiting in the Approval panel — then open the first so it can be sent now
  if ($("supGenPo")) $("supGenPo").onclick = async () => {
    try {
      const d = await withBusy("Drafting purchase orders…", "One per supplier, at each item's DOQ.",
        () => api("/api/supply/replenish/check", { method: "POST" }));
      _supAfter(d);
      const c = d.check || {}, made = [...(c.created || []), ...(c.appended || [])];
      if (!made.length) { toast("Everything short is already on order."); return; }
      if (made.length > 1) toast(`${made.length} purchase orders drafted, one per supplier. They are also in the Approval panel.`, 7000);
      openPoDetail(made[0]);
    } catch (e) { toast(e.message, 7000); }
  };
  document.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => openSupplyForm(b.dataset.edit));
  document.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => supplyDelete(b.dataset.del));
  document.querySelectorAll("[data-waste]").forEach((b) => b.onclick = () => openWastePanel(b.dataset.waste));
  document.querySelectorAll("[data-apply]").forEach((b) => b.onclick = () => supplyApplySuggested(b.dataset.apply));
  /* The card shows the five fields that answer "have I got enough, and who do
     I ring". Behind this one tap sit the other six numbers — the arithmetic
     those five came from — and the three tools for the item: edit it, record
     waste against it, take it off the list. Measured at 447px a card with all
     of that always open, which is 2,731px for six items and most of the
     screen. Someone checking stock between customers is not editing anything;
     charging them for the tools on every card was the wrong trade. */
  document.querySelectorAll("[data-more]").forEach((b) => b.onclick = () => {
    const tr = b.closest("tr");
    if (!tr) return;
    const open = tr.classList.toggle("show-all");
    const lbl = b.querySelector(".btn-lbl");
    if (lbl) lbl.textContent = open ? "Hide this" : "The numbers, and what you can do";
    b.classList.toggle("is-open", open);
  });
  document.querySelectorAll("[data-openpo]").forEach((b) => b.onclick = () => supplyOpenPo([b.dataset.openpo]));
  document.querySelectorAll("[data-draftpo]").forEach((b) => b.onclick = supplyCheckNow);
  document.querySelectorAll("[data-podetail]").forEach((b) => b.onclick = () => openPoDetail(b.dataset.podetail));
  document.querySelectorAll("[data-posend]").forEach((b) => b.onclick = () => approvePo(b.dataset.posend));
  document.querySelectorAll("[data-pomove]").forEach((b) => b.onclick = () => movePo(b.dataset.pomove, b.dataset.postatus));
  on("supCheck", supplyCheckNow);
  on("supSign", pickSignature);
  on("supMail", openMailAccount);
  on("supSignClear", () => saveSignature(""));
  document.querySelectorAll("[data-doq]").forEach((inp) => inp.onchange = async () => {
    const val = inp.value === "" ? null : parseFloat(inp.value);
    try {
      _supAfter(await api("/api/supply/doq", { method: "POST", json: { id: inp.dataset.doq, doq: val } }));
      toast(val ? "DOQ saved: used for every order of this item." : "Back to the worked-out DOQ.");
    } catch (e) { toast(e.message); }
  });
  document.querySelectorAll("[data-popdf]").forEach((b) => b.onclick = () => download(`/api/supply/po/${encodeURIComponent(b.dataset.popdf)}/pdf`, `${b.dataset.popdf}.pdf`));
  document.querySelectorAll("[data-poxls]").forEach((b) => b.onclick = () => download(`/api/supply/po/${encodeURIComponent(b.dataset.poxls)}/download`, `${b.dataset.poxls}.xlsx`));
}

/* Suppliers, derived from the items they stock — so a phone number is edited
   once instead of on every item. */
async function renderSuppliers() {
  const box = $("supSuppliers");
  if (!box) return;
  let rows = [];
  try { rows = (await api("/api/supply/suppliers")).suppliers || []; }
  catch (e) { box.innerHTML = `<div class="card">${esc(e.message)}</div>`; return; }

  box.innerHTML = `
    <div class="sup-head">
      <div class="section-title" style="margin:0;">Who you buy from</div>
      <button class="btn primary sm" id="poNew">${sic("plus")}Create purchase order</button>
    </div>
    ${rows.length ? `<div class="sup-grid">${rows.map((x) => `
      <div class="sup-card">
        <div class="sup-card-h">
          <b>${esc(x.name)}</b>
          <button class="btn ghost tiny" data-supedit="${esc(x.name)}">Edit</button>
        </div>
        <div class="sup-card-c">
          ${x.phone ? `<a href="https://wa.me/${esc(String(x.phone).replace(/\D/g, ""))}"
             target="_blank" rel="noopener">${sic("whatsapp")}${esc(x.phone)}</a>` : ""}
          ${x.email ? `<a href="mailto:${esc(x.email)}">${sic("mail")}${esc(x.email)}</a>` : ""}
          ${!x.phone && !x.email ? `<span class="muted tiny">No contact details yet</span>` : ""}
        </div>
        <div class="sup-card-f">
          <span>${fmt(x.item_count)} item${x.item_count === 1 ? "" : "s"}</span>
          <span>₹${fmt(x.stock_value)} in stock</span>
        </div>
        <div class="sup-card-i">${x.items.slice(0, 4).map((i) => esc(i.name)).join(" · ")}${
          x.items.length > 4 ? ` +${x.items.length - 4} more` : ""}</div>
      </div>`).join("")}</div>`
      : `<div class="ap-empty">No suppliers yet. Add one against any inventory item
           and they will appear here.</div>`}`;

  box.querySelectorAll("[data-supedit]").forEach((b) =>
    b.onclick = () => editSupplier(rows.find((r) => r.name === b.dataset.supedit)));
  const poBtn = $("poNew");
  if (poBtn) poBtn.onclick = () => openManualPo(rows);
}

function editSupplier(sup) {
  if (!sup) return;
  openModal(`Edit ${sup.name}`, `
    <p class="muted" style="margin-top:0;">Changes apply to all
      ${fmt(sup.item_count)} item${sup.item_count === 1 ? "" : "s"} you buy from them.</p>
    <label class="fld"><span>Name</span><input id="seName" value="${esc(sup.name)}" /></label>
    <label class="fld"><span>Phone</span><input id="sePhone" value="${esc(sup.phone)}" placeholder="+91 …" /></label>
    <label class="fld"><span>Email <em>purchase orders are sent here</em></span><input id="seEmail" type="email" value="${esc(sup.email)}" /></label>
    <label class="fld"><span>Lead time: days they take to deliver <em>applies to every item they supply</em></span>
      <input id="seLead" type="number" min="0" step="any" value="${sup.lead_time_days || ""}" placeholder="7" /></label>
    <div class="modal-actions">
      <button class="btn ghost" id="seDetach">Remove from all items</button>
      <button class="btn primary" id="seSave">Save</button>
    </div>`);
  $("seSave").onclick = async () => {
    try {
      await api("/api/supply/supplier", { method: "POST", json: { name: sup.name, patch: {
        name: $("seName").value.trim(), phone: $("sePhone").value.trim(),
        email: $("seEmail").value.trim(),
        lead_time_days: $("seLead").value === "" ? null : parseFloat($("seLead").value) } } });
      closeModal(); renderSuppliers(); toast("Supplier updated everywhere.");
    } catch (e) { toast(e.message); }
  };
  $("seDetach").onclick = async () => {
    closeModal();
    try {
      const r = await api("/api/supply/supplier/detach", { method: "POST", json: { name: sup.name } });
      renderSuppliers();
      // Undo works from the item ids, not the name — once the last item is
      // cleared there is no supplier left to look up.
      toastUndo(`${sup.name} removed from every item. Your stock is untouched.`, async () => {
        await api("/api/supply/supplier/attach", { method: "POST", json: {
          name: sup.name,
          patch: { item_ids: r.detached_item_ids || [], name: sup.name,
                   phone: sup.phone, email: sup.email } } });
        renderSuppliers();
      });
    } catch (e) { toast(e.message); }
  };
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
/* Three steps, Next / Back, Submit only at the end: the raw material and the
   product it goes into, who you buy it from, and how much to order. Add Item
   lives here in Inventory only — suppliers come from the items they supply. */
function openSupplyForm(id) {
  _closePanels();
  const it = id ? (_supplyData.inventory || []).find((x) => x.id === id) : null;
  const f = $("supForm");
  f.hidden = false;
  const v = (x, dflt = "") => (it && it[x] != null ? it[x] : dflt);
  const catalog = _supplyData.catalog || [];
  const sups = _supplyData.suppliers || [];
  const links = it ? (_supplyData.maps || []).filter((m) => m.inventory_id === it.id) : [];
  const rule = _supplyData.rule || { dos_multiple: 1.2, eoq_min_days: 30 };
  f.innerHTML = `
    <div class="card sup-form pf">
      <div class="pf-head">
        <h4>${id ? "Edit item" : "Add item"}</h4>
        <p class="muted tiny">${id ? esc(it.name)
          : "A raw material or packing item, what it goes into, who sells it to you, and how much to order."}</p>
      </div>

      <div class="pf-tabs" role="tablist">
        <button type="button" class="pf-tab on" data-sf="basics">The item</button>
        <button type="button" class="pf-tab" data-sf="supplier">Supplier</button>
        <button type="button" class="pf-tab" data-sf="reorder">How much to order</button>
      </div>

      <div class="pf-panel on" data-sf="basics">
        <div class="sup-form-grid">
          <label>Which product uses it? <span class="muted tiny">from Product Management</span>
            <select id="sfProd">
              <option value="">Not linked to a product yet</option>
              ${catalog.map((pr) => `<option value="${esc(pr.name)}">${esc(pr.name)}${pr.category ? ` · ${esc(pr.category)}` : ""}</option>`).join("")}
            </select></label>
          <label>How much one unit of that product uses <span class="muted tiny">e.g. 2.5 (metres per kurta)</span>
            <input id="sfQpu" type="number" min="0" step="any" value="1" /></label>
          <label>Item name <span class="req">required</span> <span class="muted tiny">picking a product fills this in, change it to what you call the material</span>
            <input id="sfName" value="${esc(v("name"))}" placeholder="e.g. Cotton fabric, 2m roll" /></label>
          <label>How much do you have now?
            <input id="sfStock" type="number" min="0" step="any" value="${v("current_stock", 0)}" /></label>
          <label>Measured in <span class="muted tiny">pieces, kg, metres, boxes…</span>
            <input id="sfUnit" value="${esc(v("unit_label", "unit"))}" placeholder="pcs" /></label>
          <label>Category <span class="muted tiny">optional</span>
            <input id="sfCat" value="${esc(v("category"))}" placeholder="Fabric" /></label>
          <label>What one costs you ₹ <span class="muted tiny">used for order values</span>
            <input id="sfCost" type="number" min="0" step="any" value="${it && it.unit_cost != null ? it.unit_cost : ""}" /></label>
        </div>
        ${links.length ? `<p class="muted tiny" style="margin:8px 0 0;">Already used in: ${links.map((m) =>
          `<b>${esc(m.product)}</b> × ${fmt(m.qty_per_unit)}`).join(", ")}. Picking a product above adds another.</p>` : ""}
      </div>

      <div class="pf-panel" data-sf="supplier">
        <p class="muted tiny" style="margin:0 0 12px;">Purchase orders for this item are emailed to this
          supplier, so the email matters most. Pick someone you already buy from to fill it in.</p>
        <div class="sup-form-grid">
          <label>Supplier name<input id="sfSupN" list="sfSupList" value="${esc(v("supplier_name"))}" placeholder="Sharma Textiles" />
            <datalist id="sfSupList">${sups.map((x) => `<option value="${esc(x.name)}">`).join("")}</datalist></label>
          <label>Email <span class="muted tiny">where purchase orders go</span>
            <input id="sfSupE" type="email" value="${esc(v("supplier_email"))}" placeholder="orders@supplier.com" /></label>
          <label>Phone<input id="sfSupP" value="${esc(v("supplier_phone"))}" placeholder="+91 …" inputmode="tel" /></label>
          <label>Lead time: days they take to deliver <span class="muted tiny">blank = we assume 7</span>
            <input id="sfLead" type="number" min="0" step="any" placeholder="7"
                   value="${it && it.lead_time_days > 0 ? it.lead_time_days : ''}" /></label>
          <label>Minimum order (MOQ) <span class="muted tiny">the smallest quantity they will sell, 0 if none</span>
            <input id="sfMoq" type="number" min="0" step="any" value="${v("moq", 0)}" /></label>
        </div>
      </div>

      <div class="pf-panel" data-sf="reorder">
        <div class="nudge">${sic("spark")}<div><b>How ordering works here</b>
          We order when the days your stock will last fall below ${rule.dos_multiple} × the lead time.
          Each order is for the DOQ (default order quantity): the supplier's minimum, until you
          add both costs below and there is a month of sales, then the cheapest quantity (EOQ), if it
          is more than the minimum. Or type your own.</div></div>
        <div class="sup-form-grid">
          <label>Cost of placing one order ₹ <span class="muted tiny">calls, transport, paperwork</span>
            <input id="sfOrder" type="number" min="0" step="any" placeholder="e.g. 300"
                   value="${it && it.ordering_cost != null ? it.ordering_cost : ""}" /></label>
          <label>Cost of holding one unit for a year ₹ <span class="muted tiny">storage, damage, money tied up</span>
            <input id="sfHold" type="number" min="0" step="any" placeholder="e.g. 12"
                   value="${it && it.holding_cost != null ? it.holding_cost : ""}" /></label>
          <label>Your own DOQ <span class="muted tiny">leave blank and we work it out${it && it.doq ? `, now ${fmt(it.doq)}` : ""}</span>
            <input id="sfQty" type="number" min="0" step="any" placeholder="we work it out"
                   value="${it && it.reorder_qty != null ? it.reorder_qty : ""}" /></label>
        </div>
      </div>

      <div class="pf-foot">
        <div class="err" id="sfErr" hidden></div>
        <div class="pf-foot-b">
          <button class="btn ghost" id="sfCancel">Cancel</button>
          <button class="btn primary" id="sfSave">${id ? "Save changes" : "Add item"}</button>
        </div>
      </div>
    </div>`;

  // Picking a product fills the name, which stays editable.
  const prod = $("sfProd");
  prod.onchange = () => {
    const nm = $("sfName");
    if (prod.value && (!nm.value.trim() || nm.dataset.auto === "1")) {
      nm.value = prod.value; nm.dataset.auto = "1";
    }
    nm.focus(); nm.select();
  };
  $("sfName").addEventListener("input", (e) => { e.target.dataset.auto = ""; });
  // An existing supplier fills in their details.
  $("sfSupN").addEventListener("change", () => {
    const x = sups.find((y) => y.name.toLowerCase() === $("sfSupN").value.trim().toLowerCase());
    if (!x) return;
    if (!$("sfSupE").value) $("sfSupE").value = x.email || "";
    if (!$("sfSupP").value) $("sfSupP").value = x.phone || "";
    if (!$("sfLead").value && x.lead_time_days) $("sfLead").value = x.lead_time_days;
  });

  wizardify(f, { tabSel: ".pf-tab", panelSel: ".pf-panel", key: "sf", submitId: "sfSave",
    validate: (step) => {
      if (step === 0 && !$("sfName").value.trim()) return "Give the item a name (or pick the product it goes into).";
      if (step === 0) {
        const nm = $("sfName").value.trim().toLowerCase();
        const twin = ((_supplyData || {}).inventory || []).find((x) => x.id !== id && String(x.name || "").trim().toLowerCase() === nm);
        if (twin) return `You already have "${twin.name}". Edit that one ( in the list), or, if another product uses it too, add it under "What each product uses" so its stock is counted once.`;
      }
      if (step === 0 && $("sfProd").value && !(parseFloat($("sfQpu").value) > 0)) return "How much of it does one unit of the product use? It has to be more than 0.";
      if (step === 1) {
        const e = $("sfSupE").value.trim();
        if (e && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) return "That email does not look right, purchase orders are sent to it.";
      }
      return null;
    } });

  f.scrollIntoView({ behavior: "smooth", block: "nearest" });
  $("sfCancel").onclick = () => { f.hidden = true; f.innerHTML = ""; };
  const numOrNull = (x) => ($(x).value === "" ? null : parseFloat($(x).value));
  $("sfSave").onclick = async () => {
    const payload = {
      id: id || null,
      name: $("sfName").value.trim(),
      category: $("sfCat").value.trim(),
      unit_label: $("sfUnit").value.trim() || "unit",
      current_stock: parseFloat($("sfStock").value) || 0,
      lead_time_days: numOrNull("sfLead"),
      safety_stock: it ? it.safety_stock : null,
      moq: parseFloat($("sfMoq").value) || 0,
      ordering_cost: numOrNull("sfOrder"),
      holding_cost: numOrNull("sfHold"),
      unit_cost: numOrNull("sfCost"),
      reorder_qty: numOrNull("sfQty"),
      supplier_name: $("sfSupN").value.trim(),
      supplier_phone: $("sfSupP").value.trim(),
      supplier_email: $("sfSupE").value.trim(),
      link_product: $("sfProd").value,
      qty_per_unit: numOrNull("sfQpu"),
    };
    if (!payload.name) { const e = $("sfErr"); e.textContent = "Item name is required."; e.hidden = false; return; }
    try { _supAfter(await api("/api/supply/item", { method: "POST", json: payload })); toast(id ? "Saved" : "Item added"); }
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
  try { _supAfter(await api("/api/supply/item", { method: "POST", json: payload })); toast("Suggested values applied, edit them anytime."); }
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
  const opts = items.map((it) => `<option value="${it.id}"${it.id === preId ? "selected" : ""}>${esc(it.name)} (${fmt(it.current_stock)} ${esc(it.unit_label || "")})</option>`).join("");
  p.innerHTML = `
    <div class="card sup-form">
      <h4 style="margin:0 0 4px;"> Record waste</h4>
      <p class="muted tiny">Logs the loss and reduces stock, e.g. a packing material spoiled by mistake.</p>
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
    try { _supAfter(await api("/api/supply/waste", { method: "POST", json: payload })); toast("Waste recorded, stock reduced"); }
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
        <button class="lc-x" data-unmap="${m.id}" title="Remove" aria-label="Remove this link">${sic("close")}</button></span>`;
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
      <h4 style="margin:0 0 4px;"> Product links <span class="muted tiny">(how much inventory each product needs)</span></h4>
      <p class="muted tiny">When you sell one of a product, how many of this item does it use up? Set that here and we can tell when you are about to run out, based on what you actually sell, not guesswork.</p>
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

// ---- Replenishment: check now, review a drafted PO, approve & send ----
async function supplyCheckNow() {
  try {
    const d = await withBusy("Checking every raw material…",
      "Days of supply against 1.2 × each supplier's lead time, anything short gets a purchase order drafted.",
      () => api("/api/supply/replenish/check", { method: "POST" }));
    _supAfter(d);
    const c = d.check || {};
    const made = (c.created || []).length + (c.appended || []).length;
    toast(made ? `${(c.low || []).length} item${(c.low || []).length === 1 ? "" : "s"} short, purchase order${made === 1 ? "" : "s"} drafted. Approve ${made === 1 ? "it" : "them"} in the Approval panel.`
      : (c.low || []).length ? "Everything short is already on order." : "Every raw material has enough days of supply.", 7000);
  } catch (e) { toast(e.message, 6000); }
}

/* Moving a purchase order along its track. Receiving one puts the ordered
   quantities back into stock, which is the whole reason to record it. */
async function movePo(poNumber, status) {
  const WORD = { mailed: "marked as mailed", replied: "marked as replied",
                 confirmed: "marked as confirmed", received: "received, the quantities are back in stock",
                 cancelled: "cancelled" };
  if (status === "cancelled") return cancelPo(poNumber);
  try {
    const d = await api("/api/supply/po/move", { method: "POST",
      json: { po_number: poNumber, status } });
    _supAfter(d);
    toast(`${poNumber} ${WORD[status] || status}.`, status === "received" ? 7000 : 4000);
  } catch (e) { toast(e.message, 7000); }
}

/* Cancelling an order. One that has already gone out is the dangerous case:
   cancel it quietly and the supplier still makes it, still delivers it, still
   bills for it. So the note to them is written for the seller and sent by
   default, with the PO number in it. */
async function cancelPo(poNumber) {
  const po = ((_supplyData || {}).purchase_orders || []).find((p) => p.po_number === poNumber) || {};
  const out = ["mailed", "replied", "confirmed"].includes(po.status);
  openModal(`Cancel ${poNumber}?`, `
    <p style="margin-top:0;">${out
      ? `This order is already with ${esc((po.supplier || {}).name || "the supplier")}. Unless they are told, they can keep making it and bill you for it.`
      : "Nothing has gone to the supplier, so this just closes the order here."}</p>
    ${out ? `<label class="inline-check" style="display:flex;gap:8px;align-items:flex-start;margin:10px 0;">
      <input type="checkbox" id="cpTell" checked />
      <span>Email ${esc((po.supplier || {}).email || "the supplier")} to call it off, we write it, with the PO number in it.</span></label>
    <label class="fld"><span>Anything to add? <em>optional</em></span>
      <input id="cpWhy" placeholder="e.g. the festival order is covered, we no longer need it" /></label>` : ""}
    <div class="modal-actions">
      <button class="btn ghost" data-cpx>Keep the order</button>
      <button class="btn danger" id="cpGo">${sic("close")}Cancel the order</button>
    </div>`);
  document.querySelector("[data-cpx]").onclick = closeModal;
  $("cpGo").onclick = async () => {
    const tell = out && ($("cpTell") || {}).checked;
    try {
      const d = await withBusy("Cancelling the order…",
        tell ? "Writing to the supplier so nothing is made or dispatched." : "Closing it here.",
        () => api("/api/supply/po/cancel", { method: "POST", json: {
          po_number: poNumber, tell_supplier: !!tell, note: (($("cpWhy") || {}).value || "").trim() } }));
      closeModal();
      _supAfter(d);
      const t = d.told_supplier || {};
      if (tell && t.sent) toast(`${poNumber} cancelled, and ${t.to} has been told.`, 7000);
      else if (tell) toast(`${poNumber} cancelled here, but the email did not go: ${t.reason || "no address on file"}. Tell them yourself.`, 10000);
      else toast(`${poNumber} cancelled.`, 5000);
    } catch (e) { toast(e.message, 8000); }
  };
}

/* Connecting the seller's own email. A purchase order from no-reply@ourapp is
   an order from a stranger; from their own address it is the shop the supplier
   already deals with, and the reply comes back to them without us in the way. */
/* ============================================================================
   Connecting the seller's own email, drawn in two places.
   Account > Email and the Suppliers "Send orders from my email" button both
   call renderMailGuide(), so there is one guide and not two that drift. The
   providers, their links and their steps come from the server
   (seller_mail.GUIDES); this file keeps no host table of its own any more.

   THE STEPS THIS REMOVES: the seller used to press a button that closed
   Account, read one line of Gmail-only help with no link, leave the app to
   hunt for the app-password page, fill in five fields, and land on Suppliers.
   Now their provider is already picked from their address, one button opens
   the exact page, the server is worked out for them, and they stay where they
   started. An error sits under the button that caused it instead of in a
   toast that vanishes while they are reading it.
   ============================================================================ */
async function renderMailGuide(boxId, opts = {}) {
  const box = $(boxId);
  if (!box) return;
  box.innerHTML = `<div class="ap-empty">Checking your email…</div>`;
  let d;
  try { d = await api("/api/mail/account"); }
  catch (e) { box.innerHTML = `<p class="muted tiny">${esc(e.message)}</p>`; return; }
  const provs = d.providers || [];
  const byId = Object.fromEntries(provs.map((p) => [p.id, p]));
  const domains = d.domains || {};
  const form = { address: d.address || state.email || "", password: "", name: "",
                 host: "", port: "", editing: !d.connected, error: "" };
  let pick = (d.guess && d.guess.provider_id) || "gmail";
  if (!byId[pick]) pick = provs.length ? provs[0].id : "other";

  const out = (href, label) => href
    ? `<a class="btn primary block mg-link" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${sic("arrow-up-right")}${esc(label)}</a>`
    : "";
  const draw = () => {
    const p = byId[pick] || {};
    const connected = d.connected && !form.editing;
    let body;
    if (connected) {
      body = `<div class="action-card ok" style="margin:0 0 10px;">
          <div class="do">Orders go out from ${esc(d.address)}</div>
          <div class="why">${d.checked_at ? `Tested ${esc(String(d.checked_at).slice(0, 16).replace("T", " "))}. ` : ""}A supplier's reply comes straight to that inbox.</div></div>
        <div class="mg-row">
          <button type="button" class="btn ghost sm" data-mgedit>Change</button>
          <button type="button" class="btn ghost sm danger" data-mgoff>Disconnect</button></div>`;
    } else if (p.works === false) {
      body = `<div class="mg-note">${esc(p.note || "")}</div>${out(p.link, p.link_label)}`;
    } else {
      body = `${p.prereq ? `<p class="muted tiny mg-pre">First: <a href="${esc(p.prereq.link)}" target="_blank" rel="noopener noreferrer">${esc(p.prereq.label)}</a></p>` : ""}
        ${(p.steps || []).length ? `<ol class="mg-steps">${p.steps.map((t) => `<li>${esc(t)}</li>`).join("")}</ol>` : ""}
        ${out(p.link, p.link_label)}
        <div class="sup-form-grid" style="grid-template-columns:1fr;">
          <label>Your email address<input data-mgf="address" type="email" value="${esc(form.address)}" placeholder="you@yourshop.com" autocomplete="email" /></label>
          <label>${esc(p.password_label || "App password")}<input data-mgf="password" type="password" value="${esc(form.password)}" placeholder="${d.connected ? "saved, type a new one to replace it" : "paste it here"}" autocomplete="new-password" /></label>
          <label>Name suppliers see <span class="muted tiny">optional</span><input data-mgf="name" value="${esc(form.name)}" placeholder="Kora Studio" /></label>
        </div>
        <details class="mg-adv"><summary>Advanced: mail server and port</summary>
          <div class="sup-form-grid">
            <label>Mail server<input data-mgf="host" value="${esc(form.host)}" placeholder="${esc(p.host || "worked out from your address")}" /></label>
            <label>Port<input data-mgf="port" type="number" value="${esc(form.port)}" placeholder="587, or 465 if that is blocked" /></label>
          </div></details>
        <div class="err mg-err" ${form.error ? "" : "hidden"}>${esc(form.error)}</div>
        <div class="mg-row">
          ${d.connected ? `<button type="button" class="btn ghost sm" data-mgcancel>Keep the current one</button>` : ""}
          <button type="button" class="btn primary" data-mgsave>${sic("mail")}Connect and send a test</button></div>
        <p class="sm-hint">We only send with this, we never read your mail. The password is stored encrypted and never shown again. The test goes to your own inbox, so you see it arrive before a supplier ever does.</p>`;
    }
    box.innerHTML = `<div class="mg">
        ${connected ? "" : `<div class="mg-q" id="${boxId}Q">Which email do you use?</div>
        <div class="mg-chips" role="radiogroup" aria-labelledby="${boxId}Q">${provs.map((q) =>
          `<button type="button" class="mg-chip" role="radio" aria-checked="${q.id === pick}" data-mgp="${esc(q.id)}">${esc(q.name)}</button>`).join("")}</div>`}
        <div class="mg-body">${body}</div></div>`;
    bind();
  };

  const done = (r, message) => {
    toast(message, 8000);
    if (opts.onDone) return opts.onDone(r);
    renderMailGuide(boxId, opts);
  };
  const bind = () => {
    box.querySelectorAll("[data-mgp]").forEach((b) => b.onclick = () => {
      pick = b.dataset.mgp; form.error = ""; draw();
    });
    box.querySelectorAll("[data-mgf]").forEach((el) => el.oninput = () => {
      form[el.dataset.mgf] = el.value;
      if (el.dataset.mgf !== "address") return;
      // Typing a Gmail or Yahoo address picks that guide. An unknown domain
      // leaves the seller's own pick alone: orders@yourshop.com could be
      // Google Workspace, Zoho or anything else, and only they know which.
      const dom = (el.value.split("@")[1] || "").trim().toLowerCase();
      if (domains[dom] && domains[dom] !== pick) {
        pick = domains[dom]; draw();
        const a = box.querySelector('[data-mgf="address"]');
        if (a) { a.focus(); a.setSelectionRange(a.value.length, a.value.length); }
      }
    });
    const on = (sel, fn) => { const el = box.querySelector(sel); if (el) el.onclick = fn; };
    on("[data-mgedit]", () => { form.editing = true; draw(); });
    on("[data-mgcancel]", () => { form.editing = false; form.error = ""; draw(); });
    on("[data-mgoff]", async () => {
      if (!confirm("Disconnect your email? Purchase orders stop going out from your address.")) return;
      try { const r = await api("/api/mail/account", { method: "DELETE" }); done(r, "Disconnected."); }
      catch (e) { toast(e.message); }
    });
    on("[data-mgsave]", async (ev) => {
      ev.currentTarget.disabled = true;
      form.error = "";
      try {
        const r = await withBusy("Checking your email…",
          "Signing in and sending a test message to yourself. You can leave this screen.",
          () => api("/api/mail/account", { method: "POST", json: {
            address: form.address.trim(), password: form.password, provider: pick,
            host: form.host.trim(), port: Number(form.port) || 0,
            display_name: form.name.trim() } }));
        done(r, `Connected. A test message is waiting in ${r.address}.`);
      } catch (e) { form.error = e.message; draw(); }
    });
  };
  draw();
}

async function openMailAccount() {
  openModal("Send purchase orders from your email", `
    <div id="mailGuideModal"></div>
    <div class="modal-actions"><button class="btn ghost" data-mamx>Close</button></div>`);
  document.querySelector("[data-mamx]").onclick = closeModal;
  // From Suppliers, finishing returns to Suppliers, which is where they were.
  renderMailGuide("mailGuideModal", { onDone: () => { closeModal(); openSupply(); } });
}

/* ============================================================================
   The Account tab. Everything the app asks a seller to set up once, in one
   place: where they are, where and in what currency they sell, the address
   their mail goes out from, their Instagram, their storefront payment gateway,
   and (optionally) their own AI keys. One fetch, one screen. No secret is ever
   shown back — only whether a thing is connected and its last four characters.
   ============================================================================ */
let _account = null;
async function openAccount() {
  let d;
  try { d = await withBusy("Opening your account…", "", () => api("/api/account")); }
  catch (e) { return toast(e.message); }
  _account = d;
  const m = d.market || {};
  const opt = (list, val, labeler) => (list || []).map((x) =>
    `<option value="${esc(labeler(x).v)}"${labeler(x).v === val ? " selected" : ""}>${esc(labeler(x).t)}</option>`).join("");
  const countryOpts = (val) => opt(d.countries, val, (c) => ({ v: c.code, t: c.name }));
  const ccyOpts = (val) => opt(d.currencies, val, (c) => ({ v: c.code, t: `${c.symbol}  ${c.name} (${c.code})` }));

  const email = d.sender_email || {};
  const ig = d.instagram || {};
  const pay = d.payments || {};
  const ai = d.ai_keys || {};
  const cr = d.credits || {};
  const cst = cr.costs || {};
  const pl = d.plan || {};

  const dot = (on) => `<span class="acc-dot ${on ? "on" : "off"}"></span>`;

  // one payment-gateway card
  const provCard = (p) => {
    const active = pay.active === p.id;
    const ready = (pay.charge_ready || {})[p.id];
    return `
    <div class="acc-prov ${active ? "active" : ""}" data-prov="${esc(p.id)}">
      <div class="acc-prov-h">
        <b>${dot(p.connected)}${esc(p.label)}</b>
        <span class="muted tiny">${esc((p.currencies || []).join(", "))}</span>
        ${active ? `<span class="acc-badge">In use</span>`
          : (p.connected ? `<button class="btn ghost tiny" data-use="${esc(p.id)}">Use for checkout</button>` : "")}
      </div>
      ${p.connected
        ? `<div class="muted tiny">Connected${p.mode ? ` (${esc(p.mode)})` : ""}${p.last4 ? ` · ends ${esc(p.last4)}` : ""}.
             ${ready ? "" : "Card capture for this gateway needs a test with your own keys before you rely on it."}
             <button class="btn ghost tiny danger" data-disc="${esc(p.id)}">Disconnect</button></div>`
        : `<div class="acc-prov-form">
             ${(p.fields || []).map((f) => `<label class="fld">
               <span>${esc(f.label)}${f.hint ? ` <span class="muted tiny">${esc(f.hint)}</span>` : ""}</span>
               <input data-pf="${esc(p.id)}:${esc(f.key)}" type="${f.secret ? "password" : "text"}"
                 autocomplete="off" placeholder="${esc(f.hint || "")}" /></label>`).join("")}
             <button class="btn primary sm" data-save="${esc(p.id)}">${sic("check")}Connect ${esc(p.label)}</button>
             <p class="muted tiny" style="margin:6px 0 0;">${esc(p.help || "")} Money settles into your own ${esc(p.label)} account, we never hold it.</p>
           </div>`}
    </div>`;
  };
  const providersHtml = ["razorpay", "stripe", "paypal"]
    .map((id) => pay.providers && pay.providers[id] ? provCard(pay.providers[id]) : "").join("");

  const aiRow = (id, label, hint) => {
    const st = ai[id] || {};
    return `<div class="acc-ai" data-ai="${esc(id)}">
      <label class="fld"><span>${dot(st.connected)}${esc(label)} key <span class="muted tiny">${esc(hint)}</span></span>
        <input data-aikey="${esc(id)}" type="password" autocomplete="off"
          placeholder="${st.connected ? `saved, ends ${esc(st.last4 || "")}, type a new one to replace` : "optional, leave blank to use ours"}" /></label>
      <div class="acc-ai-acts">
        <button class="btn ghost sm" data-aisave="${esc(id)}">Save key</button>
        ${st.connected ? `<button class="btn ghost sm danger" data-airemove="${esc(id)}">Remove</button>` : ""}
      </div></div>`;
  };

  // ---- Plan: current tier, and the Upgrade to Max (premium) offer ----
  const up = pl.upgrade || {};
  const planHtml = pl.is_pro ? `
      <section class="acc-sec">
        <h4>Plan</h4>
        <p style="margin-top:0;"><b>${esc(pl.name || "Max")}</b> (you're on premium. Everything is unlocked: unlimited AI, supply management, purchase orders, custom domain and multi-outlet.)</p>
        <button class="btn ghost sm danger" id="accCancelPlan">Cancel subscription</button>
        <p class="muted tiny" style="margin:6px 0 0;">Cancelling returns you to Free, which keeps all the numbers and actions. You can re-subscribe any time.</p>
      </section>` : `
      <section class="acc-sec" style="border:1px solid var(--accent,#4f46e5); border-radius:12px; padding:14px;">
        <h4 style="margin-top:0;">Upgrade to ${esc(up.name || "Max")}</h4>
        <p class="muted tiny" style="margin-top:0;">You're on <b>${esc(pl.name || "Free")}</b>. ${esc(up.tagline || "Runs the shop, not just the reporting.")}${
          pl.launch_mode ? " Everything is free during launch, upgrade now and you keep these when pricing starts." : ""}</p>
        <ul style="margin:8px 0 12px; padding-left:18px; font-size:13px; line-height:1.6;">
          ${(up.includes || []).map((x) => `<li>${esc(x)}</li>`).join("")}
        </ul>
        <button class="btn primary" id="accUpgrade">Upgrade to ${esc(up.name || "Max")}, ₹${up.price_inr ?? 999}/${esc(up.period || "month")}</button>
      </section>`;

  // ---- Credits: a monthly allowance + purchased packs, spent by real usage ----
  const pct = cr.monthly_grant
    ? Math.max(0, Math.min(100, Math.round(100 * (cr.monthly_left || 0) / cr.monthly_grant)))
    : 0;
  const creditsHtml = (cr.enabled === false) ? "" : `
      <section class="acc-sec">
        <h4>Credits</h4>
        <p class="muted tiny" style="margin-top:0;">A monthly allowance you can top up. Every generation spends what it actually costs,
          a picture ${cst.image ?? 10}, a video ${cst.video ?? 280}, a caption or an image read ${cst.text ?? 1}.${
          cr.launch_mode ? " Everything is free during launch; this is the meter for later." : ""}</p>
        <div style="display:flex; justify-content:space-between; font-size:13px;"><span class="muted">This month</span><b>${cr.monthly_left ?? 0} of ${cr.monthly_grant ?? 0} left</b></div>
        <div style="height:8px; border-radius:6px; background:rgba(127,127,127,.18); overflow:hidden; margin:6px 0 3px;"><div style="height:100%; width:${pct}%; background:var(--accent,#4f46e5);"></div></div>
        <div class="muted tiny" style="margin:0 0 10px;">Resets ${esc(cr.resets || "on the 1st")}.</div>
        <div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:4px;"><span class="muted">Purchased credits <span class="tiny">(never expire)</span></span><b>${cr.purchased ?? 0}</b></div>
        <div style="display:flex; justify-content:space-between; font-size:13px; border-top:1px solid rgba(127,127,127,.18); padding-top:6px;"><span>Available to spend</span><b>${cr.balance ?? 0}</b></div>
        <button class="btn primary sm" id="accBuyCredits" style="margin-top:12px;">Buy more credits</button>
      </section>`;

  // ---- Danger zone: reset (keep login) and delete (remove everything) ----
  const dangerHtml = `
      <section class="acc-sec">
        <h4 style="margin-top:0;">Privacy</h4>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; padding:8px 0;">
          <div><b>Cookie settings</b><p class="muted tiny" style="margin:2px 0 0;">Change whether this site may count your visit. Saying no also deletes the cookies that were already set.</p></div>
          <span data-cookie-settings style="flex:none;"></span>
        </div>
      </section>
      <section class="acc-sec">
        <h4 style="color:var(--danger,#dc2626);">Danger zone</h4>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; padding:8px 0; border-bottom:1px solid rgba(127,127,127,.15);">
          <div><b>Reset account</b><p class="muted tiny" style="margin:2px 0 0;">Clears your settings, storefront, products, tasks and uploaded data. Your login and purchased credits stay.</p></div>
          <button class="btn ghost sm danger" id="accReset" style="flex:none;">Reset</button>
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; padding:8px 0;">
          <div><b>Delete account</b><p class="muted tiny" style="margin:2px 0 0;">Permanently removes your account and everything in it. This cannot be undone.</p></div>
          <button class="btn ghost sm danger" id="accDelete" style="flex:none;">Delete</button>
        </div>
      </section>`;

  // ---- each settings area as its own pane ----
  const marketHtml = `
      <section class="acc-sec">
        <h4 style="margin-top:0;">Store</h4>
        <p class="muted tiny" style="margin-top:0;">Sets your clock, your prices, and whether tax is added. ${esc(m.tz_label || "")}.</p>
        <label class="fld"><span>Your country</span><select id="accCountry">${countryOpts(m.country)}</select></label>
        <label class="fld"><span>Selling to</span><select id="accSelling">${countryOpts(m.selling_country)}</select></label>
        <label class="fld"><span>Currency</span><select id="accCcy">${ccyOpts(m.currency)}</select></label>
        <p class="muted tiny">${m.charges_tax
          ? "GST applies on your store, as it does for a business in India."
          : "No tax is added on your store, tax outside India is not handled yet, so prices are shown as you set them."}</p>
        <button class="btn primary sm" id="accSaveMarket">${sic("check")}Save</button>
      </section>`;

  // The guide is drawn inline when this pane opens (see the nav handler below),
  // so connecting never takes the seller out of Account.
  const emailHtml = `
      <section class="acc-sec">
        <h4 style="margin-top:0;">Email you send orders from</h4>
        <p class="muted tiny" style="margin-top:0;">Purchase orders go out from this address, so your supplier recognises it and replies straight to your inbox.</p>
        <div id="accMailBox"><div class="ap-empty">Checking your email…</div></div>
      </section>`;

  const igHtml = `
      <section class="acc-sec">
        <h4 style="margin-top:0;">${dot(ig.connected)}Instagram</h4>
        <p class="muted tiny" style="margin-top:0;">${ig.connected
          ? `Connected as <b>@${esc(ig.username || "your account")}</b>, posts can publish straight from here.`
          : (ig.oauth_available ? "Connect Instagram to publish posts straight from the app."
             : "Instagram publishing is not configured on this server yet.")}</p>
        <button class="btn ghost sm" id="accIg">${sic("instagram")}${ig.connected ? "Manage" : "Connect Instagram"}</button>
      </section>`;

  const paymentsHtml = `
      <section class="acc-sec">
        <h4 style="margin-top:0;">Payments on your storefront</h4>
        <p class="muted tiny" style="margin-top:0;">Connect the gateway you already use. Razorpay for India, Stripe or PayPal for the US, UK and Europe. You pick one for checkout.</p>
        ${providersHtml}
      </section>`;

  const apiHtml = `
      <section class="acc-sec">
        <h4 style="margin-top:0;">Your own AI keys <span class="muted tiny">optional</span></h4>
        <p class="muted tiny" style="margin-top:0;">Leave these blank to use ours (subject to the monthly picture limit). Add your own and captions and pictures run on your key and your bill, with no monthly limit from us.</p>
        ${aiRow("openai", "OpenAI", "for captions and pictures, starts with sk-")}
        ${aiRow("gemini", "Google Gemini", "for brand-aware pictures")}
      </section>`;

  // ---- Sales channels: connect a store's orders straight into analytics ----
  const channelsHtml = `
      <section class="acc-sec">
        <h4 style="margin-top:0;">Sales channels</h4>
        <p class="muted tiny" style="margin-top:0;">Connect where you already sell, WooCommerce, Wix, Shopify, Amazon, and pull your orders in. Once connected, press <b>Pull orders</b> and those sales show up in Sales Analytics like any other data.</p>
        <div class="chan-strip" id="accChanStrip"><div class="ap-empty">Loading channels…</div></div>
      </section>`;

  // ---- left-hand nav: one row per settings area, with an inline icon ----
  const NAV = [
    ["store",     "Store",          '<path d="M4 4h16l-1 5H5L4 4Z"/><path d="M6 9v10h12V9"/><path d="M10 19v-5h4v5"/>'],
    ["channels",  "Sales channels", '<path d="M3 6h18"/><path d="M6 6v13h12V6"/><path d="M9 10h6"/><path d="M9 14h6"/>'],
    ["billing",   "Plan & Billing", '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/>'],
    ["payments",  "Payments",       '<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="16.5" cy="12" r="1.2"/><path d="M3 9h13"/>'],
    ["email",     "Email",          '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>'],
    ["instagram", "Instagram",      '<rect x="4" y="4" width="16" height="16" rx="4.5"/><circle cx="12" cy="12" r="3.6"/><circle cx="17" cy="7" r="1"/>'],
    ["api",       "API keys",       '<circle cx="8" cy="12" r="3.4"/><path d="M11.2 12H20l-2.2 2.2M20 12l-2.2-2.2"/>'],
    ["danger",    "Account",        '<circle cx="12" cy="8" r="3.4"/><path d="M5 20c0-3.3 3.1-6 7-6s7 2.7 7 6"/>'],
  ];
  const navHtml = NAV.map(([id, label, icon], i) =>
    `<button type="button" data-nav="${id}"${i === 0 ? ' class="active"' : ""}>
       <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${icon}</svg>
       <span>${label}</span></button>`).join("");

  openModal("Account", `
    <style>
      .acc2{display:flex;gap:0;min-height:440px}
      .acc2-nav{flex:0 0 178px;display:flex;flex-direction:column;gap:2px;border-right:1px solid rgba(128,128,128,.18);padding-right:10px}
      .acc2-nav button{display:flex;align-items:center;gap:10px;width:100%;text-align:left;background:none;border:none;color:var(--text,#e5e7eb);padding:9px 11px;border-radius:8px;cursor:pointer;font-size:14px;line-height:1.2}
      .acc2-nav button svg{width:17px;height:17px;flex:none;opacity:.75}
      .acc2-nav button:hover{background:rgba(128,128,128,.12)}
      .acc2-nav button.active{background:rgba(128,128,128,.18);font-weight:600}
      .acc2-nav button.active svg{opacity:1}
      .acc2-body{flex:1 1 auto;min-width:0;padding:0 2px 4px 20px;max-height:64vh;overflow:auto}
      .acc2-pane{display:none;max-width:600px}
      .acc2-pane.active{display:block}
      @media (max-width:640px){
        .acc2{flex-direction:column}
        .acc2-nav{flex:none;flex-direction:row;overflow-x:auto;border-right:none;border-bottom:1px solid rgba(128,128,128,.18);padding:0 0 8px;margin-bottom:8px}
        .acc2-nav button{width:auto;white-space:nowrap}
        .acc2-body{padding:0;max-height:none}
      }
    </style>
    <div class="acc2">
      <nav class="acc2-nav">${navHtml}</nav>
      <div class="acc2-body">
        <div class="acc2-pane active" data-pane="store">${marketHtml}</div>
        <div class="acc2-pane" data-pane="channels">${channelsHtml}</div>
        <div class="acc2-pane" data-pane="billing">${planHtml}${creditsHtml}</div>
        <div class="acc2-pane" data-pane="payments">${paymentsHtml}</div>
        <div class="acc2-pane" data-pane="email">${emailHtml}</div>
        <div class="acc2-pane" data-pane="instagram">${igHtml}</div>
        <div class="acc2-pane" data-pane="api">${apiHtml}</div>
        <div class="acc2-pane" data-pane="danger">${dangerHtml}</div>
      </div>
    </div>
    <div class="modal-actions"><button class="btn ghost" data-accx>Close</button></div>`, { wide: true });

  // This screen was just rebuilt, which threw away the Cookie settings control
  // along with the old DOM. consent.js puts it back into the slot above.
  if (window.cxCookieSettings) window.cxCookieSettings();

  // settings-style nav: show one pane at a time
  (function () {
    const navs = Array.from(document.querySelectorAll(".acc2-nav [data-nav]"));
    const panes = Array.from(document.querySelectorAll(".acc2-pane"));
    const body = document.querySelector(".acc2-body");
    navs.forEach((b) => b.onclick = () => {
      navs.forEach((n) => n.classList.toggle("active", n === b));
      panes.forEach((p) => p.classList.toggle("active", p.dataset.pane === b.dataset.nav));
      if (body) body.scrollTop = 0;
      // The slot only becomes visible when its own pane opens, so re-home the
      // control then: findSlot() prefers whichever slot is actually on screen.
      if (window.cxCookieSettings) window.cxCookieSettings();
      // The email guide is drawn fresh each time, so it always shows the
      // current connection rather than the one from when Account opened.
      if (b.dataset.nav === "email") renderMailGuide("accMailBox");
      // Load the sales-channel connectors the first time that pane is opened.
      if (b.dataset.nav === "channels") {
        const el = $("accChanStrip");
        if (el && !el.dataset.loaded) { el.dataset.loaded = "1"; renderChannels("accChanStrip"); }
      }
    });
  })();

  document.querySelector("[data-accx]").onclick = closeModal;

  // when the selling country changes and the seller has not overridden the
  // currency, follow it — the same rule the server uses.
  const CCY_BY_COUNTRY = { IN: "INR", US: "USD", GB: "GBP",
    DE: "EUR", FR: "EUR", ES: "EUR", IT: "EUR", NL: "EUR", IE: "EUR", PT: "EUR",
    AT: "EUR", BE: "EUR", FI: "EUR", GR: "EUR" };
  $("accSelling").onchange = () => {
    const c = CCY_BY_COUNTRY[$("accSelling").value] || "USD";
    if ($("accCcy")) $("accCcy").value = c;
  };

  $("accSaveMarket").onclick = async () => {
    try {
      _account = await withBusy("Saving…", "", () => api("/api/account/settings", { method: "POST", json: {
        country: $("accCountry").value, selling_country: $("accSelling").value,
        currency: $("accCcy").value } }));
      toast("Saved. Your prices now show in " + ($("accCcy").value) + ".");
      closeModal(); openAccount();
    } catch (e) { toast(e.message, 7000); }
  };
  if ($("accIg")) $("accIg").onclick = () => { closeModal(); openModule("instagram"); };

  // payment gateways
  document.querySelectorAll("[data-save]").forEach((b) => b.onclick = async () => {
    const pid = b.dataset.save;
    const vals = {};
    document.querySelectorAll(`[data-pf^="${pid}:"]`).forEach((i) => {
      vals[i.dataset.pf.split(":")[1]] = i.value.trim();
    });
    const route = pid === "razorpay" ? "/api/site/gateway"
      : pid === "stripe" ? "/api/site/gateway/stripe" : "/api/site/gateway/paypal";
    const json = pid === "razorpay" ? { key_id: vals.key_id, key_secret: vals.key_secret }
      : pid === "stripe" ? { secret_key: vals.secret_key, publishable_key: vals.publishable_key }
      : { client_id: vals.client_id, client_secret: vals.client_secret };
    try {
      await api(route, { method: "POST", json });
      toast(`${pid[0].toUpperCase() + pid.slice(1)} connected.`);
      closeModal(); openAccount();
    } catch (e) { toast(e.message, 7000); }
  });
  document.querySelectorAll("[data-use]").forEach((b) => b.onclick = async () => {
    try { await api("/api/site/gateway/provider", { method: "POST", json: { provider: b.dataset.use } });
      closeModal(); openAccount(); } catch (e) { toast(e.message); }
  });
  document.querySelectorAll("[data-disc]").forEach((b) => b.onclick = async () => {
    if (!confirm("Disconnect this gateway? Your storefront stops taking online payment through it.")) return;
    try { await api(`/api/site/gateway/disconnect?provider=${encodeURIComponent(b.dataset.disc)}`, { method: "POST" });
      closeModal(); openAccount(); } catch (e) { toast(e.message); }
  });

  // AI keys
  document.querySelectorAll("[data-aisave]").forEach((b) => b.onclick = async () => {
    const id = b.dataset.aisave;
    const key = (document.querySelector(`[data-aikey="${id}"]`) || {}).value || "";
    if (!key.trim()) return toast("Paste a key first, or leave it blank to use ours.");
    try { await api("/api/account/ai-key", { method: "POST", json: { provider: id, api_key: key.trim() } });
      toast("Saved. That AI now runs on your key."); closeModal(); openAccount(); }
    catch (e) { toast(e.message, 7000); }
  });
  document.querySelectorAll("[data-airemove]").forEach((b) => b.onclick = async () => {
    try { await api(`/api/account/ai-key/${encodeURIComponent(b.dataset.airemove)}`, { method: "DELETE" });
      toast("Removed. Back to ours."); closeModal(); openAccount(); } catch (e) { toast(e.message); }
  });

  // plan + credits + danger zone
  if ($("accUpgrade")) $("accUpgrade").onclick = () => upgradeToMax((pl.upgrade || {}).product || "pro");
  if ($("accCancelPlan")) $("accCancelPlan").onclick = async () => {
    if (!confirm("Cancel your Max subscription and return to the free plan? "
               + "You keep all the numbers and actions, and can re-subscribe any time.")) return;
    try {
      const r = await api("/api/pay/cancel", { method: "POST", json: {} });
      toast(r.message || "Subscription cancelled: you're back on Free.", 6000);
      closeModal(); openAccount();
    } catch (e) { toast(e.message); }
  };
  if ($("accBuyCredits")) $("accBuyCredits").onclick = () => openBuyCredits(cr);
  if ($("accReset")) $("accReset").onclick = () => confirmReset();
  if ($("accDelete")) $("accDelete").onclick = () => confirmDelete();
}

/* ============================================================================
   Buy credits — the packs from the pricing catalog, paid with Razorpay, the
   same two-call flow the storefront uses (create-order → gateway → verify).
   ========================================================================== */
function loadRazorpayScript() {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = resolve;
    s.onerror = () => reject(new Error("Could not load the payment window, check your connection."));
    document.head.appendChild(s);
  });
}

function openBuyCredits(cr) {
  cr = cr || {};
  const packs = cr.packs || [];
  const cst = cr.costs || {};
  const rows = packs.length ? packs.map((p) => `
    <div class="acc-sec" style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
      <div>
        <b>${esc(p.name)}</b> <span class="muted tiny">₹${p.price_inr}</span>
        <p class="muted tiny" style="margin:2px 0 0;">${esc(p.description || (p.credits + " credits"))}</p>
      </div>
      <button class="btn primary sm" data-pack="${esc(p.id)}" style="flex:none;">Buy: ₹${p.price_inr}</button>
    </div>`).join("") : `<p class="muted">No credit packs are configured on this server yet.</p>`;

  openModal("Buy credits", `
    <p class="muted tiny" style="margin-top:0;">Credits never expire and stack on top of your monthly allowance.
      A picture costs ${cst.image ?? 10}, a video ${cst.video ?? 280}, a caption or an image read ${cst.text ?? 1}.
      Paid securely through Razorpay.</p>
    ${rows}
    <div class="modal-actions"><button class="btn ghost" data-mclose2>Close</button></div>`, { wide: true });
  const x = document.querySelector("[data-mclose2]"); if (x) x.onclick = closeModal;
  document.querySelectorAll("[data-pack]").forEach((b) => b.onclick = () => buyCredits(b.dataset.pack));
}

function buyCredits(productId) { return startCheckout(productId, "Payment successful: credits added.", "It's free during launch, nothing to buy yet."); }

/* Upgrade to Max (premium). Same pay flow as a credit pack; the server grants
   the tier on a verified signature, so all this does is start the checkout. */
function upgradeToMax(productId) {
  return startCheckout(productId || "pro", "You're on Max now, everything's unlocked.",
    "Everything is free during launch, you're already getting Max features.");
}

/* One Razorpay round-trip, shared by credit packs and the plan upgrade:
   create-order → gateway → verify, then refresh the Account tab. */
async function startCheckout(productId, successMsg, launchMsg) {
  if (!state.token) { closeModal(); return toast("Log in first."); }
  try {
    const order = await api("/api/pay/create-order", { method: "POST", json: { product: productId } });
    if (order.launch_free) { toast(launchMsg || "It's free during launch."); return; }
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
          await api("/api/pay/verify", { method: "POST", json: {
            razorpay_order_id: resp.razorpay_order_id,
            razorpay_payment_id: resp.razorpay_payment_id,
            razorpay_signature: resp.razorpay_signature,
            product: productId,
          }});
          closeModal();
          toast(successMsg || "Payment successful.", 5000);
          openAccount();
        } catch (e) { toast(e.message, 6000); }
      },
    });
    rzp.open();
  } catch (e) { toast(e.message, 6000); }
}

/* A typed-confirmation popup for the two irreversible actions, so neither can
   fire on a stray click. `word` is what the seller must type to arm the button. */
function confirmDanger({ title, body, word, danger, run }) {
  openModal(title, `
    ${body}
    <label class="fld" style="margin-top:10px;"><span>Type <b>${esc(word)}</b> to confirm</span>
      <input id="dangerType" autocomplete="off" placeholder="${esc(word)}" /></label>
    <div class="modal-actions">
      <button class="btn ghost" data-dcancel>Cancel</button>
      <button class="btn ${danger ? "danger" : "primary"}" id="dangerGo" disabled>${esc(title)}</button>
    </div>`, {});
  const input = $("dangerType"), go = $("dangerGo");
  const cancel = document.querySelector("[data-dcancel]");
  if (cancel) cancel.onclick = closeModal;
  input.oninput = () => { go.disabled = input.value.trim().toUpperCase() !== word.toUpperCase(); };
  go.onclick = async () => {
    go.disabled = true;
    try { await run(); }
    catch (e) { toast(e.message, 7000); go.disabled = false; }
  };
  setTimeout(() => input.focus(), 50);
}

function confirmReset() {
  confirmDanger({
    title: "Reset account",
    word: "RESET",
    danger: false,
    body: `<p class="muted">This clears your settings, storefront, products, tasks and every uploaded file, and drops you back to an empty workspace. Your login and any purchased credits stay. This cannot be undone.</p>`,
    run: async () => {
      await withBusy("Resetting your account…", "", () => api("/api/account/reset", { method: "POST" }));
      warmClear(); warmModClearAll();
      closeModal();
      toast("Your account has been reset. Starting fresh.", 5000);
      await goHome();
    },
  });
}

function confirmDelete() {
  confirmDanger({
    title: "Delete account",
    word: "DELETE",
    danger: true,
    body: `<p class="muted">This permanently removes your account and everything in it, settings, storefront, products, data and your login. It cannot be undone, and you'll be signed out.</p>`,
    run: async () => {
      await withBusy("Deleting your account…", "", () => api("/api/account/delete", { method: "DELETE" }));
      // The session no longer exists on the server; clear the client the same
      // way logout does and drop the seller back at the login screen.
      state.token = null; state.email = null;
      try { localStorage.removeItem("cx_token"); localStorage.removeItem("cx_email"); } catch (e) {}
      resetSessionId();   // the old session belonged to the account we just deleted
      warmClear(); warmModClearAll();
      closeModal();
      if ($("appShell")) $("appShell").hidden = true;
      if ($("loginView")) $("loginView").hidden = false;
      try { if (window.google && google.accounts) google.accounts.id.disableAutoSelect(); } catch (e) {}
      try { setupGoogleSignIn(); } catch (e) {}
      toast("Your account has been deleted.", 5000);
    },
  });
}

/* The signature that goes on every PO. Optional — without one the PO still
   carries the shop's name over "authorised signatory". */
function pickSignature() {
  pickImage(async (url) => saveSignature(url), false, "image/png,image/jpeg,image/webp");
}

async function saveSignature(url) {
  try {
    _supAfter(await api("/api/supply/signature", { method: "POST", json: { url } }));
    toast(url ? "Signature saved: it will appear on every purchase order." : "Signature removed.");
  } catch (e) { toast(e.message); }
}

/* Details on a drafted PO: each line with its days of supply and how its
   quantity was worked out (editable), the supplier, and the email the content
   writer drafted — editable too — before anything is sent. */
async function openPoDetail(poNumber) {
  let d;
  try { d = await withBusy("Opening the purchase order…", "Drafting the email to the supplier if there is not one yet.",
    () => api(`/api/supply/po/${encodeURIComponent(poNumber)}/detail`)); }
  catch (e) { toast(e.message); return; }
  const po = d.po, sup = po.supplier || {}, em = d.email || {};
  const draft = po.status === "draft" || po.status === "open";
  const rows = (po.lines || []).map((ln) => {
    const n = ln.now || {};
    return `<tr>
      <td><b>${esc(ln.name)}</b>${(n.linked_products || []).length ? `<div class="muted tiny">in ${n.linked_products.map(esc).join(", ")}</div>` : ""}</td>
      <td class="num">${n.current_stock == null ? "–" : fmt(n.current_stock)}</td>
      <td class="num">${n.dos == null ? "–" : n.dos} <span class="muted tiny">/ ${n.dos_threshold ?? "–"}</span></td>
      <td class="num">${n.effective_lead_time_days ?? "–"}</td>
      <td class="num">${draft ? `<input class="doq-in" type="number" min="0" step="1" data-poqty="${esc(ln.inventory_id)}" value="${ln.order_qty}" />` : fmt(ln.order_qty)}
        <span class="muted tiny">${esc(ln.unit_label || "")} · ${esc(DOQ_BASIS[n.doq_basis || ln.doq_basis] || "")}</span></td>
      <td class="num">${ln.line_amount == null ? "–" : _rupee(ln.line_amount)}</td>
    </tr>`;
  }).join("");
  openModal(`${po.po_number} – ${sup.name || "supplier"}`, `
    <div class="po-d-sup">
      <div><b>${esc(sup.name || "No supplier named")}</b>
        <div class="muted tiny">${esc(sup.email || "no email on file")}${sup.phone ? " · " + esc(sup.phone) : ""}</div></div>
      <span class="po-st st-${esc(po.status)}">${esc(po.status === "draft" ? "waiting for you" : po.status)}</span>
    </div>
    ${po.note ? `<p class="muted tiny" style="margin:6px 0 10px;">${esc(po.note)}</p>` : ""}
    <div class="table-scroll"><table class="sup-table">
      <thead><tr><th>Item</th><th class="num">Left</th><th class="num" title="Days of supply / what we want in hand (1.2 × lead time)">DOS / need</th>
        <th class="num">Lead time</th><th class="num">Order</th><th class="num">Amount</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    ${(po.lines || []).map((ln) => { const nw = ln.now || {}; if (!nw.reason) return "";
      const moved = nw.doq != null && ln.order_qty != null && Math.round(nw.doq) !== Math.round(ln.order_qty);
      return `<p class="muted tiny" style="margin:6px 0 0;"><b>${esc(ln.name)}:</b> ${esc(nw.reason)}${moved
        ? ` <span class="warn-t">This order was drafted for ${fmt(ln.order_qty)}; with the latest sales the DOQ is now ${fmt(nw.doq)}, change the quantity above if you want it.</span>` : ""}</p>`; }).join("")}

    <div class="sup-sub" style="margin-top:16px;">${sic("mail")}Email to the supplier <span class="muted tiny">(the PO goes as a PDF attachment)</span></div>
    <label class="fld"><span>To</span><input id="poTo" type="email" value="${esc(em.to || sup.email || "")}" placeholder="orders@supplier.com" /></label>
    <label class="fld"><span>Subject</span><input id="poSubj" value="${esc(em.subject || "")}" /></label>
    <label class="fld"><span>Message</span><textarea id="poMsg" rows="9">${esc(em.body || "")}</textarea></label>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="btn ghost sm" id="poRewrite">${sic("spark")}Rewrite with AI</button>
      <a class="btn ghost sm" id="poPdf" href="#">${sic("receipt")}See the PDF</a>
      ${d.email_ready ? "" : `<span class="muted tiny">Email sending is not set up on this server, Approve gives you the PDF and opens your own mail app with this message.</span>`}
    </div>
    <div class="modal-actions">
      <button class="btn ghost" data-poclose>Close</button>
      ${draft ? `<button class="btn reject" id="poCancel">Cancel order</button>
      <button class="btn ghost" id="poSave">Save changes</button>
      <button class="btn approve" id="poSend">${sup.email || em.to ? "Approve &amp; send" : "Approve &amp; download"}</button>` : ""}
    </div>`, { wide: true });

  document.querySelector("[data-poclose]").onclick = closeModal;
  $("poPdf").onclick = (e) => { e.preventDefault(); download(d.pdf_url, `${po.po_number}.pdf`); };
  $("poRewrite").onclick = async () => {
    const b = $("poRewrite"); b.disabled = true; b.innerHTML = sic("spark") + "Writing…";
    try {
      const r = await api(`/api/supply/po/${encodeURIComponent(po.po_number)}/email/rewrite`, { method: "POST" });
      $("poSubj").value = r.email.subject || ""; $("poMsg").value = r.email.body || "";
    } catch (e) { toast(e.message); }
    b.disabled = false; b.innerHTML = sic("spark") + "Rewrite with AI";
  };
  const saveAll = async () => {
    const qty = {};
    document.querySelectorAll("[data-poqty]").forEach((inp) => { qty[inp.dataset.poqty] = parseFloat(inp.value) || 0; });
    if (Object.keys(qty).length) await api(`/api/supply/po/${encodeURIComponent(po.po_number)}/lines`, { method: "POST", json: { qty } });
    await api(`/api/supply/po/${encodeURIComponent(po.po_number)}/email`, { method: "POST",
      json: { subject: $("poSubj").value, body: $("poMsg").value, to: $("poTo").value.trim() } });
  };
  if ($("poSave")) $("poSave").onclick = async () => {
    try { await saveAll(); toast("Saved."); } catch (e) { toast(e.message); }
  };
  if ($("poCancel")) $("poCancel").onclick = async () => {
    closeModal();
    await decide(`po_${po.po_number}`, "cancel");
  };
  if ($("poSend")) $("poSend").onclick = async () => {
    try { await saveAll(); } catch (e) { toast(e.message); return; }
    closeModal();
    await approvePo(po.po_number);
  };
}

/* Approve a drafted PO: the backend writes/uses the email, attaches the PDF
   and sends it. If it could not be emailed from here, the seller gets the PDF
   and their own mail app opened with the message, so it still goes today. */
async function approvePo(poNumber) {
  /* Writing the email, rendering the PDF and handing it to an SMTP server is
     several seconds the seller has nothing to contribute to. Same rule as a
     post: the decision was theirs, the sending is ours.
     The one thing that cannot go quietly is a send that did not happen —
     a supplier who never got the order is a stockout three weeks later — so
     the failure path puts the card back exactly as it does for a post, and the
     "we could not email it, here is the PDF" case still opens its popup, since
     that one needs the seller to do something. */
  runInBackground(`po_${poNumber}`, {
    label: "Sending the purchase order",
    run: () => api(`/api/supply/po/${encodeURIComponent(poNumber)}/approve`, { method: "POST", json: {} }),
    onDone: (r) => {
      if (_currentModule === "supply" || _currentModule === "inventory") openSupply();
      if (r.sent) { toast(`Sent to ${r.to} with the PO attached.`, 6000); return; }
      poSendItYourself(poNumber, r);
    },
  });
}

/* The server could not send it. The order is approved either way, so this is
   not a failure of the decision — it is a handover, and it needs the seller. */
function poSendItYourself(poNumber, r) {
  openModal("Approved: send it yourself", `
    <p style="margin-top:0;">${esc(r.reason || "It could not be emailed from here.")}</p>
    <p class="muted">The order is approved. Download the PDF and send it with the ready-written message,
      the button below opens your own mail app with it filled in; attach the PDF there.</p>
    <div class="modal-actions">
      <button class="btn ghost" data-apx>Close</button>
      <button class="btn ghost" id="apPdf">${sic("receipt")}Download PDF</button>
      ${r.mailto ? `<a class="btn primary" href="${esc(r.mailto)}" target="_blank" rel="noopener">${sic("mail")}Open my mail app</a>` : ""}
    </div>`);
  document.querySelector("[data-apx]").onclick = closeModal;
  $("apPdf").onclick = () => download(r.pdf_url, `${poNumber}.pdf`);
}

// ---- Purchase orders ----
async function supplyOpenPo(itemIds) {
  try {
    const d = await api("/api/supply/po/create", { method: "POST", json: { item_ids: itemIds } });
    if (d.download_url) await download(d.download_url, `${d.po_number}.pdf`);
    _supAfter(d);
    toast(`${d.po_number}, PDF saved to your device.`);
  } catch (e) { toast(e.message); }
}

async function supplyGeneratePo() {
  // One order form per supplier, because an order form listing four items from
  // three suppliers cannot be sent to anybody. The seller gets one sheet per
  // person they buy from, and a WhatsApp/email button for each.
  try {
    const d = await withBusy("Working out what to order",
      "Checking what is running low, then making one order form per supplier.",
      () => api("/api/supply/reorder/generate", { method: "POST" }));
    _supAfter(d);
    const orders = d.orders || (d.po_number ? [{ po_number: d.po_number, supplier_name: "",
      download_url: d.download_url, excel_url: d.excel_url }] : []);
    if (!orders.length) { toast("Nothing to order right now."); return; }
    showSupplierOrders(orders);
  } catch (e) { toast(e.message, 7000); }
}

/* The panel that turns "we made you 3 order forms" into 3 things you can
   actually do — open, WhatsApp, email — with the supplier's name on each, so
   nobody has to work out which sheet goes where. */
function showSupplierOrders(orders) {
  const rows = orders.map((o) => {
    const who = o.unassigned_supplier
      ? `<b>No supplier set</b><div class="muted tiny">Add a supplier to these items and we can send it for you.</div>`
      : `<b>${esc(o.supplier_name || "Supplier")}</b><div class="muted tiny">${esc(o.supplier_phone || "")}${o.supplier_phone && o.supplier_email ? " · " : ""}${esc(o.supplier_email || "")}</div>`;
    const msg = encodeURIComponent(
      `Hello${o.supplier_name ? " " + o.supplier_name : ""}, I would like to place an order. `
      + `Reference ${o.po_number} – ${o.n_items || 0} item${(o.n_items || 0) === 1 ? "" : "s"}. `
      + `Sending the details now.`);
    const wa = o.supplier_phone
      ? `<a class="btn ghost sm" target="_blank" rel="noopener" href="https://wa.me/${String(o.supplier_phone).replace(/[^0-9]/g, "")}?text=${msg}">WhatsApp them</a>` : "";
    const mail = o.supplier_email
      ? `<a class="btn ghost sm" href="mailto:${esc(o.supplier_email)}?subject=${encodeURIComponent("Order " + o.po_number)}&body=${msg}">Email them</a>` : "";
    return `<div class="po-row">
        <div class="po-who">${who}</div>
        <div class="po-facts muted tiny">${fmt(o.total_qty || 0)} units${o.total_amount != null ? " · about " + _rupee(o.total_amount) : ""}</div>
        <div class="po-acts">
          <button class="btn primary sm" data-podl="${esc(o.po_number)}">Open the form</button>
          ${wa}${mail}
        </div>
      </div>`;
  }).join("");

  openModal("Order forms ready", `
    <p class="muted">One form per supplier, with the quantities already worked out.
      Open it, check it, send it.</p>
    <div class="po-list">${rows}</div>
    <div class="row" style="display:flex;justify-content:flex-end;margin-top:14px;">
      <button class="btn primary" data-mclose>Done</button>
    </div>`, { wide: true });
  document.querySelectorAll("[data-podl]").forEach((b) => b.onclick = () =>
    download(`/api/supply/po/${encodeURIComponent(b.dataset.podl)}/pdf`, `${b.dataset.podl}.pdf`));
  document.querySelectorAll(".modal-body [data-mclose]").forEach((b) => b.onclick = closeModal);
}

// ---------- MODULE: Sales Analytics ----------
async function openSales() {
  await openCached("sales", "Sales Analytics",
    async () => {
      await api("/api/smart/state");
      // Cancellations come from your own website's orders, and they are already
      // out of the revenue figure beside them — fetched together so the page
      // paints once.
      const [d, cx] = await Promise.all([
        api("/api/analytics?lang=en"),
        api("/api/cancellations").catch(() => null),
      ]);
      return { d, cx };
    }, renderSales);
}

function renderSales(payload) {
  const { d, cx } = payload;
  {
    const k = d.kpis;
    const rowCount = (state.data && state.data.sales && state.data.sales.rows) || 0;
    const thin = rowCount > 0 && rowCount < THIN_DATA_ROWS;

    // The headline cards are COUNTS AND SUMS of what the seller uploaded. They
    // are exactly as true at 6 orders as at 6,000 — nothing is being inferred.
    // Hiding them behind a "not enough data" screen (which is what used to
    // happen) told a seller who had just finished their first upload that the
    // app could not even add up their own sales. What genuinely needs volume is
    // the *inference* — a trend line, a weekday pattern, a 30-day forecast —
    // and that, and only that, is what gets held back now.
    const cards = `
      <div class="kpis">
        <div class="kpi"><div class="label">Revenue</div><div class="value">₹${fmt(k.revenue)}</div></div>
        <div class="kpi"><div class="label">Orders</div><div class="value">${fmt(k.orders)}</div></div>
        <div class="kpi"><div class="label">Customers</div><div class="value">${fmt(k.customers)}</div></div>
        <div class="kpi"><div class="label">Average order</div><div class="value">₹${fmt(k.avg_order_value)}</div></div>
        ${cancelKpi(cx)}
      </div>`;

    if (thin) {
      moduleShell("Sales Analytics", cards + cancelPanel(cx) + renderActions(d.insights)
        + thinData(rowCount, THIN_DATA_ROWS,
                   "your revenue trend, your best days of the week and next month's forecast",
                   false));
      bindCancelPanel(cx);
      return;
    }

    let html = cards + `
      ${cancelPanel(cx)}
      ${renderActions(d.insights)}
      <div class="chart-card"><h4>Monthly revenue</h4><div class="plot" id="cMonthly"></div></div>
      ${d.forecast ? `<div class="chart-card"><h4>Next 30 days: ≈ ₹${fmt(d.forecast.next_30_total)} (${d.forecast.vs_last_30_pct >= 0 ? "+" : ""}${d.forecast.vs_last_30_pct}% vs last 30)</h4><div class="plot" id="cFcst"></div></div>` : ""}
      <div class="grid-2">
        ${d.by_category ? `<div class="chart-card"><h4>Revenue by category</h4><div class="plot" id="cCat"></div></div>` : ""}
        <div class="chart-card"><h4>Revenue by weekday</h4><div class="plot" id="cWk"></div></div>
      </div>
      ${d.top_products ? `<div class="chart-card"><h4>Top products</h4><div class="plot" id="cTop"></div></div>` : ""}`;
    moduleShell("Sales Analytics", html);
    bindCancelPanel(cx);
    const primary = cssVar("--primary", "#6d28d9");
    plot($("cMonthly"), [{ x: d.monthly_trend.x, y: d.monthly_trend.y, type: "scatter", mode: "lines+markers", line: { color: primary, width: 2.5, shape: "spline" }, fill: "tozeroy", fillcolor: softFill() }], { yaxis: { tickprefix: "₹" } }, "Monthly revenue");
    if (d.forecast) {
      const f = d.forecast;
      plot($("cFcst"), [
        { x: f.hist_x, y: f.hist_y, type: "scatter", mode: "lines", name: "Actual", line: { color: primary, width: 2.5 } },
        { x: f.fcst_x, y: f.fcst_y, type: "scatter", mode: "lines", name: "Forecast", line: { color: cssVar("--green", "#0a7a4d"), width: 2.5, dash: "dash" } },
      ], { yaxis: { tickprefix: "₹" } }, "30-day forecast");
    }
    if (d.by_category) plot($("cCat"), [{ x: d.by_category.x, y: d.by_category.y, type: "bar", marker: { color: primary } }], { yaxis: { tickprefix: "₹" } }, "Revenue by category");
    plot($("cWk"), [{ x: d.weekday_pattern.x, y: d.weekday_pattern.y, type: "bar", marker: { color: series(1) } }], { yaxis: { tickprefix: "₹" } }, "Revenue by weekday");
    if (d.top_products) plot($("cTop"), [{ x: d.top_products.x, y: d.top_products.y, type: "bar", orientation: "h", marker: { color: series(2) } }], { xaxis: { tickprefix: "₹" }, yaxis: { autorange: "reversed" }, margin: { l: 150, r: 20, t: 8, b: 40 } }, "Top products");
  }
}

/* ---------------------------------------------------------- cancellations --
   The number the seller asked for: how many orders were cancelled and what
   they were worth. It sits beside Revenue on purpose — the revenue figure has
   these already taken out, and showing the two apart is how sellers end up
   believing their sales dropped. */
function cancelKpi(cx) {
  if (!cx || !cx.available) return "";
  const rate = cx.rate != null ? ` · ${cx.rate}%` : "";
  return `
    <div class="kpi kpi-warn" id="cancelKpi" title="Click for the breakdown">
      <div class="label">Cancelled${rate}</div>
      <div class="value">₹${fmt(cx.cancelled_value)}</div>
      <div class="kpi-sub">${fmt(cx.cancelled)} order${cx.cancelled === 1 ? "" : "s"}
        of ${fmt(cx.orders)}</div>
    </div>`;
}

function cancelPanel(cx) {
  if (!cx || !cx.available || !cx.cancelled) return "";
  const bar = (rows, total) => rows.map((r) => `
    <div class="cx-row">
      <span class="cx-lbl">${esc(r.label)}</span>
      <span class="cx-bar"><i style="width:${total ? (r.orders / total * 100) : 0}%"></i></span>
      <span class="cx-n">${fmt(r.orders)}</span>
      <span class="cx-v">₹${fmt(r.value)}</span>
    </div>`).join("");

  const coverage = cx.reason_coverage;
  const gap = coverage != null && coverage < 100;

  return `
    <div class="card cx-card" id="cancelPanel">
      <div class="cx-head">
        <div>
          <h4 style="margin:0 0 4px;">Cancellations</h4>
          <p class="muted tiny" style="margin:0;">${esc(cx.headline)}</p>
        </div>
        <button class="btn ghost tiny" id="cxToggle">Show breakdown</button>
      </div>

      <div id="cxBody" hidden>
        <p class="muted tiny cx-note">${esc(cx.note)}</p>
        ${!cx.enough_data ? `<p class="muted tiny cx-note">
          Only ${fmt(cx.orders)} orders so far, too few for percentages to mean
          anything, so this shows counts and rupees. Rates appear from
          ${cx.min_denominator} orders.</p>` : ""}

        <div class="cx-sub">How far they had got</div>
        <p class="muted tiny cx-note">Cancelling before packing costs you the sale.
          Cancelling after dispatch costs freight both ways and a week of stock.</p>
        ${bar(cx.stages, cx.cancelled)}

        <div class="cx-sub">Why</div>
        ${gap ? `<p class="muted tiny cx-note">Only ${coverage}% of these have a
          reason recorded. Pick one when you cancel an order and this becomes
          the most useful chart on the page.</p>` : ""}
        ${bar(cx.reasons, cx.cancelled)}

        ${(cx.by_payment || []).length > 1 ? `
          <div class="cx-sub">Cash on delivery vs paid online</div>
          <p class="muted tiny cx-note">Across India, cash-on-delivery orders fail
            far more often than prepaid ones, Shipway's FY25 data puts COD
            return-to-origin at 26% against under 2% for prepaid. Your own split
            is below.</p>
          <div class="cx-pay">
            ${cx.by_payment.map((p) => `
              <div class="cx-pay-cell">
                <b>${esc(p.label)}</b>
                <span>${fmt(p.cancelled)} of ${fmt(p.orders)} cancelled${p.rate != null ? ` · ${p.rate}%` : ""}</span>
                <i>₹${fmt(p.value)}</i>
              </div>`).join("")}
          </div>` : ""}

        ${(cx.by_product || []).length ? `
          <div class="cx-sub">Which products</div>
          ${bar(cx.by_product, cx.cancelled)}` : ""}

        ${(cx.trend.x || []).length > 1
          ? `<div class="cx-sub">Week by week</div><div class="plot" id="cxTrend"></div>`
          : ""}
      </div>
    </div>`;
}

function bindCancelPanel(cx) {
  const k = $("cancelKpi"), t = $("cxToggle"), body = $("cxBody");
  if (!t || !body) return;
  const open = () => {
    body.hidden = !body.hidden;
    t.textContent = body.hidden ? "Show breakdown" : "Hide breakdown";
    if (!body.hidden && cx && (cx.trend.x || []).length > 1 && $("cxTrend")) {
      plot($("cxTrend"), [
        { x: cx.trend.x, y: cx.trend.orders, type: "bar", name: "Orders",
          marker: { color: cssVar("--primary", "#5c6790") } },
        { x: cx.trend.x, y: cx.trend.cancelled, type: "bar", name: "Cancelled",
          marker: { color: cssVar("--amber", "#96702f") } },
      ], { barmode: "overlay" }, "Cancellations by week");
    }
  };
  t.onclick = open;
  if (k) k.onclick = open;
}

// ---------- MODULE: Sub-Category Analysis ----------
async function openSubcategory() {
  await openCached("subcategory", "Sub-Category Analysis",
    async () => {
      await api("/api/smart/state");
      return api("/api/subcategory?lang=en");
    }, renderSubcategory);
}

function renderSubcategory(d) {
  {
    const rowCount = (state.data && state.data.sales && state.data.sales.rows) || 0;
    // Same rule as Sales Analytics: the cards are sums of the seller's own rows
    // and are always shown; only the trend charts wait for enough history.
    const cards = (d.cards || []).length ? `
      <div class="kpis">${d.cards.map((c) => `
        <div class="kpi"><div class="label">${esc(c.label)}</div>
          <div class="value">${esc(String(c.value))}</div>
          ${c.note ? `<div class="muted tiny">${esc(c.note)}</div>` : ""}</div>`).join("")}
      </div>` : "";
    if (!d.available) {
      moduleShell("Sub-Category Analysis", cards + `<div class="card">${esc(d.reason || "")}</div>`
        + thinData(rowCount, THIN_DATA_ROWS,
                   "which kinds of product bring the money in", !cards));
      return;
    }
    const label = d.field === "subcategory" ? "sub-categories" : "categories";
    if (rowCount > 0 && rowCount < THIN_DATA_ROWS) {
      moduleShell("Sub-Category Analysis", cards + renderActions(d.insights)
        + thinData(rowCount, THIN_DATA_ROWS,
                   `how each of your ${label} is trending month to month`, false));
      return;
    }
    let html = cards + `
      <div class="row" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px;">
        <span class="muted">Drill into a ${d.field === "subcategory" ? "sub-category" : "category"}:</span>
        <select id="subSel" class="sub-select"><option value="">All (overview)</option>${d.all_values.map((v) => `<option>${esc(v)}</option>`).join("")}</select>
      </div>
      ${renderActions(d.insights)}
      <div class="chart-card"><h4>Monthly trend: top ${label}</h4><div class="plot" id="cSubTrend"></div></div>
      <div class="chart-card"><h4>Total revenue by ${label}</h4><div class="plot" id="cSubTot"></div></div>`;
    moduleShell("Sub-Category Analysis", html);
    $("subSel").onchange = () => $("subSel").value ? renderSubDetail($("subSel").value) : openSubcategory();
    plot($("cSubTrend"), d.series.map((s) => ({ x: s.x, y: s.y, name: s.name, type: "scatter", mode: "lines+markers" })), { yaxis: { tickprefix: "₹" } }, "Monthly trend");
    plot($("cSubTot"), [{ x: d.totals.x, y: d.totals.y, type: "bar", marker: { color: cssVar("--primary", "#6d28d9") } }], { yaxis: { tickprefix: "₹" } }, "Total revenue");
  }
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
      <div class="chart-card"><h4>${esc(value)}, monthly revenue</h4><div class="plot" id="cDT"></div></div>
      <div class="grid-2">
        <div class="chart-card"><h4>Revenue by weekday</h4><div class="plot" id="cDW"></div></div>
        ${d.top_products ? `<div class="chart-card"><h4>Top items</h4><div class="plot" id="cDP"></div></div>` : ""}
      </div>`;
    setView(`<div class="page-head"><h2>Sub-Category Analysis</h2><button class="btn ghost sm" id="backHome">← All apps</button></div>${html}`);
    $("backHome").onclick = goHome; $("subBack").onclick = openSubcategory;
    plot($("cDT"), [{ x: d.monthly_trend.x, y: d.monthly_trend.y, type: "scatter", mode: "lines+markers", fill: "tozeroy", fillcolor: softFill(), line: { color: cssVar("--primary", "#6d28d9") } }], { yaxis: { tickprefix: "₹" } }, value + " monthly");
    plot($("cDW"), [{ x: d.weekday_pattern.x, y: d.weekday_pattern.y, type: "bar", marker: { color: series(1) } }], { yaxis: { tickprefix: "₹" } }, "Weekday");
    if (d.top_products) plot($("cDP"), [{ x: d.top_products.x, y: d.top_products.y, type: "bar", orientation: "h", marker: { color: series(2) } }], { xaxis: { tickprefix: "₹" }, yaxis: { autorange: "reversed" }, margin: { l: 150, r: 20, t: 8, b: 40 } }, "Top items");
  } catch (e) { toast(e.message); }
}

// ---------- MODULE: Review Analytics (self positioning, no peer comparison) ----------
async function openReview() {
  await openCached("review", "Review Analytics",
    () => api("/api/smart/positioning?lang=en"), renderReview);
}

function renderReview(d) {
  {
    if (!d.available) { moduleShell("Review Analytics", `<div class="card">${esc(d.reason || "Not enough review data.")}</div>`); return; }
    const pos = d.position || {};
    const html = `
      ${renderActions(d.insights)}
      <div class="card pos-banner"><span class="muted tiny">Your position, from your own reviews</span>
        <h3 style="margin:4px 0 0;"> ${esc(pos.quadrant || "–")}</h3></div>
      <div class="kpis">
        <div class="kpi"><div class="label">Reviews</div><div class="value">${fmt(d.n_reviews)}</div></div>
        <div class="kpi"><div class="label">Your rating</div><div class="value">${d.avg_rating ?? "–"}</div></div>
        <div class="kpi"><div class="label">Sentiment</div><div class="value">${d.overall_sentiment > 0 ? "+" : ""}${d.overall_sentiment}</div></div>
      </div>
      <div class="chart-card"><h4>What your customers talk about (% of reviews)</h4><div class="plot" id="cShare"></div></div>
      <div class="chart-card"><h4>How positively they talk about it (sentiment)</h4><div class="plot" id="cSent"></div></div>`;
    moduleShell("Review Analytics", html);
    const primary = cssVar("--primary", "#6d28d9");
    plot($("cShare"), [{ x: d.share_chart.themes, y: d.share_chart.yours, type: "bar", marker: { color: primary } }], { margin: { l: 46, r: 16, t: 8, b: 120 }, xaxis: { tickangle: -35 } }, "What customers talk about");
    plot($("cSent"), [{ x: d.sentiment_chart.themes, y: d.sentiment_chart.yours, type: "bar", marker: { color: series(1) } }], { margin: { l: 46, r: 16, t: 8, b: 120 }, xaxis: { tickangle: -35 } }, "Sentiment by theme");
  }
}

// ---------- MODULE: Complaint Analysis ----------
async function openComplaints() {
  await openCached("complaints", "Complaint Analysis",
    () => api("/api/smart/complaints"), renderComplaints);
}

function renderComplaints(d) {
  {
    const det = d.detected || {};
    let html = `<p class="muted">${fmt(det.n_reviews)} reviews · ${fmt(det.n_complaints)} complaints (${det.complaint_rate ?? 0}% rate)</p>`;
    const focus = (d.focus && d.focus.focus_now) || [];
    if (focus.length) {
      html += `<div class="card"><h4> Fix these first</h4>${focus.map((x, i) => `
        <div class="action-card negative"><div class="do">${i + 1}. ${esc(x.theme)} – ${esc(x.severity)}</div>
        <div class="why"> ${esc(x.action)} · ${x.count} complaints (${x.share_pct}%)</div></div>`).join("")}</div>`;
    } else {
      html += `<div class="card"> No significant complaint patterns found.</div>`;
    }
    if (d.monthly) {
      html += `<div class="chart-card"><h4> Complaints per month (avg ${d.monthly.avg_per_month}/mo)</h4><div class="plot" id="cCompM"></div></div>`;
    }
    if (d.deep && d.deep.length) {
      html += `<div class="card"><h4 style="margin-bottom:8px;">Deep analysis</h4>
        <div class="table-scroll"><table><thead><tr><th>Theme</th><th>Complaints</th><th>Share</th><th>Severity</th><th>Example</th></tr></thead>
        <tbody>${d.deep.map((r) => `<tr><td><b>${esc(r.theme)}</b></td><td>${r.count}</td><td>${r.share_pct}%</td><td>${esc(r.severity)}</td><td class="muted">"${esc(r.example)}…"</td></tr>`).join("")}</tbody></table></div></div>`;
    }
    moduleShell("Complaint Analysis", html);
    if (d.monthly) plot($("cCompM"), [{ x: d.monthly.months, y: d.monthly.counts, type: "bar", marker: { color: "#f97316" } }], {}, "Complaints per month");
  }
}

// ---------- MODULE: Position Strategy + AI ----------
async function openStrategy() {
  await openCached("strategy", "Position Strategy + AI",
    async () => {
      try { return await api("/api/smart/strategy/detect?lang=en", { method: "POST" }); }
      catch (e) {
        const d = await api("/api/position-strategy");
        if (!d.detected) throw e;
        return d;
      }
    },
    renderStrategy,
    // Detection runs an analysis pass, so the empty state has to explain where
    // the input comes from rather than just showing a failure.
    (msg) => `<div class="card">${esc(msg)}<br><br>Upload your reviews in <b>Review Analytics</b> first, the strategy is detected from them.</div>`);
}

function posCard(p, eyebrow) {
  return `<div class="card" style="border-left:4px solid var(--primary);">
    <div class="section-title" style="margin:0;">${esc(eyebrow)}</div>
    <h3 style="margin:2px 0 2px;">${esc(p.name)}</h3>
    <div class="muted" style="font-size:13px;">${esc(p.tagline)}</div>
    <div class="grid-2" style="margin-top:12px;">
      <div><b style="color:var(--green);"> Pros</b><ul style="margin:6px 0 0;padding-left:18px;font-size:13px;color:var(--text-2);">${p.pros.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div><b style="color:var(--red);">⚠️ Cons</b><ul style="margin:6px 0 0;padding-left:18px;font-size:13px;color:var(--text-2);">${p.cons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    </div></div>`;
}

function renderStrategy(d) {
  let html = posCard(d.current, `You are here${d.n_reviews ? ` · from ${d.n_reviews} reviews` : ""}`);
  html += `<div class="section-title">Choose a target: or strengthen where you are</div>
    <div class="apps-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));">
    ${d.options.map((o) => `<div class="app-tile opt-tile ${o.id === d.target_id ? "selected" : ""}" data-target="${o.id}" style="text-align:left;">
        <div class="opt-diff ${o.is_current ? "stay" : (o.axes_changing === 1 ? "adj" : "big")}">${esc(o.difficulty)}</div>
        <div class="name" style="margin-top:5px;">${esc(o.name)}${o.is_current ? " ★" : ""}</div>
        <div class="sub">${esc(o.tagline)}</div>
      </div>`).join("")}</div>`;

  if (d.plan) {
    const pl = d.plan; const pct = pl.progress.total ? Math.round(pl.progress.done / pl.progress.total * 100) : 0;
    if (!pl.same_position) html += posCard(pl.target, "Your target");
    html += `<div class="card" style="border-left:4px solid var(--blue);"><b style="color:var(--blue);">${pl.same_position ? "Plan:" : "The gap:"}</b> ${esc(pl.gap)}</div>`;
    html += `<div class="card" style="border-left:4px solid var(--green);"><h4 style="color:var(--green);">Keep these the same</h4>
      <p class="muted tiny" style="margin:4px 0;">${esc(pl.keep_note)}</p>
      <ul style="margin:8px 0 0;padding-left:18px;font-size:13px;color:var(--text-2);">${pl.keep_same.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    html += `<div class="section-title">Your levelled checklist: ${pl.progress.done}/${pl.progress.total} (${pct}%)</div>
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
        <div class="level-head"><span class="level-badge">Level ${lv}</span> ${esc(phaseName.replace(/^Level \d+ · /, ""))} <span class="muted tiny">${doneByLevel[lv] || 0}/${totByLevel[lv]}</span>${locked ? ` <span class="lock-note"> finish Level ${lv - 1} first</span>` : (levelDone ? ` <span style="color:var(--green);">✓ done</span>` : "")}</div>`;
      items.forEach((it) => {
        html += `<label class="task-item ${it.done ? "done" : ""}" data-item="${it.id}" data-level="${lv}" style="align-items:flex-start;border:1px solid var(--border);border-radius:8px;padding:11px 13px;margin-bottom:8px;background:var(--surface);${locked ? "opacity:.55;pointer-events:none;" : ""}">
          <input type="checkbox"${it.done ? "checked" : ""} ${locked ? "disabled" : ""} style="margin-top:2px;" />
          <span class="t"><b>${esc(it.text)}</b><div class="muted tiny" style="margin-top:3px;">Why: ${esc(it.why)}</div></span></label>`;
      });
      html += `</div>`;
      prevComplete = prevComplete && levelDone;
    });
  }

  html += `<div class="section-title">AI</div>
    <div class="card"><div class="row" style="display:flex;gap:10px;flex-wrap:wrap;">
      <button class="btn primary sm" id="runAnalyst"> Run AI Analyst</button>
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
    out.innerHTML = d.results.map((file) => `<h4> ${esc(file.file)}</h4>` + file.insights.map((ins) => `
      <div class="action-card"><div class="do"> ${esc(ins.decision || "")}</div>
      <div class="why"><b>Action:</b> ${esc(ins.action || "")}<br><b>Impact:</b> ${esc(ins.impact || "")}</div></div>`).join("")).join("");
    if (!out.innerHTML) out.innerHTML = `<div class="ap-empty">No insights generated.</div>`;
  } catch (e) { out.innerHTML = `<div class="card">${esc(e.message)}</div>`; }
  btn.disabled = false;
}

function renderActions(insights) {
  if (!insights || !insights.length) return "";
  return `<div style="margin-bottom:14px;">${insights.map((ins) => {
    const type = ["positive", "negative", "warning", "neutral"].includes(ins.type) ? ins.type : "neutral";
    return `<div class="action-card ${type}">${ins.action ? `<div class="do"> ${esc(ins.action)}</div><div class="why">${esc(ins.text)}</div>` : `<div class="do">${esc(ins.text)}</div>`}</div>`;
  }).join("")}</div>`;
}

// ---------- MODULE: Marketing ----------
// Win-back used to surface only as an Approval-panel card, and only when the
// insight engine decided to generate one -- so a seller who wanted to check
// on it between those moments had nowhere to go. This gives it a permanent
// home: open it any time and it fetches the current at-risk list itself,
// same endpoint the panel card uses, no waiting for an insight to appear.
async function openMarketing() {
  await openCached("marketing", "Marketing",
    async () => {
      const [wb, proof, sends, auto] = await Promise.all([
        api("/api/rfm/winback", { method: "POST" }).catch((e) => ({ customers: [], _error: e.message })),
        api("/api/rfm/winback/proof").catch(() => null),
        api("/api/rfm/winback/sends").catch(() => null),
        api("/api/winback/auto").catch(() => null),
      ]);
      return { wb, proof, sends, auto };
    },
    (d) => renderMarketing(d.wb, d.proof, d.sends, d.auto));
}

/* ------------------------------------------- the weekly win-back strip -----
   Win-back used to be a thing the seller had to remember to do. Nobody
   remembers on a Tuesday, and a customer who went quiet 70 days ago is
   reachable while the same customer at 140 days is a stranger — so the value
   of the feature was mostly theoretical.

   It now runs itself weekly and leaves ONE card in the Approval panel. This
   strip is where that schedule is visible and changeable, and where the
   cooldown is stated: without saying it out loud, a seller cannot tell the
   difference between "we are being careful with your customers" and "it is
   broken and only found four people". */
function winbackStrip(a) {
  if (!a) return "";
  const hr = (h) => { const n = Number(h) || 0; return `${((n + 11) % 12) + 1}${n < 12 ? "AM" : "PM"}`; };
  const p = a.pending;
  const last = a.last || null;
  const head = p
    ? `<b>${fmt(p.reachable || p.n)} message${(p.reachable || p.n) === 1 ? "" : "s"} are written and waiting for you</b>
       <span class="muted tiny">Prepared ${esc(String(p.at || "").slice(0, 10))}. Approve them in the panel on the right and they go out from your own email address.${
         p.skipped_cooldown ? `${fmt(p.skipped_cooldown)} more were left out, they were contacted within the last ${a.cooldown_days} days.` : ""}</span>`
    : a.enabled
      ? `<b>Checks every ${esc(a.day_name)} at ${esc(hr(a.hour))}${a.tz_label ? `${esc(a.tz_label)}` : ""}</b>
         <span class="muted tiny">It reads your sales for customers who have gone quiet, writes each message against what that person actually bought, and puts one card in your Approval panel. Nothing is ever sent until you approve it. Anyone contacted in the last ${a.cooldown_days} days is left alone.
           ${last && !last.ok && last.reason ? `Last check: ${esc(last.reason)}.` : ""}
           ${a.next_run_label ? `Next check ${esc(a.next_run_label)}.` : ""}</span>`
      : `<b>Automatic win-back is off</b>
         <span class="muted tiny">Turn it on and it finds your quiet customers every week for you.</span>`;
  return `
    <div class="ap-strip ${p ? "on" : (a.enabled ? "on" : "off")}">
      <div class="ap-strip-t">${sic(p ? "bell" : "clock")}<div>${head}</div></div>
      <div class="ap-strip-a">
        ${p ? `<button class="btn ghost sm" id="wbaSkip" title="Throw this batch away, these customers stay eligible next week">Skip this week</button>`
            : `<button class="btn primary sm" id="wbaRun">${sic("refresh")}Check now</button>`}
        <button class="btn ghost sm" id="wbaChange">${sic("settings")}${a.enabled ? "Change day" : "Turn on"}</button>
      </div>
    </div>`;
}

function wireWinbackStrip() {
  const run = $("wbaRun");
  if (run) run.onclick = async () => {
    run.disabled = true; run.textContent = "Checking…";
    try {
      const r = await api("/api/winback/auto/run", { method: "POST" });
      const res = r.run || {};
      toast(res.ok ? `${res.reachable || res.n} customers ready, approve them in the panel`
                   : `Nothing to send: ${res.reason || "no one has gone quiet"}`, 6000);
      warmModClearAll();
      openMarketing();
      refreshApprovals(true);
    } catch (e) { toast(e.message, 6000); run.disabled = false; }
  };
  const skip = $("wbaSkip");
  if (skip) skip.onclick = async () => {
    if (!confirm("Throw away this week's win-back batch? Nothing is sent, and these customers will be eligible again next week.")) return;
    try {
      await api("/api/winback/auto/skip", { method: "POST" });
      toast("Skipped. Nobody was contacted.");
      warmModClearAll();
      openMarketing();
      refreshApprovals(true);
    } catch (e) { toast(e.message, 6000); }
  };
  const ch = $("wbaChange");
  if (ch) ch.onclick = openWinbackAutoSetup;
}

async function openWinbackAutoSetup() {
  let a;
  try { a = await api("/api/winback/auto"); } catch (e) { return toast(e.message); }
  const days = (a.day_names || []).map((d, i) =>
    `<option value="${i}"${i === a.day ? "selected" : ""}>${esc(d)}</option>`).join("");
  const hours = Array.from({ length: 24 }, (_, h) =>
    `<option value="${h}"${h === a.hour ? "selected" : ""}>${((h + 11) % 12) + 1}${h < 12 ? "AM" : "PM"}</option>`).join("");
  openModal("Automatic win-back", `
    <label class="site-toggle" style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
      <input type="checkbox" id="wbaOn"${a.enabled ? "checked" : ""} />
      <span class="tsw"></span><b>Look for quiet customers every week</b>
    </label>
    <div class="grid-2">
      <label>Day <select id="wbaDay">${days}</select></label>
      <label>Time <select id="wbaHour">${hours}</select></label>
    </div>
    <p class="muted tiny" style="margin-top:10px;">Times are ${esc(a.tz_label || "your local time")}.
      Anyone already contacted in the last ${a.cooldown_days} days is skipped, so the same
      customer never gets two of these close together. Nothing is sent without your approval.</p>
    <div class="row" style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px;">
      <button class="btn ghost" data-mclose2>Cancel</button>
      <button class="btn primary" id="wbaSave">Save</button>
    </div>`);
  document.querySelector("[data-mclose2]").onclick = closeModal;
  $("wbaSave").onclick = async () => {
    try {
      await api("/api/winback/auto", { method: "POST", json: {
        enabled: $("wbaOn").checked,
        day: Number($("wbaDay").value),
        hour: Number($("wbaHour").value),
      }});
      closeModal();
      toast("Saved");
      warmModClearAll();
      openMarketing();
    } catch (e) { toast(e.message, 6000); }
  };
}

function renderMarketing(wb, proof, sends, auto) {
  const rows = (wb && wb.customers) || [];
  const sendRows = (sends && sends.sends) || [];

  const proofLine = proof && proof.headline && proof.totals && proof.totals.contacted
    ? `<div class="today-proof">${sic("trend")}<span>${esc(proof.headline)}</span>
         <button class="btn ghost tiny" id="mkProofMore">How this is counted</button></div>`
    : "";

  let body;
  if (wb && wb._error) {
    body = `<div class="ap-empty">${esc(wb._error)}</div>`;
  } else if (!rows.length) {
    body = `<div class="ap-empty">No customers are at risk of going quiet right now,
      nice work. This list is built from your order history, so check back as it grows.</div>`;
  } else {
    body = `
      <div class="card mk-card">
        <h4 style="margin:0 0 4px;">${rows.length} customer${rows.length === 1 ? "" : "s"} have gone quiet</h4>
        <p class="muted tiny" style="margin:0 0 12px;">Each one gets a written message
          with their favourite item and a coupon, you edit every row before anything sends.</p>
        <ul class="mk-list">
          ${rows.slice(0, 8).map((r) => `<li><b>${esc(r.customer_name || "Customer")}</b>
            <span class="muted tiny">${esc(r.favorite_item || "")}${r.favorite_item ? " · " : ""}last order ${esc(r.last_purchase_date || "–")}</span></li>`).join("")}
        </ul>
        ${rows.length > 8 ? `<p class="muted tiny">+ ${rows.length - 8} more</p>` : ""}
        <button class="btn primary" id="mkReview">Review &amp; send</button>
      </div>`;
  }

  const pastCampaigns = sendRows.length ? `
    <details class="sm-fold">
      <summary>Past campaigns (${sendRows.length})</summary>
      <div class="mk-sends">
        ${sendRows.slice(0, 20).map((s) => `
          <div class="mk-send-row">
            <b>${esc((s.channels || []).join(" + ") || "–")}</b>
            <span class="muted tiny">${esc(String(s.at || "").slice(0, 10))}
              · ${fmt(s.recipients || 0)} sent
              ${s.skipped ? ` · ${fmt(s.skipped)} skipped (no email/phone)` : ""}</span>
          </div>`).join("")}
      </div>
    </details>` : "";

  moduleShell("Marketing", `
    <p class="muted" style="margin-top:0;">Win-back campaigns for customers who used to
      buy from you and have gone quiet, written and ready, one tap to send.</p>
    ${winbackStrip(auto)}
    ${proofLine}
    ${body}
    ${pastCampaigns}`);

  wireWinbackStrip();
  const m = $("mkProofMore");
  if (m) m.onclick = () => toast(proof.method, 7000);
  const rv = $("mkReview");
  if (rv) rv.onclick = openWinbackEditor;
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
    <td><button class="btn ghost tiny" data-del="${i}" title="Remove this row" aria-label="Remove this row">${sic("close")}</button></td></tr>`).join("");
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
    // The app used to hand over an Excel file and stop, leaving the seller to
    // open WhatsApp and type. Now it can send.
    openWinbackSend(_wbRows.slice());
  } catch (e) { toast(e.message, 6000); }
};

/* Send the campaign — email for real, WhatsApp through a provider when one is
   connected and as tap-to-send links until then. Recording it for measurement
   happens automatically, so "did you send it" stops being a question. */
async function openWinbackSend(rows) {
  let pv;
  try { pv = await api("/api/rfm/winback/preview", { method: "POST", json: { rows } }); }
  catch (e) { return askWinbackSent(rows); }

  const withEmail = rows.filter((r) => (r.email || r.customer_email || "").trim()).length;
  const withPhone = rows.filter((r) => (r.phone || r.customer_phone || "").trim()).length;

  openModal(`Send to ${rows.length} customer${rows.length === 1 ? "" : "s"}`, `
    <p class="muted" style="margin-top:0;">These are the customers who have gone
      quiet. One message is the cheapest revenue you will find this week, and we
      measure what comes back.</p>

    <div class="wb-ch">
      <label class="wb-c"><input type="checkbox" id="wbEmail" checked ${withEmail ? "" : "disabled"} />
        <span><b>Email</b><i>${withEmail} of ${rows.length} have an address${
          pv.email_ready ? "" : " · needs SMTP set up on the server"}</i></span></label>
      <label class="wb-c"><input type="checkbox" id="wbWa" checked ${withPhone ? "" : "disabled"} />
        <span><b>WhatsApp</b><i>${withPhone} of ${rows.length} have a number${
          pv.whatsapp_live ? "" : " · no provider connected, so you'll get tap-to-send links"}</i></span></label>
    </div>

    <label class="fld"><span>The message</span>
      <textarea id="wbTpl" data-ai="message" data-ai-label="Win-back message (keep the {name} placeholders)" rows="5">${esc(pv.template)}</textarea></label>
    <p class="muted tiny">{name} {brand} {item} {days} {coupon} are filled in per
      customer. Here is the first one:</p>
    <div class="wb-prev" id="wbPrev">${esc((pv.preview[0] || {}).message || "")}</div>

    <div class="modal-actions">
      <button class="btn ghost" id="wbLater">Not now</button>
      <button class="btn primary" id="wbGo">Send</button>
    </div>`);

  const repaint = () => {
    const t = $("wbTpl").value;
    api("/api/rfm/winback/preview", { method: "POST", json: { rows, template: t } })
      .then((r) => { const n = $("wbPrev"); if (n) n.textContent = (r.preview[0] || {}).message || ""; })
      .catch(() => {});
  };
  let tmr; $("wbTpl").addEventListener("input", () => { clearTimeout(tmr); tmr = setTimeout(repaint, 400); });

  $("wbLater").onclick = () => { closeModal(); toast("Exported & approved, moved to History."); };
  $("wbGo").onclick = async () => {
    const ch = [];
    if ($("wbEmail").checked && !$("wbEmail").disabled) ch.push("email");
    if ($("wbWa").checked && !$("wbWa").disabled) ch.push("whatsapp");
    if (!ch.length) { toast("Pick at least one channel."); return; }
    const b = $("wbGo"); b.disabled = true; b.textContent = "Sending…";
    try {
      const r = await api("/api/rfm/winback/send", { method: "POST",
        json: { rows, template: $("wbTpl").value, channels: ch } });
      closeModal();
      showWinbackResult(r);
      renderProof();
    } catch (e) { toast(e.message); b.disabled = false; b.textContent = "Send"; }
  };
}

function showWinbackResult(r) {
  const links = (r.results || []).filter((x) => x.wa_link);
  openModal("Campaign sent", `
    <p style="margin-top:0;"><b>${esc(r.summary)}</b></p>
    ${links.length ? `
      <p class="muted tiny">No WhatsApp provider is connected yet, so these open
        WhatsApp with the message already written, tap each one and press send.
        Connect a provider and they will go on their own.</p>
      <div class="wb-links">${links.map((x) => `
        <a class="wb-link" href="${esc(x.wa_link)}" target="_blank" rel="noopener">
          ${sic("whatsapp")}<b>${esc(x.customer_name || x.phone)}</b>
          <span>${esc(x.phone)}</span></a>`).join("")}</div>` : ""}
    ${r.skipped ? `<p class="muted tiny">${r.skipped} customer${r.skipped === 1 ? " has" : "s have"}
      neither an email nor a phone number on file, so they could not be contacted.</p>` : ""}
    <p class="muted tiny">Recorded for measurement: Sales Analytics will show what
      comes back over the next 30 days.</p>
    <div class="modal-actions"><button class="btn primary" id="wbDone">Done</button></div>`, { wide: true });
  $("wbDone").onclick = closeModal;
}

function askWinbackSent(rows) {
  openModal("Did you send it?", `
    <p class="muted" style="margin-top:0;">Tell us when this campaign actually goes out and we can
    measure it: of the <b>${rows.length}</b> customers on this list, how many come back, and how
    much they spend, in the 30 days after.</p>
    <p class="muted tiny">Nothing is sent from here, you send it your own way. This is just the
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
      <button class="btn ghost" id="wbLater">Not yet: I'll tick it later</button>
      <button class="btn primary" id="wbSent">I've sent it</button>
    </div>`);
  $("wbLater").onclick = () => { closeModal(); toast("Exported & approved, moved to History."); };
  $("wbSent").onclick = async () => {
    try {
      const p = await api("/api/rfm/winback/sent", { method: "POST",
        json: { customers: rows, channel: $("wbCh").value } });
      closeModal();
      toast(p.headline || "Recorded: we'll measure it from today.", 6000);
      renderProof();
    } catch (e) { toast(e.message); }
  };
}

/* WHY THE SERVER'S LIST IS FILTERED ON THE WAY IN.
   A job in the queue has not reached the server yet, so the server still
   reports its insight as pending. Painting that list verbatim would put the
   card back on screen a second after the seller watched it leave — and then
   remove it again when the job lands. The card flickers, and a seller who
   taps the resurrected card approves the same thing twice.
   Anything currently in flight is held out until its job settles. If the job
   fails, the failure path puts the card back deliberately, with a reason. */
function withoutInFlight(insights) {
  if (!_jobs.length) return insights || [];
  const busy = new Set(_jobs.map((j) => j.id));
  return (insights || []).filter((i) => !busy.has(i.id));
}

/* WHY THIS COUNTS ITS OWN REQUESTS.
   This is called unawaited from several places at once, and the queue is busy
   hammering the same small server, so two reads of the app state overlap
   routinely. Without sequencing:
     t0  seller approves card A; a slow GET is already in flight, holding the
         list as it was at t0 — with A still pending on it
     t7  the job succeeds, a fresh GET goes out and paints the correct list
     t9  the SLOW one finally lands, overwrites everything, and paints A back
         as an ordinary undecided card with nothing to explain it
   The seller taps the resurrected card and pays for a second picture, or a
   supplier gets the same order twice. A response older than one already
   painted is stale by definition and is dropped. */
let _stateGen = 0;
async function refreshApprovals(silent) {
  const gen = ++_stateGen;
  try {
    const s = await api("/api/smart/state");
    if (gen !== _stateGen) return;          // a newer read already landed
    state.lastState = s;
    renderApprovals(s.insights);            // filters in-flight work itself
    prunePhantomFailures(s.insights);
    if (!silent) toast("Refreshed");
  } catch (e) { if (!silent) toast(e.message); }
}

/* A failure record outlives the card it belongs to, and insight ids repeat:
   "winback" is literally a fixed string, and a weekly plan can rehash a post
   to the same id. Without this, a nine-day-old failure from one win-back list
   attaches itself to next week's — sorted to the top as urgent, wearing a
   reason from work that was never attempted on it, its button reading "Try
   again" instead of "Approve". Whenever the server tells us what actually
   exists, anything else in the record is stale. */
function prunePhantomFailures(insights) {
  const live = new Set((insights || []).map((i) => i.id));
  let changed = false;
  for (const id of Object.keys(_failed)) {
    if (!live.has(id)) { delete _failed[id]; changed = true; }
  }
  if (changed) saveFailures();
}
$("refreshApprovals").onclick = () => refreshApprovals();

// ---------- MODULE: Instagram connection ----------
async function openInstagramModule() {
  moduleShell("Instagram", `<div class="ap-empty">Loading…</div>`);
  try {
    const s = await api("/api/instagram/status");
    const oauth = !!s.oauth_available;   // set by the admin via env vars
    const advancedHidden = oauth && !s.connected;  // hide the paste form behind a disclosure

    const connectPanel = oauth ? `
      <div class="row" style="display:flex;gap:10px;flex-wrap:wrap;">
        <button class="btn primary sm" id="igOauth"> Connect Instagram</button>
        <span class="muted tiny" style="align-self:center;">Opens Instagram's own login. Nothing to paste, and no Facebook Page needed.</span>
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
          <div class="muted tiny" style="margin-top:3px;">Ask the admin to set <code>META_APP_ID</code> and <code>META_APP_SECRET</code> env vars, then this page becomes a single "Connect Instagram" button. Until then, paste an access token below.</div>
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
            <h3 style="margin:0;">${s.connected ? "Connected" : "Not connected yet"}</h3>
            ${s.connected ? `<div class="muted tiny" style="margin-top:4px;">Account: <b>@${esc(s.account_username || "–")}</b> · IG user id: <code>${esc(s.ig_user_id)}</code> · since ${esc(String(s.connected_at || "").slice(0,10))}</div>`
                          : `<div class="muted tiny" style="margin-top:4px;">${oauth ? "Sign in at instagram.com with the password you already use, it never passes through us." : "Follow the steps below."}</div>`}
          </div>
          ${s.connected ? `<button class="btn ghost sm" id="igDisconnect">Disconnect</button>` : ""}
        </div>
        ${s.connected ? `
          <p class="muted tiny" style="margin-top:10px;">Approved posts on your
            calendar go out on this account at the time you scheduled them,
            reels as reels, photos as photos. Nothing is posted that you have
            not approved.</p>
          <div class="row" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px;">
            <button class="btn primary sm" id="igPreflight">${sic("check")}Check posting works</button>
            <span class="muted tiny">Tests the whole chain without putting anything on your profile.</span>
          </div>
          <div id="igPfMsg" style="margin-top:10px;"></div>
          <details class="ig-testpost">
            <summary>Or put a real test post up now</summary>
            <p class="muted tiny">This posts for real, immediately, on @${esc(s.account_username || "")}.
              Use it once to see a post actually appear with your caption. Delete it
              from Instagram afterwards, we cannot remove it for you.</p>
            <label>Caption
              <input id="igTpCap" placeholder="Testing our new posting setup." /></label>
            <label>Picture <span class="muted tiny">optional, leave blank for a plain test card</span>
              <input id="igTpUrl" placeholder="/generated_images/… or a public https link" /></label>
            <button class="btn ghost sm" id="igTpGo">${sic("instagram")}Post it now</button>
            <div id="igTpMsg" style="margin-top:8px;"></div>
          </details>` : connectPanel}
      </div>
      ${!s.connected ? `
      <div class="card">
        <h4>${oauth ? "What happens when you click Connect Instagram" : "How to set OAuth up (admin)"}</h4>
        ${oauth ? `
        <div class="ig-pre">
          <b>Two things to check first</b>
          <ol style="line-height:1.7;padding-left:18px;margin:6px 0 0;">
            <li><b>Your account must be Business or Creator.</b> Instagram app →
              Settings → Account type and tools → Switch to professional account.
              It is free and takes a minute. A personal account cannot connect,
              this is the reason almost every failed connection fails.</li>
            <li><b>If we are still in testing, accept the invite first.</b> You were
              added as a tester, and the invite has to be accepted before Instagram
              will allow the login: open
              <a href="https://www.instagram.com/accounts/manage_access_tools/" target="_blank" rel="noopener">instagram.com → Apps and websites → Tester invites</a>
              and press Accept. On a phone: Instagram app → Settings → Website
              permissions → Apps and websites → Tester invites. Nothing happens on
              facebook.com, this invite lives on Instagram.</li>
          </ol>
        </div>
        <b class="ig-then">Then press Connect Instagram, and:</b>
        <ol class="muted tiny" style="line-height:1.7;padding-left:18px;">
          <li>An Instagram login window opens, instagram.com, not us, and no Facebook Page anywhere.</li>
          <li>You sign in with the Instagram password you already use.</li>
          <li>Instagram asks whether to allow this app to see your profile, publish posts and read your insights. Press Allow.</li>
          <li>You land back here, connected. We store the access token encrypted, you never see it and neither does anyone else.</li>
        </ol>
        <p class="muted tiny" style="margin-top:8px;">Use a desktop browser if you can,
          and turn off any VPN or ad blocker for this one step, both are common causes of
          a login window that opens and then does nothing. Once Meta approves the app,
          the tester step disappears and this works for any Business or Creator account.</p>` : `
        <ol class="muted tiny" style="line-height:1.7;padding-left:18px;">
          <li>Create a Meta app at <a href="https://developers.facebook.com/apps" target="_blank">developers.facebook.com/apps</a>.</li>
          <li>Add the <b>"Instagram"</b> product (not "Facebook Login") and set up Business Login for Instagram, with the OAuth Redirect URI <code>https://YOUR-APP/api/instagram/oauth/callback</code>.</li>
          <li>Add permissions: <code>instagram_business_basic</code>, <code>instagram_business_content_publish</code>.</li>
          <li>Set env vars on the server: <code>META_APP_ID</code>, <code>META_APP_SECRET</code> (the Instagram product's App ID/Secret), optionally <code>META_REDIRECT_URL</code>.</li>
          <li>Reload this page: the "Connect Instagram" button appears.</li>
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
          $("igMsg").innerHTML = r.ok ? `<span style='color:var(--green)'>✓ OK, @${esc(r.username || "–")}</span>` : `<span style='color:var(--red)'>${esc(r.error || "Not OK")}</span>`;
        } catch (e) { $("igMsg").innerHTML = `<span style='color:var(--red)'>${esc(e.message)}</span>`; }
      };
      if (saveBtn) saveBtn.onclick = async () => {
        const at = $("igToken").value.trim(), ig = $("igUserId").value.trim();
        if (!at || !ig) { toast("Fill both fields first."); return; }
        try { await api("/api/instagram/connect", { method: "POST", json: { access_token: at, ig_user_id: ig } });
          toast("Instagram connected"); openInstagramModule();
        } catch (e) { $("igMsg").innerHTML = `<span style='color:var(--red)'>${esc(e.message)}</span>`; }
      };
    } else {
      /* WHY A TEST BUTTON EXISTS AT ALL: "Connected" only means the login
         worked. Whether a post can go out depends on three other things — the
         publish permission the seller may have unticked, whether Instagram can
         reach this server to fetch the picture, and whether the account is
         eligible. All three fail silently until a real post is due on a
         Saturday evening. Ten seconds now beats finding out then. */
      const pf = $("igPreflight");
      if (pf) pf.onclick = async () => {
        const box = $("igPfMsg");
        pf.disabled = true; pf.textContent = "Checking…";
        box.innerHTML = `<span class="muted tiny">Asking Instagram to accept a test picture. Nothing is posted.</span>`;
        try {
          const r = await api("/api/instagram/preflight", { method: "POST" });
          if (r.can_publish) {
            box.innerHTML = `<div class="focus-box" style="background:var(--green-soft,var(--surface-2));border-radius:8px;padding:10px 12px;">
              <b style="color:var(--green);">✓ Posting works.</b>
              <div class="muted tiny" style="margin-top:3px;">Instagram accepted a test picture from this server and
                confirmed permission to publish on @${esc(r.username || "")}. The test was thrown away, nothing
                appeared on your profile. Your scheduled posts will go out.</div></div>`;
          } else {
            box.innerHTML = `<div class="focus-box" style="background:var(--amber-soft,var(--surface-2));border-radius:8px;padding:10px 12px;">
              <b style="color:var(--amber);">Posting will not work yet.</b>
              <div class="muted tiny" style="margin-top:3px;">${esc(r.hint || "")}</div>
              ${r.error ? `<div class="muted tiny" style="margin-top:6px;opacity:.8;">Instagram said: ${esc(r.error)}</div>` : ""}</div>`;
          }
        } catch (e) {
          box.innerHTML = `<span class="err">${esc(e.message)}</span>`;
        }
        pf.disabled = false; pf.innerHTML = `${sic("check")}Check again`;
      };

      /* The preflight proves the chain without posting, which is the right
         default. This answers the other question — does a real post actually
         appear, with my caption — and the only honest answer to that is a real
         post. Deliberate, explicit, and folded away so nobody hits it by
         accident. */
      const tp = $("igTpGo");
      if (tp) tp.onclick = async () => {
        const box = $("igTpMsg");
        if (!confirm("Post this to Instagram now? It goes out for real and you will have to delete it from Instagram yourself.")) return;
        tp.disabled = true; tp.textContent = "Posting…";
        box.innerHTML = `<span class="muted tiny">Sending…</span>`;
        try {
          const r = await api("/api/instagram/test-post", { method: "POST", json: {
            caption: ($("igTpCap").value || "").trim(),
            image_url: ($("igTpUrl").value || "").trim(),
          }});
          box.innerHTML = `<div class="focus-box" style="background:var(--green-soft,var(--surface-2));border-radius:8px;padding:10px 12px;">
            <b style="color:var(--green);">✓ It posted.</b>
            ${r.permalink ? ` <a href="${esc(r.permalink)}" target="_blank" rel="noopener">Open it on Instagram</a>` : ""}
            <div class="muted tiny" style="margin-top:3px;">Remember to delete it if you do not want it on the account.</div></div>`;
        } catch (e) {
          box.innerHTML = `<div class="focus-box" style="background:var(--amber-soft,var(--surface-2));border-radius:8px;padding:10px 12px;">
            <b style="color:var(--amber);">It did not go out.</b>
            <div class="muted tiny" style="margin-top:3px;">${esc(e.message)}</div></div>`;
        }
        tp.disabled = false; tp.innerHTML = `${sic("instagram")}Post it now`;
      };
      $("igDisconnect").onclick = async () => {
        if (!confirm("Disconnect Instagram? Scheduled posts will fail until you reconnect.")) return;
        await api("/api/instagram/disconnect", { method: "POST" }); openInstagramModule();
      };
    }
  } catch (e) { moduleShell("Instagram", failed(e.message, () => openModule(_currentModule))); }
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
    if (!popup) { toast("Popup was blocked, allow popups for this site and try again."); return; }
    const handler = (ev) => {
      if (!ev.data || ev.data.type !== "ig-oauth") return;
      window.removeEventListener("message", handler);
      const p = ev.data.payload || {};
      if (p.ok) toast(`Connected @${p.username || "-"}`);
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
      : `<span class="pill-off">OpenAI off: using templates (set OPENAI_API_KEY on the server)</span>`;
    let html = `<div class="card">
      <div class="row" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <h3 style="margin:0;">Current suggestion</h3><span style="flex:1"></span>${openaiNote}
        <button class="btn ghost sm" id="ccRotate">↻ Rotate</button>
      </div>
      ${s.id ? `<p class="muted tiny">Topic: ${esc(s.topic || "–")}${s.generated ? " · generated" : " · not yet generated, open Details to fill in caption + image"}</p>
      <div class="row" style="display:flex;gap:10px;flex-wrap:wrap;">
        <button class="btn primary sm" id="ccOpen"> Open editor</button>
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
  } catch (e) { moduleShell("Content Creator", failed(e.message, () => openModule(_currentModule))); }
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
          <button class="btn ghost sm" id="ccRegenImg"> Regenerate</button>
          <button class="btn ghost sm" id="ccUploadImg"> Upload from device</button>
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
            <option value="instagram"${sug.platform==="instagram"?"selected":""}>Instagram</option>
            <option value="facebook"  ${sug.platform==="facebook"?"selected":""}>Facebook</option>
          </select>
        </label>
        <label>Caption <textarea id="ccCaption" data-ai="caption" data-ai-label="Instagram caption" rows="6">${esc(sug.caption || "")}</textarea></label>
        <label>Hashtags (space-separated) <textarea id="ccTags" data-ai="hashtags" data-ai-ctx="post" data-ai-label="Hashtags" rows="2">${esc(tags)}</textarea></label>
        <label>Description <textarea id="ccDesc" data-ai="product_description" data-ai-label="Description" rows="3">${esc(sug.description || "")}</textarea></label>
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
      toast("Image uploaded");
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
    closeCommerce(); toast("Connected, click “Pull orders” to import your sales."); refreshChannels();
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
      toast("No image yet, saving the caption only. Open the editor to add an image.", 5000);
    }
    await download(`/api/content/asset?insight_id=${encodeURIComponent(insightId)}&kind=text`, `${topic}.txt`);
    const r = await api(`/api/smart/insight/${insightId}/decision`, { method: "POST", json: { decision: "approve" } });
    if (r && r.insights) {
      if (state.lastState) { state.lastState.insights = r.insights; if (r.history) state.lastState.history = r.history; }
      renderApprovals(r.insights);
    }
    toast("Saved to your device, image + caption downloaded. Moved to History.");
  } catch (e) { toast(e.message, 6000); }
}

// ---------- store connectors (Shopify / Amazon) ----------
let _coCtx = null;

// ---------- Listed platforms strip (home) ----------
// One row for every place the seller's products can sell: their own website
// first, then the live marketplace connectors, then the ones we haven't built
// yet. The switch on each live channel decides whether that channel's sales are
// counted in analytics, forecasts and the approval panel.
async function renderChannels(containerId = "chanStrip") {
  const strip = $(containerId);
  if (!strip) return;
  strip.innerHTML = skeleton("cards");
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
          : `<button class="btn primary sm" data-co-connect="${c.id}"> Connect</button>`;
      return `
        <div class="chan-card ${soon ? "soon" : ""} ${c.id === "site" ? "own" : ""}">
          <div class="chan-top">
            <span class="chan-ico">${ico(c.icon)}</span>
            <div class="chan-name"><b>${esc(c.label)}</b>${pill}</div>
            <label class="site-toggle sm" title="${c.toggleable ? "Count this channel's sales in your insights" : "Available once this channel is live"}">
              <input type="checkbox" data-chan="${c.id}"${c.enabled ? "checked" : ""} ${c.toggleable ? "" : "disabled"} />
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
    strip.innerHTML = failed(e.message, () => renderChannels(containerId));
  }
}

function openCommerceModal(id, connectors) {
  const c = (connectors || []).find((x) => x.id === id);
  if (!c) return;
  _coCtx = c;
  $("coTitle").innerHTML = `${ico(c.icon)} Connect ${esc(c.label)}`;
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
    toast(`Pulled ${fmt(r.rows)} orders from ${id} → saved as Sales.`);
    goHome();
  } catch (e) { toast(e.message, 7000); }
}
async function commerceDisconnect(id) {
  try { await api("/api/commerce/disconnect", { method: "POST", json: { connector: id, credentials: {} } }); toast("Disconnected"); refreshChannels(); }
  catch (e) { toast(e.message); }
}

// Re-render whichever channel strip is on screen — the home foldout, the Account
// tab's Sales-channels pane, or both.
function refreshChannels() {
  if ($("chanStrip")) renderChannels("chanStrip");
  if ($("accChanStrip")) renderChannels("accChanStrip");
}

// ---------- MODULE: Ad Analytics ----------
async function openAdsModule() {
  await openCached("ads", "Ad Analytics",
    () => api("/api/ads/connectors"), renderAdsModule);
}

function renderAdsModule(d) {
  {
    let html = `<div class="card"><p class="muted tiny">Connect each ad account once, free platforms will start pulling live data in the next update; paid ones show a demo dashboard for now.</p></div>
      <div class="ads-grid">${d.connectors.map((c) => `
        <div class="ads-card ${c.connected ? "connected" : ""}">
          <div class="row" style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:22px;">${ico(c.icon)}</span>
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
  }
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
    <h3 style="margin:0 0 6px;">${esc(id)}, last ${m.range.days} days ${m.mode === "demo" ? "<span class='pill-off'>demo</span>" : "<span class='pill-on'>live</span>"}</h3>
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
      toast("Started your site from your catalogue, change anything you like.", 6000);
    }
  } catch (e) { moduleShell("Website Builder", failed(e.message, () => openModule(_currentModule))); }
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
/* An icon the SERVER chose. Those used to be emoji, which Brand.md bans as
   interface icons, so the server now sends names from this same stroke set.
   Anything that is not shaped like a name (an old cached emoji, a "•") is shown
   as escaped text, so a stale payload degrades to a character, never to markup. */
function ico(v, cls) {
  const k = String(v == null ? "" : v);
  return /^[a-z][a-z0-9-]*$/.test(k) ? sic(k, cls) : esc(k);
}

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
      <i></i>Draft: saved</span>`;
  }
  const ahead = _siteMeta && _siteMeta.site &&
    _siteMeta.site.updated_at && _site.published_at &&
    _siteMeta.site.updated_at > _site.published_at;
  return ahead
    ? `<span class="save-state ahead" id="siteDirty" title="Saved changes are not live until you publish">
        <i></i>Saved: not live yet</span>`
    : `<span class="save-state live" id="siteDirty" title="This is what shoppers see">
        <i></i>Published</span>`;
}

/* The shop's public address: onetapmanager.com/<company>. The server decides
   it (see public_path in _site_state), because only the server knows which
   words are the app's own routes; a handle that is one of them only works at
   /s/<handle>. Falls back to /s/, which always works, before the first load. */
function shopPath() {
  if (!_site || !_site.handle) return "";
  return (_siteMeta && _siteMeta.public_path) || `/s/${_site.handle}`;
}

function renderSite() {
  const live = _site.published && _site.handle;
  const url = shopPath();

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
            : "Draft: only you can see it"}</div>
        </div>
      </div>
      <div class="site-bar-r">
        ${saveState(live)}
        <button class="btn ghost sm" id="siteSave"${_siteDirty ? "" : "disabled"}>${_siteDirty ? "Save" : "Saved"}</button>
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
    if (!_site.brand) _site.brand = "My store";   // never the email handle (Gate 1)
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
  else if (_step === "checkout") { b.innerHTML = stepCheckout() + stepNav(); setTimeout(renderGateway, 0); }
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

/* Which site fields the content writer can help with, and as what. Contact
   details, handles, prices and numbers are the seller's facts — no there. */
const SITE_AI = {
  "tagline": "tagline", "brief": "", "announcement": "announcement",
  "hero.heading": "hero_heading", "hero.sub": "hero_sub", "hero.cta_text": "label",
  "story.title": "label", "story.body": "story", "manifesto": "manifesto",
  "copy.news_sub": "newsletter", "copy.news_title": "label", "copy.drop_title": "label",
  "policies.shipping": "policy", "policies.returns": "policy", "policies.privacy": "policy",
  "seo.description": "seo_description", "seo.title": "label",
  "commerce.order_note": "general",
};
function siteAiAttr(path, label) {
  let kind = SITE_AI[path];
  if (kind === undefined && /^copy\.[a-z_]+_(title|eyebrow)$/.test(path)) kind = "label";
  if (!kind) return "";
  return ` data-ai="${kind}" data-ai-ctx="site" data-ai-label="${esc(String(label).replace(/<[^>]+>/g, ""))}"`;
}

function field(label, path, opts = {}) {
  const v = readPath(path);
  const hint = opts.hint ? ` <span class="muted tiny">${opts.hint}</span>` : "";
  const ai = opts.ai === false ? "" : siteAiAttr(path, label);
  if (opts.type === "textarea")
    return `<label>${label}${hint}<textarea rows="${opts.rows || 3}" data-bind="${path}"${ai} placeholder="${esc(opts.ph || "")}">${esc(v || "")}</textarea></label>`;
  if (opts.type === "check")
    return `<label class="inline-check"><input type="checkbox" data-bind="${path}"${v ? "checked" : ""} /> ${label}${hint}</label>`;
  if (opts.type === "select")
    return `<label>${label}${hint}<select data-bind="${path}">${opts.options.map((o) =>
      `<option value="${esc(o[0])}"${String(v) === String(o[0]) ? "selected" : ""}>${esc(o[1])}</option>`).join("")}</select></label>`;
  if (opts.type === "range") {
    const id = "rng_" + path.replace(/\./g, "_");
    return `<label>${label}
      <span class="rng-val"><b id="${id}Out">${v == null ? opts.def : v}</b>${opts.hint ? ` <span class="muted tiny">${opts.hint}</span>` : ""}</span>
      <input type="range" id="${id}" data-bind="${path}" data-num="1" min="${opts.min}" max="${opts.max}" step="${opts.step || 1}" value="${v == null ? opts.def : v}" /></label>`;
  }
  return `<label>${label}${hint}<input type="${opts.type || "text"}" data-bind="${path}"${(opts.type || "text") === "text" && !opts.num ? ai : ""} ${opts.num ? 'data-num="1" min="0" step="any"' : ""} value="${esc(v == null ? "" : v)}" placeholder="${esc(opts.ph || "")}" /></label>`;
}

/* ============================== STEP 1: SETUP ============================ */
function stepSetup() {
  return `
  <div class="card sup-form form-v ai-brief">
    <div class="sup-sub">${sic("spark")}Tell us about your shop</div>
    <p class="muted tiny" style="margin:0 0 10px;">A sentence or two in your own words, what you sell,
      who makes it, who buys it, what makes it yours. The AI content writer turns it into every
      piece of text on your site: headline, story, promises, newsletter line and the words Google
      and WhatsApp show. You see it all before anything changes.</p>
    <div class="sup-form-grid" style="grid-template-columns:1fr;margin-bottom:10px;">
      <label>About your shop
        <textarea id="siteBrief" rows="3" data-bind="brief" data-ai="site_brief" data-ai-ctx="site" data-ai-label="About your shop" placeholder="Hand-block printed cotton kurtas from Jaipur. My mother and I run it with four karigars. Our buyers are working women who want something comfortable that doesn't look like everyone else's.">${esc(_site.brief || "")}</textarea></label>
    </div>
    <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
      <button class="btn primary sm" id="siteWriteAll" type="button">${sic("spark")}Write my website</button>
      <span class="muted tiny">Uses your products and Product Studio brand profile too.</span>
    </div>
  </div>

  <div class="card sup-form form-v">
    <div class="sup-sub">Your brand</div>
    <div class="sup-form-grid">
      ${field("Brand name", "brand", { ph: "Aureva" })}
      ${field("Tagline", "tagline", { hint: "(one line, shown under the logo)", ph: "Handmade fragrance, made in Bengaluru" })}
      ${imageField("siteLogo", _site.logo_url, "Logo", "square or wide, transparent PNG works best")}
    </div>

    <div class="sup-sub">Web address</div>
    <p class="muted tiny" style="margin:0 0 10px;">Your site always lives here. Pointing your own domain at it below does not take this address away.</p>
    <div class="handle-row">
      <span class="handle-pre">${esc(location.origin)}/</span>
      <input id="siteHandle" value="${esc(_site.handle || "")}" placeholder="${esc((_siteMeta && _siteMeta.suggested_handle) || "your-company")}" />
      <span class="handle-state" id="handleState"></span>
    </div>

    <div class="sup-sub">Your own domain <span class="muted tiny">optional</span></div>
    <div class="sup-form-grid" style="grid-template-columns:1fr;">
      <label>Domain you own
        <input id="siteDomain" value="${esc(_site.custom_domain || "")}" placeholder="korastudio.com" /></label>
    </div>
    <div class="dom-help">
      <p class="muted tiny" style="margin:0 0 6px;">Buy the domain anywhere (GoDaddy, Namecheap, Hostinger). Then, in that
        provider's DNS settings, add two records pointing at this app:</p>
      <table class="tbl dom-dns"><thead><tr><th>Type</th><th>Name</th><th>Points to</th></tr></thead>
        <tbody>
          <tr><td>CNAME</td><td>www</td><td><code>${esc(location.host)}</code></td></tr>
          <tr><td>ALIAS / ANAME / CNAME flattening</td><td>@ <span class="muted tiny">(the bare domain)</span></td><td><code>${esc(location.host)}</code></td></tr>
        </tbody></table>
      <p class="muted tiny" style="margin:6px 0 0;">If your provider has no ALIAS for the bare domain, point <b>www</b> only and
        set the bare domain to forward to it. DNS usually takes a few minutes, sometimes a few hours.
        Your host also has to be told to accept the domain, on Render that is Settings → Custom Domains.
        Both the bare and www versions are answered here once they resolve.</p>
      <div class="row" style="display:flex;gap:8px;align-items:center;margin-top:8px;">
        <button class="btn ghost sm" id="siteDomCheck" type="button">${sic("refresh")}Check it</button>
        <span class="muted tiny" id="siteDomState"></span>
      </div>
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
  return `<p class="muted" style="margin:6px 0 16px;">Each theme is a different website, its own layout, type scale and motion, not a colour swap. Pick the closest one; you can change every detail in the next step.</p>
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
      <p class="ed-hint muted tiny">Click anything on the site, a photo, a headline, the footer, and its controls open on the right.</p>
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
    `<option value="${f.id}"${sel === f.id ? "selected" : ""}>${esc(f.label)} · ${f.kind}</option>`).join("");
  const cur = (id, fallback) => fontStack(id || fallback);
  const chosen = _site.style.pairing || "";
  const hand = !chosen && (_site.style.heading_font || _site.style.body_font || _site.style.accent_font);
  // Three free-choice dropdowns across thirty-five families is forty-two
  // thousand combinations, most of them bad, offered to a seller who never
  // asked to become a typographer. Pairings first; the dropdowns stay, one
  // click away, for the seller who does want them.
  return `
  <p class="muted tiny" style="margin:0 0 12px;">Pick a pairing: a display face, the body face
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
  <div id="typeManual"${hand ? "" : "hidden"}>
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
    <label>Accent: light mode
      <span class="colour-row"><input type="color" data-bind="style.accent" value="${esc(_site.style.accent || t.light.accent)}" />
      <button type="button" class="btn ghost tiny" data-reset="style.accent">Theme colour</button></span></label>
    <label>Accent: dark mode
      <span class="colour-row"><input type="color" data-bind="style.accent_dark" value="${esc(_site.style.accent_dark || t.dark.accent)}" />
      <button type="button" class="btn ghost tiny" data-reset="style.accent_dark">Theme colour</button></span></label>
    ${field("Colour mode", "style.mode", { type: "select", options: [["auto", "Follow the visitor's device"], ["light", "Always light"], ["dark", "Always dark"]] })}
  </div>`;
}
function gShape() {
  const t = _siteMeta.themes.find((x) => x.id === _site.theme) || _siteMeta.themes[0];
  return `<div class="sup-form-grid">
    ${field("Corner radius", "style.radius", { type: "range", min: 0, max: 28, def: t.layout.radius, hint: "px" })}
    ${field("Animation", "style.motion", { type: "select", options: [["full", "Full: everything this theme does"], ["subtle", "Subtle: fades and rails only"], ["none", "None: completely static"]] })}
    ${field("Page width", "style.width", { type: "select", options: [["wide", "Wide"], ["compact", "Compact"], ["full", "Edge to edge"]] })}
    ${field("Show a loading screen on first visit", "style.preloader", { type: "check", hint: "(your name, a counter, then the site)" })}
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
    key points. Everything shown here comes from that product in <b>Product Management</b>,
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
    Write it however you like, “2,400+”, “6 weeks”, “4.9”.</p>
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
      Your product being used, held, worn, opened. Clips work here too, they autoplay
      muted in the rail.</div></div>`}
    <div id="glEditor" class="gal-wrap"></div>`;
}

function gManifesto() {
  return `${field("Show the statement", "sections.manifesto", { type: "check" })}
    <div class="sup-form-grid">
      ${field("Statement", "manifesto", { type: "textarea", rows: 3, ph: "We make small batches, rest them properly, and stop when the batch is done." })}
    </div>
    <p class="muted tiny">One sentence, set large. It brightens word by word as the visitor scrolls
    through it, keep it short and it lands.</p>`;
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
    ${field("Product layout", "style.card_style", { type: "select", options: [["", `Theme default (${t.layout.grid})`], ["cards", "Cards: square photos in a grid"], ["editorial", "Editorial: tall photos, no borders"], ["list", "List: a menu-style row per product"]] })}
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
        <button class="icon-pick" data-iconpick="${i}" title="Change icon" aria-label="Change this icon">${sic(h.icon || "check")}</button>
        <input value="${esc(h.title)}" data-hl="${i}" data-k="title" placeholder="Fast dispatch" />
        <input value="${esc(h.text)}" data-hl="${i}" data-k="text" placeholder="Orders leave within 24 hours." />
        <button class="btn ghost tiny danger" data-hlrm="${i}" title="Remove this promise" aria-label="Remove this promise">${sic("close")}<span class="btn-lbl">Remove</span></button>
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
        <button class="btn ghost tiny danger" data-strm="${i}" title="Remove this figure" aria-label="Remove this figure">${sic("close")}<span class="btn-lbl">Remove</span></button>
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
        <button class="gal-x" data-glrm="${i}" title="Remove" aria-label="Remove this image">${sic("close")}</button>
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
        <select data-ts="${i}" data-k="rating" class="rep-ico">${[5, 4, 3, 2, 1].map((r) => `<option value="${r}"${t.rating === r ? "selected" : ""}>${"★".repeat(r)}</option>`).join("")}</select>
        <input value="${esc(t.name)}" data-ts="${i}" data-k="name" placeholder="Customer name" />
        <input value="${esc(t.text)}" data-ts="${i}" data-k="text" placeholder="What they said" />
        <button class="btn ghost tiny danger" data-tsrm="${i}" title="Remove this review" aria-label="Remove this review">${sic("close")}<span class="btn-lbl">Remove</span></button>
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
      ${field("My prices already include GST", "commerce.gst_inclusive", { type: "check", hint: "(when off, GST is added on top at checkout)" })}
    </div>
    <div class="sup-sub">Take payment online</div>
    <div id="gatewayBox"><div class="ap-empty">Checking your payment settings…</div></div>

    <div class="sup-sub">Cash on delivery</div>
    <p class="muted tiny" style="margin:-6px 0 10px;">Across India, cash-on-delivery orders come back
      undelivered about <b>26%</b> of the time against under 2% for prepaid
      (Shipway, FY25). A small advance paid online turns an idle order into a
      committed one, it is the cheapest thing you can do about it.</p>
    <div class="sup-form-grid">
      ${field("Offer cash on delivery", "commerce.cod_enabled", { type: "check" })}
      ${field("Advance to pay online ₹", "commerce.cod_advance", { type: "number", num: true,
        hint: "(0 = full cash on delivery, no advance)", ph: "100" })}
      ${field("Note shown at checkout", "commerce.order_note", { type: "textarea", rows: 2, ph: "We'll call to confirm your order before dispatch." })}
    </div>
  </div>`;
}

/* The seller's own Razorpay. Their keys, their bank account — the money never
   passes through us, which is what keeps this out of payment-aggregator
   territory. The secret is write-only: it goes up, and only ever comes back as
   its last four characters. */
let _gateway = null;

async function renderGateway() {
  const box = $("gatewayBox");
  if (!box) return;
  try { _gateway = await api("/api/site/gateway"); }
  catch (e) { box.innerHTML = `<div class="card">${esc(e.message)}</div>`; return; }

  if (_gateway.connected) {
    box.innerHTML = `
      <div class="gw gw-on">
        <div class="gw-i">${sic("check")}</div>
        <div class="gw-b">
          <b>Razorpay connected · ${esc(_gateway.mode)} keys</b>
          <span>Key ending ${esc(_gateway.key_id_last4)}. ${esc(_gateway.detail)}</span>
          ${_gateway.mode === "test" ? `<span class="gw-warn">These are test keys,
            real cards will not be charged. Swap in your live keys before you sell.</span>` : ""}
          ${!_gateway.sdk_installed ? `<span class="gw-warn">The server is missing the
            razorpay package, run <code>pip install razorpay</code> and restart.</span>` : ""}
        </div>
        <button class="btn ghost sm" id="gwOff">Disconnect</button>
      </div>
      ${field("Show 'Pay online' at checkout", "commerce.online_enabled", { type: "check" })}`;
    $("gwOff").onclick = async () => {
      try { _gateway = await api("/api/site/gateway/disconnect", { method: "POST" }); renderGateway(); toast("Disconnected."); }
      catch (e) { toast(e.message); }
    };
    wireBinds($("gatewayBox"));
    return;
  }

  box.innerHTML = `
    <div class="gw">
      <div class="gw-b">
        <b>Connect your own Razorpay</b>
        <span>Shoppers pay straight into your bank account, we never hold your
          money. You need a Razorpay account; keys are in Dashboard →
          Settings → API Keys.</span>
      </div>
    </div>
    <div class="sup-form-grid">
      <label>Key ID<input id="gwId" placeholder="rzp_test_… or rzp_live_…" autocomplete="off" /></label>
      <label>Key Secret <span class="muted tiny">(stored encrypted, never shown again)</span>
        <input id="gwSecret" type="password" placeholder="Paste the secret" autocomplete="off" /></label>
    </div>
    <button class="btn primary sm" id="gwSave">Connect Razorpay</button>
    <div class="err" id="gwErr" hidden></div>`;
  $("gwSave").onclick = async () => {
    const e2 = $("gwErr"); e2.hidden = true;
    try {
      _gateway = await api("/api/site/gateway", { method: "POST",
        json: { key_id: $("gwId").value.trim(), key_secret: $("gwSecret").value.trim() } });
      renderGateway();
      toast("Razorpay connected, turn on “Pay online” to show it at checkout.");
    } catch (err) { e2.textContent = err.message; e2.hidden = false; }
  };
}

/* ============================= STEP 5: PUBLISH =========================== */
function stepPublish() {
  const c = _siteMeta.counts;
  const url = location.origin + shopPath();
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
        : "You can still publish, the warnings above are things shoppers will notice."}</p>
      <div class="row" style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;">
        <button class="btn ${_site.published ? "ghost" : "primary"}" id="pubBtn">${_site.published ? "Unpublish site" : "Publish my site"}</button>
        ${_site.published ? `<a class="btn ghost" href="${esc(shopPath())}" target="_blank" rel="noopener">Visit site ↗</a>` : ""}
      </div>
    </div>
    <div class="card">
      <h4 style="margin:0 0 12px;">Your link</h4>
      <div class="share-row"><input id="shareUrl" readonly value="${esc(url)}" /><button class="btn ghost sm" id="copyUrl">Copy</button></div>
      <p class="muted tiny" style="margin-top:10px;">Share this anywhere: Instagram bio, WhatsApp, a QR code on your packaging.</p>
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
  if ($("siteWriteAll")) $("siteWriteAll").onclick = writeWholeSite;

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

  const dom = $("siteDomain");
  if (dom) {
    dom.addEventListener("input", () => {
      const clean = dom.value.trim().toLowerCase()
        .replace(/^https?:\/\//, "").replace(/\/.*$/, "").replace(/\s+/g, "");
      if (clean !== dom.value) dom.value = clean;
      _site.custom_domain = clean; _siteDirty = true;
      const b = $("siteSave"); if (b) { b.disabled = false; b.textContent = "Save"; }
      const d = $("siteDirty"); if (d) d.hidden = false;
    });
  }
  const domBtn = $("siteDomCheck");
  if (domBtn) domBtn.onclick = async () => {
    const st = $("siteDomState");
    const d = ($("siteDomain").value || "").trim();
    if (!d) { st.textContent = "Enter your domain first."; return; }
    st.textContent = "Checking…";
    try {
      const r = await api(`/api/site/domain-check?domain=${encodeURIComponent(d)}`);
      st.textContent = r.message;
      st.className = "muted tiny " + (r.ok ? "good-t" : "warn-t");
    } catch (e) { st.textContent = e.message; st.className = "muted tiny warn-t"; }
  };

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

/* "Write my website": the content writer drafts every piece of copy from the
   seller's brief; they tick what to use, and it goes straight into the site. */
const SITE_COPY_FIELDS = [
  ["tagline", "Tagline", (v) => { _site.tagline = v; }],
  ["hero_heading", "Hero headline", (v) => { _site.hero.heading = v; }],
  ["hero_sub", "Hero sub-headline", (v) => { _site.hero.sub = v; }],
  ["hero_cta", "Hero button", (v) => { _site.hero.cta_text = v; }],
  ["announcement", "Announcement bar", (v) => { _site.announcement = v; }],
  ["story_title", "Story title", (v) => { _site.story.title = v; }],
  ["story_body", "Our story", (v) => { _site.story.body = v; }],
  ["manifesto", "Brand statement", (v) => { _site.manifesto = v; _site.sections.manifesto = true; }],
  ["highlights", "Promise strip", (v) => {
    const icons = ["truck", "shield", "refresh"];
    _site.highlights = (v || []).slice(0, 3).map((h, i) => ({
      icon: ((_site.highlights || [])[i] || {}).icon || icons[i], title: h.title, text: h.text }));
  }],
  ["news_title", "Newsletter heading", (v) => { _site.copy.news_title = v; }],
  ["news_sub", "Newsletter line", (v) => { _site.copy.news_sub = v; }],
  ["shop_title", "All-products heading", (v) => { _site.copy.shop_title = v; }],
  ["feat_title", "Featured heading", (v) => { _site.copy.feat_title = v; }],
  ["seo_title", "Search / link title", (v) => { _site.seo.title = v; }],
  ["seo_description", "Search / link description", (v) => { _site.seo.description = v; }],
  ["seo_keywords", "Search keywords", (v) => { _site.seo.keywords = v; }],
];

async function writeWholeSite() {
  const brief = ($("siteBrief") || {}).value || _site.brief || "";
  if (brief.trim().length < 8) { toast("Write a sentence or two about your shop first."); return; }
  _site.brief = brief.trim();
  let r;
  try {
    r = await withBusy("Writing your website…",
      "The content writer is drafting your headline, story, promises and search text from what you told us.",
      () => api("/api/ai/site-copy", { method: "POST", json: { brief } }));
  } catch (e) { toast(e.message, 6000); return; }
  let copy = r.copy || {};
  let via = r.ai ? `Written by AI (${r.provider})` : "No AI connected on the server, a starting draft from your words";
  const fb = await puterFallback(r);
  if (fb) { const j = _aiJson(fb.text); if (j && j.hero_heading) { copy = j; via = "Written by AI (Puter, your account)"; } }
  const rows = SITE_COPY_FIELDS.filter(([k]) => copy[k] && (!Array.isArray(copy[k]) || copy[k].length));
  if (!rows.length) { toast("Nothing came back, try again in a moment."); return; }
  const show = (v) => Array.isArray(v) ? v.map((h) => `<b>${esc(h.title || "")}</b>, ${esc(h.text || "")}`).join("<br>") : esc(v);
  openModal("Your website, written", `
    <p class="muted tiny" style="margin-top:0;">${esc(via)}. Untick anything you want to keep as it is,
      then use the rest. Every line stays editable afterwards.</p>
    <div class="sc-list">${rows.map(([k, label]) => `
      <label class="sc-row"><input type="checkbox" data-sc="${k}" checked />
        <div><span class="muted tiny">${esc(label)}</span><div class="sc-v">${show(copy[k])}</div></div></label>`).join("")}</div>
    <div class="modal-actions">
      <button class="btn ghost" data-scx>Cancel</button>
      <button class="btn ghost" id="scAgain">${sic("spark")}Try again</button>
      <button class="btn primary" id="scUse">Use the ticked ones</button>
    </div>`, { wide: true });
  document.querySelector("[data-scx]").onclick = closeModal;
  $("scAgain").onclick = () => { closeModal(); writeWholeSite(); };
  $("scUse").onclick = async () => {
    let n = 0;
    document.querySelectorAll("[data-sc]").forEach((cb) => {
      if (!cb.checked) return;
      const f = SITE_COPY_FIELDS.find(([k]) => k === cb.dataset.sc);
      if (f) { f[2](copy[f[0]]); n++; }
    });
    closeModal();
    siteMark();
    try { await saveSite({ quiet: true }); } catch (e) { /* saveSite already said why */ }
    renderStep();
    toast(`${n} part${n === 1 ? "" : "s"} of your site written, see them in the editor.`, 6000);
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
      toast(_site.published ? "Saved: press Publish to make it live" : "Saved as a draft");
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
    toast(want ? `Live at ${location.origin}${shopPath()}` : "Site unpublished");
  } catch (e) { toast(e.message, 5000); }
}


// =========================================================================
// MODULE: Orders
// =========================================================================
let _ordersData = null;
let _ordersFilter = "";
let _ordersTab = "orders";

async function openOrders() {
  await openCached("orders", "Orders",
    async () => {
      const [od, cr] = await Promise.all([
        api("/api/store/orders"),
        api("/api/cancel-requests").catch(() => ({ open: [], summary: {} })),
      ]);
      return { od, cr };
    },
    ({ od, cr }) => { _ordersData = od; _cancelReqs = cr; renderOrders(); });
}

let _cancelReqs = { open: [], summary: {} };

/* The cancellation inbox. It sits ABOVE the order list because an open request
   is time-sensitive in a way a status change is not — a shopper waiting to hear
   back is a sale still in play, and every hour of silence makes it less so. */
function cancelInbox() {
  const open = (_cancelReqs && _cancelReqs.open) || [];
  if (!open.length) return "";
  return `
    <div class="cr-inbox">
      <div class="cr-h">${sic("whatsapp")}
        <b>${open.length} cancellation request${open.length === 1 ? "" : "s"}</b>
        <span class="muted">Nothing is cancelled until you approve it.</span></div>
      ${open.map(r => `
        <div class="cr-row" data-cr="${esc(r.id)}">
          <div class="cr-meta">
            <b>${esc(r.ref_no)}</b>
            <span>${esc((r.counterparty || {}).name || "")}</span>
            <span class="cr-reason">${esc(r.reason_label)}</span>
            ${r.reason_text ? `<span class="muted tiny">"${esc(r.reason_text)}"</span>` : ""}
          </div>
          ${r.save_play ? `<div class="cr-play">${sic("spark")}${esc(r.save_play)}</div>` : ""}
          <div class="cr-acts">
            ${(r.links || {}).shopper_wa
              ? `<a class="btn ghost sm" href="${esc(r.links.shopper_wa)}" target="_blank" rel="noopener">${sic("whatsapp")}Message them</a>`
              : `<span class="muted tiny">No phone number on this order</span>`}
            <button class="btn ghost sm" data-crkeep="${esc(r.id)}">Keep the order</button>
            <button class="btn ghost sm danger" data-crcancel="${esc(r.id)}">Cancel it</button>
          </div>
        </div>`).join("")}
    </div>`;
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
      <button class="${_ordersTab === "orders" ? "on" : ""}" data-otab="orders"> Orders</button>
      <button class="${_ordersTab === "customers" ? "on" : ""}" data-otab="customers"> Customers</button>
    </div>`;

  let body;
  if (_ordersTab === "customers") {
    body = `<div id="custBody"><div class="ap-empty">Loading customers…</div></div>`;
  } else if (!d.orders.length) {
    body = `<div class="ap-empty">No orders yet.${d.site.published ? "" : "Publish your website from the Website Builder to start taking them."}</div>`;
  } else {
    const chips = [["", "All", d.orders.length]].concat(d.statuses.map((s) =>
      [s.id, s.label, st.by_status[s.id] || 0])).map(([id, label, n]) =>
      `<button class="chip ${_ordersFilter === id ? "on" : ""}" data-ofil="${id}">${esc(label)} <b>${n}</b></button>`).join("");
    body = `
      <div class="ord-toolbar">
        <div class="ord-chips">${chips}</div>
        <div class="ord-tools">
          <button class="btn ghost sm" id="ordLabels">${sic("tag")}Print ${_ordersFilter ? "these" : "all"} labels</button>
          <button class="btn ghost sm" id="ordExport">⬇ Export CSV</button>
        </div>
      </div>
      <div class="ord-list">${rows.map(orderCard).join("") || `<div class="ap-empty">Nothing with that status.</div>`}</div>`;
  }

  moduleShell("Orders", kpis + cancelInbox() + tabs + body);
  document.querySelectorAll("[data-otab]").forEach((b) => b.onclick = () => { _ordersTab = b.dataset.otab; renderOrders(); if (_ordersTab === "customers") loadCustomers(); });
  document.querySelectorAll("[data-ofil]").forEach((b) => b.onclick = () => { _ordersFilter = b.dataset.ofil; renderOrders(); });
  const ex = $("ordExport");
  if (ex) ex.onclick = () => download("/api/store/orders/export", "site_orders.csv");

  const lab = $("ordLabels");
  if (lab) lab.onclick = async () => {
    const ids = (_ordersFilter ? _ordersData.orders.filter(o => o.status === _ordersFilter)
                               : _ordersData.orders).map(o => o.id);
    if (!ids.length) return toast("No orders to print.");
    await postDownload("/api/orders/labels", { order_ids: ids }, `labels-${ids.length}.pdf`);
  };

  document.querySelectorAll("[data-label]").forEach(b => b.onclick = async () => {
    const o = _ordersData.orders.find(x => x.id === b.dataset.label);
    await postDownload("/api/orders/labels", { order_ids: [b.dataset.label] },
                       `label-${(o && o.order_no) || "order"}.pdf`);
  });

  document.querySelectorAll("[data-invoice]").forEach(b => b.onclick = () =>
    openInvoiceFor(b.dataset.invoice));
  document.querySelectorAll("[data-upiok]").forEach(b => b.onclick = () => answerUpi(b.dataset.upiok, true));
  document.querySelectorAll("[data-upino]").forEach(b => b.onclick = () => answerUpi(b.dataset.upino, false));

  document.querySelectorAll("[data-crkeep]").forEach(b => b.onclick = () =>
    resolveCancel(b.dataset.crkeep, "declined"));
  document.querySelectorAll("[data-crcancel]").forEach(b => b.onclick = () =>
    resolveCancel(b.dataset.crcancel, "approved"));
  document.querySelectorAll("[data-ostat]").forEach((sel) => sel.onchange = async () => {
    const id = sel.dataset.ostat;
    // Cancelling is the one status change worth a question. Asked here, in the
    // half-second where the seller still knows the answer — ask later and
    // nobody ever fills it in, which is how a "why" chart ends up empty.
    if (sel.value === "cancelled") { askCancelReason(id, sel); return; }
    await setOrderStatus(id, sel.value);
  });
  if (_ordersTab === "customers") loadCustomers();
}

async function setOrderStatus(id, status, reason) {
  try {
    _ordersData = await api("/api/store/orders/status", { method: "POST",
      json: { order_id: id, status, reason: reason || "" } });
    toast(status === "cancelled"
      ? "Cancelled: it is out of your sales figures and counted in Cancellations."
      : "Order updated: sales figures refreshed");
    renderOrders();
  } catch (e) { toast(e.message); }
}

let _cancelReasons = null;

/* "Was this clip made by AI?" — asked once, before a clip is attached.
   We have to know, because since 20 February 2026 Indian law requires this
   platform to label AI-made pictures and clips clearly, and it equally requires
   us not to mislabel: stamping "AI generated" on footage a seller filmed on
   their own phone would be a false claim about their own product. The reel flow
   already knows the answer (it sent the seller to Google Flow two steps ago) and
   passes it straight through; this dialog is for the post editor, where a clip
   can be either. Resolves to true, false, or null if the seller backs out. */
function askClipOrigin() {
  return new Promise((resolve) => {
    openModal("Where did this clip come from?", `
      <p class="muted" style="margin-top:0;">One tap, and it only matters for one
      reason: an AI-made clip has to carry an "AI generated" label, and a clip you
      filmed must <b>not</b> carry one. We add the label for you either way you
      answer, correctly.</p>
      <div class="modal-actions" style="flex-direction:column;align-items:stretch;gap:8px;">
        <button class="btn primary" id="coAi">An AI tool made it (Flow, Veo, Kling)</button>
        <button class="btn" id="coReal">I filmed it myself</button>
        <button class="btn ghost" id="coAbort">Not now</button>
      </div>`);
    const pick = (v) => { closeModal(); resolve(v); };
    $("coAi").onclick = () => pick(true);
    $("coReal").onclick = () => pick(false);
    $("coAbort").onclick = () => pick(null);
  });
}

async function askCancelReason(id, sel) {
  if (!_cancelReasons) {
    try { _cancelReasons = (await api("/api/cancellations")).reason_options || []; }
    catch (e) { _cancelReasons = []; }
  }
  const opts = _cancelReasons.map((r) =>
    `<option value="${esc(r.id)}">${esc(r.label)}</option>`).join("");
  openModal("Why is this cancelled?", `
    <p class="muted" style="margin-top:0;">One tap. It is the difference between
    knowing you lost twelve orders and knowing <b>why</b> you lost them, and it
    is the only field Cancellation Analysis cannot work without.</p>
    <label class="fld"><span>Reason</span>
      <select id="cxReason">${opts}<option value="">Rather not say</option></select></label>
    <p class="muted tiny">The stage: before packing, packed, or already shipped,
    is worked out from the order's own history, so you do not have to tell us that.</p>
    <div class="modal-actions">
      <button class="btn ghost" id="cxAbort">Don't cancel</button>
      <button class="btn primary" id="cxGo">Cancel this order</button>
    </div>`);
  const restore = () => { if (sel) sel.value = (_ordersData.orders || [])
    .find((o) => o.id === id)?.status || "new"; };
  $("cxAbort").onclick = () => { closeModal(); restore(); };
  $("cxGo").onclick = async () => {
    const reason = $("cxReason").value;
    closeModal();
    await setOrderStatus(id, "cancelled", reason);
  };
}

/* A UPI order waits for the seller, not the shopper: the money went to the
   seller's own UPI ID, so only they can see whether it arrived. Two answers,
   in the order they will almost always be given. "Not received" cancels the
   order, which puts the stock back. */
function upiCheckBox(o) {
  if (o.payment !== "upi") return "";
  if (o.payment_status === "paid") {
    return `<div class="upi-check paid">${sic("check")}<span>UPI payment received</span></div>`;
  }
  if (o.payment_status !== "to_check" || o.status === "cancelled") return "";
  const hrs = Math.max(0, Math.round((Date.now() - Date.parse(o.created_at)) / 36e5));
  const waited = hrs < 1 ? "just now" : hrs < 48 ? `${hrs} hour${hrs === 1 ? "" : "s"} ago` : `${Math.round(hrs / 24)} days ago`;
  return `
    <div class="upi-check">
      <div><b>Payment to check: ₹${fmt(o.upi_due || o.total)}</b>
        <span class="muted tiny">Ordered ${esc(waited)}. Look in your UPI app for order ${esc(o.order_no)}.</span></div>
      <div class="upi-check-acts">
        <button class="btn primary sm" data-upiok="${esc(o.id)}">${sic("check")}Money received</button>
        <button class="btn ghost sm" data-upino="${esc(o.id)}">Not received</button>
      </div>
    </div>`;
}

async function answerUpi(id, received) {
  if (!received && !confirm("Cancel this order? The stock goes back on your shelf.")) return;
  try {
    await api("/api/orders/upi", { method: "POST", json: { order_id: id, received } });
    _ordersData = await api("/api/store/orders");
    toast(received ? "Marked paid." : "Order cancelled. Stock is back.");
    renderOrders();
  } catch (e) { toast(e.message); }
}

function orderCard(o) {
  const a = o.address || {};
  const items = (o.items || []).map((i) =>
    `<div class="oi"><span>${esc(i.name)} <span class="muted tiny">× ${i.qty}</span></span><b>₹${fmt(i.line_total)}</b></div>`).join("");
  const opts = _ordersData.statuses.map((s) =>
    `<option value="${s.id}"${o.status === s.id ? "selected" : ""}>${esc(s.label)}</option>`).join("");
  return `
    <div class="ord-card ${esc(o.status)}">
      <div class="ord-card-h">
        <div>
          <b>${esc(o.order_no)}</b>
          <span class="chan-pill ${esc(o.status)}">${esc(o.status)}</span>
          <div class="muted tiny">${esc(String(o.created_at).replace("T", " ").slice(0, 16))} · ${esc(o.payment === "cod" ? "Cash on delivery" : o.payment === "upi" ? "UPI" : "Pay online")}</div>
        </div>
        <div class="ord-total">₹${fmt(o.total)}</div>
      </div>
      ${upiCheckBox(o)}
      <div class="ord-grid">
        <div>
          <div class="ord-lbl">Customer</div>
          <div><b>${esc(o.customer_name || "–")}</b></div>
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
        <button class="btn ghost tiny" data-label="${esc(o.id)}">${sic("tag")}Bill sticker</button>
        <button class="btn ghost tiny" data-invoice="${esc(o.id)}">${sic("receipt")}Invoice</button>
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
          <td><b>${esc(c.name || "–")}</b></td><td>${esc(c.email)}</td><td>${esc(c.phone || "–")}</td>
          <td>${fmt(c.orders)}</td><td>₹${fmt(c.spend)}</td>
          <td class="muted tiny">${esc(String(c.last || "").replace("T", " ").slice(0, 16) || "–")}</td>
        </tr>`).join("")}</tbody>
      </table></div>
      <p class="muted tiny" style="margin-top:10px;">These shoppers are yours alone, they also appear in RFM and Win-Back once their orders are counted in your sales.</p>`
      : `<div class="ap-empty">No one has signed up on your site yet.</div>`;
  } catch (e) { box.innerHTML = `<div class="card">${esc(e.message)}</div>`; }
}

// ---------- boot ----------
(async function init() {
  // Every table the app ever draws gets its cells labelled, so each one can
  // fall back to card layout on a phone. Started before anything renders.
  watchTables();
  // Icons come from localStorage on any warm start, so this almost never
  // blocks. On a cold one it is still the only thing the shell needs first.
  await loadIcons();
  if (!state.token) {
    $("loginView").hidden = false;
    setupGoogleSignIn();     // not awaited: the password form is usable meanwhile
    return;
  }

  // Only a 401 means the session is actually gone. A 500, a timeout or a cold
  // start is the server having a bad moment — throwing the seller back to the
  // login screen for that, and deleting their token on the way out, is why
  // stepping onto the landing page and back felt like being signed out.
  const signedOut = (e) => e && (e.status === 401 || e.status === 403);
  const forget = () => {
    state.token = null;
    localStorage.removeItem("cx_token");
    localStorage.removeItem("cx_email");
    warmClear(); warmModClearAll();   // never leave one account's screens for the next
    $("loginView").hidden = false;
  };

  // With a warm home screen already on disk there is nothing to wait for: show
  // the app now and check the session alongside it, rather than holding a
  // blank page for a round trip. This is the difference the seller actually
  // feels when they switch away and come back.
  //
  // Safe because the only thing painted early is THIS account's own last view,
  // and nothing privileged can happen without a valid token — every action
  // goes back to the server. If the check does come back 401, we sign out.
  if (warmRead()) {
    showShell();
    loadMediaStatus();
    api("/api/me").catch((e) => { if (signedOut(e)) forget(); });
    return;
  }

  try {
    await api("/api/me");
    loadMediaStatus();
    showShell();
  } catch (e) {
    if (signedOut(e)) return forget();
    try {                                   // one retry for a cold start
      await new Promise((r) => setTimeout(r, 1200));
      await api("/api/me");
      loadMediaStatus();
      showShell();
    } catch (e2) {
      if (signedOut(e2)) return forget();
      // Still signed in — let them in and say what happened, rather than
      // pretending their session expired.
      showShell();
      toast("Could not reach the server just now. You are still signed in, "
            + "press Refresh on any page to try again.", 6000);
    }
  }
})();

/* =====================================================================
   MODULE: Social Media Manager

   The screen order follows the research rather than the obvious product
   shape. "This Week" is the home screen, not a settings page, because the
   binding constraint on a small seller is production capacity, not
   scheduling — so the fastest possible path from opening the module to
   having four posts approved is what the whole layout optimises for.
   ===================================================================== */
let _socialData = null;

async function openSocial() {
  await openCached("social", "Social Media Manager",
    () => api("/api/social"),
    (d) => { _socialData = d; return renderSocial(); });
}

/* ---------------------------------------------- why a post has not gone ----
   A scheduled post that does not appear gives the seller nothing to work with.
   The calendar shows a time, Instagram says connected, and the reason is one of
   eight conditions none of which are visible. This puts the answer on the
   screen, per post, in a sentence. */
/* ===========================================================================
   How it did
   ===========================================================================
   The planner chooses a kind of post, a format and a product for every slot,
   and it chooses from published research: detail posts outsell lifestyle ones,
   reels out-reach carousels below 50k followers. That is the right way to
   start and the wrong way to continue, because it is somebody else's average.

   This screen closes the loop. Every post the app publishes carries its
   Instagram media id, so the real numbers can be fetched and attached to the
   choice that produced them.

   Two things it refuses to do, and both matter more than what it does:

   1. It never shows a zero it is not sure of. Instagram's own figures lag by
      up to 48 hours, so a post inside that window is held back rather than
      reported as nobody having seen it. A seller who thinks a good post failed
      will stop making that kind of post.
   2. It never ranks on a handful of posts. Six in a bucket and two buckets to
      compare, or it says plainly that it is too early. A ranking off two reels
      is worse than no ranking, because the seller will rearrange their week
      around it. */
async function openSocialPerformance(days) {
  const window = days || 28;
  let d;
  try {
    // Instagram is slow and this is a per-post round trip, so the seller is
    // told it is working and told they can walk away, rather than watching a
    // frozen screen and pressing the button again.
    d = await withBusy("Reading your Instagram numbers",
                       "Instagram takes a few seconds. You can go and do "
                       + "something else, this keeps going.",
                       () => api(`/api/social/performance?days=${window}`));
  } catch (e) {
    return toast(e.message, 7000);
  }

  const R = d.readiness || {};
  const acct = d.account || {};
  const refused = d.refused;

  // Why the screen might be empty, in the order a seller would ask it. Each of
  // these is a different problem with a different fix, and collapsing them into
  // one "no data" message sends people chasing the wrong one.
  let blocker = "";
  if (!R.connected) {
    blocker = `<div class="perf-note">
      <b>Instagram is not connected.</b>
      <p>Connect the account and its numbers appear here within a day.</p>
      <button class="btn primary sm" id="perfConnect">${sic("instagram")}Connect Instagram</button>
    </div>`;
  } else if (refused) {
    blocker = `<div class="perf-note${refused.reason === "not_a_tester" ? " perf-rule" : ""}">
      <b>${refused.reason === "not_a_tester"
            ? "Instagram will not share these numbers with us yet"
            : "Instagram did not send the numbers"}</b>
      <p>${esc(refused.message || "")}</p>
      ${refused.reason === "token_expired"
        ? `<button class="btn primary sm" id="perfConnect">${sic("refresh")}Reconnect</button>` : ""}
    </div>`;
  } else if (!R.published) {
    blocker = `<div class="perf-note">
      <b>Nothing has gone out yet.</b>
      <p>Once posts start publishing from here, this page fills in by itself.
      Instagram counts them within two days.</p>
    </div>`;
  }

  const n = (v) => (typeof v === "number" ? v.toLocaleString("en-IN") : "–");
  const m = acct.metrics || {};
  const cards = [
    ["Times seen", m.views, "How many times your posts appeared on a screen."],
    ["People reached", m.reach, "Separate people, not repeat views."],
    ["People who did something", m.accounts_engaged, "Liked, saved, shared, commented or replied."],
    ["Taps on your link", m.profile_links_taps, "The one that turns into a sale."],
    ["New followers", m.followers_gained, "Over the same period."],
  ].filter((c) => typeof c[1] === "number");

  const statBlock = cards.length ? `
    <div class="perf-stats">
      ${cards.map(([label, value, why]) => `
        <div class="perf-stat">
          <div class="perf-num">${n(value)}</div>
          <div class="perf-lbl">${esc(label)}</div>
          <div class="perf-why">${esc(why)}</div>
        </div>`).join("")}
    </div>` : "";

  // The verdicts are the point of the page, so they go above the tables.
  const verdicts = (d.verdicts || []).length ? `
    <h4 class="perf-h">What your own posts say</h4>
    ${(d.verdicts || []).map((v) => `
      <div class="perf-verdict">
        <div class="perf-v-text">${esc(v.sentence)}</div>
        <div class="muted tiny">Worked out from ${v.sample} posts. Instagram's
        own numbers, not an estimate.</div>
      </div>`).join("")}`
    : (d.measured >= 1 ? `
    <h4 class="perf-h">What your own posts say</h4>
    <div class="perf-note perf-soft">
      <b>Not enough to call it yet.</b>
      <p>${esc((d.why_not_yet || {}).sentence || "")}</p>
      <p class="muted tiny">${d.measured} post${d.measured === 1 ? "" : "s"} counted.
      The bar is ${R.needed} of a kind, twice over, because a ranking off two or
      three posts is luck wearing a number, and you would rearrange your week
      around it.</p>
    </div>` : "");

  const table = (rows, title, unit) => (rows || []).length ? `
    <h4 class="perf-h">${esc(title)}</h4>
    <div class="table-scroll"><table class="perf-table">
      <thead><tr><th>${esc(unit)}</th><th>Posts</th><th>Average times seen</th></tr></thead>
      <tbody>${rows.map((r) => `
        <tr class="${r.enough ? "" : "perf-thin"}">
          <td>${esc(r.label || r.key)}</td>
          <td>${r.posts}</td>
          <td><b>${n(r.average)}</b>${r.enough ? "" :
            ` <span class="muted tiny">too few to compare</span>`}</td>
        </tr>`).join("")}</tbody>
    </table></div>` : "";

  const posts = (d.posts || []).length ? `
    <h4 class="perf-h">Every post, best first</h4>
    <div class="table-scroll"><table class="perf-table">
      <thead><tr><th>Post</th><th>Kind</th><th>Seen</th><th>Reached</th><th>Saved</th><th>Shared</th></tr></thead>
      <tbody>${(d.posts || []).map((p) => `
        <tr>
          <td>${p.permalink
                ? `<a href="${esc(p.permalink)}" target="_blank" rel="noopener">${esc(p.caption_hook || p.product_name || "View")}</a>`
                : esc(p.caption_hook || p.product_name || "–")}
              <div class="muted tiny">${esc((p.posted_at || "").slice(0, 10))}${p.product_name ? " · " + esc(p.product_name) : ""}</div></td>
          <td class="muted tiny">${esc(p.pillar_name || p.format || "–")}</td>
          <td><b>${n(p.views)}</b></td>
          <td>${n(p.reach)}</td>
          <td>${n(p.saved)}</td>
          <td>${n(p.shares)}</td>
        </tr>`).join("")}</tbody>
    </table></div>` : "";

  const settling = d.settling ? `
    <p class="muted tiny perf-settle">${sic("clock")}${d.settling} recent
    post${d.settling === 1 ? " is" : "s are"} not counted above. Instagram takes
    up to two days to report, and showing a zero in the meantime would read as a
    post that failed.</p>` : "";

  openModal(`How your posts did${acct.username ? " · @" + esc(acct.username) : ""}`, `
    <p class="muted tiny perf-intro">
      The last ${window} days, straight from Instagram.
      ${typeof acct.followers === "number" ? `${n(acct.followers)} followers.` : ""}
      ${d.cached ? "Refreshed at most an hour ago." : ""}
    </p>
    ${blocker}
    ${statBlock}
    ${verdicts}
    ${table(d.by_pillar, "By kind of post", "Kind")}
    ${table(d.by_format, "By format", "Format")}
    ${table(d.by_product, "By product", "Product")}
    ${posts}
    ${settling}
    <div class="modal-actions">
      <button class="btn ghost sm" data-perfdays="7">Last 7 days</button>
      <button class="btn ghost sm" data-perfdays="28">Last 28 days</button>
      <button class="btn ghost sm" data-perfdays="90">Last 90 days</button>
      <button class="btn ghost sm" id="perfRefresh">${sic("refresh")}Fetch again</button>
      <button class="btn" id="perfClose">Close</button>
    </div>`);

  $("perfClose").onclick = closeModal;
  const conn = $("perfConnect");
  if (conn) conn.onclick = () => { closeModal(); openModule("instagram"); };
  document.querySelectorAll("[data-perfdays]").forEach((b) => {
    b.onclick = () => { closeModal(); openSocialPerformance(Number(b.dataset.perfdays)); };
  });
  $("perfRefresh").onclick = async () => {
    // "Fetch again" has to actually go back to Instagram, or the button is a
    // lie. The server drops this account's cached copy before re-reading.
    closeModal();
    try {
      await withBusy("Asking Instagram again",
                     "Dropping what we had and re-reading. A few seconds.",
                     () => api(`/api/social/performance?days=${window}&refresh=1`));
    } catch (e) { /* the reopen below reports it */ }
    openSocialPerformance(window);
  };
}


async function openPostQueue() {
  let q;
  try { q = await api("/api/social/queue"); } catch (e) { return toast(e.message, 6000); }
  const rows = (q.posts || []).filter((p) => p.state !== "published");
  const body = rows.length ? `
    <div class="table-scroll"><table>
      <thead><tr><th>When</th><th>Type</th><th>Where it stands</th></tr></thead>
      <tbody>${rows.map((p) => `
        <tr class="${p.will_post ? "pq-go" : ""}">
          <td class="muted tiny">${esc((p.scheduled_at || "–").slice(0, 16).replace("T", " "))}</td>
          <td class="muted tiny">${esc(p.format)}</td>
          <td>${esc(p.verdict)}</td>
        </tr>`).join("")}</tbody>
    </table></div>`
    : `<div class="ap-empty">Nothing waiting: every post has either gone out or been cancelled.</div>`;
  openModal("What is going out, and what is not", `
    <p class="muted tiny">It is <b>${esc((q.now || "").replace("T", " at "))}</b> ${esc(q.tz || "")}.
      Instagram is ${q.instagram_connected ? "connected" : "<b>not connected</b>"}.
      ${q.due_now ? `<b>${q.due_now} post${q.due_now === 1 ? " is" : "s are"} due now.</b>` : ""}</p>
    ${body}
    <div class="row" style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px;">
      <button class="btn ghost" data-mclose3>Close</button>
      ${q.due_now ? `<button class="btn primary" id="pqRun">Send the ${q.due_now} due now</button>` : ""}
    </div>`, { wide: true });
  document.querySelector("[data-mclose3]").onclick = closeModal;
  const run = $("pqRun");
  if (run) run.onclick = async () => {
    run.disabled = true; run.textContent = "Sending…";
    try {
      const r = await api("/api/social/publish-due", { method: "POST" });
      toast(r.published ? `${r.published} posted.`
            : `Nothing went out. ${(r.details && r.details.failed[0] && r.details.failed[0].error) || ""}`, 7000);
      closeModal();
      warmModClearAll();
      openModule("social");
    } catch (e) { toast(e.message, 6000); run.disabled = false; }
  };
}

function socialStateChip(st) {
  const map = { draft: ["Draft", "st-draft"], ready: ["Ready", "st-ready"],
                approved: ["Approved · needs media", "st-appr"],
                scheduled: ["Scheduled", "st-sched"], published: ["Published", "st-pub"],
                failed: ["Failed", "st-fail"], cancelled: ["Cancelled", "st-fail"] };
  const [label, cls] = map[st] || ["Draft", "st-draft"];
  return `<span class="sm-chip ${cls}">${label}</span>`;
}

let _socialMonth = null;   // {year, month} being viewed

function socialStateChipFor(st) {
  const map = { draft: ["Needs you", "st-draft"], ready: ["Ready", "st-ready"],
                approved: ["Needs its media", "st-appr"],
                scheduled: ["Scheduled", "st-sched"], published: ["Posted", "st-pub"],
                failed: ["Skipped", "st-fail"], cancelled: ["Cancelled", "st-fail"] };
  const [label, cls] = map[st] || ["Draft", "st-draft"];
  return `<span class="sm-chip ${cls}">${label}</span>`;
}

async function renderSocial() {
  const d = _socialData;
  const ai = d.ai || {};
  const t = new Date();
  if (!_socialMonth) _socialMonth = { year: t.getFullYear(), month: t.getMonth() + 1 };

  let cal;
  try {
    cal = await api(`/api/social/month?year=${_socialMonth.year}&month=${_socialMonth.month}`);
  } catch (e) {
    if (_currentModule !== "social") return;
    return moduleShell("Social Media Manager", failed(e.message, () => openModule(_currentModule)));
  }
  // The calendar is a second round trip after the module's own, so this is the
  // screen most likely to still be loading when the seller taps away. Painting
  // it now would put Social back over whatever they went to instead.
  if (_currentModule !== "social") return;
  _socialCal = cal;

  const aiLine = ai.ready
    ? `<span class="sm-ok">${sic("check")}Writing with ${esc(ai.active)}${ai.free_ready && !(ai.providers || []).some((x) => x.name === ai.active && !x.free) ? ", free tier" : ""}</span>`
    : `<span class="sm-warn">${sic("alert")}No AI connected: captions come from a template.</span>`;

  // Decisions for these posts live in the Approval panel now (the next-7-days
  // ones get a one-tap card there automatically) -- this page used to have
  // its own separate approve/skip strip here, which meant a seller could be
  // asked to decide the same post in two different places. Any post, near or
  // far, can still be decided by opening it below: the editor has its own
  // Approve/Skip.
  const undecided = [];
  (cal.days || []).forEach((day) => (day.posts || []).forEach((p) => {
    if (p.state === "draft") undecided.push(p);
  }));

  // --- the month grid
  const pad = cal.starts_on;                       // Monday = 0
  const cells = [];
  /* The strip under the grid is built from the days the grid actually marked,
     not from cal.festivals — a festival whose own date falls in the NEXT
     month still gets a "starts" mark in this one, and reading its date
     straight off the record put "11 Navratri" under a September calendar when
     the 11th is in October and what September has is the 20th. */
  const legend = [];
  for (let i = 0; i < pad; i++) cells.push(`<div class="cal-cell is-pad"></div>`);
  (cal.days || []).forEach((day) => {
    const fest = (cal.festivals || []).find((f) => f.date === day.date);
    const startsFest = (cal.festivals || []).find((f) => f.start_on === day.date);
    if (fest) legend.push({ d: Number(day.date.slice(-2)), name: fest.name, starts: false });
    else if (startsFest) legend.push({ d: Number(day.date.slice(-2)), name: startsFest.name, starts: true });
    const isToday = day.date === cal.today;
    cells.push(`
      <div class="cal-cell${isToday ? " is-today" : ""}${fest ? " is-fest" : ""}" data-day="${esc(day.date)}">
        <div class="cal-num">${Number(day.date.slice(-2))}</div>
        ${fest ? `<div class="cal-fest" title="${esc(fest.note || "")}">${esc(fest.name)}</div>` : ""}
        ${startsFest && !fest ? `<div class="cal-start">${esc(startsFest.name)} starts</div>` : ""}
        ${(day.posts || []).map((p) => `
          <button class="cal-post st-${esc(p.state)}" data-open="${esc(p.id)}"
                  title="${esc((p.caption || {}).hook || "")}">
            <span class="cal-fmt">${esc((p.format || "").slice(0, 4))}</span>
            <span class="cal-name">${esc(p.product_name || "")}</span>
            ${p.video_url ? `<i class="cal-has-img cal-has-vid" title="Clip uploaded"></i>`
              : p.image_url ? `<i class="cal-has-img"></i>` : ""}
          </button>`).join("")}
      </div>`);
  });

  const fests = (cal.festivals || []).filter((f) => f.relevant);

  moduleShell("Social Media Manager", `
    <div class="sm-head">
      <div>${aiLine}
        ${undecided.length ? `<div class="muted tiny sm-pending-note">${sic("bell")}${undecided.length} post${undecided.length === 1 ? "" : "s"} still need a decision, the next 7 days' worth are in the Approval panel; open any post below to decide it directly.</div>` : ""}
        ${imageQuotaTracker(d.image_quota)}
      </div>
      <div class="sm-head-actions">
        <button class="btn primary" id="smBuild">${sic("spark")}Plan this week</button>
        <button class="btn ghost sm" id="smBuild4">${sic("spark")}Plan 4 weeks</button>
        <button class="btn ghost sm" id="smShoot">${sic("camera")}Shoot list</button>
        <button class="btn ghost sm" id="smSettings">${sic("settings")}Setup</button>
        <button class="btn ghost sm" id="smQueue" title="Why a post has or has not gone out">${sic("clock")}What is going out</button>
        <button class="btn ghost sm" id="smPerf" title="What your published posts actually did, from Instagram">${sic("trend")}How it did</button>
        ${d.instagram && d.instagram.connected
          ? `<button class="btn ghost sm" id="smInsta" title="Instagram connection">${sic("instagram")}@${esc(d.instagram.account_username || "connected")}</button>`
          : ""}<!-- not connected? the strip below asks, and asking twice on one
               screen makes both requests easier to ignore -->
        <button class="btn ghost sm danger" id="smClearPlan" title="Delete every planned post and campaign">${sic("close")}Clear plan</button>
      </div>
    </div>

    ${igStrip(d.instagram)}
    ${autoplanStrip(d.autoplan)}

    <div id="smCampaigns"></div>

    ${fests.length ? `<div class="sm-radar">
      <div class="sm-radar-h">${sic("bell")}This month</div>
      ${fests.map((f) => `<div class="sm-radar-i">
        <b>${esc(f.name)}</b> ${esc(f.date.slice(-2))} ${esc(cal.label.split(" ")[0])}
        – ${f.planned ? `${f.planned} post${f.planned === 1 ? "" : "s"} planned`
                      : `<span class="sm-warn2">nothing planned yet</span>`}.
        Start posting ${esc(f.start_on)}.${f.note ? ` <span class="muted">${esc(f.note)}</span>` : ""}
      </div>`).join("")}
    </div>` : ""}

    <div class="cal-wrap">
      <div class="cal-head">
        <!-- A bare chevron is readable as "back a month" by convention, so it
             keeps its shape, but a screen reader and a long-press both need
             a name, and neither gets one from a glyph. -->
        <button class="btn ghost sm" id="calPrev" title="The month before" aria-label="Go to the month before">‹</button>
        <b>${esc(cal.label)}</b>
        <button class="btn ghost sm" id="calNext" title="The month after" aria-label="Go to the month after">›</button>
        <span class="muted tiny">${cal.counts.planned} planned</span>
        <button class="btn ghost sm" id="calToday" style="margin-left:auto;">Today</button>
      </div>
      <div class="cal-dow">${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        .map((x) => `<span>${x}</span>`).join("")}</div>
      <div class="cal-grid">${cells.join("")}</div>
      <!-- WHAT A 45px COLUMN CANNOT HOLD.
           A phone gives each day about 45 pixels. "Ganesh Chaturthi" does not
           fit, and forcing it to wrap turned the cell into "Ganes / h /
           Chatur / thi", which is worse than not showing it, because it
           reads as a broken layout rather than as a festival. So below phone
           width the day keeps its amber tint (the signal: something is on)
           and the names move here, under the grid, where there is a whole
           line to say them in. Above that width the cells have room and this
           strip is hidden as a duplicate. -->
      ${legend.length ? `<div class="cal-legend">
        <span class="cal-legend-h">This month</span>
        ${legend.map((f) => `<span class="cal-leg">
          <b>${esc(String(f.d))}</b> ${esc(f.name)}${f.starts ? " starts" : ""}</span>`).join("")}
      </div>` : ""}
    </div>

    <details class="sm-fold">
      <summary>Why these posts, and not the ones you were going to make</summary>
      <div class="sm-explain">
        <p>Across 86 studies and 95 million observations, the content mix that
        wins <b>likes</b> is close to the inverse of the mix that wins
        <b>sales</b>. Informational product content has a +0.58 elasticity to
        sales; emotional content has −0.07. Discount posts are negatively
        associated with sales, which is why offers are capped at
        ${esc(String(d.offer_cap))}% of your week here rather than left to habit.</p>
        <div class="sm-pillars">${(d.pillars || []).map((p) => `
          <div class="sm-pil"><div class="sm-pil-h"><b>${esc(p.name)}</b><span>${p.share}%</span></div>
            <div class="sm-pil-w">${esc(p.why)}</div></div>`).join("")}</div>
      </div>
    </details>`);

  renderCampaignRail();

  const move = (n) => {
    let m = _socialMonth.month + n, y = _socialMonth.year;
    if (m < 1) { m = 12; y--; } if (m > 12) { m = 1; y++; }
    _socialMonth = { year: y, month: m };
    renderSocial();
  };
  $("calPrev").onclick = () => move(-1);
  $("calNext").onclick = () => move(1);
  $("calToday").onclick = () => { _socialMonth = null; renderSocial(); };

  const build = async (weeks) => {
    // Every slot gets a written caption, and every reel slot a shot list and a
    // video prompt on top — so a four-week plan is dozens of model calls. This
    // is the slowest thing in the app and the one people re-press.
    //
    // The indicator no longer covers the screen, which is the point — but it
    // means these buttons stay clickable, so they are disabled for the
    // duration. Pressing Plan twice would otherwise start a second plan over
    // the first.
    const planBtns = [$("smBuild"), $("smBuild4")].filter(Boolean);
    if (planBtns.some((b) => b.disabled)) return;
    planBtns.forEach((b) => b.disabled = true);
    const n = weeks > 1 ? `${weeks} weeks` : "your week";
    try {
      await withBusy(
        `Planning ${n}…`,
        "Writing a caption for every post, and a shot list for every reel.",
        async () => {
          await api("/api/social/week", { method: "POST", json: { weeks } });
          busyStep("Laying the posts out across the calendar…");
          _socialData = await api("/api/social");
        });
      // The seller was told they could carry on using the app, so they may well
      // be somewhere else by now. Repainting Social over whatever they opened
      // would be the app grabbing the wheel back.
      if (_currentModule === "social") await renderSocial();
      toast(_currentModule === "social"
        ? "Planned. Replanning replaces drafts, it never doubles them."
        : `Your ${n} ${weeks > 1 ? "are" : "is"} planned, open Social Media Manager to see it.`);
    } catch (e) { toast(e.message); }
    // Re-enabled by id, because renderSocial() above may have replaced the DOM
    // these references point at.
    [$("smBuild"), $("smBuild4")].forEach((b) => { if (b) b.disabled = false; });
  };
  $("smBuild").onclick = () => build(1);
  $("smBuild4").onclick = () => build(4);
  if ($("apRunNow")) $("apRunNow").onclick = () => runAutoplanNow();
  if ($("apChange")) $("apChange").onclick = openSocialSetup;
  $("smShoot").onclick = openShootList;
  $("smSettings").onclick = openSocialSetup;
  const sq = $("smQueue");
  if (sq) sq.onclick = openPostQueue;
  const sp = $("smPerf");
  if (sp) sp.onclick = () => openSocialPerformance(28);
  const igBtn = $("smInsta");
  if (igBtn) igBtn.onclick = () => openModule("instagram");
  const igHere = $("igConnectHere");
  if (igHere) igHere.onclick = () => openModule("instagram");
  const igRe = $("igReconnect");
  if (igRe) igRe.onclick = () => openModule("instagram");
  $("smClearPlan").onclick = async () => {
    // Same destructive-action pattern as productDelete(): a native confirm()
    // up front, since wiping every planned post has no undo-toast-sized
    // amount of state to hold onto (unlike a single deleted product).
    //
    // The extra line about the picture allowance is here because clearing and
    // re-planning is the fastest way to burn through it: every post whose
    // picture you regenerate on the new plan spends one of the month's images,
    // and if the allowance runs out mid-replan the rest of the week falls back
    // to you uploading your own photos. A seller who is already low should know
    // that before they wipe a plan they have pictures on.
    const q = _imgQuota();
    let warn = "Delete every planned and scheduled post, and the current "
      + "campaign? This can't be undone.";
    if (q && q.enabled) {
      warn += q.left <= 0
        ? "\n\nYou have used all " + q.cap + " AI pictures this month, so any new "
          + "plan's photos will be your own uploads until it resets " + (q.resets || "on the 1st") + "."
        : q.left <= IMG_LOW_LEFT
          ? "\n\nHeads up: only " + q.left + " of " + q.cap + " AI pictures are left this "
            + "month. Re-planning and regenerating photos uses them up, and after that "
            + "you'll be uploading your own photos for the rest of the month."
          : "\n\nRe-planning regenerates photos, which uses your monthly picture "
            + "allowance (" + q.left + " of " + q.cap + " left). If it runs out you'll "
            + "add your own photos for the rest of the month.";
    }
    if (!confirm(warn)) return;
    try {
      await api("/api/social/clear", { method: "POST" });
      toast("Plan cleared.");
      _socialData = await api("/api/social");
      await renderSocial();
      refreshApprovals(true);
    } catch (e) { toast(e.message); }
  };

  const findPost = (id) => {
    for (const day of (_socialCal.days || []))
      for (const p of (day.posts || [])) if (p.id === id) return p;
    return null;
  };
  document.querySelectorAll("[data-open]").forEach((b) =>
    b.onclick = () => { const p = findPost(b.dataset.open); if (p) openSocialEditor(p); });

  // Drag a post onto another day to reschedule it. Only the date changes --
  // the time of day carries over, since sellers plan by morning/evening slot
  // as much as by day and a drag across the grid shouldn't quietly reset that.
  document.querySelectorAll(".cal-post").forEach((b) => {
    b.draggable = true;
    b.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", b.dataset.open);
      e.dataTransfer.effectAllowed = "move";
    });
  });
  document.querySelectorAll(".cal-cell:not(.is-pad)").forEach((cell) => {
    cell.addEventListener("dragover", (e) => { e.preventDefault(); cell.classList.add("cal-drop-over"); });
    cell.addEventListener("dragleave", () => cell.classList.remove("cal-drop-over"));
    cell.addEventListener("drop", async (e) => {
      e.preventDefault();
      cell.classList.remove("cal-drop-over");
      const id = e.dataTransfer.getData("text/plain");
      const post = id && findPost(id);
      const newDay = cell.dataset.day;
      if (!post || !newDay) return;
      const oldDay = (post.scheduled_at || "").slice(0, 10);
      if (newDay === oldDay) return;
      const time = (post.scheduled_at || "").slice(10) || "T09:00";
      try {
        await api("/api/social/post", { method: "POST",
          json: { post_id: id, patch: { scheduled_at: newDay + time } } });
        _socialData = await api("/api/social");
        await renderSocial();
        toast(`Moved to ${Number(newDay.slice(-2))} ${esc(cal.label.split(" ")[0])}.`);
      } catch (e2) { toast(e2.message); }
    });
  });
}

let _socialCal = null;

/* The automatic weekly plan, said in one line at the top of the planner. */
/* ------------------------------------------------- the Instagram strip -----
   THE BUG THIS FIXES: the Instagram connection screen existed, worked, and
   was completely unreachable. It had no tile on the home grid, no entry in
   openModule's dispatch, and nothing anywhere linked to it — a seller could
   not have connected their account if they had wanted to.

   It belongs here rather than on the home grid. Connecting Instagram is a step
   inside planning posts, not a sixteenth app to choose between, and this is
   the screen where the absence of a connection actually costs something. */
function igStrip(ig) {
  if (!ig) return "";
  if (ig.connected) {
    // Quiet when it is working. The only thing worth saying is when it is
    // about to stop working: a token dies at 60 days and a seller who finds
    // out by a post silently failing never trusts the feature again.
    if (!ig.needs_attention) return "";
    return `
      <div class="ap-strip off">
        <div class="ap-strip-t">${sic("alert")}
          <div><b>Your Instagram connection expires in ${Number(ig.expires_in_days) || 0} day${Number(ig.expires_in_days) === 1 ? "" : "s"}</b>
            <span class="muted tiny">Reconnect @${esc(ig.account_username || "")} and scheduled posts keep going out. It takes one tap.</span></div>
        </div>
        <div class="ap-strip-a"><button class="btn primary sm" id="igReconnect">${sic("refresh")}Reconnect</button></div>
      </div>`;
  }
  return `
    <div class="ap-strip off">
      <div class="ap-strip-t">${sic("instagram")}
        <div><b>Instagram is not connected</b>
          <span class="muted tiny">Everything below still works, the week is planned, written and scheduled. Connecting only changes the last step: approved posts go out by themselves instead of you posting them by hand.</span></div>
      </div>
      <div class="ap-strip-a">
        <button class="btn primary sm" id="igConnectHere">${sic("instagram")}Connect Instagram</button>
      </div>
    </div>`;
}

function autoplanStrip(ap) {
  if (!ap) return "";
  const hr = (h) => { const n = Number(h) || 0; return `${((n + 11) % 12) + 1}${n < 12 ? "AM" : "PM"}`; };
  const last = ap.last || null;
  return `
    <div class="ap-strip ${ap.enabled ? "on" : "off"}">
      <div class="ap-strip-t">
        ${sic("clock")}
        <div>
          <b>${ap.enabled
            ? `Plans next week by itself every ${esc(ap.day_name)} at ${esc(hr(ap.hour))}${ap.tz_label ? `${esc(ap.tz_label)}` : ""}`
            : "Automatic weekly planning is off"}</b>
          <span class="muted tiny">${ap.enabled
            ? (ap.pending_week ? `Next week is due now, it runs in the background as soon as it can.`
               : `Next run ${esc(ap.next_run_label || "")}. It checks festivals, what is already planned and how each product is selling, then puts the posts in your Approval panel.`)
            : "Turn it on in Setup and the week plans itself."}
            ${last ? `Last plan: ${esc(last.week_label || "")} – ${esc(last.note || "")}` : ""}</span>
        </div>
      </div>
      <div class="ap-strip-a">
        <button class="btn primary sm" id="apRunNow">${sic("spark")}Plan next week now</button>
        <button class="btn ghost sm" id="apChange">${sic("settings")}Change day</button>
      </div>
    </div>`;
}

async function runAutoplanNow() {
  const b = $("apRunNow");
  if (b && b.disabled) return;
  if (b) b.disabled = true;
  try {
    const r = await withBusy("Planning next week…",
      "Checking festivals and seasons, what is already on the calendar and how each product is selling, then writing each post and its Product Studio prompt.",
      () => api("/api/social/autoplan/run-now", { method: "POST", json: {} }));
    const br = r.brief || {};
    await afterPostChange();
    toast(br.added
      ? `${br.added} post${br.added === 1 ? "" : "s"} planned for ${br.week_label}, they are in your Approval panel.`
      : (br.note || "Nothing to add."), 8000);
  } catch (e) { toast(e.message, 6000); }
  if ($("apRunNow")) $("apRunNow").disabled = false;
}

function shortWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" })
       + " · " + d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

async function decidePost(id, newState) {
  try {
    // Cancelling a post that had failed resolves the failure. Without this the
    // record sits in localStorage waiting to attach itself to whatever insight
    // next carries that id.
    clearFailure("post_" + id);
    await api("/api/social/state", { method: "POST", json: { post_id: id, state: newState } });
    if (_currentModule === "social" && _socialData) {
      _socialData = await api("/api/social");
      await renderSocial();
    }
    refreshApprovals(true);   // the side panel is always on screen, whatever module this is
  } catch (e) { toast(e.message); }
}

// A reel has no single photograph that IS the video, so it never gets the
// image-generation buttons -- it gets a shot list to film from instead.
// This holds the script being edited for whichever reel post is currently
// open, mirroring the _wbRows pattern used for the win-back table.
let _smScript = { beats: [], voiceover: "", caption_hint: "", ai_prompt: "" };

function openSocialEditor(post) {
  const c = post.caption || {};
  const isReel = post.format === "reel";
  _smScript = post.script ? {
    beats: (post.script.beats || []).map((b) => ({ ...b })),
    voiceover: post.script.voiceover || "",
    caption_hint: post.script.caption_hint || "",
    ai_prompt: post.script.ai_prompt || "",
  } : { beats: [], voiceover: "", caption_hint: "", ai_prompt: "" };

  /* Where this post sits in the week's story. Without it the seller sees six
     posts and no reason why they are different from each other — which was
     the whole complaint. Now every post spells out: what KIND of post it is
     (format + the archetype / type of image), its PURPOSE, the STORY it belongs
     to and the role it plays, and HOW IT CONNECTS to the posts around it. */
  const FMT_LABEL = { reel: "Reel", carousel: "Carousel", image: "Single image" };
  const fmtLabel = FMT_LABEL[post.format] || (post.format ? esc(post.format) : "");
  const shotLabel = (post.shot_type || "").replace(/_/g, " ");
  // How this beat connects to the ones on either side of it in the week's arc.
  const CONNECT = {
    tease:  "Opens the week: it holds the product back so the reveal that follows lands.",
    reveal: "Follows the tease and shows the product properly; the proof posts back it up next.",
    prove:  "Earns the price the reveal set up, and leads into seeing it used in real life.",
    place:  "Puts the proven product into a real life, the payoff of the reveal and proof before it.",
    close:  "Closes the loop the week opened, turning the story into a reason to act now.",
  };
  const connect = CONNECT[post.beat] || (post.job || "");
  const roleLabel = post.story_role ? post.story_role.replace(/_/g, " ") : "";
  const storyBar = post.beat ? `
    <div class="sm-story">
      <div class="sm-story-line">
        <span class="sm-beat">${esc(post.beat)}</span>
        <b>${esc(post.archetype_label || "")}</b>
        ${fmtLabel ? `<span class="sm-fmt">${fmtLabel}</span>` : ""}
        ${post.occasion ? `<span class="sm-occ">${esc(post.occasion)}</span>` : ""}
      </div>
      ${post.story_name ? `<p class="sm-hint" style="margin:6px 0 0;"><b>Story:</b> ${esc(post.story_name)}${roleLabel ? ` · this post's role: <b>${esc(roleLabel)}</b>` : ""}</p>` : ""}
      <p class="sm-hint" style="margin:${post.story_name ? 2 : 6}px 0 0;"><b>Type of post:</b> ${fmtLabel || "Post"}${post.archetype_label ? ` – ${esc(post.archetype_label)}` : ""}${shotLabel ? ` <span class="muted">(${esc(shotLabel)} shot)</span>` : ""}</p>
      ${post.beat_job ? `<p class="sm-hint" style="margin:2px 0 0;"><b>Purpose:</b> ${esc(post.beat_job)}</p>` : ""}
      ${connect ? `<p class="sm-hint" style="margin:2px 0 0;"><b>How it connects:</b> ${esc(connect)}</p>` : ""}
      ${post.earns ? `<p class="sm-hint" style="margin:2px 0 0;"><b>Earns:</b> ${esc(post.earns)}</p>` : ""}
      ${post.theme ? `<p class="sm-hint" style="margin:2px 0 0;"><b>This week:</b> ${esc(post.theme)}</p>` : ""}
      ${post.plan_reason ? `<p class="sm-hint sm-why" style="margin:6px 0 0;"><b>Why this product:</b> ${esc(post.plan_reason)}</p>` : ""}
    </div>` : "";

  /* What Product Studio will draw, written when the week was planned from the
     product's own photo and the brand's look — readable before approving. */
  const studioBlock = (!isReel && post.image_prompt && !post.image_url) ? `
    <details class="sm-vid-opt" open>
      <summary>What Product Studio will draw${post.reference_photo ? " (starting from your photo)" : ""}</summary>
      <div class="sm-studio">
        ${post.reference_photo ? `<img src="${esc(post.reference_photo)}" alt="Your product photo" />` : ""}
        <pre class="pp-text">${esc(post.image_prompt)}</pre>
      </div>
    </details>` : "";

  /* Where the finished clip goes.
     A reel slot could be planned, scripted and handed a prompt for a video AI
     — and then there was nowhere to put the resulting video, so the format
     that reaches the most people was the one that could never be finished.
     The slot is always visible, empty or full, so it is obvious that a clip is
     what this post is still waiting for. */
  const videoBlock = (label) => `
    <div class="sm-vid" id="smVidBlock">
      <div class="sm-vid-slot" id="smVidSlot">
        ${post.video_url
          ? `<video src="${esc(post.video_url)}" controls playsinline preload="metadata"></video>`
          : `<div class="sm-vid-empty">${sic("play")}
               <b>${esc(label)}</b>
               <span>MP4 or WEBM, up to 48MB. Film it on your phone, or generate it
                     from the prompt below and upload the file here.</span>
             </div>`}
      </div>
      <div class="sm-vid-acts">
        <button class="btn ${post.video_url ? "ghost" : "primary"} sm" id="smVidPick">
          ${sic("arrow-up-right")}${post.video_url ? "Replace clip" : "Upload clip"}</button>
        <button class="btn ghost sm" id="smVidFlow">${sic("arrow-up-right")}Make it free in Google Flow</button>
        <button class="btn ghost sm" id="smVidGen">${sic("spark")}Make it here (paid)</button>
        ${post.video_url
          ? `<button class="btn ghost sm danger" id="smVidClear">${sic("close")}Remove</button>`
          : ""}
        <input type="file" id="smVidFile" accept="video/mp4,video/webm,video/quicktime" hidden />
      </div>
      <div id="smVidWm" class="muted tiny" style="margin:6px 0 0;">${post.video_url ? esc(clipNote({ ai_label: post.video_ai_label, watermark: post.video_watermark })) : ""}</div>
      ${wmFixRow("smWmFix")}
      <div id="rpTools"></div>
    </div>`;

  /* Warned about, never blocked. The app's rule everywhere else (caption
     checks, GST) is to say what the evidence says and let the seller decide;
     refusing to schedule a post because we cannot see a file would be a
     worse product than telling them plainly what is missing. */
  /* Asked every time, not captured once.
     This used to be a `const` read at render time, which is wrong the moment
     the seller uploads the clip WITHOUT closing the popup — the most ordinary
     path there is. The buttons would still think the post had no media and
     Save would refuse to schedule something that was sitting right there on
     screen, already playing. */
  const mediaMissing = () => (isReel ? !post.video_url : !(post.image_url || post.video_url));
  const needsMedia = mediaMissing();

  const topHtml = isReel ? `
    ${storyBar}
    <div class="sm-ed-script-block">
      <div class="sm-ed-meta">
        <div><b>${esc(post.pillar_name || "")}</b> · Reel
          ${post.occasion ? `<span class="sm-occ">${esc(post.occasion)}</span>` : ""}</div>
      </div>
      ${videoBlock("No clip uploaded yet")}
      <p class="sm-hint" style="margin:12px 0;"><b>This is a reel, so it needs a video.</b>
        Film it on your phone from the shot list below, that usually looks better than
        anything an AI makes, or press "Generate a clip" above and pick which AI does it.
        Either way, the clip goes in the slot above.</p>
      <div id="smEdScript"></div>
    </div>` : `
    ${storyBar}
    <div class="sm-ed-top">
      <div class="sm-ed-shot" id="smEdShot">
        ${post.image_url
          ? `<img src="${esc(post.image_url)}" alt="" />${post.image_generated ? `<span class="sm-gen">AI</span>` : ""}`
          : `<div class="sm-ed-noimg">${sic("image")}<span>No picture yet</span></div>`}
      </div>
      <div class="sm-ed-meta">
        <div><b>${esc(post.pillar_name || "")}</b> · ${esc(post.format || "")}
          ${post.occasion ? `<span class="sm-occ">${esc(post.occasion)}</span>` : ""}</div>
        <div class="sm-ed-imgacts">
          <button class="btn primary sm" id="smGenRef">${sic("image")}Re-shoot my photo</button>
          <button class="btn ghost sm" id="smGenNew">${sic("spark")}Invent a picture</button>
          <button class="btn ghost sm" id="smUpImg">${sic("arrow-up-right")}Use my own photo</button>
        </div>
        <div class="ai-pick" id="smEnginePick">
          <label for="smEngine">Draw with</label>
          <select id="smEngine"><option value="">Loading…</option></select>
          <span class="ai-pick-note" id="smEngineNote"></span>
        </div>
        <div class="row" style="margin-top:6px;">
          <button class="btn ghost tiny" id="smShowPrompt">See exactly what we will ask for</button>
        </div>
        <div id="smPromptBox" hidden></div>
        <p class="sm-hint" style="margin:8px 0 0;">
          <b>Re-shoot</b> starts from your own photograph, so the item in the picture
          is the item you ship, only the light and setting change.
          <b>Invent</b> draws from the description instead: fine for a backdrop,
          not for showing a customer what they are buying.</p>
      </div>
    </div>
    ${studioBlock}
    <details class="sm-vid-opt">
      <summary>Post a video instead of the picture</summary>
      ${videoBlock("No clip on this post")}
    </details>`;

  openModal(`${esc(shortWhen(post.scheduled_at))} – ${esc(post.product_name || "")}`, `
    ${topHtml}
    <label class="fld"><span>Hook <em id="smHookCount">${(c.hook || "").length} / 125</em></span>
      <textarea id="smHook" data-ai="caption_hook" data-ai-ctx="post" data-ai-label="Hook" rows="2">${esc(c.hook || "")}</textarea></label>
    <p class="sm-hint">Instagram cuts the caption at 125 characters. Everything past
      that hides behind "… more", so the product and the reason to care both belong here.</p>

    <label class="fld"><span>Body</span>
      <textarea id="smBody" data-ai="caption" data-ai-ctx="post" data-ai-label="Caption body, under 30 words" rows="4">${esc(c.body || "")}</textarea></label>
    <p class="sm-hint">Under 30 words performs best across nine million posts studied.</p>

    <label class="fld"><span>Question</span>
      <input id="smQ" value="${esc(c.question || "")}" /></label>
    <p class="sm-hint">A comment-focused question is the single biggest lever in a
      caption, worth roughly 200% more comments.</p>

    <label class="fld"><span>How to order</span>
      <input id="smCta" value="${esc(c.cta || "")}" /></label>

    <label class="fld"><span>Hashtags <em>max 5</em></span>
      <input id="smTags" value="${esc((c.tags || []).join(" "))}" /></label>
    <p class="sm-hint">Instagram capped hashtags at 5 in January 2026. They are worth
      about +2% reach now, the category words in your hook matter more.</p>

    <label class="fld"><span>When</span>
      <input id="smWhen" type="datetime-local" value="${esc(post.scheduled_at || "")}" /></label>

    ${needsMedia ? `<div class="sm-needs">${sic("alert")}
      <span>${isReel
        ? "This reel has no clip yet. Upload one above and it is ready to schedule."
        : "This post has no picture or clip yet. Add one above and it is ready to schedule."}</span>
    </div>` : ""}

    <div class="modal-actions">
      <button class="btn ghost" data-mclose2>Close</button>
      ${post.state === "draft" ? `<button class="btn reject" id="smSkip">Cancel post</button>` : ""}
      <!-- ORDER IS THE BUG HERE, AND IT COST REAL POSTS.
           This used to ask "is it an approved reel?"BEFORE "is it ready?", so
           an approved reel that already had its clip uploaded was still only
           offered "Open the video task", never "Save & schedule". The seller
           uploaded the clip in this very editor, pressed Save, and the post
           stayed approved forever. Nothing publishes from the approved state:
           the publisher selects on scheduled. The post simply never went out
           and nothing said so.
           Ready beats reel-ness. A post that has its media can be scheduled,
           whatever shape it is. -->
      ${post.state === "approved" && !needsMedia
        ? `<button class="btn approve" id="smSched">Save &amp; schedule</button>`
        : post.state === "approved" && isReel
          ? `<button class="btn approve" id="smTask">${sic("play")}Open the video task</button>`
          : post.state === "draft"
            ? `<button class="btn approve" id="smApprove">${isReel ? "Approve & add the video task" : "Approve & make the picture"}</button>` : ""}
      ${post.state === "scheduled" && !needsMedia
        ? `<button class="btn ghost" id="smNow" title="Send this to Instagram right now instead of waiting for its time">${sic("instagram")}Post now</button>` : ""}
      <button class="btn primary" id="smSave">Save</button>
    </div>
    <div id="smNowMsg"></div>`, { owner: post.id });

  /* WHY "POST NOW"EXISTS: the only way to find out whether posting really
     works was to schedule something and then wait — for the time to arrive,
     and then for the fifteen-minute ticker after it. A forty-minute feedback
     loop on a thing that either works or does not is why "is it even posting?"
     went unanswered for so long. This answers it in ten seconds, with the real
     result rather than a cheerful acknowledgement. */
  const nowBtn = $("smNow");
  if (nowBtn) nowBtn.onclick = async () => {
    if (!confirm("Send this to Instagram now? It goes out immediately and cannot be unsent from here.")) return;
    const box = $("smNowMsg");
    nowBtn.disabled = true; nowBtn.textContent = "Posting…";
    box.innerHTML = `<p class="muted tiny">Sending to Instagram. A reel can take a minute while Instagram processes the video.</p>`;
    try {
      const r = await api("/api/social/post-now", { method: "POST", json: { post_id: post.id } });
      if (r.ok) {
        box.innerHTML = `<div class="focus-box" style="background:var(--green-soft,var(--surface-2));border-radius:8px;padding:10px 12px;">
          <b style="color:var(--green);">✓ Posted.</b>
          ${r.permalink ? ` <a href="${esc(r.permalink)}" target="_blank" rel="noopener">See it on Instagram</a>` : ""}</div>`;
        warmModClearAll();
      } else {
        box.innerHTML = `<div class="focus-box" style="background:var(--amber-soft,var(--surface-2));border-radius:8px;padding:10px 12px;">
          <b style="color:var(--amber);">It did not go out.</b>
          <div class="muted tiny" style="margin-top:3px;">${esc(r.error || "Instagram refused it.")}</div></div>`;
      }
    } catch (e) {
      box.innerHTML = `<span class="err">${esc(e.message)}</span>`;
    }
    nowBtn.disabled = false; nowBtn.innerHTML = `${sic("instagram")}Post now`;
  };

  if (isReel) renderScriptSection(post);

  /* Uploading the clip. Two steps on purpose: the file goes to the durable
     media store first (which already handles video up to 48MB and survives a
     redeploy), then the post records which clip is its own. Doing it in one
     endpoint would have meant a second upload path to keep correct. */
  /* Which AI draws this picture. Loaded from the server rather than hardcoded,
     so the list only ever offers engines that actually have a key — an option
     that fails on click is worse than no option. Re-shoot and Invent have
     DIFFERENT valid sets (Cloudflare can invent but would redraw the product
     on a re-shoot), so the list is reloaded when the seller switches between
     them rather than showing one union that is wrong for one of the two. */
  let _engines = [], _engineFor = null;
  async function loadEngines(forReshoot) {
    if (_engineFor === forReshoot) return;
    const sel = $("smEngine"), note = $("smEngineNote");
    if (!sel) return;
    try {
      const d = await api(`/api/studio/image-engines?reshoot=${forReshoot ? "true" : "false"}`);
      _engines = d.engines || [];
      _engineFor = forReshoot;
      sel.innerHTML = _engines.length
        ? _engines.map((e) => `<option value="${esc(e.id)}">${esc(e.label)}${e.free ? ", free tier" : ""}</option>`).join("")
        : `<option value="">No engine connected</option>`;
      const showNote = () => {
        const e = _engines.find((x) => x.id === sel.value);
        if (note) note.textContent = e ? `${e.cost}. ${e.note}` : "";
        showAiLeft();          // re-append the remaining count after a repaint
      };
      sel.onchange = showNote;
      showNote();
    } catch (e) {
      sel.innerHTML = `<option value="">Could not load engines</option>`;
    }
  }
  if ($("smEngine")) loadEngines(true);
  // What is left of today's allowance, shown before they press anything. A cap
  // discovered by hitting it feels like a fault; a cap you can see is a budget.
  showAiLeft();

  /* "It ignored my brand" and "it was never told about my brand" look identical
     from outside. This shows which one happened, before anything is spent. */
  if ($("smShowPrompt")) $("smShowPrompt").onclick = async () => {
    const box = $("smPromptBox"), btn = $("smShowPrompt");
    if (!box.hidden) { box.hidden = true; btn.textContent = "See exactly what we will ask for"; return; }
    btn.disabled = true; btn.textContent = "Checking…";
    try {
      const d = await api("/api/studio/prompt-preview", { method: "POST", json: {
        product_id: post.product_id, pillar: post.pillar || "", format: post.format || "",
        post_id: post.id, use_reference: true, shot_type: post.shot_type || "" } });
      const gaps = (d.sources || []).filter((x) => !x.have);
      box.innerHTML = `
        <div class="prompt-peek">
          <div class="pp-head">What the AI is told <span class="muted tiny">${d.words} words${d.from_reference ? " · starting from your own photo" : " · no photo to start from"}</span></div>
          <pre class="pp-text">${esc(d.prompt)}</pre>
          <div class="pp-src">${(d.sources || []).map((x) => `
            <div class="pp-row ${x.have ? "on" : "off"}"><i>${x.have ? "✓" : "–"}</i>
              <b>${esc(x.part)}</b><span class="muted tiny">${esc(x.note)}</span></div>`).join("")}</div>
          ${gaps.length ? `<p class="muted tiny" style="margin:8px 0 0;">
            The greyed-out rows are what is missing. Filling those in is what makes the
            next picture look more like yours.</p>` : ""}
        </div>`;
      box.hidden = false;
      btn.textContent = "Hide";
    } catch (e) { toast(e.message); btn.textContent = "See exactly what we will ask for"; }
    btn.disabled = false;
  };

  const vidPick = $("smVidPick"), vidFile = $("smVidFile");
  if (vidPick && vidFile) {
    vidPick.onclick = () => vidFile.click();
    vidFile.onchange = async () => {
      const f = vidFile.files && vidFile.files[0];
      if (!f) return;
      // Checked here as well as on the server so a seller on a slow connection
      // is told immediately, instead of after uploading 60MB.
      if (f.size > 48 * 1024 * 1024) {
        return toast("That clip is over 48MB. Export it at 1080p, a reel rarely "
                     + "needs more.", 7000);
      }
      /* The bar goes INSIDE the clip slot — the box the video is about to
         appear in — rather than behind a modal. The seller watches the thing
         fill up in the place it is going to end up. */
      const bar = progressBar($("smVidBlock") || $("smVidSlot"),
                              `Uploading ${Math.round(f.size / 1048576)}MB clip`);
      try {
        const fd = new FormData();
        fd.append("files", f);
        const up = await apiUpload("/api/site/image", fd, (frac) => bar.set(frac));
        const u = up.url || up.image_url;
        if (!u) throw new Error("The upload did not come back with a file.");
        /* A clip in the post editor can be either: generated in Flow, or
           filmed on a phone. The label is required for one and wrong for the
           other, so this is the one place we ask. Backing out of the question
           still attaches the clip unlabelled, and says so, rather than losing
           an upload the seller already waited for. */
        const aiMade = await askClipOrigin();
        bar.working(aiMade ? "Adding the \u201cAI generated\u201d label\u2026"
                           : "Saving the clip\u2026");
        const att = await attachClip(post.id, u, aiMade === null ? false : aiMade);
        if (aiMade === null) {
          toast("Clip saved without a label. If an AI tool made it, add the AI "
                + "label in Instagram before you post.", 9000);
        }
        if (clipNote(att)) toast(clipNote(att), att.fallback ? 9000 : 4000);
        const url = att.video_url || u;     // the labelled copy when a label went on
        bar.done("Clip attached");
        post.video_url = url;
        const slotEl = $("smVidSlot");
        if (slotEl) {
          slotEl.innerHTML =
            `<video src="${esc(url)}" controls playsinline preload="metadata"></video>`;
          vidPick.innerHTML = sic("arrow-up-right") + "Replace clip";
          if ($("smWmFix")) $("smWmFix").hidden = false;
          vidPick.className = "btn ghost sm";
        }
        _socialData = await api("/api/social");
        /* The post just became schedulable while the popup is still open, so
           the buttons have to say so now. Without this the seller is looking
           at their own clip playing above a button that still only offers to
           open a video task. */
        syncEditorActions();
        toast("Clip attached, this post is ready to schedule.");
      } catch (e) {
        bar.fail(e.message);
        toast(e.message, 7000);
      }
      vidFile.value = "";       // so picking the same file again still fires
    };
  }
  /* Generating a clip costs real money per call and takes about a minute, so
     the price is confirmed BEFORE anything is spent — never after. */
  /* Offered BEFORE the paid button, and labelled as free, because it is the
     better answer for almost every seller: Flow gives them about five clips a
     day for nothing and shows them the result before they commit, where our own
     generator charges roughly a hundred rupees a clip sight unseen. */
  const vidFlow = $("smVidFlow");
  if (vidFlow) vidFlow.onclick = async () => {
    const text = ((post.script || {}).ai_prompt || post.video_prompt
                  || (post.caption || {}).hook || "").trim();
    let copied = false;
    if (text) {
      try { await navigator.clipboard.writeText(text); copied = true; } catch (e) { copied = false; }
    }
    await showVideoTools(text, copied && !!text);
  };

  const vidGen = $("smVidGen");
  if (vidGen) vidGen.onclick = async () => {
    let eng;
    try { eng = await api("/api/studio/video-engine"); }
    catch (e) { return toast(e.message, 6000); }
    if (!eng.ready) return toast(eng.note, 8000);
    const opts = eng.engines || [];
    // The seller picks the engine and sees the price before a rupee moves. A
    // clip is the most expensive thing in the app — six times the price
    // difference between the two engines — so this is a real choice, not a
    // confirmation dialog with the decision already made.
    const picked = await pickVideoEngine(opts);
    if (!picked) return;
    try {
      const vid = await withBusy(`Making your clip with ${picked.label}…`,
        "One to three minutes. It animates your own photograph, so the product "
        + "stays yours. You can go and do something else, it keeps going.",
        () => api("/api/studio/video", { method: "POST", json: {
          product_id: post.product_id, post_id: post.id,
          engine: picked.id || "" } }));
      post.video_url = vid.url;
      showAiLeft(true);
      const mine3 = document.querySelector(`.modal[data-post="${post.id}"]`);
      const slot = mine3 && mine3.querySelector("#smVidSlot");
      if (slot) {
        slot.innerHTML = `<video src="${esc(vid.url)}" controls playsinline preload="metadata"></video>`;
        if (vidPick) { vidPick.innerHTML = sic("arrow-up-right") + "Replace clip"; vidPick.className = "btn ghost sm"; }
        if ($("smWmFix")) $("smWmFix").hidden = false;
        /* The upload path did this and the paid path did not, so a seller who
           PAID for a clip watched it appear in the slot and was still told
           "This reel has no clip yet" above a button offering to walk them
           through making one. The post was schedulable; only the screen
           disagreed, which is the worst version of this. */
        syncEditorActions();
      }
      _socialData = await api("/api/social");
      toast("Clip made and attached. Check it before you schedule, the product "
            + "holds for the first couple of seconds, then detail can drift.", 9000);
    } catch (e) { toast(e.message, 8000); }
  };

  wireWmFix("smWmFix", post);
  const vidClear = $("smVidClear");
  if (vidClear) vidClear.onclick = async () => {
    try {
      await api("/api/social/attach-video", { method: "POST",
        json: { post_id: post.id, url: "" } });
      post.video_url = "";
      closeModal();
      await afterEdit();
      toast("Clip removed. The post and its caption are untouched.");
    } catch (e) { toast(e.message); }
  };

  const gen = async (useRef) => {
    // Before spending a picture, tell the seller where they stand — a limit you
    // can see coming is a budget, one you hit by surprise feels like a fault.
    // Spent: skip the call entirely and go straight to uploading their own
    // photo (with the shot we would have drawn). Low: confirm the spend. The
    // count is read from the last /api/social load, refreshed after each draw.
    const q = _imgQuota();
    if (q && q.enabled) {
      if (q.left <= 0) {
        toast("That is all " + q.cap + " AI pictures for this month. Add your own "
          + "photo instead, resets " + (q.resets || "on the 1st") + ".", 8000);
        openPhotoUploadForPost(post);
        return;
      }
      if (q.left <= IMG_LOW_LEFT) {
        if (!confirm("You have " + q.left + " of " + q.cap + " AI pictures left this "
          + "month, and this uses one. When they run out, posts ask you to upload your "
          + "own photo. Generate this one now?")) return;
      }
    }
    const btns = [$("smGenRef"), $("smGenNew")].filter(Boolean);
    btns.forEach((b) => b.disabled = true);
    const b = useRef ? $("smGenRef") : $("smGenNew");
    const was = b.innerHTML; b.innerHTML = sic("image") + "Drawing…";
    try {
      const img = await withBusy(
        useRef ? "Re-shooting your photo…" : "Drawing your picture…",
        useRef
          ? "Starting from your own photograph, so the item stays the item you ship."
          : "Building it from your brand's look and this product's description.",
        () => api("/api/studio/image", { method: "POST", json: {
          product_id: post.product_id, pillar: post.pillar, format: post.format,
          post_id: post.id, use_reference: useRef, shot_type: post.shot_type || "",
          engine: ($("smEngine") || {}).value || "" } }));
      /* WHOSE POPUP IS THIS? Drawing takes half a minute and sellers do not
         sit and watch it — they close the popup and open the next post. Asking
         for `#smEdShot` finds whatever editor is open NOW, so without the
         ownership check this painted post A's picture into post B's frame.
         The picture is saved to post A either way; there is nothing to
         recover, only someone else's popup to not write into. */
      showAiLeft(true);
      post.image_url = img.url;
      const mine = document.querySelector(`.modal[data-post="${post.id}"]`);
      const shotEl = mine && mine.querySelector("#smEdShot");
      if (shotEl) { shotEl.innerHTML = `<img src="${esc(img.url)}" alt="" /><span class="sm-gen">AI</span>`; offerSchedule(); }
      else toast("Your picture is ready, reopen the post to see it.", 6000);
      if (img.ai_label && img.ai_label.labelled) {
        toast("Picture made, and labelled \u201cAI generated\u201d in the corner. "
              + "Indian law has required that on AI pictures since February 2026, "
              + "so it goes on every one of them.", 7000);
      }
      if (useRef && !img.had_reference) {
        toast("No photo on this product, so it was invented rather than re-shot. " +
              "Add a photo in Product Studio for a picture of the real item.", 7000);
      }
      _socialData = await api("/api/social");
      refreshImgQuota();          // move the header tracker without a full repaint
    } catch (e) {
      // Hitting the monthly allowance mid-draw is not an error to shrug at: the
      // server has put an upload task on this post, so open that flow rather
      // than leaving a red toast the seller cannot act on.
      if (e.status === 429 && e.code === "monthly_image_cap") {
        toast(e.message, 8000);
        try { _socialData = await api("/api/social"); refreshImgQuota(); } catch (_) {}
        openPhotoUploadForPost(post);
      } else {
        toast(e.message, 6000);
      }
      b.innerHTML = was;
    }
    btns.forEach((x) => x.disabled = false);
  };
  // The seller's own photograph, straight onto the post — the answer when no
  // image AI is connected, and often the better picture anyway. Deliberately NOT
  // labelled: it is a real photograph of a real product, and stamping "AI
  // generated" on it would be a false claim about their own goods.
  if ($("smUpImg")) $("smUpImg").onclick = () => pickImage(async (url) => {
    try {
      await api("/api/social/attach-image", { method: "POST", json: { post_id: post.id, url } });
      post.image_url = url;
      const mine2 = document.querySelector(`.modal[data-post="${post.id}"]`);
      const shotEl = mine2 && mine2.querySelector("#smEdShot");
      if (shotEl) shotEl.innerHTML = `<img src="${esc(url)}" alt="" />`;
      offerSchedule();
    } catch (e) { toast(e.message, 6000); }
  });
  // An approved post that was only waiting for its picture can go out as soon
  // as it has one — offer Save & schedule right here instead of a round trip.
  /* WHY THIS IS NOT ITS OWN FUNCTION ANY MORE.
     There used to be a second one here — `offerSchedule` — that built a button
     with the same id, the same label and the same green, but which sent only
     `post_id` and `scheduled_at`. It was the button the picture paths added,
     so a seller who rewrote their caption and then pressed "Invent a picture"
     got a Save & schedule that silently threw the caption away. That is the
     exact bug the note above `saveEditor` says was fixed on the other path;
     having two functions build the same button was what let it live on in one
     of them. There is one now. */
  const offerSchedule = () => syncEditorActions({ force: true });
  if ($("smGenRef")) $("smGenRef").onclick = async () => { await loadEngines(true); gen(true); };
  if ($("smGenNew")) $("smGenNew").onclick = async () => { await loadEngines(false); gen(false); };

  const h = $("smHook"), cnt = $("smHookCount");
  if (h && cnt) h.oninput = () => {
    cnt.textContent = `${h.value.length} / 125`;
    cnt.classList.toggle("over", h.value.length > 125);
  };
  document.querySelector("[data-mclose2]").onclick = closeModal;
  const afterEdit = async () => {
    if (_currentModule === "social" && _socialData) {
      _socialData = await api("/api/social");
      await renderSocial();
    }
    refreshApprovals(true);
  };
  // Approve here means the same as in the Approval panel: a photo post gets
  // its picture made and is scheduled; a reel gets its task.
  if ($("smApprove")) $("smApprove").onclick = async () => {
    closeModal();
    await approvePostReady(post.id);
  };
  if ($("smTask")) $("smTask").onclick = () => {
    const t = ((((state.lastState || {}).tasks) || []).find((x) => x.post_id === post.id && !x.done));
    closeModal();
    openVideoTask(t ? t.id : `post-${post.id}`, post);
  };
  /* Everything typed into this popup, in one place.
     "Save & schedule" used to send only `post_id` and `scheduled_at`, so a
     seller who rewrote the hook and then pressed the obvious green button
     watched their edit vanish. Both buttons collect the same patch now. */
  const collectPatch = () => {
    const tags = ($("smTags").value || "").split(/\s+/).filter(Boolean).slice(0, 5);
    const patch = {
      hook: $("smHook").value, body: $("smBody").value, question: $("smQ").value,
      cta: $("smCta").value, tags, scheduled_at: $("smWhen").value,
    };
    if (isReel) {
      patch.script = {
        beats: _smScript.beats.filter((b) => (b.shot || "").trim() || (b.on_screen_text || "").trim()),
        voiceover: _smScript.voiceover, caption_hint: _smScript.caption_hint,
      };
    }
    return patch;
  };

  /* Turns "Open the video task" into "Save & schedule" in place, the instant
     the post stops needing media. Surgical rather than a full re-render,
     because a re-render would throw away whatever the seller has typed into
     the caption fields but not yet saved. */
  function syncEditorActions(opts = {}) {
    /* WHOSE POPUP IS THIS?
       Generating a picture takes half a minute on a small server, and a seller
       does not sit and watch it: they close the popup and open the next post.
       `document.querySelector(".modal-actions")` finds whatever popup is open
       NOW — thirty-one elements in this app carry that class — so without this
       check the finished job writes post A's button, closed over post A, into
       post B's popup. Pressing it scheduled A at B's time.
       The popup stamps the post it belongs to; a late arrival that finds
       someone else's popup does nothing, which is the correct outcome. */
    const acts = document.querySelector(`.modal[data-post="${post.id}"] .modal-actions`);
    if (!acts) return;
    if (post.state !== "approved") return;
    if (!opts.force && mediaMissing()) return;
    const warn = acts.closest(".modal").querySelector(".sm-needs");
    if (warn) warn.remove();
    if ($("smSched")) return;                       // already the right button
    const task = $("smTask");
    const b = document.createElement("button");
    b.className = "btn approve";
    b.id = "smSched";
    b.innerHTML = "Save &amp; schedule";
    b.onclick = () => saveEditor({ schedule: true });
    if (task) task.replaceWith(b);
    else acts.insertBefore(b, $("smSave"));
  }

  if ($("smSched")) $("smSched").onclick = () => saveEditor({ schedule: true });
  if ($("smSkip")) $("smSkip").onclick = async () => {
    await decidePost(post.id, "cancelled");
    closeModal();
    toast("Cancelled, it will not go out.");
  };
  $("smSave").onclick = () => saveEditor({ schedule: "if-ready" });

  /* WHY PLAIN "SAVE"ALSO SCHEDULES.
     A seller approves a reel, comes here, uploads the clip, fixes the caption
     and presses Save — and reasonably believes the post is now going out. It
     was not: Save only patched the fields, the post stayed `approved`, and the
     publisher only ever selects `scheduled`. The post sat there until someone
     noticed it had never appeared.
     There is no case where a seller edits an approved, media-complete post and
     means "and do not put it in the calendar". So Save finishes the job and
     says which of the two things it did. Where it cannot — the media is still
     missing — it says that too, instead of succeeding silently and leaving a
     post that can never go out. */
  async function saveEditor({ schedule }) {
    const btn = schedule === true ? $("smSched") : $("smSave");
    const was = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
    const wantSchedule = schedule === true
      || (schedule === "if-ready" && post.state === "approved" && !mediaMissing());
    try {
      await api("/api/social/post", { method: "POST", json: { post_id: post.id, patch: collectPatch() } });
      let scheduled = false;
      if (wantSchedule) {
        const r = await api("/api/social/schedule-ready", { method: "POST",
          json: { post_id: post.id, scheduled_at: $("smWhen").value } });
        if (r.tasks) refreshTaskList(r.tasks);
        scheduled = true;
      }
      closeModal();
      await afterEdit();
      toast(scheduled
        ? `Saved and scheduled for ${shortWhen($("smWhen").value || post.scheduled_at)}.`
        : mediaMissing() && post.state === "approved"
          ? (isReel
             ? "Saved. It still needs a clip before it can go out, upload one and it schedules itself."
             : "Saved. It still needs a picture before it can go out.")
          : "Saved.");
    } catch (e) {
      if (btn) { btn.disabled = false; btn.innerHTML = was; }
      toast(e.message, 6000);
    }
  }
}

/* The reel shot-list editor: an empty/generate state for reels planned
   before scripts existed, and an editable beat list once one is written --
   same shape as the win-back table (_wbRows / renderWinbackTable), just
   scoped to _smScript instead. */
function renderScriptSection(post) {
  const el = $("smEdScript");
  if (!el) return;
  const has = _smScript.beats.length > 0;
  el.innerHTML = has ? `
    <div class="sm-script-rows" id="smBeats"></div>
    <button class="btn ghost sm" id="smAddBeat">${sic("plus")}Add beat</button>
    <label class="fld" style="margin-top:12px;"><span>Voiceover <em>optional</em></span>
      <textarea id="smVoiceover" data-ai="voiceover" data-ai-ctx="reel" data-ai-label="Voiceover" rows="2">${esc(_smScript.voiceover || "")}</textarea></label>

    ${_smScript.ai_prompt ? `
    <div class="sm-prompt">
      <div class="sm-prompt-head">
        <div>
          <b>Prompt for a video AI</b>
          <p class="sm-hint" style="margin:2px 0 0;">Paste this straight into Gemini,
            Veo, Sora or Kling. It already carries your product, your look and this
            week's story.</p>
        </div>
        <button class="btn ghost tiny" id="smCopyPrompt">${sic("layers")}Copy</button>
      </div>
      <pre class="sm-prompt-body" id="smPromptBody">${esc(_smScript.ai_prompt)}</pre>
    </div>` : ""}

    <div style="margin-top:10px;">
      <button class="btn ghost sm" id="smRegenScript">${sic("spark")}Regenerate script</button>
    </div>` : `
    <div class="sm-ed-noimg" style="height:auto;padding:22px 10px;">
      ${sic("spark")}<span>No shot list yet, this reel was planned before scripts existed.</span>
    </div>
    <button class="btn primary sm" id="smGenScript" style="margin-top:10px;">${sic("spark")}Generate script</button>`;

  if (has) {
    renderBeatRows();
    $("smAddBeat").onclick = () => {
      _smScript.beats.push({ sec: "", shot: "", on_screen_text: "" });
      renderBeatRows();
    };
    $("smVoiceover").onchange = (e) => { _smScript.voiceover = e.target.value; };
    $("smRegenScript").onclick = () => generateScript(post, $("smRegenScript"));
    if ($("smCopyPrompt")) $("smCopyPrompt").onclick = async () => {
      const b = $("smCopyPrompt"), was = b.innerHTML;
      try {
        await navigator.clipboard.writeText(_smScript.ai_prompt || "");
        b.innerHTML = sic("check") + "Copied";
      } catch (e) {
        // Clipboard is blocked in some embedded webviews — select the text so
        // the seller can still copy it by hand rather than hitting a dead button.
        const r = document.createRange();
        r.selectNodeContents($("smPromptBody"));
        const sel = window.getSelection();
        sel.removeAllRanges(); sel.addRange(r);
        b.innerHTML = sic("check") + "Selected: press Ctrl+C";
      }
      setTimeout(() => { b.innerHTML = was; }, 2500);
    };
  } else {
    $("smGenScript").onclick = () => generateScript(post, $("smGenScript"));
  }
}

function renderBeatRows() {
  const el = $("smBeats");
  if (!el) return;
  el.innerHTML = _smScript.beats.map((b, i) => `
    <div class="sm-beat-row" data-r="${i}">
      <input class="sm-beat-sec" data-k="sec" value="${esc(b.sec || "")}" placeholder="0-3s" />
      <input class="sm-beat-shot" data-k="shot" value="${esc(b.shot || "")}" placeholder="Camera / shot" />
      <input class="sm-beat-osd" data-k="on_screen_text" value="${esc(b.on_screen_text || "")}" placeholder="On-screen text" />
      <button class="btn ghost tiny" data-del="${i}" title="Remove beat" aria-label="Remove this beat from the shot list">${sic("close")}</button>
    </div>`).join("") || `<p class="muted" style="margin:6px 0;">No beats yet: add one below.</p>`;
  el.querySelectorAll("input").forEach((inp) => inp.onchange = (e) => {
    const row = e.target.closest("[data-r]");
    _smScript.beats[+row.dataset.r][e.target.dataset.k] = e.target.value;
  });
  el.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => {
    _smScript.beats.splice(+b.dataset.del, 1);
    renderBeatRows();
  });
}

async function generateScript(post, btn) {
  const was = btn.innerHTML;
  btn.disabled = true; btn.innerHTML = sic("spark") + "Writing…";
  try {
    const updated = await withBusy(
      "Writing the shot list…",
      "Turning this post into beats you can film, plus a prompt for a video AI.",
      () => api("/api/social/regenerate-script", { method: "POST", json: { post_id: post.id } }));
    const sc = updated.script || {};
    _smScript = {
      beats: (sc.beats || []).map((b) => ({ ...b })),
      voiceover: sc.voiceover || "", caption_hint: sc.caption_hint || "",
      ai_prompt: sc.ai_prompt || "",
    };
    renderScriptSection(post);
    toast("Script written.");
    _socialData = await api("/api/social");
  } catch (e) {
    toast(e.message, 6000);
    btn.disabled = false; btn.innerHTML = was;
  }
}

async function openShootList() {
  let sl;
  try { sl = await api("/api/social/shoot-list"); }
  catch (e) { return toast(e.message); }
  openModal("Shoot list", `
    <p class="muted" style="margin-top:0;">One session of about ${esc(String(sl.minutes))}
       minutes on ${esc(String((sl.products || []).length))} products gives you
       ${esc(String((sl.yields || []).length))} assets, two to three weeks of posting.
       Batching is the only way the arithmetic works.</p>
    <div class="sm-shoot">
      <h4>Shoot these</h4>
      <ul>${(sl.products || []).map(p => `<li>${esc(p.name)}</li>`).join("") || "<li>Add a product first</li>"}</ul>
      <h4>For each one</h4>
      <ul>${(sl.per_product || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul>
      <h4>What it turns into</h4>
      <table class="sm-yield"><tbody>
        ${(sl.yields || []).map(y => `<tr><td><b>${esc(y.asset)}</b></td><td>${esc(y.from)}</td><td>${esc(y.angle)}</td></tr>`).join("")}
      </tbody></table>
      <p class="sm-note">${esc(sl.note || "")}</p>
    </div>
    <div class="modal-actions"><button class="btn primary" data-mclose3>Close</button></div>`);
  document.querySelector("[data-mclose3]").onclick = closeModal;
}

let _locale = null;                       // {country, tz, label, options[]}

async function loadLocale(force) {
  if (_locale && !force) return _locale;
  try { _locale = await api("/api/settings/locale"); } catch (e) { _locale = null; }
  return _locale;
}

async function openSocialSetup() {
  const d = _socialData, s = d.settings || {};
  const loc = await loadLocale();
  openModal("Social setup", `
    <label class="fld"><span>What do you sell?</span>
      <select id="soCat">${["clothing", "jewellery", "perfume"].map(c =>
        `<option value="${c}"${s.category === c ? " selected" : ""}>${c}</option>`).join("")}</select></label>

    <label class="fld"><span>Language</span>
      <select id="soLang">${Object.entries(d.languages || {}).map(([k, v]) =>
        `<option value="${k}"${s.language === k ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></label>
    <p class="sm-hint">Hinglish in Roman script is the default because 76% of Indian
      festive shoppers prefer advertising in their own language, and Roman script reads
      across literacy levels without a keyboard switch.</p>

    <label class="fld"><span>How much time do you have?</span>
      <select id="soCad">${Object.entries(d.cadence || {}).map(([k, v]) =>
        `<option value="${k}"${s.cadence === k ? " selected" : ""}>${esc(v.label)} – ${esc(String(v.posts))} posts a week, ${esc(v.hours)}</option>`).join("")}</select></label>
    <p class="sm-hint" id="soCadWhy">${esc(((d.cadence || {})[s.cadence] || {}).why || "")}</p>

    <div class="ap-setup">
      <label class="ap-toggle"><input type="checkbox" id="apOn"${s.auto_plan !== false ? "checked" : ""} />
        <b>Plan next week automatically</b></label>
      <div class="ap-setup-row">
        <label class="fld"><span>Every</span>
          <select id="apDay">${(d.day_names || ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            .map((n, i) => `<option value="${i}"${Number(s.auto_plan_day ?? 5) === i ? " selected" : ""}>${n}</option>`).join("")}</select></label>
        <label class="fld"><span>At</span>
          <select id="apHour">${Array.from({ length: 24 }, (_, h) =>
            `<option value="${h}"${Number(s.auto_plan_hour ?? 9) === h ? " selected" : ""}>${((h + 11) % 12) + 1}:00 ${h < 12 ? "AM" : "PM"}</option>`).join("")}</select></label>
      </div>
      <p class="sm-hint">It checks festivals and the season, what is already on the calendar
        and which products are selling or stuck, then tops next week up to your number of
        posts, never past it. The posts wait in your Approval panel; nothing goes out
        until you approve it.</p>
      ${loc ? `<label class="fld"><span>Times are local to</span>
        <select id="soCountry">${(loc.options || []).map((o) =>
          `<option value="${esc(o.code)}"${o.code === loc.country ? " selected" : ""}>${esc(o.name)}${o.note ? ` – ${esc(o.note)}` : ""} · ${esc(o.now)} now</option>`).join("")}</select></label>
      <p class="sm-hint" id="soTzWhy">Every posting time and this weekly check run on
        ${esc(loc.label)}${loc.set ? "" : ", the default until you pick your country"}. The server
        itself runs on UTC, so without this a 7:00 pm post goes out at the server's 7:00 pm.</p>` : ""}
    </div>

    <label class="fld"><span>Your city</span><input id="soCity" value="${esc(s.city || "")}" /></label>

    <label class="fld"><span>How people order</span>
      <input id="soCta" value="${esc(s.order_cta || "")}" /></label>
    <p class="sm-hint">In India the sale closes in DMs or on WhatsApp, not at a
      link-in-bio checkout. Every caption ends here.</p>

    <div class="modal-actions">
      <button class="btn ghost" data-mclose4>Cancel</button>
      <button class="btn primary" id="soSave">Save</button>
    </div>`);
  const cad = $("soCad");
  if (cad) cad.onchange = () => {
    const why = ((_socialData.cadence || {})[cad.value] || {}).why || "";
    if ($("soCadWhy")) $("soCadWhy").textContent = why;
  };
  document.querySelector("[data-mclose4]").onclick = closeModal;
  $("soSave").onclick = async () => {
    try {
      await api("/api/social/settings", { method: "POST", json: { patch: {
        category: $("soCat").value, language: $("soLang").value,
        cadence: $("soCad").value, city: $("soCity").value,
        order_cta: $("soCta").value } } });
      await api("/api/social/autoplan/settings", { method: "POST", json: {
        enabled: $("apOn").checked, day: Number($("apDay").value), hour: Number($("apHour").value) } });
      const cSel = $("soCountry");
      if (cSel && (!_locale || cSel.value !== _locale.country)) {
        _locale = await api("/api/settings/locale", { method: "POST", json: { country: cSel.value } });
        toast(`Times now follow ${_locale.label}.`, 6000);
      }
      closeModal(); await openSocial();
    } catch (e) { toast(e.message); }
  };
}

/* =====================================================================
   MODULE: Billing & GST

   The screen leads with the registration warning rather than with the
   settings form, because the most valuable thing this module can tell an
   Indian D2C seller is that Section 24(i) compels GST registration for
   inter-state sale of goods from the first rupee — there is no turnover
   floor. A seller who believes the Rs 40 lakh threshold protects them
   while shipping to the next state is in breach from their first order
   and will not find out until it is expensive.
   ===================================================================== */
let _gstData = null;

async function openGst() {
  await openCached("gst", "Billing & GST",
    async () => {
      const [inv, st] = await Promise.all([api("/api/invoices"), api("/api/gst/settings")]);
      return { invoices: inv.invoices || [], st, fy: inv.fy };
    },
    (d) => { _gstData = d; renderGst(); });
}

function renderGst() {
  const d = _gstData, st = d.st, s = st.settings || {}, doc = st.document || {};
  const w = st.warning;

  const warnHtml = w ? `
    <div class="gst-warn gst-${esc(w.level)}">
      ${sic(w.level === "blocking" ? "alert" : "shield")}
      <div><b>${w.level === "blocking" ? "This needs your attention" : "Where you stand"}</b>
        <span>${esc(w.text)}</span></div>
    </div>` : "";

  const rows = (d.invoices || []).map(i => `
    <tr class="${i.status === "cancelled" ? "gst-cancelled" : ""}">
      <td><b>${esc(i.number)}</b></td>
      <td>${esc(i.date)}</td>
      <td>${esc((i.buyer || {}).name || "")}</td>
      <td>${esc((i.place_of_supply || {}).kind === "inter" ? "IGST" : "CGST+SGST")}
          <span class="muted">${esc((i.buyer || {}).state || "")}</span></td>
      <td class="num">₹${fmt(i.grand_total / 100)}</td>
      <td>${i.status === "cancelled"
            ? `<span class="sm-chip st-fail">Cancelled</span>`
            : `<span class="sm-chip st-pub">Issued</span>`}</td>
      <td class="row-acts">
        <button class="btn ghost xs" data-pdf="${esc(i.id)}">PDF</button>
        ${i.status === "cancelled" ? "" : `<button class="btn ghost xs danger" data-void="${esc(i.id)}">Cancel</button>`}
      </td>
    </tr>`).join("");

  moduleShell("Billing & GST", `
    ${warnHtml}
    <div class="gst-top">
      <div class="card gst-ident">
        <h3>Who you are on an invoice</h3>
        <div class="gst-doc">You currently issue: <b>${esc(doc.title || "Receipt")}</b></div>
        <p class="muted">${esc(doc.why || "")}</p>
        <label class="fld"><span>GSTIN</span>
          <input id="gsGstin" value="${esc(s.gstin || "")}" placeholder="29AAGCB7383J1Z4"
                 maxlength="15" style="text-transform:uppercase" /></label>
        <div id="gsCheck" class="gst-check">${
          st.gstin_check ? (st.gstin_check.ok
            ? `<span class="sm-ok">${sic("check")}Valid: ${esc(st.gstin_check.state)}</span>`
            : `<span class="sm-warn">${sic("alert")}${esc(st.gstin_check.reason)}</span>`) : ""}</div>
        <label class="fld"><span>Legal name</span>
          <input id="gsLegal" value="${esc(s.legal_name || "")}" /></label>
        <label class="fld"><span>Trading name</span>
          <input id="gsTrade" value="${esc(s.trade_name || "")}" /></label>
        <label class="fld"><span>Invoice series</span>
          <input id="gsSeries" value="${esc(s.series || "INV")}" maxlength="3" /></label>
        <p class="sm-hint">Rule 46(b) caps an invoice number at 16 characters and
          requires it to be unique within a financial year. A 3-letter series keeps
          you inside that: ${esc((s.series || "INV").toUpperCase())}/2627/000001.</p>
        <label class="fld chk"><input type="checkbox" id="gsIncl"${s.prices_include_tax !== false ? " checked" : ""} />
          <span>My prices already include GST</span></label>
        <p class="sm-hint">This is the Indian default and, for packaged goods, the law,
          the Legal Metrology rules require MRP to include all taxes. Tax is worked
          backwards out of the price your shopper sees.</p>
        <div class="modal-actions"><button class="btn primary" id="gsSave">Save</button></div>
      </div>

      <div class="card gst-pickup">
        <h3>Pickup and return address</h3>
        <p class="muted">Printed on every shipping label. A parcel that cannot be
          delivered and has no return address is destroyed rather than returned.</p>
        ${["line1", "line2", "city", "state", "pincode"].map(k => `
          <label class="fld"><span>${k === "line1" ? "Address" : k === "line2" ? "Area" : k[0].toUpperCase() + k.slice(1)}</span>
            <input id="gsA_${k}" value="${esc((s.pickup_address || {})[k] || "")}" /></label>`).join("")}
        <div class="modal-actions"><button class="btn primary" id="gsSaveAddr">Save address</button></div>
      </div>
    </div>

    <div class="card">
      <div class="gst-inv-head">
        <h3>Invoices <span class="muted">FY ${esc(d.fy)}</span></h3>
        <button class="btn ghost sm" id="gsGstr1">${sic("receipt")}Export GSTR-1</button>
      </div>
      ${rows ? `<div class="tbl-scroll"><table class="tbl">
        <thead><tr><th>Number</th><th>Date</th><th>Customer</th><th>Tax</th>
          <th class="num">Total</th><th>Status</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div>`
      : `<div class="ap-empty">No invoices yet. Issue one from any order in the Orders module.</div>`}
      <p class="sm-hint">Cancelled invoices stay in this list on purpose. GSTR-1
        Table 13 requires the number range issued and the count cancelled, so
        deleting one would make that table unproducible for the rest of the year.</p>
    </div>

    <details class="sm-fold">
      <summary>What still needs a chartered accountant to confirm</summary>
      <div class="sm-explain">
        <p>These rates were researched against the CBIC notifications, but three
        things could not be verified at source and a confident wrong answer here
        is expensive. Please have your CA check them before you rely on this for filing.</p>
        <ul>${(st.needs_ca_review || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul>
        <h4>Where the rounding convention comes from</h4>
        <pre class="gst-rule">${esc(st.threshold_rule || "")}</pre>
      </div>
    </details>`);

  const gstinBox = $("gsGstin");
  let t = null;
  if (gstinBox) gstinBox.oninput = () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const v = gstinBox.value.trim().toUpperCase();
      if (!v) { $("gsCheck").innerHTML = ""; return; }
      try {
        const r = await api("/api/gst/check?gstin=" + encodeURIComponent(v));
        $("gsCheck").innerHTML = r.ok
          ? `<span class="sm-ok">${sic("check")}Valid: ${esc(r.state)}</span>`
          : `<span class="sm-warn">${sic("alert")}${esc(r.reason)}</span>`;
      } catch (e) { /* typing; not worth a toast */ }
    }, 350);
  };

  $("gsSave").onclick = async () => {
    try {
      await api("/api/gst/settings", { method: "POST", json: { patch: {
        gstin: $("gsGstin").value.trim().toUpperCase(),
        legal_name: $("gsLegal").value.trim(), trade_name: $("gsTrade").value.trim(),
        series: $("gsSeries").value.trim(), prices_include_tax: $("gsIncl").checked } } });
      toast("Saved."); await openGst();
    } catch (e) { toast(e.message); }
  };
  $("gsSaveAddr").onclick = async () => {
    const addr = {};
    ["line1", "line2", "city", "state", "pincode"].forEach(k => addr[k] = $("gsA_" + k).value.trim());
    try {
      await api("/api/gst/settings", { method: "POST", json: { patch: { pickup_address: addr } } });
      toast("Address saved."); await openGst();
    } catch (e) { toast(e.message); }
  };
  $("gsGstr1").onclick = () => download("/api/gstr1.csv?fy=" + encodeURIComponent(_gstData.fy),
                                        `gstr1-${_gstData.fy}.csv`);

  document.querySelectorAll("[data-pdf]").forEach(b => b.onclick = () =>
    download("/api/invoices/" + encodeURIComponent(b.dataset.pdf) + "/pdf", "invoice.pdf"));
  document.querySelectorAll("[data-void]").forEach(b => b.onclick = async () => {
    const why = prompt("Why is this invoice being cancelled?");
    if (why === null) return;
    try {
      await api("/api/invoices/cancel", { method: "POST", json: { invoice_id: b.dataset.void, reason: why } });
      toast("Invoice cancelled. The number stays in the series."); await openGst();
    } catch (e) { toast(e.message); }
  });
}

/* A POST that yields a file. `download` only does GET, and a label request
   carries a list of order ids too long to sit safely in a query string. */
async function postDownload(url, json, filename) {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-Id": state.sessionId,
                 "Authorization": "Bearer " + state.token },
      body: JSON.stringify(json),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || res.statusText);
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  } catch (e) { toast(e.message || "Could not build that file."); }
}

async function resolveCancel(id, decision) {
  const note = decision === "declined"
    ? prompt("What did you agree with them? (optional)") : "";
  if (note === null) return;
  try {
    await api("/api/cancel-requests/resolve", { method: "POST",
      json: { request_id: id, decision, note: note || "" } });
    toast(decision === "approved" ? "Order cancelled." : "Kept: request closed.");
    await openOrders();
  } catch (e) { toast(e.message); }
}

/* Invoice preview before issuing. The preview exists because issuing burns a
   number out of a legally consecutive series — you cannot take it back, only
   cancel it, and a cancelled number still has to be reported. */
async function openInvoiceFor(orderId) {
  let d;
  try { d = await api("/api/invoices/preview?order_id=" + encodeURIComponent(orderId)); }
  catch (e) { return toast(e.message); }

  if (d.existing) {
    openModal(`Invoice ${d.existing.number}`, `
      <p class="muted" style="margin-top:0;">Already issued on ${esc(d.existing.date)}.</p>
      <div class="modal-actions">
        <button class="btn ghost" data-mclose5>Close</button>
        <button class="btn primary" id="ivDl">Download PDF</button>
      </div>`);
    document.querySelector("[data-mclose5]").onclick = closeModal;
    $("ivDl").onclick = () => download("/api/invoices/" + encodeURIComponent(d.existing.id) + "/pdf",
                                       (d.existing.number || "invoice").replace(/\//g, "-") + ".pdf");
    return;
  }

  const p = d.preview, doc = p.document || {}, pos = p.place_of_supply || {};
  const lines = (p.lines || []).map(l => `
    <tr><td>${esc(l.name)}</td><td>${esc(l.hsn || "–")}</td>
        <td class="num">${l.qty}</td><td class="num">${l.rate}%</td>
        <td class="num">₹${fmt(l.taxable / 100)}</td></tr>
    ${l.rate_why ? `<tr class="iv-why"><td colspan="5">${esc(l.rate_why)}</td></tr>` : ""}`).join("");

  openModal("Issue invoice", `
    <div class="iv-doc"><b>${esc(doc.title || "Receipt")}</b>
      <span class="muted">${esc(doc.why || "")}</span></div>
    <div class="iv-pos">Place of supply: <b>${esc((p.buyer || {}).state || "–")}</b>
     , ${esc(pos.kind === "inter" ? "inter-state, IGST" : "intra-state, CGST + SGST")}</div>
    <div class="tbl-scroll"><table class="tbl">
      <thead><tr><th>Item</th><th>HSN</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">Taxable</th></tr></thead>
      <tbody>${lines}</tbody></table></div>
    <div class="iv-tot">
      <div><span>Taxable</span><b>₹${fmt(p.taxable / 100)}</b></div>
      ${pos.kind === "inter"
        ? `<div><span>IGST</span><b>₹${fmt((p.heads || {}).igst / 100)}</b></div>`
        : `<div><span>CGST</span><b>₹${fmt((p.heads || {}).cgst / 100)}</b></div>
           <div><span>SGST</span><b>₹${fmt((p.heads || {}).sgst / 100)}</b></div>`}
      ${p.shipping ? `<div><span>Shipping</span><b>₹${fmt(p.shipping / 100)}</b></div>` : ""}
      <div class="iv-grand"><span>Total</span><b>₹${fmt(p.grand_total / 100)}</b></div>
    </div>
    ${(p.blockers || []).length ? `<div class="iv-block">${sic("alert")}
      <div><b>Fix these first</b><ul>${p.blockers.map(b => `<li>${esc(b)}</li>`).join("")}</ul></div></div>` : ""}
    <p class="sm-hint">Issuing takes the next number in your series. Numbers must run
      consecutively, so a number that is issued and later cancelled still has to be
      reported, that is why this preview exists.</p>
    <div class="modal-actions">
      <button class="btn ghost" data-mclose6>Not yet</button>
      <button class="btn primary" id="ivIssue">Issue ${esc(doc.title || "invoice")}</button>
    </div>`);

  document.querySelector("[data-mclose6]").onclick = closeModal;
  $("ivIssue").onclick = async () => {
    try {
      const r = await api("/api/invoices/issue", { method: "POST",
        json: { order_id: orderId, force: (p.blockers || []).length > 0 } });
      if (r.error === "blocked") return toast("Still blocked: " + (r.blockers || []).join(" "));
      closeModal();
      toast("Issued " + r.number);
      download("/api/invoices/" + encodeURIComponent(r.id) + "/pdf",
               (r.number || "invoice").replace(/\//g, "-") + ".pdf");
    } catch (e) { toast(e.message); }
  };
}

/* =====================================================================
   Manual purchase order.

   The automatic PO only knows about inventory items that have fallen below
   a reorder point, which covers restocking and nothing else — not a first
   order from a new supplier, not a sample run, not fabric for a product
   that does not exist yet. Those are most of the POs a small seller
   actually raises.
   ===================================================================== */
let _poLines = [];

/* A line is an item you already stock, picked from a dropdown. Typing the
   name by hand is still possible (a first order from a new supplier, a sample)
   but it is no longer the default: a typed name cannot be matched when the
   order arrives, so receiving it never puts the stock back. */
function poItemOptions(selectedId, supplierName) {
  const inv = ((_supplyData || {}).inventory || []);
  const mine = supplierName
    ? inv.filter((x) => _norm(x.supplier_name) === _norm(supplierName)) : [];
  const rest = inv.filter((x) => !mine.includes(x));
  const opt = (x) => `<option value="${esc(x.id)}"${x.id === selectedId ? "selected" : ""}>`
    + `${esc(x.name)}${x.unit_label ? ` (${esc(x.unit_label)})` : ""}</option>`;
  return `<option value="">Pick an item</option>`
    + (mine.length ? `<optgroup label="From this supplier">${mine.map(opt).join("")}</optgroup>` : "")
    + (rest.length ? `<optgroup label="${mine.length ? "Everything else" : "Your inventory"}">${rest.map(opt).join("")}</optgroup>` : "")
    + `<option value="__other"${selectedId === "__other" ? "selected" : ""}>Something not in my inventory…</option>`;
}

function _norm(x) { return String(x || "").trim().toLowerCase(); }

function poLineRow(l, i) {
  const typed = l.inventory_id === "__other";
  return `
    <tr data-poi="${i}">
      <td>
        <select class="po-item">${poItemOptions(l.inventory_id || "", (_poSupplierName || ""))}</select>
        ${typed ? `<input class="po-name" value="${esc(l.name || "")}" placeholder="What are you buying?" style="margin-top:5px;" />` : ""}
      </td>
      <td><input class="po-qty" type="number" min="1" value="${esc(String(l.order_qty || 1))}" /></td>
      <td><input class="po-unit" value="${esc(l.unit_label || "unit")}" /></td>
      <td><input class="po-cost" type="number" min="0" step="0.01" value="${l.unit_cost != null ? esc(String(l.unit_cost)) : ""}" placeholder="–" /></td>
      <td class="num po-amt">${l.unit_cost != null ? "₹" + fmt(l.unit_cost * (l.order_qty || 1)) : "–"}</td>
      <td><button class="btn ghost tiny danger" data-podel="${i}" title="Remove this line" aria-label="Remove this line from the order">✕</button></td>
    </tr>`;
}

let _poSupplierName = "";

function paintPoTotal() {
  const box = $("poTotal");
  if (!box) return;
  const total = _poLines.reduce((a, l) =>
    a + (l.unit_cost != null ? Number(l.unit_cost) * Number(l.order_qty || 1) : 0), 0);
  box.innerHTML = _poLines.some((l) => l.unit_cost != null)
    ? `<b>₹${fmt(total)}</b>`
    : `<span class="muted">No rates entered: the PO will show quantities only.</span>`;
}

function renderPoLines() {
  const body = $("poBody");
  if (!body) return;
  body.innerHTML = _poLines.map(poLineRow).join("");
  paintPoTotal();

  body.querySelectorAll("[data-poi]").forEach(tr => {
    const i = Number(tr.dataset.poi);
    // Typing updates the numbers in place. Re-rendering the whole table on
    // every keystroke threw the caret out of the field being typed in — the
    // quantity ended up in whichever box had focus next.
    const sync = () => {
      const nm = tr.querySelector(".po-name");
      if (nm) _poLines[i].name = nm.value;
      _poLines[i].order_qty = Number(tr.querySelector(".po-qty").value || 0);
      _poLines[i].unit_label = tr.querySelector(".po-unit").value;
      const c = tr.querySelector(".po-cost").value;
      _poLines[i].unit_cost = c === "" ? null : Number(c);
      const l = _poLines[i];
      tr.querySelector(".po-amt").textContent =
        l.unit_cost != null ? "₹" + fmt(l.unit_cost * (l.order_qty || 1)) : "–";
      paintPoTotal();
    };
    // Picking an item fills its unit and last known rate, so the usual case is
    // choose-and-type-a-quantity.
    tr.querySelector(".po-item").onchange = (e) => {
      const id = e.target.value;
      const it = ((_supplyData || {}).inventory || []).find((x) => x.id === id);
      const typedQty = Number(_poLines[i].order_qty) > 1;   // the seller set it themselves
      _poLines[i] = { ...(_poLines[i] || {}), inventory_id: id,
        name: it ? it.name : "",
        unit_label: it ? (it.unit_label || "unit") : "unit",
        unit_cost: it && it.unit_cost != null ? it.unit_cost : null,
        // start at what this item is usually ordered in — its DOQ
        order_qty: typedQty ? Number(_poLines[i].order_qty)
          : (it && it.doq ? Math.max(1, Math.round(it.doq)) : 1) };
      renderPoLines();
    };
    tr.querySelectorAll("input").forEach((inp) => { inp.oninput = sync; inp.onchange = sync; });
    tr.querySelector("[data-podel]").onclick = () => { _poLines.splice(i, 1); renderPoLines(); };
  });
}

function openManualPo(suppliers) {
  _poLines = [{ inventory_id: "", name: "", order_qty: 1, unit_label: "unit", unit_cost: null }];
  _poSupplierName = "";
  const opts = (suppliers || []).map(x =>
    `<option value="${esc(x.name)}">${esc(x.name)}</option>`).join("");

  openModal("Create purchase order", `
    <div class="po-form">
      <div class="po-sup">
        <label class="fld"><span>Supplier</span>
          <input id="poSupName" list="poSupList" placeholder="Name" />
          <datalist id="poSupList">${opts}</datalist></label>
        <label class="fld"><span>Phone</span><input id="poSupPhone" placeholder="+91 …" /></label>
        <label class="fld"><span>Email</span><input id="poSupEmail" /></label>
        <label class="fld"><span>Expected by</span><input id="poWhen" type="date" /></label>
      </div>
      <label class="fld"><span>Terms</span>
        <input id="poTerms" placeholder="50% advance, balance on delivery" /></label>

      <div class="section-title">What you are ordering</div>
      <div class="tbl-scroll"><table class="tbl po-tbl">
        <thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Rate ₹</th><th class="num">Amount</th><th></th></tr></thead>
        <tbody id="poBody"></tbody>
      </table></div>
      <div class="po-foot">
        <button class="btn ghost sm" id="poAdd">${sic("plus")}Add another item</button>
        <div id="poTotal"></div>
      </div>
      <label class="fld"><span>Note to the supplier</span>
        <textarea id="poNote" data-ai="po_note" data-ai-ctx="po" data-ai-label="Note to the supplier" rows="2"></textarea></label>
    </div>
    <div class="modal-actions">
      <button class="btn ghost" data-mclose7>Cancel</button>
      <button class="btn ghost" id="poSaveDraft">Save as draft</button>
      <button class="btn primary" id="poSave">${sic("mail")}Create &amp; send</button>
    </div>`, { wide: true });

  renderPoLines();
  $("poAdd").onclick = () => {
    _poLines.push({ name: "", order_qty: 1, unit_label: "unit", unit_cost: null });
    renderPoLines();
  };
  const sup = $("poSupName");
  sup.onchange = () => {
    const hit = (suppliers || []).find(x => x.name === sup.value);
    if (hit) { $("poSupPhone").value = hit.phone || ""; $("poSupEmail").value = hit.email || ""; }
    // the item dropdown puts this supplier's own items at the top
    _poSupplierName = sup.value.trim();
    renderPoLines();
  };
  document.querySelector("[data-mclose7]").onclick = closeModal;
  const create = async (send) => {
    const lines = _poLines.filter(l => (l.name || "").trim() && Number(l.order_qty) > 0);
    if (!lines.length) return toast("Pick an item and a quantity.");
    if (!sup.value.trim()) return toast("Who are you ordering from?");
    if (send && !$("poSupEmail").value.trim())
      return toast("Add the supplier's email to send it, or save it as a draft.", 6000);
    try {
      const r = await withBusy(send ? "Sending the purchase order…" : "Saving the purchase order…",
        send ? "The PO goes to the supplier as a PDF attachment." : "It will wait in your Approval panel.",
        () => api("/api/purchase-orders/manual", { method: "POST", json: {
          supplier: { name: sup.value.trim(), phone: $("poSupPhone").value.trim(),
                      email: $("poSupEmail").value.trim() },
          lines, expected_on: $("poWhen").value, terms: $("poTerms").value.trim(),
          note: $("poNote").value.trim(), send } }));
      closeModal();
      if (r.supply) _supAfter(r.supply);
      const s = r.send || {};
      if (!send) toast(`${r.po_number} saved as a draft, approve it when you are ready.`, 6000);
      else if (s.sent) toast(`${r.po_number} emailed to ${s.to}, PDF attached.`, 7000);
      else { toast(`${r.po_number} created, but not emailed: ${s.reason || "email is not set up."}`, 9000); openPoActions(r); }
    } catch (e) { toast(e.message, 7000); }
  };
  $("poSave").onclick = () => create(true);
  $("poSaveDraft").onclick = () => create(false);
}

/* After creating one, the seller has three things they might want: send it,
   download it, or ask the supplier to cancel it. Offering them together beats
   making them hunt through a list for the PO they just made. */
function openPoActions(po) {
  const phone = ((po.supplier || {}).phone || "").replace(/\D/g, "");
  const text = encodeURIComponent(
    `Purchase order ${po.po_number}\n` +
    (po.lines || []).map(l => `${l.order_qty} ${l.unit_label} ${l.name}`).join("\n") +
    (po.expected_on ? `\nNeeded by ${po.expected_on}` : "") +
    (po.terms ? `\nTerms: ${po.terms}` : ""));
  openModal(po.po_number, `
    <p class="muted" style="margin-top:0;">${fmt(po.n_items)} line${po.n_items === 1 ? "" : "s"},
       ${fmt(po.total_qty)} units${po.total_amount != null ? `, ₹${fmt(po.total_amount)}` : ""}.</p>
    <div class="po-acts">
      ${phone ? `<a class="btn primary" href="https://wa.me/${phone}?text=${text}" target="_blank" rel="noopener">${sic("whatsapp")}Send on WhatsApp</a>` : ""}
      <button class="btn ghost" id="poDl">Download PDF</button>
      <button class="btn ghost" id="poSent">Mark as sent</button>
      <button class="btn ghost danger" id="poCancelReq">Ask to cancel</button>
    </div>
    <div class="modal-actions"><button class="btn ghost" data-mclose8>Close</button></div>`);
  document.querySelector("[data-mclose8]").onclick = closeModal;
  $("poDl").onclick = () => download("/api/supply/po/" + encodeURIComponent(po.po_number) + "/pdf",
                                     po.po_number + ".pdf");
  $("poSent").onclick = async () => {
    try {
      await api("/api/purchase-orders/status", { method: "POST",
        json: { po_number: po.po_number, status: "sent" } });
      toast("Marked as sent."); closeModal();
    } catch (e) { toast(e.message); }
  };
  $("poCancelReq").onclick = async () => {
    const why = prompt("Why are you cancelling this order with them?");
    if (why === null) return;
    try {
      const r = await api("/api/purchase-orders/cancel-request", { method: "POST",
        json: { po_number: po.po_number, reason_code: "other", reason_text: why } });
      closeModal();
      const wa = (r.links || {}).shopper_wa;
      if (wa) window.open(wa, "_blank", "noopener");
      toast("Nothing is cancelled yet, talk to them, then approve it in Orders.");
    } catch (e) { toast(e.message); }
  };
}

/* The next few days of the social plan, on the home screen.

   It sits here rather than only inside the module because a plan the seller has
   to remember to go and look at is a plan that quietly rots. Anything still
   undecided can be approved or skipped without leaving the page — the whole
   point is that deciding costs one tap from where they already are. */
async function renderUpcomingSocial() {
  const box = $("upStrip");
  if (!box) return;
  let d;
  try { d = await api("/api/social/upcoming?days=5"); }
  catch (e) { return; }
  const rows = d.posts || [];
  if (!rows.length) { box.hidden = true; return; }
  box.hidden = false;

  box.innerHTML = `
    <div class="up-h">
      <div>
        <div class="today-eyebrow">Next 5 days</div>
        <h3>${rows.length} post${rows.length === 1 ? "" : "s"} planned${
          d.needs_decision ? ` · <span class="up-need">${d.needs_decision} need${d.needs_decision === 1 ? "s" : ""} you</span>` : ""}</h3>
      </div>
      <button class="btn ghost tiny" id="upOpen">${sic("spark")}Open the plan</button>
    </div>
    <div class="up-rows">
      ${rows.slice(0, 5).map((p) => `
        <div class="up-row" data-id="${esc(p.id)}">
          <div class="up-shot">${p.image_url
            ? `<img src="${esc(p.image_url)}" alt="" />`
            : `<span>${sic("image")}</span>`}</div>
          <div class="up-body">
            <div class="up-when">${esc(shortWhen(p.scheduled_at))}
              ${p.occasion ? `<em class="sm-occ">${esc(p.occasion)}</em>` : ""}
              <span class="up-fmt">${esc(p.format || "")}</span></div>
            <b>${esc(p.product_name || "–")}</b>
            <span class="up-hook">${esc(((p.caption || {}).hook || "").slice(0, 80))}</span>
          </div>
          <div class="up-acts">
            ${p.state === "draft" ? `
              <button class="btn ghost xs" data-upok="${esc(p.id)}">Approve</button>
              <button class="btn ghost xs danger" data-upno="${esc(p.id)}">Cancel</button>`
              : p.state === "approved" ? `<span class="sm-chip st-appr">Needs media</span>`
              : `<span class="sm-chip st-sched">Scheduled</span>`}
          </div>
        </div>`).join("")}
    </div>`;

  $("upOpen").onclick = () => openModule("social");
  const decide = async (id, state_) => {
    try {
      await api("/api/social/state", { method: "POST", json: { post_id: id, state: state_ } });
      renderUpcomingSocial();
    } catch (e) { toast(e.message); }
  };
  // Same paths as the Approval panel: approving makes the post ready.
  box.querySelectorAll("[data-upok]").forEach((b) => b.onclick = () => approvePostReady(b.dataset.upok));
  box.querySelectorAll("[data-upno]").forEach((b) => b.onclick = () => decide(b.dataset.upno, "cancelled"));
}

/* =====================================================================
   Festival campaigns.

   The difference between this and "Plan my week" is the whole point of the
   module. A week is four posts that happen to be in the same seven days.
   A campaign is six posts positioned relative to a date, each with one job
   that no other post in the set has, building toward a day when the seller's
   customers are actually buying.

   The seller does not build campaigns. The Indian calendar hands them ten a
   year with known dates and known demand, so the app builds them and the
   seller says yes.
   ===================================================================== */
let _fests = null;

async function renderCampaignRail() {
  const box = $("smCampaigns");
  if (!box) return;
  try { _fests = await api("/api/social/festivals"); }
  catch (e) { return; }

  const live = _fests.campaigns || [];
  const next = (_fests.festivals || [])
    .filter((f) => !f.undated && f.days_out != null && f.days_out >= 0)
    .slice(0, 4);

  box.innerHTML = `
    ${live.length ? `
      <div class="cmp-live">
        ${live.map((c) => `
          <div class="cmp-run">
            <div class="cmp-run-h">
              <b>${esc(c.festival)} campaign</b>
              <span class="cmp-run-r">
                <span class="muted tiny">${c.published} of ${c.total} posted${
                  c.waiting ? ` · ${c.waiting} waiting on you` : ""}</span>
                <button class="btn ghost tiny" data-revert="${esc(c.key)}"
                  title="Remove this campaign and its unposted drafts. Anything already posted stays.">
                  ${sic("close")}Revert</button>
              </span>
            </div>
            <div class="cmp-bar"><i style="width:${c.total ? (100 * c.published / c.total) : 0}%"></i></div>
            <div class="cmp-obj">${esc(c.objective || "")}</div>
          </div>`).join("")}
      </div>` : ""}

    ${next.length ? `
      <div class="cmp-rail">
        <div class="cmp-rail-h">${sic("spark")}<b>Campaigns worth running</b>
          <span class="muted tiny">picked for what you sell, soonest first</span></div>
        <div class="cmp-cards">
          ${next.map((f) => `
            <button class="cmp-card${f.late ? " is-late" : ""}${f.running ? " is-running" : ""}"
                    data-fest="${esc(f.key)}" data-running="${f.running ? "1" : "0"}">
              <span class="cmp-when">${f.days_out === 0 ? "Today"
                : f.days_out === 1 ? "Tomorrow" : `In ${f.days_out} days`}</span>
              <b>${esc(f.name)}</b>
              <span class="cmp-weight" title="How much this festival matters for what you sell">
                ${"●".repeat(Math.round(f.weight / 2))}<i>${"●".repeat(5 - Math.round(f.weight / 2))}</i></span>
              <span class="cmp-core">${esc((f.core || "").slice(0, 96))}…</span>
              <span class="cmp-go">${f.running ? "Running · view"
                : f.late ? "Plan it now: already late" : "Plan it: one tap"}</span>
            </button>`).join("")}
        </div>
      </div>` : ""}`;

  box.querySelectorAll("[data-fest]").forEach((b) =>
    b.onclick = () => openCampaign(b.dataset.fest, b.dataset.running === "1"));
  box.querySelectorAll("[data-revert]").forEach((b) =>
    b.onclick = () => revertCampaign(b.dataset.revert));
}

/* Undo a planned campaign. Used by the Revert button on a running campaign and
   by the Undo on the toast shown the moment one is planned. Silent when it is
   the toast's own undo, which shows its own "Put back." confirmation. */
async function revertCampaign(key, silent) {
  try {
    const r = await api("/api/social/campaign/revert", { method: "POST", json: { festival: key } });
    _socialData = await api("/api/social");
    if (_currentModule === "social") await renderSocial();
    else await renderCampaignRail();
    if (!silent) toast(r.reverted
      ? `${r.festival} campaign reverted, ${r.reverted} unposted draft${r.reverted === 1 ? "" : "s"} removed.`
      : `Nothing to revert: every ${r.festival} post had already gone out.`);
    return r;
  } catch (e) { if (!silent) toast(e.message, 6000); throw e; }
}

async function openCampaign(key, running) {
  /* One tap plans the whole campaign. The seller no longer has to open a modal
     and confirm — the calendar already knows the date and the beats, so the app
     builds and SAVES the six posts straight away and offers Undo. An already
     running campaign still opens its detail sheet so it can be read or reverted
     rather than silently re-planned. */
  if (!running) return planCampaign(key);

  let p;
  try { p = await api("/api/social/campaign?festival=" + encodeURIComponent(key)); }
  catch (e) { return toast(e.message); }

  if (p.error && p.undated) {
    openModal(p.festival, `
      <p class="muted" style="margin-top:0;">${esc(p.error)}</p>
      <h4>What we would post</h4>
      <ul class="cmp-list">${(p.angles || []).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
      <div class="modal-actions"><button class="btn primary" data-cx>Close</button></div>`);
    document.querySelector("[data-cx]").onclick = closeModal;
    return;
  }
  if (p.error) return toast(p.error);

  openModal(`${esc(p.festival)} campaign`, `
    <div class="cmp-obj-box">
      <div class="cmp-obj-h">The point of this campaign</div>
      <b>${esc(p.objective)}</b>
      <p class="muted tiny" style="margin:6px 0 0;">${esc(p.core)}</p>
    </div>

    <div class="cmp-grammar">${sic("edit")}<div>
      <b>Who your customer is buying for</b>
      <span>${esc(p.grammar)}</span></div></div>

    ${p.late ? `<div class="cmp-late">${sic("alert")}<div>
      <b>You are inside the window already</b>
      <span>${esc(p.festival)} is ${p.days_out} days away and the run-up has
      started. The early beats will be skipped, start now rather than
      waiting.</span></div></div>` : ""}

    <h4>The six posts, and what each one is for</h4>
    <div class="cmp-beats">
      ${(p.beats || []).map((b) => `
        <div class="cmp-beat${b.past ? " is-past" : ""}">
          <div class="cmp-beat-when">
            <b>${esc(b.date.slice(8) + "/" + b.date.slice(5, 7))}</b>
            <span>D-${b.days_before}</span>
          </div>
          <div class="cmp-beat-body">
            <div class="cmp-beat-h"><b>${esc(b.label)}</b>
              <span class="sm-fmt sm-fmt-${esc(b.format)}">${esc(b.format)}</span>
              ${b.past ? `<span class="muted tiny">already passed, will be skipped</span>` : ""}</div>
            <div class="cmp-beat-job">${esc(b.job)}</div>
            <div class="cmp-beat-why">${esc(b.why)}</div>
          </div>
        </div>`).join("")}
    </div>

    <details class="sm-fold" style="margin-top:14px;">
      <summary>What people actually buy, and the lines that work</summary>
      <div class="sm-explain">
        <h4>Angles worth taking</h4>
        <ul class="cmp-list">${(p.angles || []).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
        <h4>Lines in the right register</h4>
        <ul class="cmp-list">${(p.taglines || []).map((t) => `<li><em>${esc(t)}</em></li>`).join("")}</ul>
        <h4>Colours to shoot in</h4>
        <p>${esc((p.colours || []).join(", "))}</p>
        ${p.note ? `<h4>Worth knowing</h4><p>${esc(p.note)}</p>` : ""}
      </div>
    </details>

    <div class="cmp-caution">
      <div class="cmp-caution-h">${sic("shield")}<b>Do not do these</b></div>
      <ul>${(p.caution || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      <p class="muted tiny" style="margin:6px 0 0;">Festival campaigns have been
        pulled by much larger brands over exactly these mistakes. Worth thirty
        seconds of reading.</p>
    </div>

    <div class="cmp-run-note">${sic("check")}<span>This campaign is already planned and
      saved. Its posts are in your plan below, edit any of them, or revert the
      whole campaign to remove every post that has not gone out yet.</span></div>

    <div class="modal-actions">
      <button class="btn ghost" data-cx>Close</button>
      <button class="btn reject" id="cmpRevert">${sic("close")} Revert campaign</button>
    </div>`, { wide: true });

  document.querySelector("[data-cx]").onclick = closeModal;
  $("cmpRevert").onclick = async () => {
    const b = $("cmpRevert");
    b.disabled = true; b.textContent = "Reverting…";
    try { await revertCampaign(key); closeModal(); }
    catch (e) { b.disabled = false; b.innerHTML = `${sic("close")} Revert campaign`; }
  };
}

/* Plan a festival campaign in one tap — no approval gate.
   The calendar already knows the festival's date and its six beats, so there is
   nothing for the seller to decide up front: the app writes the posts, SAVES
   them as drafts against the festival, and refreshes the plan. The only thing it
   asks of the seller is afterwards, and it is optional — an Undo on the toast,
   and a Revert button on the running-campaign card, both of which remove every
   post that has not yet gone out. Nothing is published by this; each post still
   waits in the plan until the seller sends it. */
async function planCampaign(key) {
  let r;
  try {
    r = await withBusy(
      "Building the campaign…",
      "Six beats, each with its own job, written and dated against the festival, saved as you watch.",
      () => api("/api/social/campaign", { method: "POST", json: { festival: key } }));
  } catch (e) { return toast(e.message, 6000); }
  if (r && r.error) return toast(r.error, 6000);

  _socialData = await api("/api/social");
  if (_currentModule === "social") await renderSocial();
  else await renderCampaignRail();

  const n = r.created || 0;
  toastUndo(
    `${r.festival} campaign planned, ${n} post${n === 1 ? "" : "s"} saved as drafts.`,
    () => revertCampaign(key, true),
    8000);
}

/* ---------------------------------------------------------------------
   Warming the modules a seller is about to open.

   The API answers in single-digit milliseconds once it is awake, but the
   FIRST request after the server has been idle pays the whole wake-up
   cost. Whichever screen the seller happened to click first absorbed it —
   which is why Site Builder felt like it took minutes while everything
   else felt fine. It was not Site Builder; it was whatever was clicked
   first.

   So once home is on screen and the seller is reading it, we quietly warm
   the handful of screens a pitch actually walks through. By the time they
   click, the server is awake and its per-account cache is populated.

   Deliberately: after first paint, lowest priority, failures ignored, and
   never on a metered connection.
   --------------------------------------------------------------------- */
const WARM_PATHS = [
  "/api/products/state",    // Product Management
  "/api/store/orders",      // Orders
  "/api/site/state",        // Website Builder — the slow-feeling one
  "/api/supply/state",      // Inventory / Suppliers
];
let _warmed = false;

function warmModules() {
  if (_warmed || !state.token) return;
  // Respect a seller on a metered or slow connection — warming costs them
  // data they did not ask to spend.
  const c = navigator.connection;
  if (c && (c.saveData || /2g/.test(c.effectiveType || ""))) return;
  _warmed = true;

  const run = () => WARM_PATHS.forEach((p, i) =>
    setTimeout(() => { api(p).catch(() => {}); }, i * 250));

  if ("requestIdleCallback" in window) requestIdleCallback(run, { timeout: 3000 });
  else setTimeout(run, 1200);
}

/* Hovering a tile is a strong signal it is about to be opened. On a phone
   there is no hover, so touchstart does the same job a beat earlier than
   the click. */
function warmOnIntent() {
  document.querySelectorAll("[data-mod]").forEach((el) => {
    const path = {
      products: "/api/products/state", orders: "/api/store/orders",
      site: "/api/site/state", supply: "/api/supply/state",
      inventory: "/api/supply/state", social: "/api/social",
      studio: "/api/studio/state", gst: "/api/invoices",
    }[el.dataset.mod];
    if (!path) return;
    let done = false;
    const warm = () => { if (done) return; done = true; api(path).catch(() => {}); };
    el.addEventListener("pointerenter", warm, { once: true, passive: true });
    el.addEventListener("touchstart", warm, { once: true, passive: true });
  });
}

/* ===========================================================================
   HIG CONFORMANCE: dialog behaviour
   Rules: MOD-5 (an obvious way out), MOD-6 (confirm before losing work),
   MOD-8 (one modal at a time), A11Y-9 / A11Y-21 (VoiceOver and keyboard).
   Reference: docs/apple-design-rules.md

   WHAT WAS WRONG
   --------------
   Every popup in this app was a plain <div> that got `hidden = false`. To a
   screen reader that is not a dialog, it is just more page: there is no
   announcement, no boundary, and the rest of the app stays reachable behind
   it. To a keyboard user it is worse. Focus stays wherever it was when the
   popup opened, Tab walks straight out of the popup into the page underneath,
   and when the popup closes focus has been lost entirely, which on a long
   screen means being dumped back at the top of the document.

   Three of the popups (the win-back editor, the add-records grid and the
   content editor) hold typed work. Escape threw it away with no warning in
   two of them and did nothing at all in the rest.

   WHAT THIS DOES
   --------------
   One observer, rather than twenty call sites. The popups are still opened
   the way they always were (`hidden = false`, or display:flex for the chart);
   this watches for that and adds the behaviour around it:

     * remembers what had focus, moves focus into the dialog, and puts it back
       on close, even if the thing that opened it has since been re-rendered,
       in which case focus goes somewhere sensible rather than to <body>
     * marks the app shell inert so Tab, VoiceOver and the pointer all stop at
       the dialog edge
     * wraps Tab at the first and last control inside the dialog
     * Escape closes the popups that had no Escape. The chart modal, the
       history drawer and the runtime-built modals already had their own and
       are left alone, so nothing fires twice.
     * if a field inside the dialog has been edited, Escape asks first. The
       explicit Cancel button is left alone: choosing Cancel IS the intent to
       discard, and asking again would be the "are you sure you are sure" the
       guidelines specifically warn against.
     * opening a second dialog closes the first, rather than stacking two
   ========================================================================= */
(function higDialogs() {
  "use strict";

  /* Popups that use the hidden attribute and had no Escape of their own. */
  const NEEDS_ESC = ["mapModal", "ptModal", "wbModal", "ccModal", "coModal", "addModal"];
  /* Everything that should behave like a dialog, however it is toggled. */
  const HIDDEN_DIALOGS = NEEDS_ESC.concat(["historyDrawer"]);

  const FOCUSABLE = [
    "a[href]", "button:not([disabled])", "input:not([disabled]):not([type=hidden])",
    "select:not([disabled])", "textarea:not([disabled])", "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  let openEl = null;        // the outer element (backdrop or drawer)
  let returnTo = null;      // what had focus before it opened
  let dirtySnapshot = null; // field values at open, for the work-loss guard

  const panelOf = (el) => el.querySelector('[role="dialog"]') || el;

  const isOpen = (el) => {
    if (!el || !el.isConnected) return false;
    if (el.id === "chartModal") return getComputedStyle(el).display !== "none";
    return !el.hidden;
  };

  const fields = (el) =>
    Array.from(el.querySelectorAll("input, textarea, select"))
         .filter((f) => f.type !== "hidden");

  const snapshot = (el) => JSON.stringify(fields(el).map(
    (f) => (f.type === "checkbox" || f.type === "radio" ? f.checked : f.value)));

  const isDirty = (el) => dirtySnapshot !== null && snapshot(el) !== dirtySnapshot;

  const closerFor = (el) =>
    el.querySelector("[data-mclose]") ||
    el.querySelector('[aria-label^="Close"], [aria-label^="close"]') ||
    el.querySelector(".modal-head .btn.ghost");

  function shellParts() {
    return ["appShell", "loginView"].map((id) => document.getElementById(id)).filter(Boolean);
  }

  function lockBackground(on) {
    shellParts().forEach((n) => {
      if (on) { n.setAttribute("inert", ""); n.setAttribute("aria-hidden", "true"); }
      else    { n.removeAttribute("inert"); n.removeAttribute("aria-hidden"); }
    });
  }

  function focusInto(el) {
    const panel = panelOf(el);
    const auto = panel.querySelector("[autofocus]");
    const all = Array.from(panel.querySelectorAll(FOCUSABLE)).filter((n) => n.offsetParent !== null);
    /* The close button is first in the DOM but it is the one thing nobody
       opened the popup in order to press, so it is the last resort here, not
       the first. */
    const preferred = auto
      || all.find((n) => !/close/i.test(n.getAttribute("aria-label") || ""))
      || all[0];
    if (preferred) { preferred.focus(); return; }
    if (!panel.hasAttribute("tabindex")) panel.setAttribute("tabindex", "-1");
    panel.focus();
  }

  function restoreFocus() {
    const t = returnTo;
    returnTo = null;
    if (t && t !== document.body && t.isConnected && typeof t.focus === "function") { t.focus(); return; }
    /* Whatever opened the dialog has been re-rendered. Land inside the view
       rather than at the top of the document. */
    const main = document.getElementById("view");
    if (main) {
      if (!main.hasAttribute("tabindex")) main.setAttribute("tabindex", "-1");
      main.focus();
    }
  }

  function handleOpen(el) {
    if (openEl === el) return;
    if (openEl && isOpen(openEl)) {
      const c = closerFor(openEl);           // MOD-8: never two at once
      if (c) c.click();
    }
    returnTo = document.activeElement;
    openEl = el;
    dirtySnapshot = snapshot(el);
    lockBackground(true);
    /* rAF, because the popup's contents are usually written in the same tick
       that unhides it, and focusing before that finds an empty box. */
    requestAnimationFrame(() => { if (openEl === el) focusInto(el); });
  }

  function handleClose(el) {
    if (openEl !== el) return;
    openEl = null;
    dirtySnapshot = null;
    lockBackground(false);
    restoreFocus();
  }

  function watch(el) {
    if (!el) return;
    const sync = () => (isOpen(el) ? handleOpen(el) : handleClose(el));
    new MutationObserver(sync).observe(el, {
      attributes: true, attributeFilter: ["hidden", "style", "class"],
    });
    sync();
  }

  HIDDEN_DIALOGS.forEach((id) => watch(document.getElementById(id)));
  watch(document.getElementById("chartModal"));

  /* Modals built at runtime are appended to <body> and removed again. */
  new MutationObserver((muts) => {
    muts.forEach((m) => {
      m.addedNodes.forEach((n) => {
        if (n.nodeType === 1 && n.classList && n.classList.contains("modal-back") && !n.id) handleOpen(n);
      });
      m.removedNodes.forEach((n) => {
        if (n.nodeType === 1 && n === openEl) handleClose(n);
      });
    });
  }).observe(document.body, { childList: true });

  /* Tab stays inside the open dialog (A11Y-21). */
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Tab" || !openEl || !isOpen(openEl)) return;
    const panel = panelOf(openEl);
    const all = Array.from(panel.querySelectorAll(FOCUSABLE)).filter((n) => n.offsetParent !== null);
    if (!all.length) return;
    const first = all[0], last = all[all.length - 1];
    if (e.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  });

  /* Escape for the popups that had none, with the work-loss guard (MOD-6). */
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !openEl || !openEl.id || NEEDS_ESC.indexOf(openEl.id) < 0) return;
    if (isDirty(openEl) &&
        !window.confirm("Close this and lose what you have typed here?")) return;
    const c = closerFor(openEl);
    if (c) { e.preventDefault(); c.click(); }
  });
})();


/* ---------- tab bar (phone) ----------
   Three places a seller goes from any screen: Home, the approvals waiting on
   them, and their Account. The tab bar is hidden by CSS above 900px, where the
   approval panel is a column beside the workspace and Account is in the top bar. */
(function wireTabbar() {
  const bar = $("tabbar"); if (!bar) return;
  const mark = (name) => bar.querySelectorAll("button").forEach((b) =>
    name === b.dataset.tab ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
  bar.addEventListener("click", (e) => {
    const b = e.target.closest("[data-tab]"); if (!b) return;
    const tab = b.dataset.tab;
    if (tab === "home") { mark("home"); window.scrollTo({ top: 0, behavior: "smooth" }); goHome(); }
    else if (tab === "account") { openAccount(); }
    else if (tab === "approvals") {
      mark("approvals");
      const panel = $("approvalPanel");
      _apShut = false; panel.classList.remove("shut");
      const head = $("apHead"); if (head) head.setAttribute("aria-expanded", "true");
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
  // Any move to a module or back home resets the highlighted tab.
  window.addEventListener("hashchange", () => mark("home"));
})();

/* ---------- pointer-tracking glow on app tiles ----------
   Writes the cursor position into --mx/--my on whichever tile is under the
   pointer, which the ::before radial gradient in ios.css reads. Delegated and
   attached once, so it keeps working across every Home re-render. Passive, and
   it only touches a style property, so it never blocks a scroll. Skipped
   entirely when the visitor has asked for reduced motion. */
(function tileGlow() {
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  let raf = 0, tile = null, x = 0, y = 0;
  document.addEventListener("pointermove", (e) => {
    const t = e.target.closest && e.target.closest(".app-tile");
    if (!t) return;
    tile = t; x = e.clientX; y = e.clientY;
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      if (!tile) return;
      const r = tile.getBoundingClientRect();
      tile.style.setProperty("--mx", ((x - r.left) / r.width * 100).toFixed(1) + "%");
      tile.style.setProperty("--my", ((y - r.top) / r.height * 100).toFixed(1) + "%");
    });
  }, { passive: true });
})();
