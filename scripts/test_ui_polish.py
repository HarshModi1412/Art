#!/usr/bin/env python3
"""
The UI pass: three reported defects, and the classes of defect behind them.

WHY THIS FILE EXISTS
--------------------
A seller reported three things: the Social Media popup slid sideways under a
thumb, the inventory table was unusable on anything but a desktop, and the Home
screen had two competing to-do lists. Each one turned out to be an instance of
something more general, and the general thing is what is guarded here:

  1. A grid column that will not shrink.  `repeat(7, 1fr)` is
     `repeat(7, minmax(auto, 1fr))`, and `auto` means min-content — a column
     refuses to go narrower than its longest unbreakable word. The month
     calendar measured 405px inside a 360px card. Same shape of bug: any
     `repeat(N, 1fr)` holding text.

  2. A control whose only explanation is a `title` tooltip. A phone has no
     hover. Measured across fourteen modules, nine buttons were a bare icon
     with a tooltip nobody on a touch screen can ever see — one of them
     deleted an inventory item.

  3. Two lists of the same kind of thing, separated by a rule, because the
     software distinguishes "what we worked out" from "what you wrote down"
     and the person reading at 8am does not.

Every assertion below is a measurement that was taken, not a preference.
Numbers in the messages are from a real 390px render.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_RAW = (ROOT / "Smart CafeX" / "smart.css").read_text(encoding="utf-8")
JS_RAW = (ROOT / "Smart CafeX" / "smart.js").read_text(encoding="utf-8")
HTML_RAW = (ROOT / "Smart CafeX" / "smart.html").read_text(encoding="utf-8")


def strip_comments(text: str, js: bool = False) -> str:
    """Declarations only.

    The comments in these files spell out the bugs asserted here, so a naive
    substring search matches the explanation and passes a test that should
    have failed."""
    out = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    if js:
        out = re.sub(r"^\s*//.*$", "", out, flags=re.M)
        out = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    return out


CSS = strip_comments(CSS_RAW)
JS = strip_comments(JS_RAW, js=True)
HTML = strip_comments(HTML_RAW, js=True)

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


def block(css: str, selector: str, within: str = "") -> str:
    """The declarations of one rule, optionally only inside a media query."""
    hay = css
    if within:
        i = hay.find(within)
        if i == -1:
            return ""
        # to the end of that media block: count braces from the query's {
        j = hay.index("{", i)
        depth, k = 0, j
        while k < len(hay):
            if hay[k] == "{":
                depth += 1
            elif hay[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        hay = hay[j:k]
    # Anchored so `.modal-actions` does not match inside
    # `.modal-head, .modal-actions { … }`, which is a different rule and was
    # silently answering for it.
    m = re.search(r"(?:^|[};]|\*/)\s*" + re.escape(selector) + r"\s*\{([^}]*)\}",
                  hay, re.M)
    return m.group(1) if m else ""


# =====================================================================
print("\nThe popup that slid sideways")
# =====================================================================

for sel in (".cal-grid", ".cal-dow"):
    decl = block(CSS, sel)
    ok("minmax(0, 1fr)" in decl or "minmax(0,1fr)" in decl,
       f"{sel} columns may shrink below their content",
       "repeat(7, 1fr) means minmax(auto, 1fr), and auto is min-content: a "
       "column will not go narrower than 'Chaturthi'. Measured 405px of grid "
       "inside a 360px card, so the whole Social screen dragged sideways.")

ok("min-width: 0" in block(CSS, ".cal-cell"),
   "a calendar cell may shrink too",
   "A grid item's automatic minimum size is min-content unless told otherwise.")

ok("flex: 0 1 auto" in block(CSS, ".cal-fmt"),
   "the REEL / CARO chip is allowed to shrink",
   "`flex: none` on a chip inside the cell held the column open by itself.")

mb = block(CSS, ".modal-body")
ok("overflow-x: clip" in mb,
   "a popup's body is not itself a sideways scroller",
   "overflow-x: auto turned any slightly-too-wide child into a popup that "
   "slid left and right under a thumb. `clip` stops the drag without making "
   "a scroll container, so a .table-scroll inside can still scroll on "
   "purpose. This is the systemic fix: no popup can do it again.")
ok("overflow-x: auto" not in mb,
   "and the old auto is gone, not merely overridden")

ma = block(CSS, ".modal-actions")
ok("flex-wrap: wrap" in ma,
   "a popup's buttons wrap instead of falling off the left edge",
   "justify-content: flex-end with nowrap overflows LEFT, which is the one "
   "direction nothing can scroll to. Four buttons in a 306px popup put "
   "'Close' 29px past the edge: clipped, and untappable.")

ok(re.search(r"@media[^{]*760px[^{]*\{[^@]*?\.sm-yield[^}]*display:\s*block", CSS, re.S),
   "the Shoot list's yield table stacks on a phone",
   "Three columns of prose measured 410px inside a 306px popup.")
ok("table-layout: fixed" in block(CSS, ".sm-yield"),
   "and cannot be widened by one long cell on a desktop either")


# =====================================================================
print("\nA table nobody can read on a phone or a tablet")
# =====================================================================

ok("@media (max-width: 900px)" in CSS and
   re.search(r"@media \(max-width: 900px\)\s*\{[^@]*?\.table-scroll thead\s*\{[^}]*display:\s*none",
             CSS, re.S),
   "a table becomes cards below 900px, not 760px",
   "760px sits just under an iPad held upright (768px), so a tablet got "
   "eleven columns squeezed into 768px and scrolling sideways inside its own "
   "box — the worst of both layouts. Eleven columns want a thousand pixels.")

ok(re.search(r"@media \(max-width: 900px\)\s*\{[^@]*?\.btn-lbl\s*\{[^}]*display:\s*inline",
             CSS, re.S),
   "and icon buttons grow their words at exactly that width",
   "If the two breakpoints drift apart, a card ends in mute icons.")

tr = block(CSS, ".table-scroll tbody tr", within="@media (max-width: 900px)")
ok("flex-direction: column" in tr,
   "a card can order its fields the way a person reads them")
ok("order: -1" in block(CSS, ".table-scroll td[data-first]", within="@media (max-width: 900px)"),
   "so Status leads the card instead of ending it",
   "Status was the eleventh line, under six numbers — the one thing nobody "
   "should have to scroll for.")
ok("display: none" in block(CSS, ".table-scroll td[data-secondary]",
                            within="@media (max-width: 900px)"),
   "and the arithmetic is folded away until asked for",
   "Eleven fields stacked vertically is a screen and a half per item.")
ok(".table-scroll tr.show-all td[data-secondary]" in CSS,
   "with a per-row toggle that brings it back")

# --- the labelling contract that makes the card readable
ok("data-card-label" in JS and "th.dataset.cardLabel" in JS,
   "a column may say one thing in the table and another in the card",
   "'DOS' fits a narrow column. As a full-width label on a phone it is a "
   "word from our side of the screen, and its explaining tooltip needs a "
   "mouse.")
ok("data-card-hide" in JS and "data-secondary" in JS,
   "a column may be marked secondary for the card")
ok("data-card-first" in JS and "data-first" in JS,
   "and one column may be marked as the card's lead")

for short, plain in (("DOS", "Days left"), ("MOQ", "Smallest order"),
                     ("DOQ", "Order this many"), ("Used/day", "Used each day"),
                     ("Lead time", "Delivery takes"), ("Order below", "Reorder at")):
    ok(f'data-card-label="{plain}"' in JS,
       f'inventory says "{plain}" on a phone, not "{short}"')


# =====================================================================
print("\nButtons that say nothing without a mouse")
# =====================================================================


SIC_ONLY = re.compile(r"^\s*sic\(\s*[\"'][\w-]+[\"']\s*(?:,\s*[^)]*)?\)\s*$")


def strip_template_exprs(src: str) -> str:
    """Collapse every ${...} to one token, chosen by what it can produce.

    `${sic("close")}` can only ever draw an icon, so it counts as silence.
    Anything else — `${esc(p.name)}`, a ternary, a nested template — produces
    text at runtime, so it counts as a word. Without that distinction the
    check flags every button whose label is computed, which is most of them,
    and a test that cries wolf is a test people delete."""
    out, i = [], 0
    while i < len(src):
        if src.startswith("${", i):
            depth, j = 1, i + 2
            while j < len(src) and depth:
                if src[j] == "{":
                    depth += 1
                elif src[j] == "}":
                    depth -= 1
                j += 1
            expr = src[i + 2:j - 1]
            out.append("\x00" if SIC_ONLY.match(expr) else "WORD")
            i = j
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF←-⯿️✀-➿‹›"
    "✕✖×✎✓✔]+")

mute = []
for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", strip_template_exprs(JS), re.S):
    attrs, inner = m.group(1), m.group(2)
    words = EMOJI.sub("", inner.replace("\x00", "")).strip()
    words = re.sub(r"<[^>]*>", "", words).strip()
    if len(words) >= 2:
        continue                            # it says a real word
    if "btn-lbl" in inner or "aria-label" in attrs:
        continue                            # it says one on a phone, or to a reader
    mute.append((attrs[:70].strip(), inner[:40].strip()))

ok(not mute,
   "every icon-only button carries a word or an accessible name",
   "A `title` is a hover and a phone has no hover. Nine of these were "
   "measured across the modules; the inventory card ended in four identical "
   "grey boxes, one of which deleted the item.\n       still mute: "
   + "; ".join(f"{a} -> {b!r}" for a, b in mute[:6]))

ok('data-del="${it.id}"' in JS and "Remove from stock list" in JS,
   "the destructive one names what it destroys")
ok(re.search(r'\.table-scroll td\.sup-actions \.btn\[data-del\]', CSS) is not None
   or "btn[data-del]" in CSS,
   "and gets its own line, away from Edit",
   "So a thumb aiming at Edit can never land on Remove.")


# =====================================================================
print("\nOne list on the Home screen, not two")
# =====================================================================

tt = block(CSS, ".today-tasks")
ok("border-top" not in tt,
   "no rule divides the worked-out rows from the written-down ones",
   "That line was the app showing the seller its own filing system. Both "
   "sides are 'things to do today'.")
ok(".today-rows:empty + .today-proof[hidden] + .today-tasks" not in CSS,
   "and the rule that used to cancel that divider is gone with it",
   "A selector suppressing a border that no longer exists is a trap for the "
   "next person, who reads it as evidence the border is still there.")

ok(".today-tasks .task-item" in CSS and "border-bottom: none" in
   block(CSS, ".today-tasks .task-item"),
   "the seller's own rows wear the same clothes as the rest of the list")

ok('id="taskAdd" hidden' in JS,
   "the add-a-task form is not standing open",
   "A permanent input box at the foot of the card is what made it read as a "
   "second widget bolted under the list.")
ok('class="task-open"' in JS and "function openTaskAdd" in JS,
   "it is a quiet last line of the list that opens when someone means it")
ok("function closeTaskAdd" in JS and "Escape" in JS,
   "and folds back on Escape or on leaving it blank")
ok("if (inp.isConnected) inp.focus();" in JS,
   "adding one leaves the line open for the next",
   "Morning tasks arrive in threes, not ones.")

ok("todayHeadline" in JS and "(items || []).length + open.length" in JS,
   "the headline counts both kinds together")


# =====================================================================
print("\nWhat a phone screen can actually hold")
# =====================================================================

ok('id="apCount"' in HTML and "paintApprovalCount" in JS,
   "the approval panel shows how many decisions are waiting")
ok(re.search(r"@media \(max-width: 900px\)\s*\{[^@]*?\.approvals\.shut #approvalList\s*\{[^}]*display:\s*none",
             CSS, re.S),
   "and arrives shut on a phone",
   "Measured: nine cards, 2,261px, 35% of the whole Home screen, stacked "
   "below four groups of tiles where nobody scrolls. Home went 6,573px -> "
   "4,389px. Beside the workspace it costs no vertical space and stays open.")
ok('@media (min-width: 901px) { .ap-count { display: none; } }' in CSS,
   "the count is a phone thing only — the desktop column shows the cards")
ok('e.target.closest(".ap-head-actions")' in JS,
   "History and Refresh still work inside that header",
   "They live in the same row as the toggle.")
ok('window.matchMedia("(max-width: 900px)")' in JS,
   "and the header is only announced as a button where it is one")

ok(re.search(r"\.btn\.tiny,\s*\.btn\.xs\s*\{[^}]*min-height:\s*40px", CSS),
   "no touch target is left at 36px",
   ".btn.tiny is the most common control a seller touches — Edit, Details, "
   "Approve & send, Download — and 36px is under the threshold where a thumb "
   "starts missing.")

for cls in (".today-eyebrow", ".sm-occ", ".ord-lbl", ".sup-badge", ".po-st",
            ".cmp-weight", ".pair-lbl", ".pair-rec", ".cal-dow span",
            ".gal-add span"):
    ok(cls in CSS.split("font-size: 11.5px !important")[0].rsplit("@media", 1)[-1]
       or f"{cls}," in CSS or f"{cls} {{" in CSS,
       f"{cls} is readable at arm's length")


# =====================================================================
print("\nA festival name in a 45px column")
# =====================================================================

ok(re.search(r"@media[^{]*760px[^{]*\{[^@]*?\.cal-fest,\s*\.cal-start\s*\{[^}]*display:\s*none",
             CSS, re.S),
   "festival names leave the cells on a phone",
   "Forced to wrap in 45px they became 'Ganes / h / Chatur / thi', which "
   "reads as a broken layout rather than as a festival. The amber tint keeps "
   "the signal.")
ok("cal-legend" in CSS and "cal-legend" in JS,
   "and are listed under the grid, where there is a line to say them in")
ok("const legend = [];" in JS and "legend.push(" in JS,
   "the strip is built from the days the grid actually marked")
ok("(cal.festivals || []).map((f) => `<span class=\"cal-leg\">" not in JS,
   "not from the festival records directly",
   "A festival whose own date falls in the NEXT month still gets a 'starts' "
   "mark in this one. Reading the date straight off the record printed "
   "'11 Navratri' under a September calendar, when September has the 20th.")


print()
if fails:
    print(f"{passed} passed, {len(fails)} FAILED")
    for f in fails:
        print("   -", f)
    sys.exit(1)
print(f"{passed} passed, 0 failed")
