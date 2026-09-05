/* =========================================================================
   Storefront runtime.

   One file, no framework. It reads the seller's resolved theme from
   /api/shop/<handle>/site, writes it to CSS custom properties, and renders a
   themed shop: home, catalogue, product detail, cart drawer, checkout, and the
   shopper's own order history.

   Buying requires a shopper account on THIS store — that is the seller's rule,
   enforced server-side too. The cart itself lives in this browser only; every
   price and total is recalculated by the server before an order is accepted.
   ========================================================================= */

const HANDLE = decodeURIComponent(location.pathname.split("/s/")[1] || "").replace(/\/.*$/, "");
const LS_CART = "cs_cart_" + HANDLE;
const LS_TOKEN = "cs_tok_" + HANDLE;
// The builder's live preview loads this page with ?preview=<seller token> so an
// unpublished site renders for its owner and nobody else.
const PREVIEW = new URLSearchParams(location.search).get("preview") || "";

const S = {
  data: null, style: null, site: null, products: [],
  token: null, customer: null,
  cart: {}, route: { name: "home" }, filter: "", query: "",
};

/* ---------------------------------------------------------------- helpers */
const $ = (s, r = document) => r.querySelector(s);
const el = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const initials = (s) => (s || "S").trim().slice(0, 2).toUpperCase();

function store(key, val) {
  try {
    if (val === undefined) { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; }
    if (val === null) localStorage.removeItem(key); else localStorage.setItem(key, JSON.stringify(val));
  } catch (e) { /* private mode — cart simply won't persist */ }
  return null;
}

function toast(msg, ms = 2600) {
  const t = el("toast");
  t.textContent = msg; t.classList.add("on");
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
  set("--radius", (L.radius == null ? 12 : L.radius) + "px");
  set("--track", (L.track || 0) / 100 + "em");
  set("--case", L.case === "upper" ? "uppercase" : "none");
  set("--fh", style.heading_font.stack);
  set("--fb", style.body_font.stack);

  (style.motion || []).forEach((m) => root.classList.add("m-" + m));

  const fams = (style.google_fonts || []).map((f) => "family=" + f).join("&");
  if (fams) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?${fams}&display=swap`;
    document.head.appendChild(link);
  }
  document.title = (site.brand || "Store") + (site.tagline ? " — " + site.tagline : "");
}

/* ------------------------------------------------------------------- cart */
function cartLines() {
  return Object.entries(S.cart).map(([product_id, qty]) => ({ product_id, qty }));
}
function cartCount() {
  return Object.values(S.cart).reduce((a, b) => a + b, 0);
}
function saveCart() { store(LS_CART, S.cart); paintCartCount(); }
function paintCartCount() {
  const n = cartCount(), b = el("cartN");
  if (b) { b.textContent = n; b.hidden = n === 0; }
}
function addToCart(id, qty = 1) {
  const p = S.products.find((x) => x.id === id);
  if (!p) return;
  if (!p.in_stock) { toast("That one is out of stock right now."); return; }
  const next = (S.cart[id] || 0) + qty;
  if (p.available != null && next > p.available) {
    S.cart[id] = p.available;
    toast(`Only ${p.available} left — cart updated.`);
  } else {
    S.cart[id] = next;
    toast(`Added ${p.name} to your bag`);
  }
  saveCart();
}
function setQty(id, qty) {
  if (qty <= 0) delete S.cart[id]; else S.cart[id] = qty;
  saveCart();
}

/* ------------------------------------------------------------------ motion */
let _io = null;
function observeReveals(scope = document) {
  if (!document.documentElement.classList.contains("m-reveal")) return;
  if (!_io) {
    _io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); _io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
  }
  scope.querySelectorAll(".rv:not(.in), .zm:not(.in)").forEach((n) => _io.observe(n));
}

let _pxNodes = [];
function bindParallax(scope = document) {
  _pxNodes = Array.from(document.querySelectorAll("[data-px]"));
  onScroll();
}
function onScroll() {
  const y = window.scrollY;
  const hdr = el("hdr");
  if (hdr) hdr.classList.toggle("stuck", y > 12);
  if (!document.documentElement.classList.contains("m-parallax")) return;
  for (const n of _pxNodes) {
    const r = n.getBoundingClientRect();
    if (r.bottom < -200 || r.top > innerHeight + 200) continue;
    const speed = parseFloat(n.dataset.px) || 0.16;
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
      const dx = e.clientX - x0; moved = Math.abs(dx);
      rail.scrollLeft = l0 - dx;
    });
    const up = () => { down = false; rail.classList.remove("drag"); setTimeout(() => (rail._moved = moved), 0); };
    rail.addEventListener("pointerup", up);
    rail.addEventListener("pointerleave", up);
    rail.addEventListener("click", (e) => { if (rail._moved > 6) { e.stopPropagation(); e.preventDefault(); rail._moved = 0; } }, true);
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
      const step = rail.clientWidth * 0.8 * (btn.dataset.dir === "next" ? 1 : -1);
      rail.scrollBy({ left: step, behavior: "smooth" });
    };
  });
}

function afterRender() {
  paintCartCount();
  observeReveals();
  bindParallax();
  bindRails();
}

/* ----------------------------------------------------------------- routing */
function go(name, params = {}) {
  S.route = { name, ...params };
  const q = name === "home" ? "" : `#${name}${params.id ? "/" + params.id : ""}`;
  history.pushState(S.route, "", location.pathname + q);
  render();
  window.scrollTo({ top: 0, behavior: "instant" in document.documentElement.style ? "instant" : "auto" });
}
addEventListener("popstate", () => { readHash(); render(); });
function readHash() {
  const h = (location.hash || "").replace(/^#/, "");
  if (!h) { S.route = { name: "home" }; return; }
  const [name, id] = h.split("/");
  S.route = { name, id };
}

/* ------------------------------------------------------------------ chrome */
function header() {
  const s = S.site;
  const logo = s.logo_url
    ? `<img src="${esc(s.logo_url)}" alt="${esc(s.brand)}" />`
    : `<span class="mark">${esc(initials(s.brand))}</span>`;
  return `
  ${s.announcement ? `<div class="announce">${esc(s.announcement)}</div>` : ""}
  <header class="hdr" id="hdr">
    <div class="wrap hdr-in">
      <a class="brand" href="#" data-go="home">${logo}<span>${esc(s.brand || "Store")}</span></a>
      <nav class="nav">
        <a href="#" data-go="home">Home</a>
        <a href="#" data-go="shop">Shop</a>
        ${(s.sections || {}).story && (s.story || {}).body ? `<a href="#story">Our story</a>` : ""}
        <a href="#" data-go="orders">Orders</a>
      </nav>
      <div class="search"><input id="q" placeholder="Search products" value="${esc(S.query)}" /></div>
      <div class="hdr-r">
        <button class="icon-b" id="accBtn" title="${S.customer ? esc(S.customer.email) : "Log in"}">${S.customer ? "👤" : "🔑"}</button>
        <button class="icon-b" id="cartBtn" title="Your bag">🛍️<span class="cart-n" id="cartN" hidden>0</span></button>
      </div>
    </div>
  </header>`;
}

function footer() {
  const s = S.site, c = s.contact || {}, p = s.policies || {};
  const links = [
    c.email ? `<li><a href="mailto:${esc(c.email)}">${esc(c.email)}</a></li>` : "",
    c.phone ? `<li><a href="tel:${esc(c.phone)}">${esc(c.phone)}</a></li>` : "",
    c.whatsapp ? `<li><a href="https://wa.me/${esc(String(c.whatsapp).replace(/\D/g, ""))}" target="_blank" rel="noopener">WhatsApp</a></li>` : "",
    c.instagram ? `<li><a href="https://instagram.com/${esc(String(c.instagram).replace(/^@/, ""))}" target="_blank" rel="noopener">Instagram</a></li>` : "",
  ].join("");
  const pol = [
    p.shipping ? `<li><a href="#" data-policy="shipping">Shipping</a></li>` : "",
    p.returns ? `<li><a href="#" data-policy="returns">Returns</a></li>` : "",
    p.privacy ? `<li><a href="#" data-policy="privacy">Privacy</a></li>` : "",
  ].join("");
  return `
  <footer class="ftr"><div class="wrap">
    <div class="ftr-grid">
      <div>
        <div class="brand" style="margin-bottom:12px">${s.logo_url ? `<img src="${esc(s.logo_url)}" alt="" />` : `<span class="mark">${esc(initials(s.brand))}</span>`}<span>${esc(s.brand || "Store")}</span></div>
        <p class="muted" style="max-width:38ch;margin:0">${esc(s.tagline || "")}</p>
        ${c.address ? `<p class="muted tiny" style="margin-top:12px">${esc(c.address)}</p>` : ""}
      </div>
      <div><h4>Contact</h4><ul>${links || `<li class="muted">—</li>`}</ul></div>
      <div><h4>Shop</h4><ul>
        <li><a href="#" data-go="shop">All products</a></li>
        <li><a href="#" data-go="orders">My orders</a></li>
        ${pol}
      </ul></div>
    </div>
    <div class="ftr-bot">
      <span>© ${new Date().getFullYear()} ${esc(s.brand || "Store")}. All rights reserved.</span>
      <span>Powered by Content Seller</span>
    </div>
  </div></footer>`;
}

/* ------------------------------------------------------------- components */
function productCard(p, i = 0) {
  const off = p.mrp && p.price && p.mrp > p.price ? Math.round((1 - p.price / p.mrp) * 100) : 0;
  const img = p.image_url || (p.images || [])[0] || "";
  return `
  <article class="card rv zm d${(i % 4) + 1} ${p.in_stock ? "" : "sold"}" data-p="${esc(p.id)}">
    <div class="card-img" style="${img ? `background-image:url('${esc(img)}')` : ""}">
      ${img ? "" : `<div style="height:100%;display:grid;place-items:center;color:var(--muted);font-size:30px">🛍️</div>`}
      ${p.in_stock ? "" : `<div class="badge-out">Sold out</div>`}
    </div>
    <div class="card-body">
      ${p.category ? `<div class="card-cat">${esc(p.category)}</div>` : ""}
      <div class="card-name">${esc(p.name)}</div>
      ${p.description ? `<div class="card-desc">${esc(p.description)}</div>` : ""}
      <div class="price-row">
        <span class="price">${p.price != null ? money(p.price) : "—"}</span>
        ${off ? `<span class="mrp">${money(p.mrp)}</span><span class="off">${off}% off</span>` : ""}
      </div>
      <button class="b p sm card-add" data-add="${esc(p.id)}" ${p.in_stock ? "" : "disabled"}>
        ${p.in_stock ? "Add to bag" : "Sold out"}
      </button>
    </div>
  </article>`;
}

function railSection(id, title, sub, cardsHtml, count) {
  const nav = count > 3 ? `<div class="rail-nav">
      <button data-rail-nav="${id}" data-dir="prev" aria-label="Previous">‹</button>
      <button data-rail-nav="${id}" data-dir="next" aria-label="Next">›</button>
    </div>` : "";
  return `
  <section class="sec"><div class="wrap">
    <div class="sec-head rv">
      <div><div class="eyebrow">${esc(sub)}</div><h2>${esc(title)}</h2></div>
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
  const onImage = !!heroImg && (S.style.layout.hero === "full");

  const heroHtml = `
  <section class="hero ${onImage ? "on-image" : ""}" data-align="${esc(hero.align || "left")}">
    ${heroImg && S.style.layout.hero === "full" ? `
      <div class="hero-img" data-px="0.14" style="background-image:url('${esc(heroImg)}')"></div>
      <div class="hero-veil" style="background:linear-gradient(100deg, rgba(0,0,0,${(hero.overlay || 45) / 100}) 12%, rgba(0,0,0,${Math.max(0, (hero.overlay || 45) - 22) / 100}) 78%)"></div>` : ""}
    <div class="wrap hero-in">
      <div class="hero-copy rv">
        ${s.tagline ? `<div class="eyebrow" style="${onImage ? "color:rgba(255,255,255,.78)" : ""}">${esc(s.tagline)}</div>` : ""}
        <h1>${esc(hero.heading || s.brand || "Welcome")}</h1>
        <p>${esc(hero.sub || "Everything we make, in one place.")}</p>
        <div class="hero-cta">
          <button class="b p" data-go="shop">${esc(hero.cta_text || "Shop now")}</button>
          ${sec.story && (s.story || {}).body ? `<a class="b g" href="#story">Our story</a>` : ""}
        </div>
      </div>
      ${S.style.layout.hero === "split" ? `
        <div class="hero-art rv d2"><div style="${heroImg ? `background-image:url('${esc(heroImg)}')` : "background:var(--surface)"}"></div></div>` : ""}
    </div>
  </section>`;

  const marquee = document.documentElement.classList.contains("m-marquee")
    ? (() => {
        const words = [s.brand, "Free shipping over " + money(s.commerce.free_shipping_above || 0),
          "Secure checkout", "Made with care", s.tagline].filter(Boolean);
        const strip = words.map((w) => `<span>${esc(w)}</span>`).join("");
        return `<div class="marquee"><div class="marquee-t">${strip}${strip}</div></div>`;
      })()
    : "";

  const highlights = sec.highlights && (s.highlights || []).length ? `
    <section class="sec" style="padding-top:calc(var(--sec) * .7)"><div class="wrap">
      <div class="hl-grid">${(s.highlights || []).map((h, i) => `
        <div class="hl rv d${(i % 4) + 1}"><div class="i">${esc(h.icon || "✅")}</div>
          <b>${esc(h.title)}</b><p>${esc(h.text)}</p></div>`).join("")}</div>
    </div></section>` : "";

  const cats = sec.categories && S.data.categories.length ? railSection(
    "cats", "Shop by category", "Browse",
    S.data.categories.map((c, i) => {
      const n = S.products.filter((p) => p.category === c).length;
      return `<button class="cat-chip rv d${(i % 4) + 1}" data-cat="${esc(c)}"><b>${esc(c)}</b><span>${n} item${n === 1 ? "" : "s"}</span></button>`;
    }).join(""), S.data.categories.length) : "";

  const feat = sec.featured && featured.length ? railSection(
    "feat", "Featured", "Handpicked",
    featured.map(productCard).join(""), featured.length) : "";

  const story = sec.story && (s.story || {}).body ? `
    <section class="sec" id="story"><div class="wrap">
      <div class="story">
        <div class="story-art rv"><div data-px="0.1" style="${(s.story.image_url) ? `background-image:url('${esc(s.story.image_url)}')` : "background:var(--surface)"}"></div></div>
        <div class="rv d2">
          <div class="eyebrow">About us</div>
          <h2 style="margin-bottom:16px">${esc(s.story.title || "Our story")}</h2>
          <p style="color:var(--muted);white-space:pre-line">${esc(s.story.body)}</p>
        </div>
      </div>
    </div></section>` : "";

  const tst = sec.testimonials && (s.testimonials || []).length ? `
    <section class="sec"><div class="wrap">
      <div class="sec-head rv"><div><div class="eyebrow">Reviews</div><h2>What buyers say</h2></div></div>
      <div class="hl-grid">${s.testimonials.map((t, i) => `
        <div class="t-card rv d${(i % 4) + 1}">
          <div class="stars">${"★".repeat(t.rating || 5)}${"☆".repeat(5 - (t.rating || 5))}</div>
          <p>${esc(t.text)}</p><b>${esc(t.name || "Verified buyer")}</b>
        </div>`).join("")}</div>
    </div></section>` : "";

  const news = sec.newsletter ? `
    <section class="sec"><div class="wrap"><div class="news rv">
      <h2>Stay in the loop</h2>
      <p class="muted" style="margin:10px 0 0">New drops and offers, no spam.</p>
      <form id="newsForm"><input type="email" placeholder="you@email.com" required /><button class="b p">Join</button></form>
    </div></div></section>` : "";

  const all = `
    <section class="sec"><div class="wrap">
      <div class="sec-head rv"><div><div class="eyebrow">Catalogue</div><h2>All products</h2></div>
        <button class="b g sm" data-go="shop">View all →</button></div>
      <div class="grid">${S.products.slice(0, 8).map(productCard).join("")}</div>
    </div></section>`;

  return header() + heroHtml + marquee + highlights + cats + feat + all + story + tst + news + footer();
}

function viewShop() {
  const q = S.query.trim().toLowerCase();
  let list = S.products;
  if (S.filter) list = list.filter((p) => p.category === S.filter);
  if (q) list = list.filter((p) => (p.name + " " + p.category + " " + p.description).toLowerCase().includes(q));
  const chips = ["", ...S.data.categories].map((c) =>
    `<button class="chip ${S.filter === c ? "on" : ""}" data-cat="${esc(c)}">${c ? esc(c) : "All"}</button>`).join("");
  return header() + `
    <div class="wrap" style="padding-top:38px">
      <div class="eyebrow">${list.length} product${list.length === 1 ? "" : "s"}</div>
      <h1 style="font-size:clamp(28px,4vw,44px);margin-bottom:24px">${S.filter ? esc(S.filter) : "Everything we sell"}</h1>
      <div class="filters">${chips}</div>
      ${list.length ? `<div class="grid">${list.map(productCard).join("")}</div>`
        : `<div class="empty"><div class="i">🔍</div><p>Nothing matches that yet.</p></div>`}
      <div style="height:70px"></div>
    </div>` + footer();
}

function viewProduct(id) {
  const p = S.products.find((x) => x.id === id);
  if (!p) return header() + `<div class="wrap"><div class="empty"><div class="i">🫥</div><p>That product is no longer listed.</p><button class="b g" data-go="shop">Back to shop</button></div></div>` + footer();
  const imgs = [p.image_url, ...(p.images || [])].filter(Boolean);
  const off = p.mrp && p.price && p.mrp > p.price ? Math.round((1 - p.price / p.mrp) * 100) : 0;
  const related = S.products.filter((x) => x.id !== p.id && (!p.category || x.category === p.category)).slice(0, 8);
  const c = S.site.commerce || {};
  return header() + `
    <div class="wrap">
      <nav class="tiny muted" style="padding-top:22px"><a href="#" data-go="home">Home</a> / <a href="#" data-go="shop">Shop</a>${p.category ? ` / ${esc(p.category)}` : ""}</nav>
      <div class="pd">
        <div class="pd-gal">
          <div class="pd-main zm rv" id="pdMain" style="${imgs[0] ? `background-image:url('${esc(imgs[0])}')` : ""}">
            ${imgs.length ? "" : `<div style="height:100%;display:grid;place-items:center;color:var(--muted);font-size:44px">🛍️</div>`}
          </div>
          ${imgs.length > 1 ? `<div class="pd-thumbs">${imgs.map((u, i) =>
            `<button class="${i === 0 ? "on" : ""}" data-img="${esc(u)}" style="background-image:url('${esc(u)}')"></button>`).join("")}</div>` : ""}
        </div>
        <div class="rv d2">
          ${p.category ? `<div class="eyebrow">${esc(p.category)}</div>` : ""}
          <h1>${esc(p.name)}</h1>
          <div class="price-row" style="margin:14px 0 6px">
            <span class="price">${p.price != null ? money(p.price) : "—"}</span>
            ${off ? `<span class="mrp">${money(p.mrp)}</span><span class="off">${off}% off</span>` : ""}
          </div>
          <div class="tiny muted">${c.gst_percent ? (c.gst_inclusive ? `Inclusive of ${c.gst_percent}% GST` : `+ ${c.gst_percent}% GST at checkout`) : "No tax added"}${p.unit_label ? ` · per ${esc(p.unit_label)}` : ""}</div>
          ${p.description ? `<p style="margin-top:20px;white-space:pre-line">${esc(p.description)}</p>` : ""}
          ${(p.highlights || []).length ? `<ul class="pd-hl">${p.highlights.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>` : ""}
          <div class="pd-buy">
            <div class="qty">
              <button id="qMinus">−</button><span id="qVal">1</span><button id="qPlus">+</button>
            </div>
            <button class="b p" id="pdAdd" ${p.in_stock ? "" : "disabled"}>${p.in_stock ? "Add to bag" : "Sold out"}</button>
            <button class="b g" id="pdBuy" ${p.in_stock ? "" : "disabled"}>Buy now</button>
          </div>
          <div class="tiny ${p.in_stock ? "muted" : ""}" style="${p.in_stock ? "" : "color:#c0392b"}">
            ${p.in_stock ? (p.available != null && p.available <= 5 ? `Only ${p.available} left in stock` : "In stock") : "Currently unavailable"}
          </div>
          <div class="pd-meta">
            <div>🚚 ${c.free_shipping_above ? `Free delivery over ${money(c.free_shipping_above)}` : `Delivery ${money(c.shipping_fee || 0)}`}</div>
            ${c.cod_enabled ? `<div>💵 Cash on delivery available</div>` : ""}
            <div>🔐 You'll sign in to this store before placing an order</div>
          </div>
        </div>
      </div>
      ${related.length ? railSection("rel", "You may also like", "More from " + (p.category || S.site.brand), related.map(productCard).join(""), related.length) : ""}
    </div>` + footer();
}

function viewOrders() {
  if (!S.customer) {
    return header() + `<div class="wrap"><div class="empty">
      <div class="i">🔐</div><h3 style="margin-bottom:8px">Sign in to see your orders</h3>
      <p>Your order history lives with your ${esc(S.site.brand)} account.</p>
      <button class="b p" id="loginCta" style="margin-top:14px">Log in or sign up</button>
    </div></div>` + footer();
  }
  const orders = S.myOrders || [];
  const flow = ["new", "confirmed", "packed", "shipped", "delivered"];
  return header() + `
    <div class="wrap" style="padding-top:36px">
      <div class="eyebrow">Account</div>
      <h1 style="font-size:clamp(26px,3.6vw,40px);margin-bottom:6px">Your orders</h1>
      <p class="muted" style="margin-bottom:26px">${esc(S.customer.email)} · <a href="#" id="logoutLink" style="text-decoration:underline">log out</a></p>
      ${orders.length ? orders.map((o) => {
        const idx = flow.indexOf(o.status);
        return `<div class="ord">
          <div class="ord-h">
            <div><b>${esc(o.order_no)}</b><div class="tiny muted">${esc(String(o.created_at).replace("T", " ").slice(0, 16))}</div></div>
            <div style="display:flex;gap:10px;align-items:center">
              <span class="pill ${esc(o.status)}">${esc(o.status)}</span>
              <b>${money(o.total)}</b>
            </div>
          </div>
          <div class="tiny muted">${(o.items || []).map((i) => `${esc(i.name)} × ${i.qty}`).join(" · ")}</div>
          ${o.status === "cancelled" ? "" : `<div class="steps">${flow.map((_, i) => `<i class="${i <= idx ? "on" : ""}"></i>`).join("")}</div>`}
        </div>`;
      }).join("") : `<div class="empty"><div class="i">📦</div><p>No orders yet.</p><button class="b p" data-go="shop">Start shopping</button></div>`}
      <div style="height:70px"></div>
    </div>` + footer();
}

function viewCheckout() {
  const priced = S.priced;
  if (!priced || !priced.items.length) {
    return header() + `<div class="wrap"><div class="empty"><div class="i">🛍️</div><p>Your bag is empty.</p><button class="b p" data-go="shop">Shop products</button></div></div>` + footer();
  }
  const a = (S.customer && S.customer.address) || {};
  const c = S.site.commerce || {};
  return header() + `
    <div class="wrap">
      <div class="co">
        <div>
          <h1 style="font-size:clamp(24px,3.2vw,36px);margin-bottom:6px">Checkout</h1>
          <p class="muted" style="margin:0 0 20px">Signed in as ${esc(S.customer.email)}</p>

          <div class="co-box">
            <h3 style="margin-bottom:16px">Delivery address</h3>
            <div class="two">
              <label class="field"><span>Full name</span><input id="coName" value="${esc(S.customer.name || "")}" placeholder="Your name" /></label>
              <label class="field"><span>Phone</span><input id="coPhone" value="${esc(S.customer.phone || "")}" placeholder="10-digit mobile" inputmode="numeric" /></label>
            </div>
            <label class="field"><span>Address</span><input id="coL1" value="${esc(a.line1 || "")}" placeholder="Flat / house, street" /></label>
            <label class="field"><span>Area, landmark <span class="muted">(optional)</span></span><input id="coL2" value="${esc(a.line2 || "")}" /></label>
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
            <h3 style="margin-bottom:16px">Payment</h3>
            ${c.cod_enabled ? `<label class="pay-opt on" data-pay="cod"><input type="radio" name="pay" value="cod" checked />
              <div><b>Cash on delivery</b><div class="tiny muted">Pay the courier when your order arrives.</div></div></label>` : ""}
            <label class="pay-opt ${c.cod_enabled ? "" : "on"}" data-pay="prepaid"><input type="radio" name="pay" value="prepaid" ${c.cod_enabled ? "" : "checked"} />
              <div><b>Pay online</b><div class="tiny muted">We'll send you a payment link to confirm this order.</div></div></label>
            <label class="field" style="margin-top:14px"><span>Order note <span class="muted">(optional)</span></span><textarea id="coNote" rows="2" placeholder="Anything we should know?"></textarea></label>
          </div>
        </div>

        <div class="co-side">
          <div class="co-box">
            <h3 style="margin-bottom:14px">Order summary</h3>
            ${priced.items.map((i) => `<div class="ci" style="grid-template-columns:52px 1fr auto">
              <div class="ci-img" style="width:52px;height:52px;${i.image_url ? `background-image:url('${esc(i.image_url)}')` : ""}"></div>
              <div><b>${esc(i.name)}</b><div class="tiny muted">Qty ${i.qty}</div></div>
              <b>${money(i.line_total)}</b></div>`).join("")}
            <div class="sum" style="margin-top:16px">
              <div><span>Subtotal</span><span>${money(priced.subtotal)}</span></div>
              <div><span>Shipping</span><span>${priced.shipping ? money(priced.shipping) : "Free"}</span></div>
              ${priced.gst_percent ? `<div><span>GST (${priced.gst_percent}%)${priced.gst_inclusive ? " incl." : ""}</span><span>${money(priced.tax)}</span></div>` : ""}
              <div class="tot"><span>Total</span><span>${money(priced.total)}</span></div>
            </div>
            <button class="b p blk" id="placeBtn">Place order</button>
            <div class="err" id="coErr" hidden></div>
            ${c.order_note ? `<p class="tiny muted" style="margin:12px 0 0">${esc(c.order_note)}</p>` : ""}
          </div>
        </div>
      </div>
    </div>` + footer();
}

function viewDone(order) {
  const flow = ["new", "confirmed", "packed", "shipped", "delivered"];
  return header() + `
    <div class="wrap"><div class="empty" style="padding-top:80px">
      <div class="i">🎉</div>
      <h1 style="font-size:clamp(24px,3.4vw,38px);margin-bottom:10px">Order placed</h1>
      <p>Thank you, ${esc(order.customer_name || "friend")}. Your order <b>${esc(order.order_no)}</b> is confirmed for ${money(order.total)}.</p>
      <div class="ord" style="text-align:left;max-width:520px;margin:26px auto 0">
        <div class="ord-h"><b>${esc(order.order_no)}</b><span class="pill new">new</span></div>
        <div class="tiny muted">${(order.items || []).map((i) => `${esc(i.name)} × ${i.qty}`).join(" · ")}</div>
        <div class="steps">${flow.map((_, i) => `<i class="${i === 0 ? "on" : ""}"></i>`).join("")}</div>
      </div>
      <div style="display:flex;gap:10px;justify-content:center;margin-top:26px;flex-wrap:wrap">
        <button class="b p" data-go="orders">Track my orders</button>
        <button class="b g" data-go="shop">Keep shopping</button>
      </div>
    </div></div>` + footer();
}

/* --------------------------------------------------------------- overlays */
function closeLayer() { el("layer").innerHTML = ""; }

function openCart() {
  const lines = cartLines();
  const items = lines.map((l) => {
    const p = S.products.find((x) => x.id === l.product_id);
    return p ? { ...p, qty: l.qty } : null;
  }).filter(Boolean);
  const subtotal = items.reduce((a, i) => a + (i.price || 0) * i.qty, 0);
  const c = S.site.commerce || {};
  const ship = items.length && c.shipping_fee && (!c.free_shipping_above || subtotal < c.free_shipping_above) ? c.shipping_fee : 0;
  const away = c.free_shipping_above && subtotal < c.free_shipping_above ? c.free_shipping_above - subtotal : 0;

  el("layer").innerHTML = `
    <div class="scrim" id="cScrim"></div>
    <aside class="drawer" id="cDrawer">
      <div class="drawer-h"><h3>Your bag${items.length ? ` (${cartCount()})` : ""}</h3><button class="icon-b" id="cClose">✕</button></div>
      <div class="drawer-b">
        ${items.length ? items.map((i) => `
          <div class="ci">
            <div class="ci-img" style="${i.image_url ? `background-image:url('${esc(i.image_url)}')` : ""}"></div>
            <div>
              <b>${esc(i.name)}</b>
              <div class="tiny muted">${money(i.price)} each</div>
              <div class="qty"><button data-dec="${esc(i.id)}">−</button><span>${i.qty}</span><button data-inc="${esc(i.id)}">+</button></div>
            </div>
            <div style="text-align:right"><b>${money((i.price || 0) * i.qty)}</b><br/><button class="ci-x" data-rm="${esc(i.id)}">✕</button></div>
          </div>`).join("")
        : `<div class="empty"><div class="i">🛍️</div><p>Your bag is empty.</p></div>`}
        ${away > 0 ? `<p class="tiny muted" style="margin-top:16px">Add ${money(away)} more for free shipping.</p>` : ""}
      </div>
      ${items.length ? `<div class="drawer-f">
        <div class="sum">
          <div><span>Subtotal</span><span>${money(subtotal)}</span></div>
          <div><span>Shipping</span><span>${ship ? money(ship) : "Free"}</span></div>
          <div class="tot"><span>Total</span><span>${money(subtotal + ship)}</span></div>
        </div>
        <button class="b p blk" id="coBtn">${S.customer ? "Checkout" : "Log in to check out"}</button>
      </div>` : ""}
    </aside>`;

  requestAnimationFrame(() => {
    el("cScrim").classList.add("on"); el("cDrawer").classList.add("on");
  });
  const shut = () => { el("cScrim").classList.remove("on"); el("cDrawer").classList.remove("on"); setTimeout(closeLayer, 340); };
  el("cScrim").onclick = shut; el("cClose").onclick = shut;
  el("layer").querySelectorAll("[data-inc]").forEach((b) => b.onclick = () => { addToCart(b.dataset.inc, 1); openCart(); });
  el("layer").querySelectorAll("[data-dec]").forEach((b) => b.onclick = () => { setQty(b.dataset.dec, (S.cart[b.dataset.dec] || 1) - 1); openCart(); });
  el("layer").querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => { setQty(b.dataset.rm, 0); openCart(); });
  const co = el("coBtn");
  // shut() clears the layer after its slide-out finishes, so the next overlay
  // has to open AFTER that or it gets wiped out from under the shopper.
  if (co) co.onclick = () => {
    shut();
    setTimeout(() => (S.customer ? startCheckout() : openAuth(startCheckout)), 360);
  };
}

function openAuth(after) {
  let mode = "login";
  const paint = () => {
    el("layer").innerHTML = `
      <div class="modal-s" id="aScrim"><div class="modal">
        <h3>${mode === "login" ? "Welcome back" : "Create your account"}</h3>
        <p class="muted tiny" style="margin:0">Your account is specific to ${esc(S.site.brand)} — we never share it with other stores.</p>
        <div class="tabs">
          <button class="${mode === "login" ? "on" : ""}" data-m="login">Log in</button>
          <button class="${mode === "signup" ? "on" : ""}" data-m="signup">Sign up</button>
        </div>
        ${mode === "signup" ? `<div class="two">
          <label class="field"><span>Name</span><input id="aName" placeholder="Your name" /></label>
          <label class="field"><span>Phone</span><input id="aPhone" placeholder="10-digit mobile" inputmode="numeric" /></label>
        </div>` : ""}
        <label class="field"><span>Email</span><input id="aEmail" type="email" autocomplete="username" placeholder="you@email.com" /></label>
        <label class="field"><span>Password</span><input id="aPass" type="password" autocomplete="${mode === "login" ? "current-password" : "new-password"}" placeholder="${mode === "login" ? "Your password" : "At least 6 characters"}" /></label>
        <button class="b p blk" id="aGo">${mode === "login" ? "Log in" : "Create account"}</button>
        <div class="err" id="aErr" hidden></div>
        <button class="b g blk" id="aCancel" style="margin-top:10px">Cancel</button>
      </div></div>`;
    el("layer").querySelectorAll("[data-m]").forEach((b) => b.onclick = () => { mode = b.dataset.m; paint(); });
    el("aCancel").onclick = closeLayer;
    el("aScrim").onclick = (e) => { if (e.target.id === "aScrim") closeLayer(); };
    const submit = async () => {
      const err = el("aErr"); err.hidden = true;
      const body = { email: el("aEmail").value.trim(), password: el("aPass").value };
      if (mode === "signup") { body.name = (el("aName") || {}).value || ""; body.phone = (el("aPhone") || {}).value || ""; }
      el("aGo").disabled = true;
      try {
        const r = await api(mode === "login" ? "/login" : "/register", { method: "POST", json: body });
        S.token = r.token; S.customer = r.customer; store(LS_TOKEN, r.token);
        closeLayer(); toast(`Welcome, ${r.customer.name || r.customer.email}`);
        render();
        if (after) after();
      } catch (e) { err.textContent = e.message; err.hidden = false; }
      const goBtn = el("aGo");
    if (goBtn) goBtn.disabled = false;   // the modal is gone on success
    };
    el("aGo").onclick = submit;
    el("aPass").addEventListener("keydown", (e) => e.key === "Enter" && submit());
  };
  paint();
}

function openPolicy(kind) {
  const text = (S.site.policies || {})[kind] || "";
  const titles = { shipping: "Shipping policy", returns: "Returns & refunds", privacy: "Privacy" };
  el("layer").innerHTML = `<div class="modal-s" id="pScrim"><div class="modal wide">
      <h3 style="margin-bottom:14px">${esc(titles[kind] || "Policy")}</h3>
      <p style="white-space:pre-line;color:var(--muted)">${esc(text)}</p>
      <button class="b g blk" id="pClose" style="margin-top:18px">Close</button></div></div>`;
  el("pClose").onclick = closeLayer;
  el("pScrim").onclick = (e) => { if (e.target.id === "pScrim") closeLayer(); };
}

/* ------------------------------------------------------------- checkout fl */
async function startCheckout() {
  if (!S.customer) { openAuth(startCheckout); return; }
  try {
    S.priced = await api("/cart", { method: "POST", json: { lines: cartLines() } });
    (S.priced.issues || []).forEach((i) => {
      if (i.reason === "out_of_stock") { delete S.cart[i.product_id]; toast(`${i.name} sold out — removed from your bag`); }
      if (i.reason === "reduced") { S.cart[i.product_id] = i.available; toast(`Only ${i.available} of ${i.name} left`); }
      if (i.reason === "unavailable") delete S.cart[i.product_id];
    });
    if ((S.priced.issues || []).length) saveCart();
    go("checkout");
  } catch (e) { toast(e.message); }
}

async function placeOrder() {
  const err = el("coErr"); err.hidden = true;
  const btn = el("placeBtn"); btn.disabled = true; btn.textContent = "Placing order…";
  const pay = (document.querySelector('input[name="pay"]:checked') || {}).value || "cod";
  try {
    const r = await api("/order", {
      method: "POST",
      json: {
        lines: cartLines(),
        payment: pay,
        note: el("coNote").value,
        address: {
          name: el("coName").value, phone: el("coPhone").value,
          line1: el("coL1").value, line2: el("coL2").value,
          city: el("coCity").value, state: el("coState").value,
          pincode: el("coPin").value, landmark: el("coLm").value,
        },
      },
    });
    S.cart = {}; saveCart();
    await refreshCatalogue();
    el("app").innerHTML = viewDone(r.order);
    bindView(); afterRender();
    history.pushState({ name: "done" }, "", location.pathname + "#done");
  } catch (e) {
    err.textContent = e.message; err.hidden = false;
    btn.disabled = false; btn.textContent = "Place order";
  }
}

async function refreshCatalogue() {
  try {
    const d = await api("/site");
    S.data = d; S.site = d.site; S.products = d.products;
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
  document.querySelectorAll("[data-cat]").forEach((n) => n.onclick = () => { S.filter = n.dataset.cat; go("shop"); });
  document.querySelectorAll("[data-policy]").forEach((n) => n.onclick = (e) => { e.preventDefault(); openPolicy(n.dataset.policy); });

  const cb = el("cartBtn"); if (cb) cb.onclick = openCart;
  const ab = el("accBtn"); if (ab) ab.onclick = () => (S.customer ? go("orders") : openAuth());
  const lc = el("loginCta"); if (lc) lc.onclick = () => openAuth(() => loadMe(true));
  const ll = el("logoutLink"); if (ll) ll.onclick = async (e) => {
    e.preventDefault();
    try { await api("/logout", { method: "POST" }); } catch (err) { /* token already gone */ }
    S.token = null; S.customer = null; S.myOrders = null; store(LS_TOKEN, null);
    toast("Logged out"); go("home");
  };

  const q = el("q");
  if (q) q.addEventListener("input", () => {
    S.query = q.value;
    clearTimeout(q._t);
    q._t = setTimeout(() => { if (S.route.name !== "shop") go("shop"); else render(); }, 260);
  });

  // product detail interactions
  const qv = el("qVal");
  if (qv) {
    const p = S.products.find((x) => x.id === S.route.id) || {};
    const cap = p.available == null ? 99 : p.available;
    el("qMinus").onclick = () => { qv.textContent = Math.max(1, +qv.textContent - 1); };
    el("qPlus").onclick = () => { qv.textContent = Math.min(cap, +qv.textContent + 1); };
    el("pdAdd").onclick = () => addToCart(S.route.id, +qv.textContent);
    el("pdBuy").onclick = () => { addToCart(S.route.id, +qv.textContent); S.customer ? startCheckout() : openAuth(startCheckout); };
    document.querySelectorAll("[data-img]").forEach((b) => b.onclick = () => {
      el("pdMain").style.backgroundImage = `url('${b.dataset.img}')`;
      document.querySelectorAll("[data-img]").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
    });
  }

  const pb = el("placeBtn"); if (pb) pb.onclick = placeOrder;
  document.querySelectorAll(".pay-opt").forEach((n) => n.onclick = () => {
    document.querySelectorAll(".pay-opt").forEach((x) => x.classList.remove("on"));
    n.classList.add("on");
  });
  const nf = el("newsForm");
  if (nf) nf.onsubmit = (e) => { e.preventDefault(); nf.reset(); toast("Thanks — we'll be in touch."); };
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

/* -------------------------------------------------------------------- boot */
(async function boot() {
  try {
    const d = await api("/site");
    S.data = d; S.site = d.site; S.style = d.style; S.products = d.products;
  } catch (e) {
    el("boot").innerHTML = `<div style="text-align:center;max-width:400px">
      <div style="font-size:38px;margin-bottom:10px">🚧</div>
      <h3 style="font-family:system-ui">This store isn't open</h3>
      <p style="color:#777">${esc(e.message)}</p></div>`;
    return;
  }
  applyTheme(S.style, S.site);
  S.cart = store(LS_CART) || {};
  S.token = store(LS_TOKEN);
  readHash();
  el("boot").hidden = true; el("app").hidden = false;
  render();
  if (S.token) loadMe(S.route.name === "orders");
})();
