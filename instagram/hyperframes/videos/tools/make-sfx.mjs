// Synthesizes the small sound-effect kit (paper, pen, stamps, clicks, coins,
// chimes) with FFmpeg, plus the paper-grain texture. Run once:
//   node tools/make-sfx.mjs
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "_lib", "sfx");
mkdirSync(out, { recursive: true });

const N = "(random(0)*2-1)"; // white noise inside aevalsrc
const ev = (expr, d, post = "") => ["-f", "lavfi", "-i", `aevalsrc='${expr}':s=48000:d=${d}${post ? "," + post : ""}`];
const noise = (color, d, a, post) => ["-f", "lavfi", "-i", `anoisesrc=color=${color}:d=${d}:a=${a}:r=48000,${post}`];

const kit = {
  tick: ev(`0.55*sin(2*PI*1900*t)*exp(-t*90)`, 0.06),
  click: ev(`0.5*sin(2*PI*2600*t)*exp(-t*120)+0.3*${N}*exp(-t*300)`, 0.06),
  key: ev(`0.35*sin(2*PI*1300*t)*exp(-t*140)+0.35*${N}*exp(-t*260)`, 0.05, "highpass=f=700"),
  chain: ev(`0.55*sin(2*PI*900*t)*exp(-t*60)+0.25*${N}*exp(-t*200)`, 0.09),
  thud: ev(`0.95*sin(2*PI*(52+46*exp(-t*22))*t)*exp(-t*9)`, 0.5, "lowpass=f=900"),
  bass: ev(`0.95*sin(2*PI*(42+32*exp(-t*8))*t)*exp(-t*3.2)`, 1.1, "lowpass=f=220"),
  whoomp: ev(`0.95*sin(2*PI*(48+60*exp(-t*14))*t)*exp(-t*6)+0.2*${N}*exp(-t*12)`, 0.6, "lowpass=f=500"),
  stamp: ev(`0.85*sin(2*PI*(80+70*exp(-t*30))*t)*exp(-t*14)+0.5*${N}*exp(-t*38)`, 0.38, "lowpass=f=3200"),
  pop: ev(`0.6*sin(2*PI*(300+1500*t)*t)*exp(-t*32)`, 0.13),
  tap: ev(`0.5*sin(2*PI*3400*t)*exp(-t*80)+0.3*sin(2*PI*5200*t)*exp(-t*120)`, 0.09),
  chime: ev(`0.34*sin(2*PI*880*t)*exp(-t*6)*lt(t,0.2)+gte(t,0.2)*(0.34*sin(2*PI*1318.5*(t-0.2))*exp(-(t-0.2)*3.2)+0.08*sin(2*PI*2637*(t-0.2))*exp(-(t-0.2)*6))`, 1.5),
  ding: ev(`0.38*sin(2*PI*1568*t)*exp(-t*3)+0.18*sin(2*PI*3136*t)*exp(-t*5)+0.08*sin(2*PI*4704*t)*exp(-t*8)`, 1.4),
  bell: ev(`0.3*sin(2*PI*1046.5*t)*exp(-t*2.4)+0.14*sin(2*PI*2093*t)*exp(-t*4)+0.07*sin(2*PI*3140*t)*exp(-t*7)`, 1.6),
  coin: ev(`0.34*sin(2*PI*3100*t)*exp(-t*14)+0.28*sin(2*PI*4650*t)*exp(-t*18)+0.18*sin(2*PI*6200*t)*exp(-t*25)`, 0.4),
  heartbeat: ev(`0.95*sin(2*PI*56*t)*exp(-t*18)*lt(t,0.26)+0.75*gte(t,0.28)*sin(2*PI*50*(t-0.28))*exp(-(t-0.28)*16)`, 0.62, "lowpass=f=260"),
  beep: ev(`0.3*sin(2*PI*1000*t)*lt(t,0.14)`, 0.16, "afade=t=out:st=0.12:d=0.04"),
  scratch: ev(`0.5*sin(2*PI*(700+520*sin(2*PI*7*t))*t)*exp(-t*3)+0.3*${N}*exp(-t*4)`, 0.42, "bandpass=f=1500:width_type=h:w=1800"),
  deal: ev(`0.5*${N}*exp(-t*55)+0.2*sin(2*PI*2200*t)*exp(-t*90)`, 0.1, "highpass=f=1800"),
  creak: ev(`0.35*sin(2*PI*(170+45*sin(2*PI*9*t))*t)*(1+0.6*sin(2*PI*37*t))*exp(-t*2)`, 0.55, "bandpass=f=900:width_type=h:w=900"),
  boop: ev(`0.4*sin(2*PI*(320+700*t)*t)*exp(-t*4)`, 0.32),
  deflate: ev(`0.4*sin(2*PI*(520-300*t)*t)*exp(-t*2.5)`, 0.55),
  odometer: ev(`0.3*sin(2*PI*1500*mod(t,0.045))*exp(-mod(t,0.045)*120)`, 0.75, "afade=t=out:st=0.5:d=0.25"),
  printer: ev(`0.32*${N}*exp(-mod(t,0.055)*55)+0.06*sin(2*PI*120*t)`, 1.2, "bandpass=f=2200:width_type=h:w=2600,afade=t=out:st=1.0:d=0.2"),
  clatter: ev(`0.5*${N}*exp(-mod(t,0.11)*38)*exp(-t*2)`, 0.9, "lowpass=f=1400"),
  splat: ev(`0.6*${N}*exp(-t*24)+0.5*sin(2*PI*(90+120*exp(-t*30))*t)*exp(-t*16)`, 0.28, "lowpass=f=1100"),
  jingle: ev(`0.26*${N}*exp(-mod(t,0.07)*60)*exp(-t*2.2)`, 0.95, "highpass=f=4200"),
  screech: ev(`0.26*sin(2*PI*(2300+260*sin(2*PI*13*t))*t)*(1-exp(-t*20))`, 1.0, "bandpass=f=2400:width_type=h:w=1400,afade=t=out:st=0.6:d=0.4"),
  blender: ev(`0.3*sin(2*PI*118*t)*(1+0.6*sin(2*PI*236*t))+0.18*${N}`, 1.6, "bandpass=f=600:width_type=h:w=900,afade=t=in:d=0.15,afade=t=out:st=1.3:d=0.3"),
  bonk: ev(`0.8*sin(2*PI*(320+180*exp(-t*40))*t)*exp(-t*18)+0.3*${N}*exp(-t*60)`, 0.35, "lowpass=f=2400"),
  step: ev(`0.7*sin(2*PI*(110+80*exp(-t*40))*t)*exp(-t*20)+0.2*${N}*exp(-t*70)`, 0.22, "lowpass=f=1600"),
  trickle: ev(`0.2*${N}*(0.6+0.4*sin(2*PI*7*t))`, 1.6, "bandpass=f=1800:width_type=h:w=2400,afade=t=in:d=0.2,afade=t=out:st=1.2:d=0.4"),
  whoosh: noise("pink", 0.62, 0.55, "highpass=f=300,lowpass=f=4200,afade=t=in:d=0.28,afade=t=out:st=0.3:d=0.32"),
  flutter: noise("white", 0.46, 0.5, "highpass=f=1500,tremolo=f=28:d=0.8,afade=t=in:d=0.05,afade=t=out:st=0.22:d=0.24"),
  rustle: noise("pink", 0.36, 0.38, "highpass=f=2000,afade=t=in:d=0.08,afade=t=out:st=0.14:d=0.22"),
  pen: noise("brown", 0.32, 0.8, "bandpass=f=4000:width_type=h:w=3000,tremolo=f=13:d=0.6,afade=t=in:d=0.04,afade=t=out:st=0.22:d=0.1"),
  wind: noise("pink", 1.3, 0.7, "lowpass=f=700,afade=t=in:d=0.45,afade=t=out:st=0.7:d=0.6"),
  sigh: noise("pink", 0.6, 0.4, "lowpass=f=1500,afade=t=in:d=0.2,afade=t=out:st=0.3:d=0.3"),
  crowd: noise("pink", 3.0, 0.35, "bandpass=f=900:width_type=h:w=1200,tremolo=f=3:d=0.4,afade=t=in:d=0.3,afade=t=out:st=2.4:d=0.6"),
};

let ok = 0;
for (const [name, args] of Object.entries(kit)) {
  const r = spawnSync("ffmpeg", ["-y", "-v", "error", ...args, "-ac", "2", "-ar", "48000", join(out, `${name}.wav`)], { encoding: "utf8" });
  if (r.status !== 0) console.error(`${name}: ${r.stderr}`); else ok++;
}
console.log(`sfx: ${ok}/${Object.keys(kit).length}`);

// paper grain tile: soft monochrome noise, blended with multiply at low opacity
const grain = spawnSync("ffmpeg", ["-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x808080:s=512x512:d=1",
  "-vf", "noise=alls=48:allf=u,format=gray,eq=contrast=0.7:brightness=0.06", "-frames:v", "1", join(here, "..", "_lib", "grain.png")], { encoding: "utf8" });
console.log(grain.status === 0 ? "grain: ok" : grain.stderr);
