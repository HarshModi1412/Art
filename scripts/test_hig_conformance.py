#!/usr/bin/env python3
"""Apple HIG conformance guard for the Smart app shell.

WHY THIS EXISTS
---------------
docs/apple-design-rules.md is the Human Interface Guidelines read page by page
and turned into numbered rules. Most of it is about native Apple apps and does
not transfer to a browser: Liquid Glass is a material the system draws, SF
Symbols are licensed for Apple platforms only, and an app icon has no web
equivalent. What does transfer is everything measurable, and every one of the
defects asserted below was live in this app before this file existed:

  * --border-strong was #d0d3da, which is 1.50:1 against white. In light mode
    you could not see where a text field ended. The dark theme had already been
    rebuilt to clear 3:1 and light was simply never brought with it.
  * --muted was 4.12:1 on --surface-2, i.e. under AA, and --muted is every
    hint, timestamp and helper line in the app: exactly the text a seller who
    has never used it before has to read.
  * 43 font-size declarations were under 11pt, five of them between 8.5 and
    9.5px. Apple's floor is 11pt on iOS and 10pt on macOS.
  * Every font size was in px, so a seller who had turned their browser text
    size up got nothing. That is the one accessibility setting the app silently
    dropped, and rem is the web's Dynamic Type.
  * Tap targets stopped at 40px on touch where Apple asks 44, and on a pointer
    there was no minimum at all: .btn.xs computed to 24px against a 28pt
    default.
  * There was no safe-area handling and no viewport-fit=cover, so the app was
    letterboxed on a notched phone.
  * None of the seven popups were dialogs. No role, no announcement, focus left
    behind on open and lost on close, Tab walking out of the popup into the
    page underneath, and Escape throwing away typed work with no warning.

Two halves. The static half reads the stylesheet and markup and runs anywhere.
The rendered half opens the real shell in Chromium and measures what is
actually painted, because reading a stylesheet tells you what it says, not
what wins. It skips loudly if playwright is missing rather than passing
silently.

Run: python3 scripts/test_hig_conformance.py
"""
import json
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "Smart CafeX"
CSS_PATH = APP / "smart.css"
HTML_PATH = APP / "smart.html"
JS_PATH = APP / "smart.js"

CSS_RAW = CSS_PATH.read_text(encoding="utf-8")
HTML = HTML_PATH.read_text(encoding="utf-8")
JS = JS_PATH.read_text(encoding="utf-8")

# The comments in these files describe the very bugs asserted here, so a naive
# substring search matches the explanation and reports a regression that is not
# there. Only real declarations count.
CSS = re.sub(r"/\*.*?\*/", "", CSS_RAW, flags=re.S)

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}\n      {extra}")


# ---------------------------------------------------------------- colour maths
def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _rl(rgb):
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = _rl(a), _rl(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def parse_colour(value):
    """#rrggbb or rgba(); returns (rgb, alpha) or None."""
    value = value.strip()
    m = re.match(r"#([0-9a-fA-F]{6})", value)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), 1.0
    m = re.match(r"rgba?\(([^)]+)\)", value)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        return (tuple(int(float(p)) for p in parts[:3]),
                float(parts[3]) if len(parts) > 3 else 1.0)
    return None


def over(fg, bg_rgb):
    (r, g, b), a = fg
    return tuple(round(a * c + (1 - a) * d) for c, d in zip((r, g, b), bg_rgb))


def tokens(selector):
    for m in re.finditer(re.escape(selector) + r"\s*\{([^{}]*)\}", CSS):
        found = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)))
        if len(found) > 20:
            return {k: v.strip() for k, v in found.items()}
    raise AssertionError(f"no token block found for {selector}")


LIGHT = tokens(":root")
DARK = tokens('[data-theme="dark"]')

# Every ground a piece of text can land on. The worst one is the one that
# decides, which is the mistake the original palette made: --muted cleared AA
# on white and was checked on white, and then got used on --surface-2.
GROUNDS = ("bg", "surface", "surface-2", "surface-3", "surface-4")
TEXT_TOKENS = ("text", "text-2", "muted", "primary", "green", "amber", "red", "blue")

print("\n== colour, computed rather than asserted (A11Y-5, DRK-8) ==")
for theme_name, theme in (("light", LIGHT), ("dark", DARK)):
    def colour(name, _theme=theme):
        raw = _theme.get("--" + name) or LIGHT.get("--" + name)
        return parse_colour(raw)

    worst = []
    for ground in GROUNDS:
        bg = colour(ground)
        if not bg:
            continue
        for tok in TEXT_TOKENS:
            fg = colour(tok)
            if not fg:
                continue
            r = ratio(over(fg, bg[0]), bg[0])
            if r < 4.5:
                worst.append(f"--{tok} on --{ground} = {r:.2f}:1")
    check(f"every {theme_name}-theme text colour clears AA on every ground it lands on",
          not worst,
          "; ".join(worst))

    # WCAG 2.2 SC 1.4.11: the boundary that identifies a control needs 3:1.
    bad_border = []
    for ground in ("surface", "surface-2", "bg"):
        bg = colour(ground)
        r = ratio(over(colour("border-strong"), bg[0]), bg[0])
        if r < 3.0:
            bad_border.append(f"on --{ground} = {r:.2f}:1")
    check(f"{theme_name} input and button borders are visible (3:1, SC 1.4.11)",
          not bad_border, "; ".join(bad_border))

    fill, on_fill = colour("primary-fill"), colour("on-primary")
    r = ratio(over(on_fill, fill[0]), fill[0])
    check(f"{theme_name} button label on the accent fill clears AA ({r:.2f}:1)", r >= 4.5)

    focus, bg = colour("focus"), colour("bg")
    r = ratio(over(focus, bg[0]), bg[0])
    check(f"{theme_name} focus ring is visible ({r:.2f}:1, needs 3.0)", r >= 3.0)

    # The topbar is a gradient, so both ends have to work, and it is the light
    # end that fails: --topbar-mute was 4.35:1 on #5c6790.
    stops = re.findall(r"#[0-9a-fA-F]{6}", theme.get("--topbar", ""))
    bad_bar = []
    for stop in stops:
        g = tuple(int(stop[1:][i:i + 2], 16) for i in (0, 2, 4))
        for tok in ("topbar-ink", "topbar-mute"):
            r = ratio(over(colour(tok), g), g)
            if r < 4.5:
                bad_bar.append(f"--{tok} on {stop} = {r:.2f}:1")
    check(f"{theme_name} topbar text clears AA at both ends of the gradient",
          not bad_bar, "; ".join(bad_bar))

check("an increased-contrast scheme exists for readers who ask for one (A11Y-6)",
      "@media (prefers-contrast: more)" in CSS)

# ---------------------------------------------------------------------- type
print("\n== type (TYP-1, TYP-4, TYP-19) ==")
px_sizes = [float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", CSS)]
# The one legitimate px font-size in the file: below 16 actual pixels iOS zooms
# the page on focus and never zooms back. A rem there would reintroduce that the
# moment a seller chose a smaller base size.
check("the only px font-size left is the 16px that stops iOS zooming inputs",
      px_sizes == [16.0], px_sizes)

rem_sizes = [float(x) for x in re.findall(r"font-size:\s*([\d.]+)rem", CSS)]
check("every other font size is a rem, so the browser's text-size setting works",
      len(rem_sizes) > 300, len(rem_sizes))
too_small = sorted({round(v * 16, 2) for v in rem_sizes if v * 16 < 11})
check("nothing is set below 11pt, which is Apple's floor on iOS",
      not too_small, too_small)

base = re.search(r"\nbody\s*\{[^}]*font-size:\s*([\d.]+)rem", CSS)
check("the base size is at least the 13pt macOS default",
      base and float(base.group(1)) * 16 >= 13, base and base.group(1))

check("no Ultralight, Thin or Light weights (TYP-4)",
      not re.search(r"font-weight:\s*([12]00|light|thin)\b", CSS, re.I))

# ------------------------------------------------------------- target sizing
print("\n== target size and spacing (A11Y-14, A11Y-15) ==")
check("touch targets are 44px, not the 40px this settled for before",
      'min-height: 44px' in CSS and "min-height: 40px" not in CSS,
      "40px is above the 28pt absolute minimum but below the 44pt default")
check("a pointer gets the 28pt macOS default rather than the 20pt floor",
      re.search(r"@media \(pointer: fine\)\s*\{[^@]*min-height:\s*28px", CSS, re.S) is not None)
check("the gallery remove button has a real hit area under its 20px circle",
      re.search(r"\.gal-x::after\s*\{[^}]*inset:", CSS) is not None)
check("adjacent row actions are 12px apart on touch, not 8",
      re.search(r"\.row-acts,\s*\.pi-acts\s*\{\s*gap:\s*12px", CSS) is not None)

# ---------------------------------------------------------------- safe areas
print("\n== safe areas (LAY-23) ==")
check("the page is allowed to fill a notched screen",
      "viewport-fit=cover" in HTML)
for sel, why in (
    (".topbar", "the sticky topbar sits under the status bar"),
    (".toast", "the toast sits over the home indicator"),
    (".modal-back", "a popup runs to the screen edge"),
    (".main", "content runs under the notch in landscape"),
):
    check(f"{sel} clears the insets  ({why})",
          re.search(re.escape(sel) + r"[^{]*\{[^}]*env\(safe-area-inset", CSS, re.S) is not None)

# --------------------------------------------------------------------- motion
print("\n== motion (MOT-2, MOT-10) ==")
check("Reduce Motion is honoured in more than one place",
      CSS.count("@media (prefers-reduced-motion: reduce)") >= 8)
check("and the hover lifts, which are the z-axis depth change the rule names, stop",
      re.search(r"prefers-reduced-motion[^@]*?\.app-tile:hover[^}]*transform:\s*none", CSS, re.S) is not None)

# --------------------------------------------------------- dialogs and focus
print("\n== dialogs (MOD-5, MOD-6, MOD-8, A11Y-9, A11Y-21) ==")
dialog_count = HTML.count('aria-modal="true"')
check("every popup in the shell is a real dialog", dialog_count >= 8, dialog_count)
check("and each one is labelled by its own title",
      HTML.count("aria-labelledby=") >= 8, HTML.count("aria-labelledby="))
check("popups built at runtime are dialogs too",
      'role="dialog" aria-modal="true"' in JS)
check("the toast announces itself instead of appearing silently",
      'role="status"' in HTML and 'aria-live="polite"' in HTML)
for fragment, label in (
    ("inert", "the app behind an open popup is inert, so Tab and VoiceOver stop at its edge"),
    ('e.key !== "Tab"', "Tab wraps inside the popup rather than walking out of it"),
    ("restoreFocus", "focus goes back where it came from when the popup closes"),
    ("MOD-8", "opening a second popup closes the first"),
    ("lose what you have typed", "Escape asks before throwing away typed work"),
):
    check(label, fragment in JS)

# ------------------------------------------------------------------- writing
print("\n== writing (WRI-6, WRI-12, WRI-17) ==")
strings = [a or b or c for a, b, c in re.findall(
    r'"([^"\\\n]{6,200})"|\'([^\'\\\n]{6,200})\'|`([^`\\]{6,200})`',
    re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", JS, flags=re.S), flags=re.M))]
check("no 'oops' or 'uh-oh' in anything a seller reads",
      not [s for s in strings if re.search(r"\b(oops|uh[- ]oh)\b", s, re.I)])
check("no 'click here' link text",
      not [s for s in strings if re.search(r"\bclick here\b", s, re.I)])
check("no bare 'Invalid' as an error",
      not [s for s in strings if re.match(r"^\s*invalid\b", s, re.I)])
check("errors do not open by blaming the seller",
      not [s for s in strings if re.match(r"^You (must|forgot|didn't|did not|failed)", s)])
check("no vague 'we' error, which never says what to do about it",
      not [s for s in strings if re.search(r"\bwe(?:'re| are| could not| can't)\b.*\b(trouble|problem|issue)\b", s, re.I)])

# =========================================================================
# Rendered half. Everything above reads the source; this measures the paint.
# =========================================================================
print("\n== rendered in Chromium ==")
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("  ! playwright is not installed, so the rendered checks did not run.")
    print("    pip install playwright && playwright install chromium")
    sync_playwright = None

if sync_playwright is not None:
    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "smart.css").write_text(CSS_RAW, encoding="utf-8")
    (tmp / "smart.js").write_text(JS, encoding="utf-8")
    # Version-agnostic on purpose: the cache-busting ?v= is bumped every time
    # these files change, and a test that pinned it would start silently
    # rendering the unstyled page the next time someone bumped it.
    page_html = re.sub(r'/smart-static/smart\.(css|js)\?v=\d+', r"smart.\1", HTML)
    page_html = re.sub(r'<script src="/consent\.js"[^>]*></script>', "", page_html)
    (tmp / "shell.html").write_text(page_html, encoding="utf-8")
    url = (tmp / "shell.html").as_uri()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # ---- what the browser actually paints, at desktop width ----
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url)
        page.wait_for_timeout(700)

        smallest = page.evaluate("""() => {
            let min = 99, what = '';
            document.querySelectorAll('*').forEach(el => {
              if (!el.offsetParent) return;
              if (el.children.length || !(el.textContent || '').trim()) return;
              const fs = parseFloat(getComputedStyle(el).fontSize);
              if (fs < min) { min = fs; what = el.tagName + '.' + String(el.className).slice(0, 24); }
            });
            return { min, what };
        }""")
        check(f"nothing painted is under 11px ({smallest['min']}px on {smallest['what']})",
              smallest["min"] >= 11, smallest)

        desktop = page.evaluate("""() => Array.from(
            document.querySelectorAll('button, select, [role=button], input:not([type=hidden])'))
            .filter(e => e.offsetParent)
            .map(e => { const r = e.getBoundingClientRect();
                        return { id: e.id || String(e.className).slice(0, 24),
                                 w: Math.round(r.width), h: Math.round(r.height) }; })""")
        small = [d for d in desktop if d["h"] < 28 or d["w"] < 28]
        check("every control on a pointer is at least the 28pt macOS default",
              not small, small[:5])

        # ---- and at phone width, where Apple asks for 44 ----
        phone = browser.new_page(viewport={"width": 390, "height": 844},
                                 is_mobile=True, has_touch=True)
        phone.goto(url)
        phone.wait_for_timeout(700)
        touch = phone.evaluate("""() => Array.from(
            document.querySelectorAll('button, select, [role=button], input:not([type=hidden])'))
            .filter(e => e.offsetParent)
            .map(e => { const r = e.getBoundingClientRect();
                        return { id: e.id || String(e.className).slice(0, 24),
                                 w: Math.round(r.width), h: Math.round(r.height) }; })""")
        # Inline links inside a sentence are excluded by Apple and by WCAG 2.2
        # SC 2.5.8 alike: a word in a paragraph is text, not a control. Every
        # real control has to make the number.
        small_touch = [t for t in touch if t["h"] < 44]
        check("every control on a phone is a 44pt target", not small_touch, small_touch[:5])
        check("and the page does not scroll sideways",
              phone.evaluate("document.documentElement.scrollWidth") <= 390,
              phone.evaluate("document.documentElement.scrollWidth"))
        phone.close()

        # ---- dialog behaviour, driven rather than read ----
        page.evaluate("""() => {
            document.getElementById('loginView').hidden = true;
            document.getElementById('appShell').hidden = false;
            document.getElementById('mapGrid').innerHTML =
              '<label>Date <select id="_t1"><option>a</option></select></label>' +
              '<label>Amount <input id="_t2" value="original"></label>';
        }""")
        page.evaluate("document.getElementById('mapModal').hidden = false")
        page.wait_for_timeout(250)
        opened = page.evaluate("""() => ({
            focus: document.activeElement ? (document.activeElement.id || document.activeElement.tagName) : null,
            inert: document.getElementById('appShell').hasAttribute('inert'),
            role:  document.querySelector('#mapModal .modal').getAttribute('role'),
        })""")
        check("opening a popup moves focus into it, past the close button",
              opened["focus"] == "_t1", opened)
        check("and makes the app behind it inert", opened["inert"] is True)
        check("and it is announced as a dialog", opened["role"] == "dialog")

        inside = []
        for _ in range(12):
            page.keyboard.press("Tab")
            inside.append(page.evaluate(
                "!!document.getElementById('mapModal').contains(document.activeElement)"))
        check("Tab never escapes the popup", all(inside), inside)

        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        check("Escape closes a popup with nothing typed in it",
              page.evaluate("document.getElementById('mapModal').hidden") is True)
        check("and clears the inert state behind it",
              page.evaluate("!document.getElementById('appShell').hasAttribute('inert')"))

        # typed work is not thrown away silently
        page.evaluate("document.getElementById('mapModal').hidden = false")
        page.wait_for_timeout(250)
        page.evaluate("document.getElementById('_t2').value = 'edited'")
        page.once("dialog", lambda d: d.dismiss())
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        check("Escape asks first when a field has been edited, and stays open on no",
              page.evaluate("document.getElementById('mapModal').hidden") is False)

        # one at a time
        page.evaluate("document.getElementById('addModal').hidden = false")
        page.wait_for_timeout(300)
        both = page.evaluate("""() => ({ map: !document.getElementById('mapModal').hidden,
                                          add: !document.getElementById('addModal').hidden })""")
        check("opening a second popup closes the first", both["map"] is False and both["add"] is True, both)

        browser.close()

print()
if FAIL:
    print(f"{FAIL} failed, {PASS} passed")
    sys.exit(1)
print(f"all {PASS} checks passed")
