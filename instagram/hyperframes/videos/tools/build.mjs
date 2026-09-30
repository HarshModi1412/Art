// Builds one video project from its script.json:
//   1. speaks every sentence with the local Kokoro voice (cached),
//   2. trims silence and lays the sentences on a timeline,
//   3. mixes voice + sound effects into assets/mix.wav,
//   4. writes index.html from index.src.html with the timing baked in.
//
//   node tools/build.mjs <video-folder>
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const lib = join(root, "_lib");
const cache = join(root, "_cache", "tts");
mkdirSync(cache, { recursive: true });

const dir = resolve(process.argv[2]);
const S = JSON.parse(readFileSync(join(dir, "script.json"), "utf8"));
const voice = S.voice || "af_heart";
const speed = S.speed || 0.94;
const run = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { encoding: "utf8", shell: false, ...opts });
  if (r.status !== 0) throw new Error(`${cmd} ${args.slice(0, 6).join(" ")}...\n${r.stderr || r.stdout}`);
  return r.stdout;
};
const duration = (f) => parseFloat(run("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]));

// ---------- 1 + 2: voice chunks ----------
function speak(text) {
  const key = createHash("sha1").update(`${voice}|${speed}|${text}`).digest("hex").slice(0, 16);
  const raw = join(cache, `${key}.raw.wav`);
  const trimmed = join(cache, `${key}.wav`);
  if (!existsSync(trimmed)) {
    for (let attempt = 0; attempt < 3 && !existsSync(raw); attempt++) {
      const r = spawnSync("cmd", ["/c", "npx", "--yes", "hyperframes@0.8.78", "tts", text, "-v", voice, "-s", String(speed), "-o", raw, "--json"], {
        encoding: "utf8", env: { ...process.env, HYPERFRAMES_SKIP_SKILLS: "1", PYTHONUTF8: "1" },
      });
      if (!existsSync(raw) && attempt === 2) throw new Error(`tts failed for "${text}": ${r.stdout}${r.stderr}`);
    }
    const trim = "silenceremove=start_periods=1:start_threshold=-48dB,areverse,silenceremove=start_periods=1:start_threshold=-48dB,areverse,adelay=30|30,apad=pad_dur=0.04";
    run("ffmpeg", ["-y", "-v", "error", "-i", raw, "-af", trim, "-ar", "48000", "-ac", "2", trimmed]);
  }
  return { file: trimmed, dur: duration(trimmed) };
}

function wordsFor(text, s, e) {
  const words = text.split(/\s+/).filter(Boolean);
  const weight = (w) => w.replace(/[^\w$%']/g, "").length + 1.6 + (/[,:;]$/.test(w) ? 2.2 : 0) + (/[.?!]$/.test(w) ? 3 : 0);
  const total = words.reduce((a, w) => a + weight(w), 0);
  let t = s;
  return words.map((w) => {
    const d = ((e - s) * weight(w)) / total;
    const out = { w, s: +t.toFixed(3), e: +(t + d).toFixed(3) };
    t += d;
    return out;
  });
}

const hook = S.hook;
let t = S.voStart ?? hook + 0.3;
const lines = [];
S.lines.forEach((line, li) => {
  if (line.at != null) t = Math.max(t, line.at);
  const L = { id: `L${li + 1}`, s: t, chunks: [] };
  line.say.forEach((text, ci) => {
    if (ci > 0) t += line.chunkGap ?? S.chunkGap ?? 0.2;
    const { file, dur } = speak(text);
    L.chunks.push({ text, file, s: +t.toFixed(3), e: +(t + dur).toFixed(3), words: wordsFor(text, t + 0.03, t + dur - 0.05) });
    t += dur;
  });
  L.e = +t.toFixed(3);
  L.s = +L.s.toFixed(3);
  lines.push(L);
  t += line.gapAfter ?? S.lineGap ?? 0.45;
});
const last = lines[lines.length - 1];
const endCard = S.endCardAt ? resolveExpr(S.endCardAt) : +(last.s - 0.25).toFixed(3);
const total = +Math.max(endCard + (S.endCardDur || 2.6), last.e + 0.7).toFixed(2);
const timing = { total, hook, endCard, lines: lines.map(({ id, s, e, chunks }) => ({ id, s, e, chunks: chunks.map(({ text, s, e, words }) => ({ text, s, e, words })) })) };

// ---------- expression resolver (same grammar as ledger.js T.at) ----------
function resolveExpr(expr) {
  if (typeof expr === "number") return expr;
  if (/^-?\d*\.?\d+$/.test(String(expr).trim())) return parseFloat(expr);
  const m = String(expr).replace(/\s+/g, "").match(/^(H|EC|T|L\d+(?:\.\d+)?e?(?::[^+\-]+?)?)((?:[+-]\d*\.?\d+)*)$/i);
  if (!m) throw new Error(`bad time expression: ${expr}`);
  let [, base, offs] = m;
  let v;
  if (base === "H") v = hook;
  else if (base === "EC") v = endCard;
  else if (base === "T") v = total;
  else {
    const [ref, word] = base.split(":");
    const lm = ref.match(/^L(\d+)(?:\.(\d+))?(e?)$/i);
    const L = lines[+lm[1] - 1];
    if (!L) throw new Error(`no line ${lm[1]} in ${expr}`);
    const C = lm[2] ? L.chunks[+lm[2] - 1] : null;
    if (word) {
      const want = word.replace(/>$/, "").toLowerCase();
      const pool = (C ? [C] : L.chunks).flatMap((c) => c.words);
      const hit = pool.find((w) => w.w.toLowerCase().replace(/[^\w$%']/g, "") === want) || pool.find((w) => w.w.toLowerCase().includes(want));
      if (!hit) throw new Error(`word "${want}" not in ${ref}`);
      v = word.endsWith(">") ? hit.e : hit.s;
    } else v = C ? (lm[3] ? C.e : C.s) : lm[3] ? L.e : L.s;
  }
  for (const o of (offs || "").match(/[+-]\d*\.?\d+/g) || []) v += parseFloat(o);
  return v;
}

// ---------- 3: mix ----------
mkdirSync(join(dir, "assets"), { recursive: true });
const inputs = [];
const voParts = [];
const fxParts = [];
lines.forEach((L) => L.chunks.forEach((c) => {
  inputs.push(c.file);
  voParts.push(`[${inputs.length - 1}:a]adelay=${Math.round(c.s * 1000)}:all=1[v${inputs.length - 1}]`);
}));
const voLabels = voParts.map((p) => p.match(/\[(v\d+)\]$/)[1]);
// entries: [time, name, vol] or {series:[from, to, count], name, vol}
const cues = (S.sfx || []).flatMap((c) => {
  if (Array.isArray(c)) return [c];
  const [a, b, n] = c.series.map((v, i) => (i < 2 ? resolveExpr(v) : v));
  return Array.from({ length: n }, (_, i) => [a + (n === 1 ? 0 : ((b - a) * i) / (n - 1)), c.name, c.vol ?? 0.4]);
});
cues.forEach(([expr, name, vol = 0.5]) => {
  const f = join(lib, "sfx", `${name}.wav`);
  if (!existsSync(f)) throw new Error(`missing sfx ${name}`);
  const at = resolveExpr(expr);
  if (at < 0 || at > total) return;
  inputs.push(f);
  fxParts.push(`[${inputs.length - 1}:a]adelay=${Math.round(at * 1000)}:all=1,volume=${vol}[f${inputs.length - 1}]`);
});
const fxLabels = fxParts.map((p) => p.match(/\[(f\d+)\]$/)[1]);
const graph = [
  ...voParts,
  `${voLabels.map((l) => `[${l}]`).join("")}amix=inputs=${voLabels.length}:normalize=0:dropout_transition=0,loudnorm=I=-15:TP=-1.5:LRA=11[vo]`,
  ...fxParts,
  fxLabels.length
    ? `${fxLabels.map((l) => `[${l}]`).join("")}amix=inputs=${fxLabels.length}:normalize=0:dropout_transition=0[fx]`
    : `anullsrc=r=48000:cl=stereo,atrim=0:${total}[fx]`,
  `[vo][fx]amix=inputs=2:normalize=0:dropout_transition=0,alimiter=limit=0.94,apad=whole_dur=${total},atrim=0:${total}[out]`,
].join(";");
const graphFile = join(root, "_cache", `${S.id}.graph.txt`);
writeFileSync(graphFile, graph);
// optional pre-roll (a title before the hook, e.g. "Attention test"): the whole reel plays
// after it, so content time 0 lands at PRE in the final mix and on the page timeline
const PRE = S.preroll ? S.preroll.dur : 0;
timing.pre = PRE;
const contentWav = PRE ? join(root, "_cache", `${S.id}.content.wav`) : join(dir, "assets", "mix.wav");
run("ffmpeg", ["-y", "-v", "error", ...inputs.flatMap((f) => ["-i", f]), "-/filter_complex", graphFile, "-map", "[out]", "-ar", "48000", "-ac", "2", contentWav]);
if (PRE) {
  const pin = [contentWav], parts = [`[0:a]adelay=${Math.round(PRE * 1000)}:all=1[pc]`];
  if (S.preroll.say) {
    const v = speak(S.preroll.say);
    console.log(`  pre-roll voice ${v.dur.toFixed(2)}s: ${S.preroll.say}`);
    pin.push(v.file);
    parts.push(`[1:a]loudnorm=I=-11:TP=-1.0:LRA=7,volume=${S.preroll.sayVol ?? 1},adelay=${Math.round((S.preroll.sayAt ?? 0.06) * 1000)}:all=1[pv]`);
  }
  (S.preroll.sfx || []).forEach(([t, name, vol = 0.5]) => {
    pin.push(join(lib, "sfx", `${name}.wav`));
    parts.push(`[${pin.length - 1}:a]adelay=${Math.round(t * 1000)}:all=1,volume=${vol}[p${pin.length - 1}]`);
  });
  const labels = parts.map((p) => p.match(/\[(p\w+)\]$/)[1]);
  const len = +(total + PRE).toFixed(2);
  const g = [...parts, `${labels.map((l) => `[${l}]`).join("")}amix=inputs=${labels.length}:normalize=0:dropout_transition=0,alimiter=limit=0.95,apad=whole_dur=${len},atrim=0:${len}[out]`].join(";");
  const gf = join(root, "_cache", `${S.id}.pre.graph.txt`);
  writeFileSync(gf, g);
  run("ffmpeg", ["-y", "-v", "error", ...pin.flatMap((f) => ["-i", f]), "-/filter_complex", gf, "-map", "[out]", "-ar", "48000", "-ac", "2", join(dir, "assets", "mix.wav")]);
}

// ---------- 4: html ----------
for (const f of ["ledger.css", "ledger.js", "reward.js"]) copyFileSync(join(lib, f), join(dir, f));
copyFileSync(join(lib, "grain.png"), join(dir, "assets", "grain.png"));
const src = readFileSync(join(dir, "index.tpl"), "utf8");
const HEAD = `<meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&family=JetBrains+Mono:wght@500;600;700&family=Kalam:wght@700&display=block" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <link rel="stylesheet" href="ledger.css" />`;
const ROOT = +(total + PRE).toFixed(2);
const STAGE = `<div id="root" data-composition-id="main" data-start="0" data-duration="${ROOT}" data-width="1080" data-height="1920">
      <div id="stage" class="clip" data-start="0" data-duration="${ROOT}" data-track-index="0"></div>
      <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="${ROOT}" data-track-index="9" data-volume="1"></audio>
    </div>
    <!--TIMING-->
    <script src="ledger.js"></script>`;
const html = src
  .replace("<!--HEAD-->", HEAD)
  .replace("<!--STAGE-->", STAGE)
  .replaceAll("{{TOTAL}}", String(total))
  .replace("<!--TIMING-->", `<script>window.T = ${JSON.stringify(timing)};</script>`);
writeFileSync(join(dir, "index.html"), html);
writeFileSync(join(dir, "timing.json"), JSON.stringify(timing, null, 1));
console.log(`${S.id}: ${total}s Â· ${lines.length} lines Â· ${fxLabels.length} sfx`);
lines.forEach((L) => console.log(`  ${L.id} ${L.s.toFixed(2)}-${L.e.toFixed(2)}  ${L.chunks.map((c) => c.text).join(" / ")}`));
console.log(`  end card ${endCard.toFixed(2)}`);
