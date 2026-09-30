<!doctype html>
<html lang="en">
  <head>
    <!--HEAD-->
    <style>
      .wk-head { position: absolute; left: 72px; top: 262px; }
      .day { position: absolute; left: 72px; width: 132px; height: 108px; border-radius: 16px; background: var(--paper2); display: flex; flex-direction: column; align-items: center; justify-content: center; }
      .day small { font-family: var(--mono); font-weight: 600; font-size: 22px; letter-spacing: 0.08em; color: var(--ink-soft); }
      .day b { font-weight: 800; font-size: 44px; letter-spacing: -0.03em; line-height: 1; margin-top: 2px; }
      .cell { position: absolute; left: 222px; width: 708px; height: 108px; border-radius: 16px; }
      .cell.dash { border: 3px dashed rgba(71, 84, 103, 0.45); display: flex; align-items: center; padding-left: 28px; font-family: var(--mono); font-weight: 500; font-size: 24px; letter-spacing: 0.06em; color: rgba(71, 84, 103, 0.8); text-transform: uppercase; }
      .pcard { position: absolute; left: 222px; width: 708px; height: 108px; border-radius: 16px; background: #fff; border: 2.5px solid var(--ink); display: flex; align-items: center; gap: 18px; padding: 0 18px 0 12px; box-shadow: 6px 7px 0 rgba(16, 24, 40, 0.08); }
      .pcard .ill { width: 84px; height: 84px; border-radius: 12px; background: var(--paper2); flex: none; display: grid; place-items: center; }
      .pcard .cap { font-weight: 700; font-size: 26px; color: var(--ink); white-space: nowrap; border-radius: 6px; padding: 0 4px; margin-left: -4px; }
      .pcard .tags { display: flex; gap: 8px; margin-top: 8px; }
      .pcard .tags span, .pcard .time { font-family: var(--mono); font-weight: 600; font-size: 19px; color: var(--ink-soft); background: var(--paper2); border-radius: 8px; padding: 4px 9px; }
      .pcard .time { position: absolute; right: 16px; bottom: 14px; color: var(--indigo); }
      .pcard .ok { position: absolute; left: 74px; top: 4px; width: 38px; height: 38px; }
      .flap { position: absolute; width: 150px; height: 220px; border-radius: 18px; background: #1F2937; box-shadow: 0 16px 30px rgba(0, 0, 0, 0.45); overflow: hidden; }
      .flap span { position: absolute; inset: 0; display: grid; place-items: center; font-family: var(--mono); font-weight: 700; font-size: 170px; color: var(--paper); line-height: 1; }
      .flap::after { content: ""; position: absolute; left: 0; right: 0; top: 109px; height: 3px; background: rgba(0, 0, 0, 0.55); }
      .field { position: absolute; left: 72px; right: 150px; top: 760px; min-height: 190px; background: var(--paper2); border-radius: 20px; padding: 26px 30px; }
      .field .lab { font-family: var(--mono); font-weight: 600; font-size: 22px; letter-spacing: 0.08em; color: var(--ink-soft); margin-bottom: 12px; }
      .field .in { font-weight: 600; font-size: 44px; line-height: 1.25; color: var(--ink); }
    </style>
  </head>
  <body>
    <!--STAGE-->
    <script src="reward.js"></script>
    <script>
      const tl = L.init();
      window.__timelines = window.__timelines || {};
      window.__timelines["main"] = tl;
      const at = T.at, H = T.hook, EC = at("EC");
      const L1 = at("L1"), L2 = at("L2"), L3 = at("L3"), L4 = at("L4"), L5 = at("L5");
      const tCal = L1 + 0.9;      // the calendar slides up
      const tNight = L2 - 0.15;   // hard cut to 11:58 pm
      const tRip = at("L2e") + 0.6;

      // ================= HOOK · step stool, Christmas lights, a new SUV with a bow =================
      const hook = L.scene(0, tCal + 0.7, { bg: "#1D2D52", vignette: false });
      const shake = L.div("fill", hook.cam);
      shake.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920">
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#18264A"/><stop offset=".55" stop-color="#34507F"/><stop offset="1" stop-color="#7486AD"/></linearGradient>
          <radialGradient id="door" cx=".5" cy=".6" r=".7"><stop offset="0" stop-color="#FFE3A3"/><stop offset="1" stop-color="#F0A94A"/></radialGradient>
          <radialGradient id="glow"><stop offset="0" stop-color="#FFE6A8" stop-opacity=".9"/><stop offset="1" stop-color="#FFE6A8" stop-opacity="0"/></radialGradient>
          <linearGradient id="suv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#C9CFDB"/></linearGradient>
        </defs>
        <rect width="1080" height="1320" fill="url(#sky)"/>
        <g fill="#fff" opacity=".7"><circle cx="120" cy="140" r="2.5"/><circle cx="380" cy="90" r="2"/><circle cx="930" cy="170" r="2.5"/><circle cx="700" cy="60" r="2"/><circle cx="1000" cy="330" r="2"/></g>
        <g id="neighbors"></g>
        <rect x="250" y="520" width="660" height="800" fill="#4A566F"/>
        <g stroke="#56637C" stroke-width="3">${Array.from({ length: 18 }, (_, k) => `<line x1="250" y1="${560 + k * 42}" x2="910" y2="${560 + k * 42}"/>`).join("")}</g>
        <path d="M200 540 L580 330 L960 540 Z" fill="#262C3B"/>
        <rect x="200" y="530" width="760" height="22" fill="#1E2330"/>
        <rect x="510" y="620" width="150" height="280" fill="url(#door)"/>
        <rect x="330" y="640" width="120" height="140" fill="#F4C77A"/><rect x="720" y="640" width="120" height="140" fill="#F4C77A"/>
        <rect x="300" y="1030" width="150" height="170" fill="#F4C77A"/><rect x="720" y="1030" width="150" height="170" fill="#F4C77A"/>
        <g id="man">
          <g id="stool"><path d="M548 902 L560 820 L652 820 L664 902" fill="none" stroke="#2E9BD1" stroke-width="12" stroke-linejoin="round"/><rect x="546" y="808" width="120" height="20" rx="6" fill="#43B3E6"/></g>
          <rect x="572" y="690" width="26" height="122" rx="10" fill="#2E4A7A"/><rect x="612" y="690" width="26" height="122" rx="10" fill="#2E4A7A"/>
          <rect x="556" y="570" width="100" height="136" rx="30" fill="#7C8594"/>
          <rect x="560" y="470" width="24" height="120" rx="12" fill="#7C8594" transform="rotate(-10 572 580)"/><rect x="628" y="470" width="24" height="120" rx="12" fill="#7C8594" transform="rotate(10 640 580)"/>
          <circle cx="606" cy="548" r="34" fill="#3A2A20"/><path d="M572 560 Q606 590 640 560 L640 600 L572 600Z" fill="#6D7684"/>
        </g>
        <rect x="320" y="898" width="520" height="22" fill="#20263A"/>
        <g fill="#20263A"><rect x="320" y="812" width="520" height="12"/>${Array.from({ length: 14 }, (_, k) => `<rect x="${326 + k * 38}" y="820" width="8" height="80"/>`).join("")}</g>
        <g id="cat" transform="translate(770 760)"><path d="M0 52 C-6 20 8 8 22 8 C38 8 48 22 44 52 Z" fill="#D9822B"/><path d="M42 44 C70 40 72 18 58 12" fill="none" stroke="#D9822B" stroke-width="7" stroke-linecap="round"/><g id="catHead"><circle cx="20" cy="4" r="15" fill="#D9822B"/><path d="M8 -6 L10 -20 L18 -9Z M24 -9 L32 -20 L33 -6Z" fill="#D9822B"/></g></g>
        <g id="lightsHouse"></g>
        <path d="M0 1310 H1080 V1920 H0Z" fill="#D9DFEA"/>
        <path d="M330 1310 L750 1310 L1000 1920 L80 1920 Z" fill="#3A3F4B"/>
        <g fill="#FFFFFF" opacity=".75"><ellipse cx="140" cy="1360" rx="120" ry="14"/><ellipse cx="960" cy="1400" rx="110" ry="12"/><ellipse cx="60" cy="1700" rx="90" ry="12"/></g>
        <g id="suvG">
          <ellipse cx="545" cy="1668" rx="330" ry="26" fill="#1C1F26" opacity=".5"/>
          <path d="M230 1560 Q240 1470 330 1450 L410 1370 Q420 1356 440 1356 L680 1356 Q700 1356 712 1372 L790 1450 Q860 1468 866 1560 L866 1630 L230 1630Z" fill="url(#suv)"/>
          <path d="M428 1378 L670 1378 L740 1452 L360 1452Z" fill="#2A3445"/><line x1="550" y1="1378" x2="550" y2="1452" stroke="#fff" stroke-width="8"/>
          <rect x="256" y="1520" width="80" height="26" rx="10" fill="#FFF3C4"/><rect x="760" y="1520" width="80" height="26" rx="10" fill="#FFF3C4"/>
          <circle cx="330" cy="1640" r="46" fill="#1C1F26"/><circle cx="765" cy="1640" r="46" fill="#1C1F26"/>
          <g id="bow"><path d="M548 1356 C470 1250 420 1300 470 1340 C500 1360 530 1356 548 1356 C566 1356 596 1360 626 1340 C676 1300 626 1250 548 1356Z" fill="#D7263D"/><path d="M548 1356 L500 1420 M548 1356 L596 1420" stroke="#D7263D" stroke-width="18" stroke-linecap="round"/><circle cx="548" cy="1352" r="20" fill="#B21E33"/></g>
        </g>
        <g id="snow" fill="#FFFFFF" opacity=".85"></g>
      </svg>`;
      const hs = shake.querySelector("svg");
      const r = L.rng(3);
      {
        let n = "";
        [[-60, 860, 330], [790, 880, 330]].forEach(([x, y, w]) => {
          n += `<path d="M${x} ${y + 60} L${x + w / 2} ${y - 70} L${x + w} ${y + 60} Z" fill="#1E2740"/><rect x="${x + 20}" y="${y + 60}" width="${w - 40}" height="${1320 - y - 60}" fill="#2B3550"/>`;
          n += `<rect x="${x + 70}" y="${y + 130}" width="70" height="80" fill="#F2C06A"/><rect x="${x + w - 140}" y="${y + 130}" width="70" height="80" fill="#F2C06A"/>`;
          for (let k = 0; k < 9; k++) n += `<circle cx="${x + 30 + k * (w - 60) / 8}" cy="${y + 60 + Math.sin((k / 8) * Math.PI) * 18}" r="6" fill="${["#F5A623", "#E26D5A", "#6DBE8C", "#5B8DD6"][k % 4]}"/>`;
        });
        hs.querySelector("#neighbors").innerHTML = n;
        // warm lights: hung along the eave, then drooping loosely from his hands over the railing
        let lh = `<path d="M230 548 L600 548" stroke="#2A2A2A" stroke-width="3"/><path d="M600 480 Q720 700 850 812" stroke="#2A2A2A" stroke-width="3" fill="none"/>`;
        const bulb = (x, y) => `<circle class="glow" cx="${x}" cy="${y}" r="22" fill="url(#glow)"/><circle cx="${x}" cy="${y + 6}" r="7" fill="#FFE6A8"/>`;
        for (let k = 0; k <= 8; k++) lh += bulb(230 + k * 46, 548);
        for (let k = 1; k <= 6; k++) { const t = k / 7; const x = (1 - t) * (1 - t) * 600 + 2 * (1 - t) * t * 720 + t * t * 850; const y = (1 - t) * (1 - t) * 480 + 2 * (1 - t) * t * 700 + t * t * 812; lh += bulb(x, y); }
        hs.querySelector("#lightsHouse").innerHTML = lh;
        let s = "";
        for (let k = 0; k < 40; k++) s += `<circle class="flake" cx="${r() * 1080}" cy="${r() * 1920}" r="${2 + r() * 3}"/>`;
        hs.querySelector("#snow").innerHTML = s;
      }
      hs.querySelectorAll(".flake").forEach((f, k) => tl.fromTo(f, { y: -40 }, { y: 120 + (k % 5) * 20, x: ((k % 3) - 1) * 12, duration: 6, ease: "none" }, 0));
      // the stool wobbles harder and harder, then tilts
      const stool = hs.querySelector("#stool"), man = hs.querySelector("#man");
      gsap.set(stool, { transformOrigin: "50% 100%" });
      gsap.set(man, { transformOrigin: "606px 900px" });
      [[0.2, 3], [0.55, -4], [0.9, 5], [1.25, -6], [1.6, 7], [1.95, -8], [2.25, 9]].forEach(([t, a]) => {
        tl.to(stool, { skewX: a, duration: 0.32, ease: "sine.inOut" }, t);
        tl.to(man, { rotation: a * 0.45, duration: 0.32, ease: "sine.inOut" }, t);
      });
      tl.to(stool, { rotation: 16, skewX: 12, duration: 0.2, ease: "power2.in" }, 2.52);
      tl.to(man, { rotation: 11, x: 14, duration: 0.2, ease: "power2.in" }, 2.52);
      tl.to(hs.querySelector("#catHead"), { rotation: -28, transformOrigin: "20px 10px", duration: 0.25, ease: "power2.out" }, 1.2);
      // a clumsy late zoom toward the balcony, handheld
      gsap.set(hook.cam, { transformOrigin: "600px 760px" });
      tl.fromTo(hook.cam, { scale: 1 }, { scale: 1.16, duration: 0.8, ease: "power2.inOut" }, 1.6);
      L.handheld(shake, 0, H, 6, 9);
      tl.fromTo(shake, { filter: "blur(5px)" }, { filter: "blur(0px)", duration: 0.4 }, 0);
      L.aiChip(hook);
      // FREEZE: record scratch, a red circle around the car, the lights bloom
      L.flash(H);
      const zx = (x) => 600 + (x - 600) * 1.16, zy = (y) => 760 + (y - 760) * 1.16;
      const circWrap = L.div("fill", L.stage, "z-index:720;pointer-events:none;visibility:visible");
      const circ = L.svg(circWrap);
      L.circleMark(circ, zx(548), zy(1500), 360, 200, H + 0.12, 0.5, { color: "#C4320A", w: 10 });
      tl.to(hs.querySelectorAll(".glow"), { attr: { r: 40 }, duration: 0.6, ease: "sine.out" }, H + 0.3);
      L.drain(hook, L1 + 0.5, 0.5);

      // the lights leave the house and swing down over a paper calendar
      const lightsSvg = (id) => {
        let s = `<svg width="1080" height="200" viewBox="0 0 1080 200"><path d="M-20 30 Q540 150 1100 30" stroke="#2A2A2A" stroke-width="4" fill="none"/>`;
        for (let k = 0; k <= 16; k++) { const t = k / 16, x = -20 + t * 1120, y = 30 + 4 * t * (1 - t) * 120; s += `<circle class="${id}g" cx="${x}" cy="${y + 12}" r="26" fill="url(#glow2)"/><circle class="${id}b" cx="${x}" cy="${y + 16}" r="10" fill="#FFE6A8"/>`; }
        return s.replace(">", `><defs><radialGradient id="glow2${id}"><stop offset="0" stop-color="#FFE6A8" stop-opacity=".95"/><stop offset="1" stop-color="#FFE6A8" stop-opacity="0"/></radialGradient></defs>`).replaceAll("url(#glow2)", `url(#glow2${id})`) + "</svg>";
      };

      // ================= BEAT 1 · the calendar: every day says "no post yet" =================
      const week = [["MON", 21], ["TUE", 22], ["WED", 23], ["THU", 24], ["FRI", 25], ["SAT", 26], ["SUN", 27]];
      const rowT = (k) => 350 + k * 116;
      const buildWeek = (parent) => {
        L.div("wk-head", parent, "", `<div class="label" style="font-size:26px">DECEMBER · WEEK OF DEC 21</div>`);
        const cells = week.map(([d, n], k) => {
          L.div("day", parent, `top:${rowT(k)}px`, `<small>${d}</small><b>${n}</b>`);
          return L.div("cell dash", parent, `top:${rowT(k)}px`, "no post yet");
        });
        L.div("abs label", parent, "left:72px;top:1180px", "NEXT WEEK");
        L.div("day", parent, "top:1216px;height:90px", `<small>THU</small><b style="font-size:36px">31</b>`);
        const nextCell = L.div("cell dash", parent, "top:1216px;height:90px", "no post yet");
        return { cells, nextCell };
      };
      const cal = L.scene(tCal, tNight, { bg: "paper" });
      tl.fromTo(cal, { y: 1920 }, { y: 0, duration: 0.6, ease: "power3.out" }, tCal);
      const w1 = buildWeek(cal.cam);
      w1.cells.concat([w1.nextCell]).forEach((c) => (c.style.visibility = "hidden"));
      L.series(at("L1.2"), at("L1.2") + 0.6, 8).forEach((t, i) => { const c = w1.cells.concat([w1.nextCell])[i]; tl.set(c, { visibility: "visible" }, t); L.pop(c, t, { from: 0.9, dur: 0.25 }); });
      L.push(cal.cam, at("L1.2"), tNight, 1.06, { origin: "50% 40%" });
      const lights1 = L.div("abs", L.stage, "left:0;top:0;width:1080px;height:200px;z-index:710;visibility:hidden", lightsSvg("a"));
      tl.set(lights1, { visibility: "visible" }, tCal - 0.05);
      tl.fromTo(lights1, { x: 120, y: 470, scale: 0.55, rotation: 18, transformOrigin: "50% 0%" }, { x: 0, y: 80, scale: 1, rotation: 0, duration: 0.9, ease: "elastic.out(1, 0.55)" }, tCal - 0.05);
      tl.set(hs.querySelector("#lightsHouse"), { visibility: "hidden" }, tCal - 0.05);
      tl.set(lights1, { visibility: "hidden" }, tNight);
      // the red circle slides off the car and lands on Dec 24
      tl.to(circWrap, { x: 142 - zx(548) + 0, y: rowT(3) + 54 - zy(1500), scale: 0.3, transformOrigin: `${zx(548)}px ${zy(1500)}px`, duration: 0.55, ease: "power3.inOut" }, tCal + 0.55);
      tl.set(circWrap, { visibility: "hidden" }, tNight);

      // ================= BEAT 2 · 11:58 pm, still writing the caption =================
      const night = L.scene(tNight, tRip + 0.7, { bg: "radial-gradient(ellipse 70% 50% at 24% 18%, rgba(245,166,35,.30), rgba(245,166,35,0) 70%), radial-gradient(ellipse 80% 60% at 50% 50%, rgba(30,58,138,.35), rgba(17,24,39,0) 75%), #111827", grain: false });
      L.div("grain light", night);
      const flapX = [96, 262, 470, 636], digits = ["1", "1", "5", "8"];
      L.div("abs num", night.cam, "left:410px;top:430px;font-size:150px;color:var(--paper)", ":");
      const flaps = flapX.map((x, i) => {
        const f = L.div("flap", night.cam, `left:${x}px;top:400px`);
        const seq = [String((i * 3 + 4) % 10), String((i * 7 + 2) % 10), digits[i]];
        const spans = seq.map((d, j) => L.el("span", "", f, j ? "display:none" : "", d));
        const t0 = tNight + 0.05 + i * 0.1;
        spans.forEach((s, j) => { if (j) { tl.set(spans[j - 1], { display: "none" }, t0 + j * 0.1); tl.set(s, { display: "grid" }, t0 + j * 0.1); tl.fromTo(s, { rotationX: -80, transformPerspective: 600 }, { rotationX: 0, duration: 0.1, ease: "power2.out" }, t0 + j * 0.1); } });
        L.pop(f, tNight + i * 0.05, { from: 0.8, dur: 0.25 });
        f.spans = spans;
        return f;
      });
      L.div("abs num", night.cam, "left:810px;top:520px;font-size:64px;color:var(--sky)", "PM");
      const tStill = at("L2.2:still");
      const nine = L.el("span", "", flaps[3], "display:none", "9");
      tl.set(flaps[3].spans[2], { display: "none" }, tStill);
      tl.set(nine, { display: "grid" }, tStill);
      tl.fromTo(nine, { rotationX: -80, transformPerspective: 600 }, { rotationX: 0, duration: 0.15, ease: "power2.out" }, tStill);
      const field = L.div("field", night.cam, "", `<div class="lab">CAPTION</div>`);
      L.rise(field, tNight + 0.3, { y: 30 });
      const typed = L.type(field, "New holiday collection is here, DM for pri", L2 + 0.3, 41 / Math.max(1.5, tStill - 0.5 - (L2 + 0.3)), { el: L.div("in", field), cursor: true, cursorUntil: tRip });
      L.backspace(typed, 11, tStill, 18);
      // crumpled paper ball rolls in; a coffee-mug ring in the corner
      const ball = L.div("abs", night.cam, "left:130px;top:1110px;width:130px;height:120px", `<svg width="130" height="120" viewBox="0 0 130 120"><path d="M20 70 L10 44 L34 16 L66 8 L98 20 L120 50 L112 86 L84 110 L44 112 Z" fill="#EFECE3" stroke="#B9B3A6" stroke-width="3"/><path d="M34 16 L52 52 L98 20 M52 52 L44 112 M52 52 L112 86 M10 44 L52 52" stroke="#C9C3B5" stroke-width="3" fill="none"/></svg>`);
      tl.fromTo(ball, { x: -400, rotation: -360 }, { x: 0, rotation: 0, duration: 0.9, ease: "power3.out" }, at("L2.2") + 0.2);
      L.div("abs", night.cam, "left:40px;top:1530px;width:180px;height:180px;border-radius:50%;border:9px solid rgba(160,110,60,.28)");
      const plan = L.div("btn", night.cam, "left:340px;top:1160px", "Plan this week");
      L.rise(plan, at("L2e") + 0.1, { y: 60, dur: 0.4 });
      tl.to(plan, { scale: 0.94, duration: 0.08 }, at("L2e") + 0.55);
      tl.to(plan, { scale: 1, duration: 0.15 }, at("L2e") + 0.63);

      // ================= BEAT 3 to 5 · the week fills in one tap =================
      const sc = L.scene(tRip, null, { bg: "paper" });
      L.ripple(sc, tRip, 540, 1206);
      const calWrap = L.div("fill", sc.cam);
      const w2 = buildWeek(calWrap);
      tl.fromTo(calWrap, { opacity: 0.25, scale: 0.94 }, { opacity: 1, scale: 1, duration: 0.7, ease: "power2.inOut" }, at("L3e") - 0.6);
      tl.set(calWrap, { opacity: 0.25 }, tRip);
      const lights2 = L.div("abs", sc.cam, "left:0;top:80px;width:1080px;height:200px", lightsSvg("b"));
      const ring24 = L.svg(sc.cam);
      L.circleMark(ring24, 142, rowT(3) + 54, 104, 60, null, 0, { color: "#C4320A", w: 8 });
      // the phone with the rebuilt planner, then it steps aside
      const ph = L.phone(sc.cam, { x: 330, y: 400, w: 420, crumb: "Social planner" });
      tl.fromTo(ph, { y: 120, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.5, ease: "power3.out" }, tRip + 0.2);
      L.div("app-h1", ph.body, "", "This week");
      const prow = week.map(([d, n], k) => L.div("app-card", ph.body, "padding:10px 12px;margin-bottom:8px;display:flex;align-items:center;gap:10px;font-size:13px", `<b style="font-family:var(--mono);font-size:11px;color:#6B6B73;width:46px">${d} ${n}</b><span style="width:28px;height:28px;border-radius:7px;background:#EFECE3"></span><span style="font-weight:600">Post planned</span><span style="margin-left:auto;font-family:var(--mono);font-size:11px;color:#0B6FE6">${k % 2 ? "12:30 PM" : "7:00 PM"}</span>`));
      L.series(L3 + 0.3, L3 + 1.5, 7).forEach((t, k) => L.rise(prow[k], t, { y: 14, dur: 0.3 }));
      tl.to(ph, { x: 440, y: 1120, scale: 0.62, duration: 0.7, ease: "power3.inOut" }, at("L3e") - 0.6);

      // Beat 4 · seven post cards deal into the seven days
      const ICONS = {
        candle: `<rect x="22" y="30" width="36" height="40" rx="6" fill="#E8DCC8" stroke="#101828" stroke-width="3"/><path d="M40 12 C48 20 46 28 40 28 C34 28 32 20 40 12Z" fill="#F5A623"/><line x1="40" y1="28" x2="40" y2="32" stroke="#101828" stroke-width="3"/>`,
        dress: `<path d="M32 12 L48 12 L50 26 L62 68 L18 68 L30 26 Z" fill="#9CAF94" stroke="#101828" stroke-width="3" stroke-linejoin="round"/><path d="M30 26 L50 40" stroke="#101828" stroke-width="3"/>`,
        hoops: `<circle cx="28" cy="44" r="16" fill="none" stroke="#D4A640" stroke-width="6"/><circle cx="54" cy="44" r="16" fill="none" stroke="#D4A640" stroke-width="6"/>`,
        perfume: `<rect x="22" y="30" width="36" height="40" rx="8" fill="#F3D9CF" stroke="#101828" stroke-width="3"/><rect x="33" y="14" width="14" height="16" rx="3" fill="#D4A640" stroke="#101828" stroke-width="3"/>`,
        scarf: `<path d="M16 22 C30 14 50 30 64 20 L64 34 C50 44 30 28 16 36 Z" fill="#C4633A" stroke="#101828" stroke-width="3"/><path d="M48 34 L44 66 L56 66 L60 30" fill="#C4633A" stroke="#101828" stroke-width="3" stroke-linejoin="round"/>`,
        sweater: `<path d="M28 14 L52 14 L68 26 L62 40 L56 36 L56 68 L24 68 L24 36 L18 40 L12 26 Z" fill="#D3A1A0" stroke="#101828" stroke-width="3" stroke-linejoin="round"/>`,
        tote: `<path d="M18 30 L62 30 L58 70 L22 70 Z" fill="#E8C98E" stroke="#101828" stroke-width="3" stroke-linejoin="round"/><path d="M30 30 C30 12 50 12 50 30" fill="none" stroke="#101828" stroke-width="3"/>`,
      };
      const posts = [
        ["candle", "Last day for Christmas delivery", "#giftideas", "7:00 PM"],
        ["dress", "Wrap it or wear it?", "#holidaystyle", "12:30 PM"],
        ["hoops", "Hoops for every party this month", "#giftideas", "7:00 PM"],
        ["perfume", "A scent for the holidays", "#giftsforher", "12:30 PM"],
        ["scarf", "The scarf that makes the coat", "#holidaystyle", "7:00 PM"],
        ["sweater", "Softest sweater we've ever stocked", "#giftideas", "12:30 PM"],
        ["tote", "The tote that fits the whole weekend", "#weekendbag", "7:00 PM"],
      ];
      const pcards = posts.map(([ic, cap, tag, time], k) => L.div("pcard", calWrap, `top:${rowT(k)}px`,
        `<div class="ill"><svg width="70" height="70" viewBox="0 0 80 80">${ICONS[ic]}</svg></div><div><div class="cap">${cap}</div><div class="tags"><span>${tag}</span><span>#shopsmall</span></div></div><div class="time">${time}</div><svg class="ok" viewBox="0 0 38 38" style="visibility:hidden"><circle cx="19" cy="19" r="18" fill="#34D399"/><path d="M10 20 L16 26 L28 13" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`));
      L.series(L4 - 0.1, L4 + 1.4, 7).forEach((t, k) => {
        tl.fromTo(pcards[k], { x: 700, rotation: 8, autoAlpha: 0 }, { x: 0, rotation: 0, autoAlpha: 1, duration: 0.35, ease: "power3.out" }, t);
        tl.set(w2.cells[k], { visibility: "hidden" }, t + 0.3);
      });
      const pulse = (sel, t) => tl.fromTo(calWrap.querySelectorAll(sel), { backgroundColor: "rgba(245,166,35,0)" }, { backgroundColor: "rgba(245,166,35,0.75)", duration: 0.18, yoyo: true, repeat: 1, stagger: 0.04 }, t);
      pulse(".pcard .cap", at("L4.1:captions"));
      pulse(".pcard .tags span", at("L4.1:hashtags"));
      pulse(".pcard .time", at("L4.1:times"));
      L.stamp(calWrap, "CHRISTMAS", at("L4.2:christmas"), { x: 600, y: rowT(3) + 20, color: "leak", size: 44, r: -7 });
      tl.set(w2.nextCell, { visibility: "hidden" }, at("L4.2:year"));
      L.div("pcard", calWrap, "top:1216px;height:90px", `<div style="font-weight:700;font-size:28px;padding-left:10px">New Year campaign · planned</div>`).style.visibility = "hidden";
      tl.set(calWrap.lastElementChild, { visibility: "visible" }, at("L4.2:year") - 0.05);
      L.stamp(calWrap, "NEW YEAR", at("L4.2:year"), { x: 640, y: 1226, color: "indigo", size: 40, r: 6 });

      // Beat 5 · approve: the stamp, the checks cascade, the lights come fully on
      const appr = L.div("btn", sc.cam, "left:640px;top:250px;font-size:32px;padding:18px 30px", "Approve week");
      L.rise(appr, L5 + 0.05, { y: 30, dur: 0.35 });
      tl.to(appr, { scale: 0.94, duration: 0.08 }, L5 + 0.5);
      tl.to(appr, { scale: 1, duration: 0.15 }, L5 + 0.58);
      const tr = L.svg(sc.cam);
      const tapR = L.s(tr, "circle", { cx: 790, cy: 290, r: 10, fill: "none", stroke: "#F5A623", "stroke-width": 8 }, "visibility:hidden");
      tl.set(tapR, { visibility: "visible" }, L5 + 0.5);
      tl.fromTo(tapR, { attr: { r: 10 }, opacity: 1 }, { attr: { r: 170 }, opacity: 0, duration: 0.5, ease: "power2.out" }, L5 + 0.5);
      L.stamp(sc.cam, "APPROVED", L5 + 0.65, { x: 200, y: 640, color: "indigo", size: 104, r: 6 });
      L.series(L5 + 0.95, L5 + 1.65, 7).forEach((t, k) => { const ok = pcards[k].querySelector(".ok"); tl.set(ok, { visibility: "visible" }, t); L.pop(ok, t, { from: 0.2, dur: 0.3 }); });
      // bulbs twinkle slightly out of sync, then all come fully on
      const bulbs = lights2.querySelectorAll(".bb"), glows = lights2.querySelectorAll(".bg");
      glows.forEach((g, k) => { const t0 = tRip + 0.3 + (k % 5) * 0.23; for (let i = 0; i < 8; i++) tl.set(g, { opacity: i % 2 ? 1 : 0.35 }, t0 + i * 0.6); });
      tl.set(glows, { opacity: 1 }, L5 + 1.8);
      tl.to(glows, { attr: { r: 36 }, duration: 0.5, ease: "sine.out" }, L5 + 1.8);
      L.drift(lights2, tRip, EC, { period: 5, y: 6, x: 0, r: 0.6 });

      // ================= end card =================
      L.flip(sc, EC - 0.45);
      const ecScene = L.endCard(EC - 0.45, "Comment WEEK.", { anim: EC });
      gsap.set(ecScene.cam, { y: 30 }); // a little room for the Attention Legend card above the logo

      // ================= ATTENTION SPAN LEADERBOARD =================
      // Opens as a full-screen "ATTENTION TEST" card (the pre-roll) that lands as the meter.
      // Top 100% at the start; one tier per story beat; Top 0.01% for watching to the very end.
      const focusSecs = Math.round(T.total);
      const tBar = L.attentionTest({ top: 140, secs: focusSecs });
      L.attention({
        start: tBar,
        enter: "fade",
        top: 140,
        times: [H + 0.1, L2, L3, L4, at("L4.2:christmas"), L5, EC + 0.6],
        labels: [
          { t: 1.25, until: 2.45, text: `${focusSecs}s OF FOCUS · TOP 0.01%`, color: "#A9C1F5" },
          { t: at("L4.2:christmas") + 1.5, until: L5 - 0.1, text: "DON'T BREAK THE STREAK", color: "#F08A63" },
          { t: EC - 1.25, until: EC - 0.05, text: "HOLD YOUR FOCUS", color: "#FFD66B" },
        ],
        countdown: EC - 0.9,
      });
      L.legend(EC + 0.6, { hold: T.total - EC, top: 264, sub: `${focusSecs} seconds of unbroken focus. Rank resets next reel. Follow and go longer.` });
      L.captions({ hide: [["L1.2", "L1e+0.3"]] });
      L.done();
    </script>
  </body>
</html>
