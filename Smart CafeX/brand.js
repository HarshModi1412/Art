/* =========================================================================
   MODULE: Brand Management
   Design: docs/designs/brand-management-module.md   Server: backend/core/brandkit.py

   The seller picks who they sell to and a direction; the server composes a
   whole brand (name set in type, colours, type, voice, copy); every part is
   editable here; Apply copies it into the Website Builder and Product Studio.

   Rules this file keeps:
   - The wordmark is the seller's name SET IN TYPE, by the browser. Nothing
     here draws a logo with AI, and the PNG export draws the same type.
   - The server is the only writer of copy. This file sends choices and the
     seller's own edits; whatever came back is what shows.
   - Faces load from Google Fonts only after the seller opens this module
     (their action, like the storefront's own font loader). The app shell
     never loads them.
   ========================================================================= */
let _bm = null;          // /api/brand/state
let _bmKit = null;       // the working kit (what the screen shows)
let _bmDesc = null;      // derived: monogram, contrast, filled voice and imagery
let _bmStep = "basics";
let _bmSaveT = null;
let _bmSeq = 0;
let _bmPlan = null;      // last /api/brand/plan answer
let _bmPlanOpts = {};
const _bmFonts = new Set();

const BM_STEPS = [
  { id: "basics", label: "Your brand", hint: "Name, what you sell, who buys" },
  { id: "direction", label: "Direction", hint: "The look and the voice" },
  { id: "book", label: "Brand book", hint: "Logo, colours, type, words" },
  { id: "apply", label: "Apply", hint: "Your website and posts" },
];
const BM_ROLES = [
  ["ground", "Background"], ["surface", "Panels"], ["ink", "Text"],
  ["accent", "Accent"], ["support", "Support"],
];
const BM_CAT_ICON = { jewellery: "spark", clothing: "scissors", fragrance: "droplet", home_decor: "leaf" };
const BM_SOURCE = {
  studio: "From your Product Studio brand.", site: "From your website.",
  business: "From your business details.",
};

/* ------------------------------------------------------------- lookups -- */
const bmDir = (id) => ((_bm && _bm.library.directions) || []).find((d) => d.id === id) || null;
const bmFontRow = (id) => ((_bm && _bm.fonts) || []).find((f) => f.id === id) || null;
function bmFamily(id) {
  const f = bmFontRow(id);
  const m = f && /'([^']+)'/.exec(f.stack);
  return m ? m[1] : "serif";
}
const bmStack = (id) => (bmFontRow(id) || {}).stack || "Georgia, serif";
const bmCaseCss = (wm, keep) => keep ? "none" : ({ upper: "uppercase", lower: "lowercase" }[wm.case] || "none");
function bmCased(text, wm, keep) {
  if (keep) return text;
  if (wm.case === "upper") return text.toUpperCase();
  if (wm.case === "lower") return text.toLowerCase();
  return text;
}

/* Google Fonts, on demand. A card only needs its one weight and the letters
   of the seller's name (text= subset, a few KB); the brand book loads the
   full families later, and the later stylesheet wins. */
function bmLoadFonts(ids, opts = {}) {
  const fams = [];
  ids.filter(Boolean).forEach((id) => {
    const f = bmFontRow(id);
    if (!f) return;
    const key = opts.text ? `${id}|${opts.weight}|${opts.text}` : id;
    if (_bmFonts.has(key) || _bmFonts.has(id)) return;
    _bmFonts.add(key);
    fams.push(opts.text ? `${f.g.split(":")[0]}${opts.weight ? `:wght@${opts.weight}` : ""}` : f.g);
  });
  if (!fams.length) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "https://fonts.googleapis.com/css2?" + fams.map((g) => "family=" + g).join("&")
    + (opts.text ? "&text=" + encodeURIComponent(opts.text + opts.text.toUpperCase() + opts.text.toLowerCase()) : "")
    + "&display=swap";
  document.head.appendChild(link);
}

/* The brand as CSS custom properties. Every brand-styled surface reads these,
   so a colour or type change repaints without rebuilding the page. */
function bmVars(kit, colours) {
  const c = colours || kit.colours || {};
  const wm = kit.wordmark || {};
  const f = kit.fonts || {};
  const onAccent = c.accent ? bmOnAccent(c) : c.ground;
  return [
    `--b-ground:${c.ground}`, `--b-surface:${c.surface}`, `--b-ink:${c.ink}`,
    `--b-accent:${c.accent}`, `--b-support:${c.support}`, `--b-on-accent:${onAccent}`,
    `--b-wm:${bmStack(wm.font)}`, `--b-wm-weight:${wm.weight || 400}`,
    `--b-wm-track:${(wm.track || 0)}em`, `--b-wm-case:${bmCaseCss(wm, kit.keep_case)}`,
    `--b-head:${bmStack(f.heading)}`, `--b-body:${bmStack(f.body)}`, `--b-accent-font:${bmStack(f.accent)}`,
  ].join(";");
}
function bmSetVars(el) {
  if (!el) return;
  el.setAttribute("style", bmVars(_bmKit));
}

/* WCAG contrast, the same maths as brandkit.contrast(). Used to pick the
   text colour that sits on the accent for whichever palette is drawn. */
function bmLum(hex) {
  const h = String(hex || "#000000").replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)))
    .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i], 0);
}
function bmContrast(a, b) {
  const x = bmLum(a), y = bmLum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
const bmOnAccent = (c) => (bmContrast(c.ground, c.accent) >= bmContrast(c.ink, c.accent) ? c.ground : c.ink);

/* Shrink a wordmark to fit its box. A long name must never overflow a card,
   a post or the cover; the type size gives way, not the layout. */
function bmFit(root) {
  (root || document).querySelectorAll("[data-fit]").forEach((el) => {
    el.style.fontSize = "";
    const box = el.parentElement;
    if (!box) return;
    const avail = box.clientWidth * (parseFloat(el.dataset.fit) || 0.9);
    const w = el.scrollWidth;
    if (w > avail && w > 0) {
      const size = parseFloat(getComputedStyle(el).fontSize);
      el.style.fontSize = Math.max(10, Math.floor(size * avail / w)) + "px";
    }
  });
}
function bmFitSoon(root) {
  requestAnimationFrame(() => bmFit(root));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => bmFit(root));
  setTimeout(() => bmFit(root), 700);
}

/* ----------------------------------------------------------------- open -- */
async function openBrand(step) {
  moduleShell("Brand Management", `<div class="ap-empty">Loading your brand…</div>`);
  try {
    _bm = await api("/api/brand/state");
  } catch (e) {
    moduleShell("Brand Management", failed(e.message, () => openModule("brand")));
    return;
  }
  _bmKit = JSON.parse(JSON.stringify(_bm.kit));
  _bmDesc = _bm.describe;
  if (!_bmKit.name && _bm.suggested.name) {
    _bmKit.name = _bm.suggested.name.slice(0, 80);
    _bmKit.name_source = _bm.suggested.source;
  }
  if (!_bmKit.category && _bm.suggested.category) _bmKit.category = _bm.suggested.category;
  _bmStep = step || (_bmKit.direction && _bmKit.name ? "book" : "basics");
  _bmPlan = null;
  bmRender();
}

function bmReady(stepId) {
  const k = _bmKit;
  const nameOk = k.name && k.name.trim().length >= 1 && k.name.length <= _bm.library.name_max;
  if (stepId === "direction") return nameOk && k.category && k.age;
  if (stepId === "book" || stepId === "apply") return nameOk && k.category && k.age && k.direction;
  return true;
}

function bmGo(id) {
  if (!bmReady(id)) {
    const k = _bmKit;
    const need = !k.name ? "your shop's name" : k.name.length > _bm.library.name_max ? "a shorter name (40 characters at most)"
      : !k.category ? "what you sell" : !k.age ? "who buys from you" : "a direction";
    toast(`Add ${need} first.`, 4000);
    if (_bmStep !== "basics" && (!k.name || !k.category || !k.age)) { _bmStep = "basics"; bmRender(); }
    return;
  }
  _bmStep = id;
  bmRender();
  const main = document.querySelector(".main");
  if (main) main.scrollTo({ top: 0, behavior: "smooth" });
}

function bmRender() {
  const idx = BM_STEPS.findIndex((s) => s.id === _bmStep);
  const rail = BM_STEPS.map((s, i) => `
    <button class="wz ${s.id === _bmStep ? "on" : ""} ${i < idx ? "done" : ""}" data-bmstep="${s.id}">
      <span class="wz-n">${i < idx ? "✓" : i + 1}</span>
      <span class="wz-t"><b>${esc(s.label)}</b><i>${esc(s.hint)}</i></span></button>`).join("");
  moduleShell("Brand Management", `
    <div class="bm-bar">
      <p class="muted tiny" style="margin:0;">Pick the brand your buyers respond to. We set your name in type,
        choose the colours and fonts, write the words, and put it on your website and posts.</p>
      <span class="bm-save" id="bmSave">${_bmKit.updated_at ? "Saved" : ""}</span>
    </div>
    <div class="wz-rail bm-rail">${rail}</div>
    <div id="bmBody"></div>`);
  document.querySelectorAll("[data-bmstep]").forEach((b) => b.onclick = () => bmGo(b.dataset.bmstep));
  const body = $("bmBody");
  if (_bmStep === "basics") { body.innerHTML = bmBasicsHtml(); bmWireBasics(); }
  else if (_bmStep === "direction") { body.innerHTML = bmDirectionsHtml(); bmWireDirections(); }
  else if (_bmStep === "book") { body.innerHTML = bmBookHtml(); bmWireBook(); }
  else { body.innerHTML = `<div class="ap-empty">Checking what Apply would change…</div>`; bmLoadPlan(); }
  body.querySelectorAll("[data-bmgo]").forEach((b) => b.onclick = () => bmGo(b.dataset.bmgo));
}

/* --------------------------------------------------------------- saving -- */
function bmSaveState(t) { const s = $("bmSave"); if (s) s.textContent = t; }

function bmDraft() {
  const k = _bmKit;
  return {
    name: k.name, name_source: k.name_source, keep_case: k.keep_case, category: k.category, age: k.age,
    direction: k.direction, palette: k.palette, colours: k.colours, fonts: k.fonts, wordmark: k.wordmark,
    frame: k.frame, text: k.text, variants: k.variants, edited: k.edited, reset_visuals: !!k.reset_visuals,
  };
}

function bmQueue(delay = 380) {
  clearTimeout(_bmSaveT);
  bmSaveState("Saving…");
  _bmSaveT = setTimeout(bmSave, delay);
}

async function bmSave() {
  const seq = ++_bmSeq;
  const sent = bmDraft();
  _bmKit.reset_visuals = false;
  try {
    const d = await api("/api/brand/save", { method: "POST", json: { kit: sent } });
    if (seq !== _bmSeq) return;            // a newer save is already on its way
    // Whatever the seller is typing in right now stays exactly as typed; the
    // server's copy of that field is the same text, a few keystrokes behind.
    const a = document.activeElement;
    const typing = a && a.dataset ? a.dataset.edit : "";
    const local = typing ? JSON.parse(JSON.stringify(_bmKit.text)) : null;
    const localName = a && a.id === "bmName" ? _bmKit.name : null;
    _bmKit = d.kit;
    _bmDesc = d.describe;
    if (typing && local) {
      if (typing === "captions") _bmKit.text.captions = local.captions;
      else _bmKit.text[typing] = local[typing];
    }
    if (localName !== null) _bmKit.name = localName;
    bmSaveState("Saved");
    bmRefresh();
  } catch (e) {
    if (seq !== _bmSeq) return;
    bmSaveState("Not saved");
    toast(e.message, 5000);
  }
}

/* Repaint after a save without rebuilding anything the seller is touching. */
function bmRefresh() {
  if (_bmStep === "basics") { bmPaintBasicsPreview(); return; }
  if (_bmStep !== "book") return;
  const book = $("bmBook");
  if (!book) return;
  bmSetVars(book);
  const active = document.activeElement;
  // Only a control the seller is typing into or dragging is protected; a
  // button that merely kept focus after a click is redrawn like the rest.
  const busy = active && /^(TEXTAREA|SELECT)$/.test(active.tagName)
    || (active && active.tagName === "INPUT" && active.type !== "checkbox");
  book.querySelectorAll("[data-sec]").forEach((sec) => {
    if (busy && sec.contains(active)) {
      // Only refresh the parts of this section that are not inputs.
      sec.querySelectorAll("[data-text]").forEach((n) => { n.textContent = bmText(n.dataset.text); });
      return;
    }
    const fn = BM_SECTIONS[sec.dataset.sec];
    if (fn) { sec.innerHTML = fn(); bmWireSection(sec); }
  });
  bmLoadBookFonts();
  bmFitSoon(book);
}

function bmText(key) {
  if (key === "name") return _bmKit.name;
  if (key === "monogram") return (_bmDesc && _bmDesc.monogram) || "";
  return (_bmKit.text || {})[key] || "";
}

/* ======================================================= STEP 1: BASICS === */
function bmBasicsHtml() {
  const k = _bmKit;
  const lib = _bm.library;
  const tooLong = k.name.length > lib.name_max;
  const src = k.name_source && BM_SOURCE[k.name_source];
  const cats = lib.categories.map((c) => `
    <button type="button" class="bm-opt ${k.category === c.id ? "on" : ""}" data-cat="${c.id}" aria-pressed="${k.category === c.id}">
      ${sic(BM_CAT_ICON[c.id] || "tag")}<b>${esc(c.label)}</b></button>`).join("");
  const ages = lib.ages.map((a) => `
    <button type="button" class="bm-chip ${k.age === a.id ? "on" : ""}" data-age="${a.id}" aria-pressed="${k.age === a.id}">
      <b>${esc(a.label)}</b><span>${esc(a.name)}</span></button>`).join("");
  return `
  <div class="bm-grid2">
    <div class="card bm-card">
      <div class="sup-sub">Your shop's name</div>
      <label class="bm-name"><span class="sr-only">Shop name</span>
        <input id="bmName" value="${esc(k.name)}" maxlength="80" autocomplete="organization"
          placeholder="The name your customers know you by" />
        <span class="bm-count ${tooLong ? "bad" : ""}" id="bmNameCount">${k.name.length}/${lib.name_max}</span></label>
      <p class="muted tiny" id="bmNameNote" style="margin:6px 0 0;">${tooLong
        ? `<span class="warn-t">A wordmark reads best at ${lib.name_max} characters or fewer. Shorten it here; your shop keeps its full name until you apply.</span>`
        : src ? esc(src) + " Change it if your customers know you by another name."
        : _bm.has_site ? "" : "No website yet, so type the name you use on Instagram or WhatsApp."}</p>
      <label class="inline-check" style="margin-top:8px;"><input type="checkbox" id="bmKeepCase" ${k.keep_case ? "checked" : ""} />
        Keep my capitalisation exactly as typed</label>

      <div class="sup-sub" style="margin-top:18px;">What do you sell?</div>
      <div class="bm-cats">${cats}</div>

      <div class="sup-sub" style="margin-top:18px;">Who buys from you most?</div>
      <div class="bm-ages">${ages}</div>
      <p class="muted tiny" style="margin:8px 0 0;">We use this to suggest directions that tend to suit these buyers.
        It is a starting point. You can pick any direction.</p>
    </div>
    <div class="bm-preview" id="bmPreview"></div>
  </div>
  <div class="wz-nav"><span></span><span class="muted tiny">Step 1 of 4</span>
    <button class="btn primary" data-bmgo="direction">See directions →</button></div>`;
}

function bmPaintBasicsPreview() {
  const box = $("bmPreview");
  if (!box) return;
  const k = _bmKit;
  const d = bmDir(k.direction);
  const name = k.name || "Your shop";
  if (!d) {
    box.innerHTML = `<div class="bm-preview-empty">
      <span class="bm-preview-name">${esc(name)}</span>
      <p class="muted tiny">Pick what you sell and who buys it. Next you will see your name set in thirteen
        different directions, each one a complete brand.</p></div>`;
    return;
  }
  const colours = k.colours && k.colours.ground ? k.colours : d.palettes[0].colours;
  bmLoadFonts([k.wordmark.font || d.wordmark.font]);
  box.innerHTML = `<div class="bm-preview-card" style="${bmVars({ ...k, wordmark: k.wordmark.font ? k.wordmark : d.wordmark }, colours)}">
    <span class="bm-eyebrow">${esc(d.name)}</span>
    <div class="bm-preview-mark"><span class="bm-wm" data-fit="0.86">${esc(name)}</span></div>
    <span class="bm-eyebrow">${esc((k.text && k.text.tagline) || d.essence)}</span></div>`;
  bmFitSoon(box);
}

function bmWireBasics() {
  bmPaintBasicsPreview();
  const name = $("bmName");
  name.addEventListener("input", () => {
    _bmKit.name = name.value.replace(/\s+/g, " ").replace(/^\s/, "");
    _bmKit.name_source = "typed";
    const max = _bm.library.name_max;
    const cnt = $("bmNameCount");
    cnt.textContent = `${_bmKit.name.length}/${max}`;
    cnt.classList.toggle("bad", _bmKit.name.length > max);
    $("bmNameNote").innerHTML = _bmKit.name.length > max
      ? `<span class="warn-t">A wordmark reads best at ${max} characters or fewer.</span>` : "";
    bmPaintBasicsPreview();
    if (_bmKit.name.trim() && _bmKit.name.length <= max) bmQueue(600);
  });
  $("bmKeepCase").onchange = (e) => { _bmKit.keep_case = e.target.checked; bmPaintBasicsPreview(); bmQueue(); };
  document.querySelectorAll("[data-cat]").forEach((b) => b.onclick = () => {
    _bmKit.category = b.dataset.cat;
    const d = bmDir(_bmKit.direction);
    if (d && !d.categories.includes(_bmKit.category)) _bmKit.direction = "";
    document.querySelectorAll("[data-cat]").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
    bmQueue();
  });
  document.querySelectorAll("[data-age]").forEach((b) => b.onclick = () => {
    _bmKit.age = b.dataset.age;
    document.querySelectorAll("[data-age]").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
    bmQueue();
  });
}

/* ==================================================== STEP 2: DIRECTION === */
function bmRanked() {
  const k = _bmKit;
  const lib = _bm.library;
  const order = lib.order[k.category] || lib.directions.map((d) => d.id);
  return order.map((id, pos) => ({ d: bmDir(id), pos }))
    .filter((r) => r.d && r.d.categories.includes(k.category))
    .map((r) => ({ ...r, fit: k.age && k.age !== "all" ? (r.d.ages[k.age] || 0) : null }))
    .sort((a, b) => ((b.fit || 0) - (a.fit || 0)) || (a.pos - b.pos));
}

function bmAsset(did, key) {
  const a = (_bm.assets || {})[did];
  return a ? a[key] || "" : "";
}

function bmDirectionsHtml() {
  const k = _bmKit;
  const age = _bm.library.ages.find((a) => a.id === k.age) || {};
  const cat = _bm.library.categories.find((c) => c.id === k.category) || {};
  const name = k.name || "Your shop";
  const cards = bmRanked().map(({ d, fit }) => {
    const pal = d.palettes[0];
    const kit = { ...k, wordmark: d.wordmark, fonts: d.fonts, keep_case: k.keep_case };
    const hero = bmAsset(d.id, "hero");
    return `
    <button type="button" class="bm-dcard ${k.direction === d.id ? "on" : ""}" data-dir="${d.id}"
      aria-pressed="${k.direction === d.id}" style="${bmVars(kit, pal.colours)}">
      <div class="bm-dart ${hero ? "has-img" : ""}" ${hero ? `style="background-image:url('${esc(hero)}')"` : ""}>
        <span class="bm-mood">${d.mood.map(esc).join(" · ")}</span>
        <span class="bm-wm" data-fit="0.84">${esc(name)}</span>
        <span class="bm-ess">${esc(d.essence)}</span>
      </div>
      <div class="bm-dfoot">
        <div class="bm-sw">${["ground", "surface", "ink", "accent", "support"].map((r) => `<i style="background:${pal.colours[r]}"></i>`).join("")}</div>
        <div class="bm-dname"><b>${esc(d.name)}</b>${fit === 3 && age.label ? `<span class="bm-badge">Suggested for ${esc(age.label)}</span>` : ""}</div>
        <span class="muted tiny">In the spirit of ${d.spirit.map(esc).join(", ")}</span>
      </div>
    </button>`;
  }).join("");
  return `
    <div class="bm-dhead">
      <div><h3 style="margin:0 0 2px;">Directions for ${esc((cat.label || "").toLowerCase())}${age.id && age.id !== "all" ? `, buyers aged ${esc(age.label)}` : ""}</h3>
      <p class="muted tiny" style="margin:0;">Each one is a complete brand: how your name is set, the colours, the type and the voice.
        "Suggested" means it tends to suit these buyers. It is a judgement, not a rule.</p></div>
    </div>
    <div class="bm-dgrid">${cards}</div>
    <div class="wz-nav"><button class="btn ghost" data-bmgo="basics">← Your brand</button>
      <span class="muted tiny">Step 2 of 4</span>
      <button class="btn primary" data-bmgo="book" ${k.direction ? "" : "disabled"}>Open brand book →</button></div>`;
}

function bmWireDirections() {
  const name = _bmKit.name || "Your shop";
  bmRanked().forEach(({ d }) => bmLoadFonts([d.wordmark.font], { text: name, weight: d.wordmark.weight }));
  bmFitSoon($("bmBody"));
  document.querySelectorAll("[data-dir]").forEach((b) => b.onclick = async () => {
    const id = b.dataset.dir;
    const k = _bmKit;
    if (k.direction && k.direction !== id && (k.edited.colours || k.edited.fonts || k.edited.wordmark)) {
      const keep = await bmConfirm("Keep your custom colours and fonts?",
        "You changed the colours or type in your brand book. Keep them with the new direction, or use the new direction's own?",
        "Use the new direction's", "Keep mine");
      k.reset_visuals = keep === "a";
    }
    k.direction = id;
    clearTimeout(_bmSaveT);
    bmSaveState("Saving…");
    await bmSave();
    bmGo("book");
  });
}

/* Two-choice confirm in the app's own modal. Resolves "a", "b" or null. */
function bmConfirm(title, text, a, b) {
  return new Promise((resolve) => {
    openModal(title, `<p style="margin-top:0;">${esc(text)}</p>
      <div class="modal-actions"><button class="btn ghost" data-c="b">${esc(b)}</button>
      <button class="btn primary" data-c="a">${esc(a)}</button></div>`);
    let done = false;
    document.querySelectorAll(".modal [data-c]").forEach((x) => x.onclick = () => { done = true; closeModal(); resolve(x.dataset.c); });
    const back = document.querySelector(".modal-back");
    const obs = new MutationObserver(() => { if (!document.body.contains(back)) { obs.disconnect(); if (!done) resolve(null); } });
    obs.observe(document.body, { childList: true });
  });
}

/* =================================================== STEP 3: BRAND BOOK === */
const BM_TOC = [
  ["cover", "Cover"], ["words", "Words"], ["logo", "Logo"], ["colour", "Colours"],
  ["type", "Type"], ["voice", "Voice"], ["photo", "Photography"], ["use", "In use"],
];

function bmLoadBookFonts() {
  const k = _bmKit;
  bmLoadFonts([k.wordmark.font, k.fonts.heading, k.fonts.body, k.fonts.accent]);
}

function bmBookHtml() {
  const d = bmDir(_bmKit.direction);
  return `
  <div class="bm-book-wrap">
    <nav class="bm-toc" aria-label="Brand book sections">
      ${BM_TOC.map(([id, l]) => `<a href="#bm-${id}" data-toc="${id}">${esc(l)}</a>`).join("")}
      <button class="btn ghost sm" data-bmgo="direction" style="margin-top:10px;">Change direction</button>
    </nav>
    <div class="bm-book" id="bmBook" style="${bmVars(_bmKit)}">
      ${Object.keys(BM_SECTIONS).map((id) => `<section class="bm-sec" id="bm-${id}" data-sec="${id}">${BM_SECTIONS[id]()}</section>`).join("")}
    </div>
  </div>
  <div class="wz-nav"><button class="btn ghost" data-bmgo="direction">← ${esc(d ? d.name : "Direction")}</button>
    <span class="muted tiny">Step 3 of 4</span>
    <button class="btn primary" data-bmgo="apply">Apply to website and posts →</button></div>`;
}

function bmSecHead(title, sub, extra = "") {
  return `<div class="bm-sec-h"><div><h3>${esc(title)}</h3>${sub ? `<p class="muted tiny">${sub}</p>` : ""}</div>${extra}</div>`;
}

function bmFrameHtml(cls = "") {
  const frame = _bmKit.frame || "none";
  return `<span class="bm-mono bm-frame-${frame} ${cls}" data-text="monogram">${esc(bmText("monogram"))}</span>`;
}

function bmPaletteChips() {
  const d = bmDir(_bmKit.direction);
  if (!d) return "";
  const chips = d.palettes.map((p) => `
    <button type="button" class="bm-pchip ${_bmKit.palette === p.id ? "on" : ""}" data-palette="${p.id}" aria-pressed="${_bmKit.palette === p.id}">
      <span class="bm-pdots">${["ground", "ink", "accent"].map((r) => `<i style="background:${p.colours[r]}"></i>`).join("")}</span>${esc(p.name)}</button>`).join("");
  return chips + (_bmKit.palette === "custom" ? `<span class="bm-pchip on" aria-current="true"><span class="bm-pdots">${["ground", "ink", "accent"].map((r) => `<i style="background:${_bmKit.colours[r]}"></i>`).join("")}</span>Custom</span>` : "");
}

const BM_SECTIONS = {
  cover() {
    const d = bmDir(_bmKit.direction);
    const latin = !_bmDesc || _bmDesc.latin;
    return `
    <div class="bm-cover">
      <div class="bm-cover-top"><span class="bm-eyebrow">Brand book</span><span class="bm-eyebrow">${esc(d ? d.name : "")}</span></div>
      <div class="bm-cover-mark"><span class="bm-wm" data-fit="0.9" data-text="name">${esc(_bmKit.name)}</span></div>
      <div class="bm-cover-foot">
        <p class="bm-cover-tag" data-text="tagline">${esc(_bmKit.text.tagline)}</p>
        ${bmFrameHtml("bm-cover-mono")}
      </div>
    </div>
    <div class="bm-palette-row">${bmPaletteChips()}</div>
    ${latin ? "" : `<p class="muted tiny warn-t">These fonts cover Latin letters only, so your name shows in a system font. Add a Latin spelling for the wordmark if you have one.</p>`}`;
  },

  words() {
    const t = _bmKit.text;
    const ed = _bmKit.edited || {};
    const stale = new Set(_bmKit.stale || []);
    const counts = (_bmDesc && _bmDesc.variant_counts) || {};
    const field = (key, label, hint, cls = "", rows = 2) => `
      <div class="bm-field ${stale.has(key) ? "stale" : ""}">
        <div class="bm-field-h"><b>${esc(label)}</b>
          <span class="bm-field-acts">
            ${counts[key] > 1 ? `<button type="button" class="btn ghost xs" data-another="${key}">${sic("refresh")}Show another</button>` : ""}
            ${ed[key] ? `<button type="button" class="btn ghost xs" data-reset="${key}">${sic("undo")}Use suggested</button>` : ""}
          </span></div>
        <textarea class="bm-ta ${cls}" data-edit="${key}" rows="${rows}" aria-label="${esc(label)}">${esc(t[key] || "")}</textarea>
        <small class="muted tiny">${stale.has(key) ? `<span class="warn-t">This still uses your old name. Update it before you apply.</span>` : hint}${key === "bio" ? ` <span class="bm-count" data-count="bio">${(t.bio || "").length}/150</span>` : ""}</small>
      </div>`;
    const caps = (t.captions || []).map((c, i) => `
      <textarea class="bm-ta bm-ta-cap" data-edit="captions" data-i="${i}" rows="2" aria-label="Caption ${i + 1}">${esc(c)}</textarea>`).join("");
    return bmSecHead("Words", "Written in your direction's voice with your name in it. Change anything; what you write is kept, and the rest follows your name and direction.")
      + `<div class="bm-fields">
        ${field("tagline", "Tagline", "Under your name on your website, in your bio and on packaging.", "bm-ta-head", 1)}
        ${field("statement", "Brand statement", "Who you are, in three sentences. It guides every post the app writes for you.", "bm-ta-head", 3)}
        ${field("promise", "Promise", "One line about your attitude. Never a delivery or returns promise.", "", 1)}
        ${field("bio", "Instagram bio", "Paste this into your Instagram profile.", "", 2)}
        ${field("about", "About us", "The story on your website. Add your own facts: what you make, how, and where.", "", 5)}
        <div class="bm-field ${stale.has("captions") ? "stale" : ""}">
          <div class="bm-field-h"><b>Caption starters</b><span class="bm-field-acts">
            ${counts.captions > 1 ? `<button type="button" class="btn ghost xs" data-another="captions">${sic("refresh")}Show another set</button>` : ""}
            ${ed.captions ? `<button type="button" class="btn ghost xs" data-reset="captions">${sic("undo")}Use suggested</button>` : ""}</span></div>
          <div class="bm-caps">${caps}</div>
          <small class="muted tiny">Opening lines in your voice. The Social Media Manager writes the rest in the same voice.</small>
        </div>
      </div>`;
  },

  logo() {
    const k = _bmKit;
    const wm = k.wordmark;
    const lib = _bm.library;
    const opts = lib.wordmark_fonts.map((id) => `<option value="${id}" ${wm.font === id ? "selected" : ""}>${esc((bmFontRow(id) || {}).label || id)}</option>`).join("");
    const tile = (cls, label) => `<div class="bm-ltile ${cls}"><span class="bm-wm" data-fit="0.82" data-text="name">${esc(k.name)}</span><span class="bm-ltile-l">${esc(label)}</span></div>`;
    return bmSecHead("Logo", "Your name, set in type. This is how H&M, Zara and Gucci do it: a wordmark, not a picture. It stays sharp at every size.",
      k.edited.wordmark ? `<button type="button" class="btn ghost xs" data-resetvis="wordmark">${sic("undo")}Use the direction's</button>` : "")
      + `<div class="bm-ltiles">
          ${tile("on-ground", "On your background")}
          ${tile("on-ink", "Reversed")}
          ${tile("on-accent", "On your accent")}
          <div class="bm-ltile on-surface">${bmFrameHtml("bm-mono-lg")}<span class="bm-ltile-l">Monogram, for small spaces</span></div>
        </div>
        <div class="bm-controls">
          <label>Face<select data-wm="font">${opts}</select></label>
          <label>Capitals<select data-wm="case">
            <option value="upper" ${wm.case === "upper" ? "selected" : ""}>ALL CAPITALS</option>
            <option value="none" ${wm.case === "none" ? "selected" : ""}>As written</option>
            <option value="lower" ${wm.case === "lower" ? "selected" : ""}>all lowercase</option></select></label>
          <label>Letter spacing<input type="range" data-wm="track" min="-0.05" max="0.4" step="0.01" value="${wm.track}" /></label>
          <label>Weight<select data-wm="weight">${[300, 400, 500, 600, 700, 800].map((w) => `<option ${+wm.weight === w ? "selected" : ""}>${w}</option>`).join("")}</select></label>
          <label>Monogram frame<select data-frame>${lib.frames.map((f) => `<option value="${f}" ${k.frame === f ? "selected" : ""}>${esc({ none: "None", circle: "Circle line", square: "Square line", "circle-solid": "Solid circle", "square-solid": "Solid square" }[f])}</option>`).join("")}</select></label>
        </div>
        <div class="bm-dl">
          <span class="muted tiny">Download your logo (transparent PNG):</span>
          <button type="button" class="btn ghost sm" data-logo="ink" data-w="3000">${sic("download")}Dark, 3000 px</button>
          <button type="button" class="btn ghost sm" data-logo="reversed" data-w="3000">${sic("download")}Light, 3000 px</button>
          <button type="button" class="btn ghost sm" data-logo="ink" data-w="1000">${sic("download")}Dark, 1000 px</button>
          <span class="muted tiny">3000 px prints sharp on labels up to about 25 cm wide.</span>
        </div>`;
  },

  colour() {
    const k = _bmKit;
    const rep = (_bmDesc && _bmDesc.contrast) || [];
    const sw = BM_ROLES.map(([r, label]) => `
      <label class="bm-swatch">
        <span class="bm-swatch-c" style="background:${k.colours[r]}"><input type="color" data-colour="${r}" value="${k.colours[r]}" aria-label="${esc(label)} colour" /></span>
        <b>${esc(label)}</b><code>${esc(k.colours[r])}</code></label>`).join("");
    return bmSecHead("Colours", "Five colours, each with one job. Click a colour to change it; we check that text stays readable.",
      k.palette === "custom" ? `<button type="button" class="btn ghost xs" data-resetvis="colours">${sic("undo")}Use a palette</button>` : "")
      + `<div class="bm-palette-row">${bmPaletteChips()}</div>
        <div class="bm-swatches">${sw}</div>
        <ul class="bm-checks">${rep.map((r) => `<li class="${r.ok ? "ok" : "warn"}">${sic(r.ok ? "check" : "close")}<span>${esc(r.label)}: ${r.ratio}:1 ${r.ok ? "" : `(needs ${r.need}:1)`}</span></li>`).join("")}</ul>
        ${(_bmDesc && _bmDesc.blocking && _bmDesc.blocking.length) ? `<p class="warn-t tiny">Your text is too faint on your background to read. Pick darker text or a lighter background before you apply.</p>` : ""}`;
  },

  type() {
    const k = _bmKit;
    const fonts = _bm.fonts || [];
    const kinds = [["serif", "Serif"], ["grotesk", "Sans serif"], ["display", "Display"], ["mono", "Mono"]];
    const sel = (role) => `<select data-font="${role}">${kinds.map(([kind, kl]) => `<optgroup label="${kl}">${fonts.filter((f) => f.kind === kind).map((f) => `<option value="${f.id}" ${k.fonts[role] === f.id ? "selected" : ""}>${esc(f.label)}</option>`).join("")}</optgroup>`).join("")}</select>`;
    const fl = (id) => esc((bmFontRow(id) || {}).label || id);
    return bmSecHead("Type", "Three faces with three jobs. The same ones go on your website when you apply.",
      k.edited.fonts ? `<button type="button" class="btn ghost xs" data-resetvis="fonts">${sic("undo")}Use the direction's</button>` : "")
      + `<div class="bm-type">
          <div class="bm-spec"><span class="bm-spec-l">Headings · ${fl(k.fonts.heading)}</span>
            <div class="bm-spec-big" style="font-family:var(--b-head)">Aa</div>
            <p class="bm-spec-head" data-text="tagline">${esc(k.text.tagline)}</p>${sel("heading")}</div>
          <div class="bm-spec"><span class="bm-spec-l">Body · ${fl(k.fonts.body)}</span>
            <p class="bm-spec-body" data-text="statement">${esc(k.text.statement)}</p>${sel("body")}</div>
          <div class="bm-spec"><span class="bm-spec-l">Small caps · ${fl(k.fonts.accent)}</span>
            <p class="bm-spec-acc">New in · Shop all · About · Contact</p>${sel("accent")}</div>
        </div>`;
  },

  voice() {
    const v = (_bmDesc && _bmDesc.voice) || {};
    const list = (arr) => (arr || []).map((s) => `<li>${esc(s)}</li>`).join("");
    const chips = (arr, cls) => (arr || []).map((s) => `<span class="bm-word ${cls}">${esc(s)}</span>`).join("");
    return bmSecHead("Voice", "How your brand sounds. The post writer follows these rules once you apply.")
      + `<div class="bm-traits">${(v.traits || []).map((t) => `<span>${esc(t)}</span>`).join("")}</div>
        <div class="bm-voice">
          <div><b>We say it like this</b><ul>${list(v.say)}</ul><div class="bm-words">${chips(v.use, "use")}</div></div>
          <div><b>We never</b><ul>${list(v.never)}</ul><div class="bm-words">${chips(v.avoid, "avoid")}</div></div>
        </div>
        ${_bmDesc && _bmDesc.age_note ? `<p class="bm-age-note">${sic("user")}${esc(_bmDesc.age_note)}</p>` : ""}`;
  },

  photo() {
    const k = _bmKit;
    const did = k.direction;
    const usePhotos = bmPhotosAllowed();
    const mood = usePhotos ? bmAsset(did, `mood-${k.category}`) : "";
    const pack = usePhotos ? bmAsset(did, "packaging") : "";
    const tiles = [mood, pack].filter(Boolean).map((u) => `<div class="bm-mood-img" style="background-image:url('${esc(u)}')"></div>`).join("")
      || `<div class="bm-mood-art a"></div><div class="bm-mood-art b"></div><div class="bm-mood-art c"></div>`;
    return bmSecHead("Photography", "Rules for every product photo and post. Product Studio follows your own photos first; these keep everything else consistent.")
      + `<div class="bm-photo"><ol class="bm-rules">${((_bmDesc && _bmDesc.imagery) || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
        <div class="bm-moods">${tiles}</div></div>
        ${usePhotos && (mood || pack) ? `<p class="muted tiny">Example images are shared backgrounds for this direction, not your own photos.</p>` : ""}`;
  },

  use() {
    return bmSecHead("In use", "Your brand on the things buyers actually see. Packaging is a guide for your printer; printable files come later.")
      + bmMockupsHtml();
  },
};

/* Shared direction images are made in the direction's FIRST palette. Shown
   only while that palette is untouched; otherwise the palette-built
   backgrounds take over so nothing clashes with the seller's colours. */
function bmPhotosAllowed() {
  const d = bmDir(_bmKit.direction);
  return !!d && _bmKit.palette === d.palettes[0].id;
}

function bmMockupsHtml() {
  const k = _bmKit;
  const t = k.text;
  const photos = _bm.photos || [];
  const allow = bmPhotosAllowed();
  const postBg = allow ? bmAsset(k.direction, "post-bg") : "";
  const storyBg = allow ? bmAsset(k.direction, "story-bg") : "";
  const pattern = bmAsset(k.direction, "pattern");
  const product = (i, cls) => photos[i]
    ? `<div class="bm-post ${cls}" style="background-image:url('${esc(photos[i])}')"><span class="bm-wm bm-post-mark">${esc(k.name)}</span></div>`
    : `<div class="bm-post ${cls} bm-still"><i></i><i></i><span class="bm-wm bm-post-mark">${esc(k.name)}</span></div>`;
  const cap = (i) => esc((t.captions || [])[i] || t.tagline);
  const grid = [
    product(0, ""),
    `<div class="bm-post on-accent"><span class="bm-post-q">${esc(t.tagline)}</span><span class="bm-wm bm-post-sig">${esc(k.name)}</span></div>`,
    `<div class="bm-post on-surface ${postBg ? "has-img" : ""}" ${postBg ? `style="background-image:url('${esc(postBg)}')"` : ""}><span class="bm-post-band"><span class="bm-eyebrow">New in</span><span class="bm-post-h">${cap(0)}</span></span></div>`,
    `<div class="bm-post on-ink"><span class="bm-wm" data-fit="0.8">${esc(k.name)}</span></div>`,
    product(1, ""),
    `<div class="bm-post on-ground bm-patterned" ${pattern ? `style="--b-pattern:url('${esc(pattern)}')"` : ""}><span class="bm-post-h">${cap(2)}</span></div>`,
  ].join("");
  return `
  <div class="bm-use">
    <div class="bm-ig">
      <div class="bm-ig-head">
        <span class="bm-ig-av">${esc(bmText("monogram"))}</span>
        <div><b>${esc(k.name)}</b><p data-text="bio">${esc(t.bio)}</p></div>
        <span class="bm-ig-follow">Follow</span>
      </div>
      <div class="bm-ig-grid">${grid}</div>
    </div>
    <div class="bm-story ${storyBg ? "has-img" : ""}" ${storyBg ? `style="background-image:url('${esc(storyBg)}')"` : ""}>
      <span class="bm-wm bm-story-mark" data-fit="0.8">${esc(k.name)}</span>
      <span class="bm-story-band"><span class="bm-eyebrow">New in</span><span class="bm-post-h">${cap(1)}</span>
      <span class="bm-story-btn">Shop now</span></span>
    </div>
    <div class="bm-pack">
      <div class="bm-box bm-patterned" ${pattern ? `style="--b-pattern:url('${esc(pattern)}')"` : ""}><div class="bm-box-lid"><span class="bm-wm" data-fit="0.7">${esc(k.name)}</span></div></div>
      <div class="bm-tag"><span class="bm-tag-hole"></span>${bmFrameHtml("bm-mono-tag")}<span class="bm-tag-line">${esc(t.tagline)}</span></div>
      <div class="bm-ty"><span class="bm-ty-h">Thank you</span><p>${esc(t.promise)}</p><span class="bm-wm bm-ty-mark">${esc(k.name)}</span></div>
    </div>
  </div>`;
}

function bmWireBook() {
  bmLoadBookFonts();
  const book = $("bmBook");
  book.querySelectorAll("[data-sec]").forEach(bmWireSection);
  document.querySelectorAll("[data-toc]").forEach((a) => a.onclick = (e) => {
    e.preventDefault();
    const el = $("bm-" + a.dataset.toc);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  bmFitSoon(book);
}

function bmWireSection(sec) {
  const k = _bmKit;
  sec.querySelectorAll("textarea[data-edit]").forEach((ta) => {
    ta.addEventListener("input", () => {
      const key = ta.dataset.edit;
      if (key === "captions") {
        const caps = [...(k.text.captions || [])];
        caps[+ta.dataset.i] = ta.value;
        k.text.captions = caps;
      } else {
        k.text[key] = ta.value;
        const cnt = sec.querySelector(`[data-count="${key}"]`);
        if (cnt) { cnt.textContent = `${ta.value.length}/150`; cnt.classList.toggle("bad", ta.value.length > 150); }
      }
      k.edited = { ...k.edited, [key]: true };
      // Mirror into the brand-styled previews on this page right away.
      document.querySelectorAll(`#bmBook [data-text="${key}"]`).forEach((n) => { if (n !== ta) n.textContent = ta.value; });
      bmQueue(700);
    });
    // Once they stop typing, redraw the section so "Use suggested" appears.
    ta.addEventListener("blur", () => setTimeout(() => {
      if (!sec.contains(document.activeElement)) bmRefresh();
    }, 0));
  });
  sec.querySelectorAll("[data-another]").forEach((b) => b.onclick = () => {
    const key = b.dataset.another;
    const n = ((_bmDesc && _bmDesc.variant_counts) || {})[key] || 1;
    const cur = typeof k.variants[key] === "number" ? k.variants[key] : -1;
    k.variants = { ...k.variants, [key]: (cur + 1 + n) % n };
    k.edited = { ...k.edited, [key]: false };
    bmQueue(0);
  });
  sec.querySelectorAll("[data-reset]").forEach((b) => b.onclick = () => {
    k.edited = { ...k.edited, [b.dataset.reset]: false };
    bmQueue(0);
  });
  sec.querySelectorAll("[data-palette]").forEach((b) => b.onclick = () => {
    k.palette = b.dataset.palette;
    k.edited = { ...k.edited, colours: false };
    const d = bmDir(k.direction);
    const p = d && d.palettes.find((x) => x.id === k.palette);
    if (p) { k.colours = { ...p.colours }; bmSetVars($("bmBook")); }
    bmQueue(0);
  });
  sec.querySelectorAll("[data-colour]").forEach((inp) => {
    inp.addEventListener("input", () => {
      k.colours = { ...k.colours, [inp.dataset.colour]: inp.value.toUpperCase() };
      k.edited = { ...k.edited, colours: true };
      k.palette = "custom";
      inp.parentElement.style.background = inp.value;
      const code = inp.closest(".bm-swatch").querySelector("code");
      if (code) code.textContent = inp.value.toUpperCase();
      bmSetVars($("bmBook"));
      bmQueue(500);
    });
  });
  sec.querySelectorAll("[data-resetvis]").forEach((b) => b.onclick = () => {
    const what = b.dataset.resetvis;
    k.edited = { ...k.edited, [what]: false };
    if (what === "colours") { const d = bmDir(k.direction); k.palette = d ? d.palettes[0].id : ""; }
    bmQueue(0);
  });
  sec.querySelectorAll("[data-font]").forEach((s) => s.onchange = () => {
    k.fonts = { ...k.fonts, [s.dataset.font]: s.value };
    k.edited = { ...k.edited, fonts: true };
    bmLoadFonts([s.value]);
    bmSetVars($("bmBook"));
    bmQueue(0);
  });
  sec.querySelectorAll("[data-wm]").forEach((s) => {
    const ev = s.type === "range" ? "input" : "change";
    s.addEventListener(ev, () => {
      const v = s.dataset.wm === "track" ? parseFloat(s.value) : s.dataset.wm === "weight" ? parseInt(s.value, 10) : s.value;
      k.wordmark = { ...k.wordmark, [s.dataset.wm]: v };
      k.edited = { ...k.edited, wordmark: true };
      if (s.dataset.wm === "font") bmLoadFonts([v]);
      bmSetVars($("bmBook"));
      bmFitSoon($("bmBook"));
      bmQueue(s.type === "range" ? 450 : 0);
    });
  });
  sec.querySelectorAll("[data-frame]").forEach((s) => s.onchange = () => {
    k.frame = s.value;
    document.querySelectorAll("#bmBook .bm-mono").forEach((m) => { m.className = m.className.replace(/bm-frame-[a-z-]+/, "bm-frame-" + s.value); });
    bmQueue(0);
  });
  sec.querySelectorAll("[data-logo]").forEach((b) => b.onclick = () => bmExportLogo(b.dataset.logo, +b.dataset.w));
}

/* -------------------------------------------------------- logo export -- */
/* Drawn glyph by glyph with the same face, weight, case and letter spacing
   as the screen. Canvas letterSpacing is missing in older Safari, so the
   spacing is placed by hand from prefix widths (which keep kerning). */
async function bmExportLogo(variant, width) {
  const k = _bmKit;
  const wm = k.wordmark;
  const fam = bmFamily(wm.font);
  try { await document.fonts.load(`${wm.weight} 200px "${fam}"`); } catch (e) { /* draw with what we have */ }
  const text = bmCased(k.name, wm, k.keep_case);
  const fs = 400;
  const probe = document.createElement("canvas").getContext("2d");
  probe.font = `${wm.weight} ${fs}px "${fam}", sans-serif`;
  const chars = [...text];
  const track = (wm.track || 0) * fs;
  const xs = chars.map((_, i) => probe.measureText(chars.slice(0, i).join("")).width + track * i);
  const total = probe.measureText(text).width + track * (chars.length - 1);
  const pad = fs * 0.2;
  const scale = width / (total + pad * 2);
  const c = document.createElement("canvas");
  c.width = Math.round(width);
  c.height = Math.round((fs * 1.35 + pad * 2) * scale);
  const ctx = c.getContext("2d");
  ctx.scale(scale, scale);
  ctx.font = probe.font;
  ctx.textBaseline = "middle";
  ctx.fillStyle = variant === "reversed" ? k.colours.ground : k.colours.ink;
  const y = (c.height / scale) / 2;
  chars.forEach((ch, i) => ctx.fillText(ch, pad + xs[i], y));
  c.toBlob((blob) => {
    if (!blob) { toast("Could not make the image in this browser."); return; }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${(k.name || "logo").replace(/[^\w-]+/g, "-").toLowerCase()}-logo-${variant === "reversed" ? "light" : "dark"}-${width}px.png`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }, "image/png");
}

/* ========================================================= STEP 4: APPLY === */
async function bmLoadPlan(keepOpts) {
  if (!keepOpts) _bmPlanOpts = {};
  const body = $("bmBody");
  try {
    _bmPlan = await api("/api/brand/plan", { method: "POST", json: { kit: bmDraft(), options: _bmPlanOpts } });
  } catch (e) {
    body.innerHTML = `<div class="card"><p class="warn-t">${esc(e.message)}</p>
      <button class="btn ghost" data-bmgo="book">← Back to the brand book</button></div>`;
    body.querySelectorAll("[data-bmgo]").forEach((b) => b.onclick = () => bmGo(b.dataset.bmgo));
    return;
  }
  body.innerHTML = bmApplyHtml();
  bmWireApply();
}

function bmRowHtml(r) {
  const show = (v) => {
    if (v === null || v === undefined || v === "") return `<i class="muted">empty</i>`;
    if (/^#[0-9A-F]{6}$/i.test(String(v))) return `<span class="bm-hex"><i style="background:${v}"></i>${esc(v)}</span>`;
    const f = bmFontRow(String(v));
    if (f) return esc(f.label);
    const s = String(v);
    return esc(s.length > 90 ? s.slice(0, 88) + "…" : s);
  };
  return `<label class="bm-row ${r.drift ? "drift" : ""}">
    <input type="checkbox" data-row="${esc(r.path)}" ${r.default ? "checked" : ""} />
    <span class="bm-row-l"><b>${esc(r.label)}</b>
      ${r.drift ? `<span class="bm-flag">Changed since you last applied. Kept unless you tick it.</span>`
        : !r.default ? `<span class="bm-flag">Your own words. Kept unless you tick it.</span>` : ""}</span>
    <span class="bm-row-v"><span class="bm-before">${show(r.before)}</span><span class="bm-arrow">→</span><span>${show(r.after)}</span></span>
  </label>`;
}

function bmSitePreviewHtml() {
  const p = _bmPlan;
  const th = (_bm.themes || []).find((t) => t.id === p.theme.after);
  if (!th) return "";
  const acc = (p.preview && p.preview.accent) || th.light.accent;
  const caseCss = th.case === "upper" ? "uppercase" : "none";
  return `<div class="bm-site" style="background:${th.light.bg};color:${th.light.ink}">
      <span class="bm-site-brand" style="font-family:${bmStack(_bmKit.fonts.heading)};text-transform:${caseCss}">${esc(_bmKit.name)}</span>
      <span class="bm-site-nav" style="font-family:${bmStack(_bmKit.fonts.accent)}">Shop · About · Contact</span>
      <span class="bm-site-btn" style="background:${acc};color:${th.light.accent_ink}">Shop now</span>
    </div>
    <p class="muted tiny" style="margin:6px 0 0;">Your website after Apply, on the ${esc(th.label)} layout. The layout keeps its own background and text colours;
      your fonts and accent colour change.${th.case === "upper" ? " This layout sets headings in capitals." : ""}</p>`;
}

function bmApplyHtml() {
  const p = _bmPlan;
  const site = p.rows.filter((r) => r.path.startsWith("site."));
  const stu = p.rows.filter((r) => r.path.startsWith("studio."));
  const blocked = (p.blocked || []).map((b) => `<p class="warn-t">${esc(b)}</p>`).join("");
  const themeLabel = p.theme && p.theme.label;
  return `
  ${blocked ? `<div class="card bm-blocked">${blocked}<button class="btn ghost sm" data-bmgo="book">Fix it in the brand book</button></div>` : ""}
  <div class="bm-apply">
    <div class="card">
      <div class="bm-sec-h"><div><h3>Your website</h3>
        <p class="muted tiny">${p.has_site ? (p.published ? "Your shop is live. These changes show to shoppers as soon as you apply." : "Your website is a draft. Nothing here is public until you publish.") : ""}</p></div></div>
      ${p.has_site ? `
        ${bmSitePreviewHtml()}
        <label class="inline-check" style="margin-top:12px;"><input type="checkbox" id="bmSwitch" ${p.theme.switch ? "checked" : ""} />
          Use the ${esc(themeLabel || "")} layout for this direction${p.theme.current === p.theme.after && p.theme.switch ? " (you already use it)" : ""}</label>
        ${p.has_logo ? `<label class="inline-check"><input type="checkbox" id="bmClearLogo" ${_bmPlanOpts.clear_logo ? "checked" : ""} />
          Remove my uploaded logo image, so the site shows my name in the brand face</label>` : ""}
        <div class="bm-rows">${site.length ? site.map(bmRowHtml).join("") : `<p class="muted tiny">Your website already matches.</p>`}</div>`
      : `<p>You do not have a One Tap website yet, so Apply updates your posts only.
          If you sell on Shopify, Etsy or another store, copy your brand sheet below into it.</p>
        <button class="btn ghost sm" onclick="openModule('site')">${sic("globe")}Build a website</button>`}
    </div>
    <div class="card">
      <div class="bm-sec-h"><div><h3>Your posts</h3>
        <p class="muted tiny">Product Studio and the Social Media Manager write and design from these.${p.aesthetic_kept ? " Your photo look, read from your own pictures, stays in charge of how images look." : ""}</p></div></div>
      <div class="bm-rows">${stu.length ? stu.map(bmRowHtml).join("") : `<p class="muted tiny">Your posts already follow this brand.</p>`}</div>
    </div>
  </div>
  <div class="wz-nav"><button class="btn ghost" data-bmgo="book">← Brand book</button>
    <span>${_bm.undo ? `<button class="btn ghost" id="bmUndo">${sic("undo")}Undo last apply</button>` : `<span class="muted tiny">Step 4 of 4</span>`}</span>
    <button class="btn primary" id="bmApply" ${blocked || !p.rows.length ? "disabled" : ""}>Apply ticked changes</button></div>
  ${bmSheetHtml()}`;
}

function bmWireApply() {
  const body = $("bmBody");
  body.querySelectorAll("[data-bmgo]").forEach((b) => b.onclick = () => bmGo(b.dataset.bmgo));
  const sw = $("bmSwitch");
  if (sw) sw.onchange = () => { _bmPlanOpts.switch_theme = sw.checked; bmLoadPlan(true); };
  const cl = $("bmClearLogo");
  if (cl) cl.onchange = () => { _bmPlanOpts.clear_logo = cl.checked; bmLoadPlan(true); };
  const ap = $("bmApply");
  if (ap) ap.onclick = () => bmDoApply(false);
  const un = $("bmUndo");
  if (un) un.onclick = bmUndoFlow;
  const cp = $("bmSheetCopy");
  if (cp) cp.onclick = async () => {
    try { await navigator.clipboard.writeText(bmSheetText()); toast("Brand sheet copied"); }
    catch (e) { toast("Select the text and copy it."); }
  };
  const dl = $("bmSheetDl");
  if (dl) dl.onclick = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([bmSheetText()], { type: "text/plain" }));
    a.download = `${(_bmKit.name || "brand").replace(/[^\w-]+/g, "-").toLowerCase()}-brand-sheet.txt`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
}

function bmTicks(scope) {
  const out = {};
  (scope || $("bmBody")).querySelectorAll("[data-row]").forEach((c) => { out[c.dataset.row] = c.checked; });
  return out;
}

async function bmDoApply(confirmLive) {
  const btn = $("bmApply");
  if (btn) { btn.disabled = true; btn.textContent = "Applying…"; }
  try {
    const d = await api("/api/brand/apply", { method: "POST", json: {
      kit: bmDraft(), options: { ..._bmPlanOpts, fields: bmTicks(), confirm_live: confirmLive } } });
    _bmKit = d.kit; _bmDesc = d.describe; _bm.undo = d.undo;
    toast(d.applied.length ? `Applied ${d.applied.length} change${d.applied.length === 1 ? "" : "s"}. Undo is here if you change your mind.`
      : "Nothing needed changing.", 6000);
    bmLoadPlan(true);
  } catch (e) {
    if (e.status === 409) {
      const go = await bmConfirm("Update your live shop?", e.message, "Update my live shop", "Not now");
      if (go === "a") return bmDoApply(true);
    } else toast(e.message, 6000);
    if (btn) { btn.disabled = false; btn.textContent = "Apply ticked changes"; }
  }
}

async function bmUndoFlow(confirmLive) {
  let plan;
  try { plan = await api("/api/brand/undo"); } catch (e) { toast(e.message); return; }
  if (!plan.rows.length) { toast("There is nothing to undo."); return; }
  if (confirmLive !== true) {
    openModal("Undo the last apply?", `
      <p class="muted tiny" style="margin-top:0;">This puts back what was there before you applied.
        Anything you changed yourself since then is left alone unless you tick it.</p>
      <div class="bm-rows">${plan.rows.map((r) => bmRowHtml({ ...r, before: r.now, after: r.before })).join("")}</div>
      <div class="modal-actions"><button class="btn ghost" data-mclose2>Cancel</button>
        <button class="btn primary" id="bmUndoGo">Undo</button></div>`, { wide: true });
    document.querySelector("[data-mclose2]").onclick = closeModal;
    $("bmUndoGo").onclick = () => { const ticks = bmTicks(document.querySelector(".modal")); closeModal(); bmUndoRun(ticks, false); };
  }
}

async function bmUndoRun(ticks, confirmLive) {
  try {
    const d = await api("/api/brand/undo", { method: "POST", json: { options: { fields: ticks, confirm_live: confirmLive } } });
    _bmKit = d.kit; _bmDesc = d.describe; _bm.undo = false;
    toast(`Put back ${d.restored.length} thing${d.restored.length === 1 ? "" : "s"}.`, 5000);
    bmLoadPlan(true);
  } catch (e) {
    if (e.status === 409) {
      const go = await bmConfirm("Update your live shop?", e.message, "Update my live shop", "Not now");
      if (go === "a") return bmUndoRun(ticks, true);
    } else toast(e.message, 6000);
  }
}

/* The brand on one page of plain text: for a Shopify or Etsy store, a
   printer, or a designer. */
function bmSheetText() {
  const k = _bmKit;
  const d = bmDir(k.direction);
  const fl = (id) => (bmFontRow(id) || {}).label || id;
  const gf = (id) => `https://fonts.google.com/specimen/${encodeURIComponent(fl(id)).replace(/%20/g, "+")}`;
  const caseWord = { upper: "all capitals", lower: "all lowercase", none: "as written" }[k.wordmark.case] || "";
  return [
    `${k.name}: brand sheet`,
    d ? `Direction: ${d.name}` : "",
    "",
    `Tagline: ${k.text.tagline}`,
    `Statement: ${k.text.statement}`,
    `Promise: ${k.text.promise}`,
    `Instagram bio: ${k.text.bio}`,
    "",
    "Colours",
    ...BM_ROLES.map(([r, l]) => `  ${l}: ${k.colours[r]}`),
    "",
    "Type",
    `  Logo: ${fl(k.wordmark.font)}, weight ${k.wordmark.weight}, ${caseWord}, letter spacing ${k.wordmark.track}em  ${gf(k.wordmark.font)}`,
    `  Headings: ${fl(k.fonts.heading)}  ${gf(k.fonts.heading)}`,
    `  Body: ${fl(k.fonts.body)}  ${gf(k.fonts.body)}`,
    `  Small caps: ${fl(k.fonts.accent)}  ${gf(k.fonts.accent)}`,
    "",
    "About us",
    k.text.about,
  ].filter((l) => l !== null).join("\n");
}

function bmSheetHtml() {
  return `<div class="card bm-sheet">
    <div class="bm-sec-h"><div><h3>Brand sheet</h3>
      <p class="muted tiny">Everything on one page: for another store, a printer or a designer.</p></div>
      <span><button class="btn ghost sm" id="bmSheetCopy">${sic("copy")}Copy</button>
      <button class="btn ghost sm" id="bmSheetDl">${sic("download")}Download</button></span></div>
    <pre class="bm-sheet-t">${esc(bmSheetText())}</pre></div>`;
}
