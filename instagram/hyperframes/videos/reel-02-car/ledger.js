/* One Tap Manager · ledger-world motion helpers.
   Needs gsap and window.T (timing baked in by tools/build.mjs).
   Everything is a tween or a set on one paused timeline: no callbacks,
   no randomness, so any frame renders the same when seeked. */
(function () {
  const W = 1080, H = 1920, NS = "http://www.w3.org/2000/svg";
  const L = (window.L = {});
  let tl, stage, uid = 0;

  // ---------- time ----------
  T.at = function (expr) {
    if (typeof expr === "number") return expr;
    if (/^-?\d*\.?\d+$/.test(String(expr).trim())) return parseFloat(expr);
    const m = String(expr).replace(/\s+/g, "").match(/^(H|EC|T|L\d+(?:\.\d+)?e?(?::[^+\-]+?)?)((?:[+-]\d*\.?\d+)*)$/i);
    if (!m) throw new Error("bad time " + expr);
    const base = m[1];
    let v;
    if (base === "H") v = T.hook;
    else if (base === "EC") v = T.endCard;
    else if (base === "T") v = T.total;
    else {
      const [ref, word] = base.split(":");
      const lm = ref.match(/^L(\d+)(?:\.(\d+))?(e?)$/i);
      const Ln = T.lines[+lm[1] - 1];
      const C = lm[2] ? Ln.chunks[+lm[2] - 1] : null;
      if (word) {
        const want = word.replace(/>$/, "").toLowerCase();
        const pool = (C ? [C] : Ln.chunks).flatMap((c) => c.words);
        const hit = pool.find((w) => w.w.toLowerCase().replace(/[^\w$%']/g, "") === want) || pool.find((w) => w.w.toLowerCase().includes(want));
        if (!hit) throw new Error("no word " + want + " in " + ref);
        v = word.endsWith(">") ? hit.e : hit.s;
      } else v = C ? (lm[3] ? C.e : C.s) : lm[3] ? Ln.e : Ln.s;
    }
    for (const o of m[2].match(/[+-]\d*\.?\d+/g) || []) v += parseFloat(o);
    return v;
  };
  L.series = (a, b, n) => { a = T.at(a); b = T.at(b); return Array.from({ length: n }, (_, i) => a + (n === 1 ? 0 : ((b - a) * i) / (n - 1))); };

  // ---------- setup ----------
  L.init = function () {
    tl = gsap.timeline({ paused: true });
    stage = document.getElementById("stage");
    L.tl = tl;
    L.stage = stage;
    window.__timelines = window.__timelines || {};
    window.__timelines.main = tl;
    L.flashEl = L.div("flash", stage);
    L.overlay = L.svg(stage, "z-index:700");
    return tl;
  };
  L.done = function () {
    tl.set({}, {}, T.total);
    tl.seek(0);
  };
  L.rng = (seed) => () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };

  // ---------- DOM ----------
  L.el = (tag, cls, parent, css, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (css) e.style.cssText = css;
    if (html != null) e.innerHTML = html;
    (parent || stage).appendChild(e);
    return e;
  };
  L.div = (cls, parent, css, html) => L.el("div", cls, parent, css, html);
  L.svg = (parent, css, vb) => {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", vb || `0 0 ${W} ${H}`);
    if (!vb) { s.setAttribute("width", W); s.setAttribute("height", H); }
    s.setAttribute("class", "ink-layer");
    if (css) s.style.cssText = css;
    (parent || stage).appendChild(s);
    return s;
  };
  L.s = (parent, tag, attrs, css) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (css) e.style.cssText = css;
    parent.appendChild(e);
    return e;
  };
  L.markup = (parent, html) => { parent.insertAdjacentHTML("beforeend", html); return parent.lastElementChild; };
  L.show = (el, t) => { el.style.visibility = "hidden"; tl.set(el, { visibility: "visible" }, t); return el; };
  L.hide = (el, t) => tl.set(el, { visibility: "hidden" }, t);

  // ---------- scenes ----------
  L.scene = function (start, end, o = {}) {
    const s = L.div("scene", stage);
    const bg = o.bg || "paper";
    if (bg === "paper") {
      s.classList.add("bg-paper");
      if (o.ruled !== false) L.div(o.grid ? "fill grid-paper" : "fill ruled", s);
    } else if (bg === "night") s.classList.add("bg-night");
    else if (bg !== "none") s.style.background = bg;
    s.cam = L.div("fill", s);
    if (bg !== "none" && o.grain !== false) L.div(bg === "night" ? "grain light" : "grain", s);
    if (o.vignette !== false && bg !== "none") L.div(bg === "night" ? "vignette dark" : "vignette", s);
    // display also flips, so children that were set visible cannot leak outside the scene window
    tl.set(s, { visibility: "visible", display: "block" }, start);
    if (end != null) tl.set(s, { visibility: "hidden", display: "none" }, end);
    s.t0 = start;
    s.t1 = end;
    return s;
  };

  // ---------- motion vocabulary ----------
  L.slam = (el, t, o = {}) => {
    tl.fromTo(el, { scale: o.from ?? 1.45, autoAlpha: 0 }, { scale: 0.97, autoAlpha: 1, duration: 0.28, ease: "expo.out" }, t);
    tl.to(el, { scale: 1, duration: 0.2, ease: "sine.out" }, t + 0.28);
    return el;
  };
  L.pop = (el, t, o = {}) => { tl.fromTo(el, { scale: o.from ?? 0.3, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: o.dur ?? 0.4, ease: "back.out(1.8)" }, t); return el; };
  L.glide = (el, t, o = {}) => {
    tl.fromTo(el, { x: o.x ?? 0, y: o.y ?? 0, rotation: o.r ?? 0, autoAlpha: o.fade === false ? 1 : 0 },
      { x: 0, y: 0, rotation: o.toR ?? 0, autoAlpha: 1, duration: o.dur ?? 0.8, ease: o.ease ?? "power3.inOut" }, t);
    return el;
  };
  L.rise = (el, t, o = {}) => { tl.fromTo(el, { y: o.y ?? 44, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: o.dur ?? 0.5, ease: o.ease ?? "power3.out" }, t); return el; };
  L.fadeIn = (el, t, d = 0.4) => { tl.fromTo(el, { autoAlpha: 0 }, { autoAlpha: 1, duration: d, ease: "power1.out" }, t); return el; };
  L.fadeOut = (el, t, d = 0.4) => { tl.to(el, { autoAlpha: 0, duration: d, ease: "power1.in" }, t); return el; };
  L.drift = (el, t0, t1, o = {}) => {
    const half = (o.period ?? 4.4) / 2;
    const n = Math.max(0, Math.floor((t1 - t0) / half) - 1);
    tl.fromTo(el, { x: 0, y: 0, rotation: 0 }, { x: o.x ?? 8, y: o.y ?? -10, rotation: o.r ?? 1.5, duration: half, ease: "sine.inOut", yoyo: true, repeat: n }, t0);
    return el;
  };
  L.bob = (el, t0, t1, amp = 10, period = 1.6) => {
    const half = period / 2;
    const n = Math.max(0, Math.floor((t1 - t0) / half) - 1);
    tl.fromTo(el, { y: 0 }, { y: -amp, duration: half, ease: "sine.inOut", yoyo: true, repeat: n }, t0);
  };
  L.shake = (el, t, amp = 10, dur = 0.3) => {
    const r = L.rng(Math.round(t * 1000));
    const steps = 6;
    for (let i = 0; i < steps; i++) tl.to(el, { x: (r() - 0.5) * amp * (1 - i / steps), y: (r() - 0.5) * amp * 0.5 * (1 - i / steps), duration: dur / steps, ease: "none" }, t + (i * dur) / steps);
    tl.to(el, { x: 0, y: 0, duration: 0.05 }, t + dur);
  };
  L.handheld = (el, t0, t1, amp = 7, seed = 7) => {
    const r = L.rng(seed);
    const step = 0.22;
    for (let t = t0; t < t1 - 0.01; t += step)
      tl.to(el, { x: (r() - 0.5) * amp * 2, y: (r() - 0.5) * amp * 1.6, rotation: (r() - 0.5) * 0.9, duration: Math.min(step, t1 - t), ease: "sine.inOut" }, t);
  };
  L.push = (el, t0, t1, to = 1.04, o = {}) => { tl.fromTo(el, { scale: o.from ?? 1 }, { scale: to, duration: t1 - t0, ease: o.ease ?? "none", transformOrigin: o.origin ?? "50% 50%" }, t0); };
  L.flash = (t) => { tl.set(L.flashEl, { visibility: "visible" }, t); tl.set(L.flashEl, { visibility: "hidden" }, t + 2 / 30); };
  L.drain = (el, t, dur = 0.6) => {
    tl.fromTo(el, { filter: "sepia(0) saturate(1) brightness(1) contrast(1)" },
      { filter: "sepia(0.75) saturate(0.32) brightness(1.2) contrast(0.7)", duration: dur, ease: "power1.inOut" }, t);
  };

  // ---------- ink ----------
  L.ink = (svg, d, t, dur, o = {}) => {
    const p = L.s(svg, "path", { d, class: "ink", pathLength: 1 });
    if (o.color) p.style.stroke = o.color;
    if (o.w) p.style.strokeWidth = o.w;
    if (o.fill) p.style.fill = o.fill;
    p.style.strokeDasharray = "1 2";
    if (t == null) { p.style.strokeDashoffset = 0; return p; }
    p.style.strokeDashoffset = 1.02;
    tl.fromTo(p, { strokeDashoffset: 1.02 }, { strokeDashoffset: 0, duration: dur, ease: o.ease ?? "power1.inOut" }, t);
    return p;
  };
  L.dotted = (svg, d, t, dur, o = {}) => {
    const id = "mk" + ++uid;
    const mask = L.s(svg, "mask", { id, maskUnits: "userSpaceOnUse", x: 0, y: 0, width: W, height: H });
    const mp = L.s(mask, "path", { d, fill: "none", stroke: "#fff", "stroke-width": (o.w ?? 6) + 14, "stroke-linecap": "round", pathLength: 1 });
    mp.style.strokeDasharray = "1 2";
    mp.style.strokeDashoffset = 1.02;
    tl.fromTo(mp, { strokeDashoffset: 1.02 }, { strokeDashoffset: 0, duration: dur, ease: o.ease ?? "power1.inOut" }, t);
    const p = L.s(svg, "path", { d, class: "ink", mask: `url(#${id})` });
    p.style.strokeDasharray = o.dash ?? "4 18";
    if (o.color) p.style.stroke = o.color;
    if (o.w) p.style.strokeWidth = o.w;
    return p;
  };
  L.circleMark = (svg, cx, cy, rx, ry, t, dur = 0.5, o = {}) => {
    // a hand-drawn loop that overshoots its start, like a real pen circle
    const r = L.rng(Math.round(cx + cy));
    const pts = [];
    for (let i = 0; i <= 28; i++) {
      const a = -Math.PI * 0.7 + (i / 28) * Math.PI * 2.18;
      const k = 1 + (r() - 0.5) * 0.06;
      pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
    }
    const d = "M" + pts.map((p) => p.map((v) => v.toFixed(1)).join(" ")).join(" L");
    return L.ink(svg, d, t, dur, { ease: "power2.inOut", ...o });
  };
  L.hl = (scope, t, stagger = 0.2) => {
    const is = scope.querySelectorAll(".hl > i");
    if (is.length) tl.fromTo(is, { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: "power2.out", stagger }, t);
  };

  // ---------- props ----------
  L.chip = (parent, text, css, t) => { const c = L.div("chip", parent, css, text); if (t != null) L.pop(c, t, { from: 0.6 }); return c; };
  L.stamp = (parent, text, t, o = {}) => {
    const s = L.div("stamp " + (o.color || "leak"), parent, `left:${o.x}px;top:${o.y}px;font-size:${o.size ?? 64}px;${o.css || ""}`, text);
    gsap.set(s, { rotation: o.r ?? -6, transformOrigin: "50% 50%" });
    tl.fromTo(s, { scale: 2.2, autoAlpha: 0 }, { scale: 0.94, autoAlpha: 1, duration: 0.15, ease: "power4.in" }, t);
    tl.to(s, { scale: 1, duration: 0.24, ease: "back.out(3)" }, t + 0.15);
    return s;
  };
  L.bubble = (parent, text, css, t, o = {}) => { const b = L.div("bubble", parent, css, text); if (t != null) L.glide(b, t, { x: o.x ?? 120, dur: 0.45, ease: "back.out(1.6)" }); return b; };
  L.logo = (parent, css, size = 200) =>
    L.div("", parent, `position:absolute;width:${size}px;height:${size}px;border-radius:${size * 0.23}px;background:var(--indigo);color:var(--paper);font-family:var(--mono);font-weight:700;font-size:${size * 0.5}px;letter-spacing:-0.06em;display:grid;place-items:center;${css}`, "1T");

  // counter: discrete values toggled on the timeline (seek-safe, no callbacks)
  L.counter = (parent, css, cls, from, to, t, dur, fmt, o = {}) => {
    const wrap = L.div("abs " + (cls || ""), parent, css);
    const steps = o.steps ?? Math.min(30, Math.max(2, Math.abs(Math.round(to - from)) || 2));
    const ease = gsap.parseEase(o.ease ?? "power2.out");
    const spans = [];
    for (let i = 0; i <= steps; i++) {
      const v = from + (to - from) * ease(i / steps);
      const sp = L.el("span", "", wrap, i === 0 ? "" : "display:none", fmt(v));
      spans.push(sp);
    }
    wrap.style.whiteSpace = "nowrap";
    for (let i = 1; i <= steps; i++) {
      const at = t + (dur * i) / steps;
      tl.set(spans[i - 1], { display: "none" }, at);
      tl.set(spans[i], { display: "inline" }, at);
    }
    // stack spans so the box has the final width
    return wrap;
  };
  // typing: one span per character, shown one by one; cursor optional
  L.type = (parent, text, t, cps = 24, o = {}) => {
    const wrap = o.el || L.div("abs " + (o.cls || ""), parent, o.css || "");
    const chars = [...text].map((ch) => L.el("span", "", wrap, "display:none", ch === " " ? " " : ch.replace("<", "&lt;")));
    chars.forEach((c, i) => tl.set(c, { display: "inline" }, t + i / cps));
    let cursor = null;
    if (o.cursor) {
      cursor = L.el("span", "", wrap, `display:inline-block;width:0.08em;height:1em;background:currentColor;margin-left:0.04em;vertical-align:-0.12em`);
      const n = Math.floor(((o.cursorUntil ?? t + text.length / cps + 2) - t) / 0.5);
      for (let i = 0; i < n; i++) tl.set(cursor, { opacity: i % 2 ? 1 : 0 }, t + text.length / cps + i * 0.5);
    }
    wrap.chars = chars;
    wrap.cursor = cursor;
    wrap.tEnd = t + text.length / cps;
    return wrap;
  };
  L.backspace = (wrap, keep, t, cps = 18) => {
    const kill = wrap.chars.slice(keep).reverse();
    kill.forEach((c, i) => tl.set(c, { display: "none" }, t + i / cps));
    return t + kill.length / cps;
  };
  L.wipeIn = (el, t, dur = 0.7, ease = "power1.inOut") => { tl.fromTo(el, { clipPath: "inset(-20% 100% -20% 0%)" }, { clipPath: "inset(-20% 0% -20% 0%)", duration: dur, ease }, t); return el; };

  // receipt that prints line by line from a slot
  L.receipt = (parent, o, t, perLine = 0.32) => {
    const r = L.div("receipt", parent, `left:${o.x}px;top:${o.y}px;width:${o.w}px;${o.css || ""}`);
    const rows = [];
    o.rows.forEach((row) => {
      if (row === "---") rows.push(L.div("rule", r));
      else rows.push(L.div("row " + (row[2] || ""), r, row[3] || "", `<span>${row[0]}</span><span>${row[1] ?? ""}</span>`));
    });
    // zig-zag torn edge
    const teeth = Math.round(o.w / 28);
    let poly = "0 0, 100% 0, 100% calc(100% - 18px)";
    for (let i = teeth; i >= 0; i--) poly += `, ${(i / teeth) * 100}% ${i % 2 ? "calc(100% - 18px)" : "100%"}`;
    r.style.clipPath = `polygon(${poly})`;
    rows.forEach((row, i) => {
      row.style.visibility = "hidden";
      tl.set(row, { visibility: "visible" }, t + i * perLine);
      tl.fromTo(r, { y: 0 }, { y: 3, duration: perLine / 2, ease: "sine.inOut", yoyo: true, repeat: 1 }, t + i * perLine);
    });
    r.rows = rows;
    return r;
  };

  // ---------- transitions ----------
  L.ripple = (next, t, x, y, o = {}) => {
    const dur = o.dur ?? 0.62;
    tl.fromTo(next, { clipPath: `circle(0px at ${x}px ${y}px)` }, { clipPath: `circle(2300px at ${x}px ${y}px)`, duration: dur, ease: "power2.in" }, t);
    tl.set(next, { clipPath: "none" }, t + dur + 0.01);
    const dot = L.s(L.overlay, "circle", { cx: x, cy: y, r: 16, fill: "#F5A623" });
    dot.style.visibility = "hidden";
    tl.set(dot, { visibility: "visible" }, t - 0.12);
    tl.fromTo(dot, { attr: { r: 30 } }, { attr: { r: 12 }, duration: 0.12, ease: "power2.in" }, t - 0.12);
    tl.set(dot, { visibility: "hidden" }, t + 0.05);
    const ring = L.s(L.overlay, "circle", { cx: x, cy: y, r: 0, fill: "none", stroke: o.color || "#F5A623", "stroke-width": 12 });
    ring.style.visibility = "hidden";
    tl.set(ring, { visibility: "visible" }, t);
    tl.fromTo(ring, { attr: { r: 10 }, opacity: 1 }, { attr: { r: 2400 }, opacity: 0.25, duration: dur + 0.1, ease: "power2.in" }, t);
    tl.set(ring, { visibility: "hidden" }, t + dur + 0.1);
  };
  L.flip = (out, t, dur = 0.45) => {
    tl.set(out, { zIndex: 60, transformPerspective: 2400, transformOrigin: "0% 50%" }, t);
    const shade = L.div("fill", out, "background:#000;opacity:0;z-index:99");
    tl.to(out, { rotationY: -95, duration: dur, ease: "power2.in" }, t);
    tl.to(shade, { opacity: 0.35, duration: dur, ease: "power2.in" }, t);
    tl.set(out, { visibility: "hidden", display: "none" }, t + dur);
  };
  L.crossfade = (a, b, t, dur = 0.5) => { tl.fromTo(b, { autoAlpha: 0 }, { autoAlpha: 1, duration: dur }, t); tl.set(a, { visibility: "hidden", display: "none" }, t + dur); };

  // ---------- phone with our rebuilt app ----------
  const ICON = {
    grid: `<svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="#0B6FE6" stroke-width="2.2"><rect x="2" y="2" width="7" height="7" rx="2"/><rect x="13" y="2" width="7" height="7" rx="2"/><rect x="2" y="13" width="7" height="7" rx="2"/><rect x="13" y="13" width="7" height="7" rx="2"/></svg>`,
    sun: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#333" stroke-width="1.5"><circle cx="8" cy="8" r="3"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6 13 13M3 13l1.4-1.4M11.6 4.4 13 3"/></svg>`,
    moon: `<svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="#666" stroke-width="1.5"><path d="M12.5 10.5A5.5 5.5 0 0 1 5.5 3.5a5.5 5.5 0 1 0 7 7z"/></svg>`,
    exit: `<svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="#0B6FE6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 4h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4M9 15l-4-4 4-4M5 11h10"/></svg>`,
  };
  L.phone = (parent, o) => {
    const w = o.w ?? 420, h = o.h ?? Math.round(w * 2.13);
    const p = L.div("phone", parent, `left:${o.x}px;top:${o.y}px;width:${w}px;height:${h}px;${o.css || ""}`);
    const sc = L.div("screen", p);
    const k = (w - 24) / 390;
    const app = L.div("app", sc, `transform:scale(${k});height:${(h - 24) / k}px`);
    if (o.tag !== false) p.tagEl = L.div("chip tag", p, "", "SAMPLE SHOP DATA");
    p.app = app;
    p.k = k;
    if (o.crumb) {
      L.markup(app, `<div class="app-top"><div class="app-grid">${ICON.grid}</div><div class="app-logo">1T</div><div class="app-crumb">&rsaquo;&nbsp; ${o.crumb}</div><div class="app-toggle"><span>${ICON.sun}</span><span>${ICON.moon}</span></div><div style="margin-left:8px">${ICON.exit}</div></div>`);
      p.body = L.div("app-body", app);
      if (o.nav !== false) L.markup(app, `<div class="app-nav"><div><i></i>Home</div><div><i style="border-radius:50%"></i>Approvals</div><div><i style="border-radius:50% 50% 6px 6px"></i>Account</div></div>`);
    }
    return p;
  };

  // ---------- captions (word level, from the voice timing) ----------
  L.captions = (o = {}) => {
    const layer = L.div("captions", stage);
    const hideFrom = o.hideAfter ?? T.endCard;
    const pages = [];
    T.lines.forEach((Ln) => Ln.chunks.forEach((c) => {
      const w = c.words;
      const per = w.length <= 8 ? w.length : Math.ceil(w.length / Math.ceil(w.length / 7));
      for (let i = 0; i < w.length; i += per) pages.push(w.slice(i, i + per));
    }));
    pages.forEach((words, pi) => {
      const s = words[0].s, e = words[words.length - 1].e;
      if (s >= hideFrom) return;
      const next = pages[pi + 1];
      const until = Math.min(next ? next[0].s : e + 0.5, e + 0.5, hideFrom);
      const page = L.div("cap-page", layer);
      const box = L.div("cap-box", page);
      // two lines at most, six words a line
      const perLine = words.length > 6 ? Math.ceil(words.length / 2) : words.length;
      words.forEach((wd, i) => {
        if (i === perLine) L.el("br", "", box);
        const sp = L.el("span", "", box, "", wd.w + (i < words.length - 1 && i !== perLine - 1 ? " " : ""));
        tl.set(sp, { color: "#1E3A8A" }, wd.s);
        tl.set(sp, { color: "#101828" }, Math.min(wd.e, until));
      });
      tl.set(page, { visibility: "visible" }, s - 0.02);
      tl.set(page, { visibility: "hidden" }, until);
    });
    (o.hide || []).forEach(([a, b]) => {
      tl.set(layer, { autoAlpha: 0 }, T.at(a));
      tl.set(layer, { autoAlpha: 1 }, T.at(b));
    });
    return layer;
  };

  // ---------- end cards ----------
  L.endCard = (sceneStart, comment, o = {}) => {
    const s = L.scene(sceneStart, null, { bg: "paper" });
    const start = o.anim ?? sceneStart;
    const logo = L.div("ec-logo", s.cam, "", "1T");
    const ov = L.svg(s.cam);
    const ring = L.s(ov, "circle", { cx: 540, cy: 672, r: 120, fill: "none", stroke: "#F5A623", "stroke-width": 6 });
    tl.fromTo(ring, { attr: { r: 100 }, opacity: 0 }, { attr: { r: 150 }, opacity: 1, duration: 0.5, ease: "power2.out" }, start + 0.35);
    const ring2 = L.s(ov, "circle", { cx: 540, cy: 672, r: 150, fill: "none", stroke: "#F5A623", "stroke-width": 4 });
    tl.fromTo(ring2, { attr: { r: 150 }, opacity: 0.8 }, { attr: { r: 520 }, opacity: 0, duration: 1.0, ease: "power2.out" }, start + 0.4);
    L.pop(logo, start + 0.1);
    const tx = L.div("ec-text", s.cam, o.top ? `top:${o.top}px` : "");
    const c = L.div("ec-comment", tx, "", comment);
    const l2 = L.div("ec-line2", tx, "", o.line2 ?? "One shop problem. Fixed every week.");
    const hd = L.div("ec-handle", tx, "", o.handle ?? "@onetapmanager");
    L.rise(c, start + 0.3);
    L.rise(l2, start + 0.5);
    L.rise(hd, start + 0.65);
    s.logo = logo;
    return s;
  };
  L.fridayCard = (sceneStart, nextTopic, anim) =>
    L.endCard(sceneStart, "Save this.", { anim, line2: `Next Friday: ${nextTopic}`, handle: "Shop Doctor · every Friday · @onetapmanager" });

  // ---------- Shop Doctor sting (exactly 1.6 s) ----------
  L.sting = (start, episode) => {
    const s = L.scene(start, start + 1.6, { bg: "paper" });
    const ov = L.svg(s.cam);
    const t = start;
    // stethoscope in one continuous stroke: earpieces, tube, chest piece
    const scope = "M380 470 C360 520 372 590 430 620 M600 470 C620 520 608 590 550 620 M430 620 Q490 660 550 620 M490 648 C490 760 420 800 430 900 C440 1000 560 1020 600 950";
    L.ink(ov, scope, t, 0.6, { w: 9, ease: "power1.inOut" });
    const chest = L.s(ov, "circle", { cx: 612, cy: 930, r: 30, fill: "#F5A623" });
    L.pop(chest, t + 0.5, { dur: 0.25 });
    // paper storefront
    const shop = L.markup(s.cam, `<svg class="abs" style="left:600px;top:840px" width="300" height="260" viewBox="0 0 300 260">
      <rect x="30" y="80" width="240" height="170" rx="6" fill="#FFFFFF" stroke="#101828" stroke-width="5"/>
      <path d="M20 40 H280 L270 90 H30 Z" fill="#fff" stroke="#101828" stroke-width="5"/>
      <path d="M52 40 L46 90 M98 40 L96 90 M150 40 V90 M202 40 L204 90 M248 40 L254 90" stroke="#C4320A" stroke-width="16"/>
      <rect x="120" y="150" width="60" height="100" fill="#1E3A8A"/><rect x="52" y="130" width="50" height="50" fill="#A9C1F5" stroke="#101828" stroke-width="4"/><rect x="198" y="130" width="50" height="50" fill="#A9C1F5" stroke="#101828" stroke-width="4"/></svg>`);
    L.pop(shop, t + 0.45, { from: 0.6, dur: 0.3 });
    // heartbeat line out of the shop, two spikes, the last one bursts
    L.ink(ov, "M140 1300 H330 L370 1300 L400 1180 L440 1420 L470 1300 H560 L590 1300 L620 1150 L660 1300 H760", t + 0.6, 0.45, { color: "#C4320A", w: 7, ease: "none" });
    // lockup revealed by the tap ripple from the last spike
    const lock = L.div("fill", s.cam, "background:var(--paper)");
    L.div("fill ruled", lock);
    L.div("abs display", lock, "left:0;right:0;top:760px;text-align:center;font-size:110px;color:var(--ink)", "SHOP DOCTOR");
    L.div("chip", lock, "left:50%;top:910px;transform:translateX(-50%);font-size:26px", `${episode} · FRIDAY`);
    const cross = (x, y) => L.div("abs", lock, `left:${x}px;top:${y}px;width:36px;height:36px;background:linear-gradient(var(--leak),var(--leak)) center/100% 10px no-repeat,linear-gradient(var(--leak),var(--leak)) center/10px 100% no-repeat;opacity:.8`);
    const c1 = cross(200, 620), c2 = cross(830, 1060);
    L.drift(c1, t + 1.05, t + 1.6, { period: 1.2, y: -14 });
    L.drift(c2, t + 1.05, t + 1.6, { period: 1.2, y: 12, x: -8 });
    lock.style.visibility = "hidden";
    tl.set(lock, { visibility: "visible" }, t + 1.05);
    tl.fromTo(lock, { clipPath: "circle(0px at 620px 1150px)" }, { clipPath: "circle(2200px at 620px 1150px)", duration: 0.4, ease: "power2.in" }, t + 1.05);
    return s;
  };

  // ---------- prescription pad ----------
  L.rxPad = (start, end, lines) => {
    const s = L.scene(start, end, { bg: "linear-gradient(170deg,#B98552,#8C5A30 60%,#6E4424)", vignette: true });
    L.div("fill", s.cam, "background:repeating-linear-gradient(176deg,rgba(0,0,0,0) 0 38px,rgba(60,30,10,.12) 38px 41px);filter:blur(3px)");
    // pen lying beside the pad
    L.markup(s.cam, `<svg class="abs" style="left:790px;top:560px;transform:rotate(18deg)" width="60" height="760" viewBox="0 0 60 760"><rect x="14" y="0" width="32" height="600" rx="14" fill="#1E3A8A"/><rect x="14" y="80" width="32" height="18" fill="#F5A623"/><path d="M14 600 L30 700 L46 600 Z" fill="#E8D8B8"/><path d="M26 676 L30 700 L34 676 Z" fill="#101828"/><rect x="40" y="20" width="8" height="200" rx="4" fill="#C9D3E8"/></svg>`);
    const pad = L.div("abs", s.cam, "left:110px;top:330px;width:700px;height:1000px;background:var(--paper2);border-radius:10px;box-shadow:24px 36px 60px rgba(40,20,5,.45)");
    gsap.set(pad, { rotation: -3 });
    L.div("abs", pad, "left:20px;right:20px;top:18px;height:14px;background:radial-gradient(circle,rgba(16,24,40,.35) 4px,transparent 5px) 0 0/26px 14px repeat-x");
    L.logo(pad, "left:44px;top:62px", 64);
    L.div("abs", pad, "left:126px;top:74px;font-family:var(--mono);font-weight:600;font-size:26px;color:var(--ink-soft);letter-spacing:.04em", "Shop Doctor · One Tap Manager");
    L.div("abs", pad, "left:40px;right:40px;top:150px;height:3px;background:rgba(16,24,40,.25)");
    L.div("abs", pad, "left:44px;top:170px;font-family:Georgia,serif;font-style:italic;font-weight:700;font-size:150px;color:var(--marigold);line-height:1", "Rx");
    L.div("abs", pad, "right:60px;top:40px;width:130px;height:130px;border-radius:50%;border:10px solid rgba(110,70,30,.14)");
    const ov = L.svg(pad, "", "0 0 700 1000");
    ov.setAttribute("width", 700); ov.setAttribute("height", 1000);
    tl.fromTo(pad, { y: 900 }, { y: 0, duration: 0.5, ease: "power3.out" }, start);
    lines.forEach((txt, i) => {
      const y = 380 + i * 170;
      L.div("abs", pad, `left:60px;right:60px;top:${y + 92}px;height:2px;background:rgba(16,24,40,.18)`);
      const ln = L.div("abs hand", pad, `left:128px;top:${y}px;font-size:62px;color:var(--ink);white-space:nowrap`, txt);
      const t0 = start + 0.6 + i * 0.95;
      L.wipeIn(ln, t0, 0.75, "none");
      L.ink(ov, `M58 ${y + 50} L78 ${y + 72} L108 ${y + 26}`, t0 + 0.78, 0.18, { w: 8 });
    });
    L.stamp(pad, "FIXED", start + 0.6 + lines.length * 0.95 + 0.15, { x: 400, y: 860, color: "indigo", size: 84, r: -7 });
    return s;
  };

  // ---------- hook frame helpers ----------
  L.aiChip = (parent) => L.div("chip ai-chip", parent, "", "AI GENERATED");
  L.money = (v, d = 2) => "$" + v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
})();
