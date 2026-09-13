#!/usr/bin/env python3
"""
Mobile layout regression guard.

WHY THIS EXISTS
---------------
Every defect asserted below was a real bug that shipped, and two of them were
introduced by a previous attempt to FIX mobile. They are cheap to reintroduce
and expensive to notice: nothing throws, no test fails, the app just quietly
becomes unusable on a phone — which is where most of these sellers are.

This is a static check on the stylesheets, not a browser test. It cannot prove
the layout is good. It can prove the specific mistakes that already cost a day
have not come back, which is what a regression guard is for.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def _rules(path: Path) -> str:
    """Stylesheet with comments stripped.

    The comments in these files explain the very bugs asserted below, so a
    naive substring search matches the explanation and reports a regression
    that is not there. Only actual declarations count."""
    return re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)


APP = _rules(ROOT / "Smart CafeX" / "smart.css")
STORE = _rules(ROOT / "Smart CafeX" / "storefront" / "store.css")

fails = []


def must(cond, msg, why=""):
    if cond:
        print("  ✓", msg)
    else:
        print("  ✗", msg, "\n      ", why)
        fails.append(msg)


print("\n== mobile layout regressions ==")

# ---------------------------------------------------------------- the clipper
# WHAT THIS RULE ACTUALLY IS, AND WHY IT WAS WRITTEN TOO WIDE.
#
# The bug was `html, body { overflow-x: hidden }`: on the document it promotes
# the element to a scroll container, and with the height:100% above it that
# container is exactly one viewport tall, so every page was clipped at the
# fold with dead grey below. It looked like the app had failed to load.
#
# The check used to forbid the string ANYWHERE in the stylesheet. That is not
# the rule. On a bounded box — a popup, a scrolling table — `overflow-x:
# hidden` is correct and deliberate, and the app relies on it: `.modal` uses it
# to guarantee a popup can never slide sideways whatever it is given.
#
# It passed for a long time only because the one occurrence in the file sat
# inside a comment that the stripper above removes. The first real declaration
# to appear made it fail, having proved nothing in between. So it now checks
# the thing it always meant: not on the document, and not on a full-page
# container. Anywhere else is the author's business.
_doc_clip = re.search(
    r"(?:^|[}\n])\s*(?:html|body|html\s*,\s*body|body\s*,\s*html|#view|\.main)"
    r"\s*\{[^}]*overflow-x:\s*hidden", APP, re.M)
must(_doc_clip is None,
     "overflow-x:hidden is never put on the document or a full-page container",
     "On <body> it makes the page one viewport tall and clips everything "
     "below the fold. Use `overflow-x: clip` there, or fix the wide child. "
     "On a popup or a table box it is fine and the app depends on it.")

must(not re.search(r"^html,\s*body\s*\{[^}]*[^-]height:\s*100%", APP, re.M),
     "the app document can grow past one viewport",
     "`height: 100%` on html/body pins the page to the viewport. Use min-height.")

must("overflow-x: hidden" not in STORE,
     "the storefront never sets overflow-x:hidden either",
     "It also silently breaks every position:sticky descendant, and the "
     "spotlight image is sticky.")

# ------------------------------------------------------------ the toast box
toast_base = STORE.find(".toast { bottom:")
toast_media = STORE.find("top: calc(env(safe-area-inset-top")
must(toast_base != -1 and toast_media != -1 and toast_base < toast_media,
     "the toast's desktop `bottom` is declared BEFORE the mobile override",
     "Declared after, `bottom` wins at equal specificity and the toast has "
     "both edges pinned — it became a 746px invisible overlay across the "
     "screen. Order is load-bearing here.")

must(re.search(r"@media[^{]*760px[^{]*\{[^@]*?\.toast\s*\{[^}]*bottom:\s*auto", STORE, re.S),
     "and the mobile rule explicitly releases `bottom`")

# ------------------------------------------------------------- touch targets
must("min-height: 40px" in APP or "min-height: 44px" in APP,
     "the app sets a minimum touch height")
must("min-height: 44px" in STORE,
     "the storefront sets a minimum touch height",
     "Measured at 20-23px before this. Apple asks 44pt, Android 48dp.")

# -------------------------------------------------------------- the iOS zoom
for name, css in (("app", APP), ("storefront", STORE)):
    must(re.search(r"input,\s*select,\s*textarea\s*\{[^}]*font-size:\s*16px", css),
         f"the {name} keeps form inputs at 16px on phones",
         "iOS zooms the whole page when a focused input is under 16px and "
         "never zooms back. It reads as the layout breaking.")

# ------------------------------------------------------------ readable type
must("font-size: 11.5px !important" in APP,
     "nothing readable is left below 11px on a phone",
     "Chips and helper text measured 9.5-10.5px, unreadable outdoors.")

# ------------------------------------------------- the five-column step rail
must(re.search(r"\.wz-rail\s*\{\s*grid-template-columns:\s*repeat\(2", APP),
     "the builder's step rail drops to 2 columns on a phone",
     "repeat(5,1fr) gave each chip 78px for 114px of content, so the active "
     "step pushed past the viewport and the row looked broken.")

# --------------------------------------------------------- the preview frame
must(re.search(r"\.prev-stage[^{]*\{[^}]*height:\s*52vh", APP),
     "the desktop preview canvas is capped on a phone",
     "It was a tall empty box below the fold.")

print()
if fails:
    print(f"{len(fails)} MOBILE REGRESSION(S)")
    sys.exit(1)
print("MOBILE LAYOUT CHECKS PASSED ✓")
