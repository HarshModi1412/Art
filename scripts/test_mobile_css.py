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
must("overflow-x: hidden" not in APP,
     "the app never sets overflow-x:hidden",
     "On <body> it promotes the element to a scroll container. Combined with "
     "height:100% that container is one viewport tall, so every page was "
     "clipped at the fold with dead grey below. Use `overflow-x: clip` on "
     "<html>, or fix the wide child instead.")

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
