/* =========================================================================
   Storefront runtime.

   One file, no framework. It reads the seller's resolved theme from
   /api/shop/<handle>/site, writes it to CSS custom properties, and renders a
   themed shop: home, catalogue, product detail, cart drawer, checkout, and the
   shopper's own order history.

   Buying requires a shopper account on THIS store — the seller's rule,
   enforced server-side too. The cart lives in this browser only; every price
   and total is recalculated by the server before an order is accepted.

   The page doubles as the builder's live canvas. Loaded with ?edit=1 it
   outlines every editable region, and clicking one posts a message to the
   parent window so the inspector can jump straight to those controls. The
   parent posts patched site data back and the page re-renders in place, with
   no network round-trip and no reload.
   ========================================================================= */

const HANDLE = decodeURIComponent(location.pathname.split("/s/")[1] || "").replace(/\/.*$/, "");
const LS_CART = "cs_cart_" + HANDLE;
const LS_TOKEN = "cs_tok_" + HANDLE;
const QS = new URLSearchParams(location.search);
// The builder's live preview loads this page with ?preview=<seller token> so an
// unpublished site renders for its owner and nobody else. ?edit=1 turns the
// same page into the builder's canvas.
const PREVIEW = QS.get("preview") || "";
const EDIT = QS.get("edit") === "1" && !!PREVIEW;

const S = {
  data: null, style: null, site: null, products: [], icons: {},
  token: null, customer: null,
  cart: {}, route: { name: "home" }, filter: "", query: "", selected: "",
};

/* ---------------------------------------------------------------- helpers */
const el = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const initials = (s) => (s || "S").trim().replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase() || "S";

/** Inline SVG from the shared icon set. Stroke-based, inherits colour. */
function ic(name, cls) {
  const path = S.icons[name] || S.icons.check || "";
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"${cls ? ` class="${cls}"` : ""}>${path}</svg>`;
}

function store(key, val) {
  try {
    if (val === undefined) { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; }
    if (val === null) localStorage.removeItem(key); else localStorage.setItem(key, JSON.stringify(val));
  } catch (e) { /* private mode — the cart simply won't persist */ }
  return null;
}

function toast(msg, icon = "check", ms = 2600) {
  const t = el("toast");
  t.innerHTML = ic(icon) + `<span>${esc(msg)}</span>`;
  t.classList.add("on");
  clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("on"), ms);
}

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.json) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  if (S.token) headers["X-Store-Token"] = S.token;
  if (PREVIEW) headers["X-Preview-Token"] = PREVIEW;
  const r = await fetch(`/api/shop/${encodeURIComponent(HANDLE)}${path}`, { ...opts, headers });
  const text = await r.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { detail: text }; }
  if (!r.ok) throw new Error(data.detail || data.message || `Request failed (${r.status})`);
  return data;
}

/* ------------------------------------------------------------------ theme */
function applyTheme(style, site) {
  const root = document.documentElement;
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const mode = style.mode === "auto" ? (prefersDark ? "dark" : "light") : style.mode;
  const pal = mode === "dark" ? style.dark : style.light;
  const L = style.layout || {};

  root.setAttribute("data-mode", mode);
  root.setAttribute("data-theme-id", style.theme);
  root.setAttribute("data-hero", L.hero || "split");
  root.setAttribute("data-grid", L.grid || "cards");
  root.setAttribute("data-cta", L.cta || "solid");
  root.setAttribute("data-density", L.density || "normal");
  root.setAttribute("data-width", style.width || "wide");

  const set = (k, v) => root.style.setProperty(k, v);
  set("--bg", pal.bg); set("--surface", pal.surface); set("--ink", pal.ink);
  set("--muted", pal.muted); set("--border", pal.border);
  set("--accent", pal.accent); set("--accent-ink", pal.accent_ink);
  set("--radius", (L.radius == null ? 10 : L.radius) + "px");
  set("--track", (L.track || 0) / 100 + "em");
  set("--case", L.case === "upper" ? "uppercase" : "none");
  set("--grain", L.grain || 0);
  set("--fh", style.heading_font.stack);
  set("--fb", style.body_font.stack);
  set("--fa", (style.accent_font || style.body_font).stack);
  const ty = style.type || {};
  if (ty.heading_weight) set("--hw", ty.heading_weight);
  if (ty.heading_track != null) set("--track", ty.heading_track / 100 + "em");
  set("--hs", (ty.heading_scale || 100) / 100);
  set("--bs", (ty.body_scale || 100) / 100);

  ["reveal", "parallax", "hscroll", "pin", "marquee", "zoom", "split", "mask", "shine", "drift"]
    .forEach((m) => root.classList.toggle("m-" + m, (style.motion || []).includes(m)));
  root.classList.toggle("editing", EDIT);

  loadFonts(style.google_fonts || []);
  document.title = (site.brand || "Store") + (site.tagline ? " — " + site.tagline : "");
}

const _fontsLoaded = new Set();
function loadFonts(list) {
  const want = list.filter((f) => !_fontsLoaded.has(f));
  if (!want.length) return;
  want.forEach((f) => _fontsLoaded.add(f));
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `https://fonts.googleapis.com/css2?${list.map((f) => "family=" + f).join("&")}&display=swap`;
  document.head.appendChild(link);
}

/* ------------------------------------------------------------------- cart */
/* A shirt is not one thing to count, it is twelve. So a cart key is the
   product AND the cell of its size x colour matrix: "prod123|var456". A
   product with no variants keeps an empty second half, which also means carts
   saved before variants existed still load. */
const KEY_SEP = "|";
const cartKey = (pid, vid) => pid + KEY_SEP + (vid || "");
const splitKey = (k) => {
  const i = String(k).indexOf(KEY_SEP);
  return i < 0 ? { pid: k, vid: "" } : { pid: k.slice(0, i), vid: k.slice(i + 1) };
};
const cartLines = () => Object.entries(S.cart).map(([k, qty]) => {
  const { pid, vid } = splitKey(k);
  return vid ? { product_id: pid, variant_id: vid, qty } : { product_id: pid, qty };
});
const cartCount = () => Object.values(S.cart).reduce((a, b) => a + b, 0);
function saveCart() { store(LS_CART, S.cart); paintCartCount(); }
function paintCartCount() {
  const n = cartCount(), b = el("cartN");
  if (b) { b.textContent = n; b.hidden = n === 0; }
}

/* Resolve a cart key back to what it is: the product, the chosen cell, the
   price that applies, and the label a human reads. */
function lineInfo(key) {
  const { pid, vid } = splitKey(key);
  const p = S.products.find((x) => x.id === pid);
  if (!p) return null;
  const v = vid ? (p.variants || []).find((x) => x.id === vid) : null;
  if (vid && !v) return null;
  return {
    key, product: p, variant: v,
    id: pid, variantId: vid,
    name: p.name,
    label: v ? v.label : "",
    display: v ? `${p.name} — ${v.label}` : p.name,
    price: v ? v.price : p.price,
    image_url: (v && v.image_url) || p.image_url || (p.images || [])[0] || "",
    available: v ? v.available : p.available,
    in_stock: v ? v.in_stock : p.in_stock,
  };
}

function addToCart(id, qty = 1, variantId = "") {
  const p = S.products.find((x) => x.id === id);
  if (!p) return;
  if ((p.variants || []).length && !variantId) {
    // never guess a size on the shopper's behalf
    go("product", { id });
    toast("Pick a size and colour first.", "package");
    return;
  }
  const info = lineInfo(cartKey(id, variantId));
  if (!info) return;
  if (!info.in_stock) { toast("That one is out of stock right now.", "close"); return; }
  const k = info.key;
  const next = (S.cart[k] || 0) + qty;
  if (info.available != null && next > info.available) {
    S.cart[k] = info.available;
    toast(`Only ${info.available} left — cart updated.`, "package");
  } else {
    S.cart[k] = next;
    toast(`${info.display} added to your bag`, "bag");
  }
  saveCart();
}
function setQty(key, qty) {
  if (qty <= 0) delete S.cart[key]; else S.cart[key] = qty;
  saveCart();
}

/* ------------------------------------------------------------------ motion */
let _io = null;
function observeReveals(scope = document) {
  const root = document.documentElement;
  if (!root.classList.contains("m-reveal") && !root.classList.contains("m-mask")
      && !root.classList.contains("m-split") && !root.classList.contains("m-zoom")) return;
  if (!_io) {
    _io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); _io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.06 });
  }
  scope.querySelectorAll(".rv:not(.in), .zm:not(.in), .mk:not(.in), .sw:not(.in)").forEach((n) => _io.observe(n));
}

/** Wrap each word in a mask so headlines can rise into place. */
function splitWords(text) {
  return String(text || "").split(/\s+/).filter(Boolean)
    .map((w) => `<span class="sw"><i>${esc(w)}</i></span>`).join(" ");
}

let _pxNodes = [];
function bindParallax() { _pxNodes = Array.from(document.querySelectorAll("[data-px]")); onScroll(); }
function onScroll() {
  const hdr = el("hdr");
  if (hdr) hdr.classList.toggle("stuck", window.scrollY > 12);
  if (S.spine) {
    const h = document.documentElement.scrollHeight - innerHeight;
    S.spine.style.height = (h > 0 ? (window.scrollY / h) * 100 : 0) + "%";
  }
  scrubManifesto();
  if (!document.documentElement.classList.contains("m-parallax")) return;
  for (const n of _pxNodes) {
    const r = n.getBoundingClientRect();
    if (r.bottom < -240 || r.top > innerHeight + 240) continue;
    const speed = parseFloat(n.dataset.px) || 0.14;
    const mid = r.top + r.height / 2 - innerHeight / 2;
    n.style.transform = `translate3d(0, ${(-mid * speed).toFixed(1)}px, 0)`;
  }
}
addEventListener("scroll", () => requestAnimationFrame(onScroll), { passive: true });
addEventListener("resize", () => requestAnimationFrame(onScroll));

function bindRails(scope = document) {
  scope.querySelectorAll(".rail").forEach((rail) => {
    if (rail._bound) return; rail._bound = true;
    let down = false, x0 = 0, l0 = 0, moved = 0;
    rail.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "touch") return;
      down = true; moved = 0; x0 = e.clientX; l0 = rail.scrollLeft; rail.classList.add("drag");
    });
    rail.addEventListener("pointermove", (e) => {
      if (!down) return;
      const dx = e.clientX - x0; moved = Math.abs(dx); rail.scrollLeft = l0 - dx;
    });
    const up = () => { down = false; rail.classList.remove("drag"); setTimeout(() => (rail._moved = moved), 0); };
    rail.addEventListener("pointerup", up);
    rail.addEventListener("pointerleave", up);
    rail.addEventListener("click", (e) => {
      if (rail._moved > 6) { e.stopPropagation(); e.preventDefault(); rail._moved = 0; }
    }, true);
    rail.addEventListener("wheel", (e) => {
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      if (rail.scrollWidth <= rail.clientWidth) return;
      const atStart = rail.scrollLeft <= 0 && e.deltaY < 0;
      const atEnd = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 1 && e.deltaY > 0;
      if (atStart || atEnd) return;
      e.preventDefault(); rail.scrollLeft += e.deltaY;
    }, { passive: false });
  });
  scope.querySelectorAll("[data-rail-nav]").forEach((btn) => {
    if (btn._bound) return; btn._bound = true;
    btn.onclick = () => {
      const rail = document.querySelector(`[data-rail="${btn.dataset.railNav}"]`);
      if (!rail) return;
      rail.scrollBy({ left: rail.clientWidth * 0.82 * (btn.dataset.dir === "next" ? 1 : -1), behavior: "smooth" });
    };
  });
}

function afterRender() {
  paintCartCount();
  observeReveals();
  bindParallax();
  bindRails();
  bindCountUps();
  bindBars();
  bindCardVideo();
  bindMagnets();
  numberSections();
  _manWords = Array.from(document.querySelectorAll(".manifesto .w"));
  scrubManifesto();
  if (EDIT) bindEditRegions();
}

/* Figures that count themselves up the first time they are seen. Any prefix or
   suffix the seller typed ("₹", "+", "k", "%") is preserved — only the digits
   animate. */
function bindCountUps() {
  const nodes = document.querySelectorAll("[data-count]:not([data-counted])");
  if (!nodes.length) return;
  if (prefersReduced()) { nodes.forEach((n) => n.setAttribute("data-counted", "1")); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const n = e.target; io.unobserve(n); n.setAttribute("data-counted", "1");
      const raw = n.dataset.count || "";
      const m = raw.match(/([^\d]*)([\d][\d,.]*)(.*)/);
      if (!m) return;
      const [, pre, digits, post] = m;
      const target = parseFloat(digits.replace(/,/g, ""));
      if (!isFinite(target)) return;
      const dec = (digits.split(".")[1] || "").length;
      const t0 = performance.now(), dur = 1500;
      (function step(t) {
        const k = Math.min(1, (t - t0) / dur);
        const v = target * (1 - Math.pow(1 - k, 4));
        n.textContent = pre + v.toLocaleString("en-IN", {
          minimumFractionDigits: dec, maximumFractionDigits: dec }) + post;
        if (k < 1) requestAnimationFrame(step); else n.textContent = raw;
      })(t0);
    });
  }, { threshold: 0.4 });
  nodes.forEach((n) => io.observe(n));
}

/* Progress bars fill once, when they scroll into view. */
function bindBars() {
  const bars = document.querySelectorAll("[data-bar]:not([data-filled])");
  if (!bars.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      io.unobserve(e.target); e.target.setAttribute("data-filled", "1");
      requestAnimationFrame(() => { e.target.style.width = e.target.dataset.bar + "%"; });
    });
  }, { threshold: 0.5 });
  bars.forEach((b) => io.observe(b));
}

/* Cards with a clip play it on hover and rewind on the way out — nothing
   downloads until the shopper shows interest. */
function bindCardVideo() {
  if (prefersReduced()) return;
  document.querySelectorAll(".card.has-vid").forEach((card) => {
    if (card._vid) return; card._vid = true;
    const v = card.querySelector(".card-vid");
    if (!v) return;
    card.addEventListener("pointerenter", () => {
      if (!v.src || v.readyState === 0) v.load();
      const play = v.play(); if (play && play.catch) play.catch(() => {});
    });
    card.addEventListener("pointerleave", () => { v.pause(); v.currentTime = 0; });
  });
}

/* Buttons lean very slightly towards the cursor. Pointer-fine only. */
function bindMagnets() {
  if (prefersReduced() || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  document.querySelectorAll(".b, .rail-nav button").forEach((n) => {
    if (n._mag) return; n._mag = true; n.classList.add("mag");
    n.addEventListener("pointermove", (e) => {
      const r = n.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / r.width;
      const dy = (e.clientY - (r.top + r.height / 2)) / r.height;
      n.style.transform = `translate(${(dx * 7).toFixed(1)}px, ${(dy * 5).toFixed(1)}px)`;
    });
    n.addEventListener("pointerleave", () => { n.style.transform = ""; });
  });
}

/* The statement brightens word by word, tied to scroll position rather than a
   timer, so it reads at whatever pace the visitor scrolls. */
let _manWords = [];
function scrubManifesto() {
  if (!_manWords.length) return;
  const host = _manWords[0].parentElement;
  const r = host.getBoundingClientRect();
  const span = r.height + innerHeight * 0.65;
  const p = Math.max(0, Math.min(1, (innerHeight * 0.82 - r.top) / span));
  const lit = Math.round(p * _manWords.length * 1.35);
  _manWords.forEach((w, i) => w.classList.toggle("lit", i < lit));
}

/* ----------------------------------------------------------------- routing */
function go(name, params = {}) {
  S.route = { name, ...params };
  const q = name === "home" ? "" : `#${name}${params.id ? "/" + params.id : ""}`;
  history.pushState(S.route, "", location.pathname + location.search + q);
  render();
  window.scrollTo({ top: 0 });
}
addEventListener("popstate", () => { readHash(); render(); });
function readHash() {
  const h = (location.hash || "").replace(/^#/, "");
  if (!h) { S.route = { name: "home" }; return; }
  const [name, id] = h.split("/");
  S.route = { name, id };
}

/* ------------------------------------------------------------------ chrome */
/** Mark a block as editable. In shopper mode this returns nothing at all. */
function ed(key, label) {
  return EDIT ? ` data-edit="${key}" data-edit-label="${esc(label)}"` : "";
}

function header() {
  const s = S.site;
  const logo = s.logo_url
    ? `<img src="${esc(s.logo_url)}" alt="${esc(s.brand)}" />`
    : `<span class="mark">${esc(initials(s.brand))}</span>`;
  const nav = [["home", "Home"], ["shop", "Shop"]];
  if ((s.sections || {}).story && (s.story || {}).body) nav.push(["#story", "Our story"]);
  nav.push(["orders", "Orders"]);
  return `
  ${s.announcement ? `<div class="announce"${ed("announcement", "Announcement bar")}>${esc(s.announcement)}</div>` : ""}
  <header class="hdr" id="hdr">
    <div class="wrap hdr-in">
      <a class="brand" href="#" data-go="home"${ed("brand", "Brand & logo")}>${logo}<span>${esc(s.brand || "Store")}</span></a>
      <nav class="nav">
        ${nav.map(([k, l]) => k.startsWith("#")
          ? `<a href="${k}">${l}</a>`
          : `<a href="#" data-go="${k}" class="${S.route.name === k ? "on" : ""}">${l}</a>`).join("")}
      </nav>
      <div class="search">${ic("search")}<input id="q" placeholder="Search" value="${esc(S.query)}" /></div>
      <div class="hdr-r">
        <button class="icon-b" id="accBtn" aria-label="${S.customer ? "Your account" : "Log in"}">${ic(S.customer ? "user" : "lock")}</button>
        <button class="icon-b" id="cartBtn" aria-label="Your bag">${ic("bag")}<span class="cart-n" id="cartN" hidden>0</span></button>
        <button class="icon-b burger" id="burger" aria-label="Menu">${ic("menu")}</button>
      </div>
    </div>
  </header>`;
}

function footer() {
  const s = S.site, c = s.contact || {}, p = s.policies || {};
  const social = [
    c.instagram ? `<a href="https://instagram.com/${esc(String(c.instagram).replace(/^@/, ""))}" target="_blank" rel="noopener" aria-label="Instagram">${ic("instagram")}</a>` : "",
    c.whatsapp ? `<a href="https://wa.me/${esc(String(c.whatsapp).replace(/\D/g, ""))}" target="_blank" rel="noopener" aria-label="WhatsApp">${ic("whatsapp")}</a>` : "",
    c.email ? `<a href="mailto:${esc(c.email)}" aria-label="Email">${ic("mail")}</a>` : "",
    c.phone ? `<a href="tel:${esc(c.phone)}" aria-label="Phone">${ic("phone")}</a>` : "",
  ].join("");
  const pol = [
    p.shipping ? `<li><a href="#" data-policy="shipping" class="ul">Shipping</a></li>` : "",
    p.returns ? `<li><a href="#" data-policy="returns" class="ul">Returns</a></li>` : "",
    p.privacy ? `<li><a href="#" data-policy="privacy" class="ul">Privacy</a></li>` : "",
  ].join("");
  return `
  <footer class="ftr"${ed("footer", "Footer & contact")}><div class="wrap">
    <div class="ftr-word">${esc(s.brand || "Store")}</div>
    <div class="ftr-grid">
      <div>
        <p class="muted" style="max-width:34ch;margin:0">${esc(s.tagline || "")}</p>
        ${c.address ? `<p class="muted tiny" style="margin-top:14px">${esc(c.address)}</p>` : ""}
        ${social ? `<div class="ftr-social">${social}</div>` : ""}
      </div>
      <div><h4>Shop</h4><ul>
        <li><a href="#" data-go="shop" class="ul">All products</a></li>
        ${(S.data.categories || []).slice(0, 4).map((c2) => `<li><a href="#" data-cat="${esc(c2.name)}" class="ul">${esc(c2.name)}</a></li>`).join("")}
      </ul></div>
      <div><h4>Account</h4><ul>
        <li><a href="#" data-go="orders" class="ul">My orders</a></li>
        <li><a href="#" data-go="shop" class="ul">Track an order</a></li>
      </ul></div>
      <div><h4>Help</h4><ul>
        ${pol || `<li class="muted">—</li>`}
        ${c.email ? `<li><a href="mailto:${esc(c.email)}" class="ul">${esc(c.email)}</a></li>` : ""}
      </ul></div>
    </div>
    <div class="ftr-bot">
      <span>© ${new Date().getFullYear()} ${esc(s.brand || "Store")}</span>
      <span>Powered by One Tap Manager</span>
    </div>
  </div></footer>`;
}

/* ------------------------------------------------------------- components */
/* With per-variant price overrides a product has a range, not a price. Showing
   the lowest with "from" is the honest shorthand. */
function priceLabel(p) {
  const vs = (p.variants || []).filter((v) => v.price != null);
  if (!vs.length) return p.price != null ? money(p.price) : "—";
  const lo = Math.min(...vs.map((v) => v.price));
  const hi = Math.max(...vs.map((v) => v.price));
  return lo === hi ? money(lo) : `from ${money(lo)}`;
}

function productCard(p, i = 0) {
  const off = p.mrp && p.price && p.mrp > p.price ? Math.round((1 - p.price / p.mrp) * 100) : 0;
  const img = p.image_url || (p.images || [])[0] || "";
  return `
  <article class="card rv zm d${(i % 4) + 1} ${p.in_stock ? "" : "sold"} ${p.video_url ? "has-vid" : ""}" data-p="${esc(p.id)}">
    <div class="card-img" style="${img ? `background-image:url('${esc(img)}')` : ""}">
      ${img ? "" : `<div class="ph">${ic("image")}</div>`}
      ${p.video_url ? `<video class="card-vid" muted loop playsinline preload="none" src="${esc(p.video_url)}"></video>` : ""}
      ${p.in_stock ? "" : `<span class="tag-out">Sold out</span>`}
      ${p.in_stock ? ((p.variants || []).length
        ? `<button class="card-quick" data-open="${esc(p.id)}">${ic("arrow-right")}<span>Choose options</span></button>`
        : `<button class="card-quick" data-add="${esc(p.id)}">${ic("bag")}<span>Add to bag</span></button>`) : ""}
    </div>
    <div class="card-body">
      ${p.category ? `<div class="card-cat">${esc(p.category)}</div>` : ""}
      <div class="card-name">${esc(p.name)}</div>
      ${p.description ? `<div class="card-desc">${esc(p.description)}</div>` : ""}
      <div class="price-row">
        <span class="price">${priceLabel(p)}</span>
        ${off ? `<span class="mrp">${money(p.mrp)}</span><span class="off">−${off}%</span>` : ""}
      </div>
      ${(p.options || []).length ? `<div class="card-opts">${p.options.map((ax) =>
        `${esc(ax.name)}: ${ax.values.slice(0, 4).map(esc).join(", ")}${ax.values.length > 4 ? "…" : ""}`
      ).join(" · ")}</div>` : ""}
    </div>
  </article>`;
}

function secHead(idx, eyebrow, title, action) {
  return `<div class="sec-head rv">
      <div><div class="eyebrow">${esc(eyebrow)}</div><h2>${esc(title)}</h2></div>
      <div class="sec-idx"${action ? "" : " data-autonum"}>${action || ""}</div>
    </div>`;
}

/* Sections are numbered by where they land on the page, not the order the
   template happened to build them in. */
function numberSections() {
  let n = 0;
  document.querySelectorAll("[data-autonum]").forEach((el2) => {
    el2.textContent = String(++n).padStart(2, "0");
  });
}

function railSection(id, idx, eyebrow, title, cardsHtml, count, editKey, editLabel) {
  const nav = count > 3 ? `<div class="rail-nav">
      <button data-rail-nav="${id}" data-dir="prev" aria-label="Previous">${ic("arrow-left")}</button>
      <button data-rail-nav="${id}" data-dir="next" aria-label="Next">${ic("arrow-right")}</button>
    </div>` : `<span class="sec-idx" data-autonum></span>`;
  return `
  <section class="sec"${editKey ? ed(editKey, editLabel) : ""}><div class="wrap">
    <div class="sec-head rv">
      <div><div class="eyebrow">${esc(eyebrow)}</div><h2>${esc(title)}</h2></div>
      ${nav}
    </div>
    <div class="rail-wrap"><div class="rail" data-rail="${id}">${cardsHtml}</div></div>
  </div></section>`;
}

/* ------------------------------------------------------------------ views */
function viewHome() {
  const s = S.site, sec = s.sections || {}, hero = s.hero || {};
  const featured = S.products.slice(0, 10);
  const heroImg = hero.image_url || "";
  const heroVid = hero.video_url || "";
  const full = S.style.layout.hero === "full";
  const onImage = (!!heroImg || !!heroVid) && full;
  let n = 0;
  const idx = () => String(++n).padStart(2, "0");

  const headline = hero.heading || s.brand || "Welcome";
  const heroHtml = `
  <section class="hero ${onImage ? "on-image" : ""}" data-align="${esc(hero.align || "left")}"${ed("hero", "Hero section")}>
    ${onImage ? `
      ${heroVid
        ? `<video class="hero-vid" data-px="0.10" autoplay muted loop playsinline ${heroImg ? `poster="${esc(heroImg)}"` : ""} src="${esc(heroVid)}"></video>`
        : `<div class="hero-img" data-px="0.12" style="background-image:url('${esc(heroImg)}')"></div>`}
      <div class="hero-veil" style="background:linear-gradient(102deg, rgba(0,0,0,${(hero.overlay || 45) / 100}) 8%, rgba(0,0,0,${Math.max(0, (hero.overlay || 45) - 26) / 100}) 82%)"></div>` : ""}
    <div class="wrap hero-in">
      <div class="hero-copy rv in">
        ${s.tagline ? `<div class="eyebrow">${esc(s.tagline)}</div>` : ""}
        <h1 style="margin-top:20px">${splitWords(headline)}</h1>
        <p class="lead">${esc(hero.sub || "Everything we make, in one place.")}</p>
        <div class="hero-cta">
          <button class="b p" data-go="shop">${esc(hero.cta_text || "Shop now")}${ic("arrow-right")}</button>
          ${sec.story && (s.story || {}).body ? `<a class="b g" href="#story">Our story</a>` : ""}
        </div>
      </div>
      ${full ? "" : `<div class="hero-art rv mk d2">${heroVid
        ? `<video autoplay muted loop playsinline style="width:100%;height:100%;object-fit:cover" ${heroImg ? `poster="${esc(heroImg)}"` : ""} src="${esc(heroVid)}"></video>`
        : `<div style="${heroImg ? `background-image:url('${esc(heroImg)}')` : "background:var(--surface)"}"></div>`}</div>`}
    </div>
    ${full ? `<div class="scroll-cue"><span>Scroll</span><i></i></div>` : ""}
  </section>`;

  const marquee = document.documentElement.classList.contains("m-marquee") ? (() => {
    const words = [s.brand, s.commerce.free_shipping_above ? "Free shipping over " + money(s.commerce.free_shipping_above) : "Free shipping",
      "Secure checkout", s.tagline, "Made with care"].filter(Boolean);
    const strip = `<span>${words.map(esc).join("</span><span>")}</span>`;
    return `<div class="marquee"><div class="marquee-t">${strip}${strip}</div></div>`;
  })() : "";

  const highlights = sec.highlights && (s.highlights || []).length ? `
    <section class="sec" style="padding-block:calc(var(--sec) * .62)"${ed("highlights", "Promise strip")}><div class="wrap">
      <div class="hl-grid">${s.highlights.map((h, i) => `
        <div class="hl rv d${(i % 4) + 1}"><div class="i">${ic(h.icon || "check")}</div>
          <b>${esc(h.title)}</b><p>${esc(h.text)}</p></div>`).join("")}</div>
    </div></section>` : "";

  const C = s.copy || {};
  const cats = sec.categories && (S.data.categories || []).length ? railSection(
    "cats", idx(), C.cat_eyebrow || "Browse", C.cat_title || "Shop by category",
    S.data.categories.map((c, i) => `
      <button class="cat-chip rv d${(i % 4) + 1}" data-cat="${esc(c.name)}">
        <div class="cimg" style="${c.image ? `background-image:url('${esc(c.image)}')` : "background:var(--surface)"}"></div>
        <div class="cveil"></div>
        <div class="ctext"><b>${esc(c.name)}</b><span>${c.count} item${c.count === 1 ? "" : "s"}</span></div>
      </button>`).join(""), S.data.categories.length, "categories", "Category rail") : "";

  const feat = sec.featured && featured.length ? railSection(
    "feat", idx(), C.feat_eyebrow || "Handpicked", C.feat_title || "Featured",
    featured.map(productCard).join(""), featured.length, "featured", "Featured rail") : "";

  // ---- spotlight: one product, sticky media, copy scrolling past it ----
  const hero_p = S.products[0];
  const spot = sec.spotlight && hero_p ? (() => {
    const img = hero_p.image_url || (hero_p.images || [])[0] || "";
    const off = hero_p.mrp && hero_p.price && hero_p.mrp > hero_p.price
      ? Math.round((1 - hero_p.price / hero_p.mrp) * 100) : 0;
    return `
    <section class="sec"${ed("spotlight", "Spotlight product")}><div class="wrap">
      <div class="spot">
        <div class="spot-media rv mk zm" style="position:sticky">
          ${hero_p.video_url
            ? `<video autoplay muted loop playsinline ${img ? `poster="${esc(img)}"` : ""} src="${esc(hero_p.video_url)}"></video>`
            : img ? `<img src="${esc(img)}" alt="${esc(hero_p.name)}" />`
                  : `<div class="ph" style="height:100%;display:grid;place-items:center;color:var(--muted);opacity:.3">${ic("image")}</div>`}
          <span class="spot-plate">${esc(hero_p.category || "Signature")}</span>
        </div>
        <div class="spot-copy rv d2">
          <div class="eyebrow">Signature</div>
          <h2>${esc(hero_p.name)}</h2>
          ${hero_p.description ? `<p class="lead">${esc(hero_p.description)}</p>` : ""}
          ${(hero_p.highlights || []).length
            ? `<ul class="pd-hl">${hero_p.highlights.map((h) => `<li>${ic("check")}${esc(h)}</li>`).join("")}</ul>` : ""}
          <div class="spot-buy">
            <span class="price">${hero_p.price != null ? money(hero_p.price) : "—"}</span>
            ${off ? `<span class="mrp">${money(hero_p.mrp)}</span><span class="off">−${off}%</span>` : ""}
            <span class="spot-stock">${hero_p.in_stock
              ? (hero_p.available != null ? `${hero_p.available} left` : "In stock") : "Sold out"}</span>
          </div>
          <div class="hero-cta" style="margin-top:26px">
            <button class="b p" data-p2="${esc(hero_p.id)}">View the piece${ic("arrow-right")}</button>
            ${hero_p.in_stock ? `<button class="b g" data-add="${esc(hero_p.id)}">Add to bag</button>` : ""}
          </div>
        </div>
      </div>
    </div></section>`;
  })() : "";

  // ---- stats: figures that count up ----
  const statRows = (s.stats || []).filter((x) => x.value && x.label);
  const stats = sec.stats && statRows.length ? `
    <section class="sec"${ed("stats", "Numbers")}><div class="wrap">
      <div class="eyebrow rv" style="margin-bottom:34px">${esc(C.stats_eyebrow || "By the numbers")}</div>
      <div class="stats">${statRows.map((x, i) => `
        <div class="stat rv d${(i % 4) + 1}"><b data-count="${esc(x.value)}">${esc(x.value)}</b><span>${esc(x.label)}</span></div>`).join("")}</div>
    </div></section>` : "";

  // ---- drop: real scarcity from the catalogue ----
  const sc = S.data.scarce;
  const drop = sec.drop && sc ? (() => {
    const claimed = Math.max(0, sc.of - sc.left);
    const pct = Math.round((claimed / Math.max(sc.of, 1)) * 100);
    return `
    <section class="sec"${ed("drop", "Scarcity block")}><div class="wrap drop-wrap">
      <div class="eyebrow rv" style="margin-inline:auto">${esc(C.drop_eyebrow || "Limited")}</div>
      <h2 class="rv" style="margin-top:18px;max-width:16ch;margin-inline:auto">${esc(C.drop_title || "When it's gone, it's gone")}</h2>
      <div class="drop-card rv d2">
        <div class="drop-head"><span>${esc(sc.name)}</span><span><b>${claimed}</b> claimed</span></div>
        <div class="drop-bar"><i data-bar="${pct}"></i></div>
        <div class="drop-foot"><b>${sc.left}</b> ${sc.left === 1 ? "piece" : "pieces"} remaining</div>
      </div>
    </div></section>`;
  })() : "";

  const all = `
    <section class="sec"${ed("products", "Product grid")}><div class="wrap">
      ${secHead(idx(), C.all_eyebrow || "Catalogue", C.all_title || "All products",
        `<button class="b g sm" data-go="shop">View all${ic("arrow-right")}</button>`)}
      <div class="grid">${S.products.slice(0, 8).map(productCard).join("")}</div>
    </div></section>`;

  const story = sec.story && (s.story || {}).body ? `
    <section class="sec" id="story"${ed("story", "Our story")}><div class="wrap">
      <div class="story">
        <div class="story-art rv mk"><div data-px="0.09" style="${s.story.image_url ? `background-image:url('${esc(s.story.image_url)}')` : "background:var(--surface)"}"></div></div>
        <div class="story-body rv d2">
          <div class="eyebrow">${esc(C.story_eyebrow || "About us")}</div>
          <h2 style="margin-top:16px">${esc(s.story.title || "Our story")}</h2>
          <p>${esc(s.story.body)}</p>
        </div>
      </div>
    </div></section>` : "";

  // ---- lookbook ----
  const look = sec.gallery && (s.gallery || []).length ? `
    <section class="sec"${ed("gallery", "Lookbook")}><div class="wrap">
      ${secHead(idx(), C.gallery_eyebrow || "Lookbook", C.gallery_title || "In the wild")}
      <div class="look">${s.gallery.map((g) => `
        <figure class="rv"><div class="lk">${/\.(mp4|webm|mov|m4v)$/i.test(g.url)
          ? `<video muted loop playsinline autoplay src="${esc(g.url)}"></video>`
          : `<img src="${esc(g.url)}" alt="${esc(g.caption || "")}" loading="lazy" />`}</div>
          ${g.caption ? `<figcaption>${esc(g.caption)}</figcaption>` : ""}</figure>`).join("")}</div>
    </div></section>` : "";

  // ---- manifesto: brightens word by word on scroll ----
  const man = sec.manifesto && s.manifesto ? `
    <section class="sec manifesto"${ed("manifesto", "Statement")}><div class="wrap">
      <p id="manifesto">${s.manifesto.split(/\s+/).filter(Boolean)
        .map((w) => `<span class="w">${esc(w)}</span>`).join(" ")}</p>
    </div></section>` : "";

  const tst = sec.testimonials && (s.testimonials || []).length ? `
    <section class="sec"${ed("testimonials", "Customer reviews")}><div class="wrap">
      ${secHead(idx(), C.rev_eyebrow || "Reviews", C.rev_title || "What buyers say")}
      <div class="t-grid">${s.testimonials.map((t, i) => `
        <div class="t-card rv d${(i % 4) + 1}">
          <div class="stars">${Array.from({ length: t.rating || 5 }, () => ic("star")).join("")}</div>
          <p>“${esc(t.text)}”</p><b>${esc(t.name || "Verified buyer")}</b>
        </div>`).join("")}</div>
    </div></section>` : "";

  const news = sec.newsletter ? `
    <section class="sec"${ed("newsletter", "Newsletter")}><div class="wrap"><div class="news rv">
      <h2>${esc(C.news_title || "Stay in the loop")}</h2>
      <p>${esc(C.news_sub || "New drops and offers. No spam, ever.")}</p>
      <form id="newsForm"><input type="email" placeholder="you@email.com" required /><button class="b">${esc(C.news_cta || "Join")}${ic("arrow-right")}</button></form>
    </div></div></section>` : "";

  return header() + heroHtml + marquee + highlights + spot + cats + feat + stats + all
       + look + story + man + drop + tst + news + footer();
}

function viewShop() {
  const q = S.query.trim().toLowerCase();
  let list = S.products;
  if (S.filter) list = list.filter((p) => p.category === S.filter);
  if (q) list = list.filter((p) => (p.name + " " + p.category + " " + p.description).toLowerCase().includes(q));
  const names = (S.data.categories || []).map((c) => c.name);
  const chips = ["", ...names].map((c) =>
    `<button class="chip ${S.filter === c ? "on" : ""}" data-cat="${esc(c)}">${c ? esc(c) : "All"}</button>`).join("");
  return header() + `
    <div class="wrap" style="padding-top:52px">
      <div class="eyebrow">${list.length} product${list.length === 1 ? "" : "s"}</div>
      <h1 style="font-size:clamp(30px,5vw,60px);margin:18px 0 34px">${S.filter ? esc(S.filter) : esc((S.site.copy || {}).shop_title || "Everything we sell")}</h1>
      <div class="filters">${chips}</div>
      ${list.length ? `<div class="grid">${list.map(productCard).join("")}</div>`
        : `<div class="empty"><div class="i">${ic("search")}</div><h3>Nothing matches that</h3><p>Try another category or search term.</p></div>`}
      <div style="height:90px"></div>
    </div>` + footer();
}

/* Which cell of the matrix is selected on the product page, per product.
   Held here rather than in the DOM so re-rendering never loses the choice. */
S.chosen = S.chosen || {};

function axisValues(p, axisName) {
  const ax = (p.options || []).find((a) => a.name === axisName);
  return ax ? ax.values : [];
}

/* The cell matching the current selection — null until every axis is chosen. */
function chosenVariant(p) {
  const pick = S.chosen[p.id] || {};
  if (!(p.options || []).length) return null;
  if ((p.options || []).some((ax) => !pick[ax.name])) return null;
  return (p.variants || []).find((v) =>
    (p.options || []).every((ax) => v.options[ax.name] === pick[ax.name])) || null;
}

/* Would choosing `value` on `axis` leave anything in stock? Greying out the
   combinations that cannot be bought is the difference between a size picker
   and a guessing game. */
function valueBuyable(p, axisName, value) {
  const pick = { ...(S.chosen[p.id] || {}), [axisName]: value };
  return (p.variants || []).some((v) =>
    v.in_stock && Object.entries(pick).every(([k, val]) => v.options[k] === val));
}

function variantPicker(p) {
  if (!(p.options || []).length) return "";
  const pick = S.chosen[p.id] || {};
  return `<div class="opts">` + p.options.map((ax) => `
    <div class="opt-ax">
      <div class="opt-h"><span>${esc(ax.name)}</span>${
        pick[ax.name] ? `<b>${esc(pick[ax.name])}</b>` : `<i class="muted">Choose</i>`}</div>
      <div class="opt-vals">
        ${ax.values.map((val) => {
          const on = pick[ax.name] === val;
          const buyable = valueBuyable(p, ax.name, val);
          return `<button class="opt-v${on ? " on" : ""}${buyable ? "" : " gone"}"
            data-ax="${esc(ax.name)}" data-val="${esc(val)}" data-pid="${esc(p.id)}"
            ${buyable ? "" : 'aria-disabled="true"'}
            title="${buyable ? esc(val) : esc(val) + " — sold out"}">${esc(val)}</button>`;
        }).join("")}
      </div>
    </div>`).join("") + `</div>`;
}

function viewProduct(id) {
  const p = S.products.find((x) => x.id === id);
  if (!p) return header() + `<div class="wrap"><div class="empty"><div class="i">${ic("package")}</div>
      <h3>No longer listed</h3><p>That product isn't available any more.</p>
      <button class="b g" data-go="shop">Back to shop${ic("arrow-right")}</button></div></div>` + footer();
  const chosen = chosenVariant(p);
  const needsChoice = (p.options || []).length && !chosen;
  const imgs = [(chosen && chosen.image_url) || p.image_url, ...(p.images || [])].filter(Boolean);
  const shownPrice = chosen ? chosen.price : p.price;
  const shownMrp = chosen && chosen.mrp != null ? chosen.mrp : p.mrp;
  const off = shownMrp && shownPrice && shownMrp > shownPrice
    ? Math.round((1 - shownPrice / shownMrp) * 100) : 0;
  const avail = chosen ? chosen.available : p.available;
  const stockOn = chosen ? chosen.in_stock : p.in_stock;
  const buyable = p.in_stock && !needsChoice && stockOn;
  const buyLabel = needsChoice
    ? `Choose ${(p.options || []).map((a) => a.name.toLowerCase()).join(" & ")}`
    : (stockOn ? "Add to bag" : "Sold out");
  const stockLine = needsChoice
    ? "Pick your options to see what's in stock."
    : (stockOn
        ? (avail != null && avail <= 5 ? `Only ${avail} left` : "In stock, ready to ship")
        : "Currently unavailable");
  const related = S.products.filter((x) => x.id !== p.id && (!p.category || x.category === p.category)).slice(0, 8);
  const c = S.site.commerce || {}, pol = S.site.policies || {};
  const acc = [
    p.description ? ["Description", p.description] : null,
    pol.shipping ? ["Shipping", pol.shipping] : null,
    pol.returns ? ["Returns", pol.returns] : null,
  ].filter(Boolean);
  return header() + `
    <div class="wrap">
      <nav class="crumbs"><a href="#" data-go="home" class="ul">Home</a>${ic("arrow-right")}<a href="#" data-go="shop" class="ul">Shop</a>${p.category ? `${ic("arrow-right")}<span>${esc(p.category)}</span>` : ""}</nav>
      <div class="pd">
        <div class="pd-gal">
          <div class="pd-main zm rv in" id="pdMain" style="${imgs[0] ? `background-image:url('${esc(imgs[0])}')` : ""}">
            ${imgs.length ? "" : `<div class="ph" style="height:100%;display:grid;place-items:center;color:var(--muted);opacity:.35">${ic("image")}</div>`}
          </div>
          ${imgs.length > 1 ? `<div class="pd-thumbs">${imgs.map((u, i) =>
            `<button class="${i === 0 ? "on" : ""}" data-img="${esc(u)}" style="background-image:url('${esc(u)}')" aria-label="View image ${i + 1}"></button>`).join("")}</div>` : ""}
        </div>
        <div class="pd-info rv d2 in" id="pdInfo">
          ${p.category ? `<div class="eyebrow">${esc(p.category)}</div>` : ""}
          <h1 style="margin-top:16px">${esc(p.name)}</h1>
          <div class="price-row" style="margin:0 0 8px">
            <span class="price">${chosen ? money(chosen.price) : priceLabel(p)}</span>
            ${off ? `<span class="mrp">${money(shownMrp)}</span><span class="off">−${off}%</span>` : ""}
          </div>
          <div class="tiny muted">${c.gst_percent ? (c.gst_inclusive ? `Inclusive of ${c.gst_percent}% GST` : `+ ${c.gst_percent}% GST at checkout`) : "No tax added"}${p.unit_label ? ` · per ${esc(p.unit_label)}` : ""}</div>
          ${(p.highlights || []).length ? `<ul class="pd-hl">${p.highlights.map((h) => `<li>${ic("check")}${esc(h)}</li>`).join("")}</ul>` : ""}
          ${variantPicker(p)}
          <div class="pd-buy">
            <div class="qty"><button id="qMinus" aria-label="Fewer">${ic("minus")}</button><span id="qVal">1</span><button id="qPlus" aria-label="More">${ic("plus")}</button></div>
            <button class="b p" id="pdAdd" ${buyable ? "" : "disabled"}>${buyLabel}${buyable ? ic("bag") : ""}</button>
            <button class="b g" id="pdBuy" ${buyable ? "" : "disabled"}>Buy now${ic("arrow-right")}</button>
          </div>
          <div class="pd-stock ${stockOn ? "" : "out"}"><i></i>${stockLine}</div>
          <div class="acc">
            ${acc.map(([t, b], i) => `
              <div class="acc-item ${i === 0 ? "open" : ""}">
                <button class="acc-h">${esc(t)}${ic("plus")}</button>
                <div class="acc-b"><p>${esc(b)}</p></div>
              </div>`).join("")}
            <div class="acc-item">
              <button class="acc-h">Delivery${ic("plus")}</button>
              <div class="acc-b"><p>${c.free_shipping_above ? `Free delivery on orders over ${money(c.free_shipping_above)}, otherwise ${money(c.shipping_fee || 0)}.` : `Delivery ${money(c.shipping_fee || 0)}.`}${c.cod_enabled ? "\nCash on delivery available." : ""}\nNo account needed — you can check out as a guest.</p></div>
            </div>
          </div>
        </div>
      </div>
      ${related.length ? railSection("rel", "", "More like this", "You may also like", related.map(productCard).join(""), related.length) : ""}
    </div>` + footer();
}

/* Repaint only the product's info column after a variant choice. Falls back to
   a full render if the panel is not on screen (nothing to patch). */
function repaintProductInfo(pid) {
  const host = el("pdInfo");
  const p = S.products.find((x) => x.id === pid);
  if (!host || !p) { render(); return; }
  const fresh = document.createElement("div");
  fresh.innerHTML = viewProduct(pid);
  const next = fresh.querySelector("#pdInfo");
  if (!next) { render(); return; }
  host.innerHTML = next.innerHTML;

  // swapping the gallery's main image is the only thing outside the panel that
  // a variant can change
  const chosen = chosenVariant(p);
  const main = el("pdMain");
  if (main) {
    const img = (chosen && chosen.image_url) || p.image_url || (p.images || [])[0] || "";
    if (img) main.style.backgroundImage = `url('${img}')`;
  }
  bindProductPanel(p);
}

/* Handlers that live inside the info panel — shared by the full render and the
   targeted repaint so the two can never drift apart. */
function bindProductPanel(p) {
  document.querySelectorAll("[data-ax]").forEach((n) => n.onclick = () => {
    const pid = n.dataset.pid;
    S.chosen[pid] = { ...(S.chosen[pid] || {}) };
    if (S.chosen[pid][n.dataset.ax] === n.dataset.val) delete S.chosen[pid][n.dataset.ax];
    else S.chosen[pid][n.dataset.ax] = n.dataset.val;
    repaintProductInfo(pid);
  });
  const qv = el("qVal");
  if (!qv) return;
  const v = chosenVariant(p);
  const avail = v ? v.available : p.available;
  const cap = avail == null ? 99 : Math.max(1, avail);
  const vid = v ? v.id : "";
  el("qMinus").onclick = () => { qv.textContent = Math.max(1, +qv.textContent - 1); };
  el("qPlus").onclick = () => { qv.textContent = Math.min(cap, +qv.textContent + 1); };
  el("pdAdd").onclick = () => addToCart(p.id, +qv.textContent, vid);
  el("pdBuy").onclick = () => { addToCart(p.id, +qv.textContent, vid); startCheckout(); };
  document.querySelectorAll(".acc-h").forEach((h) =>
    h.onclick = () => h.parentElement.classList.toggle("open"));
}

function viewOrders() {
  if (!S.customer) {
    return header() + `<div class="wrap"><div class="empty">
      <div class="i">${ic("lock")}</div><h3>Sign in to see your orders</h3>
      <p>Your order history lives with your ${esc(S.site.brand)} account.</p>
      <button class="b p" id="loginCta">Log in or sign up${ic("arrow-right")}</button>
    </div></div>` + footer();
  }
  const orders = S.myOrders || [];
  const flow = ["new", "confirmed", "packed", "shipped", "delivered"];
  return header() + `
    <div class="wrap" style="padding-top:52px">
      <div class="eyebrow">Account</div>
      <h1 style="font-size:clamp(28px,4.4vw,52px);margin:18px 0 8px">Your orders</h1>
      <p class="muted" style="margin-bottom:36px">${esc((S.customer || {}).email || "your account")} · <a href="#" id="logoutLink" class="ul">log out</a></p>
      ${orders.length ? orders.map((o) => {
        const i = flow.indexOf(o.status);
        return `<div class="ord">
          <div class="ord-h">
            <div><b>${esc(o.order_no)}</b><div class="tiny muted">${esc(String(o.created_at).replace("T", " ").slice(0, 16))}</div></div>
            <div style="display:flex;gap:12px;align-items:center">
              <span class="pill ${esc(o.status)}">${esc(o.status)}</span><b>${money(o.total)}</b>
            </div>
          </div>
          <div class="tiny muted">${(o.items || []).map((it) => `${esc(it.name)} × ${it.qty}`).join(" · ")}</div>
          ${o.status === "cancelled" ? "" : `<div class="steps">${flow.map((_, k) => `<i class="${k <= i ? "on" : ""}"></i>`).join("")}</div>`}
        </div>`;
      }).join("") : `<div class="empty"><div class="i">${ic("package")}</div><h3>No orders yet</h3><p>When you order, it'll show up here.</p><button class="b p" data-go="shop">Start shopping${ic("arrow-right")}</button></div>`}
      <div style="height:90px"></div>
    </div>` + footer();
}

function viewCheckout() {
  const priced = S.priced;
  if (!priced || !priced.items.length) {
    return header() + `<div class="wrap"><div class="empty"><div class="i">${ic("bag")}</div>
      <h3>Your bag is empty</h3><p>Add something you like and come back.</p>
      <button class="b p" data-go="shop">Shop products${ic("arrow-right")}</button></div></div>` + footer();
  }
  // A guest has no customer record yet — that is the whole point of guest
  // checkout — so every read below goes through this, never through
  // S.customer directly. Dereferencing it was what broke the page.
  const cust = S.customer || {};
  const a = cust.address || {};
  const c = S.site.commerce || {};
  const guest = !S.customer;
  return header() + `
    <div class="wrap"><div class="co">
      <div>
        <div class="eyebrow">Checkout</div>
        <h1 style="font-size:clamp(26px,3.6vw,44px);margin:16px 0 6px">Almost yours</h1>
        ${guest
          ? `<p class="muted" style="margin:0 0 10px">No account needed. We'll create one from your phone number so you can track this order.</p>
             <p class="tiny muted" style="margin:0 0 34px">Already have an account? <a href="#" id="coLogin" class="ul">Log in</a> to use your saved address.</p>`
          : `<p class="muted" style="margin:0 0 34px">Signed in as ${esc(cust.email || "")}</p>`}

        <div class="co-box">
          <h3>Delivery address</h3>
          <div class="two">
            <label class="field"><span>Full name</span><input id="coName" value="${esc(cust.name || "")}" placeholder="Your name" /></label>
            <label class="field"><span>Phone</span><input id="coPhone" value="${esc(cust.phone || "")}" placeholder="10-digit mobile" inputmode="numeric" /></label>
          </div>
          ${guest ? `<label class="field"><span>Email <span class="muted">(optional — for the receipt)</span></span><input id="coEmail" type="email" value="" placeholder="you@email.com" /></label>` : ""}
          <label class="field"><span>Address</span><input id="coL1" value="${esc(a.line1 || "")}" placeholder="Flat / house, street" /></label>
          <label class="field"><span>Area <span class="muted">(optional)</span></span><input id="coL2" value="${esc(a.line2 || "")}" /></label>
          <div class="two">
            <label class="field"><span>City</span><input id="coCity" value="${esc(a.city || "")}" /></label>
            <label class="field"><span>State</span><input id="coState" value="${esc(a.state || "")}" /></label>
          </div>
          <div class="two">
            <label class="field"><span>PIN code</span><input id="coPin" value="${esc(a.pincode || "")}" inputmode="numeric" maxlength="6" /></label>
            <label class="field"><span>Landmark <span class="muted">(optional)</span></span><input id="coLm" value="${esc(a.landmark || "")}" /></label>
          </div>
        </div>

        <div class="co-box">
          <h3>Payment</h3>
          ${c.cod_enabled ? `<label class="pay-opt on" data-pay="cod"><input type="radio" name="pay" value="cod" checked />
            <div><b>Cash on delivery</b><div class="tiny muted">Pay the courier when your order arrives.</div></div></label>` : ""}
          <label class="pay-opt ${c.cod_enabled ? "" : "on"}" data-pay="prepaid"><input type="radio" name="pay" value="prepaid" ${c.cod_enabled ? "" : "checked"} />
            <div><b>Pay online</b><div class="tiny muted">We'll send a payment link to confirm this order.</div></div></label>
          <label class="field" style="margin-top:18px"><span>Order note <span class="muted">(optional)</span></span><textarea id="coNote" rows="2" placeholder="Anything we should know?"></textarea></label>
        </div>
      </div>

      <div class="co-side">
        <h3 style="font-size:13px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:20px">Order summary</h3>
        ${priced.items.map((i) => `<div class="ci" style="grid-template-columns:56px 1fr auto;padding:14px 0">
          <div class="ci-img" style="width:56px;height:64px;${i.image_url ? `background-image:url('${esc(i.image_url)}')` : ""}"></div>
          <div><b>${esc(i.display_name || i.name)}</b><div class="tiny muted">Qty ${i.qty}</div></div>
          <b>${money(i.line_total)}</b></div>`).join("")}
        <div class="sum" style="margin-top:22px">
          <div><span>Subtotal</span><span>${money(priced.subtotal)}</span></div>
          <div><span>Shipping</span><span>${priced.shipping ? money(priced.shipping) : "Free"}</span></div>
          ${priced.gst_percent ? `<div><span>GST (${priced.gst_percent}%)${priced.gst_inclusive ? " incl." : ""}</span><span>${money(priced.tax)}</span></div>` : ""}
          <div class="tot"><span>Total</span><span>${money(priced.total)}</span></div>
        </div>
        <button class="b p blk" id="placeBtn">Place order${ic("arrow-right")}</button>
        <div class="err" id="coErr" hidden></div>
        ${c.order_note ? `<p class="tiny muted" style="margin:16px 0 0">${esc(c.order_note)}</p>` : ""}
        ${trustBlock()}
      </div>
    </div></div>` + footer();
}

/* Who you are actually paying. A shopper handing money to a brand they have
   never heard of needs this more than they would on a marketplace, not less —
   and every line here is something the seller filled in, never invented. */
function trustBlock() {
  const t = S.site.trust || {};
  if (t.show === false) return "";
  const pol = S.site.policies || {};
  const rows = [];
  if (t.returns_days) rows.push([ic("refresh"), `${t.returns_days}-day returns`,
    pol.returns ? "See our returns policy" : "Unworn, with tags"]);
  if (t.dispatch_days != null) rows.push([ic("truck"),
    t.dispatch_days <= 1 ? "Dispatched next day" : `Dispatched in ${t.dispatch_days} working days`,
    "You'll get a message at every step"]);
  if (t.support_phone || t.support_email) rows.push([ic(t.support_phone ? "phone" : "mail"),
    "A real person answers", t.support_phone || t.support_email]);
  if (!rows.length && !t.business_name) return "";
  const legal = [t.business_name, t.address, t.gstin ? `GSTIN ${t.gstin}` : ""]
    .filter(Boolean).map(esc).join(" · ");
  return `
    <div class="trust">
      ${rows.map(([icon, title, sub]) => `
        <div class="trust-r"><span class="trust-i">${icon}</span>
          <div><b>${esc(title)}</b><span>${esc(sub)}</span></div></div>`).join("")}
      ${legal ? `<p class="trust-legal">${legal}</p>` : ""}
      ${(pol.shipping || pol.returns || pol.privacy) ? `<p class="trust-legal">
        ${pol.shipping ? `<a href="#" data-policy="shipping" class="ul">Shipping</a>` : ""}
        ${pol.returns ? `<a href="#" data-policy="returns" class="ul">Returns</a>` : ""}
        ${pol.privacy ? `<a href="#" data-policy="privacy" class="ul">Privacy</a>` : ""}
      </p>` : ""}
    </div>`;
}

function viewDone(order) {
  const flow = ["new", "confirmed", "packed", "shipped", "delivered"];
  return header() + `
    <div class="wrap"><div class="empty" style="padding-top:90px">
      <div class="i" style="color:var(--accent);opacity:1">${ic("check")}</div>
      <h1 style="font-size:clamp(26px,4vw,48px);margin-bottom:14px">Order placed</h1>
      <p>Thank you, ${esc(order.customer_name || "friend")}. Order <b>${esc(order.order_no)}</b> is confirmed for ${money(order.total)}.</p>
      <div class="ord" style="text-align:left;max-width:520px;margin:30px auto 0">
        <div class="ord-h"><b>${esc(order.order_no)}</b><span class="pill new">new</span></div>
        <div class="tiny muted">${(order.items || []).map((i) => `${esc(i.display_name || i.name)} × ${i.qty}`).join(" · ")}</div>
        <div class="steps">${flow.map((_, i) => `<i class="${i === 0 ? "on" : ""}"></i>`).join("")}</div>
      </div>
      <div style="display:flex;gap:12px;justify-content:center;margin-top:30px;flex-wrap:wrap">
        <button class="b p" data-go="orders">Track my orders${ic("arrow-right")}</button>
        <button class="b g" data-go="shop">Keep shopping</button>
      </div>
    </div></div>` + footer();
}

/* --------------------------------------------------------------- overlays */
function closeLayer() { el("layer").innerHTML = ""; }

function openCart() {
  const items = Object.entries(S.cart).map(([k, qty]) => {
    const info = lineInfo(k);
    return info ? { ...info, qty } : null;
  }).filter(Boolean);
  const subtotal = items.reduce((a, i) => a + (i.price || 0) * i.qty, 0);
  const c = S.site.commerce || {};
  const ship = items.length && c.shipping_fee && (!c.free_shipping_above || subtotal < c.free_shipping_above) ? c.shipping_fee : 0;
  const away = c.free_shipping_above && subtotal < c.free_shipping_above ? c.free_shipping_above - subtotal : 0;
  const pct = c.free_shipping_above ? Math.min(100, (subtotal / c.free_shipping_above) * 100) : 100;

  el("layer").innerHTML = `
    <div class="scrim" id="cScrim"></div>
    <aside class="drawer" id="cDrawer">
      <div class="drawer-h"><h3>Your bag${items.length ? ` (${cartCount()})` : ""}</h3>
        <button class="icon-b" id="cClose" aria-label="Close">${ic("close")}</button></div>
      <div class="drawer-b">
        ${items.length ? items.map((i) => `
          <div class="ci">
            <div class="ci-img" style="${i.image_url ? `background-image:url('${esc(i.image_url)}')` : ""}"></div>
            <div>
              <b>${esc(i.name)}</b>
              ${i.label ? `<div class="ci-var">${esc(i.label)}</div>` : ""}
              <div class="tiny muted">${money(i.price)} each</div>
              <div class="qty"><button data-dec="${esc(i.key)}" aria-label="Fewer">${ic("minus")}</button><span>${i.qty}</span><button data-inc="${esc(i.key)}" aria-label="More">${ic("plus")}</button></div>
            </div>
            <div style="text-align:right"><b>${money((i.price || 0) * i.qty)}</b>
              <div style="margin-top:10px;display:flex;justify-content:flex-end"><button class="ci-x" data-rm="${esc(i.key)}" aria-label="Remove">${ic("close")}</button></div></div>
          </div>`).join("")
        : `<div class="empty" style="padding:70px 0"><div class="i">${ic("bag")}</div><h3>Your bag is empty</h3><p>Nothing here yet.</p></div>`}
        ${items.length && away > 0 ? `<div class="ship-bar"><i style="width:${pct}%"></i></div>
          <p class="tiny muted">Add ${money(away)} more for free shipping.</p>` : ""}
        ${items.length && away <= 0 && c.free_shipping_above ? `<p class="tiny muted" style="margin-top:16px">${ic("truck")} Free shipping unlocked.</p>` : ""}
      </div>
      ${items.length ? `<div class="drawer-f">
        <div class="sum">
          <div><span>Subtotal</span><span>${money(subtotal)}</span></div>
          <div><span>Shipping</span><span>${ship ? money(ship) : "Free"}</span></div>
          <div class="tot"><span>Total</span><span>${money(subtotal + ship)}</span></div>
        </div>
        <button class="b p blk" id="coBtn">Checkout${ic("arrow-right")}</button>
      </div>` : ""}
    </aside>`;

  requestAnimationFrame(() => { el("cScrim").classList.add("on"); el("cDrawer").classList.add("on"); });
  const shut = () => { el("cScrim").classList.remove("on"); el("cDrawer").classList.remove("on"); setTimeout(closeLayer, 420); };
  el("cScrim").onclick = shut; el("cClose").onclick = shut;
  el("layer").querySelectorAll("[data-inc]").forEach((b) => b.onclick = () => {
    const { pid, vid } = splitKey(b.dataset.inc); addToCart(pid, 1, vid); openCart();
  });
  el("layer").querySelectorAll("[data-dec]").forEach((b) => b.onclick = () => { setQty(b.dataset.dec, (S.cart[b.dataset.dec] || 1) - 1); openCart(); });
  el("layer").querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => { setQty(b.dataset.rm, 0); openCart(); });
  const co = el("coBtn");
  // shut() clears the layer after its slide-out finishes, so the next screen
  // has to open AFTER that or it gets wiped out from under the shopper.
  if (co) co.onclick = () => { shut(); setTimeout(startCheckout, 440); };
}

function openMobileNav() {
  const s2 = S.site, links = [["home", "Home"], ["shop", "Shop"]];
  if ((s2.sections || {}).story && (s2.story || {}).body) links.push(["#story", "Our story"]);
  links.push(["orders", "Orders"]);
  el("layer").innerHTML = `
    <nav class="mnav" id="mnav">
      <div class="mnav-h">
        <span class="brand">${s2.logo_url ? `<img src="${esc(s2.logo_url)}" alt="" />`
          : `<span class="mark">${esc(initials(s2.brand))}</span>`}<span>${esc(s2.brand || "Store")}</span></span>
        <button class="icon-b" id="mClose" aria-label="Close">${ic("close")}</button>
      </div>
      ${links.map(([k, l]) => k.startsWith("#")
        ? `<a href="${k}" data-mclose>${l}</a>`
        : `<a href="#" data-mgo="${k}">${l}</a>`).join("")}
      <div class="msearch">${ic("search")}<input id="mq" placeholder="Search products" value="${esc(S.query)}" /></div>
    </nav>`;
  requestAnimationFrame(() => el("mnav").classList.add("on"));
  const shut = () => { const n = el("mnav"); if (n) n.classList.remove("on"); setTimeout(closeLayer, 560); };
  el("mClose").onclick = shut;
  el("layer").querySelectorAll("[data-mgo]").forEach((a) => a.onclick = (e) => {
    e.preventDefault(); shut(); setTimeout(() => go(a.dataset.mgo), 120);
  });
  el("layer").querySelectorAll("[data-mclose]").forEach((a) => a.onclick = shut);
  const mq = el("mq");
  mq.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    S.query = mq.value; shut(); setTimeout(() => go("shop"), 120);
  });
}

function openAuth(after, startMode) {
  let mode = startMode || "login";
  const paint = () => {
    el("layer").innerHTML = `
      <div class="modal-s" id="aScrim"><div class="modal auth">
        <h3>${mode === "login" ? "Welcome back" : mode === "signup" ? "Create your account" : "Reset your password"}</h3>
        <p class="muted tiny" style="margin:0">${mode === "forgot"
          ? `We'll email you a link. It works once and expires in an hour.`
          : `Your account is specific to ${esc(S.site.brand)} — we never share it with other stores.`}</p>
        ${mode === "forgot" ? "" : `<div class="tabs">
          <button class="${mode === "login" ? "on" : ""}" data-m="login">Log in</button>
          <button class="${mode === "signup" ? "on" : ""}" data-m="signup">Sign up</button>
        </div>`}
        ${mode === "forgot" ? `<div style="height:22px"></div>` : ""}
        ${mode === "signup" ? `<div class="two">
          <label class="field"><span>Name</span><input id="aName" placeholder="Your name" /></label>
          <label class="field"><span>Phone</span><input id="aPhone" placeholder="10-digit mobile" inputmode="numeric" /></label>
        </div>` : ""}
        <label class="field"><span>Email</span><input id="aEmail" type="email" autocomplete="username" placeholder="you@email.com" /></label>
        ${mode === "forgot" ? "" : `<label class="field"><span>Password</span><input id="aPass" type="password" autocomplete="${mode === "login" ? "current-password" : "new-password"}" placeholder="${mode === "login" ? "Your password" : "At least 6 characters"}" /></label>`}
        <button class="b p blk" id="aGo" style="margin-top:8px">${
          mode === "login" ? "Log in" : mode === "signup" ? "Create account" : "Email me a link"}${ic("arrow-right")}</button>
        <div class="err" id="aErr" hidden></div>
        <div class="ok" id="aOk" hidden></div>
        ${mode === "login"
          ? `<p class="tiny muted" style="margin:16px 0 0;text-align:center">
               <a href="#" class="ul" data-m="forgot">Forgot your password?</a></p>`
          : mode === "forgot"
            ? `<p class="tiny muted" style="margin:16px 0 0;text-align:center">
                 <a href="#" class="ul" data-m="login">Back to log in</a></p>` : ""}
        <button class="b g blk" id="aCancel" style="margin-top:10px">Cancel</button>
      </div></div>`;
    el("layer").querySelectorAll("[data-m]").forEach((b) => b.onclick = (e) => {
      e.preventDefault(); mode = b.dataset.m; paint();
    });
    el("aCancel").onclick = closeLayer;
    el("aScrim").onclick = (e) => { if (e.target.id === "aScrim") closeLayer(); };
    const submit = async () => {
      const err = el("aErr"); err.hidden = true;
      if (mode === "forgot") {
        const go2 = el("aGo"); go2.disabled = true;
        try {
          const r = await api("/forgot", { method: "POST",
            json: { email: el("aEmail").value.trim() } });
          const ok = el("aOk");
          ok.textContent = r.message; ok.hidden = false;
        } catch (e2) {
          err.textContent = e2.message; err.hidden = false;
        }
        go2.disabled = false;
        return;
      }
      const body = { email: el("aEmail").value.trim(), password: el("aPass").value };
      if (mode === "signup") { body.name = (el("aName") || {}).value || ""; body.phone = (el("aPhone") || {}).value || ""; }
      el("aGo").disabled = true;
      try {
        const r = await api(mode === "login" ? "/login" : "/register", { method: "POST", json: body });
        S.token = r.token; S.customer = r.customer; store(LS_TOKEN, r.token);
        closeLayer(); toast(`Welcome, ${r.customer.name || r.customer.email}`, "user");
        render();
        if (after) after();
      } catch (e) {
        err.textContent = e.message; err.hidden = false;
        const goBtn = el("aGo"); if (goBtn) goBtn.disabled = false;   // the modal is gone on success
      }
    };
    el("aGo").onclick = submit;
    const pw = el("aPass");
    if (pw) pw.addEventListener("keydown", (e) => e.key === "Enter" && submit());
    el("aEmail").addEventListener("keydown", (e) => e.key === "Enter" && submit());
  };
  paint();
}

/* The emailed link comes back here as /s/<handle>?reset=<token>. Catching it
   on load is the whole difference between a shopper who is locked out of their
   own order history for good and one who is back in a minute. */
function openReset(token) {
  const paint = () => {
    el("layer").innerHTML = `
      <div class="modal-s" id="rScrim"><div class="modal auth">
        <h3>Choose a new password</h3>
        <p class="muted tiny" style="margin:0">For your ${esc(S.site.brand || "store")} account.</p>
        <div style="height:22px"></div>
        <label class="field"><span>New password</span>
          <input id="rPass" type="password" autocomplete="new-password" placeholder="At least 6 characters" /></label>
        <label class="field"><span>Repeat it</span>
          <input id="rPass2" type="password" autocomplete="new-password" placeholder="Type it again" /></label>
        <button class="b p blk" id="rGo" style="margin-top:8px">Set password${ic("arrow-right")}</button>
        <div class="err" id="rErr" hidden></div>
        <button class="b g blk" id="rCancel" style="margin-top:10px">Cancel</button>
      </div></div>`;
    const clean = () => {
      closeLayer();
      const u = new URL(location.href);
      u.searchParams.delete("reset");
      history.replaceState(null, "", u.pathname + (u.search || "") + u.hash);
    };
    el("rCancel").onclick = clean;
    el("rScrim").onclick = (e) => { if (e.target.id === "rScrim") clean(); };
    const submit = async () => {
      const err = el("rErr"); err.hidden = true;
      const a = el("rPass").value, b = el("rPass2").value;
      if (a !== b) { err.textContent = "Those two don't match."; err.hidden = false; return; }
      el("rGo").disabled = true;
      try {
        const r = await api("/reset", { method: "POST", json: { token, password: a } });
        clean();
        toast("Password set — log in with it now", "check");
        setTimeout(() => openAuth(() => loadMe(true)), 500);
      } catch (e) {
        err.textContent = e.message; err.hidden = false;
        el("rGo").disabled = false;
      }
    };
    el("rGo").onclick = submit;
    el("rPass2").addEventListener("keydown", (e) => e.key === "Enter" && submit());
  };
  paint();
}

function openPolicy(kind) {
  const text = (S.site.policies || {})[kind] || "";
  const titles = { shipping: "Shipping policy", returns: "Returns & refunds", privacy: "Privacy" };
  el("layer").innerHTML = `<div class="modal-s" id="pScrim"><div class="modal wide">
      <h3 style="margin-bottom:18px">${esc(titles[kind] || "Policy")}</h3>
      <p style="white-space:pre-line;color:var(--muted);margin:0">${esc(text)}</p>
      <button class="b g blk" id="pClose" style="margin-top:26px">Close</button></div></div>`;
  el("pClose").onclick = closeLayer;
  el("pScrim").onclick = (e) => { if (e.target.id === "pScrim") closeLayer(); };
}

/* ------------------------------------------------------------- checkout fl */
/* No account required to get here. A first-time buyer on a phone will not
   invent a password for a brand they met ten seconds ago — we take the order
   and make the account quietly afterwards. */
async function startCheckout() {
  try {
    S.priced = await api("/cart", { method: "POST", json: { lines: cartLines() } });
    (S.priced.issues || []).forEach((i) => {
      const k = cartKey(i.product_id, i.variant_id || "");
      if (i.reason === "out_of_stock") { delete S.cart[k]; toast(`${i.name} sold out — removed`, "close"); }
      if (i.reason === "reduced") { S.cart[k] = i.available; toast(`Only ${i.available} of ${i.name} left`, "package"); }
      if (i.reason === "unavailable") delete S.cart[k];
      if (i.reason === "choose_variant") {
        delete S.cart[k];
        toast(`Pick a size for ${i.name} first`, "package");
      }
    });
    if ((S.priced.issues || []).length) saveCart();
    go("checkout");
  } catch (e) { toast(e.message, "close"); }
}

async function placeOrder() {
  const err = el("coErr"); err.hidden = true;
  const btn = el("placeBtn"); btn.disabled = true; btn.textContent = "Placing order…";
  const pay = (document.querySelector('input[name="pay"]:checked') || {}).value || "cod";
  try {
    const r = await api("/order", {
      method: "POST",
      json: {
        lines: cartLines(), payment: pay, note: el("coNote").value,
        guest: !S.customer,
        name: el("coName").value,
        phone: el("coPhone").value,
        email: (el("coEmail") || {}).value || "",
        address: {
          name: el("coName").value, phone: el("coPhone").value,
          line1: el("coL1").value, line2: el("coL2").value,
          city: el("coCity").value, state: el("coState").value,
          pincode: el("coPin").value, landmark: el("coLm").value,
        },
      },
    });
    // a guest gets a session back, so "your orders" works without them ever
    // having chosen a password
    if (r.token && !S.token) { S.token = r.token; store(LS_TOKEN, r.token); }
    if (r.customer) S.customer = r.customer;
    S.cart = {}; saveCart();
    await refreshCatalogue();
    el("app").innerHTML = viewDone(r.order);
    bindView(); afterRender();
    history.pushState({ name: "done" }, "", location.pathname + location.search + "#done");
  } catch (e) {
    err.textContent = e.message; err.hidden = false;
    btn.disabled = false; btn.innerHTML = "Place order" + ic("arrow-right");
  }
}

async function refreshCatalogue() {
  try {
    const d = await api("/site");
    S.data = d; S.site = d.site; S.products = d.products; S.icons = d.icons || S.icons;
  } catch (e) { /* keep the page we already have */ }
}

/* ------------------------------------------------------------------ render */
function render() {
  const r = S.route;
  let html;
  if (r.name === "shop") html = viewShop();
  else if (r.name === "product") html = viewProduct(r.id);
  else if (r.name === "orders") html = viewOrders();
  else if (r.name === "checkout") html = viewCheckout();
  else html = viewHome();
  el("app").innerHTML = html;
  bindView();
  afterRender();
  if (r.name === "orders" && S.customer && !S.myOrders) loadMe(true);
}

function bindView() {
  document.querySelectorAll("[data-go]").forEach((n) => n.onclick = (e) => { e.preventDefault(); go(n.dataset.go); });
  document.querySelectorAll("[data-p]").forEach((n) => n.onclick = (e) => {
    if (e.target.closest("[data-add]")) return;
    go("product", { id: n.dataset.p });
  });
  document.querySelectorAll("[data-add]").forEach((n) => n.onclick = (e) => { e.stopPropagation(); addToCart(n.dataset.add); });
  document.querySelectorAll("[data-open]").forEach((n) => n.onclick = (e) => {
    e.stopPropagation(); go("product", { id: n.dataset.open });
  });
  document.querySelectorAll("[data-cat]").forEach((n) => n.onclick = (e) => { e.preventDefault(); S.filter = n.dataset.cat; go("shop"); });
  document.querySelectorAll("[data-policy]").forEach((n) => n.onclick = (e) => { e.preventDefault(); openPolicy(n.dataset.policy); });

  document.querySelectorAll("[data-p2]").forEach((n) => n.onclick = (e) => {
    e.preventDefault(); go("product", { id: n.dataset.p2 });
  });
  const cb = el("cartBtn"); if (cb) cb.onclick = openCart;
  const bg = el("burger"); if (bg) bg.onclick = openMobileNav;
  const ab = el("accBtn"); if (ab) ab.onclick = () => (S.customer ? go("orders") : openAuth());
  const lc = el("loginCta"); if (lc) lc.onclick = () => openAuth(() => loadMe(true));
  const ll = el("logoutLink"); if (ll) ll.onclick = async (e) => {
    e.preventDefault();
    try { await api("/logout", { method: "POST" }); } catch (err) { /* token already gone */ }
    S.token = null; S.customer = null; S.myOrders = null; store(LS_TOKEN, null);
    toast("Logged out", "user"); go("home");
  };

  const q = el("q");
  if (q) q.addEventListener("input", () => {
    S.query = q.value;
    clearTimeout(q._t);
    q._t = setTimeout(() => { if (S.route.name !== "shop") go("shop"); else render(); }, 280);
  });

  const qv = el("qVal");
  if (qv) {
    const p = S.products.find((x) => x.id === S.route.id) || {};
    if (p.id) bindProductPanel(p);
    document.querySelectorAll("[data-img]").forEach((b) => b.onclick = () => {
      el("pdMain").style.backgroundImage = `url('${b.dataset.img}')`;
      document.querySelectorAll("[data-img]").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
    });
  }
  document.querySelectorAll(".acc-h").forEach((h) => h.onclick = () => h.parentElement.classList.toggle("open"));

  const cl = el("coLogin");
  if (cl) cl.onclick = (e) => { e.preventDefault(); openAuth(() => loadMe(true)); };
  const pb = el("placeBtn"); if (pb) pb.onclick = placeOrder;
  document.querySelectorAll(".pay-opt").forEach((n) => n.onclick = () => {
    document.querySelectorAll(".pay-opt").forEach((x) => x.classList.remove("on"));
    n.classList.add("on");
  });
  const nf = el("newsForm");
  if (nf) nf.onsubmit = (e) => { e.preventDefault(); nf.reset(); toast("Thanks — we'll be in touch.", "mail"); };
}

async function loadMe(rerender) {
  if (!S.token) return;
  try {
    const r = await api("/me");
    S.customer = r.customer; S.myOrders = r.orders;
    if (rerender) render();
  } catch (e) {
    S.token = null; S.customer = null; store(LS_TOKEN, null);
    if (rerender) render();
  }
}

/* =========================================================================
   Edit mode — the builder's canvas
   ========================================================================= */
function post(msg) {
  if (EDIT && window.parent !== window) window.parent.postMessage({ source: "cs-store", ...msg }, "*");
}

function bindEditRegions() {
  document.querySelectorAll("[data-edit]").forEach((n) => {
    if (!n.querySelector(":scope > .edit-tag")) {
      const tag = document.createElement("span");
      tag.className = "edit-tag";
      tag.textContent = n.dataset.editLabel || n.dataset.edit;
      n.prepend(tag);
    }
    n.classList.toggle("sel", n.dataset.edit === S.selected);
  });
  // one delegated handler: the innermost editable region wins
  if (!document.body._editBound) {
    document.body._editBound = true;
    document.addEventListener("click", (e) => {
      const region = e.target.closest("[data-edit]");
      if (!region) return;
      e.preventDefault(); e.stopPropagation();
      selectRegion(region.dataset.edit);
    }, true);
  }
}

function selectRegion(key) {
  S.selected = key;
  document.querySelectorAll("[data-edit]").forEach((n) => n.classList.toggle("sel", n.dataset.edit === key));
  post({ type: "select", key });
}

addEventListener("message", (e) => {
  const m = e.data || {};
  if (m.source !== "cs-builder") return;
  if (m.type === "apply") {
    // The builder edited the document; re-theme and re-render in place.
    S.site = m.site; S.style = m.style;
    if (m.categories) S.data.categories = m.categories;
    applyTheme(S.style, S.site);
    render();
    if (m.scrollTo) scrollToRegion(m.scrollTo);
  } else if (m.type === "highlight") {
    S.selected = m.key;
    document.querySelectorAll("[data-edit]").forEach((n) => n.classList.toggle("sel", n.dataset.edit === m.key));
    scrollToRegion(m.key);
  } else if (m.type === "route") {
    // "Product" from the builder toolbar carries no id — show the first one.
    const params = m.params || {};
    if (m.name === "product" && !params.id) params.id = (S.products[0] || {}).id;
    if (m.name === "product" && !params.id) { toast("List a product first", "package"); return; }
    go(m.name, params);
  }
});

function scrollToRegion(key) {
  const n = document.querySelector(`[data-edit="${CSS.escape(key)}"]`);
  if (n) n.scrollIntoView({ behavior: "smooth", block: "center" });
}

/* -------------------------------------------------------------------- boot */
(async function boot() {
  try {
    const d = await api("/site");
    S.data = d; S.site = d.site; S.style = d.style; S.products = d.products; S.icons = d.icons || {};
  } catch (e) {
    el("boot").innerHTML = `<div style="text-align:center;max-width:420px;font-family:system-ui">
      <h3 style="margin:0 0 8px">This store isn't open</h3>
      <p style="color:#777;margin:0">${esc(e.message)}</p></div>`;
    return;
  }
  applyTheme(S.style, S.site);
  S.cart = migrateCart(store(LS_CART) || {});
  S.token = store(LS_TOKEN);
  readHash();
  el("boot").hidden = true; el("app").hidden = false;
  mountSpine();
  render();
  runPreloader();
  post({ type: "ready" });
  if (S.token) loadMe(S.route.name === "orders");
  // the emailed reset link comes back as ?reset=<token>
  const rt = QS.get("reset");
  if (rt) setTimeout(() => openReset(rt), 400);
})();

/* A cart saved before variants existed keys on the bare product id. Give those
   lines the empty variant half so they still price and still check out. */
function migrateCart(saved) {
  const out = {};
  Object.entries(saved || {}).forEach(([k, qty]) => {
    out[String(k).includes(KEY_SEP) ? k : cartKey(k, "")] = qty;
  });
  return out;
}

/* -------------------------------------------------------------- preloader */
function runPreloader() {
  // Skipped in the builder canvas (the seller would sit through it on every
  // repaint), when the seller has switched it off, and for repeat visits in
  // the same tab session.
  const seen = (() => { try { return sessionStorage.getItem("cs_seen_" + HANDLE); } catch (e) { return null; } })();
  if (EDIT || !S.style.preloader || seen || prefersReduced()) return;
  try { sessionStorage.setItem("cs_seen_" + HANDLE, "1"); } catch (e) { /* private mode */ }

  const pre = document.createElement("div");
  pre.className = "pre";
  pre.innerHTML = `
    <div class="pre-mark">${esc(S.site.brand || "Store")}</div>
    <div class="pre-bar"><i></i></div>
    <div class="pre-pct">00</div>`;
  document.body.appendChild(pre);
  document.body.style.overflow = "hidden";
  const bar = pre.querySelector("i"), pct = pre.querySelector(".pre-pct");
  const t0 = performance.now(), dur = 1250;
  (function step(t) {
    const k = Math.min(1, (t - t0) / dur);
    const eased = 1 - Math.pow(1 - k, 3);
    const v = Math.round(eased * 100);
    bar.style.width = v + "%";
    pct.textContent = (v < 10 ? "0" : "") + v;
    if (k < 1) requestAnimationFrame(step);
    else setTimeout(() => {
      pre.classList.add("gone");
      document.body.style.overflow = "";
      setTimeout(() => pre.remove(), 1050);
    }, 180);
  })(t0);
}

const prefersReduced = () =>
  window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ------------------------------------------------------------- scroll spine */
function mountSpine() {
  if (EDIT || prefersReduced()) return;
  const sp = document.createElement("div");
  sp.className = "spine"; sp.innerHTML = "<i></i>";
  document.body.appendChild(sp);
  S.spine = sp.firstElementChild;
}
