---
brand: One Tap Manager
handle: "@onetapmanager"
audience: "Small online sellers in the US: boutiques, jewelry, fragrance and clothing shops run by one person"
format:
  width: 1080
  height: 1920
  fps: 30
colors:
  paper: "#F7F5EF"
  paper-2: "#EFECE3"
  ink: "#101828"
  ink-soft: "#475467"
  night: "#111827"
  indigo: "#1E3A8A"
  marigold: "#F5A623"
  money-green: "#34D399"
  sky: "#A9C1F5"
  leak: "#C4320A"
typography:
  display: { family: "Inter", weight: 800, tracking: "-0.03em", line-height: 1.02 }
  body: { family: "Inter", weight: 600, line-height: 1.3 }
  numbers: { family: "JetBrains Mono", weight: 700, tracking: "-0.04em" }
  labels: { family: "JetBrains Mono", weight: 500, case: "uppercase", tracking: "0.08em" }
  handwriting: { family: "Kalam", weight: 700, max-per-scene: 1 }
  sizes-px: { hook-line: 104, headline: 88, body: 40, caption: 54, label: 22, big-number: 220 }
spacing:
  safe-top: 230
  safe-bottom: 420
  safe-right: 150
  side-padding: 72
  card-radius: 28
  chip-radius: 12
  border: 3
components:
  ink-line: "One continuous marigold pen stroke, 6 px, round caps, slightly uneven like a real pen. It draws charts, arrows, circles and underlines, and it carries the eye from beat to beat."
  highlighter: "Marigold at 70% opacity behind one phrase only, rough edges, rotated -1.5 degrees, draws left to right in 0.35 s."
  stamp: "Rubber stamp with ink texture and uneven edges, rotated 4 to 8 degrees, leak red or indigo. Slams, overshoots 6%, settles."
  receipt: "paper-2 strip with a zig-zag torn edge, JetBrains Mono lines, prints out of a slot with a small shake."
  phone: "Plain black phone, 12 px bezel, 64 px corner radius, long soft shadow. Holds the rebuilt app UI."
  chip: "JetBrains Mono capitals, 22 px, ink-soft on paper-2, 12 px radius. Used for SAMPLE SHOP DATA, EXAMPLE, AI GENERATED, FORECAST, NOT A PROMISE."
  tap-ripple: "A marigold ring that expands from a tap point and fills the screen. The brand's own transition."
  page-flip: "A ledger page turns right to left in 0.45 s, with a paper-flutter sound."
  chat-bubble: "Our own bubble: paper-2 rounded box, 2 px ink border, Inter 600 ink text. Never WhatsApp's or Instagram's design."
  button: "Rounded rectangle, 20 px radius, never a pill."
motion:
  character: "Tactile paper and ink. Precise, confident and a little funny. Type slams in fast, then holds long enough to read. The world feels hand-made but expensive."
  eases:
    slam: "expo.out, 0.45 s, 3% overshoot"
    pop: "back.out(1.8), 0.4 s"
    glide: "power3.inOut, 0.8 s"
    drift: "sine.inOut, 3 to 6 s, finite repeats"
  transitions-allowed:
    - "hard cut on a sound hit"
    - "page flip"
    - "tap ripple wipe"
    - "ink-line match cut out of the hook footage"
    - "one warm shader reveal per video at most (a ripple or flash-through-white)"
  transitions-banned: ["glitch", "RGB split", "zoom blur", "spin", "star wipe", "3D cube", "light-leak spam", "lens flare"]
constraints:
  - "Never use purple or violet, neon colors, or full-screen two-color gradients."
  - "No emoji anywhere."
  - "No em dashes or en dashes in any on-screen text. In sentences write ranges as 10 to 15; in a table a plain hyphen is fine (33-34)."
  - "Every rebuilt app screen carries the SAMPLE SHOP DATA chip. Every illustrative number carries the EXAMPLE chip."
  - "Never invent reviews, customers, results, testimonials, follower counts or user numbers."
  - "Never show a human face in the graphics."
  - "Never copy the interface of Instagram, WhatsApp or any real app. Build our own simplified UI."
  - "Prices: 7-day free trial, Pro $10 a month, Pro Max $12.99 a month, never a percentage of sales. Ignore any rupee prices, Hindi text or India-specific copy found on the site."
  - "US English: color, jewelry, favorite. Dollars written as $12.99."
---

# One Tap Manager, in motion

## Two worlds
Every video has two worlds and one handoff.

1. **The hook world.** A short piece of real-looking phone footage that feels caught by accident. Leave it raw: no grading, no sharpening, no stabilizing, its own sound.
2. **The ledger world.** Warm paper with faint ruled lines, ink, a marigold pen, stamps, receipts, and our app rebuilt as clean cards. Night scenes use the night color with a soft indigo radial glow, never a flat fill.

**The handoff** is the signature move of the page. Freeze the hook on its peak frame, flash two frames of paper white, let the footage drain to paper tones, and have the marigold ink line trace one object from the footage. That traced shape becomes the first graphic: a ride becomes a sales chart, a staircase becomes a stock chart, a necklace chain becomes a row of coins. The viewer should never feel a cut between the two worlds.

## Signature devices
- **The ink line.** One pen stroke that keeps drawing across the video: tracing, underlining, circling, connecting cards to the phone.
- **The highlighter.** One marigold swash per scene, behind the phrase that matters.
- **Stamps.** For verdicts: SOLD OUT, APPROVED, REORDER TODAY, FIXED.
- **Receipts.** For money: they print, they unroll, they total.
- **The tap ripple.** The brand transition. It always starts from a real tap point.
- **Page flips.** From problem to fix.
- **For Shop Doctor only:** a heartbeat (ECG) line and a prescription pad (see the Shop Doctor section).

## Scene craft
- Three layers in every scene: a textured background (paper grain, ledger lines, radial glow), the message in the middle, and small accents in front (chips, dividers, a pen mark, a stray paper scrap).
- Eight to ten elements per scene. Every decorative element keeps a slow ambient motion (drift, breathe) so nothing looks frozen.
- Hero type fills 60 to 80% of the width. Pin content to edges; avoid centered floating layouts.
- Use at least three different eases and entry directions per video.
- Keep all text inside the safe area: 230 px clear at the top, 420 px clear at the bottom, 150 px clear on the right between y = 900 and y = 1700.

## Reading time
Fast motion, never fast text. A short label holds at least 0.8 s once settled. A sentence holds 0.3 s per word, minimum 1.2 s. Slam in, then hold.

## Captions
Word-level captions from the voice-over (transcribe it). Inter 700, 54 px, ink text on a paper box with 18 px by 28 px padding and 14 px radius. The word being spoken turns indigo. Two lines at most, six words a line, sitting just above the bottom safe area. Hide captions whenever the same words are on screen as big type.

## End card (last 2.5 s)
Paper background with ledger lines. The 1T logo (indigo rounded square, "1T" in off-white mono) 200 px wide at about 35% from the top, with one tap ripple. Under it the video's comment line in Inter 800, 72 px, ink. Under that "One shop problem. Fixed every week." in Inter 800, 52 px. Then "@onetapmanager" in JetBrains Mono, 34 px, ink-soft. Soft tap and a two-note rising chime. The last frame should cut cleanly back to the first frame of the hook.

## Audio
Voice-over on top at full level. The hook's own sound plays under the hook and fades out within 0.3 s once the voice starts. Sound effects are small and matched to motion: paper, pen, stamps, soft thuds, clicks, coins, chimes. No music in the render.

## Honesty
We are new, and we show it. Sample data is labelled. Examples show their arithmetic. Forecasts say they are forecasts. If you are unsure whether the app does something, leave it out.
