/* One Tap Manager · Attention Span Leaderboard + reward kit.
   Load after ledger.js. Everything is tweens/sets on L.tl (seek-safe, seeded, no callbacks).
   Icons: Tabler Icons (MIT, github.com/tabler/tabler-icons), inlined below.
   Confetti / gloss / burst techniques adapted from the HyperFrames catalog
   (confetti, gloss-sweep) and rebuilt in the brand palette. */
(function () {
  const W = 1080;

  // ---------- icons (Tabler, MIT) ----------
  const P = {
    fish: { s: 1, p: ["M16.69 7.44a6.973 6.973 0 0 0 -1.69 4.56c0 1.747 .64 3.345 1.699 4.571", "M2 9.504c7.715 8.647 14.75 10.265 20 2.498c-5.25 -7.761 -12.285 -6.142 -20 2.504", "M18 11v.01", "M11.5 10.5c-.667 1 -.667 2 0 3"] },
    eye: { s: 0, p: ["M12 4c4.29 0 7.863 2.429 10.665 7.154l.22 .379l.045 .1l.03 .083l.014 .055l.014 .082l.011 .1v.11l-.014 .111a.992 .992 0 0 1 -.026 .11l-.039 .108l-.036 .075l-.016 .03c-2.764 4.836 -6.3 7.38 -10.555 7.499l-.313 .004c-4.396 0 -8.037 -2.549 -10.868 -7.504a1 1 0 0 1 0 -.992c2.831 -4.955 6.472 -7.504 10.868 -7.504zm0 5a3 3 0 1 0 0 6a3 3 0 0 0 0 -6z"] },
    bolt: { s: 0, p: ["M13.5 2 L4.5 13.5 H11 L10 22 L19.5 10 H13 Z"] },
    flame: { s: 0, p: ["M10 2c0 -.88 1.056 -1.331 1.692 -.722c1.958 1.876 3.096 5.995 1.75 9.12l-.08 .174l.012 .003c.625 .133 1.203 -.43 2.303 -2.173l.14 -.224a1 1 0 0 1 1.582 -.153c1.334 1.435 2.601 4.377 2.601 6.27c0 4.265 -3.591 7.705 -8 7.705s-8 -3.44 -8 -7.706c0 -2.252 1.022 -4.716 2.632 -6.301l.605 -.589c.241 -.236 .434 -.43 .618 -.624c1.43 -1.512 2.145 -2.924 2.145 -4.78"] },
    brain: { s: 1, p: ["M15.5 13a3.5 3.5 0 0 0 -3.5 3.5v1a3.5 3.5 0 0 0 7 0v-1.8", "M8.5 13a3.5 3.5 0 0 1 3.5 3.5v1a3.5 3.5 0 0 1 -7 0v-1.8", "M17.5 16a3.5 3.5 0 0 0 0 -7h-.5", "M19 9.3v-2.8a3.5 3.5 0 0 0 -7 0", "M6.5 16a3.5 3.5 0 0 1 0 -7h.5", "M5 9.3v-2.8a3.5 3.5 0 0 1 7 0v10"] },
    target: { s: 1, p: ["M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0", "M12 7a5 5 0 1 0 5 5", "M13 3.055a9 9 0 1 0 7.941 7.945", "M15 6v3h3l3 -3h-3v-3z", "M15 9l-3 3"] },
    crown: { s: 0, p: ["M12 6l4 6l5 -4l-2 10h-14l-2 -10l5 4z"] },
    trophy: { s: 0, p: ["M17 3a1 1 0 0 1 .993 .883l.007 .117v2.17a3 3 0 1 1 0 5.659v.171a6.002 6.002 0 0 1 -5 5.917v2.083h3a1 1 0 0 1 .117 1.993l-.117 .007h-8a1 1 0 0 1 -.117 -1.993l.117 -.007h3v-2.083a6.002 6.002 0 0 1 -4.996 -5.692l-.004 -.225v-.171a3 3 0 0 1 -3.996 -2.653l-.003 -.176l.005 -.176a3 3 0 0 1 3.995 -2.654l-.001 -2.17a1 1 0 0 1 1 -1h10zm-12 5a1 1 0 1 0 0 2a1 1 0 0 0 0 -2zm14 0a1 1 0 1 0 0 2a1 1 0 0 0 0 -2z"] },
    star: { s: 0, p: ["M8.243 7.34l-6.38 .925l-.113 .023a1 1 0 0 0 -.44 1.684l4.622 4.499l-1.09 6.355l-.013 .11a1 1 0 0 0 1.464 .944l5.706 -3l5.693 3l.1 .046a1 1 0 0 0 1.352 -1.1l-1.091 -6.355l4.624 -4.5l.078 -.085a1 1 0 0 0 -.633 -1.62l-6.38 -.926l-2.852 -5.78a1 1 0 0 0 -1.794 0l-2.853 5.78z"] },
  };
  const ico = (name, size = 46) => {
    const d = P[name];
    return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="${d.s ? "none" : "currentColor"}" stroke="${d.s ? "currentColor" : "none"}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d.p.map((x) => `<path d="${x}"/>`).join("")}</svg>`;
  };
  L.icon = ico;

  // ---------- styles ----------
  const css = `
  .asl { position:absolute; left:60px; width:960px; height:106px; border-radius:24px; background:rgba(12,16,28,.84); border:2px solid rgba(255,255,255,.14);
    box-shadow:0 14px 34px rgba(0,0,0,.28); z-index:760; font-family:var(--sans); visibility:hidden; transform-origin:50% 0; }
  .asl-badge { position:absolute; left:14px; top:14px; width:78px; height:78px; border-radius:22px; background:#1B2440; border:2px solid rgba(245,166,35,.6); color:#F5A623; }
  .asl-icon { position:absolute; inset:0; display:grid; place-items:center; }
  .asl-ring { position:absolute; inset:-6px; border-radius:26px; border:4px solid #FFD66B; opacity:0; }
  .asl-cd { position:absolute; inset:0; border-radius:20px; background:#C4320A; visibility:hidden; }
  .asl-cd span { position:absolute; inset:0; display:grid; place-items:center; font-family:var(--mono); font-weight:700; font-size:54px; color:#fff; }
  .asl-lab { position:absolute; left:110px; top:12px; height:32px; width:410px; overflow:hidden; }
  .asl-time { position:absolute; left:528px; top:12px; height:32px; display:flex; align-items:center; gap:7px; color:#A9C1F5; transform-origin:30% 50%; }
  .asl-time svg { flex:none; }
  .asl-time .tv { position:relative; width:62px; height:32px; }
  .asl-time .tv span { position:absolute; left:0; top:0; font-family:var(--mono); font-weight:700; font-size:22px; line-height:32px; letter-spacing:-.02em; }
  .asl-lab span { position:absolute; left:0; top:0; white-space:nowrap; font-family:var(--mono); font-weight:700; font-size:19px; letter-spacing:.1em; color:#A9C1F5; line-height:32px; }
  .asl-rank { position:absolute; right:18px; top:6px; height:46px; width:280px; overflow:hidden; }
  .asl-rank span { position:absolute; right:0; top:0; font-family:var(--mono); font-weight:700; font-size:36px; letter-spacing:-.02em; color:#fff; line-height:46px; white-space:nowrap; }
  .asl-track { position:absolute; left:110px; right:22px; top:60px; height:14px; border-radius:7px; background:rgba(255,255,255,.13); }
  .asl-fill { position:absolute; left:0; top:0; bottom:0; width:100%; border-radius:7px; background:linear-gradient(90deg,#F5A623,#FFD66B); transform-origin:0 50%; overflow:hidden; box-shadow:0 0 18px rgba(245,166,35,.65); }
  .asl-shine { position:absolute; top:0; bottom:0; left:0; width:28%; background:linear-gradient(90deg,transparent,rgba(255,255,255,.9),transparent); }
  .asl-tick { position:absolute; top:-3px; width:4px; height:20px; margin-left:-2px; border-radius:2px; background:rgba(255,255,255,.35); }
  .asl-tl { position:absolute; top:80px; width:100px; margin-left:-50px; text-align:center; font-family:var(--mono); font-weight:600; font-size:14px; color:rgba(169,193,245,.75); }
  .asl-marker { position:absolute; top:50%; left:0; width:28px; height:28px; margin:-14px 0 0 -14px; border-radius:50%; background:#fff; box-shadow:0 0 0 4px #F5A623, 0 0 26px 8px rgba(255,214,107,.85); }
  .asl-glow { position:absolute; inset:0; z-index:755; pointer-events:none; box-shadow:inset 0 0 170px 46px rgba(245,166,35,.62); opacity:0; }
  .lg-layer { position:absolute; inset:0; z-index:765; pointer-events:none; visibility:hidden; }
  .lg-rays { position:absolute; left:50%; width:1500px; height:1500px; margin-left:-750px; border-radius:50%;
    background:repeating-conic-gradient(rgba(245,166,35,.30) 0 7deg, rgba(245,166,35,0) 7deg 18deg);
    -webkit-mask-image:radial-gradient(circle,#000 18%,transparent 60%); mask-image:radial-gradient(circle,#000 18%,transparent 60%); }
  .lg-card { position:absolute; left:84px; right:84px; height:218px; border-radius:30px; border:4px solid #101828; overflow:hidden; color:#101828;
    background:linear-gradient(135deg,#FFEDB5 0%,#F7BE45 46%,#E3921B 100%); box-shadow:0 26px 60px rgba(120,70,0,.38), inset 0 3px 0 rgba(255,255,255,.65);
    display:flex; align-items:center; gap:22px; padding:0 30px 10px; }
  .lg-card .lg-ic { flex:none; width:128px; height:128px; border-radius:30px; background:#101828; color:#FFD66B; display:grid; place-items:center; }
  .lg-rank { font-family:var(--mono); font-weight:700; font-size:72px; letter-spacing:-.045em; line-height:1; }
  .lg-name { font-weight:900; font-size:34px; letter-spacing:.07em; margin-top:6px; }
  .lg-sub { font-weight:700; font-size:22px; margin-top:8px; line-height:1.25; max-width:560px; }
  .lg-foot { position:absolute; right:22px; bottom:9px; font-family:var(--mono); font-weight:500; font-size:13px; color:rgba(16,24,40,.62); }
  .lg-gloss { position:absolute; top:-30%; bottom:-30%; left:0; width:34%; background:linear-gradient(100deg,transparent,rgba(255,255,255,.8),transparent); transform:skewX(-18deg); }
  `;
  const st = document.createElement("style");
  st.textContent = css;
  document.head.appendChild(st);

  // ---------- particle burst (seeded, with gravity) ----------
  L.burst = function (parent, x, y, t, o = {}) {
    const tl = L.tl, r = L.rng(Math.round(t * 1000 + x * 7));
    const n = o.n ?? 14, D = o.dur ?? 0.85;
    const cols = o.colors ?? ["#F5A623", "#FFD66B", "#34D399", "#A9C1F5", "#FFFFFF", "#E8683F"];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + r() * 0.6, sp = (o.spread ?? 130) * (0.55 + r() * 0.7), sz = (o.size ?? 12) * (0.6 + r() * 0.8);
      const p = L.div("abs", parent, `left:${x - sz / 2}px;top:${y - sz / 2}px;width:${sz}px;height:${sz * (i % 2 ? 1 : 0.55)}px;background:${cols[i % cols.length]};border-radius:2px;z-index:770;visibility:hidden`);
      const dx = Math.cos(a) * sp, up = Math.sin(a) * sp * 0.8 - 50;
      tl.set(p, { visibility: "visible" }, t);
      tl.fromTo(p, { x: 0, rotation: 0, opacity: 1 }, { x: dx, rotation: (r() - 0.5) * 640, duration: D, ease: "power2.out", immediateRender: false }, t);
      tl.fromTo(p, { y: 0 }, { y: up, duration: D * 0.4, ease: "power2.out", immediateRender: false }, t);
      tl.to(p, { y: up + 150, duration: D * 0.6, ease: "power2.in" }, t + D * 0.4);
      tl.to(p, { opacity: 0, duration: D * 0.3 }, t + D * 0.7);
      tl.set(p, { visibility: "hidden" }, t + D);
    }
  };

  // ---------- confetti: two cannons from the bottom corners, then a rain ----------
  L.confetti = function (parent, t, o = {}) {
    const tl = L.tl, r = L.rng(o.seed ?? 4242);
    const cols = ["#F5A623", "#FFD66B", "#1E3A8A", "#A9C1F5", "#34D399", "#E8683F", "#F7F5EF"];
    const n = o.n ?? 70, y0 = o.y ?? 1560;
    for (let i = 0; i < n; i++) {
      const left = i % 2 === 0, x0 = left ? 20 : W - 20, D = 1.9 + r() * 1.2, sz = 12 + r() * 12;
      const vx = (left ? 1 : -1) * (240 + r() * 560), apex = 260 + r() * 760;
      const p = L.div("abs", parent, `left:${x0}px;top:${y0}px;width:${sz}px;height:${sz * 0.5}px;background:${cols[i % cols.length]};border-radius:2px;z-index:780;visibility:hidden`);
      const ts = t + (i % 12) * 0.018;
      tl.set(p, { visibility: "visible" }, ts);
      tl.fromTo(p, { x: 0, rotation: 0 }, { x: vx, rotation: (r() - 0.5) * 1500, duration: D, ease: "power1.out", immediateRender: false }, ts);
      tl.fromTo(p, { y: 0 }, { y: apex - y0, duration: D * 0.36, ease: "power2.out", immediateRender: false }, ts);
      tl.to(p, { y: 2000 - y0, duration: D * 0.64, ease: "power2.in" }, ts + D * 0.36);
      tl.fromTo(p, { scaleX: 1 }, { scaleX: -1, duration: 0.16, repeat: Math.floor(D / 0.16), yoyo: true, ease: "sine.inOut", immediateRender: false }, ts);
      tl.set(p, { visibility: "hidden" }, ts + D);
    }
    for (let i = 0; i < (o.rain ?? 48); i++) {
      const x = r() * W, D = 2.2 + r() * 1.5, ts = t + 0.3 + r() * 0.9, sz = 10 + r() * 10;
      const p = L.div("abs", parent, `left:${x}px;top:-40px;width:${sz}px;height:${sz * 0.55}px;background:${cols[(i + 3) % cols.length]};border-radius:2px;z-index:778;visibility:hidden`);
      tl.set(p, { visibility: "visible" }, ts);
      tl.fromTo(p, { y: 0, rotation: 0 }, { y: 2000, rotation: (r() - 0.5) * 1080, duration: D, ease: "power1.in", immediateRender: false }, ts);
      tl.fromTo(p, { x: -30 }, { x: 30, duration: 0.55, repeat: Math.floor(D / 0.55), yoyo: true, ease: "sine.inOut", immediateRender: false }, ts);
      tl.set(p, { visibility: "hidden" }, ts + D);
    }
  };

  // ---------- the leaderboard meter ----------
  L.TIERS = [
    { rank: "TOP 100%", tick: "100%", name: "GOLDFISH", icon: "fish" },
    { rank: "TOP 50%", tick: "50%", name: "WARMING UP", icon: "flame" },
    { rank: "TOP 25%", tick: "25%", name: "LOCKED IN", icon: "bolt" },
    { rank: "TOP 10%", tick: "10%", name: "IN THE ZONE", icon: "eye" },
    { rank: "TOP 5%", tick: "5%", name: "DEEP FOCUS", icon: "brain" },
    { rank: "TOP 1%", tick: "1%", name: "LASER FOCUS", icon: "target" },
    { rank: "TOP 0.1%", tick: "0.1%", name: "UNBREAKABLE", icon: "crown" },
    { rank: "TOP 0.01%", tick: "0.01%", name: "ATTENTION LEGEND", icon: "trophy" },
  ];

  // cfg: { times: [t1..t7] unlock times (tier 0 is the start), start, top, labels:[{t, until, text, color}], countdown, legendAt }
  L.attention = function (cfg) {
    const tl = L.tl, stage = L.stage;
    const tiers = L.TIERS.map((d, i) => ({ ...d, t: i ? cfg.times[i - 1] : cfg.start ?? 0.25 }));
    const top = cfg.top ?? 232, N = tiers.length, TW = 828, X0 = 110;
    const box = L.div("asl", stage, `top:${top}px;display:none`); // display too, so inline-visible children stay hidden until t0
    const glow = L.div("asl-glow", stage);
    const badge = L.div("asl-badge", box);
    const ring = L.div("asl-ring", badge);
    const icons = tiers.map((tr, k) => L.div("asl-icon", badge, k ? "visibility:hidden" : "", ico(tr.icon, 46)));
    const cd = L.div("asl-cd", badge);
    const lab = L.div("asl-lab", box);
    const defLab = L.el("span", "", lab, "", cfg.title || "ATTENTION SPAN LEADERBOARD");
    // focus timer: seconds of unbroken watching; it pulses gold at every 10 s, like a streak
    const time = L.div("asl-time", box, "", `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="13" r="8"/><path d="M12 13 V9 M10 2 H14 M19 5 L17.5 6.5"/></svg>`);
    const tv = L.div("tv", time);
    const tStart = cfg.start ?? 0.25, tEnd = cfg.until ?? T.total;
    const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    let prevSpan = null;
    for (let s = 0; s <= Math.floor(tEnd); s++) {
      const sp = L.el("span", "", tv, s ? "visibility:hidden" : "", fmt(s));
      if (s) { tl.set(prevSpan, { visibility: "hidden" }, s); tl.set(sp, { visibility: "visible" }, s); }
      if (s && s % 10 === 0) {
        tl.fromTo(time, { scale: 1, color: "#A9C1F5" }, { scale: 1.35, color: "#FFD66B", duration: 0.14, ease: "back.out(3)", immediateRender: false }, s);
        tl.to(time, { scale: 1, duration: 0.3, ease: "power2.out" }, s + 0.14);
        tl.to(time, { color: "#A9C1F5", duration: 0.6 }, s + 0.6);
      }
      prevSpan = sp;
    }
    const rankBox = L.div("asl-rank", box);
    const ranks = tiers.map((tr, k) => L.el("span", "", rankBox, k ? "visibility:hidden" : "", tr.rank));
    const track = L.div("asl-track", box);
    const fill = L.div("asl-fill", track);
    const shine = L.div("asl-shine", fill);
    const ticks = tiers.map((tr, k) => {
      const p = k / (N - 1);
      L.div("asl-tl", box, `left:${X0 + p * TW}px`, tr.tick);
      return L.div("asl-tick", track, `left:${p * TW}px`);
    });
    const marker = L.div("asl-marker", track);
    const t0 = tiers[0].t;

    // entrance: drops in, or (after L.attentionTest morphed into its slot) the contents fade up
    tl.set(box, { visibility: "visible", display: "block" }, t0);
    if (cfg.enter === "fade")
      [...box.children].forEach((c, i) => tl.fromTo(c, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.3, ease: "power2.out", immediateRender: false }, t0 + Math.min(i, 5) * 0.035));
    else tl.fromTo(box, { y: -160, opacity: 0 }, { y: 0, opacity: 1, duration: 0.55, ease: "back.out(1.6)", immediateRender: false }, t0);

    // continuous climb: the fill reaches each tick exactly at its unlock time
    gsap.set(fill, { scaleX: 0.02 });
    gsap.set(marker, { x: 0.02 * TW });
    let prevT = t0 + 0.4, prevP = 0.02;
    tiers.forEach((tr, k) => {
      if (!k) return;
      const p = k / (N - 1), d = Math.max(0.2, tr.t - prevT);
      tl.fromTo(fill, { scaleX: prevP }, { scaleX: p, duration: d, ease: "none", immediateRender: false }, prevT);
      tl.fromTo(marker, { x: prevP * TW }, { x: p * TW, duration: d, ease: "none", immediateRender: false }, prevT);
      prevT = tr.t; prevP = p;
    });
    // the marker breathes; a shine runs along the fill every few seconds
    const end = cfg.until ?? T.total;
    tl.fromTo(marker, { scale: 1 }, { scale: 1.22, duration: 0.45, yoyo: true, repeat: Math.max(1, Math.floor((end - t0) / 0.45) - 1), ease: "sine.inOut", immediateRender: false }, t0 + 0.5);
    for (let s = t0 + 1.2; s < end - 1; s += 3.6) tl.fromTo(shine, { xPercent: -120 }, { xPercent: 420, duration: 0.9, ease: "power1.inOut", immediateRender: false }, s);

    // label windows (level-up toasts, hints, warnings) swap in place of the title
    const windows = [];
    const labSwap = (text, a, b, color) => {
      windows.push([a, b]);
      const s = L.el("span", "", lab, `visibility:hidden;color:${color || "#F5A623"}`, text);
      tl.set(s, { visibility: "visible" }, a);
      tl.fromTo(s, { y: 26, opacity: 0 }, { y: 0, opacity: 1, duration: 0.2, ease: "power2.out", immediateRender: false }, a);
      tl.to(s, { y: -26, opacity: 0, duration: 0.18, ease: "power2.in" }, b - 0.18);
      tl.set(s, { visibility: "hidden" }, b);
      tl.fromTo(defLab, { y: 0, opacity: 1 }, { y: -26, opacity: 0, duration: 0.15, immediateRender: false }, a);
      tl.fromTo(defLab, { y: 26, opacity: 0 }, { y: 0, opacity: 1, duration: 0.2, immediateRender: false }, b);
    };

    // tier unlocks
    tiers.forEach((tr, k) => {
      if (!k) return;
      const t = tr.t, p = k / (N - 1), last = k === N - 1;
      tl.fromTo(ticks[k], { backgroundColor: "rgba(255,255,255,0.35)", scaleY: 1 }, { backgroundColor: "#FFD66B", scaleY: 1.5, duration: 0.18, ease: "back.out(3)", immediateRender: false }, t);
      tl.fromTo(icons[k - 1], { scale: 1, opacity: 1 }, { scale: 0.2, opacity: 0, duration: 0.15, ease: "power2.in", immediateRender: false }, t);
      tl.set(icons[k], { visibility: "visible" }, t + 0.1);
      tl.fromTo(icons[k], { scale: 0.2, rotation: -25, opacity: 0 }, { scale: 1, rotation: 0, opacity: 1, duration: 0.45, ease: "back.out(3)", immediateRender: false }, t + 0.1);
      tl.fromTo(ring, { scale: 1, opacity: 0.95 }, { scale: 1.75, opacity: 0, duration: 0.55, ease: "power2.out", immediateRender: false }, t);
      tl.fromTo(ranks[k - 1], { y: 0, opacity: 1 }, { y: -48, opacity: 0, duration: 0.18, ease: "power2.in", immediateRender: false }, t);
      tl.set(ranks[k], { visibility: "visible" }, t + 0.1);
      tl.fromTo(ranks[k], { y: 48, opacity: 0, color: "#FFD66B" }, { y: 0, opacity: 1, duration: 0.3, ease: "back.out(2)", immediateRender: false }, t + 0.1);
      if (!last) tl.to(ranks[k], { color: "#FFFFFF", duration: 0.8 }, t + 0.5);
      tl.fromTo(box, { scale: 1 }, { scale: last ? 1.07 : 1.035, duration: 0.1, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
      tl.fromTo(glow, { opacity: 0 }, { opacity: last ? 1 : 0.75, duration: 0.12, immediateRender: false }, t);
      tl.to(glow, { opacity: 0, duration: last ? 1.0 : 0.6 }, t + 0.14);
      L.burst(stage, 60 + X0 + p * TW, top + 67, t, { n: last ? 28 : 14, spread: last ? 200 : 130 });
      labSwap(last ? "NEW RECORD · ATTENTION LEGEND" : `LEVEL UP · ${tr.name}`, t, last ? end : t + 1.4, "#FFD66B");
    });
    (cfg.labels || []).forEach((l) => labSwap(l.text, l.t, l.until, l.color));

    // 3 · 2 · 1 in the badge before the final unlock
    if (cfg.countdown != null) {
      const c = cfg.countdown;
      tl.set(cd, { visibility: "visible" }, c);
      ["3", "2", "1"].forEach((d, i) => {
        const s = L.el("span", "", cd, "visibility:hidden", d);
        tl.set(s, { visibility: "visible" }, c + i * 0.5);
        tl.fromTo(s, { scale: 1.9, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.2, ease: "back.out(2)", immediateRender: false }, c + i * 0.5);
        tl.set(s, { visibility: "hidden" }, c + i * 0.5 + 0.48);
      });
      tl.set(cd, { visibility: "hidden" }, c + 1.5);
    }
    return { box, glow, tiers };
  };

  // ---------- the final payoff card ----------
  L.legend = function (t, cfg = {}) {
    const tl = L.tl, top = cfg.top ?? 350;
    const layer = L.div("lg-layer", L.stage);
    tl.set(layer, { visibility: "visible" }, t);
    const rays = L.div("lg-rays", layer, `top:${top + 109 - 750}px`);
    tl.fromTo(rays, { scale: 0.3, opacity: 0, rotation: 0 }, { scale: 1, opacity: 1, duration: 0.6, ease: "power2.out", immediateRender: false }, t);
    tl.to(rays, { rotation: 45, duration: cfg.hold ?? 4, ease: "none" }, t);
    const card = L.div("lg-card", layer, `top:${top}px`,
      `<div class="lg-ic">${ico("trophy", 92)}</div>
       <div><div class="lg-rank">TOP 0.01%</div><div class="lg-name">ATTENTION LEGEND</div>
       <div class="lg-sub">${cfg.sub || "You watched to the end. Your rank resets next reel. Follow to defend it."}</div></div>
       <div class="lg-gloss"></div>`);
    const foot = L.div("abs", layer, `left:0;right:0;top:${top + 232}px;text-align:center;font-family:var(--mono);font-weight:500;font-size:16px;color:rgba(71,84,103,.85)`, "attention leaderboard is a game, not a real ranking");
    tl.fromTo(foot, { opacity: 0 }, { opacity: 1, duration: 0.4, immediateRender: false }, t + 0.6);
    tl.fromTo(card, { scale: 1.75, rotation: -9, opacity: 0 }, { scale: 0.95, rotation: -2, opacity: 1, duration: 0.3, ease: "power4.in", immediateRender: false }, t);
    tl.to(card, { scale: 1, duration: 0.32, ease: "back.out(3)" }, t + 0.3);
    const gloss = card.querySelector(".lg-gloss");
    gsap.set(gloss, { xPercent: -160 });
    tl.fromTo(gloss, { xPercent: -160 }, { xPercent: 330, duration: 0.9, ease: "power2.inOut", immediateRender: false }, t + 0.45);
    tl.fromTo(gloss, { xPercent: -160 }, { xPercent: 330, duration: 0.9, ease: "power2.inOut", immediateRender: false }, t + 2.3);
    tl.fromTo(card.querySelector(".lg-ic"), { rotation: 0 }, { rotation: 8, duration: 0.3, yoyo: true, repeat: 3, ease: "sine.inOut", immediateRender: false }, t + 0.6);
    L.confetti(layer, t + 0.05, cfg.confetti || {});
    return layer;
  };

  // ---------- full-frame color word card cut into a hook (the reference-reel format) ----------
  // o: { bg, color, size, mono, punch }. Sits under the meter (760) and captions (800).
  L.flashCard = function (text, t, dur, o = {}) {
    const tl = L.tl;
    const c = L.div("fill", L.stage, `z-index:740;visibility:hidden;background:${o.bg || "#C4320A"};display:grid;place-items:center`,
      `<div style="font-family:${o.mono ? "var(--mono)" : "var(--sans)"};font-weight:900;font-size:${o.size ?? 230}px;letter-spacing:-.04em;line-height:1.02;color:${o.color || "#FFFFFF"};text-align:center;padding:0 60px">${text}</div>`);
    tl.set(c, { visibility: "visible" }, t);
    tl.fromTo(c.querySelector("div"), { scale: o.punch ?? 1.45 }, { scale: 1, duration: 0.18, ease: "expo.out", immediateRender: false }, t);
    tl.set(c, { visibility: "hidden" }, t + dur);
    return c;
  };

  // ---------- pre-roll: an "ATTENTION TEST" card that bounces, then morphs into the meter ----------
  // Needs T.pre (script.json "preroll"). Runs on absolute time 0 .. T.pre + 0.62 over the frozen
  // first frame; the card lands exactly on the meter's box. Returns the content time to pass
  // as L.attention({ start, enter: "fade" }).
  L.attentionTest = function (cfg = {}) {
    const tc = L.pre, top = cfg.top ?? 140, secs = cfg.secs ?? Math.round(T.total);
    const set = L.preSet, to = L.preTo, fromTo = L.preFromTo;
    const s2 = document.createElement("style");
    s2.textContent = `
    .atx-dim { position:absolute; inset:0; z-index:790; background:radial-gradient(ellipse 70% 55% at 50% 50%, rgba(8,11,22,.42), rgba(5,7,14,.8)); }
    .atx { position:absolute; left:135px; top:240px; width:810px; height:1440px; border-radius:64px; background:rgba(12,16,28,.84); border:2px solid rgba(255,255,255,.14);
      box-shadow:0px 40px 90px rgba(0,0,0,0.45); z-index:792; overflow:hidden; font-family:var(--sans); transform-origin:50% 50%; }
    .atx-in { position:absolute; left:50%; top:50%; width:810px; height:1440px; margin:-720px 0 0 -405px; display:flex; flex-direction:column; align-items:center; justify-content:center; padding-bottom:130px; }
    .atx-badge { position:relative; width:150px; height:150px; border-radius:42px; background:#1B2440; border:3px solid rgba(245,166,35,.6); color:#F5A623; display:grid; place-items:center; margin-bottom:64px; }
    .atx-ring { position:absolute; inset:-10px; border-radius:50px; border:5px solid #FFD66B; opacity:0; }
    .atx-a { font-weight:900; font-size:116px; line-height:1; letter-spacing:-.02em; color:#fff; }
    .atx-t { font-weight:900; font-size:262px; line-height:.92; letter-spacing:-.03em; color:#F5A623; text-shadow:0 0 70px rgba(245,166,35,.45); }
    .atx-s { margin-top:56px; font-family:var(--mono); font-weight:700; font-size:30px; letter-spacing:.12em; color:#A9C1F5; }
    .atx-trk { position:absolute; left:125px; right:125px; bottom:190px; height:14px; border-radius:7px; background:rgba(255,255,255,.13); }
    .atx-trk i { position:absolute; left:0; top:0; bottom:0; width:4%; border-radius:7px; background:linear-gradient(90deg,#F5A623,#FFD66B); box-shadow:0 0 18px rgba(245,166,35,.65); }
    .atx-trk b { position:absolute; top:50%; left:4%; width:30px; height:30px; margin:-15px 0 0 -15px; border-radius:50%; background:#fff; box-shadow:0 0 0 4px #F5A623, 0 0 26px 8px rgba(255,214,107,.85); }
    .atx-tl { position:absolute; bottom:132px; font-family:var(--mono); font-weight:700; font-size:22px; letter-spacing:.04em; color:rgba(169,193,245,.8); }
    .atx-gloss { position:absolute; top:-10%; bottom:-10%; left:0; width:30%; background:linear-gradient(100deg,transparent,rgba(255,255,255,.12),transparent); transform:skewX(-14deg); }`;
    document.head.appendChild(s2);
    const dim = L.div("atx-dim", L.stage);
    const card = L.div("atx", L.stage);
    const inner = L.div("atx-in", card, "", `
      <div class="atx-badge"><div class="atx-ring"></div>${ico("fish", 96)}</div>
      <div class="atx-a">ATTENTION</div><div class="atx-t">TEST</div>
      <div class="atx-s">${secs} SECONDS · DON'T SCROLL</div>
      <div class="atx-trk"><i></i><b></b></div>
      <div class="atx-tl" style="left:125px">TOP 100%</div><div class="atx-tl" style="right:125px">TOP 0.01%</div>
      <div class="atx-gloss"></div>`);
    const ring = inner.querySelector(".atx-ring"), marker = inner.querySelector(".atx-trk b"), gloss = inner.querySelector(".atx-gloss");

    // the opening bounce: a little bigger, smaller than normal, then normal
    fromTo(card, { scale: 1 }, { scale: 1.06, duration: 0.13, ease: "power2.out", immediateRender: false }, 0);
    to(card, { scale: 0.92, duration: 0.2, ease: "power2.inOut" }, 0.13);
    to(card, { scale: 1, duration: 0.3, ease: "power2.out" }, 0.33);
    [0.05, 0.6].forEach((t) => fromTo(ring, { scale: 1, opacity: 0.95 }, { scale: 1.6, opacity: 0, duration: 0.6, ease: "power2.out", immediateRender: false }, t));
    fromTo(marker, { scale: 1 }, { scale: 1.25, duration: 0.4, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }, 0.2);
    gsap.set(gloss, { xPercent: -160 });
    fromTo(gloss, { xPercent: -160 }, { xPercent: 380, duration: 0.7, ease: "power2.inOut", immediateRender: false }, 0.4);

    // the card zips up into the meter's slot and bounces into place
    to(inner, { opacity: 0, scale: 0.8, duration: 0.14, ease: "power2.in" }, tc - 0.04);
    to(card, { left: 60, top, width: 960, height: 106, borderRadius: 24, boxShadow: "0px 14px 34px rgba(0,0,0,0.28)", duration: 0.3, ease: "power3.in" }, tc);
    to(card, { scale: 1.05, duration: 0.06, ease: "power2.out" }, tc + 0.3);
    to(card, { scale: 0.94, duration: 0.1, ease: "power2.inOut" }, tc + 0.36);
    to(card, { scale: 1, duration: 0.16, ease: "power2.out" }, tc + 0.46);
    to(dim, { opacity: 0, duration: 0.35, ease: "power1.out" }, tc);
    set(dim, { visibility: "hidden" }, tc + 0.36);
    set(card, { visibility: "hidden" }, tc + 0.62);
    return 0.62;
  };
})();
