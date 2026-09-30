<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&family=JetBrains+Mono:wght@500;600;700&family=Kalam:wght@700&display=block" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <link rel="stylesheet" href="ledger.css" />
    <style>
      .mlabel { position: absolute; top: 1392px; width: 80px; text-align: center; font-family: var(--mono); font-weight: 600; font-size: 22px; letter-spacing: 0.06em; color: var(--ink-soft); }
      .ylabel { position: absolute; left: 72px; font-family: var(--mono); font-weight: 600; font-size: 24px; color: var(--ink-soft); }
      .cal { position: absolute; left: 626px; top: 900px; width: 300px; height: 390px; background: var(--paper2); border-radius: 14px; box-shadow: 0 18px 40px rgba(16, 24, 40, 0.18); overflow: hidden; }
      .cal-head { height: 74px; background: var(--leak); color: #fff; font-family: var(--mono); font-weight: 700; font-size: 30px; letter-spacing: 0.2em; display: grid; place-items: center; }
      .cal-num { position: absolute; left: 0; right: 0; top: 96px; text-align: center; font-family: var(--mono); font-weight: 700; font-size: 170px; letter-spacing: -0.05em; color: var(--ink); line-height: 1; }
      .kcard { position: absolute; left: 500px; width: 432px; padding: 30px 32px; background: #fff; border-radius: 28px; box-shadow: 0 26px 60px rgba(0, 0, 0, 0.35); }
      .kcard .k { font-family: var(--mono); font-weight: 600; font-size: 22px; letter-spacing: 0.08em; color: var(--ink-soft); text-transform: uppercase; margin-bottom: 12px; }
      .kcard .t { font-weight: 800; font-size: 46px; letter-spacing: -0.03em; line-height: 1.05; color: var(--ink); }
      .kcard .s { margin-top: 10px; font-weight: 600; font-size: 32px; line-height: 1.22; color: var(--ink-soft); }
      .kcard .item { display: flex; align-items: center; gap: 14px; font-weight: 700; font-size: 36px; color: var(--ink); margin-top: 6px; }
      .kernel { position: absolute; left: 0; top: 0; width: 70px; height: 64px; z-index: 750; visibility: hidden; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{{TOTAL}}" data-width="1080" data-height="1920">
      <div id="stage" class="clip" data-start="0" data-duration="{{TOTAL}}" data-track-index="0"></div>
      <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{{TOTAL}}" data-track-index="9" data-volume="1"></audio>
    </div>
    <!--TIMING-->
    <script src="ledger.js"></script>
    <script>
      const tl = L.init();
      window.__timelines = window.__timelines || {};
      window.__timelines["main"] = tl;
      const at = T.at, H = T.hook;
      const tDrop = at("L1:drop");
      const tR = at("L2e") + 0.5; // tap ripple into night
      const EC = at("EC");

      // chart geometry shared by the ride trace, the money chart and the forecast
      const X0 = 200, DX = 80;
      const vals = [4600, 4950, 5300, 5650, 6000, 6380, 6760, 7182, 6420];
      const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP"];
      const Y = (v) => 1400 - (v - 4400) * 0.3;
      const climbPath = () => { let d = `M${X0} ${Y(vals[0])}`; for (let i = 0; i < 7; i++) d += ` H${X0 + DX * (i + 1)} V${Y(vals[i + 1])}`; return d + ` H${X0 + DX * 8}`; };
      const dropPath = `M${X0 + DX * 8} ${Y(vals[7])} V${Y(vals[8])} H${X0 + DX * 9}`;

      // ================= HOOK · the drop tower, caught on a phone =================
      const hook = L.scene(0, tDrop + 0.8, { bg: "#8DBBE6" });
      const shake = L.div("fill", hook.cam);
      shake.innerHTML = `
      <svg viewBox="0 -300 1080 2400" width="1080" height="2400" style="position:absolute;left:0;top:-300px">
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5A9BD8"/><stop offset=".6" stop-color="#A7CBEA"/><stop offset="1" stop-color="#DCEAF3"/></linearGradient>
          <pattern id="plaid" width="10" height="10" patternUnits="userSpaceOnUse"><rect width="10" height="10" fill="#B3261E"/><rect width="10" height="3" y="4" fill="#161616" opacity=".75"/><rect width="3" height="10" x="4" fill="#161616" opacity=".75"/></pattern>
          <pattern id="awnR" width="44" height="10" patternUnits="userSpaceOnUse"><rect width="22" height="10" fill="#D94A3D"/><rect x="22" width="22" height="10" fill="#FFF8EE"/></pattern>
          <pattern id="awnY" width="44" height="10" patternUnits="userSpaceOnUse"><rect width="22" height="10" fill="#F2B532"/><rect x="22" width="22" height="10" fill="#FFF8EE"/></pattern>
          <pattern id="pop" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="4" height="8" fill="#E23A3A"/><rect x="4" width="4" height="8" fill="#fff"/></pattern>
          <filter id="fg" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="9"/></filter>
          <filter id="far" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="1.6"/></filter>
        </defs>
        <rect x="0" y="-300" width="1080" height="1720" fill="url(#sky)"/>
        <g fill="#fff" opacity=".78"><ellipse cx="190" cy="110" rx="170" ry="36"/><ellipse cx="270" cy="84" rx="92" ry="40"/><ellipse cx="880" cy="360" rx="180" ry="32"/><ellipse cx="950" cy="336" rx="86" ry="34"/></g>
        <g id="wheel" filter="url(#far)"></g>
        <path d="M0 1330 Q220 1280 430 1318 T830 1306 T1080 1296 V1520 H0Z" fill="#88AA86"/>
        <g id="lattice"></g>
        <rect x="486" y="92" width="148" height="50" rx="12" fill="#C83A2E"/>
        <rect x="506" y="62" width="108" height="34" rx="9" fill="#F5A623"/>
        <line x1="560" y1="20" x2="560" y2="64" stroke="#8C95A3" stroke-width="5"/><path d="M560 20 L600 32 L560 44Z" fill="#F5A623"/>
        <g id="capLights"></g>
        <g id="seats"></g>
        <g id="booths"></g>
        <g id="balloons"></g>
        <g id="crowd" filter="url(#fg)"></g>
      </svg>`;
      const hs = shake.querySelector("svg");
      const add = (id, html) => (hs.querySelector("#" + id).innerHTML = html);
      const r = L.rng(11);
      // ferris wheel in the far background
      {
        let w = `<g transform="translate(190 1150)" stroke="#EDE7DC" stroke-width="7" fill="none"><circle r="200"/><circle r="36" fill="#EDE7DC"/>`;
        for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; w += `<line x1="0" y1="0" x2="${(Math.cos(a) * 200).toFixed(1)}" y2="${(Math.sin(a) * 200).toFixed(1)}" stroke-width="4"/>`; }
        for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2 + 0.26; w += `<rect x="${(Math.cos(a) * 200 - 16).toFixed(1)}" y="${(Math.sin(a) * 200 - 6).toFixed(1)}" width="32" height="30" rx="6" fill="${["#E26D5A", "#F2B532", "#5B8DD6", "#6DBE8C"][i % 4]}" stroke="none"/>`; }
        add("wheel", w + `<path d="M-120 250 L0 0 L120 250" stroke-width="10"/></g>`);
      }
      // tower lattice
      {
        let g = `<rect x="516" y="130" width="12" height="1460" fill="#C8CED7"/><rect x="592" y="130" width="12" height="1460" fill="#AEB6C2"/>`;
        for (let y = 140; y < 1580; y += 52) g += `<path d="M522 ${y} L598 ${y + 26} L522 ${y + 52}" stroke="#B9C0CB" stroke-width="4" fill="none"/>`;
        add("lattice", g);
        let lights = "";
        for (let i = 0; i < 8; i++) lights += `<circle cx="${498 + i * 18}" cy="117" r="5" fill="#FFE9A8"/>`;
        add("capLights", lights);
      }
      // the ring of seats: riders from behind, grandpa in plaid with popcorn
      {
        const xs = [432, 472, 512, 552, 594, 634, 674];
        const shirts = ["#3E7CB1", "#E0A93B", "#6DBE8C", "#D9534F", "url(#plaid)", "#8E6CC0".replace("8E6CC0", "4C9A8F"), "#E57C5B"];
        const hair = ["#3A2A20", "#A0522D", "#1E1E1E", "#D9B98A", "#CFCFCF", "#5A3A22", "#1E1E1E"];
        let g = "";
        xs.forEach((x, i) => {
          if (i !== 4) g += `<g class="arms" opacity="0"><rect x="${x - 17}" y="-92" width="7" height="44" rx="3.5" fill="${shirts[i]}" transform="rotate(-14 ${x - 14} -48)"/><rect x="${x + 10}" y="-92" width="7" height="44" rx="3.5" fill="${shirts[i]}" transform="rotate(14 ${x + 14} -48)"/></g>`;
          g += `<rect x="${x - 14}" y="-44" width="28" height="36" rx="9" fill="${shirts[i]}"/><circle cx="${x}" cy="-56" r="13" fill="${hair[i]}"/>`;
        });
        g += `<g id="streaks" opacity="0" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round">${[400, 440, 690, 730, 380, 750].map((x, k) => `<line x1="${x}" y1="${-200 - k * 30}" x2="${x}" y2="${-60 - k * 20}"/>`).join("")}</g>`;
        g += `<rect x="404" y="-14" width="296" height="32" rx="12" fill="#1F6FB2" stroke="#0E3F6B" stroke-width="3"/><rect x="404" y="-14" width="296" height="7" rx="3" fill="#F5A623"/>`;
        xs.forEach((x, i) => {
          const gp = i === 4;
          const c = gp ? "#C8B48A" : ["#2F4A7A", "#36507F", "#1F2F4F", "#3F5E8C"][i % 4];
          g += `<g class="legs${gp ? " gp" : ""}"><rect x="${x - 10}" y="18" width="8" height="44" rx="4" fill="${c}"/><rect x="${x + 2}" y="18" width="8" height="44" rx="4" fill="${c}"/><ellipse cx="${x - 6}" cy="64" rx="7" ry="5" fill="${gp ? "#6B4A2A" : "#EEE"}"/><ellipse cx="${x + 6}" cy="64" rx="7" ry="5" fill="${gp ? "#6B4A2A" : "#EEE"}"/></g>`;
        });
        g += `<rect x="600" y="-22" width="15" height="18" rx="2" fill="url(#pop)"/><circle id="gpk" cx="607" cy="-26" r="4.5" fill="#FFF1C9" stroke="#E3B94B" stroke-width="1.5"/>`;
        add("seats", g);
      }
      // booths, balloons, string lights, crowd
      {
        let b = "";
        for (let i = 0; i < 5; i++) {
          const x = 30 + i * 212;
          b += `<rect x="${x + 10}" y="1446" width="180" height="140" fill="#F3E9D9"/><rect x="${x + 36}" y="1476" width="128" height="60" fill="#3B2F2A"/>`;
          b += `<path d="M${x} 1400 H${x + 200} V1446 ${Array.from({ length: 5 }, (_, k) => `Q${x + 200 - k * 40 - 20} 1470 ${x + 200 - (k + 1) * 40} 1446`).join(" ")} Z" fill="url(#${i % 2 ? "awnY" : "awnR"})"/>`;
        }
        b += `<path d="M0 1380 Q270 1440 540 1380 T1080 1380" stroke="#555" stroke-width="2" fill="none"/>`;
        for (let i = 0; i < 18; i++) { const x = 30 + i * 60; const y = 1380 + Math.sin((x / 1080) * Math.PI * 2) * -18 + 30 * Math.sin((x / 540) * Math.PI) * 0.4; b += `<circle cx="${x}" cy="${y + 10}" r="6" fill="${["#F5A623", "#E26D5A", "#6DBE8C", "#5B8DD6"][i % 4]}"/>`; }
        add("booths", b);
        let bl = "";
        [[110, 1250, "#E26D5A"], [170, 1300, "#F2B532"], [240, 1240, "#5B8DD6"], [850, 1260, "#6DBE8C"], [920, 1210, "#E26D5A"], [990, 1290, "#F2B532"]].forEach(([x, y, c]) => {
          bl += `<path d="M${x} ${y + 30} Q${x - 10} ${y + 90} ${x + 4} ${y + 170}" stroke="#666" stroke-width="2" fill="none"/><ellipse cx="${x}" cy="${y}" rx="26" ry="31" fill="${c}"/><ellipse cx="${x - 8}" cy="${y - 10}" rx="6" ry="9" fill="#fff" opacity=".45"/>`;
        });
        add("balloons", bl);
        let cr = "";
        for (let i = 0; i < 9; i++) {
          const x = -40 + i * 140 + r() * 40, y = 1760 + r() * 110, c = ["#2B303B", "#3A2F2A", "#454B58", "#23262E"][i % 4];
          cr += `<ellipse cx="${x}" cy="${y + 120}" rx="${95 + r() * 20}" ry="80" fill="${c}"/><circle cx="${x}" cy="${y}" r="${48 + r() * 10}" fill="${c}"/>`;
        }
        add("crowd", cr);
      }
      const seats = hs.querySelector("#seats");
      tl.fromTo(seats, { y: 560 }, { y: 250, duration: 1.45, ease: "power1.inOut" }, 0);
      tl.to(seats, { y: 243, duration: 0.07, ease: "power1.out" }, 1.45);
      tl.to(seats, { y: 250, duration: 0.14, ease: "power1.inOut" }, 1.52);
      tl.to(seats, { y: 1330, duration: 0.32, ease: "power2.in" }, 2.3);
      tl.to(seats, { y: 1300, duration: 0.24, ease: "power2.out" }, 2.62);
      hs.querySelectorAll(".legs:not(.gp)").forEach((lg, i) => {
        tl.to(lg, { rotation: (i % 2 ? -1 : 1) * (60 + i * 5), transformOrigin: "50% 0%", duration: 0.14, ease: "power2.out" }, 2.32);
        tl.to(lg, { rotation: 0, duration: 0.25, ease: "power2.inOut" }, 2.66);
      });
      const gpk = hs.querySelector("#gpk");
      tl.fromTo(gpk, { y: 0 }, { y: -34, duration: 0.2, ease: "power2.out" }, 1.85);
      tl.set(gpk, { autoAlpha: 0 }, 2.06);
      // everyone else throws their arms up on the drop; speed streaks
      tl.to(hs.querySelectorAll(".arms"), { opacity: 1, duration: 0.05 }, 2.31);
      tl.to(hs.querySelectorAll(".arms"), { opacity: 0, duration: 0.1 }, 2.78);
      const streaks = hs.querySelector("#streaks");
      tl.to(streaks, { opacity: 0.85, duration: 0.06 }, 2.33);
      tl.to(streaks, { opacity: 0, duration: 0.12 }, 2.6);
      // camera: zoomed in on the seats, tilts up with the climb, lags on the drop, then whips down
      gsap.set(hook.cam, { scale: 1.4, transformOrigin: "540px 960px" });
      tl.fromTo(hook.cam, { y: 330 }, { y: 690, duration: 1.45, ease: "power1.inOut" }, 0);
      tl.to(hook.cam, { y: 560, duration: 0.2, ease: "power1.in" }, 2.38);
      tl.to(hook.cam, { y: -140, duration: 0.34, ease: "power3.out" }, 2.56);
      L.handheld(shake, 0, H, 7, 5);
      tl.fromTo(shake, { filter: "blur(6px)" }, { filter: "blur(0px)", duration: 0.45, ease: "power1.out" }, 0);
      tl.to(shake, { filter: "blur(2.5px)", duration: 0.14 }, 2.5);
      tl.to(shake, { filter: "blur(0px)", duration: 0.2 }, 2.66);
      L.aiChip(hook);
      // freeze, flash, drain, then dissolve once the line lands
      L.flash(H);
      L.drain(hook, H + 0.07, 0.6);
      tl.to(hook.cam, { scale: 1.4 * 1.04, duration: at("L2") - H, ease: "none" }, H);
      tl.to(hook, { autoAlpha: 0, duration: 0.5, ease: "power1.inOut" }, tDrop + 0.25);

      // ================= BEAT 1 + 2 · the ride becomes the money chart =================
      const chart = L.scene(H, tR + 0.7, { bg: "none" });
      const paper = L.div("fill bg-paper", chart);
      const grid = L.div("fill grid-paper", chart);
      chart.insertBefore(paper, chart.cam);
      chart.insertBefore(grid, chart.cam);
      L.div("grain", chart);
      tl.fromTo(grid, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.6 }, H + 0.1);
      tl.fromTo(paper, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5 }, tDrop + 0.25);
      tl.fromTo(chart.cam, { scale: 1 }, { scale: 1.04, duration: at("L2") - H, ease: "none" }, H);
      tl.to(chart.cam, { scale: 1, duration: 0.8, ease: "power2.inOut" }, at("L2"));
      const calBox = L.div("abs", chart.cam, "left:0;top:0;width:1080px;height:1920px");
      const ink = L.svg(chart.cam);

      // climb in steps, one click per step
      const a = H + 0.55, b = at("L1:climb>") + 0.25, rs = L.series(a, b, 7), step = (b - a) / 6;
      for (let i = 0; i < 7; i++) {
        const x1 = X0 + DX * i, x2 = x1 + DX;
        L.ink(ink, `M${x1} ${Y(vals[i])} H${x2} V${Y(vals[i + 1])}`, rs[i] - step * 0.92, step * 0.92, { ease: "power1.in" });
        L.ink(ink, `M${x2} 1360 V1376`, rs[i], 0.1, { color: "#475467", w: 4 });
      }
      L.ink(ink, `M${X0} 1360 V1376`, rs[0] - step, 0.1, { color: "#475467", w: 4 });
      // hold at the top, then the drop
      L.ink(ink, `M${X0 + DX * 7} ${Y(vals[7])} H${X0 + DX * 8}`, b, Math.max(0.3, tDrop - b - 0.05), { ease: "sine.inOut" });
      L.ink(ink, `M${X0 + DX * 8} 1360 V1376`, tDrop - 0.05, 0.1, { color: "#475467", w: 4 });
      L.ink(ink, dropPath, tDrop, 0.25, { ease: "power3.in" });

      // Beat 2 · month labels, dollar axis, the red slam
      const L2 = at("L2");
      L.series(L2, L2 + 0.8, 9).forEach((t, i) => L.fadeIn(L.div("mlabel", chart.cam, `left:${X0 + DX * i}px`, months[i]), t, 0.12));
      L.ink(ink, `M170 1380 V560`, L2, 0.6, { color: "#475467", w: 3, ease: "power2.out" });
      L.ink(ink, `M170 1380 H930`, L2, 0.6, { color: "#475467", w: 3, ease: "power2.out" });
      [[5000, "$5k"], [6000, "$6k"], [7000, "$7k"]].forEach(([v, t], i) => {
        L.ink(ink, `M160 ${Y(v)} H180`, L2 + 0.2 + i * 0.12, 0.1, { color: "#475467", w: 3 });
        L.rise(L.div("ylabel", chart.cam, `top:${Y(v) - 15}px`, t), L2 + 0.2 + i * 0.12, { y: 12, dur: 0.3 });
      });
      const tSlam = at("L2:drop") + 0.1;
      L.ink(ink, dropPath, tSlam - 0.1, 0.3, { color: "#C4320A", w: 9, ease: "power2.out" });
      const big = L.div("abs big-num leak", chart.cam, "left:66px;top:236px;transform-origin:20% 60%", "-10.6%");
      L.slam(big, tSlam);
      L.rise(L.div("abs label", chart.cam, "left:78px;top:458px;font-size:30px", "last month"), tSlam + 0.3, { y: 14 });
      [[850, 300, 16], [905, 360, 9], [870, 420, 12], [820, 250, 7], [930, 290, 6], [800, 455, 8]].forEach(([x, y, rr], i) => {
        const d = L.s(ink, "circle", { cx: x, cy: y, r: rr, fill: "#C4320A" });
        L.pop(d, tSlam + 0.05 + i * 0.025, { dur: 0.25 });
      });
      // "Quietly": the room dims for one breath
      const dim = L.div("fill", chart, "background:#101828;opacity:0");
      tl.to(dim, { opacity: 0.3, duration: 0.25 }, at("L2.2"));
      tl.to(dim, { opacity: 0, duration: 0.45 }, at("L2.2e") + 0.25);
      // "weeks later": a wall calendar flips from day 1 to day 24
      const tW = at("L2.3:weeks");
      const cal = L.div("cal", calBox);
      L.div("cal-head", cal, "", "SEPTEMBER");
      L.div("abs", cal, "left:24px;right:24px;top:84px;height:10px;background:radial-gradient(circle,rgba(16,24,40,.3) 4px,transparent 5px) 0 0/28px 10px repeat-x");
      L.counter(cal, "left:0;right:0;top:108px;text-align:center", "cal-num", 1, 24, tW + 0.3, 0.95, (v) => String(Math.round(v)), { steps: 23, ease: "power1.in" });
      L.glide(cal, tW - 0.15, { x: 420, dur: 0.45, ease: "power3.out" });
      const tLater = at("L2.3:later");
      const note = L.div("abs hand", cal, "left:0;right:0;top:300px;text-align:center;font-size:44px;color:var(--indigo);white-space:nowrap", "noticed: day 24");
      L.wipeIn(note, tLater + 0.1, 0.45);
      L.circleMark(ink, 776, 1227, 150, 44, tLater + 0.55, 0.5);
      L.chip(chart.cam, "EXAMPLE", "left:760px;top:846px", tLater + 0.35);

      // ================= BEAT 3 to 5 · night =================
      const night = L.scene(tR, EC, { bg: "night" });
      L.ripple(night, tR, X0 + DX * 9, Y(vals[8]));
      const gA = L.div("fill", night.cam);
      const gB = L.div("fill", night.cam);
      const L3 = at("L3"), L4 = at("L4"), L5 = at("L5");

      // the phone rises, sales.csv drops in, the sales screen fills row by row
      const rules = L.svg(gA);
      const ph = L.phone(gA, { x: 330, y: 400, w: 420, crumb: "Sales Analytics" });
      tl.fromTo(ph, { y: 900, rotationX: 14, transformPerspective: 1400, autoAlpha: 0 }, { y: 0, rotationX: 0, autoAlpha: 1, duration: 0.8, ease: "power3.out" }, L3);
      const body = ph.body;
      const rows = [
        L.div("app-h1", body, "", "Sales"),
        L.div("app-kpis", body, "", `<div class="app-kpi"><small>Last month</small><b>$6,420</b></div><div class="app-kpi"><small>Month before</small><b>$7,182</b></div>`),
        L.div("app-card", body, "", `<h4>Revenue by month</h4><svg class="mini" width="330" height="120" viewBox="0 0 330 120"></svg><div style="display:flex;justify-content:space-between;font-size:10px;font-weight:600;color:#8A8A92;margin-top:4px"><span>Jan</span><span>Mar</span><span>May</span><span>Jul</span><span style="color:#C4320A">Sep</span></div>`),
        L.div("app-card", body, "", `<h4>Sold less last month</h4><div class="app-row">Linen Wrap Dress (Sage)<b style="margin-left:auto;color:#C4320A">&darr;</b></div><div class="app-row">Silk Scarf (Rust)<b style="margin-left:auto;color:#C4320A">&darr;</b></div>`),
        L.div("app-card", body, "", `<h4>This week</h4><div style="font-size:14px;line-height:1.35">Reorder your best seller before it runs out.</div>`),
      ];
      const tCsv = at("L3:sales");
      L.series(tCsv + 0.35, at("L3e"), rows.length).forEach((t, i) => L.rise(rows[i], t, { y: 18, dur: 0.35 }));
      const mini = rows[2].querySelector(".mini");
      const mx = (i) => 6 + i * 36, my = (v) => 110 - (v - 4400) * 0.034;
      let md = `M${mx(0)} ${my(vals[0])}`;
      for (let i = 1; i <= 7; i++) md += ` H${mx(i)} V${my(vals[i])}`;
      md += ` H${mx(8)}`;
      L.ink(mini, md, tCsv + 0.9, 0.9, { color: "#0B6FE6", w: 4, ease: "none" });
      L.ink(mini, `M${mx(8)} ${my(vals[7])} V${my(vals[8])} H${mx(9) - 6}`, tCsv + 1.8, 0.25, { color: "#C4320A", w: 4 });
      const csv = L.div("abs", gA, "left:470px;top:640px;width:150px;height:190px;background:var(--paper2);border-radius:8px;box-shadow:0 14px 30px rgba(0,0,0,.35);padding:16px 14px", `<div style="font-family:var(--mono);font-weight:700;font-size:20px;color:var(--ink)">sales.csv</div>${"<div style='height:6px;background:rgba(16,24,40,.18);border-radius:3px;margin-top:14px'></div>".repeat(6)}`);
      tl.fromTo(csv, { y: -700, rotation: -12, autoAlpha: 1 }, { y: 0, rotation: 4, duration: 0.45, ease: "power2.in" }, tCsv - 0.2);
      tl.to(csv, { scale: 0.3, autoAlpha: 0, duration: 0.3, ease: "power2.in" }, tCsv + 0.3);
      L.ink(rules, `M290 460 V1400`, L3 + 0.5, 0.6, { w: 4, ease: "power2.out" });
      L.ink(rules, `M790 460 V1400`, L3 + 0.5, 0.6, { w: 4, ease: "power2.out" });
      L.fadeOut(rules, L4 - 0.4, 0.3);

      // Beat 4 · three cards dealt out of the phone (the hero frame)
      tl.to(ph, { x: -262, y: 80, rotation: -6, scale: 0.9, duration: 0.6, ease: "power3.inOut" }, L4 - 0.45);
      const big2 = L.div("abs big-num leak", gA, "left:66px;top:236px", "-10.6%");
      L.rise(big2, L4 - 0.3, { y: 30 });
      const cards = [
        L.div("kcard", gA, "top:560px", `<div class="k">How much you're down</div><div class="t">Down <span class="leak">10.6%</span></div><div class="s">vs the month before</div>`),
        L.div("kcard", gA, "top:840px", `<div class="k">Which products</div><div class="t" style="font-size:38px">Sold less:</div><div class="item">Linen Wrap Dress <b class="leak">&darr;</b></div><div class="item">Silk Scarf <b class="leak">&darr;</b></div>`),
        L.div("kcard", gA, "top:1140px", `<div class="k">What to do this week</div><div class="t" style="font-size:38px;padding-right:56px">Reorder your best seller before it runs out</div><svg style="position:absolute;right:26px;top:24px" width="52" height="52" viewBox="0 0 52 52"><circle cx="26" cy="26" r="24" fill="#34D399"/><path d="M14 27 L23 35 L38 18" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>`),
      ];
      const conn = L.svg(gA);
      ["L4.1", "L4.2", "L4.3"].forEach((k, i) => {
        const t = at(k);
        L.pop(cards[i], t);
        tl.fromTo(cards[i], { x: -160 }, { x: 0, duration: 0.4, ease: "back.out(1.4)" }, t);
        const y0 = 760 + i * 250, y1 = [680, 960, 1270][i];
        L.ink(conn, `M455 ${y0} C480 ${y0} 468 ${y1} 500 ${y1}`, t + 0.1, 0.3, { w: 5 });
      });

      // Beat 5 · pull back: the forecast continues up as a dotted line
      tl.to(gA, { scale: 0.82, autoAlpha: 0, duration: 0.6, ease: "power2.inOut" }, L5);
      tl.fromTo(gB, { scale: 1.14, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.6, ease: "power2.inOut" }, L5);
      const wrapB = L.div("fill", gB, "transform:scale(0.82);transform-origin:540px 960px");
      const inkB = L.svg(wrapB);
      L.ink(inkB, climbPath(), null);
      L.ink(inkB, dropPath, null, 0, { color: "#E8683F", w: 9 });
      L.ink(inkB, `M170 1380 V560 M170 1380 H930`, null, 0, { color: "#A9C1F5", w: 3 });
      months.forEach((m, i) => L.div("mlabel", wrapB, `left:${X0 + DX * i}px;color:#A9C1F5`, m));
      [[5000, "$5k"], [6000, "$6k"], [7000, "$7k"]].forEach(([v, t]) => L.div("ylabel", wrapB, `top:${Y(v) - 15}px;color:#A9C1F5`, t));
      L.dotted(inkB, `M920 ${Y(vals[8])} C965 ${Y(vals[8]) - 20} 1000 ${Y(vals[8]) - 100} 1050 ${Y(vals[8]) - 190}`, L5 + 0.3, 0.8, { w: 8, dash: "3 18" });
      L.rise(L.div("abs num on-night", gB, "left:470px;top:470px;font-size:52px", "Next 30 days: <span class='green'>+8.2%</span>"), L5 + 0.7);
      L.chip(gB, "FORECAST, NOT A PROMISE", "left:474px;top:548px", L5 + 0.9).classList.add("dark");

      // ================= the popcorn kernel that travels the whole story =================
      const kWrap = L.div("kernel", L.stage);
      const kIn = L.div("fill", kWrap);
      kIn.innerHTML = `<svg width="70" height="64" viewBox="0 0 46 42"><path d="M10 30 C2 28 2 16 10 14 C10 5 22 2 26 9 C34 4 44 12 39 21 C46 27 38 38 30 34 C26 41 14 40 10 30Z" fill="#FFF3D1" stroke="#E0B64A" stroke-width="2.5"/><circle cx="20" cy="22" r="3" fill="#F0C75E"/></svg>`;
      tl.set(kWrap, { visibility: "visible" }, H + 0.3);
      tl.fromTo(kWrap, { x: 580, y: 1226, rotation: 0 }, { x: X0 + DX * 7 + 18, y: Y(vals[7]) - 50, rotation: 200, duration: 1.3, ease: "power2.out" }, H + 0.3);
      L.bob(kIn, H + 1.6, tR, 9, 1.4);
      tl.set(kWrap, { visibility: "hidden" }, tR + 0.25);
      tl.set(kWrap, { visibility: "visible" }, at("L4.3e") + 0.05);
      tl.fromTo(kWrap, { x: 852, y: 880, rotation: 0 }, { x: 852, y: 1082, rotation: 90, duration: 0.5, ease: "bounce.out" }, at("L4.3e") + 0.05);
      const hopEnd = at("L5e") - 0.25, kx = 540 + (1050 - 540) * 0.82 - 35, ky = 960 + (Y(vals[8]) - 190 - 960) * 0.82 - 56;
      tl.to(kWrap, { x: kx, duration: 0.6, ease: "none" }, hopEnd - 0.6);
      tl.to(kWrap, { y: 560, duration: 0.3, ease: "power2.out" }, hopEnd - 0.6);
      tl.to(kWrap, { y: ky, duration: 0.3, ease: "power2.in" }, hopEnd - 0.3);
      tl.set(kWrap, { visibility: "hidden" }, EC - 0.45);

      // ================= end card =================
      L.flip(night, EC - 0.45);
      L.endCard(EC - 0.45, "Comment DEMO.", { anim: EC });
      L.captions({ hide: [["L2", "L2.1e+0.3"], ["L4", "L4e+1.2"]] });
      L.done();
    </script>
  </body>
</html>
