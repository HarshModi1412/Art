<!doctype html>
<html lang="en">
  <head>
    <!--HEAD-->
    <style>
      .post { position: absolute; left: 250px; top: 420px; width: 580px; height: 860px; border-radius: 28px; border: 4px solid var(--ink); background: #fff; overflow: hidden; }
      .post .img { position: absolute; left: 22px; right: 22px; top: 22px; height: 560px; border-radius: 18px; background: var(--paper2); display: grid; place-items: center; }
      .post .cap { position: absolute; left: 30px; top: 610px; font-weight: 800; font-size: 50px; color: var(--ink); white-space: nowrap; }
      .plate { position: absolute; background: #F3E9D2; border: 3px solid #5B4A2A; border-radius: 6px; font-family: var(--sans); font-weight: 900; letter-spacing: 0.08em; color: #3B2F1A; display: grid; place-items: center; }
      .step { position: absolute; left: 150px; width: 780px; height: 140px; border-radius: 26px; background: var(--paper2); border: 3px solid var(--ink); display: flex; align-items: center; gap: 30px; padding: 0 34px; }
      .step b { font-family: var(--mono); font-weight: 700; font-size: 56px; color: var(--indigo); width: 50px; }
      .step span { font-weight: 700; font-size: 50px; color: var(--ink); }
      .tile { position: absolute; top: 820px; width: 260px; height: 330px; border-radius: 26px; background: #fff; border: 3px solid var(--ink); box-shadow: 8px 10px 0 rgba(16, 24, 40, 0.08); }
      .tile .lab { position: absolute; left: 0; right: 0; bottom: -84px; text-align: center; font-weight: 800; font-size: 54px; letter-spacing: -0.03em; }
      .szc { display: inline-block; font-family: var(--mono); font-weight: 700; font-size: 20px; border: 2px solid var(--ink); border-radius: 8px; padding: 3px 7px; margin: 2px; }
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
      const tSting = at("L2e") + 0.2;
      const tRx = at("L8") - 0.3;

      // ================= HOOK · through a cafe window: a man pushes a PULL door, three times =================
      const hook = L.scene(0, at("L1.2") + 1.2, { bg: "#6E5A48", vignette: false });
      const shake = L.div("fill", hook.cam);
      shake.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920">
        <defs><pattern id="brick" width="80" height="40" patternUnits="userSpaceOnUse"><rect width="80" height="40" fill="#B7654B"/><rect x="2" y="2" width="76" height="16" fill="#C2715A"/><rect x="-38" y="22" width="76" height="16" fill="#BE6C54"/><rect x="42" y="22" width="76" height="16" fill="#C4755D"/></pattern>
        <pattern id="awn" width="60" height="10" patternUnits="userSpaceOnUse"><rect width="30" height="10" fill="#2F6B55"/><rect x="30" width="30" height="10" fill="#F3EDE0"/></pattern>
        <radialGradient id="foam" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#F7E7CF"/><stop offset=".7" stop-color="#D8B386"/><stop offset="1" stop-color="#A9784B"/></radialGradient></defs>
        <g id="street" style="filter:blur(1.6px)">
          <rect width="1080" height="1920" fill="#9FB3C6"/>
          <rect x="60" y="250" width="960" height="1000" fill="url(#brick)"/>
          <path d="M40 470 H1040 L1000 560 H80 Z" fill="url(#awn)"/>
          <rect x="120" y="640" width="380" height="440" fill="#35505C"/><rect x="130" y="650" width="360" height="420" fill="#7FA0B0" opacity=".55"/>
          <g id="door"><rect x="560" y="610" width="250" height="600" fill="#2F4A3A"/><rect x="580" y="630" width="210" height="560" fill="#8FB1C2" opacity=".7"/><rect x="600" y="880" width="170" height="14" rx="7" fill="#C9CFD6"/>
            <g id="plateG"><rect x="636" y="820" width="96" height="46" rx="5" fill="#F3E9D2" stroke="#5B4A2A" stroke-width="3"/><text x="684" y="852" text-anchor="middle" font-family="Inter,sans-serif" font-weight="900" font-size="26" fill="#3B2F1A" letter-spacing="2">PULL</text></g></g>
          <rect x="0" y="1210" width="1080" height="300" fill="#8C9096"/>
          <g id="man"><rect x="-26" y="-190" width="20" height="190" rx="9" fill="#C7A77A"/><rect x="6" y="-190" width="20" height="190" rx="9" fill="#B89868"/>
            <rect x="-44" y="-420" width="88" height="250" rx="30" fill="#2B3A5C"/><rect id="armM" x="10" y="-390" width="120" height="26" rx="13" fill="#24324F"/>
            <circle cx="0" cy="-460" r="40" fill="#5A3A22"/></g>
        </g>
        <path d="M0 0 H1080 V1920 H0 Z M80 80 V1440 H1000 V80 Z" fill="#5C4633" fill-rule="evenodd"/>
        <rect x="0" y="1440" width="1080" height="480" fill="#7A5B40"/><rect x="0" y="1440" width="1080" height="18" fill="#8C6A4B"/>
        <g opacity=".25" fill="#fff"><polygon points="140,100 260,100 60,900 0,900"/><polygon points="700,90 760,90 520,1000 480,1000"/></g>
        <ellipse cx="540" cy="1720" rx="240" ry="48" fill="#E9E4DA"/><path d="M380 1580 H700 L670 1720 Q540 1760 410 1720 Z" fill="#F7F4EE"/><ellipse cx="540" cy="1582" rx="160" ry="36" fill="url(#foam)"/>
        <path d="M745 1620 C810 1620 810 1690 740 1690" fill="none" stroke="#F7F4EE" stroke-width="20"/>
        <g fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".4"><path id="steam1" d="M500 1520 C480 1480 520 1450 500 1410"/><path id="steam2" d="M580 1520 C560 1470 600 1440 580 1400"/></g>
      </svg>`;
      const hs = shake.querySelector("svg"), man = hs.querySelector("#man"), door = hs.querySelector("#door"), armM = hs.querySelector("#armM");
      gsap.set(man, { x: -150, y: 1215 });
      tl.to(man, { x: 470, duration: 0.8, ease: "power1.out" }, 0);
      [1.0, 1.7, 2.4].forEach((t, i) => {
        tl.to(man, { rotation: 7, x: 490, transformOrigin: "0px 0px", duration: 0.12, ease: "power2.out" }, t - 0.12);
        tl.to(armM, { x: 22, duration: 0.12 }, t - 0.12);
        if (i < 2) { tl.to(man, { rotation: 0, x: 470, duration: 0.3, ease: "power1.inOut" }, t + 0.15); tl.to(armM, { x: 0, duration: 0.3 }, t + 0.15); }
        L.shake(door, t, 8, 0.25);
      });
      tl.fromTo(hs.querySelectorAll("#steam1,#steam2"), { y: 0, opacity: 0.4 }, { y: -60, opacity: 0.1, duration: 2.6, ease: "none", stagger: 0.4 }, 0);
      L.handheld(shake, 0, H - 0.05, 4, 51);
      tl.to(shake, { x: 0, y: 0, rotation: 0, duration: 0.05 }, H - 0.05);
      L.aiChip(hook);
      L.flash(H);
      L.drain(hook, H + 0.07, 0.6);
      const hk = L.svg(hook.cam);
      L.circleMark(hk, 684, 843, 80, 46, H + 0.1, 0.45);
      L.ink(hk, "M560 1210 V610 H810 V1210", H + 0.55, 0.6, { w: 8 });

      // ================= BEAT 1 · the door becomes a post with a push door in it =================
      const b1 = L.scene(H + 1.1, tSting + 0.1, { bg: "paper" });
      L.fadeIn(b1, H + 1.1, 0.4);
      const ov = L.svg(b1.cam);
      const frame = L.s(ov, "rect", { x: 560, y: 610, width: 250, height: 600, rx: 4, fill: "none", stroke: "#F5A623", "stroke-width": 8 });
      const tMorph = at("L1.2") - 0.1;
      tl.to(frame, { attr: { x: 250, y: 420, width: 580, height: 860, rx: 28 }, duration: 0.6, ease: "power3.inOut" }, tMorph);
      const post = L.div("post", b1.cam, "", `<div class="img"><svg width="260" height="320" viewBox="0 0 80 80"><path d="M32 12 L48 12 L50 26 L62 68 L18 68 L30 26 Z" fill="#9CAF94" stroke="#101828" stroke-width="2.5" stroke-linejoin="round"/><path d="M30 26 L50 40" stroke="#101828" stroke-width="2.5"/></svg></div>`);
      L.fadeIn(post, tMorph + 0.5, 0.3);
      tl.to(frame, { autoAlpha: 0, duration: 0.2 }, tMorph + 0.7);
      const plate = L.div("plate", b1.cam, "left:636px;top:820px;width:96px;height:46px;font-size:26px", "PULL");
      tl.to(plate, { x: -356, y: 385, scale: 1.25, duration: 0.6, ease: "power3.inOut" }, tMorph);
      tl.to(plate, { autoAlpha: 0, duration: 0.15 }, tMorph + 0.6);
      const cap = L.div("cap", post, "", "DM for price");
      L.fadeIn(cap, tMorph + 0.6, 0.2);
      cap.innerHTML = `<span class="hl"><i></i>DM for price</span>`;
      L.hl(post, at("L2"));
      // a small ink arrow labelled "push" bumps against it, three times
      const arr = L.div("abs", b1.cam, "left:60px;top:1010px;width:200px;height:90px", `<svg width="200" height="90" viewBox="0 0 200 90"><path d="M10 60 H170 M140 36 L172 60 L140 84" fill="none" stroke="#1E3A8A" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg><div class="hand" style="position:absolute;left:30px;top:-6px;font-size:40px;color:var(--indigo)">push</div>`);
      L.fadeIn(arr, at("L2"), 0.2);
      [0.3, 0.75, 1.2].forEach((d, i) => {
        const t = at("L2") + d;
        tl.to(arr, { x: 36, duration: 0.12, ease: "power2.in" }, t - 0.12);
        tl.to(arr, { x: 0, duration: 0.25, ease: "back.out(2)" }, t);
        const sc = L.div("abs", b1.cam, `left:262px;top:${1040 + i * 18}px;width:22px;height:4px;background:var(--ink);opacity:.5;transform:rotate(${-30 + i * 25}deg);visibility:hidden`);
        tl.set(sc, { visibility: "visible" }, t);
      });

      // ================= the Shop Doctor sting (in the voice pause) =================
      L.sting(tSting, "EP 01");

      // ================= BEAT 2 to 5 · the corridor, the seven steps, the fix =================
      const L3 = at("L3"), L4 = at("L4"), L5 = at("L5"), L6 = at("L6"), L7 = at("L7");
      const b2 = L.scene(tSting + 1.6, tRx + 0.5, { bg: "paper" });
      // pop-up corridor of seven paper doors, receding to the center
      const cor = L.div("fill", b2.cam);
      const VP = { x: 540, y: 900 };
      const doors = [];
      // walls and floor lines converging on the far door
      const csv = L.svg(cor);
      const fr = (k) => { const s = Math.pow(0.74, k); return { s, w: 520 * s, h: 900 * s, x: VP.x - 260 * s, y: VP.y - 450 * s }; };
      const f0 = fr(0), f6 = fr(6);
      [[f0.x, f0.y, f6.x, f6.y], [f0.x + f0.w, f0.y, f6.x + f6.w, f6.y], [f0.x, f0.y + f0.h, f6.x, f6.y + f6.h], [f0.x + f0.w, f0.y + f0.h, f6.x + f6.w, f6.y + f6.h]].forEach(([a, b, c2, d2]) => L.s(csv, "line", { x1: a, y1: b, x2: c2, y2: d2, stroke: "#101828", "stroke-width": 3, opacity: 0.5 }));
      L.s(csv, "polygon", { points: `${f0.x},${f0.y + f0.h} ${f0.x + f0.w},${f0.y + f0.h} ${f6.x + f6.w},${f6.y + f6.h} ${f6.x},${f6.y + f6.h}`, fill: "rgba(239,236,227,.8)" });
      for (let k = 6; k >= 0; k--) {
        const { s, w, h, x, y } = fr(k);
        const d = L.div("abs", cor, `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border:${Math.max(2, 6 * s)}px solid var(--ink)`);
        const leaf = L.div("abs", d, `left:0;top:0;width:100%;height:100%;background:${["#F1E7D3", "#EFE2C8", "#F3EAD8", "#ECDDC2", "#F2E6CF", "#EEE0C6", "#F4ECDC"][k]};border:${Math.max(1, 3 * s)}px solid var(--ink);transform-origin:0 50%`);
        if (k < 6) gsap.set(leaf, { rotationY: -62, transformPerspective: 1000 });
        L.div("abs", d, `left:50%;top:${-40 * s}px;transform:translateX(-50%);font-family:var(--mono);font-weight:700;font-size:${Math.max(14, 40 * s)}px;color:var(--indigo);background:#fff;border:${Math.max(1, 3 * s)}px solid var(--ink);border-radius:${6 * s}px;padding:0 ${8 * s}px`, String(k + 1));
        doors[k] = leaf;
      }
      tl.fromTo(cor, { scaleY: 0.05, autoAlpha: 0 }, { scaleY: 1, autoAlpha: 1, duration: 0.5, ease: "back.out(1.5)", transformOrigin: "50% 100%" }, L3 - 0.1);
      tl.to(cor, { scale: 2.4, duration: at("L3e") - L3 + 0.5, ease: "power1.in", transformOrigin: `${VP.x}px ${VP.y}px` }, L3 + 0.3);
      L.series(L3 + 0.4, at("L3e"), 5).forEach((t, i) => tl.to(doors[i], { rotationY: -88, duration: 0.45, ease: "power2.inOut" }, t));
      // shopper dots walk in; some peel off at each door
      for (let k = 0; k < 12; k++) {
        const dot = L.div("abs", cor, `left:${VP.x - 12 + ((k % 4) - 1.5) * 60}px;top:${VP.y + 360}px;width:24px;height:24px;border-radius:50%;background:var(--ink)`);
        const peel = k % 3 === 0;
        tl.fromTo(dot, { y: 0, scale: 1, autoAlpha: 0 }, { y: -360, scale: 0.3, autoAlpha: 1, duration: 2.4, ease: "none" }, L3 + k * 0.12);
        if (peel) tl.to(dot, { x: (k % 2 ? 1 : -1) * 260, y: "-=200", autoAlpha: 0, duration: 0.6, ease: "power1.out" }, L3 + 0.8 + k * 0.1);
      }
      const want = L.div("abs headline", b2.cam, "left:72px;top:276px;font-size:76px", "I want it");
      const bought = L.div("abs headline", b2.cam, "left:560px;top:1280px;font-size:76px", "I bought it");
      L.slam(want, at("L3:want")); L.slam(bought, at("L3:bought"));
      tl.to([cor, want, bought], { autoAlpha: 0, duration: 0.3 }, L4 - 0.1);
      // Beat 3 · the doors fold flat into seven numbered step cards
      const stepsTxt = ["See the post", "Send a DM", "Wait for a reply", "Ask about sizes", "Wait again", "Get a link", "Pay"];
      const stackWrap = L.div("fill", b2.cam);
      const stack = L.div("fill", stackWrap);
      const steps = stepsTxt.map((s, i) => {
        const el = L.div("step", stack, `top:${280 + i * 168}px`, `<b>${i + 1}</b><span>${s}</span>`);
        if (i === 2 || i === 4) L.markup(el, `<svg style="margin-left:auto" width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" fill="#fff" stroke="#101828" stroke-width="4"/><line class="hand1" x1="32" y1="32" x2="32" y2="12" stroke="#101828" stroke-width="4" stroke-linecap="round"/><line x1="32" y1="32" x2="46" y2="32" stroke="#C4320A" stroke-width="4" stroke-linecap="round"/></svg>`);
        return el;
      });
      stepsTxt.forEach((_, i) => {
        const t = at(`L4.${i + 2}`);
        tl.fromTo(steps[i], { x: 700, rotation: 6, autoAlpha: 0 }, { x: 0, rotation: 0, autoAlpha: 1, duration: 0.35, ease: "power3.out" }, t);
        const hand = steps[i].querySelector(".hand1");
        if (hand) tl.fromTo(hand, { rotation: 0 }, { rotation: 720, svgOrigin: "32 32", duration: 1.6, ease: "none" }, t);
        if (i >= 5) {
          tl.to(stack, { y: -(i - 4) * 168, duration: 0.35, ease: "power2.inOut" }, t);
          tl.to(steps[i - 5], { autoAlpha: 0, duration: 0.25 }, t); // cards scrolled up to the leaderboard bar fade out
        }
      });
      // Beat 4 · SEVEN
      const seven = L.div("abs num leak", b2.cam, "left:430px;top:1110px;font-size:260px", "7");
      L.slam(seven, L5);
      L.shake(stackWrap, L5 + 0.05, 16, 0.3);
      L.rise(L.div("abs label", b2.cam, "left:300px;top:1380px;font-size:28px;width:480px;text-align:center", "chances to change their mind"), at("L5.2"));
      tl.to(stackWrap, { scaleY: 0.1, autoAlpha: 0, transformOrigin: "50% 60%", duration: 0.4, ease: "power2.in" }, L6);
      tl.to([seven, b2.cam.querySelector(".label")], { autoAlpha: 0, duration: 0.3 }, L6);
      // Beat 5 · six doors slam shut, one wide door stays open; three tiles
      const row = L.div("fill", b2.cam);
      const dsv = L.svg(row);
      for (let k = 0; k < 7; k++) {
        const x = 90 + k * 128, wide = k === 3;
        L.s(dsv, "rect", { x, y: 300, width: 110, height: 250, fill: "#EFE2C8", stroke: "#101828", "stroke-width": 4 });
        const leaf = L.div("abs", row, `left:${x}px;top:300px;width:110px;height:250px;background:${wide ? "rgba(245,166,35,.25)" : "#E2D2B2"};border:4px solid var(--ink);transform-origin:0 50%`);
        if (!wide) tl.fromTo(leaf, { rotationY: -80, transformPerspective: 900 }, { rotationY: 0, duration: 0.18, ease: "power4.in" }, L6 + 0.3 + [0, 1, 2, -1, 3, 4, 5][k] * 0.2);
        else L.markup(row, `<svg class="abs" style="left:${x - 60}px;top:540px" width="230" height="260" viewBox="0 0 230 260"><polygon points="60,0 170,0 230,260 0,260" fill="rgba(245,166,35,.28)"/></svg>`);
      }
      L.fadeIn(row, L6, 0.3);
      const tiles = [0, 1, 2].map((i) => L.div("tile", b2.cam, `left:${72 + i * 280}px`));
      tiles.forEach((t, i) => L.pop(t, L6 + 0.2 + i * 0.1, { from: 0.6 }));
      L.markup(tiles[0], `<div style="position:absolute;left:18px;right:18px;top:18px;height:170px;border-radius:14px;background:var(--paper2);display:grid;place-items:center"><svg width="110" height="140" viewBox="0 0 80 80"><path d="M32 12 L48 12 L50 26 L62 68 L18 68 L30 26 Z" fill="#9CAF94" stroke="#101828" stroke-width="3" stroke-linejoin="round"/></svg></div>`);
      const priceChip = L.div("abs", tiles[0], "left:18px;top:200px;font-family:var(--mono);font-weight:700;font-size:34px;background:var(--marigold);border-radius:10px;padding:4px 12px", "$68");
      const sizes = L.div("abs", tiles[0], "left:14px;top:260px", `<span class="szc">S</span><span class="szc">M</span><span class="szc">L</span><span class="szc">XL</span>`);
      L.pop(priceChip, at("L6.2:price")); L.pop(sizes, at("L6.3:sizes"));
      const tapIc = L.markup(tiles[1], `<svg class="abs" style="left:40px;top:50px" width="180" height="220" viewBox="0 0 180 220"><circle class="rp" cx="90" cy="70" r="60" fill="none" stroke="#F5A623" stroke-width="6"/><path d="M78 60 V150 M78 60 C78 44 102 44 102 60 V120 M102 100 C102 88 124 88 124 100 V130 M124 110 C124 98 146 98 146 110 V160 C146 196 120 214 92 214 C66 214 52 196 44 176 L28 138 C22 124 40 116 50 128 L78 160" fill="#F7E3D2" stroke="#101828" stroke-width="5" stroke-linejoin="round"/></svg>`);
      const link = L.div("abs", tiles[1], "left:18px;top:18px;font-family:var(--mono);font-weight:700;font-size:22px;color:var(--indigo)", "checkout link");
      L.pop(link, at("L6.4:link"));
      const check = L.markup(tiles[2], `<svg class="abs" style="left:40px;top:70px" width="180" height="180" viewBox="0 0 180 180"><circle cx="90" cy="90" r="84" fill="#34D399"/><path d="M48 94 L78 122 L134 60" fill="none" stroke="#fff" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/></svg>`);
      tl.fromTo(tapIc.querySelector(".rp"), { attr: { r: 20 }, opacity: 1 }, { attr: { r: 86 }, opacity: 0, duration: 0.5, ease: "power2.out" }, at("L7.3"));
      L.pop(check, at("L7.4"), { from: 0.2 });
      ["See it.", "Tap it.", "Buy it."].forEach((s, i) => L.slam(L.div("lab", tiles[i], "", s), at(`L7.${i + 2}`)));
      L.rise(L.div("abs label", b2.cam, "left:72px;top:1300px;font-size:28px", "3 steps"), at("L7.1"));
      L.chip(b2.cam, "EXAMPLE", "left:800px;top:760px", L6 + 0.5);

      // ================= prescription + Friday card =================
      L.rxPad(tRx, EC, ["Price in every post", "Sizes in every post", "One link to checkout"]);
      const ecScene = L.fridayCard(EC - 0.45, "where your profit goes", EC);
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
        times: [H + 0.1, at("L3"), at("L4"), at("L5"), at("L6"), at("L7"), EC + 0.6],
        labels: [
          { t: 1.25, until: 2.45, text: `${focusSecs}s OF FOCUS · TOP 0.01%`, color: "#A9C1F5" },
          { t: at("L4") + 4.5, until: at("L4") + 6.0, text: "STILL WATCHING · RARE FOCUS", color: "#34D399" },
          { t: at("L8"), until: at("L8") + 1.5, text: "DON'T BREAK THE STREAK", color: "#F08A63" },
          { t: EC - 1.25, until: EC - 0.05, text: "HOLD YOUR FOCUS", color: "#FFD66B" },
        ],
        countdown: EC - 0.9,
      });
      L.legend(EC + 0.6, { hold: T.total - EC, top: 264, confetti: { n: 36, rain: 0 }, sub: `${focusSecs} seconds of unbroken focus. Rank resets next Friday. Follow and go longer.` });
      // reference-reel style word card cut into the hook
      L.flashCard("IT SAYS<br/>PULL.", 0.3, 0.36, { size: 190 });

      L.captions({ hide: [["L3:want", "L3e+0.3"], ["L4.2", "L5e+0.4"], ["L7.2", "L7e+0.5"]] });
      L.done();
    </script>
  </body>
</html>
