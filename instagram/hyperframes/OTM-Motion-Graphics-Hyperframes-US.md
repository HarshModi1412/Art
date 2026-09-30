---
title: "One Tap Manager: Motion Graphics Pack for Hyperframes"
subtitle: "6 reels and 4 Shop Doctor episodes · US English"
date: "Version 5 · 27 September 2026"
---

# How this works

You bring the hook clips. Hyperframes builds everything after the hook. You record the voice-over.

1. **Once:** copy the `DESIGN.md` below into the root of your Hyperframes project. Hyperframes reads it before anything else and treats it as brand truth. Then capture the site: `npx hyperframes capture https://onetapmanager.com`
2. **Per video, record the voice-over first.** Read the **Say this** lines at a relaxed pace, about 2.5 words a second. Save it as `assets/vo.wav`. The voice sets the timing of every scene, so it has to exist before Hyperframes starts.
3. Put your hook clip in the same folder as `assets/hook.mp4`.
4. Paste the video's **Hyperframes prompt** into your agent (Claude Code, Codex or Cursor with the Hyperframes skills installed).
5. Preview it, ask for fixes in plain words, then render. Upload to Instagram and add a trending sound from Instagram's library at very low volume under your voice. The render itself has no music.

**The app screens are rebuilt, not recorded.** Hyperframes rebuilds each app screen in HTML from your site capture and the screenshots in your `instagram/screenshots` folder, using the US sample data in each prompt. So you don't need new screen recordings. Every rebuilt screen must match the real app's layout and features, carry the SAMPLE SHOP DATA tag, and show sample numbers only.

## Make the hook look like an accident

Your hooks are handled. These six rules keep them feeling found, not filmed:

- **The camera is pointed at something else.** The event happens behind or beside the subject, and the camera finds it late.
- **One take, no cuts, no music.** Keep the real sound: chatter, wind, someone saying "wait, wait."
- **Handheld, vertical, a little crooked.** Let the focus and exposure hunt for a second.
- **The action starts partly out of frame.** A late whip or a clumsy zoom finds it.
- **Two to four seconds, cut at the peak.** The motion graphics pick up from that frame.
- **If a hook is AI-made,** ask for "filmed by a bystander on a phone, not aimed at the subject" and keep the AI GENERATED tag on it.

The phone-in-the-fryer hook is gone, and so is the website reel that went with it.


# DESIGN.md (put this in your Hyperframes project root)

````
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
````


# Posting calendar

| Week | Monday | Tuesday | Thursday | Friday |
|---|---|---|---|---|
| 1 | Post 1 (carousel, pin) | Post 3 (carousel, pin) | Reel 1: Know before the drop | Shop Doctor Ep 01: The push door |
| 2 | Reel 2: The car that left | Reel 4: The last step | Reel 3: The step stool | Shop Doctor Ep 02: Money in the wind |
| 3 | Reel 5: Money down the drain | Reel 6: The lid | Post 10 (carousel) | Shop Doctor Ep 03: The juggler |
| 4 | Post 7 (carousel) | | | Shop Doctor Ep 04: The round number |

**Fix two carousel lines, because Shop Doctor now runs on Fridays:**

- Post 1, Slide 6: change the sticker to "SHOP DOCTOR · EVERY FRIDAY", and in the caption change "every Tuesday" to "every Friday".
- Post 3, Slide 7: change the sticker to "SAVE FOR MONDAY".

Post 12 (the 0 to 20 challenge) still waits until card checkout works for US sellers.


# Part 1: Reels

Each reel runs: your hook, then the handoff, then the problem, then the app doing the fix, then the end card. About 30 seconds.

| Reel | Hook you already have | Business problem | Comment word |
|---|---|---|---|
| 1 | Grandpa on the drop tower | Sales dropped and you didn't notice | DEMO |
| 2 | The car that drifts out of the feed | Past customers leaving quietly | WINBACK |
| 3 | The step stool, the lights and the SUV | Holiday posting at midnight | WEEK |
| 4 | Silk scarves on the stairs | Running out of your best seller | STOCK |
| 5 | The necklace in the sink | Monthly app fees adding up | PRICE |
| 6 | The blender with no lid | "Runs small" reviews and returns | the weirdest review |


# Reel 1: Know before the drop

**Topic:** A sales drop you don't notice for weeks, and how to see it coming. **Comment word:** DEMO. **Length:** about 30 s.

**Hook:** your Grandpa clip. Everyone on the drop tower screams; Grandpa eats his popcorn. Cut the frame the seats reach the bottom.

**Say this** (about 70 words)

1. "Grandpa isn't scared. He watched the ride climb, so he knew the drop was coming."
2. "Your sales drop the same way. Quietly. Most sellers find out weeks later."
3. "One Tap Manager reads your sales file and tells you three things."
4. "How much you're down. Which products caused it. And what to do this week."
5. "So you see the drop coming, just like Grandpa."
6. "Comment DEMO and I'll send you the link."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager called "Know before the drop".

READ FIRST
- DESIGN.md in this project is brand truth: colors, fonts, spacing, motion, bans. Follow it exactly.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: npx hyperframes catalog --query "line chart draw", "card deal", "odometer counter", "ripple transition").

FORMAT
1080x1920, 30 fps. Length = hook + voice-over, about 30 s. The voice-over sets the pace: transcribe assets/vo.wav for word timings and start every beat on the first word of its line.

INPUTS (assets/)
- hook.mp4: accidental phone footage of a drop-tower ride where everyone screams except a calm grandpa eating popcorn. Play it untouched from 0 s until the seats reach the bottom. Keep its own sound. Never grade, sharpen or stabilize it.
- vo.wav: my voice-over. Each beat below quotes its line.
- The site capture of onetapmanager.com: use its logo, UI styling and components only.
- app-sales-chart.png: layout reference for the Sales screen. Rebuild it in HTML with the sample data below. Never paste the screenshot.

THE IDEA
Grandpa isn't scared because he watched the ride climb and knew exactly when the drop was coming. A seller's sales drop the same way, but most only find out weeks later. The app is Grandpa's seat at the top: it shows the drop, the reason and the fix.

RHYTHM
raw hook, FREEZE, slow trace, SLAM, flutter, RIPPLE, deal-deal-deal, pull back, hold, end card

HERO FRAME (build this first)
Night background with a soft indigo radial glow and fine paper grain. Left third: the phone, tilted 6 degrees, long soft shadow, showing the rebuilt Sales screen with the SAMPLE SHOP DATA chip. Right two thirds: three cards fanned out of the phone, each joined to it by a marigold ink line: "Down 10.6% vs the month before" (number in leak red), "Sold less: Linen Wrap Dress, Silk Scarf" (two small down arrows), "This week: reorder your best seller before it runs out" (money-green check). Top-left: "-10.6%" in JetBrains Mono at 220 px. One popcorn kernel resting on the third card. Two thin marigold rules framing the phone. A faint ledger grid and two drifting paper specks in the background.

BEAT 1 · FREEZE AND TRACE · VO 1: "Grandpa isn't scared. He watched the ride climb, so he knew the drop was coming."
Concept: we rewind the ride as ink. The climb, the pause at the top and the drop become one pen line on a page. The viewer should feel the footage turn into paper.
Mood: an old fairground poster meets an accountant's ledger. Saul Bass line work: one confident stroke.
Choreography: FREEZE on the last hook frame with a 2-frame flash of paper white. The footage DRAINS to paper tones over 0.6 s while a faint ledger grid FADES in over it. A marigold ink line DRAWS the ride's path from the lower left: it CLIMBS in small steps (one soft click per step, like the ride's chain), HOLDS at the top for one beat of silence, then DROPS straight down in 0.25 s. As it lands, the footage DISSOLVES away and only the line on paper remains. The whole beat has a slow 4% push-in.
Depth: background, the frozen frame turning into grain and ruled lines. Midground, the ink line and its step ticks, which become month labels in Beat 2. Foreground, one popcorn kernel that floats up out of the frame and hangs at the top of the line, bobbing gently.
On screen: captions only.
Sound: ride clicks carried over from the hook on each step, silence at the top, a whoosh on the drop.
Out: continuous. The line simply becomes the chart in Beat 2.

BEAT 2 · THE QUIET DROP · VO 2: "Your sales drop the same way. Quietly. Most sellers find out weeks later."
Concept: same line, now it is money. Revenue climbs month by month, then falls off a cliff last month, and nobody notices for weeks.
Mood: an editorial chart from a great newspaper. Calm, then a slap.
Choreography: the step ticks TYPE ON as months, Jan to Sep, in JetBrains Mono 22 px. A dollar axis GROWS up the left side ($4k, $6k, $8k). The last segment of the line turns leak red and "-10.6%" SLAMS in at 220 px with a small ink splatter, label "last month" under it. On "Quietly", the frame dims to 70% for one breath. On "weeks later", a paper wall calendar SLIDES in behind the chart and its pages FLIP fast from day 1 to day 24, then a handwritten Kalam note "noticed: day 24" gets circled by the ink line, with an EXAMPLE chip beside it.
Depth: background, paper and ledger lines with a soft vignette. Midground, the chart and the big number. Foreground, the calendar corner, the Kalam note, and the popcorn kernel still hanging at the old peak.
On screen: "-10.6%", "last month", "noticed: day 24".
Sound: soft heavy thud on the slam, fast page flutter, one low bass hit on "weeks later".
Out: TAP RIPPLE into night, starting from the red segment.

BEAT 3 · THE VIEW FROM THE TOP · VO 3: "One Tap Manager reads your sales file and tells you three things."
Concept: the app is Grandpa's seat at the top of the ride: it sees the whole thing.
Mood: a product reveal with keynote confidence, but warm and paper-textured, not glossy.
Choreography: the phone GLIDES up from below with a slight tilt (rotateX 12 to 0 degrees) and a long soft shadow. A small paper sheet labelled "sales.csv" DROPS into the screen and the rebuilt Sales screen FILLS row by row. Its chart redraws the same line from Beat 2, so the story stays continuous.
Depth: background, night with an indigo radial glow behind the phone and slow-drifting grain. Midground, the phone. Foreground, the csv sheet, the SAMPLE SHOP DATA chip, two thin marigold rules.
Sound: a whoosh up, a soft drop, small UI ticks.
Out: continuous.

BEAT 4 · THREE THINGS · VO 4: "How much you're down. Which products caused it. And what to do this week."
Concept: three cards dealt out of the phone, one on each phrase, exactly on the words. This is the HERO FRAME.
Choreography: card 1 DEALS out to the right on "How much you're down"; card 2 on "Which products caused it"; card 3 on "what to do this week". Each card POPS in (back.out 1.8) and an ink line DRAWS from the phone to it. All three hold together until the end of the line so they can be read. The popcorn kernel lands on card 3 with a tiny bounce.
Depth: background glow breathing slowly. Midground, phone and cards. Foreground, ink connectors and the kernel.
Sound: one card-deal sound per card, locked to the word.
Out: the camera PULLS BACK (scale 1 to 0.82) to show the chart again.

BEAT 5 · SEE IT COMING · VO 5: "So you see the drop coming, just like Grandpa."
Concept: the callback. The forecast continues upward as a dotted line, and the calm is now yours.
Choreography: a dotted ink line DRAWS forward from the red segment and curves up, labelled "Next 30 days: +8.2%", with the chip "FORECAST, NOT A PROMISE". The popcorn kernel HOPS in a small arc from card 3 to the top of the dotted line and settles.
Sound: one soft bell as the kernel settles.
Out: PAGE FLIP to the end card.

END CARD · VO 6: "Comment DEMO and I'll send you the link."
Per DESIGN.md, with the comment line "Comment DEMO."

SAMPLE DATA (label every app screen SAMPLE SHOP DATA)
Shop: Your Shop. Revenue last month $6,420, the month before $7,182 (-10.6%). Sold less: Linen Wrap Dress (Sage), Silk Scarf (Rust). Suggested this week: reorder the best seller before it runs out. Forecast, next 30 days: +8.2%.

CAPTIONS
Word-level captions per DESIGN.md. Hide them while "-10.6%" or the three cards are being read.

MUST NOT
- Show Grandpa's face in any graphic, or add anything to the hook footage.
- Use a stock line-chart look with gradient fills.
- Claim the app predicts the future. It shows a forecast.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
Grandpa wasn't scared of the drop. He watched the ride climb, so he knew exactly when it was coming.

Most sellers find out their sales fell weeks later, when the bills show up.

Upload one sales file (or try the sample data) and One Tap Manager shows you how much you're down, which products caused it, and what to do this week.

Sample shop data. Try it free for 7 days.

Comment DEMO and I'll send you the link.

#smallbusiness #smallbusinessowner #instagramshop
```

**Pinned comment:** "When did you last find out your sales dipped? Same week, next month, or when your accountant told you?"


# Reel 2: The car that left

**Topic:** Past customers leave without a word; win them back before a new follower. **Comment word:** WINBACK. **Length:** about 32 s.

**Hook:** your car clip. The car drifts out of the post, across the feed and off the screen. It looks most accidental as a screen recording someone forgot to stop: a thumb scrolling, a notification sliding in. Cut the frame after the car leaves.

**Say this** (about 68 words)

1. "That's exactly how customers leave. No goodbye. They just stop showing up."
2. "And you never notice, because new followers keep coming in."
3. "One Tap Manager finds everyone who went quiet: what they bought and when they left."
4. "It writes the message, adds a coupon, and sends it by email. You just check it."
5. "Then it counts who came back."
6. "Comment WINBACK and I'll send you three win-back emails, free."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager called "The car that left".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "counter", "typing text", "paper fold", "ripple transition").

FORMAT
1080x1920, 30 fps. Length = hook + voice-over, about 32 s. Transcribe assets/vo.wav and start every beat on the first word of its line.

INPUTS (assets/)
- hook.mp4: a car drifting out of a social media post and off the screen, filmed like a screen recording of someone scrolling. Play it untouched until the frame after the car leaves. Keep its sound.
- vo.wav: my voice-over.
- The site capture of onetapmanager.com: logo, UI styling and components only.
- app-winback.png: layout reference for the Win-back screen. Rebuild it in HTML with the sample data below.

THE IDEA
Customers leave the way that car did: no goodbye, just gone, while new followers keep ticking up and hide the loss. The empty parking lot becomes the seller's customer list with empty rows. The app finds who left, writes and sends the email, and counts who came back.

RHYTHM
raw hook, FREEZE, trace, slide-slide-LOCK, drift, drift, RIPPLE, type, fold, fly, return, hold, end card

HERO FRAME (build this first)
Paper background with ledger rows that were once parking spaces. Eight customer chips in the rows (initials circle, first name and last initial, last order date in mono). Three rows empty with dashed outlines tagged "went quiet". A bold marigold swoosh, the old skid mark, curving out through the right edge, with one chip halfway along it, leaving. Top-right: a sky-blue follower counter "1,207" with a tiny "+1". Bottom-left: the phone peeking in at 40% with the Win-back screen and the SAMPLE SHOP DATA chip. A torn paper scrap and a pencil mark as accents.

BEAT 1 · SKID MARKS · VO 1: "That's exactly how customers leave. No goodbye. They just stop showing up."
Concept: the empty lot turns into a customer ledger. The skid mark becomes the path customers leave by.
Mood: a top-down drone shot turned into an accountant's page. Wes Anderson symmetry.
Choreography: FREEZE on the empty lot with a 2-frame paper flash. The ink line TRACES the black tire marks along their curve in 0.8 s. The asphalt DRAINS into paper. The white parking lines ROTATE 90 degrees and SLIDE into horizontal ledger rows, LOCKING IN with small clicks. The skid mark stays as a bold marigold swoosh leaving through the right edge, and a tiny ink-outline car rides out along it. "No goodbye." appears small beside the swoosh; "They just stop." SLAMS in at 96 px.
Depth: background, paper with the asphalt texture fading out. Midground, the rows. Foreground, the swoosh, the tiny car, the slammed line.
Sound: the tire screech tail fades under, row clicks, a soft thud on the slam.
Out: continuous.

BEAT 2 · EMPTY ROWS · VO 2: "And you never notice, because new followers keep coming in."
Concept: numbers go up at the top while real people leave at the bottom. The contrast is the point.
Choreography: customer chips FILL the rows with a quick staggered pop. Then five chips, one by one, DRIFT out along the swoosh and exit right, each leaving a dashed empty outline tagged "went quiet". At the same time the sky-blue follower counter top-right ticks up, 1,204 to 1,207, with tiny pings.
Depth: background paper. Midground, rows and chips. Foreground, the counter, the swoosh, one chip mid-exit with slight motion blur.
Sound: soft pings for followers, a faint whoosh for each chip that leaves.
Out: TAP RIPPLE from the last empty row into night.

BEAT 3 · FOUND · VO 3: "One Tap Manager finds everyone who went quiet: what they bought and when they left."
Concept: the app turns the vague feeling into a list with names, items and dates.
Choreography: the phone GLIDES in with the rebuilt Win-back screen. The headline number COUNTS UP from 0 to 60, "60 customers went quiet". Rows SLIDE in. The ink line CIRCLES one row, and that row LIFTS out of the phone in 3D: "Maya R. · Linen Wrap Dress, Sage · last order Aug 3".
Depth: background, night with indigo glow. Midground, the phone. Foreground, the lifted row and the SAMPLE SHOP DATA chip.
Sound: counter ticks, a UI slide, a pencil scratch on the circle.

BEAT 4 · WRITTEN AND SENT · VO 4: "It writes the message, adds a coupon, and sends it by email. You just check it."
Concept: the work is done for her; she only checks.
Choreography: a message card TYPES ON beside the phone: "Hi Maya, the wrap dress you loved just came back in two new colors. Here's 10% off, just for you: COMEBACK10." The coupon chip SNAPS into the card. A thumb taps "Check and send" with a TAP RIPPLE. The card FOLDS into a paper envelope in 0.5 s and FLIES along the swoosh in reverse, back toward the ledger. Two more envelopes follow it.
Sound: typing, a snap, a paper fold, three whooshes.
Out: hard cut as the first envelope lands.

BEAT 5 · COUNTED · VO 5: "Then it counts who came back."
Concept: the payoff. Some of the empty rows fill again.
Choreography: back on the paper ledger, three chips DRIFT back in along the swoosh and settle into empty rows; their dashed outlines turn solid. A money-green counter "came back: 3" COUNTS up, with the EXAMPLE chip. The follower counter fades to 30%.
Sound: three soft chimes as chips land.
Out: PAGE FLIP to the end card.

END CARD · VO 6: "Comment WINBACK and I'll send you three win-back emails, free."
Per DESIGN.md, with the comment line "Comment WINBACK."

SAMPLE DATA (label every app screen SAMPLE SHOP DATA)
60 customers went quiet. Sample names: Maya R., Jordan T., Priya K., Emily S., Chris P., Ava L., Sam W., Nina G. Last orders between Jul 12 and Aug 20. Coupon code: COMEBACK10. Came back after the email: 3 (EXAMPLE).

MUST NOT
- Copy Instagram's feed design or WhatsApp's design.
- Say or show that the app sends WhatsApp messages by itself. Email is sent; WhatsApp is tap to send.
- Show real customer names.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
Customers don't leave with a goodbye. They just stop showing up in your orders.

The cheapest sale in your shop is someone who bought once and drifted. They trust you. They know your sizes.

One Tap Manager finds who went quiet, writes the message, and sends it by email (or gives you a tap-to-send WhatsApp link). Then it counts who came back.

Sample shop data. Try it free for 7 days.
Comment WINBACK and I'll DM you 3 ready-to-send win-back emails. Free.

#smallbusiness #shopsmall #boutiqueowner
```

**Pinned comment:** "Guess: how many past customers haven't ordered in 45 days? 0 to 10, 10 to 50, or 50+?"


# Reel 3: The step stool

**Topic:** Holiday posting done at midnight, and planning the week in one go. **Comment word:** WEEK. **Length:** about 29 s.

**Hook:** your step-stool clip. A man on a wobbly step stool hangs Christmas lights right above a new SUV with a red bow. Cut the instant the stool tilts, before anything lands.

**Say this** (about 64 words)

1. "The house is ready for Christmas. Is your Instagram?"
2. "Because this is how most of us post in December: eleven fifty-eight at night, still writing the caption."
3. "One Tap Manager plans your whole week in one tap."
4. "Posts, captions, hashtags and times. Christmas and New Year campaigns included."
5. "You look it over, approve it, and it posts."
6. "Comment WEEK for a free seven-day holiday posting plan."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager called "The step stool".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "split flap clock", "calendar", "card deal", "stamp", "ripple transition").

FORMAT
1080x1920, 30 fps. Length = hook + voice-over, about 29 s. Transcribe assets/vo.wav and start every beat on the first word of its line.

INPUTS (assets/)
- hook.mp4: accidental phone footage of a man on a wobbly step stool hanging Christmas lights over a brand-new SUV with a red bow. Play it untouched until the stool tilts. Keep its sound.
- vo.wav: my voice-over.
- The site capture of onetapmanager.com: logo, UI styling and components only.
- app-social.png: layout reference for the weekly planner. Rebuild it in HTML with the sample data below.

THE IDEA
Everyone watching the hook knows what's about to happen, so we freeze it and circle the car like a meme. Then the house's Christmas lights move onto a paper December calendar full of empty days. The house is ready; the Instagram is not. The app fills the week in one tap.

RHYTHM
raw hook, FREEZE + circle, swing, HARD CUT, tick-tick, RIPPLE, deal x7, stamp-stamp, APPROVE, cascade, hold, end card

HERO FRAME (build this first)
Paper background, a December calendar zoomed to one week, Mon to Sun. A string of warm Christmas lights hangs across the top edge of the calendar, bulbs glowing. Seven post cards sit in the seven days, each with a flat product illustration (dress, hoops, scarf, sweater, tote, perfume bottle, candle), a first caption line, two hashtag chips and a time chip. Two stamps: "CHRISTMAS" on Dec 24 and "NEW YEAR" on Dec 31. A leak-red hand-drawn circle around Dec 24, carried over from the hook. An indigo "APPROVED" stamp across the week. The phone at the bottom right at 40% with the SAMPLE SHOP DATA chip. A few paper snow specks drifting.

BEAT 1 · FREEZE AND CIRCLE · VO 1: "The house is ready for Christmas. Is your Instagram?"
Concept: the meme freeze, then the lights leave the house and hang over an empty content calendar.
Mood: a holiday shop window made of paper. Cozy, and a little alarming.
Choreography: FREEZE on the tilt with a record scratch. A leak-red hand-drawn circle DRAWS around the SUV in 0.5 s, slightly wobbly. The warm lights in the frame BLOOM softly; then the string of lights DETACHES from the house and SWINGS down to hang across the top of a paper December calendar that SLIDES up to fill the frame as the footage dissolves. The red circle SLIDES off the car and lands on Dec 24. On "Is your Instagram?", every day cell shows a dashed box "no post yet", and the camera PUSHES in 6%.
Depth: background, paper with slow-drifting snow specks. Midground, the calendar grid. Foreground, the light string (bulbs twinkling slightly out of sync, finite repeats) and the red circle.
Sound: record scratch, one beat of silence, a soft sleigh-bell shimmer as the lights swing.
Out: HARD CUT to night.

BEAT 2 · 11:58 PM · VO 2: "Because this is how most of us post in December: eleven fifty-eight at night, still writing the caption."
Concept: the real pain. Late, tired, caption half written.
Mood: a desk lamp at midnight. Quiet, dry, funny.
Choreography: a split-flap clock "11:58 PM" CLICKS into place at 200 px, JetBrains Mono. Under it a caption field TYPES "New holiday collection is here, DM for pri" and then BACKSPACES to "New holiday" and stops, cursor blinking. On "still writing", the clock FLIPS to 11:59. A crumpled paper ball ROLLS in from the left edge and stops.
Depth: background, night with a warm desk-lamp radial glow. Midground, the clock and the caption field. Foreground, the blinking cursor, the paper ball, a coffee-mug ring stain in the corner.
Sound: typing, backspace ticks, the flap of the clock.
Out: a "Plan this week" button SLIDES up; a thumb taps it; TAP RIPPLE to paper.

BEAT 3 · ONE TAP · VO 3: "One Tap Manager plans your whole week in one tap."
Concept: the app's planner takes over the calendar.
Choreography: the ripple settles into the rebuilt planner inside the phone, then the phone steps aside and the December calendar returns, zoomed to one week, as the camera PUSHES in.
Sound: a click, then a soft whoosh.

BEAT 4 · THE WEEK FILLS · VO 4: "Posts, captions, hashtags and times. Christmas and New Year campaigns included."
Concept: seven days, done. This is the HERO FRAME.
Choreography: seven post cards DEAL into the seven days, left to right, one every 0.25 s, then all hold. As the voice says "captions", "hashtags" and "times", that part of every card PULSES marigold in turn. On "Christmas and New Year", two stamps SLAM onto Dec 24 and Dec 31.
Sound: a card deal per card, two stamp thuds.

BEAT 5 · APPROVE · VO 5: "You look it over, approve it, and it posts."
Choreography: an "Approve" button (rounded rectangle, not a pill) presses with a TAP RIPPLE. An indigo "APPROVED" stamp SLAMS across the week at 6 degrees. Small check marks CASCADE across the seven cards. The light string at the top lights up fully and holds.
Sound: a click, a stamp, seven tiny ticks, a warm chime.
Out: PAGE FLIP to the end card.

END CARD · VO 6: "Comment WEEK for a free seven-day holiday posting plan."
Per DESIGN.md, with the comment line "Comment WEEK."

SAMPLE DATA (label every app screen SAMPLE SHOP DATA)
Caption first lines: "Wrap it or wear it?", "Hoops for every party this month", "The scarf that makes the coat", "Softest sweater we've ever stocked", "The tote that fits the whole weekend", "A scent for the holidays", "Last day for Christmas delivery". Times: 7:00 PM or 12:30 PM. Hashtag chips like #giftideas and #shopsmall.

MUST NOT
- Show a real Instagram interface.
- Show anyone falling or getting hurt.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
The house is lit. The car survived. The step stool did not.

Now the real holiday question: is your Instagram ready for Christmas, or will you be writing captions at 11:58 pm again?

One Tap Manager plans your whole week of Instagram in one tap: posts, captions, hashtags and times, plus Christmas and New Year campaigns. You approve, and it posts.

Sample shop data. Try it free for 7 days.

Comment WEEK and I'll DM you a free 7-day holiday posting plan.

#smallbusiness #instagramshop #shopsmall
```

**Pinned comment:** "Holiday posts ready? Yes, no, or 'starting tomorrow, for real'?"


# Reel 4: The last step

**Topic:** Running out of your best seller, and the simple reorder rule. **Comment word:** STOCK. **Length:** about 34 s.

**Hook:** your silk-scarves clip. She carries the box tower down the stairs, misses the last step, silk floats, a box bonks her head. Cut on the bonk.

**Say this** (about 78 words)

1. "She couldn't see the last step. You can't see the last piece of your best seller either."
2. "Stock goes down one step at a time. Then one day, it's just gone."
3. "The math: stock left, divided by daily sales, equals days left."
4. "If that's less than your supplier's delivery time plus three spare days, reorder today."
5. "One Tap Manager does this for every product and fills in the purchase order."
6. "Comment STOCK for the free reorder cheat sheet."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager called "The last step".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "step chart", "equation", "timeline bar", "stamp", "form fill", "paper plane").

FORMAT
1080x1920, 30 fps. Length = hook + voice-over, about 34 s. Transcribe assets/vo.wav and start every beat on the first word of its line.

INPUTS (assets/)
- hook.mp4: accidental phone footage of a woman, seen from behind, carrying a tower of gift boxes down old wooden stairs. She misses the last step, silk scarves float out, the last empty box bonks her head. Play it untouched until the bonk. Keep its sound.
- vo.wav: my voice-over.
- The site capture of onetapmanager.com: logo, UI styling and components only.
- app-supply.png: layout reference for the reorder alert and purchase order. Rebuild it in HTML with the sample data below.

THE IDEA
The step she couldn't see is the last piece of stock you can't see coming. The staircase becomes a stock chart that steps down to zero. Then the one rule that prevents it, shown as simple arithmetic, and the app doing it for every product.

RHYTHM
raw hook, FREEZE, trace, flatten, hop-hop-hop-hop, STAMP, HARD CUT, build equation, grow-grow, SLAM, RIPPLE, fill form, fly, end card

HERO FRAME (build this first)
Night background with indigo glow. Center: a horizontal timeline ruler from day 0 to day 10. A money-green bar from 0 to 3.2 labelled "stock lasts 3.2 days". Under it an indigo bar from 0 to 5 labelled "delivery 5 days" plus a marigold segment from 5 to 8 labelled "+3 spare days". The gap from 3.2 to 8 filled with a leak-red hatch labelled "sold-out days". Above: "3.2 < 8" in JetBrains Mono at 200 px. A leak-red "REORDER TODAY" stamp at 6 degrees. Bottom-right: the phone at 45% with the reorder alert and the SAMPLE SHOP DATA chip. A small silk-scarf icon sitting on the ruler at day 0. The EXAMPLE chip by the numbers.

BEAT 1 · STAIRS TO STEPS · VO 1: "She couldn't see the last step. You can't see the last piece of your best seller either."
Concept: the staircase becomes a stock chart. Each step down is a day of sales.
Mood: a clean architectural section drawing, then a chart. Precise, satisfying.
Choreography: FREEZE mid-fall with the silk in the air and a 2-frame paper flash. The ink line TRACES the staircase edge from top to bottom, step by step. The footage DRAINS to paper; the traced staircase TILTS and FLATTENS into a descending step chart with the axes "units left" and "days". One floating scarf from the footage is cut out and FLOATS down to become a small scarf icon on the top step.
Depth: background, paper and ledger lines. Midground, the step chart. Foreground, the scarf icon and a few silk threads drifting.
Sound: a soft scratch of the pen per step, a paper settle.
Out: continuous.

BEAT 2 · ONE STEP AT A TIME · VO 2: "Stock goes down one step at a time. Then one day, it's just gone."
Concept: the countdown nobody watches.
Choreography: the scarf icon HOPS down each step while the step labels COUNT DOWN: 16, 11, 6, 1, 0. At 0 a leak-red "SOLD OUT" stamp SLAMS in. Three of our own chat bubbles STACK in from the right: "restock?", "any left?", "back soon?". "gone." appears in Inter 800 at 96 px.
Depth: background paper. Midground, chart and stamp. Foreground, the bubbles and the scarf icon.
Sound: a light wood knock per hop, a heavy stamp thud, three small pings.
Out: HARD CUT to night.

BEAT 3 · THE MATH · VO 3: "The math: stock left, divided by daily sales, equals days left."
Concept: arithmetic you can do on a napkin.
Choreography: the words TYPE ON exactly with the voice, as kinetic type: "stock left" then "÷" then "daily sales" then "=" then "days left". Then the numbers ROLL IN under each word: 16 ÷ 5 = 3.2 days, with the EXAMPLE chip.
Depth: background, night with a soft indigo glow and faint grid. Midground, the equation. Foreground, a thin marigold underline drawing under "days left".
Sound: a soft key tick per word, an odometer roll for the numbers.

BEAT 4 · THE RULE · VO 4: "If that's less than your supplier's delivery time plus three spare days, reorder today."
Concept: two bars on one ruler; the gap between them is lost sales. This is the HERO FRAME.
Choreography: the timeline ruler DRAWS in. The money-green bar GROWS to 3.2 on "that". The indigo bar GROWS to 5 on "delivery time"; the marigold segment GROWS to 8 on "three spare days". The gap FILLS with leak-red hatching. "3.2 < 8" SLAMS in. The "REORDER TODAY" stamp lands on "reorder today".
Sound: two smooth grows, a thud on the slam, a stamp.
Out: TAP RIPPLE from the stamp into the phone.

BEAT 5 · THE APP · VO 5: "One Tap Manager does this for every product and fills in the purchase order."
Concept: the rule, done for every product, with the paperwork already filled in.
Choreography: the rebuilt reorder alert fills the phone: "Time to buy more · Silk Scarf (Rust) · 3.2 days left · supplier takes 5 days". A thumb taps "Draft purchase order"; a paper purchase order SLIDES out of the phone and its fields TYPE themselves: item, quantity 40, unit cost $11.50, total $460.00. The purchase order FOLDS into a paper plane and FLIES off the top edge.
Depth: background night. Midground, phone and purchase order. Foreground, the SAMPLE SHOP DATA chip and the plane's dotted flight path.
Sound: a tap, typing ticks, a paper fold, a whoosh.
Out: PAGE FLIP to the end card.

END CARD · VO 6: "Comment STOCK for the free reorder cheat sheet."
Per DESIGN.md, with the comment line "Comment STOCK."

SAMPLE DATA (label every app screen SAMPLE SHOP DATA)
Silk Scarf (Rust): 16 left, sells 5 a day, 3.2 days of stock. Supplier delivery: 5 days. Purchase order: 40 at $11.50 = $460.00.

MUST NOT
- Show the woman's face or anything that looks like an injury.
- Use jargon on screen: no "reorder point", "safety stock" or "EOQ". Say "spare days".

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
You can't see the last step when your arms are full. You can't see the last piece of your best seller either, until a customer asks for it.

Rule of thumb: reorder when the days of stock you have left are fewer than your supplier's delivery days plus 3 spare days.

One Tap Manager does that math for every product and fills in the purchase order for you.

Sample shop data. Try it free for 7 days.
Comment STOCK for the free reorder cheat sheet, before the holiday rush.

#smallbusiness #boutiqueowner #shopsmall
```

**Pinned comment:** "How many days will your best seller last? Stock divided by daily sales. Drop your answer."


# Reel 5: Money down the drain

**Topic:** Monthly app fees that add up, and one flat price instead. **Comment word:** PRICE. **Length:** about 32 s.

**Hook:** your necklace clip. The chain slips down the sink drain link by link until two fingers pinch it out. Cut the moment it's lifted.

**Say this** (about 72 words)

1. "Saved it. But your money slips away the same way. One small monthly charge at a time."
2. "Four apps, at their starting prices: about a hundred thirty-seven dollars a month."
3. "That's over sixteen hundred a year, before platform fees."
4. "One Tap Manager does all four jobs for twelve ninety-nine a month. Flat."
5. "Try it free for seven days. We never take a cut of your sales."
6. "Comment PRICE for the full comparison."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager called "Money down the drain".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "receipt print", "coin", "odometer counter", "morph", "ripple transition").

FORMAT
1080x1920, 30 fps. Length = hook + voice-over, about 32 s. Transcribe assets/vo.wav and start every beat on the first word of its line.

INPUTS (assets/)
- hook.mp4: accidental phone footage of a gold necklace slipping down a kitchen sink drain until two fingers pinch it out. Play it untouched until it is lifted out. Keep its sound.
- vo.wav: my voice-over.
- The site capture of onetapmanager.com: logo, UI styling and components only. Ignore any rupee prices on the site.

THE IDEA
The chain's links become monthly app charges, each one sliding down the drain. A receipt adds them up, a year multiplies it, and then all four coins come back up and merge into one flat price.

RHYTHM
raw hook, FREEZE, trace, roll-roll-roll-roll, PRINT, unroll, ROLL counter, RIPPLE, orbit, MERGE, SLAM, hold, end card

HERO FRAME (build this first)
Night background with indigo glow. Center-left: one large indigo coin with the 1T mark, glowing softly at the rim. Right of it: "$12.99 a month" in JetBrains Mono at 200 px, marigold, with "Pro Max · all four jobs" under it and "Pro: $10 a month" smaller below. Behind, slightly out of focus: the receipt from Beat 2, crumpling. Bottom: "0% of your sales. Ever." with the highlighter behind "Ever". A chip "7-DAY FREE TRIAL". Four faint coin trails curving up from a black ink drain at the bottom edge.

BEAT 1 · LINKS TO COINS · VO 1: "Saved it. But your money slips away the same way. One small monthly charge at a time."
Concept: the necklace chain becomes a chain of monthly charges, and they go down the drain one by one.
Mood: a still-life painting of coins, played like a magic trick.
Choreography: FREEZE on the lift with a 2-frame paper flash. The ink line TRACES the chain. Four links DETACH, FLIP into flat brass coins stamped with a tiny calendar icon and a price ($49, $49, $20, $18.75), ROLL across a paper floor and SPIRAL down a drain that is now a black ink circle in the lower center, one after another, 0.4 s apart. The footage dissolves behind them.
Depth: background, paper with grain. Midground, the rolling coins. Foreground, the drain rim and small ink splashes.
Sound: a coin clink and a hollow drop for each coin.
Out: continuous. A slot opens at the top edge.

BEAT 2 · THE RECEIPT · VO 2: "Four apps, at their starting prices: about a hundred thirty-seven dollars a month."
Concept: the monthly stack as one honest receipt.
Choreography: a receipt PRINTS down from the slot, one line at a time, in sync with the voice: "Analytics app $49.00", "Inventory app $49.00", "Win-back email app $20.00", "Instagram planner $18.75", a dashed line, "Total per month $136.75" in leak red. The chip "STARTING PRICES · SEPT 2026" sits at the top of the receipt.
Depth: background paper. Midground, the receipt. Foreground, the chip and a small paper curl at the receipt's edge.
Sound: printer chatter, a small tick per line.

BEAT 3 · THE YEAR · VO 3: "That's over sixteen hundred a year, before platform fees."
Concept: the same bill, for a whole year.
Choreography: the receipt keeps printing and UNROLLS past the bottom of the frame as the camera TILTS down with it. An odometer ROLLS "$136.75 × 12 = $1,641 a year" in leak red, with the small label "before platform fees".
Sound: a long printer run, an odometer roll, one low thud when $1,641 lands.
Out: TAP RIPPLE into night.

BEAT 4 · ONE COIN · VO 4: "One Tap Manager does all four jobs for twelve ninety-nine a month. Flat."
Concept: four coins come back and become one. This is the HERO FRAME.
Choreography: the four coins SHOOT back up out of the drain in reverse, ORBIT once, then MERGE into one indigo coin with the 1T mark. "$12.99 a month" SLAMS in beside it, "Pro Max · all four jobs" under it, and "Pro: $10 a month" smaller below. The receipt behind CRUMPLES into a ball and drops out of frame.
Sound: four rising clinks, a satisfying merge chime, a thud on the price.

BEAT 5 · THE PROMISE · VO 5: "Try it free for seven days. We never take a cut of your sales."
Choreography: the chip "7-DAY FREE TRIAL" CLICKS in. "0% of your sales. Ever." DRAWS in with "0%" in money green and the highlighter swash behind "Ever".
Sound: a click, a pen swash.
Out: PAGE FLIP to the end card.

END CARD · VO 6: "Comment PRICE for the full comparison."
Per DESIGN.md, with the comment line "Comment PRICE."

FACTS TO SHOW EXACTLY
Analytics app $49.00, Inventory app $49.00, Win-back email app $20.00, Instagram planner $18.75, total $136.75 a month, $1,641 a year. These are starting prices of popular apps in each category, checked September 2026. Our prices: Pro $10 a month, Pro Max $12.99 a month, 7-day free trial, never a percentage of sales.

MUST NOT
- Name or show the logos of the other apps.
- Round or change any price.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
Most tools grow their fee as you grow. You sell more, they take more. That's backwards.

What a small seller's app stack can cost at starting prices: analytics $49, inventory planning $49, win-back email $20, an Instagram planner $18.75. That's $136.75 a month, before any fees your selling platform takes.

One Tap Manager does all four jobs in one app. Pro is $10 a month. Pro Max is $12.99 a month, flat. Try it free for 7 days. We never take a percentage of your sales.

App prices are the starting plans of popular apps in each category, checked September 2026. Yours may cost more or less.

Comment PRICE and I'll send you the full comparison.

#smallbusiness #smallbusinessowner #instagramshop
```

**Pinned comment:** "How much do your apps cost you each month? Guess, and we'll do the math with you."


# Reel 6: The lid

**Topic:** One kind of bad review that keeps coming back, and the boring fix. **Comment prompt:** the weirdest review you've ever gotten. **Length:** about 30 s.

**Hook:** your blender clip. The blender starts with the lid off, a white wedding dress hangs right behind it, and the lid slams on just in time. Cut on the slam or on the single green drop.

**Say this** (about 65 words)

1. "One tiny drop. That's what one 'runs small' review does to a brand."
2. "Then another. Then twenty. And the returns start piling up."
3. "One Tap Manager reads your reviews file and finds the complaint costing you the most."
4. "For clothing, it's usually sizing. The fix is boring: a real size chart, in inches."
5. "That's the lid."
6. "Comment the weirdest review you've ever gotten."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager called "The lid".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "liquid morph", "bar chart", "table build", "ripple transition").

FORMAT
1080x1920, 30 fps. Length = hook + voice-over, about 30 s. Transcribe assets/vo.wav and start every beat on the first word of its line.

INPUTS (assets/)
- hook.mp4: accidental phone footage of a blender switched on with the lid off, a white wedding dress hanging behind it, the lid slammed on just in time, one green drop on the counter. Play it untouched until the slam. Keep its sound.
- vo.wav: my voice-over.
- The site capture of onetapmanager.com: logo, UI styling and components only.
- app-complaints.png: layout reference for the review analysis screen. Rebuild it in HTML with the sample data below.

THE IDEA
The one green drop becomes one bad review. Then more drops, more reviews, and the dress gets spattered while return parcels slide away. The app sorts every review and finds the loudest complaint. The fix is a size chart, and the size chart literally becomes the lid.

RHYTHM
raw hook, FREEZE, morph, splat-splat-splat, RIPPLE, sort, GROW, build table, SNAP (the lid), clean, hold, end card

HERO FRAME (build this first)
Paper background. Left half: an ink-outline drawing of the wedding dress, with small green spatters on the skirt. Right half: the phone with the rebuilt review analysis, a bar chart where "Sizing" is by far the tallest bar in leak red, labelled "17 of 40 reviews". Floating above the phone: a size chart card (S, M, L, XL with bust, waist and hip in inches) mid-flight, tilted like a lid about to land. Three review cards scattered at the bottom, one reading "Runs a size small." with two stars. Two small parcel icons with return arrows heading off the left edge. Chips SAMPLE SHOP DATA and SAMPLE REVIEWS.

BEAT 1 · DROP TO REVIEW · VO 1: "One tiny drop. That's what one 'runs small' review does to a brand."
Concept: the single green drop turns into a review card.
Mood: liquid and playful, like a claymation drop, then crisp paper.
Choreography: FREEZE on the drop with a 2-frame paper flash. The camera PUSHES in toward the drop as the footage drains to paper. The drop WOBBLES like a liquid blob and MORPHS into a paper review card: two stars, "Runs a size small.", with the SAMPLE REVIEWS chip.
Depth: background paper. Midground, the card. Foreground, a tiny leftover droplet and a faint ring on the paper.
Sound: a wet blip, a paper snap.
Out: continuous.

BEAT 2 · THE SPLASH · VO 2: "Then another. Then twenty. And the returns start piling up."
Concept: small problems multiply and splash the brand.
Choreography: more green drops FALL from the top, each one SPLATTING into a new review card that stacks messily. A counter COUNTS from 1 to 20. On the left, the ink line DRAWS the outline of the wedding dress, and small green spatters appear on its skirt. On "returns", three small parcel icons with return arrows SLIDE off the left edge.
Depth: background paper. Midground, the card pile and the dress outline. Foreground, the counter and the parcels.
Sound: soft splats, quickening; a cardboard slide per parcel.
Out: TAP RIPPLE into the phone.

BEAT 3 · SORTED · VO 3: "One Tap Manager reads your reviews file and finds the complaint costing you the most."
Concept: the mess becomes an ordered chart.
Choreography: the review cards FLY into the phone like cards into a deck. The rebuilt review analysis SORTS them into bars: "Love: fabric, color" in money green on one side; "Complaints" on the other: sizing 17, shipping 4, color 2. The sizing bar GROWS tallest in leak red, labelled "17 of 40 reviews". The ink line underlines "Loudest complaint: sizing".
Depth: background night with indigo glow. Midground, the phone and bars. Foreground, the underline and the SAMPLE SHOP DATA chip.
Sound: a shuffle, three bar grows, a pen underline.

BEAT 4 · THE FIX · VO 4: "For clothing, it's usually sizing. The fix is boring: a real size chart, in inches."
Concept: the boring fix, built live. This leads into the HERO FRAME.
Choreography: a size chart table ASSEMBLES row by row beside the phone: sizes S, M, L, XL; columns bust, waist, hip in inches. The word "boring" appears small and deadpan in Inter 600. Then the table LIFTS and tilts like a lid.

BEAT 5 · THAT'S THE LID · VO 5: "That's the lid."
Choreography: the size chart FLIPS and SNAPS onto the top of an ink-outline blender jar like a lid, with a satisfying click. On the dress outline, the green spatters WIPE clean in one sweep, and the return parcels SLIDE back in from the left and turn into check marks.
Sound: a firm click, a clean swoosh, a small chime.
Out: PAGE FLIP to the end card.

END CARD · VO 6: "Comment the weirdest review you've ever gotten."
Per DESIGN.md, with the comment line "Comment the weirdest review you've ever gotten." set on two lines.

SAMPLE DATA (label every app screen SAMPLE SHOP DATA, and review text SAMPLE REVIEWS)
40 sample reviews. Complaints: sizing 17, shipping 4, color 2. Praise: fabric and color. Size chart (EXAMPLE, inches): S bust 33-34, waist 26-27, hip 36-37 · M 35-36, 28-29, 38-39 · L 37-39, 30-32, 40-42 · XL 40-42, 33-35, 43-45. Write the size ranges with a hyphen, never a dash.

MUST NOT
- Invent real customer reviews or names. Every review shown is labelled SAMPLE REVIEWS.
- Claim how much money returns cost. Just show them piling up.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
"Nice product" tells you nothing. "Runs a size small" tells you exactly what to fix.

A size chart is the lid on your blender. Boring, small, and it saves the dress.

One Tap Manager reads your reviews file, groups what customers love and complain about, and shows you the complaint costing you the most. For clothing, it's usually sizing.

Sample shop data and sample reviews. Try it free for 7 days.

Comment the weirdest review you've ever gotten.

#smallbusiness #boutiqueowner #shopsmall
```

**Pinned comment:** "What's the weirdest review you've ever gotten? No customer names, just the review."


# Part 2: Shop Doctor, every Friday

One shop problem, diagnosed and fixed in about 45 seconds. Same shape every week, so people know it by the second episode:

**Hook (about 3 s)** → **handoff line** → **Shop Doctor sting (1.6 s)** → **the diagnosis** → **the fix** → **the prescription pad** → **"Next Friday"** end card.

Shop Doctor teaches first. The app only appears when it does the fix for real (Episode 3). Episodes 1, 2 and 4 are pure help, which is what makes people save and follow.

**Recording tip:** leave a two-second pause after the handoff line, marked *(pause for the sting)* in each script. The sting plays in that gap.

## Build the Shop Doctor kit once

Run this prompt one time. It makes three reusable pieces (the sting, the prescription pad and the Friday end card) that every episode plugs into.

```
/hyperframes
Build a reusable "Shop Doctor" series kit for One Tap Manager: three sub-compositions with variables, saved in shop-doctor-kit/, that I will plug into every Friday episode.

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Make every piece deterministic and seek-safe. Expose the listed values as variables so each episode only changes values, not code.

1. THE STING (exactly 1.6 s). Variable: episode ("EP 01").
Concept: the doctor listens to the shop's heartbeat.
Choreography: paper background with ledger lines. The marigold ink line DRAWS a stethoscope in one continuous stroke (earpieces, tube, chest piece) in 0.6 s. The chest piece TOUCHES a small paper storefront icon (striped awning, door, window). A heartbeat line (ECG) RUNS out of the storefront across the frame, spikes twice, and its last spike BURSTS into the tap ripple, which reveals the lockup: "SHOP DOCTOR" in Inter 800 at 110 px, ink, with the episode chip under it ("EP 01 · FRIDAY").
Depth: background paper grain. Midground, stethoscope, storefront, ECG line. Foreground, the chip and two tiny paper crosses drifting.
Sound: two soft heartbeat thumps, one monitor beep, the tap and the two-note chime.

2. THE PRESCRIPTION PAD (flexible 4 to 7 s). Variables: line1, line2, line3.
Concept: every episode ends with a prescription the viewer can screenshot.
Choreography: a paper-2 prescription pad SLIDES up and lands at a 3 degree tilt with a soft paper thud. Perforated top edge, a printed header "Shop Doctor · One Tap Manager" with the 1T logo, and a large marigold "Rx" at the top left. The three lines WRITE themselves in Kalam, one at a time, each ticked by the ink line as it finishes. An indigo "FIXED" stamp SLAMS in at the bottom right. The pad must stay fully readable and still for at least 2 s after the last line.
Depth: background, a wooden desk surface in soft focus with a pen lying beside the pad. Midground, the pad. Foreground, the stamp and a faint coffee ring on the pad's corner.
Sound: pen writing, three small ticks, a stamp.

3. THE FRIDAY END CARD (2.5 s). Variable: next_topic.
Use the end card from DESIGN.md, but line 1 is "Save this." and line 2 is "Next Friday: {next_topic}". Under them, small: "Shop Doctor · every Friday · @onetapmanager". Soft tap and the two-note chime. The last frame cuts cleanly back to frame 1 of the episode.

Render a short test of each piece with sample values so I can check them.
```


# Shop Doctor Ep 01: The push door

**Topic:** "DM for price" adds steps between wanting and buying. Remove them. **Length:** about 45 s.

**Hook idea (accidental):** someone films their latte through a café window; behind them, a man pushes a PULL door three times before he pulls it. Cut on the third push.

**Say this** (about 100 words)

1. "He's not the problem. The door is."
2. "And 'DM for price' is your push door." *(pause for the sting)*
3. "Every extra step between 'I want it' and 'I bought it' loses someone."
4. "Count yours. See the post. Send a DM. Wait for a reply. Ask about sizes. Wait again. Get a link. Pay."
5. "Seven steps. Every one of them is a chance to change their mind."
6. "The fix: price in the post. Sizes in the post. One link that goes straight to checkout."
7. "Three steps. See it. Tap it. Buy it."
8. "Save this before your next post."
9. "Next Friday: where your profit actually goes."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager: Shop Doctor, Episode 01, "The push door".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Use the Shop Doctor kit in shop-doctor-kit/ for the sting, the prescription pad and the end card.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "3D corridor", "door", "card stack", "counter", "ripple transition").

FORMAT
1080x1920, 30 fps, about 45 s. Transcribe assets/vo.wav and start every beat on the first word of its line. The voice has a 2-second pause after line 2: play the sting there.

INPUTS (assets/)
- hook.mp4: accidental phone footage through a café window: a man in the background pushes a PULL door three times. Play it untouched until the third push. Keep its sound.
- vo.wav: my voice-over.

THE IDEA
The PULL door is funny because the door is badly designed, not because the man is silly. "DM for price" is the same kind of door for a shopper. We walk through all seven doors a buyer has to open, then knock them down to three.

RHYTHM
raw hook, FREEZE, trace, bump-bump-bump, STING, dolly through doors, deal x7, SLAM, fold, tile-tile-tile, Rx pad, end card

HERO FRAME (build this first)
Paper world. A 2.5D corridor of seven paper doors receding into the center of the frame, each door a slightly different warm paper tone with an ink outline and a small numbered plaque (1 to 7). "I want it" pinned top-left in Inter 800, "I bought it" bottom-right. Small ink shopper dots walking the corridor; a few near the doors peeling off and floating away. A leak-red "7" at 260 px in the upper right. One door in the foreground ajar with light spilling out onto the floor. Paper texture, ledger lines on the floor, soft vignette.

BEAT 1 · THE PULL SIGN · VO 1 + 2: "He's not the problem. The door is." / "And 'DM for price' is your push door."
Concept: the café door turns into an Instagram post with a push door in it.
Mood: comic timing from a great animated short, built from paper cutouts.
Choreography: FREEZE on the third push with a 2-frame paper flash. The ink line CIRCLES the "PULL" sign, then TRACES the door frame. The footage DRAINS to paper. The door outline MORPHS into a phone-shaped post card of our own design, and the PULL sign MORPHS into the caption line "DM for price". A small ink arrow labelled "push" BUMPS against the caption three times and bounces off each time.
Depth: background paper. Midground, the post card. Foreground, the bumping arrow and a small ink scuff mark on each bump.
Sound: three soft bumps like a door rattling, one tiny sigh of air.
Out: the Shop Doctor STING (EP 01) in the voice pause.

BEAT 2 · THE CORRIDOR · VO 3: "Every extra step between 'I want it' and 'I bought it' loses someone."
Concept: the buyer's path is a corridor of doors. This leads into the HERO FRAME.
Mood: impossible paper architecture, like a puzzle-game corridor made of card stock.
Choreography: "I want it" SLAMS in at the top-left, "I bought it" at the bottom-right. The corridor of seven doors UNFOLDS between them like a pop-up book. The camera DOLLIES slowly forward through the doors; each door SWINGS open with a small creak as we pass. Ink shopper dots walk the corridor, and at each door one or two dots PEEL OFF and float away.
Depth: background, the far end of the corridor fading into paper. Midground, the doors. Foreground, the two phrases and dots passing close to the lens.
Sound: soft creaks, paper footsteps.

BEAT 3 · COUNT YOURS · VO 4: "Count yours. See the post. Send a DM. Wait for a reply. Ask about sizes. Wait again. Get a link. Pay."
Concept: the seven steps, counted out loud.
Choreography: the doors FOLD flat and become a vertical stack of numbered step cards (our chat-bubble style), one DEALT in per phrase, numbered 1 to 7 in JetBrains Mono: "See the post", "Send a DM", "Wait for a reply", "Ask about sizes", "Wait again", "Get a link", "Pay". The two "wait" cards carry a small clock whose hands spin. The stack grows taller than the frame and the camera TILTS up to follow it.
Sound: a card deal per step, a soft tick-tock on the wait cards.

BEAT 4 · SEVEN · VO 5: "Seven steps. Every one of them is a chance to change their mind."
Choreography: a leak-red "7" SLAMS in at 260 px; the stack SHUDDERS once. Under the 7, small: "chances to change their mind".
Sound: one heavy soft thud.

BEAT 5 · THE FIX · VO 6 + 7: "The fix: price in the post. Sizes in the post. One link that goes straight to checkout." / "Three steps. See it. Tap it. Buy it."
Concept: seven doors become one open door.
Choreography: the stack FOLDS like paper into three big tiles in a row. Tile 1 "See it": a post card with a price chip "$68" and size chips S, M, L, XL. Tile 2 "Tap it": a thumb tap with a tap ripple. Tile 3 "Buy it": a money-green check. In the background, six doors SLAM shut one after another and one wide door stays open with a straight path of light through it. "See it. Tap it. Buy it." lands one word group per tile, exactly on the voice.
Sound: a paper fold, three light clicks, one warm chime.

BEAT 6 · PRESCRIPTION · VO 8: "Save this before your next post."
Use the prescription pad with: line1 "Price in every post", line2 "Sizes in every post", line3 "One link to checkout".

END CARD · VO 9: "Next Friday: where your profit actually goes."
Use the Friday end card with next_topic "where your profit goes".

MUST NOT
- Mock the man in the hook. The joke is the door.
- Use statistics about how many buyers leave. We don't have a source.
- Copy Instagram's post design.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
Shop Doctor, episode 1: the push door.

"DM for price" feels normal. For a buyer it's seven steps: see the post, DM, wait, ask about sizes, wait again, get a link, pay. Every step is a chance to change their mind.

The fix: put the price and the sizes in the post, plus one link that goes straight to checkout. See it, tap it, buy it.

Save this before your next post. New Shop Doctor every Friday.

#smallbusiness #smallbusinessowner #instagramshop
```

**Pinned comment:** "Be honest: how many of your posts say 'DM for price'? None, some, or all of them?"


# Shop Doctor Ep 02: Money in the wind

**Topic:** The hidden costs that eat your profit, and how to price for the profit you want. **Length:** about 48 s.

**Hook idea (accidental):** filmed from a car's passenger seat at a drive-thru while someone films the menu board; the driver hands cash out the window, a gust takes the bills across the lot, someone yells "no, no, no". Cut as the bills fly.

**Say this** (about 105 words)

1. "That's your profit when you forget the hidden costs." *(pause for the sting)*
2. "Say you sell a dress for thirty-five dollars. It cost you twelve. So you make twenty-three, right?"
3. "Now add the rest. Packaging, a dollar twenty. The label for your 'free shipping', six fifty. Card fees, about a dollar thirty. And set aside five percent for returns, a dollar seventy-five."
4. "You don't make twenty-three. You make twelve twenty-three. About half."
5. "The fix: list every cost once, then price for the profit you want. At forty-four dollars, you keep about twenty and a half."
6. "Save this and check your best seller tonight."
7. "Next Friday: the juggler."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager: Shop Doctor, Episode 02, "Money in the wind".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Use the Shop Doctor kit in shop-doctor-kit/ for the sting, the prescription pad and the end card.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "stacked bar", "odometer counter", "slider", "price tag", "strike through").

FORMAT
1080x1920, 30 fps, about 48 s. Transcribe assets/vo.wav and start every beat on the first word of its line. The voice has a 2-second pause after line 1: play the sting there.

INPUTS (assets/)
- hook.mp4: accidental phone footage from a car at a drive-thru: cash blows out of the driver's hand across the parking lot. Play it untouched until the bills are in the air. Keep its sound.
- vo.wav: my voice-over.

THE IDEA
The bills blowing away are the costs sellers forget. We catch each one, put a label on it, and stack them against the price to show the real profit. Then we move the price until the profit is what the seller actually wants.

RHYTHM
raw hook, FREEZE, tag-tag-tag-tag, STING, swing, stack x5, STRIKE, SLAM, slide, fill, Rx pad, end card

HERO FRAME (build this first)
Paper background. Left: a paper price tag on a string, swinging slightly, reading "$35". Center: a vertical stacked bar of five paper bills, each a different warm tone with its label and amount: "product $12.00", "packaging $1.20", "shipping $6.50", "card fees $1.32", "returns $1.75". Next to it a JetBrains odometer: "costs $22.77". Right: "$23?" struck through with a scribbled ink line, and "$12.23" in leak red at 180 px, labelled "real profit". Bottom: a ledger ruler slider with a marigold handle at $35. Chip "EXAMPLE". Two paper bills still drifting in the top corners.

BEAT 1 · CATCH THE BILLS · VO 1: "That's your profit when you forget the hidden costs."
Concept: each flying bill is a cost.
Mood: a heist movie freeze-frame, but on paper.
Choreography: FREEZE with the bills in mid-air and a 2-frame paper flash. The ink line DARTS from bill to bill and TAGS each with a label that pops on a string: "packaging", "shipping", "card fees", "returns". The footage DRAINS to paper; the real bills are replaced by stylized paper bills with a "$" and the 1T seal, and they keep DRIFTING slowly in parallax.
Depth: background paper grain. Midground, the tagged bills. Foreground, two bills drifting close to the lens, slightly soft.
Sound: a gust of wind that stops dead on the freeze, four pen ticks.
Out: the Shop Doctor STING (EP 02) in the voice pause.

BEAT 2 · THE TAG · VO 2: "Say you sell a dress for thirty-five dollars. It cost you twelve. So you make twenty-three, right?"
Choreography: a paper price tag on a string SWINGS in from the top: "$35". Under it, the sum TYPES ON: "$35 − $12 cost = $23". A Kalam question mark WOBBLES after it on "right?".
Sound: a string creak, typing ticks, a small questioning boop.

BEAT 3 · THE REAL STACK · VO 3: "Now add the rest. Packaging, a dollar twenty. The label for your 'free shipping', six fifty. Card fees, about a dollar thirty. And set aside five percent for returns, a dollar seventy-five."
Concept: the bills fly back in and stack up. This builds the HERO FRAME.
Choreography: on each cost the voice names, its bill FLIES in from the edge and STACKS onto a vertical stacked bar beside the tag, landing with a soft thud: product $12.00 (already there), packaging $1.20, shipping $6.50, card fees $1.32, returns $1.75. A JetBrains odometer beside the stack ROLLS up with each landing to "costs $22.77". The chip "EXAMPLE · card fee: Stripe's standard 2.9% + 30¢" appears under the card-fee bill.
Sound: a soft thud per bill, an odometer roll.

BEAT 4 · THE REAL PROFIT · VO 4: "You don't make twenty-three. You make twelve twenty-three. About half."
Choreography: the ink line SCRIBBLES through "$23". "$12.23" SLAMS in at 180 px in leak red, labelled "real profit". Small, deadpan: "about half".
Sound: a pen scribble, one heavy soft thud.

BEAT 5 · THE FIX · VO 5: "The fix: list every cost once, then price for the profit you want. At forty-four dollars, you keep about twenty and a half."
Concept: move the price, watch the profit.
Choreography: a ledger ruler slider SLIDES the price tag from $35 to $44. The stack RECALCULATES live as it moves (card fees become $1.58, returns become $2.20, costs $23.48). A money-green profit meter FILLS from $12.23 to $20.52. The EXAMPLE chip stays on.
Sound: a smooth slide with fine ruler ticks, a bright chime when the meter lands.

BEAT 6 · PRESCRIPTION · VO 6: "Save this and check your best seller tonight."
Use the prescription pad with: line1 "List every cost once", line2 "Price for the profit you want", line3 "Recheck when fees change".

END CARD · VO 7: "Next Friday: the juggler."
Use the Friday end card with next_topic "the juggler".

EXAMPLE NUMBERS (show exactly)
Price $35.00. Costs: product $12.00, packaging $1.20, shipping label $6.50, card fee $1.32 (2.9% + 30¢), returns set-aside 5% = $1.75. Total costs $22.77. Profit $12.23. At $44.00: card fee $1.58, returns $2.20, total costs $23.48, profit $20.52.

MUST NOT
- Draw realistic US banknotes. Use stylized paper bills only.
- Change or round any number.
- Show the driver's face.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
Shop Doctor, episode 2: money in the wind.

Sell a dress for $35 that cost you $12, and it feels like $23 profit. Now add packaging ($1.20), the label for your "free shipping" ($6.50), card fees ($1.32 at Stripe's standard 2.9% + 30¢) and 5% set aside for returns ($1.75). You keep $12.23. About half.

The fix: list every cost once, then price for the profit you want. At $44, you keep $20.52.

Example numbers. Run your own.

Save this and check your best seller tonight. New Shop Doctor every Friday.

#smallbusiness #smallbusinessowner #pricingtips
```

**Pinned comment:** "Which cost do sellers forget most? Packaging, shipping, card fees or returns?"


# Shop Doctor Ep 03: The juggler

**Topic:** Too many products, no focus. Find the few that pay the bills. **Length:** about 48 s.

**Hook idea (accidental):** a tourist films a busy plaza; in the background a street juggler keeps seven things in the air, then all of them crash down. Cut on the crash.

**Say this** (about 105 words)

1. "Seven things in the air. Zero caught." *(pause for the sting)*
2. "That's a shop with thirty products and no idea which ones pay the bills."
3. "In a lot of small shops, a handful of products bring in most of the money."
4. "Here's a sample shop. Twelve products. Three of them made seventy-one percent of last month's sales."
5. "So catch those three first. Keep them in stock, post them more, and put them first on your page."
6. "The rest? Keep juggling. Just slower."
7. "One Tap Manager shows you which products bring the money in, on one screen."
8. "Save this, and find your top three tonight."
9. "Next Friday: the magic of a round number."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager: Shop Doctor, Episode 03, "The juggler".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Use the Shop Doctor kit in shop-doctor-kit/ for the sting, the prescription pad and the end card.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "bar chart race", "bracket callout", "spotlight", "ripple transition").

FORMAT
1080x1920, 30 fps, about 48 s. Transcribe assets/vo.wav and start every beat on the first word of its line. The voice has a 2-second pause after line 1: play the sting there.

INPUTS (assets/)
- hook.mp4: accidental phone footage of a plaza where a street juggler in the background drops everything. Play it untouched until the crash. Keep its sound.
- vo.wav: my voice-over.
- The site capture of onetapmanager.com: logo, UI styling and components only.
- app-sales-top.png: layout reference for the sales-by-product screen. Rebuild it in HTML with the sample data below.

THE IDEA
The juggler's falling objects become the products in a shop. We pile them up, then sort them into a chart that shows three products carrying most of the sales. The seller catches those three first and juggles the rest slower.

RHYTHM
raw hook, FREEZE, circle x7, drop, STING, rain, sort, GROW x12, BRACKET SLAM, spotlight x3, slow arcs, RIPPLE, Rx pad, end card

HERO FRAME (build this first)
Paper background with ledger lines. A horizontal bar chart of 12 products sorted from the top, each bar with a small flat product icon at its left and its share at its right. The top three bars in marigold, the rest in ink at 35%. A hand-drawn bracket around the top three with "3 products = 71% of sales" in Inter 800 at 88 px. Three warm spotlight circles on the top three icons, each with a chip: "keep in stock", "post more", "first on your page". In the background, nine small icons arcing slowly in juggling paths. Chip SAMPLE SHOP DATA.

BEAT 1 · SEVEN IN THE AIR · VO 1: "Seven things in the air. Zero caught."
Concept: the juggler's objects become products.
Mood: a vintage circus poster meets a clean product catalog.
Choreography: FREEZE with the objects in mid-air and a 2-frame paper flash. The ink line CIRCLES each of the seven objects in quick succession. Each object is cut out and MORPHS into a flat product icon (wrap dress, gold hoops, silk scarf, knit sweater, tote, perfume bottle, candle) that keeps moving along its juggling arc. The footage DRAINS to paper. "0 caught" appears as a chip. Then all seven DROP to the bottom of the frame.
Depth: background paper. Midground, the seven icons in arcs. Foreground, ink circles and small motion marks.
Sound: seven quick pen ticks, then a clatter of seven soft paper drops.
Out: the Shop Doctor STING (EP 03) in the voice pause.

BEAT 2 · THE PILE · VO 2: "That's a shop with thirty products and no idea which ones pay the bills."
Choreography: more product icons RAIN in from the top and heap onto a ledger shelf until the pile is messy and tall. A chip "30 products" CLICKS in beside it.
Sound: a soft cascade of paper drops.

BEAT 3 · THE HANDFUL · VO 3 + 4: "In a lot of small shops, a handful of products bring in most of the money." / "Here's a sample shop. Twelve products. Three of them made seventy-one percent of last month's sales."
Concept: the pile sorts itself into the truth. This builds the HERO FRAME.
Choreography: the pile SORTS itself: icons fly into a sorted horizontal bar chart of 12 products, and the bars GROW from the left one after another with their shares counting up. The top three bars turn marigold. On "three of them", a bracket DRAWS around the top three and "3 products = 71% of sales" SLAMS in.
Sound: a quick shuffle, twelve light ticks as bars grow, one thud on the slam.

BEAT 4 · CATCH THREE · VO 5: "So catch those three first. Keep them in stock, post them more, and put them first on your page."
Choreography: three warm spotlight circles LAND on the top three icons. On each phrase, one chip CLICKS in beside its icon: "keep in stock", "post more", "first on your page". The three icons HOP up and are caught in one smooth juggling arc.
Sound: three soft spotlight thunks, three clicks.

BEAT 5 · SLOWER · VO 6: "The rest? Keep juggling. Just slower."
Choreography: the other nine icons DRIFT up into slow, lazy juggling arcs in the background, dimmed to 35%, moving at half speed (finite repeats).
Sound: a gentle whoosh, almost nothing.

BEAT 6 · ON ONE SCREEN · VO 7: "One Tap Manager shows you which products bring the money in, on one screen."
Choreography: TAP RIPPLE from the top bar into the phone, which GLIDES in with the rebuilt sales-by-product screen: the same ranking, with revenue bars and the SAMPLE SHOP DATA chip.
Sound: a tap, a soft whoosh.

BEAT 7 · PRESCRIPTION · VO 8: "Save this, and find your top three tonight."
Use the prescription pad with: line1 "Find your top 3", line2 "Never let them sell out", line3 "Give them the best spots".

END CARD · VO 9: "Next Friday: the magic of a round number."
Use the Friday end card with next_topic "the magic of a round number".

SAMPLE DATA (label every chart and app screen SAMPLE SHOP DATA)
Share of last month's sales: Linen Wrap Dress 31%, Gold Hoop Earrings 24%, Silk Scarf 16%, Knit Sweater 7%, Satin Slip Skirt 5%, Pearl Necklace 4%, Everyday Tote 4%, Amber Rose Perfume 3%, Denim Jacket 2%, Hair Claw Clip 2%, Soy Candle 1%, Gift Card 1%. The top three add up to 71%.

MUST NOT
- Say that this is true for every shop. It is a sample shop.
- Show the juggler's face.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
Shop Doctor, episode 3: the juggler.

Thirty products in the air and no idea which ones pay the bills. In a lot of small shops, a handful of products bring in most of the money.

In our sample shop, 3 of 12 products made 71% of last month's sales. Catch those first: keep them in stock, post them more, and put them first on your page. Keep juggling the rest, just slower.

One Tap Manager shows which products bring the money in, on one screen. Sample shop data. Try it free for 7 days.

Save this, and find your top three tonight. New Shop Doctor every Friday.

#smallbusiness #smallbusinessowner #boutiqueowner
```

**Pinned comment:** "How many products do you sell right now? Drop the number. Bonus points if you know your top 3."


# Shop Doctor Ep 04: The round number

**Topic:** Use a free shipping minimum to get one more item in the cart. **Length:** about 43 s.

**Hook idea (accidental):** filmed through a car window at a gas station: the pump display rolls up and stops exactly on $20.00, and someone in the car cheers. Cut on the cheer.

**Say this** (about 95 words)

1. "Exactly twenty dollars. Everyone loves a round number." *(pause for the sting)*
2. "Your customers do too. That's why a free shipping minimum works."
3. "Look at your typical order. Say it's thirty-eight dollars."
4. "Set free shipping a little above it. Like forty-five."
5. "Now the shopper at thirty-eight sees 'seven dollars away from free shipping', and adds one more thing."
6. "Set it so that extra item covers the shipping you're giving away."
7. "Too high, and nobody reaches it. Too low, and you pay shipping on every order."
8. "Save this, and look up your typical order tonight."
9. "Next Friday: a new shop problem."

**Hyperframes prompt**

```
/hyperframes
Make a vertical Instagram reel for One Tap Manager: Shop Doctor, Episode 04, "The round number".

READ FIRST
- DESIGN.md in this project is brand truth. Follow it exactly.
- Use the Shop Doctor kit in shop-doctor-kit/ for the sting, the prescription pad and the end card.
- Build the HERO FRAME below as a still first. Animate only once it looks right.
- Search the catalog before hand-building any block (for example: "flip counter", "progress bar", "split screen", "balance scale").

FORMAT
1080x1920, 30 fps, about 43 s. Transcribe assets/vo.wav and start every beat on the first word of its line. The voice has a 2-second pause after line 1: play the sting there.

INPUTS (assets/)
- hook.mp4: accidental phone footage at a gas station: the pump display stops exactly on $20.00 and someone cheers. Play it untouched until the cheer. Keep its sound.
- vo.wav: my voice-over.

THE IDEA
The joy of hitting exactly $20.00 at the pump is the same pull a free shipping minimum creates in a cart. We show the gap between a typical order and the minimum, the one small item that closes it, and why the minimum must be set with care.

RHYTHM
raw hook, FREEZE, peel, flip, STING, bag, draw bar, gap, slide, FILL, burst, balance, split, Rx pad, end card

HERO FRAME (build this first)
Paper background. A horizontal ledger-ruler progress bar across the middle from $0 to $50 with a marigold flag at $45 labelled "free shipping". The bar filled in money green up to $50, with a small burst at the flag. Above it a JetBrains flip counter showing "$50.00". Below: a paper shopping bag with a folded dress, a tote and a small hair claw clip card dropping in at an angle. A banner of our own design: "You unlocked free shipping". Chip EXAMPLE. Two small paper receipts drifting in the corners.

BEAT 1 · THE PUMP · VO 1: "Exactly twenty dollars. Everyone loves a round number."
Concept: the pump's perfect stop, turned into our flip counter.
Mood: the quiet satisfaction of a perfect stop, then a paper world.
Choreography: FREEZE on "20.00" with a 2-frame paper flash. The ink line CIRCLES the display. The digits PEEL off the footage and become a JetBrains flip counter on paper as the footage DRAINS away. The counter flips back to 19.98, then 19.99, then lands on 20.00 again with a small bounce.
Depth: background paper. Midground, the flip counter. Foreground, a small ink circle and two marigold sparkle ticks.
Sound: a gentle digit roll, a clean chime on 20.00.
Out: the Shop Doctor STING (EP 04) in the voice pause.

BEAT 2 · THE TYPICAL ORDER · VO 2 + 3: "Your customers do too. That's why a free shipping minimum works." / "Look at your typical order. Say it's thirty-eight dollars."
Choreography: a paper shopping bag SLIDES in holding a folded dress and a tote. A small receipt PRINTS beside it: "typical order $38.00", with the EXAMPLE chip.
Sound: a paper rustle, printer ticks.

BEAT 3 · THE LINE · VO 4: "Set free shipping a little above it. Like forty-five."
Choreography: a ledger-ruler progress bar DRAWS across the frame from $0 to $50. A marker sits at $38. A marigold flag PLANTS at $45 labelled "free shipping". The gap between $38 and $45 fills with a marigold hatch labelled "$7 away".
Sound: a pen draw, a small flag thunk.

BEAT 4 · ONE MORE THING · VO 5: "Now the shopper at thirty-eight sees 'seven dollars away from free shipping', and adds one more thing."
Concept: the gap does the selling. This builds the HERO FRAME.
Choreography: a checkout banner of our own design SLIDES down: "You're $7 away from free shipping". A card "Hair Claw Clip · $12" SLIDES in and DROPS into the bag. The flip counter ROLLS from $38.00 to $50.00 like the gas pump, and the bar FILLS past the flag to $50 and BURSTS into money green: "You unlocked free shipping".
Sound: a card slide, a soft drop, the pump-style digit roll, a bright ding.

BEAT 5 · THE BALANCE · VO 6: "Set it so that extra item covers the shipping you're giving away."
Choreography: a brass balance scale DRAWS itself in ink. On the left pan, a chip "what the extra item earns you". On the right pan, a chip "the shipping you pay". The pans SETTLE level.
Sound: a small metal creak as the scale settles.

BEAT 6 · TOO HIGH, TOO LOW · VO 7: "Too high, and nobody reaches it. Too low, and you pay shipping on every order."
Choreography: split the frame top and bottom. Top, "too high": the flag jumps to $90 and small ink shopper dots run toward it, then give up halfway and drift back. Bottom, "too low": the flag drops to $15 and every order crosses it, each dropping a small coin labelled "shipping" off the bottom edge.
Sound: a deflating boop on top, a run of small coin drops on the bottom.

BEAT 7 · PRESCRIPTION · VO 8: "Save this, and look up your typical order tonight."
Use the prescription pad with: line1 "Find your typical order", line2 "Free shipping a little above it", line3 "Offer one small add-on".

END CARD · VO 9: "Next Friday: a new shop problem."
Use the Friday end card with next_topic "a new shop problem".

EXAMPLE NUMBERS (show exactly)
Typical order $38.00. Free shipping minimum $45.00. Gap $7.00. Add-on: Hair Claw Clip $12.00. New order $50.00.

MUST NOT
- Copy the checkout of Shopify, Etsy, Amazon or any real store. Build our own simple banner.
- Show anyone's face or a real gas station brand.
- Claim a percentage lift. We don't have a source.

DELIVER
Run check, fix every issue, then render final.mp4 at high quality. No music in the render.
```

**Caption**

```
Shop Doctor, episode 4: the round number.

Everyone loves hitting a round number, and your shoppers do too. That's why a free shipping minimum works.

Find your typical order, say $38, and set free shipping a little above it, like $45. The shopper at $38 sees "$7 away from free shipping" and adds one more thing. Set it so that extra item covers the shipping you give away.

Too high and nobody reaches it. Too low and you pay shipping on every order.

Example numbers. Save this, and look up your typical order tonight. New Shop Doctor every Friday.

#smallbusiness #smallbusinessowner #ecommercetips
```

**Pinned comment:** "Do you offer free shipping right now? Always, over a minimum, or never?"


# Sources

**Prices used in Reel 5** (starting prices checked September 2026; check them again before posting):

- Analytics, $49 a month: [Lifetimely on the Shopify App Store](https://apps.shopify.com/lifetimely-lifetime-value-and-profit-analytics)
- Inventory, $49 a month for stores under $100K a year: [Prediko pricing](https://www.prediko.io/pricing)
- Win-back email, $20 a month for 251 to 500 active profiles: [Klaviyo pricing, Email Tool Tester (updated August 2026)](https://www.emailtooltester.com/en/reviews/klaviyo/pricing/)
- Instagram planner, $18.75 a month billed yearly: [Later pricing](https://later.com/pricing/)

**Card fee used in Shop Doctor Ep 02:** 2.9% + 30¢ per domestic card payment: [Stripe pricing](https://stripe.com/pricing)

**How Hyperframes reads these prompts:** [Hyperframes on GitHub](https://github.com/heygen-com/hyperframes) · [HeyGen's Hyperframes overview](https://developers.heygen.com/hyperframes-overview)
