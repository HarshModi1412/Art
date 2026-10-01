// High-energy hook sounds: a beat kit (kick, hat, clap), a drain gurgle, a coin cascade,
// a big impact and a reverse "suck" into the drain.
//   node tools/make-sfx-hook.mjs
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "_lib", "sfx");
mkdirSync(out, { recursive: true });
const N = "(random(0)*2-1)";
const ev = (expr, d, post = "") => ["-f", "lavfi", "-i", `aevalsrc='${expr}':s=48000:d=${d}${post ? "," + post : ""}`];

// music bed: chord index K changes every 2 s (one bar at 120 BPM); R is the bass root, TH the third
const K = "mod(floor(t/2),4)";
const R = `(110*(eq(${K},0)+eq(${K},1)*0.7937+eq(${K},2)*1.1892+eq(${K},3)*0.8909))`;
const TH = `(eq(${K},0)*1.1892+(1-eq(${K},0))*1.2599)`;
const I8 = "mod(floor(t*8),4)";
const MUSIC = [
  `0.34*exp(-mod(t,0.25)*9)*(sin(2*PI*${R}*mod(t,0.25))+0.45*sin(4*PI*${R}*mod(t,0.25))+0.2*sin(6*PI*${R}*mod(t,0.25)))`,
  `0.05*min(1,min(mod(t,2)*12,(2-mod(t,2))*12))*(sin(2*PI*2*${R}*mod(t,2))+sin(2*PI*2*${R}*${TH}*mod(t,2))+sin(2*PI*2*${R}*1.4983*mod(t,2)))*(0.8+0.2*sin(2*PI*4*t))`,
  `0.1*exp(-mod(t,0.125)*26)*sin(2*PI*4*${R}*(eq(${I8},0)+eq(${I8},1)*${TH}+eq(${I8},2)*1.4983+eq(${I8},3)*2)*mod(t,0.125))`,
].join("+");

const kit = {
  kick: ev(`0.95*sin(2*PI*(48+120*exp(-t*30))*t)*exp(-t*7.5)+0.35*${N}*exp(-t*400)`, 0.45, "lowpass=f=2400"),
  hat: ev(`0.3*${N}*exp(-t*75)`, 0.07, "highpass=f=7000"),
  clap: ev(`0.55*${N}*(exp(-t*30)+0.6*exp(-mod(t,0.011)*300)*lt(t,0.035))+0.25*sin(2*PI*210*t)*exp(-t*24)`, 0.3, "bandpass=f=1700:width_type=h:w=2600"),
  gurgle: ev(`0.4*${N}*(0.45+0.55*sin(2*PI*(8+5*sin(2*PI*1.3*t))*t))+0.28*sin(2*PI*(260+180*sin(2*PI*15*t))*t)*exp(-mod(t,0.13)*26)`, 1.5, "lowpass=f=1100,afade=t=in:d=0.12,afade=t=out:st=1.0:d=0.5"),
  coins: ev(`0.3*sin(2*PI*(2900+1700*mod(floor(t*26)*0.618,1))*t)*exp(-mod(t,0.0385)*55)*exp(-t*1.5)`, 1.3, "highpass=f=1800"),
  impact: ev(`0.95*sin(2*PI*(36+95*exp(-t*11))*t)*exp(-t*2.2)+0.6*${N}*exp(-t*28)+0.25*sin(2*PI*72*t)*exp(-t*3)`, 1.8, "lowpass=f=5200"),
  // a 120 BPM music bed: Am F C G, one chord a bar, bass eighths, a soft pad and a sixteenth-note arpeggio
  music: ev(MUSIC, 40, "lowpass=f=7000,afade=t=in:d=0.02"),
  suck: ev(`0.5*${N}*pow(t/0.55,3)*lt(t,0.55)+0.3*sin(2*PI*(900-700*t)*t)*pow(t/0.55,2)*lt(t,0.55)`, 0.58, "bandpass=f=1300:width_type=h:w=2200"),
};
let ok = 0;
for (const [name, args] of Object.entries(kit)) {
  const r = spawnSync("ffmpeg", ["-y", "-v", "error", ...args, "-ac", "2", "-ar", "48000", join(out, `${name}.wav`)], { encoding: "utf8" });
  if (r.status !== 0) console.error(`${name}: ${r.stderr}`); else ok++;
}
console.log(`hook sfx: ${ok}/${Object.keys(kit).length}`);
