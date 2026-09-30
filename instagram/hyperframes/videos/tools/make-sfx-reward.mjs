// Reward sounds for the Attention Span Leaderboard (level-up, sparkle, fanfare, confetti, riser).
//   node tools/make-sfx-reward.mjs
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "_lib", "sfx");
mkdirSync(out, { recursive: true });
const N = "(random(0)*2-1)";
const ev = (expr, d, post = "") => ["-f", "lavfi", "-i", `aevalsrc='${expr}':s=48000:d=${d}${post ? "," + post : ""}`];

const kit = {
  // three rising notes C6 E6 G6 with a bell tail
  levelup: ev(`0.3*sin(2*PI*1046.5*t)*exp(-t*10)*lt(t,0.09)+gte(t,0.08)*lt(t,0.18)*0.3*sin(2*PI*1318.5*(t-0.08))*exp(-(t-0.08)*10)+gte(t,0.16)*(0.34*sin(2*PI*1568*(t-0.16))*exp(-(t-0.16)*3.5)+0.12*sin(2*PI*3136*(t-0.16))*exp(-(t-0.16)*6))`, 1.0),
  sparkle: ev(`0.16*sin(2*PI*(3600+900*sin(2*PI*11*t))*t)*exp(-mod(t,0.07)*38)*exp(-t*3)`, 0.7, "highpass=f=2500"),
  // pickup notes into a warm major chord
  fanfare: ev(`lt(t,0.12)*0.22*sin(2*PI*784*t)+gte(t,0.12)*lt(t,0.24)*0.22*sin(2*PI*1046.5*(t-0.12))+gte(t,0.24)*(0.17*sin(2*PI*523.25*(t-0.24))+0.15*sin(2*PI*659.25*(t-0.24))+0.14*sin(2*PI*783.99*(t-0.24))+0.13*sin(2*PI*1046.5*(t-0.24))+0.05*sin(2*PI*2093*(t-0.24)))*exp(-(t-0.24)*1.1)`, 2.6, "afade=t=in:d=0.02"),
  confetti: ev(`0.26*${N}*exp(-mod(t,0.043)*85)*exp(-t*2.2)`, 0.9, "highpass=f=2800"),
  riser: ev(`0.2*sin(2*PI*(220+520*t)*t)*pow(t/1.7,2)+0.1*${N}*pow(t/1.7,3)`, 1.7, "bandpass=f=1400:width_type=h:w=2400"),
};
let ok = 0;
for (const [name, args] of Object.entries(kit)) {
  const r = spawnSync("ffmpeg", ["-y", "-v", "error", ...args, "-ac", "2", "-ar", "48000", join(out, `${name}.wav`)], { encoding: "utf8" });
  if (r.status !== 0) console.error(`${name}: ${r.stderr}`); else ok++;
}
console.log(`reward sfx: ${ok}/${Object.keys(kit).length}`);
