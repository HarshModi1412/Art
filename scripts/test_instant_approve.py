#!/usr/bin/env python3
"""
One tap, and the tap is the whole wait.

WHY THIS FILE EXISTS
--------------------
Three reports, one root cause and one real bug.

  "One tap approval is the main thing but it is taking a lot and a lot of
   time."  It was: the tap opened a blocking overlay and held the seller there
  for the entire server round trip — which for a photo post means an AI drawing
  a picture on half a CPU — then refetched the whole app state, then refetched
  the social plan, then repainted. The seller had already made the only
  decision that needed them.

  "If I approve a reel and then go to Social Media Manager and change things
   and save, it is not scheduling."  It was not. The editor asked "is this an
  approved reel?" before "does it have its media?", so an approved reel whose
  clip was already uploaded was never offered Save & schedule, and plain Save
  only patched fields. The post stayed in the approved state forever, and
  nothing publishes from there — the publisher selects on scheduled. The post
  silently never went out.

  "When uploading video or image show the progress bar."  fetch() cannot report
  upload progress at all, so there was nothing to show it with.

Measured, in a headless browser, with the approve call held for six seconds:
the card leaves in 0.22s. That is the number these assertions protect.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_RAW = (ROOT / "Smart CafeX" / "smart.js").read_text(encoding="utf-8")
CSS_RAW = (ROOT / "Smart CafeX" / "smart.css").read_text(encoding="utf-8")


def strip(text: str, js: bool = False) -> str:
    out = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    if js:
        out = re.sub(r"^\s*//.*$", "", out, flags=re.M)
        out = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    return out


JS = strip(JS_RAW, js=True)
CSS = strip(CSS_RAW)

passed = 0
fails = []


def ok(cond, msg, why=""):
    global passed
    if cond:
        passed += 1
        print("  ✓", msg)
    else:
        print("  ✗", msg)
        if why:
            print("      ", why)
        fails.append(msg)


def body(js: str, name: str) -> str:
    """The source of one function, by brace matching."""
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", js)
    if not m:
        return ""
    i = m.end() - 1
    depth, j = 0, i
    while j < len(js):
        if js[j] == "{":
            depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0:
                return js[i:j + 1]
        j += 1
    return ""


# =====================================================================
print("\nThe card leaves on the tap, not on the answer")
# =====================================================================

ok("function runInBackground" in JS, "there is one queue every decision goes through")

rb = body(JS, "runInBackground")
ok("animateCardOut(id)" in rb,
   "the card starts leaving before the request is made",
   "The seller's confirmation is the card going, not a spinner ending.")
ok(".filter((x) => x.id !== id)" in rb,
   "and the app's own list forgets it at the same moment")
ok(rb.index("animateCardOut") < rb.index("_jobs.push"),
   "the animation is ordered before the job is queued, not after")

ok(not re.search(r"withBusy\(\s*$|withBusy\(", body(JS, "approvePostReady")),
   "approving a post no longer opens a blocking overlay",
   "withBusy() held the seller in front of a modal for the whole round trip, "
   "including the AI drawing the picture.")
ok("runInBackground(id," in body(JS, "approvePostReady"),
   "it goes through the queue instead")

aw = body(JS, "approveWeek")
ok("withBusy" not in aw and "busyStep" not in aw,
   "approving a whole week does not block either",
   "This was the longest wait in the app: an overlay counting 'Post 4 of 7' "
   "while each picture was drawn in turn.")
ok('runInBackground("post_" + pid, {' in aw,
   "every post in the week becomes its own job",
   "So one that fails comes back as its own card saying why, instead of being "
   "summed into '2 could not be approved' with no way to tell which two.")

ok("const QUEUE_LANES = 2" in JS,
   "two jobs run at once, not nine",
   "Nine concurrent writes at a small dyno lose some of them, and they all "
   "mutate the same server-side insight list.")


# =====================================================================
print("\nAnd if the work fails, the card comes back and says so")
# =====================================================================

ok("function noteFailure" in JS and "function loadFailures" in JS,
   "a failure is recorded against the card it belongs to")
ok('localStorage.setItem(FAIL_KEY' in JS,
   "and survives a reload",
   "The failure outlives the page that saw it. A toast does not.")
ok("FAIL_TTL_DAYS" in JS,
   "but not forever")

pq = body(JS, "pumpQueue")
ok("noteFailure(job.id" in pq, "the reason is kept, not just the fact")
ok("[job.card, ...ins]" in pq,
   "the card is put back at the top of the list",
   "A thing the seller believes is done, and is not, outranks a thing they "
   "have not looked at yet.")
ok("clearFailure(job.id)" in pq,
   "and a later success clears the mark")

ok('class="ins-failed' in JS and "did not go through" in JS,
   "the returned card wears what went wrong, on the card")
ok("function ago(" in JS and "ago(f.at)" in JS,
   "and when it happened, in words a person uses",
   '"4 minutes ago" beats a timestamp on a card someone is scanning.')
ok('"Try again"' in JS,
   "its button stops pretending this is the first attempt")
ok(re.search(r"rank\s*=\s*\(i\)\s*=>\s*\(i\.summary\s*\?\s*0\s*:\s*_failed\[i\.id\]\s*\?\s*1", JS),
   "failed cards sort above undecided ones")

ok("function withoutInFlight" in JS,
   "work in flight is held out of every repaint",
   "The server still reports a pending insight for a job that has not reached "
   "it yet. Painting that list verbatim puts the card back a second after the "
   "seller watched it leave — and a resurrected card gets approved twice.")
ok("insights = withoutInFlight(insights);" in body(JS, "renderApprovals"),
   "filtered at the one choke point, not at eleven call sites")

ok("function settleAfterQueue" in JS and "_settleTimer" in JS,
   "one refresh after the queue drains, not one per job",
   "Approving six posts meant six full state refetches racing each other, "
   "each repainting the list under the seller's thumb.")


# =====================================================================
print("\nThe reel that would never go out")
# =====================================================================

ed = body(JS, "openSocialEditor")
# Scoped to the button block itself: `mediaMissing()` also appears further
# down inside saveEditor, and matching that instead made this assertion
# compare two positions in unrelated code and pass or fail by accident.
acts = ed[ed.find('modal-actions'):ed.find('modal-actions') + 900]
ready_first = acts.find('post.state === "approved" && !needsMedia')
reel_first = acts.find('post.state === "approved" && isReel')
ok(ready_first != -1 and reel_first != -1 and ready_first < reel_first,
   "a post that HAS its media is offered Save & schedule, whatever shape it is",
   "The test used to be 'is it an approved reel?' first, so a reel whose clip "
   "was already uploaded was only ever offered 'Open the video task'. It could "
   "not be scheduled from the screen the seller was looking at.")

ok("function saveEditor" in JS or "async function saveEditor" in JS,
   "Save and Save & schedule are one path")
se = body(JS, "saveEditor")
ok("collectPatch()" in se,
   "so Save & schedule stops throwing away the caption",
   "It used to send only post_id and scheduled_at. A seller who rewrote the "
   "hook and pressed the green button watched the edit vanish.")
ok('schedule === "if-ready"' in se and "mediaMissing()" in se,
   "and plain Save finishes the job when the post is ready to go",
   "There is no case where a seller edits an approved, media-complete post and "
   "means 'and do not put it in the calendar'.")
ok("still needs a clip before it can go out" in JS,
   "where it cannot schedule, it says why instead of succeeding silently")

ok("const mediaMissing = () =>" in JS_RAW,
   "whether media is missing is asked, not captured once",
   "As a const read at render time it was wrong the moment the seller uploaded "
   "the clip without closing the popup — the most ordinary path there is.")
ok("function syncEditorActions" in JS,
   "and the buttons change the moment a clip lands")
ok("syncEditorActions();" in body(JS, "openSocialEditor"),
   "called from the upload handler, not left for the next open")

ok("function toastAction" in JS and "toastAction(" in body(JS, "approvePostReady"),
   "approving a reel offers the steps instead of ambushing with them",
   "It used to throw the step-by-step popup open over whatever the seller was "
   "doing — fine for one reel, an ambush when working down a list of six.")


# =====================================================================
print("\nAn upload bar that is telling the truth")
# =====================================================================

ok("function apiUpload" in JS and "xhr.upload.onprogress" in JS,
   "uploads report real bytes sent",
   "fetch() cannot report upload progress at all, which is why there was "
   "nothing to show. XMLHttpRequest still can.")
ok("function progressBar" in JS,
   "there is one bar component, not one per call site")
pb = body(JS, "progressBar")
ok("working(text)" in pb,
   "100% is not reported as finished",
   "The bytes are gone but the server is still working — cleaning a watermark "
   "off a clip takes real seconds. A bar parked at 100% reads as hung.")
ok("fail(text)" in pb, "and a failed upload says so where it was going")

ok("apiUpload(\"/api/site/image\", fd, (frac) => bar.set(frac))" in JS
   or "apiUpload('/api/site/image', fd," in JS,
   "the clip upload in the post editor uses it")
ok(JS.count("apiUpload(") >= 4,
   "so do the video task, the re-shoot popup and every picture",
   "One bar in one place would have left the other three silent.")
ok("progressBar($(\"smVidBlock\")" in JS,
   "the bar sits in the clip slot, not behind a modal",
   "The place the file is going is the thing the seller wants to look at "
   "while it goes.")
ok('Uploading ${Math.round(f.size / 1048576)}MB clip' in JS_RAW,
   "and says how big the thing it is sending is")
ok(".up-prog.indet .up-prog-track::after" in CSS,
   "the indeterminate state cannot be mistaken for a measurement")


# =====================================================================
print("\nThe first hundred milliseconds")
# =====================================================================

ok(re.search(r"\.btn:active\s*\{[^}]*transform:\s*scale", CSS),
   "a button answers the finger on the press",
   "Not when the work finishes, not when the network answers. Below ~100ms a "
   "response is experienced as instantaneous; above it, as the app deciding "
   "whether to bother. Most of 'this feels slow' is a control that sat there "
   "looking dead while the work happened.")
ok(re.search(r"\.btn:active\s*\{\s*transition-duration:\s*\.0[0-9]s", CSS),
   "and answers faster than it relaxes",
   "60ms in, 150ms out: it moves under the finger, and does not flicker on "
   "release.")
ok(".app-tile:active" in CSS and ".today-row:active" in CSS,
   "rows and tiles are buttons too, and were the ones that felt dead")
ok("-webkit-tap-highlight-color: transparent" in CSS,
   "Safari's own grey box is turned off",
   "It arrives ~300ms after the touch, on top of the app's own feedback, late "
   "enough to read as lag.")
ok(re.search(r"touch-action:\s*pan-y", CSS),
   "a scrolling finger is never mistaken for a press",
   "Without it a swipe starting on a tile leaves it looking pressed all the "
   "way down the page.")
ok(CSS.count("prefers-reduced-motion") >= 6,
   "and every one of these animations can be turned off")

ok(".ins-card.ins-leaving" in CSS and "@keyframes ins-out" in CSS,
   "the card's exit is animated, not a jump")
ok("max-height: 0" in CSS and "margin-bottom: 0" in CSS,
   "and it collapses its own height so the cards below rise, not jump")
ok(".work-strip" in CSS and "pointer-events: none" in CSS,
   "background work sits at the edge and blocks nothing",
   "iOS does not put a modal over the thing you were doing to tell you it is "
   "busy on your behalf.")


# =====================================================================
print("\nThe eight ways an optimistic queue lies to you")
# =====================================================================
# Every one of these was found by reviewing the queue adversarially after it
# worked, and every one is a way for the seller to end up believing something
# that is not true. They are the expensive half of this feature.

aw2 = body(JS, "approveWeek")
ok(aw2.index("const cards = ids.map") < aw2.index("animateCardOut"),
   "a week reads its cards BEFORE it removes them",
   "It used to filter the whole week out of the list and then look each post "
   "up to see if it was a reel — by which point the lookup could only return "
   "undefined. Every job carried a null card, so the failure path had nothing "
   "to put back. Approving a week on patchy 4G gave the seller seven toasts "
   "saying the posts were 'back in your approvals' over an empty panel. "
   "Measured after the fix: 2 of 2 restored.")
ok("card: cards[n]" in aw2
   and "const keep = card ||" in body(JS, "runInBackground"),
   "and hands each job the card it belongs to",
   "approveWeek has to read the cards up front because it removes the whole "
   "week before queueing any of them, so runInBackground must accept one "
   "rather than always looking it up itself.")

ok("if (_jobs.some((j) => j.id === id)) return;" in body(JS, "runInBackground"),
   "the same card can never be queued twice",
   "The bulk bar holds the list as it was when the panel last painted, and "
   "approving one card does not repaint it — so 'Approve all 9' could re-send "
   "a post approved a moment earlier. Two lanes makes those genuinely "
   "concurrent: two AI pictures billed, or one supplier emailed the same "
   "order twice. None of these endpoints is idempotent.")
ok("function syncBulkBar" in JS,
   "and the bar counts what is actually left")
ok('document.querySelector(".ap-bulk")' in body(JS, "renderApprovals"),
   "with both bulk buttons going together",
   "'Dismiss all' stayed live over an emptied list, still wired to the nine "
   "insights captured when the bar was drawn — and for posts its branch sends "
   "cancel with no confirmation. A mis-tap cancelled the nine posts the "
   "seller had approved four seconds earlier.")

ok("let _stateGen = 0;" in JS and "if (gen !== _stateGen) return;" in JS,
   "a stale read of the app state cannot overwrite a fresher one",
   "Two reads overlap routinely while the queue is busy. The slow one, "
   "holding the list from before the tap, landed last and painted an "
   "approved card back as undecided with nothing to explain it. The seller "
   "taps it again and pays for a second picture.")

ok("function prunePhantomFailures" in JS,
   "a failure record cannot outlive the card it belongs to")
ok("const FAIL_TTL_DAYS = 3;" in JS,
   "and expires before a weekly insight can reuse its id",
   '"winback" is a fixed string and a weekly plan can rehash a post to the '
   "same id, so pruning alone cannot catch it — the id is live both times. "
   "Fourteen days let a failure from one win-back list sit at the top of the "
   "panel wearing a reason from work never attempted on the new one.")
ok('clearFailure("post_" + id)' in body(JS, "decidePost"),
   "and cancelling a failed post resolves its failure")

ok("e.status === 0" in body(JS, "pumpQueue") and "cannot tell" in JS,
   "a dropped connection is not reported as a definite failure",
   "status 0 is the connection dropping, and that can happen AFTER the "
   "request landed — the purchase order is already in the supplier's inbox "
   "and only the reply was lost. 'This did not go through' plus 'Try again' "
   "is how a supplier receives the same order twice.")
ok('"Check, then try again"' in JS and ".ins-failed.unsure" in CSS,
   "and it asks the seller to check rather than to retry")

ok('data-post="${post.id}"' in JS_RAW and 'opts.owner' in JS,
   "slow work checks it is writing into its own popup",
   "Drawing takes half a minute and sellers do not watch it — they close the "
   "popup and open the next post. Asking for '.modal-actions' finds whichever "
   "popup is open NOW; thirty-one elements carry that class. Post A's picture "
   "was painted into post B's frame, with a Save & schedule closed over A "
   "that scheduled A at B's time.")
ok(JS.count('.modal[data-post="${post.id}"]') >= 3,
   "on the picture, the clip and the buttons alike")

ok("const offerSchedule = () => syncEditorActions" in JS,
   "there is ONE function that builds the Save & schedule button",
   "There were two, with the same id, label and colour, and the one the "
   "picture paths used sent no caption patch. A seller who rewrote their "
   "caption and then pressed 'Invent a picture' got a green button that "
   "silently discarded the rewrite — the exact bug the note on the other path "
   "says was fixed.")
_gen = JS.rfind('$("smVidGen")')
ok(_gen != -1 and "syncEditorActions();" in JS[_gen:_gen + 3500],
   "and the paid clip generator refreshes them too",
   "The upload path did and the paid path did not, so a seller who PAID for a "
   "clip watched it appear and was still told 'This reel has no clip yet'.")

ok('window.addEventListener("beforeunload"' in JS,
   "closing the tab mid-work asks first",
   "'Carry on, they finish by themselves' is true of moving around the app — "
   "the panel lives outside the view modules repaint — but not of closing the "
   "tab. The work is driven from here and a request not yet sent dies with "
   "the page, silently, with no failure record because the catch never runs.")


print()
if fails:
    print(f"{passed} passed, {len(fails)} FAILED")
    for f in fails:
        print("   -", f)
    sys.exit(1)
print(f"{passed} passed, 0 failed")
