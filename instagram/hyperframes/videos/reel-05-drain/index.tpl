<!doctype html>
<html lang="en">
  <head>
    <!--HEAD-->
    <style>
      .gcoin { position: absolute; left: 0; top: 0; width: 96px; height: 96px; margin: -48px 0 0 -48px; border-radius: 50%;
        background: radial-gradient(circle at 35% 30%, #FFEFB8, #E0B04A 55%, #9A6C1C); box-shadow: inset 0 0 0 6px #B8862A, 0 8px 16px rgba(30, 20, 0, 0.35);
        display: grid; place-items: center; font-family: var(--mono); font-weight: 700; font-size: 50px; color: #6E4C12; }
      .bill { position: absolute; left: 0; top: 0; width: 156px; height: 76px; margin: -38px 0 0 -78px; border-radius: 8px;
        background: linear-gradient(135deg, #B9E2BF, #6DAE7A); border: 3px solid #3E7D4C; box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
        display: grid; place-items: center; font-family: var(--mono); font-weight: 700; font-size: 40px; color: #2D5E38; }
      .acoin { position: absolute; left: 0; top: 0; width: 300px; height: 300px; margin: -150px 0 0 -150px; border-radius: 50%;
        background: radial-gradient(circle at 35% 30%, #FFF1C2, #E2B24C 52%, #A0721F);
        box-shadow: inset 0 0 0 12px #B8862A, inset 0 0 0 17px #F3D27A, 0 24px 44px rgba(30, 20, 0, 0.45);
        display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #3B2A0A; }
      .acoin small { font-family: var(--mono); font-weight: 700; font-size: 21px; letter-spacing: 0.08em; max-width: 210px; line-height: 1.15; }
      .acoin b { font-family: var(--mono); font-weight: 700; font-size: 84px; letter-spacing: -0.05em; line-height: 1; margin-top: 6px; }
      .acoin i { font-style: normal; font-family: var(--mono); font-weight: 600; font-size: 24px; opacity: 0.75; }
      .big { position: absolute; left: 0; right: 0; text-align: center; font-family: var(--mono); font-weight: 700; letter-spacing: -0.05em; line-height: 1;
        color: #C4320A; text-shadow: 0 5px 0 #FFFFFF, 0 14px 34px rgba(0, 0, 0, 0.35); }
      .sub { position: absolute; left: 0; right: 0; text-align: center; font-family: var(--mono); font-weight: 700; font-size: 28px; letter-spacing: 0.1em; color: #101828; }
      .sub span { background: rgba(247, 245, 239, 0.92); border-radius: 10px; padding: 6px 14px; }
      .tot { position: absolute; left: 270px; top: 284px; width: 540px; height: 96px; border-radius: 48px; background: #101828; color: #FFFFFF;
        display: flex; align-items: center; justify-content: center; gap: 20px; box-shadow: 0 16px 34px rgba(0, 0, 0, 0.35); }
      .tot small { font-family: var(--mono); font-weight: 600; font-size: 22px; letter-spacing: 0.1em; color: #A9C1F5; }
      .tot b { font-family: var(--mono); font-weight: 700; font-size: 52px; letter-spacing: -0.04em; }
      .mo { position: absolute; width: 190px; height: 64px; border-radius: 14px; background: rgba(16, 24, 40, 0.86); color: #FFFFFF;
        font-family: var(--mono); font-weight: 700; font-size: 30px; letter-spacing: 0.06em; display: grid; place-items: center; }
      .plug { position: absolute; width: 240px; height: 240px; border-radius: 50%;
        background: radial-gradient(circle at 35% 30%, #3D5FC4, #1E3A8A 60%, #142A66); box-shadow: inset 0 0 0 12px #F5A623, 0 30px 60px rgba(0, 0, 0, 0.45);
        display: grid; place-items: center; font-family: var(--mono); font-weight: 700; font-size: 104px; letter-spacing: -0.06em; color: #F7F5EF; }
      .chainline { position: absolute; width: 12px; border-radius: 6px; background: repeating-linear-gradient(#DDE2E8 0 16px, #8E97A1 16px 26px); }
      .coin { position: absolute; left: 0; top: 0; width: 150px; height: 150px; margin: -75px 0 0 -75px; border-radius: 50%;
        background: radial-gradient(circle at 35% 30%, #FCE7A8, #D8A844 55%, #9A6C1C); box-shadow: inset 0 0 0 7px #B88A2E, 0 12px 24px rgba(60, 40, 10, 0.3);
        display: flex; flex-direction: column; align-items: center; justify-content: center; }
      .coin b { font-family: var(--mono); font-weight: 700; font-size: 34px; color: #3B2A0A; letter-spacing: -0.03em; }
      .coin small { font-family: var(--mono); font-weight: 700; font-size: 14px; color: #3B2A0A; letter-spacing: 0.06em; }
      .price { position: absolute; left: 72px; font-family: var(--mono); font-weight: 700; letter-spacing: -0.05em; line-height: 1; color: var(--marigold); }
    </style>
  </head>
  <body>
    <!--STAGE-->
    <script src="reward.js"></script>
    <script>
      const tl = L.init();
      window.__timelines = window.__timelines || {};
      window.__timelines["main"] = tl;
      const at = T.at, EC = at("EC");
      const L2 = at("L2"), L3 = at("L3"), L4 = at("L4"), L5 = at("L5"), L6 = at("L6");
      const tSixteen = at("L1.2:sixteen"), tDrain = at("L1.2:drain"), tPlug = at("L4:plugs");
      const DX = 540, DY = 1080; // the drain: the same one from the first frame to the plug

      // ================= ONE SINK, ONE DRAIN · money swirling away from frame one =================
      const sink = L.scene(0, L5 + 0.7, { bg: "#6F7882", vignette: false });
      const jolt = L.div("fill", sink.cam);
      const hh = L.div("fill", jolt);
      L.markup(hh, `<svg class="abs" style="left:0;top:0" width="1080" height="1920" viewBox="0 0 1080 1920">
        <defs>
          <radialGradient id="basin" cx=".5" cy=".56" r=".75"><stop offset="0" stop-color="#EEF1F4"/><stop offset=".55" stop-color="#BFC6CE"/><stop offset="1" stop-color="#7E8892"/></radialGradient>
          <radialGradient id="water" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#0F2F52" stop-opacity=".92"/><stop offset=".55" stop-color="#2F6FAA" stop-opacity=".6"/><stop offset="1" stop-color="#BFE0F5" stop-opacity="0"/></radialGradient>
        </defs>
        <rect x="30" y="232" width="1020" height="1660" rx="120" fill="#58616B"/>
        <rect x="46" y="248" width="988" height="1628" rx="108" fill="url(#basin)"/>
        <g stroke="#FFFFFF" stroke-opacity=".2" stroke-width="3">${Array.from({ length: 30 }, (_, k) => `<line x1="90" y1="${300 + k * 52}" x2="990" y2="${312 + k * 52}"/>`).join("")}</g>
        <circle id="pool" cx="${DX}" cy="${DY}" r="600" fill="url(#water)"/>
      </svg>`);
      const pool = hh.querySelector("#pool");

      // the vortex: two spiral layers turning at different speeds, and rings pulled inward
      const spiral = (col, w, n, rot) => {
        let g = "";
        for (let k = 0; k < n; k++) {
          let d = "";
          for (let j = 0; j <= 60; j++) {
            const th = (j / 60) * 3.4 * Math.PI, r = 70 * Math.exp(0.19 * th), a = th + (k * 2 * Math.PI) / n + rot;
            d += (j ? "L" : "M") + (r * Math.cos(a)).toFixed(1) + " " + (r * Math.sin(a)).toFixed(1);
          }
          g += `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linecap="round"/>`;
        }
        return g;
      };
      const vA = L.svg(hh, `position:absolute;left:${DX - 600}px;top:${DY - 600}px;width:1200px;height:1200px`, "-600 -600 1200 1200");
      vA.innerHTML = spiral("rgba(255,255,255,.78)", 16, 6, 0);
      const vB = L.svg(hh, `position:absolute;left:${DX - 600}px;top:${DY - 600}px;width:1200px;height:1200px`, "-600 -600 1200 1200");
      vB.innerHTML = spiral("rgba(46,94,150,.55)", 9, 5, 0.6);
      const spinA = Math.round(tPlug / 0.85), spinB = Math.round(tPlug / 1.3);
      tl.fromTo(vA, { rotation: 0 }, { rotation: 360 * spinA, duration: tPlug, ease: "none" }, 0);
      tl.fromTo(vB, { rotation: 0 }, { rotation: 360 * spinB, duration: tPlug, ease: "none" }, 0);
      // after the plug the water slows to a stop and calms down
      tl.to(vA, { rotation: 360 * spinA + 110, opacity: 0.12, duration: 1.4, ease: "power3.out" }, tPlug);
      tl.to(vB, { rotation: 360 * spinB + 60, opacity: 0.1, duration: 1.4, ease: "power3.out" }, tPlug);
      tl.to(pool, { opacity: 0.45, duration: 1.0 }, tPlug);
      for (let k = 0; k < 4; k++) {
        const ring = L.div("abs", hh, `left:${DX - 430}px;top:${DY - 430}px;width:860px;height:860px;border-radius:50%;border:7px solid rgba(255,255,255,.4)`);
        const Pr = 1.2, off = (k * Pr) / 4, n = Math.max(1, Math.floor((tPlug - 0.1 - off) / Pr));
        tl.fromTo(ring, { scale: 1.12, opacity: 0 }, { scale: 0.1, opacity: 0.95, duration: Pr, ease: "power1.in", repeat: n - 1 }, off);
        tl.set(ring, { opacity: 0 }, off + n * Pr);
      }

      // coins and bills spiral into the drain; each one starts mid-trip so frame one is already full
      const swirl = L.div("fill", hh);
      const rs = L.rng(11), P = 1.8, NSW = 24;
      for (let i = 0; i < NSW; i++) {
        const arm = L.div("abs", swirl, `left:${DX}px;top:${DY}px;width:0;height:0`);
        const bill = i % 4 === 1;
        const it = L.div(bill ? "bill" : "gcoin", arm, "", "$");
        const ph = i / NSW, a0 = rs() * 360, R0 = 400 + rs() * 160, s0 = bill ? 1.05 : 0.75 + rs() * 0.55;
        gsap.set(it, { rotation: rs() * 360 });
        const first = P * (1 - ph);
        tl.fromTo(arm, { rotation: a0 + 540 * ph }, { rotation: a0 + 540, duration: first, ease: "none" }, 0);
        tl.fromTo(it, { x: R0 * (1 - ph), scale: s0 * (1 - 0.85 * ph) }, { x: 0, scale: s0 * 0.15, duration: first, ease: "none" }, 0);
        const n = Math.floor((tPlug - 0.1 - first) / P);
        if (n >= 1) {
          tl.fromTo(arm, { rotation: a0 }, { rotation: a0 + 540, duration: P, ease: "none", repeat: n - 1, immediateRender: false }, first);
          tl.fromTo(it, { x: R0, scale: s0 }, { x: 0, scale: s0 * 0.15, duration: P, ease: "none", repeat: n - 1, immediateRender: false }, first);
        }
      }

      // the real sink clip (Gemini, speed-ramped to 5.3 s, cropped so its drain sits on DX, DY) covers the hook,
      // then cuts to the illustrated drain as the first app coin drops
      const tVidEnd = 5.3;
      const vid = document.getElementById("sinkvid");
      vid.style.cssText = "position:absolute;left:-30px;top:-53px;width:1140px;height:2027px;object-fit:cover";
      hh.appendChild(vid);
      tl.set(vid, { visibility: "hidden" }, tVidEnd);

      // Beat 2 · four app coins, one per line, each dropped into the same drain
      const apps = [["ANALYTICS APP", "$49"], ["INVENTORY APP", "$49"], ["WIN-BACK EMAIL APP", "$20"], ["INSTAGRAM PLANNER", "$18.75"]];
      const dropT = [];
      apps.forEach(([name, price], k) => {
        const tS = at(`L2.${k + 1}`) - 0.08, tE = at(`L2.${k + 1}e`);
        const arm = L.div("abs", hh, `left:${DX}px;top:${DY}px;width:0;height:0`);
        const c = L.div("acoin", arm, "visibility:hidden", `<small>${name}</small><b style="font-size:${price.length > 3 ? 66 : 84}px">${price}</b><i>/month</i>`);
        gsap.set(c, { y: -480 });
        tl.set(c, { visibility: "visible" }, tS);
        tl.fromTo(c, { scale: 0.2, rotation: -40 }, { scale: 1, rotation: 0, duration: 0.36, ease: "back.out(2.2)", immediateRender: false }, tS);
        tl.fromTo(c, { y: -480 }, { y: -500, duration: 0.3, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }, tS + 0.36);
        const d0 = tE - 0.32;
        tl.fromTo(arm, { rotation: 0 }, { rotation: 330, duration: 0.5, ease: "power2.in", immediateRender: false }, d0);
        tl.fromTo(c, { y: -480, scale: 1 }, { y: 0, scale: 0.12, duration: 0.5, ease: "power2.in", immediateRender: false }, d0);
        tl.set(c, { visibility: "hidden" }, d0 + 0.5);
        dropT.push(d0 + 0.5);
        // a little camera punch on every new coin
        tl.fromTo(sink.cam, { scale: 1 }, { scale: 1.045, duration: 0.09, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tS);
      });

      // Beat 3 · every single month: twelve months, twelve coins down the drain
      const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
      const moT = L.series(at("L3.2"), at("L3.2e") + 0.25, 12);
      const moPos = (k) => [136 + (k % 4) * 206, 620 + Math.floor(k / 4) * 82];
      months.forEach((m, k) => {
        const [x, y] = moPos(k);
        const c = L.div("gcoin", hh, `left:${x + 95}px;top:${y + 32}px;visibility:hidden`, "$");
        tl.set(c, { visibility: "visible" }, moT[k]);
        tl.fromTo(c, { x: 0, y: 0, scale: 0.75 }, { x: DX - (x + 95), y: DY - (y + 32), scale: 0.15, duration: 0.42, ease: "power2.in", immediateRender: false }, moT[k]);
        tl.set(c, { visibility: "hidden" }, moT[k] + 0.42);
      });

      // the drain itself sits above everything that falls into it (hidden while the real clip plays)
      const drainDisc = L.markup(hh, `<svg class="abs" style="left:${DX - 110}px;top:${DY - 110}px" width="220" height="220" viewBox="-110 -110 220 220">
        <circle r="96" fill="#9AA3AD"/><circle r="84" fill="#6F7780"/><circle r="70" fill="#15181C"/>
        <g stroke="#8E97A1" stroke-width="8">${Array.from({ length: 6 }, (_, k) => { const a = (k / 6) * Math.PI; return `<line x1="${Math.cos(a) * 64}" y1="${Math.sin(a) * 64}" x2="${-Math.cos(a) * 64}" y2="${-Math.sin(a) * 64}"/>`; }).join("")}</g>
      </svg>`);
      drainDisc.style.visibility = "hidden";
      tl.set(drainDisc, { visibility: "visible" }, tVidEnd);

      // HOOK · "Stop!": a hand slams down at the drain
      const hand = L.markup(hh, `<svg class="abs" style="left:520px;top:1010px;visibility:hidden" width="470" height="660" viewBox="0 0 470 660">
        <g fill="#D29A6C">
          <rect x="88" y="96" width="64" height="250" rx="32"/><rect x="160" y="40" width="66" height="290" rx="33"/>
          <rect x="234" y="52" width="66" height="280" rx="33"/><rect x="308" y="112" width="60" height="240" rx="30"/>
          <rect x="74" y="250" width="300" height="300" rx="120"/>
          <rect x="-6" y="300" width="64" height="200" rx="32" transform="rotate(-38 26 400)"/>
        </g>
        <g fill="#BC8458"><rect x="96" y="96" width="14" height="80" rx="7" opacity=".5"/><rect x="170" y="40" width="14" height="90" rx="7" opacity=".5"/></g>
        <rect x="120" y="520" width="220" height="150" fill="#1E3A8A"/><rect x="120" y="520" width="220" height="22" fill="#F5A623"/>
      </svg>`);
      hand.style.display = "none"; // the real clip has its own hand slam
      gsap.set(hand, { transformOrigin: "50% 100%", rotation: -14 });
      const tSlam = 0.66; // lands right after the full-frame STOP card
      tl.set(hand, { visibility: "visible" }, tSlam - 0.14);
      tl.fromTo(hand, { y: 900, scale: 1.25 }, { y: 0, scale: 1, duration: 0.14, ease: "power4.in", immediateRender: false }, tSlam - 0.14);
      tl.to(hand, { y: 30, duration: 0.08, yoyo: true, repeat: 1 }, tSlam);
      tl.to(hand, { y: 950, rotation: -4, duration: 0.45, ease: "power3.in" }, tSixteen + 0.62);
      tl.set(hand, { visibility: "hidden" }, tSixteen + 1.1);
      L.flash(tSlam);
      L.shake(jolt, tSlam, 30, 0.4);
      tl.fromTo(sink.cam, { scale: 1 }, { scale: 1.1, duration: 0.12, ease: "power3.out", immediateRender: false }, tSlam);
      tl.to(sink.cam, { scale: 1.02, duration: 0.5, ease: "power2.inOut" }, tSlam + 0.12);
      L.handheld(hh, 0, tPlug - 0.05, 5, 23);
      tl.to(hh, { x: 0, y: 0, rotation: 0, duration: 0.05 }, tPlug - 0.05);
      L.aiChip(sink);

      // "$1,641 a year" slams in, then gets sucked down the drain on "drain"
      const num = L.div("fill", hh, "visibility:hidden");
      L.counter(num, "left:0;right:0;top:330px;font-size:190px", "big", 0, 1641, tSixteen, 0.5, (v) => "$" + Math.round(v).toLocaleString("en-US"), { steps: 18, ease: "power2.out" });
      L.div("sub", num, "top:548px", "<span>A YEAR · 4 APPS AT STARTING PRICES</span>");
      gsap.set(num, { transformOrigin: "540px 440px" });
      tl.set(num, { visibility: "visible" }, tSixteen - 0.02);
      tl.fromTo(num, { scale: 1.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.26, ease: "expo.out", immediateRender: false }, tSixteen - 0.02);
      L.shake(jolt, tSixteen + 0.05, 18, 0.25);
      tl.to(num, { y: DY - 440, scale: 0.04, rotation: 420, duration: 0.55, ease: "power2.in" }, tDrain - 0.3);
      tl.set(num, { visibility: "hidden" }, tDrain + 0.25);

      // full-frame color cards cut into the hook, like the reference reels: STOP on red, $1,641 on black
      const stopCard = L.div("fill", sink.cam, "z-index:40;visibility:hidden;background:#C4320A;display:grid;place-items:center",
        `<div style="font-family:var(--sans);font-weight:900;font-size:260px;letter-spacing:-.04em;line-height:1;color:#FFFFFF">STOP.</div>`);
      tl.set(stopCard, { visibility: "visible" }, 0.3);
      tl.fromTo(stopCard.querySelector("div"), { scale: 1.5 }, { scale: 1, duration: 0.18, ease: "expo.out", immediateRender: false }, 0.3);
      tl.set(stopCard, { visibility: "hidden" }, 0.62);
      const numCard = L.div("fill", sink.cam, "z-index:40;visibility:hidden;background:#0B0F19");
      L.counter(numCard, "left:0;right:0;top:770px;text-align:center;font-size:230px;color:#F5A623", "num", 0, 1641, tSixteen, 0.45, (v) => "$" + Math.round(v).toLocaleString("en-US"), { steps: 16, ease: "power2.out" });
      L.div("abs", numCard, "left:0;right:0;top:1030px;text-align:center;font-family:var(--mono);font-weight:700;font-size:48px;letter-spacing:.14em;color:#FFFFFF", "A YEAR");
      tl.set(numCard, { visibility: "visible" }, tSixteen - 0.02);
      tl.fromTo(numCard, { scale: 1.12 }, { scale: 1, duration: 0.3, ease: "expo.out", immediateRender: false }, tSixteen - 0.02);
      tl.set(numCard, { visibility: "hidden" }, tSixteen + 0.6);

      // the running monthly total
      const tot = L.div("tot", hh, "visibility:hidden", `<small>PER MONTH</small>`);
      const totV = L.div("", tot, "position:relative;min-width:230px");
      const totals = ["$0.00", "$49.00", "$98.00", "$118.00", "$136.75"];
      const totSp = totals.map((v, i) => L.el("b", "", totV, i ? "display:none" : "", v));
      tl.set(tot, { visibility: "visible" }, L2 - 0.15);
      tl.fromTo(tot, { y: -40, opacity: 0 }, { y: 0, opacity: 1, duration: 0.3, ease: "back.out(2)", immediateRender: false }, L2 - 0.15);
      dropT.forEach((t, k) => {
        tl.set(totSp[k], { display: "none" }, t);
        tl.set(totSp[k + 1], { display: "inline" }, t);
        tl.fromTo(tot, { scale: 1.18, backgroundColor: "#C4320A" }, { scale: 1, backgroundColor: "#101828", duration: 0.4, ease: "power2.out", immediateRender: false }, t);
      });
      const spChip = L.chip(hh, "STARTING PRICES · SEPT 2026", "left:322px;top:396px", L2);
      tl.to([tot, spChip], { autoAlpha: 0, duration: 0.2 }, L3 - 0.05);

      // "A hundred thirty-seven dollars. Every single month."
      const mon = L.div("fill", hh, "visibility:hidden");
      L.div("big", mon, "top:318px;font-size:190px", "$136.75");
      const monSub = L.div("sub", mon, "top:528px", "<span>EVERY MONTH</span>");
      const yrSub = L.div("sub", mon, "top:528px;display:none;color:#C4320A", "<span>= $1,641 A YEAR</span>");
      tl.set(mon, { visibility: "visible" }, L3 - 0.03);
      tl.fromTo(mon, { scale: 1.7, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.26, ease: "expo.out", transformOrigin: "540px 420px", immediateRender: false }, L3 - 0.03);
      L.shake(jolt, L3 + 0.05, 22, 0.3);
      const moChips = months.map((m, k) => {
        const [x, y] = moPos(k);
        const ch = L.div("mo", hh, `left:${x}px;top:${y}px;visibility:hidden`, m);
        tl.set(ch, { visibility: "visible" }, at("L3.2") - 0.22 + k * 0.015);
        tl.fromTo(ch, { scale: 0.4, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.2, ease: "back.out(2)", immediateRender: false }, at("L3.2") - 0.22 + k * 0.015);
        tl.fromTo(ch, { backgroundColor: "rgba(16,24,40,0.86)", scale: 1 }, { backgroundColor: "#C4320A", scale: 1.12, duration: 0.07, immediateRender: false }, moT[k]);
        tl.to(ch, { scale: 1, duration: 0.12 }, moT[k] + 0.07);
        return ch;
      });
      tl.set(monSub, { display: "none" }, at("L3.2e") + 0.35); // display, not visibility: a hide-first visibility set would leak
      tl.set(yrSub, { display: "block" }, at("L3.2e") + 0.35);
      tl.fromTo(yrSub, { scale: 1.4 }, { scale: 1, duration: 0.25, ease: "back.out(2)", immediateRender: false }, at("L3.2e") + 0.35);
      tl.to([mon, ...moChips], { autoAlpha: 0, duration: 0.25 }, L4 + 0.05);

      // Beat 4 · "One Tap Manager plugs the leak": the 1T plug drops and slams into the drain
      const plugWrap = L.div("fill", hh, "visibility:hidden");
      L.div("chainline", plugWrap, `left:${DX - 6}px;top:-1200px;height:${DY - 100 + 1200}px`);
      const plug = L.div("plug", plugWrap, `left:${DX - 120}px;top:${DY - 120}px`, "1T");
      tl.set(plugWrap, { visibility: "visible" }, L4 + 0.1);
      tl.fromTo(plugWrap, { y: -1500 }, { y: 0, duration: tPlug - L4 - 0.1, ease: "power3.in", immediateRender: false }, L4 + 0.1);
      tl.fromTo(plug, { scaleX: 1.22, scaleY: 0.8 }, { scaleX: 1, scaleY: 1, duration: 0.4, ease: "elastic.out(1, 0.45)", immediateRender: false }, tPlug);
      L.flash(tPlug);
      L.shake(jolt, tPlug, 34, 0.45);
      tl.fromTo(sink.cam, { scale: 1 }, { scale: 1.08, duration: 0.1, ease: "power3.out", immediateRender: false }, tPlug);
      tl.to(sink.cam, { scale: 1, duration: 0.6, ease: "power2.out" }, tPlug + 0.1);
      L.burst(hh, DX, DY, tPlug, { n: 26, spread: 300, size: 18, colors: ["#BFE0F5", "#FFFFFF", "#7FB2DA", "#F5A623"] });
      // what used to drain away now stays: a ring of coins around the plug
      const pile = L.rng(77);
      for (let k = 0; k < 12; k++) {
        const a = (k / 12) * Math.PI * 2 + pile() * 0.3, r = 175 + pile() * 70;
        const c = L.div("gcoin", hh, `left:${DX + Math.cos(a) * r}px;top:${DY + Math.sin(a) * r}px;visibility:hidden`, "$");
        tl.set(c, { visibility: "visible" }, tPlug + 0.18 + k * 0.035);
        tl.fromTo(c, { scale: 0, rotation: -90 }, { scale: 0.9 + pile() * 0.3, rotation: (pile() - 0.5) * 40, duration: 0.35, ease: "back.out(2.5)", immediateRender: false }, tPlug + 0.18 + k * 0.035);
      }
      L.stamp(hh, "LEAK PLUGGED", tPlug + 0.32, { x: 170, y: 560, size: 84, r: -5, css: "color:#0E7A4F" });

      // ================= BEAT 5 + 6 · night: four app coins become one, $12.99 flat =================
      const nt = L.scene(L5 - 0.05, EC, { bg: "night" });
      L.ripple(nt, L5 - 0.05, DX, DY);
      const C0 = { x: 540, y: 560 };
      // keep the offer scene moving (v3's visual score crashed here): turning rays and a slow push-in
      const rays = L.div("abs", nt.cam, `left:${C0.x - 800}px;top:${C0.y - 800}px;width:1600px;height:1600px;border-radius:50%;opacity:0;background:repeating-conic-gradient(rgba(245,166,35,.24) 0 8deg, rgba(245,166,35,0) 8deg 20deg);-webkit-mask-image:radial-gradient(circle,#000 14%,transparent 62%);mask-image:radial-gradient(circle,#000 14%,transparent 62%)`);
      tl.fromTo(rays, { opacity: 0 }, { opacity: 1, duration: 0.6, immediateRender: false }, L5 + 0.85);
      tl.fromTo(rays, { rotation: 0 }, { rotation: 70, duration: EC - L5, ease: "none" }, L5);
      L.push(nt.cam, L5, EC, 1.06, { origin: "50% 40%" });
      const ncoins = apps.map(([name, p]) => L.div("coin", nt.cam, "visibility:hidden", `<small>${name.split(" ")[0]}</small><b>${p}</b>`));
      ncoins.forEach((c, i) => {
        const t = L5 + 0.05 + i * 0.1;
        tl.set(c, { visibility: "visible" }, t);
        tl.fromTo(c, { x: C0.x + [-330, -110, 110, 330][i], y: C0.y + 420, scale: 0.4 }, { x: C0.x + [-260, -90, 90, 260][i], y: C0.y + [70, -40, -40, 70][i], scale: 0.9, duration: 0.4, ease: "back.out(1.6)" }, t);
        for (let f = 1; f <= 10; f++) {
          const a = (i / 4) * Math.PI * 2 + (f / 10) * Math.PI * 2, r = 230 * (1 - f / 13);
          tl.set(c, { x: C0.x + Math.cos(a) * r, y: C0.y + Math.sin(a) * r * 0.6 }, L5 + 0.5 + f / 30);
        }
        tl.to(c, { x: C0.x, y: C0.y, scale: 0.4, autoAlpha: 0, duration: 0.18, ease: "power2.in" }, L5 + 0.85);
      });
      const bigCoin = L.div("abs", nt.cam, `left:${C0.x - 160}px;top:${C0.y - 160}px;width:320px;height:320px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#3D5FC4,#1E3A8A 60%,#142A66);box-shadow:inset 0 0 0 12px #F5A623,0 0 60px rgba(245,166,35,.45);display:grid;place-items:center;font-family:var(--mono);font-weight:700;font-size:130px;letter-spacing:-.06em;color:var(--paper)`, "1T");
      L.pop(bigCoin, L5 + 0.9, { from: 0.3, dur: 0.5 });
      L.burst(nt.cam, C0.x, C0.y, L5 + 0.9, { n: 18, spread: 220 });
      L.drift(bigCoin, L5 + 1.4, EC, { period: 4, y: -10, x: 0, r: 2 });
      // three saved coins orbit the 1T coin
      for (let k = 0; k < 3; k++) {
        const arm = L.div("abs", nt.cam, `left:${C0.x}px;top:${C0.y}px;width:0;height:0;visibility:hidden`);
        const c = L.div("gcoin", arm, "", "$");
        gsap.set(c, { x: 205, scale: 0.6 });
        tl.set(arm, { visibility: "visible" }, L5 + 1.0);
        const n = Math.max(1, Math.floor((EC - L5 - 1.0) / 2.4));
        tl.fromTo(arm, { rotation: k * 120 }, { rotation: k * 120 + 360, duration: 2.4, ease: "none", repeat: n - 1, immediateRender: false }, L5 + 1.0);
      }
      const tPrice = at("L5.1:twelve");
      L.slam(L.div("price", nt.cam, "top:790px;font-size:210px", "$12.99"), tPrice);
      L.shake(nt.cam, tPrice + 0.05, 14, 0.25);
      L.rise(L.div("abs on-night", nt.cam, "left:78px;top:1010px;font-weight:800;font-size:60px;letter-spacing:-.02em", "a month"), tPrice + 0.3);
      L.rise(L.div("abs on-night", nt.cam, "left:78px;top:1096px;font-weight:600;font-size:40px;color:var(--sky)", "Pro Max · all four jobs"), tPrice + 0.5);
      L.rise(L.div("abs on-night", nt.cam, "left:78px;top:1152px;font-weight:600;font-size:34px;color:var(--sky);opacity:.85", "Pro: $10 a month"), tPrice + 0.65);
      L.stamp(nt.cam, "FLAT", at("L5.2"), { x: 410, y: 984, color: "indigo", size: 50, r: 8, css: "color:#A9C1F5" });
      L.chip(nt.cam, "7-DAY FREE TRIAL", "left:78px;top:1240px;font-size:26px", L6).classList.add("dark");
      const promise = L.div("abs on-night", nt.cam, "left:78px;top:1300px;font-weight:800;font-size:66px;letter-spacing:-.03em;white-space:nowrap", `<span class="green">0%</span> of your sales. <span class="hl"><i></i>Ever.</span>`);
      L.wipeIn(promise, at("L6.2"), 0.6);
      L.hl(promise, at("L6.2:sales") + 0.1);

      // ================= end card =================
      L.flip(nt, EC - 0.45);
      const ecScene = L.endCard(EC - 0.45, "Comment PRICE.", { anim: EC });
      gsap.set(ecScene.cam, { y: 30 }); // a little room for the Attention Legend card above the logo

      // ================= ATTENTION SPAN LEADERBOARD =================
      // Opens as a full-screen "ATTENTION TEST" card (the pre-roll) that lands as the meter.
      const focusSecs = Math.round(T.total);
      const tBar = L.attentionTest({ top: 140, secs: focusSecs });
      L.attention({
        start: tBar,
        enter: "fade",
        top: 140,
        times: [tDrain, at("L2.3"), L3, tPlug + 0.1, L5, L6, EC + 0.6],
        labels: [
          { t: 1.25, until: tDrain - 0.05, text: `${focusSecs}s OF FOCUS · TOP 0.01%`, color: "#A9C1F5" },
          { t: EC - 1.25, until: EC - 0.05, text: "HOLD YOUR FOCUS", color: "#FFD66B" },
        ],
        countdown: EC - 0.9,
      });
      // the outro after the CTA settles and goes still: it takes the notebook's weakest 20% of seconds
      L.legend(EC + 0.6, { hold: T.total - EC, top: 264, confetti: { n: 36, rain: 0 }, sub: `${focusSecs} seconds of unbroken focus. Rank resets next reel. Follow and go longer.` });

      L.captions({ hide: [["L5.1:twelve", "EC"]] });
      L.done();
    </script>
  </body>
</html>
