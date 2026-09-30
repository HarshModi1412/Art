<!doctype html>
<html lang="en">
  <head>
    <!--HEAD-->
    <style>
      .tread-lab { position: absolute; width: 150px; text-align: center; font-family: var(--mono); font-weight: 700; font-size: 58px; letter-spacing: -0.04em; color: var(--ink); }
      .eq-word { position: absolute; left: 200px; font-weight: 800; font-size: 92px; letter-spacing: -0.03em; color: var(--paper); white-space: nowrap; }
      .eq-op { position: absolute; left: 72px; font-family: var(--mono); font-weight: 700; font-size: 110px; color: var(--marigold); }
      .eq-num { position: absolute; right: 150px; font-family: var(--mono); font-weight: 700; font-size: 150px; letter-spacing: -0.05em; color: var(--paper); text-align: right; }
      .blab { position: absolute; font-weight: 700; font-size: 30px; white-space: nowrap; }
      .po { position: absolute; left: 488px; top: 520px; width: 444px; padding: 30px 32px; background: var(--paper2); border-radius: 18px; box-shadow: 0 30px 70px rgba(0, 0, 0, 0.45); }
      .po h5 { font-family: var(--mono); font-weight: 700; font-size: 26px; letter-spacing: 0.12em; color: var(--ink); margin-bottom: 18px; }
      .po .f { border-top: 2px dashed rgba(16, 24, 40, 0.25); padding: 14px 0; }
      .po .f small { display: block; font-family: var(--mono); font-weight: 500; font-size: 20px; letter-spacing: 0.08em; color: var(--ink-soft); text-transform: uppercase; }
      .po .f div { font-weight: 700; font-size: 36px; color: var(--ink); min-height: 44px; }
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
      const tGone = at("L2.2:gone");
      const tNight = at("L2e") + 0.7;   // hard cut to night
      const tRip = at("L4e") + 0.6;     // tap ripple into the phone

      // ================= HOOK · the last step: a sunlit stairwell, a tower of gifts, a bonk =================
      const stairD = "M0 760 H240 V910 H430 V1060 H620 V1210 H810 V1360 H1000 V1510 H1080";
      const railY = (x) => 400 + x * 0.789;           // dado rail, parallel to the stairs
      const handY = (x) => 520 + (710 * x) / 1080;     // handrail
      const treadY = (x) => (x < 240 ? 760 : x < 1000 ? 760 + 150 * Math.ceil((x - 240) / 190) : 1510);
      const hook = L.scene(0, L1 + 2.2, { bg: "#E9D6B4", vignette: false });
      const shake = L.div("fill", hook.cam);
      const WAVE_A = "M0 0 C50 -34 90 34 140 0 C170 -20 200 10 220 0 L220 30 C200 40 170 10 140 30 C90 64 50 -4 0 30 Z";
      const WAVE_B = "M0 0 C50 30 90 -30 140 0 C170 20 200 -10 220 0 L220 30 C200 20 170 50 140 30 C90 0 50 60 0 30 Z";
      shake.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920">
        <defs>
          <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F2E3C7"/><stop offset="1" stop-color="#DCC29B"/></linearGradient>
          <pattern id="dam" width="72" height="72" patternUnits="userSpaceOnUse"><path d="M36 12 L45 36 L36 60 L27 36 Z" fill="#D7BF97" opacity=".5"/><circle cx="0" cy="0" r="4" fill="#D7BF97" opacity=".45"/><circle cx="72" cy="0" r="4" fill="#D7BF97" opacity=".45"/><circle cx="0" cy="72" r="4" fill="#D7BF97" opacity=".45"/><circle cx="72" cy="72" r="4" fill="#D7BF97" opacity=".45"/></pattern>
          <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE3A8"/><stop offset=".55" stop-color="#F7A86B"/><stop offset="1" stop-color="#C67A86"/></linearGradient>
          <linearGradient id="beam" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFF3CF" stop-opacity=".85"/><stop offset="1" stop-color="#FFF3CF" stop-opacity="0"/></linearGradient>
          <linearGradient id="stringer" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9C6439"/><stop offset="1" stop-color="#5B381E"/></linearGradient>
          <linearGradient id="rail" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7E5130"/><stop offset=".35" stop-color="#C48B59"/><stop offset="1" stop-color="#4A2C16"/></linearGradient>
          <linearGradient id="knit" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#BD827E"/><stop offset=".5" stop-color="#DDA8A4"/><stop offset="1" stop-color="#B27672"/></linearGradient>
          <linearGradient id="jean" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2A3B63"/><stop offset=".5" stop-color="#40598C"/><stop offset="1" stop-color="#25355A"/></linearGradient>
          <pattern id="rib" width="8" height="20" patternUnits="userSpaceOnUse"><line x1="4" y1="0" x2="4" y2="20" stroke="#000" stroke-opacity=".1" stroke-width="2"/></pattern>
          <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><rect width="22" height="22" fill="#F5A623"/><circle cx="11" cy="11" r="4" fill="#FFF3D6"/></pattern>
          <pattern id="stripe" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="18" height="18" fill="#9CAF94"/><rect width="8" height="18" fill="#C2D2B8"/></pattern>
          <linearGradient id="s1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E8906A"/><stop offset=".5" stop-color="#C4633A"/><stop offset="1" stop-color="#F2B08E"/></linearGradient>
          <linearGradient id="s2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#C9D8BF"/><stop offset=".5" stop-color="#8FA588"/><stop offset="1" stop-color="#DCE8D3"/></linearGradient>
          <linearGradient id="s3" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE0A0"/><stop offset=".5" stop-color="#F5A623"/><stop offset="1" stop-color="#FFE9BC"/></linearGradient>
          <linearGradient id="s4" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#C3D3F7"/><stop offset=".5" stop-color="#5B7BD6"/><stop offset="1" stop-color="#D6E1FA"/></linearGradient>
          <filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="16"/></filter>
          <filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="8" dy="12" stdDeviation="8" flood-color="#2A1608" flood-opacity=".32"/></filter>
        </defs>
        <rect width="1080" height="1920" fill="url(#wall)"/>
        <rect width="1080" height="1920" fill="url(#dam)"/>
        <rect x="60" y="140" width="290" height="500" rx="10" fill="#F7EFE2"/>
        <rect x="82" y="162" width="246" height="456" fill="url(#glass)"/>
        <circle cx="250" cy="300" r="46" fill="#FFF4CC" opacity=".9"/>
        <path d="M82 520 Q160 480 230 505 T328 490 V618 H82 Z" fill="#B97B78" opacity=".55"/>
        <path d="M205 162 V618 M82 390 H328" stroke="#F7EFE2" stroke-width="14"/>
        <rect x="44" y="636" width="322" height="22" rx="6" fill="#EFE3CF"/>
        <path d="M0 ${railY(0)} L1080 ${railY(1080)} V1920 H0 Z" fill="#CDAE82"/>
        <g stroke="#B99A6C" stroke-width="3" fill="none" opacity=".7">${[0, 1, 2, 3, 4, 5].map((k) => { const x = 40 + k * 180; return `<path d="M${x} ${railY(x) + 60} L${x + 140} ${railY(x + 140) + 60} L${x + 140} ${railY(x + 140) + 200} L${x} ${railY(x) + 200} Z"/>`; }).join("")}</g>
        <path d="M0 ${railY(0)} L1080 ${railY(1080)}" stroke="#F3E6CF" stroke-width="12"/>
        <path d="M0 ${railY(0) + 14} L1080 ${railY(1080) + 14}" stroke="#A98A5E" stroke-width="4"/>
        <g filter="url(#sh)">
          <rect x="360" y="436" width="170" height="196" rx="4" fill="#6B4A2C"/><rect x="374" y="450" width="142" height="168" fill="#F6EEDF"/><circle cx="445" cy="512" r="26" fill="#F5A623"/><path d="M374 618 L420 556 L452 590 L480 566 L516 618 Z" fill="#8FA588"/>
          <rect x="610" y="600" width="150" height="150" rx="4" fill="#6B4A2C"/><rect x="624" y="614" width="122" height="122" fill="#F6EEDF"/><circle cx="672" cy="664" r="30" fill="#1E3A8A"/><path d="M660 720 A46 46 0 0 1 740 660" stroke="#C4633A" stroke-width="12" fill="none"/>
          <rect x="826" y="790" width="126" height="160" rx="4" fill="#6B4A2C"/><rect x="840" y="804" width="98" height="132" fill="#F6EEDF"/><path d="M889 924 C850 880 858 836 889 812 C920 836 928 880 889 924 Z" fill="#8FA588"/><path d="M889 924 V818" stroke="#6E8566" stroke-width="3"/>
        </g>
        <polygon points="330,170 80,620 640,1500 1080,980 1080,760" fill="url(#beam)" filter="url(#soft)" opacity=".8"/>
        <path d="${stairD} V1920 H0 Z" fill="url(#stringer)"/>
        <g stroke="#3F2512" stroke-opacity=".22" stroke-width="3" fill="none">${[0, 1, 2, 3, 4, 5, 6].map((k) => `<path d="M0 ${980 + k * 130} C300 ${940 + k * 130} 640 ${1060 + k * 130} 1080 ${1010 + k * 130}"/>`).join("")}</g>
        <g id="steps"></g>
        <rect x="1000" y="1510" width="80" height="410" fill="#8B5E3C"/><rect x="1000" y="1510" width="80" height="6" fill="#C49064"/>
        <g id="balusters"></g>
        <path d="M-10 ${handY(-10)} L1090 ${handY(1090)}" stroke="url(#rail)" stroke-width="24" stroke-linecap="round"/>
        <path d="M-10 ${handY(-10) - 7} L1090 ${handY(1090) - 7}" stroke="#E0A876" stroke-width="4" opacity=".7"/>
        <g><rect x="986" y="1196" width="58" height="316" rx="6" fill="#6B4122"/><rect x="976" y="1178" width="78" height="26" rx="6" fill="#8A5A34"/><circle cx="1015" cy="1160" r="24" fill="#9A6A40"/><rect x="994" y="1196" width="10" height="316" fill="#8C5B34" opacity=".7"/></g>
        <g id="motes" fill="#FFF6D6"></g>
        <g id="woman">
          <ellipse cx="0" cy="2" rx="72" ry="12" fill="#2A1608" opacity=".28"/>
          <g id="boxes" filter="url(#sh)">
            <rect x="-94" y="-352" width="188" height="92" rx="6" fill="#C79A63"/><rect x="-94" y="-352" width="188" height="14" fill="#DDB47E"/><path d="M0 -352 V-260 M-94 -306 H94" stroke="#8A6A3F" stroke-width="5"/>
            <rect x="-80" y="-440" width="160" height="90" rx="6" fill="url(#dots)"/><rect x="-80" y="-440" width="160" height="12" fill="#FFD27A"/><rect x="-8" y="-440" width="16" height="90" fill="#1E3A8A"/><rect x="-80" y="-402" width="160" height="14" fill="#1E3A8A"/>
            <rect x="-68" y="-518" width="136" height="80" rx="6" fill="url(#stripe)"/><rect x="-68" y="-518" width="136" height="10" fill="#D7E3CF"/><rect x="-7" y="-518" width="14" height="80" fill="#C4320A"/>
          </g>
          <g id="scarves">
            <path class="sc" d="${WAVE_A}" fill="url(#s1)"/><path class="sc" d="${WAVE_A}" fill="url(#s2)"/><path class="sc" d="${WAVE_A}" fill="url(#s3)"/><path class="sc" d="${WAVE_A}" fill="url(#s4)"/>
          </g>
          <path d="M-58 -338 Q-100 -300 -92 -300" stroke="url(#knit)" stroke-width="30" stroke-linecap="round" fill="none"/>
          <path d="M58 -338 Q100 -300 92 -300" stroke="url(#knit)" stroke-width="30" stroke-linecap="round" fill="none"/>
          <ellipse cx="-97" cy="-304" rx="13" ry="17" fill="#C68B5E"/><ellipse cx="97" cy="-304" rx="13" ry="17" fill="#C68B5E"/>
          <g id="legL"><path d="M-40 -188 L-8 -188 L-12 -16 L-36 -16 Z" fill="url(#jean)"/><path d="M-50 -20 H-6 Q0 -4 -8 2 H-52 Q-58 -8 -50 -20Z" fill="#F4F2EE"/><rect x="-54" y="-2" width="50" height="6" rx="3" fill="#B9B4AA"/></g>
          <g id="legR"><path d="M8 -188 L40 -188 L36 -16 L12 -16 Z" fill="url(#jean)"/><path d="M6 -20 H50 Q56 -4 48 2 H4 Q-2 -8 6 -20Z" fill="#F4F2EE"/><rect x="4" y="-2" width="50" height="6" rx="3" fill="#B9B4AA"/></g>
          <path d="M-62 -352 Q0 -376 62 -352 L78 -172 Q0 -158 -78 -172 Z" fill="url(#knit)"/><path d="M-62 -352 Q0 -376 62 -352 L78 -172 Q0 -158 -78 -172 Z" fill="url(#rib)"/>
          <path d="M-78 -188 Q0 -174 78 -188 L78 -170 Q0 -156 -78 -170 Z" fill="#B27672"/>
          <rect x="-16" y="-374" width="32" height="26" rx="8" fill="#C68B5E"/>
          <ellipse cx="-41" cy="-398" rx="6" ry="10" fill="#C68B5E"/><ellipse cx="41" cy="-398" rx="6" ry="10" fill="#C68B5E"/>
          <circle cx="0" cy="-402" r="42" fill="#3A2A20"/>
          <path d="M-30 -424 Q0 -446 30 -424 M-36 -404 Q0 -430 36 -404" stroke="#241810" stroke-width="3" fill="none"/>
          <circle cx="0" cy="-452" r="24" fill="#3A2A20"/><ellipse cx="0" cy="-434" rx="18" ry="6" fill="#F5A623"/>
        </g>
        <g id="b4" filter="url(#sh)"><rect x="-56" y="-38" width="112" height="76" rx="6" fill="#C4633A"/><rect x="-56" y="-38" width="112" height="16" fill="#A94F2A"/><rect x="-6" y="-38" width="12" height="76" fill="#F5A623"/><path d="M0 -38 C-30 -72 -48 -42 -8 -34 Z M0 -38 C30 -72 48 -42 8 -34 Z" fill="#F5A623"/></g>
        <g id="impact" opacity="0">
          <polygon id="star" fill="#F5A623" stroke="#101828" stroke-width="7" stroke-linejoin="round"/>
          <text x="790" y="985" text-anchor="middle" font-family="Inter,sans-serif" font-weight="900" font-size="84" fill="#101828" transform="rotate(-8 790 960)">BONK!</text>
          <g stroke="#101828" stroke-width="7" stroke-linecap="round"><line x1="1070" y1="990" x2="1100" y2="950"/><line x1="1000" y1="970" x2="990" y2="925"/><line x1="950" y1="1010" x2="915" y2="990"/></g>
          <g fill="#FFD66B" stroke="#101828" stroke-width="3">${[[960, 1015], [1060, 1005], [1010, 985]].map(([x, y]) => `<path transform="translate(${x} ${y}) scale(.9)" d="M0 -14 L4 -4 L14 -4 L6 3 L9 14 L0 7 L-9 14 L-6 3 L-14 -4 L-4 -4 Z"/>`).join("")}</g>
        </g>
      </svg>`;
      const hs = shake.querySelector("svg");
      {
        let s = "";
        for (let k = 0; k < 5; k++) {
          const x1 = k ? 240 + 190 * (k - 1) : 0, x2 = 240 + 190 * k, y = 760 + 150 * k;
          s += `<rect x="${x1}" y="${y + 20}" width="${x2 - x1}" height="30" fill="#000" opacity=".13"/>`;
          s += `<rect x="${x1}" y="${y}" width="${x2 - x1 + 10}" height="20" rx="4" fill="#B7824F"/><rect x="${x1}" y="${y}" width="${x2 - x1 + 10}" height="5" fill="#E4B886"/>`;
          s += `<rect x="${x1 + 18}" y="${y - 11}" width="${x2 - x1 - 32}" height="13" rx="3" fill="#6F8C68"/><rect x="${x1 + 18}" y="${y - 5}" width="${x2 - x1 - 32}" height="3" fill="#F5A623"/>`;
          s += `<rect x="${x2 - 16}" y="${y + 20}" width="16" height="130" fill="#5F7A59"/><rect x="${x2 - 16}" y="${y + 20}" width="3" height="130" fill="#F5A623"/>`;
        }
        hs.querySelector("#steps").innerHTML = s;
        let b = "";
        for (let x = 30; x < 990; x += 95) {
          const y1 = handY(x) + 10, y2 = treadY(x);
          b += `<rect x="${x - 6}" y="${y1}" width="12" height="${y2 - y1}" fill="#7A4A26"/><ellipse cx="${x}" cy="${y2 - 34}" rx="11" ry="16" fill="#8A5A34"/><ellipse cx="${x}" cy="${y1 + 20}" rx="9" ry="8" fill="#8A5A34"/>`;
        }
        hs.querySelector("#balusters").innerHTML = b;
        const r = L.rng(14);
        let m = "";
        for (let k = 0; k < 26; k++) { const x = 120 + r() * 800, y = 400 + (x - 120) * 0.9 + (r() - 0.5) * 360; m += `<circle class="mote" cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${(2 + r() * 3.5).toFixed(1)}" opacity="${(0.35 + r() * 0.5).toFixed(2)}"/>`; }
        hs.querySelector("#motes").innerHTML = m;
        const star = [];
        for (let i = 0; i < 16; i++) { const a = (i / 16) * Math.PI * 2, rr = i % 2 ? 88 : 150; star.push(`${(790 + Math.cos(a) * rr * 1.25).toFixed(0)},${(955 + Math.sin(a) * rr * 0.8).toFixed(0)}`); }
        hs.querySelector("#star").setAttribute("points", star.join(" "));
      }
      hs.querySelectorAll(".mote").forEach((m, k) => tl.fromTo(m, { x: 0, y: 0 }, { x: 14 + (k % 5) * 6, y: -30 - (k % 4) * 12, duration: 3.4, ease: "sine.inOut" }, 0));
      const woman = hs.querySelector("#woman"), b4 = hs.querySelector("#b4"), impact = hs.querySelector("#impact");
      const treadPos = (k) => ({ x: 240 + 190 * k - 95, y: 760 + 150 * k });
      gsap.set(woman, { x: treadPos(1).x, y: treadPos(1).y });
      gsap.set(b4, { x: treadPos(1).x, y: treadPos(1).y - 556 });
      [[0.25, 2], [0.9, 3], [1.55, 4]].forEach(([t, k], i) => {
        const p = treadPos(k);
        tl.to(woman, { x: p.x, duration: 0.45, ease: "power1.inOut" }, t - 0.3);
        tl.to(woman, { y: p.y - 40, rotation: i % 2 ? -2 : 2, duration: 0.2, ease: "power1.out" }, t - 0.3);
        tl.to(woman, { y: p.y, rotation: 0, duration: 0.25, ease: "power2.in" }, t - 0.1);
        tl.to(b4, { x: p.x, duration: 0.45, ease: "power1.inOut" }, t - 0.3);
        tl.to(b4, { y: p.y - 596, rotation: i % 2 ? -3 : 3, duration: 0.2, ease: "power1.out" }, t - 0.3);
        tl.to(b4, { y: p.y - 556, rotation: 0, duration: 0.25, ease: "power2.in" }, t - 0.1);
      });
      // the missed step, in slow motion: she pitches forward, silk floats out, the top box launches
      const fx = treadPos(4).x, fy = treadPos(4).y;
      tl.to(hs.querySelector("#legR"), { rotation: -38, transformOrigin: "50% 0%", duration: 0.25, ease: "power2.out" }, 1.95);
      tl.to(hs.querySelector("#legL"), { rotation: 12, transformOrigin: "50% 0%", duration: 0.3, ease: "power2.out" }, 2.0);
      tl.to(woman, { x: fx + 40, y: fy + 90, rotation: 12, duration: 0.95, ease: "power1.in" }, 2.0);
      tl.to(hs.querySelector("#boxes"), { rotation: 16, x: 30, transformOrigin: "0px -300px", duration: 0.6, ease: "power2.out" }, 2.1);
      tl.to(b4, { x: fx + 10, y: fy - 1020, rotation: 170, duration: 0.5, ease: "power2.out" }, 2.12);
      tl.to(b4, { x: 1020, y: 987, rotation: 352, duration: 0.38, ease: "power2.in" }, 2.62);
      const scG = hs.querySelector("#scarves");
      gsap.set(scG, { opacity: 0 });
      tl.set(scG, { opacity: 1 }, 2.18);
      hs.querySelectorAll(".sc").forEach((s, i) => {
        gsap.set(s, { x: -100, y: -410, scale: 0.25, rotation: 0, transformOrigin: "110px 15px" });
        const dx = [-430, -220, -330, 60][i], dy = [-640, -760, -480, -700][i];
        tl.fromTo(s, { x: -100, y: -410, scale: 0.25, rotation: 0 }, { x: -100 + dx, y: -410 + dy, scale: 1.15, rotation: [-28, 22, -12, 36][i], duration: 1.05, ease: "power2.out" }, 2.18);
        tl.fromTo(s, { attr: { d: WAVE_A } }, { attr: { d: WAVE_B }, duration: 0.24, yoyo: true, repeat: 3, ease: "sine.inOut" }, 2.18 + i * 0.05);
      });
      // BONK: the impact frame
      tl.set(impact, { opacity: 1 }, 3.0);
      tl.fromTo(impact, { scale: 0.2, transformOrigin: "900px 980px" }, { scale: 1, duration: 0.12, ease: "back.out(3)" }, 3.0);
      // camera: tracks her down the stairs, then a clumsy whip out to catch the fall
      gsap.set(hook.cam, { transformOrigin: "540px 960px" });
      tl.fromTo(hook.cam, { scale: 1.14, x: 150, y: -30 }, { x: -170, duration: 1.75, ease: "sine.inOut" }, 0);
      tl.to(hook.cam, { scale: 1, x: 0, y: 0, duration: 0.4, ease: "power3.out" }, 1.95);
      L.shake(hook.cam, 3.0, 16, 0.13);
      L.handheld(shake, 0, H - 0.05, 5, 21);
      tl.to(shake, { x: 0, y: 0, rotation: 0, duration: 0.05 }, H - 0.05);
      tl.fromTo(shake, { filter: "blur(5px)" }, { filter: "blur(0px)", duration: 0.4 }, 0);
      L.aiChip(hook);
      L.flash(H);
      L.drain(hook, H + 0.07, 0.6);

      // ================= BEAT 1 + 2 · the stairs become a stock chart that steps down to zero =================
      const chartD = "M180 580 H330 V805 H480 V1030 H630 V1255 H780 V1300 H930 V1300 H930";
      const chart = L.scene(H, tNight, { bg: "none" });
      const paper = L.div("fill bg-paper grid-paper", chart);
      chart.insertBefore(paper, chart.cam);
      L.div("grain", chart);
      const tPaper = at("L1.2") - 0.3;
      tl.fromTo(paper, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5 }, tPaper);
      tl.set(hook, { visibility: "hidden", display: "none" }, tPaper + 0.5);
      const ink = L.svg(chart.cam);
      const stair = L.ink(ink, stairD, H + 0.15, 1.2, { w: 9, ease: "none" });
      tl.to(stair, { attr: { d: chartD }, duration: 0.9, ease: "power3.inOut" }, at("L1.2"));
      L.ink(ink, "M140 1330 V500", at("L1.2") + 0.5, 0.5, { color: "#475467", w: 3 });
      L.ink(ink, "M140 1330 H950", at("L1.2") + 0.5, 0.5, { color: "#475467", w: 3 });
      L.rise(L.div("abs label", chart.cam, "left:150px;top:392px", "units left"), at("L1.2") + 0.8);
      L.rise(L.div("abs label", chart.cam, "left:880px;top:1348px", "days"), at("L1.2") + 0.8);
      // one scarf from the footage floats down to become the icon on the top step
      const scarf = L.div("abs", chart.cam, "left:0;top:0;width:110px;height:70px", `<svg width="110" height="70" viewBox="0 0 110 70"><path d="M10 40 c20 -30 40 10 60 -20 s30 10 30 -10" fill="none" stroke="#C4633A" stroke-width="16" stroke-linecap="round"/></svg>`);
      tl.fromTo(scarf, { x: 520, y: 420, rotation: -30, scale: 1.6 }, { x: 200, y: 505, rotation: 0, scale: 1, duration: 1.1, ease: "sine.inOut" }, at("L1.2"));
      // Beat 2 · the scarf hops down each step as the stock counts down
      const levels = [16, 11, 6, 1, 0], ty = (k) => [580, 805, 1030, 1255, 1300][k];
      const labs = levels.map((u, k) => L.div("tread-lab", chart.cam, `left:${180 + 150 * k}px;top:${ty(k) - 150}px`, String(u)));
      labs.forEach((lb) => (lb.style.visibility = "hidden"));
      L.show(labs[0], L2); L.pop(labs[0], L2, { from: 0.6 });
      L.series(L2 + 0.4, tGone - 0.05, 4).forEach((t, i) => {
        const k = i + 1;
        tl.to(scarf, { x: 200 + 150 * k, duration: 0.32, ease: "none" }, t - 0.32);
        tl.to(scarf, { y: ty(k) - 75 - 90, duration: 0.16, ease: "power2.out" }, t - 0.32);
        tl.to(scarf, { y: ty(k) - 75, duration: 0.16, ease: "power2.in" }, t - 0.16);
        tl.to(labs[k - 1], { opacity: 0.3, duration: 0.2 }, t);
        L.show(labs[k], t); L.pop(labs[k], t, { from: 0.5 });
      });
      L.stamp(chart.cam, "SOLD OUT", tGone, { x: 330, y: 1400, color: "leak", size: 72, r: -6 });
      ["restock?", "any left?", "back soon?"].forEach((b, i) => L.bubble(chart.cam, b, `left:${640 - i * 40}px;top:${560 + i * 118}px`, tGone + 0.3 + i * 0.3));
      L.slam(L.div("abs headline", chart.cam, "left:150px;top:1120px;font-size:96px", "gone."), tGone + 0.15);

      // ================= BEAT 3 + 4 · night: the math, then the rule =================
      const night = L.scene(tNight, tRip + 0.7, { bg: "night" });
      L.div("fill grid-paper", night, "opacity:.25");
      night.appendChild(night.cam);
      const eq = L.div("fill", night.cam);
      L.rise(L.div("abs label", eq, "left:72px;top:356px;font-size:30px;color:var(--sky)", "the math"), at("L3.1"));
      const L32 = "L3.2";
      const w1 = L.div("eq-word", eq, "left:72px;top:440px", "stock left");
      const o1 = L.div("eq-op", eq, "top:700px", "&divide;");
      const w2 = L.div("eq-word", eq, "top:710px", "daily sales");
      const o2 = L.div("eq-op", eq, "top:970px", "=");
      const w3 = L.div("eq-word", eq, "top:980px", "days left");
      L.slam(w1, at(L32)); L.pop(o1, at(`${L32}:divided`)); L.slam(w2, at(`${L32}:daily`)); L.pop(o2, at(`${L32}:equals`)); L.slam(w3, at(`${L32}:days`));
      const tNum = at(`${L32}e`) + 0.1;
      L.counter(eq, "right:150px;top:404px;text-align:right", "eq-num", 0, 16, tNum, 0.6, (v) => String(Math.round(v)), { steps: 16 });
      L.counter(eq, "right:150px;top:674px;text-align:right", "eq-num", 0, 5, tNum + 0.1, 0.5, (v) => String(Math.round(v)), { steps: 5 });
      L.counter(eq, "right:150px;top:944px;text-align:right;color:var(--green)", "eq-num", 0, 3.2, tNum + 0.2, 0.6, (v) => v.toFixed(1), { steps: 16 });
      [...eq.querySelectorAll(".eq-num")].forEach((n) => L.fadeIn(n, tNum - 0.02, 0.1));
      L.ink(L.svg(eq), "M200 1098 C360 1108 540 1092 640 1100", at(`${L32}e`) + 0.4, 0.4, {});
      L.fadeIn(L.div("abs label", eq, "right:150px;top:1106px;color:var(--sky);text-align:right;font-size:30px", "days"), tNum + 0.8, 0.3);
      L.chip(eq, "EXAMPLE", "left:72px;top:1250px", tNum + 0.4).classList.add("dark");
      tl.to(eq, { y: -120, autoAlpha: 0, duration: 0.4, ease: "power2.in" }, L4 - 0.3);
      // Beat 4 · two bars on one ruler; the gap between them is lost sales
      const rule = L.div("fill", night.cam);
      const rx = (d) => 110 + d * 82;
      const rs = L.svg(rule);
      L.ink(rs, `M${rx(0)} 1100 H${rx(10)}`, L4, 0.5, { color: "#A9C1F5", w: 4, ease: "power2.out" });
      for (let d = 0; d <= 10; d++) {
        L.ink(rs, `M${rx(d)} 1090 V1112`, L4 + 0.05 * d, 0.1, { color: "#A9C1F5", w: 3 });
        L.fadeIn(L.div("abs label", rule, `left:${rx(d) - 20}px;top:1122px;width:40px;text-align:center;color:var(--sky)`, String(d)), L4 + 0.05 * d, 0.2);
      }
      const bar = (x0, x1, y, h, color, t, dur) => { const b = L.div("abs", rule, `left:${rx(x0)}px;top:${y}px;width:${(x1 - x0) * 82}px;height:${h}px;background:${color};border-radius:10px;transform-origin:0 50%`); tl.fromTo(b, { scaleX: 0 }, { scaleX: 1, duration: dur, ease: "power3.out" }, t); return b; };
      bar(0, 3.2, 850, 60, "#34D399", L4 + 0.3, 0.5);
      L.rise(L.div("blab", rule, "left:110px;top:790px;color:var(--green)", "stock lasts 3.2 days"), L4 + 0.5);
      bar(0, 5, 940, 60, "#3B5BC9", at("L4:delivery"), 0.5);
      bar(5, 8, 940, 60, "#F5A623", at("L4:spare"), 0.4);
      L.rise(L.div("blab", rule, "left:130px;top:952px;font-size:28px;color:#FFFFFF", "delivery 5 days"), at("L4:delivery") + 0.3, { y: 10 });
      L.rise(L.div("blab", rule, "left:536px;top:952px;font-size:28px;color:var(--ink)", "+3 spare days"), at("L4:spare") + 0.3, { y: 10 });
      const hatch = L.div("abs", rule, `left:${rx(3.2)}px;top:840px;width:${4.8 * 82}px;height:170px;border:3px solid #E8683F;border-radius:10px;background:repeating-linear-gradient(135deg,rgba(232,104,63,.55) 0 8px,transparent 8px 20px)`);
      L.fadeIn(hatch, at("L4.1e") - 0.4, 0.4);
      L.rise(L.div("blab", rule, `left:${rx(5.3)}px;top:790px;color:#F08A63`, "sold-out days"), at("L4.1e") - 0.3);
      L.slam(L.div("abs num on-night", rule, "left:72px;top:380px;font-size:200px", "3.2 &lt; 8"), at("L4.1e"));
      L.chip(rule, "EXAMPLE", "left:78px;top:620px", L4 + 0.4).classList.add("dark");
      const scarfIcon = L.div("abs", rule, `left:${rx(0) - 40}px;top:1040px;width:80px;height:50px`, `<svg width="80" height="50" viewBox="0 0 110 70"><path d="M10 40 c20 -30 40 10 60 -20 s30 10 30 -10" fill="none" stroke="#C4633A" stroke-width="16" stroke-linecap="round"/></svg>`);
      L.pop(scarfIcon, L4 + 0.3);
      L.stamp(rule, "REORDER TODAY", at("L4.2"), { x: 150, y: 1220, color: "leak", size: 80, r: 6 });

      // ================= BEAT 5 · the app does it for every product, and fills in the purchase order =================
      const ap = L.scene(tRip, EC, { bg: "night" });
      L.ripple(ap, tRip, 420, 1290);
      const ph = L.phone(ap.cam, { x: 70, y: 420, w: 420, crumb: "Supply" });
      tl.fromTo(ph, { y: 80, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.5, ease: "power3.out" }, tRip + 0.3);
      const app = ph.app;
      L.div("abs app-h1", app, "left:16px;top:74px;margin:0", "Reorder");
      const alert = L.div("abs app-card", app, "left:14px;right:14px;top:124px;margin:0;border-left:5px solid #C4320A", `<div style="font-size:18px;font-weight:800">Time to buy more</div><div style="font-size:16px;font-weight:700;margin-top:6px">Silk Scarf (Rust)</div><div style="font-size:13px;color:#6B6B73;margin-top:4px">3.2 days left · supplier takes 5 days</div><div class="app-btn" style="margin-top:12px">Draft purchase order</div>`);
      L.rise(alert, tRip + 0.6, { y: 20 });
      [["Linen Wrap Dress (Sage)", "12 days left", "#139A66"], ["Gold Hoop Earrings", "9 days left", "#139A66"], ["Knit Sweater", "7 days left", "#B7791F"]].forEach(([n, d, c], i) => {
        const rw = L.div("abs app-card", app, `left:14px;right:14px;top:${318 + i * 74}px;margin:0;display:flex;align-items:center;font-size:14px;font-weight:600`, `${n}<span style="margin-left:auto;font-family:var(--mono);font-size:12px;color:${c}">${d}</span>`);
        L.rise(rw, tRip + 0.8 + i * 0.12, { y: 14 });
      });
      const tTap = L5 + 1.1;
      const as = L.svg(app, "", "0 0 390 844"); as.setAttribute("width", 390); as.setAttribute("height", 844);
      const tr = L.s(as, "circle", { cx: 100, cy: 262, r: 6, fill: "none", stroke: "#F5A623", "stroke-width": 5 }, "visibility:hidden");
      tl.set(tr, { visibility: "visible" }, tTap);
      tl.fromTo(tr, { attr: { r: 6 }, opacity: 1 }, { attr: { r: 90 }, opacity: 0, duration: 0.5, ease: "power2.out" }, tTap);
      const po = L.div("po", ap.cam, "", `<h5>PURCHASE ORDER</h5>`);
      tl.fromTo(po, { x: -380, scale: 0.4, autoAlpha: 0 }, { x: 0, scale: 1, autoAlpha: 1, duration: 0.5, ease: "back.out(1.3)" }, tTap + 0.25);
      L.chip(po, "SAMPLE SHOP DATA", "left:-20px;top:-22px");
      const fields = [["Item", "Silk Scarf (Rust)"], ["Quantity", "40"], ["Unit cost", "$11.50"], ["Total", "$460.00"]];
      const tF = L.series(tTap + 0.75, at("L5e") - 0.3, 4);
      fields.forEach(([k, v], i) => {
        const f = L.div("f", po, "", `<small>${k}</small>`);
        const val = L.div("", f, i === 3 ? "color:#139A66" : "");
        L.type(f, v, tF[i], 26, { el: val });
      });
      // fold into a paper plane and fly off the top edge
      const tFold = at("L5e") + 0.3;
      tl.to(po, { scale: 0.18, rotation: -20, autoAlpha: 0, duration: 0.35, ease: "power2.in" }, tFold);
      const plane = L.div("abs", ap.cam, "left:640px;top:800px;width:150px;height:110px;visibility:hidden", `<svg width="150" height="110" viewBox="0 0 150 110"><path d="M4 60 L146 6 L96 104 L70 70 Z" fill="#EFECE3" stroke="#101828" stroke-width="4" stroke-linejoin="round"/><path d="M146 6 L70 70 L60 96" fill="none" stroke="#101828" stroke-width="4" stroke-linejoin="round"/></svg>`);
      tl.set(plane, { visibility: "visible" }, tFold + 0.25);
      tl.fromTo(plane, { scale: 0.3, rotation: 0 }, { scale: 1, duration: 0.2, ease: "back.out(2)" }, tFold + 0.25);
      tl.to(plane, { x: 420, duration: 0.9, ease: "power1.in" }, tFold + 0.45);
      tl.to(plane, { y: -1000, rotation: -18, duration: 0.9, ease: "power2.in" }, tFold + 0.45);
      L.dotted(L.svg(ap.cam), "M700 860 C820 820 960 600 1070 -120", tFold + 0.5, 0.8, { w: 5, dash: "3 16" });

      // ================= end card =================
      L.flip(ap, EC - 0.45);
      const ecScene = L.endCard(EC - 0.45, "Comment STOCK.", { anim: EC });
      gsap.set(ecScene.cam, { y: 30 }); // a little room for the Attention Legend card above the logo

      // ================= ATTENTION SPAN LEADERBOARD =================
      // Top 100% at the start; one tier per story beat; Top 0.01% for watching to the very end.
      // Framing is implicit: focus time, streaks and ranks that grow, never "improve your attention span".
      // It opens as a full-screen "ATTENTION TEST" card (the pre-roll) that lands as the meter.
      const focusSecs = Math.round(T.total);
      const tBar = L.attentionTest({ top: 140, secs: focusSecs });
      L.attention({
        start: tBar,
        enter: "fade",
        top: 140,
        times: [H + 0.1, L2, L3, L4, L5, L5 + 3.1, EC + 0.6],
        labels: [
          { t: 1.25, until: 2.45, text: `${focusSecs}s OF FOCUS · TOP 0.01%`, color: "#A9C1F5" },
          { t: L5 + 1.5, until: L5 + 3.0, text: "DON'T BREAK THE STREAK", color: "#F08A63" },
          { t: EC - 1.25, until: EC - 0.05, text: "HOLD YOUR FOCUS", color: "#FFD66B" },
        ],
        countdown: EC - 0.9,
      });
      L.legend(EC + 0.6, { hold: T.total - EC, top: 264, sub: `${focusSecs} seconds of unbroken focus. Rank resets next reel. Follow and go longer.` });

      L.captions({ hide: [["L2.2", "L2e+0.4"], ["L3.2", "L3e+0.6"], ["L4", "L4e+0.6"]] });
      L.done();
    </script>
  </body>
</html>
