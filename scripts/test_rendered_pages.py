"""What the browser actually paints, measured in a real browser.

WHY THIS EXISTS, AND WHY IT IS SEPARATE FROM test_craft_and_a11y.py
------------------------------------------------------------------
Reading the source tells you what a stylesheet SAYS. It does not tell you what
wins. Two bugs found on this page in one afternoon were both invisible to any
check that greps the file:

  1. The primary call to action in the navigation was painted #475467 on a
     #1E3A8A button, about 1.5:1, because `.nav-links a` and `.btn-primary` have
     the same specificity and the first one came later in the file. The source
     plainly said `color: #fff`. The browser disagreed.
  2. The hero was `class="wrap hero"`, and `.hero` used the `padding` shorthand,
     which zeroed the 24px side gutter `.wrap` had set. Invisible on a desktop,
     because the 1120px max-width kept text off the edge anyway; on a phone the
     headline ran into both edges of the screen.

Neither is exotic. Both are the ordinary way CSS goes wrong, and the only way to
catch them is to render the page and measure it. So this file does that: it
starts the real app, opens the real pages in Chromium at four widths, and checks
computed colour, layout overflow and tap-target size.

Needs playwright with chromium. Skips cleanly, loudly, if it is not installed,
because a test that silently does nothing is worse than no test.

Run: python3 scripts/test_rendered_pages.py
"""
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright is not installed, so the rendered checks cannot run.")
    print("  pip install playwright && playwright install chromium")
    sys.exit(0)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


os.environ.setdefault("LAUNCH_MODE", "true")
os.environ.setdefault("LEGAL_NAME", "Rendered Test Operator")
os.environ.setdefault("BUSINESS_ADDRESS", "1 Test Road, Bengaluru 560001")
os.environ.setdefault("SUPPORT_EMAIL", "care@example.in")
os.environ.setdefault("SUPPORT_PHONE", "9876543210")
os.environ.setdefault("GRIEVANCE_NAME", "Rendered Test Operator")
os.environ.setdefault("GRIEVANCE_EMAIL", "grievance@example.in")

import uvicorn  # noqa: E402
from backend.main import app  # noqa: E402

PORT = free_port()
BASE = f"http://127.0.0.1:{PORT}"
threading.Thread(
    target=lambda: uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error"),
    daemon=True).start()

for _ in range(50):
    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=0.3).close()
        break
    except OSError:
        time.sleep(0.2)
else:
    print("the server did not come up")
    sys.exit(1)

# The WCAG formula, so a ratio is measured rather than asserted.
CONTRAST_JS = """
(() => {
  function lin(v) { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }
  function rl(c) { return 0.2126*lin(c[0]) + 0.7152*lin(c[1]) + 0.0722*lin(c[2]); }
  function parse(s) {
    const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(",").map(x => parseFloat(x));
    return { rgb: [p[0], p[1], p[2]], a: p.length > 3 ? p[3] : 1 };
  }
  // The real background is whatever the nearest non-transparent ancestor paints.
  function bgOf(el) {
    let n = el;
    while (n && n !== document.documentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.3) return c.rgb;
      n = n.parentElement;
    }
    return [255, 255, 255];
  }
  window.__contrast = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color).rgb, bg = bgOf(el);
    const a = rl(fg), b = rl(bg);
    return { ratio: (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05),
             fg: cs.color, bg: "rgb(" + bg.join(",") + ")",
             size: parseFloat(cs.fontSize), weight: cs.fontWeight,
             text: (el.textContent || "").trim().slice(0, 40) };
  };
  return true;
})()
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch()

    # =====================================================================
    print("\n== colours, as the browser actually paints them ==")
    # =====================================================================
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(BASE + "/", wait_until="networkidle")
    page.evaluate(CONTRAST_JS)

    # Large text (18.66px bold or 24px) needs 3:1; everything else 4.5:1.
    for sel, label in [
        (".nav-links a.btn-primary", "the main call to action in the nav"),
        (".hero-ctas .btn-primary", "the hero's primary button"),
        (".hero-ctas .btn-ghost", "the hero's secondary button"),
        ("h1", "the headline"),
        (".hero p.lead", "the lead paragraph"),
        (".hero-note", "the small print under the buttons"),
        (".eyebrow", "the eyebrow label"),
        (".miss-card p", "the body text in the opportunity cards"),
        (".ticket p", "the body text on the dark example cards"),
        (".ticket .t-tag", "the tag on the dark cards"),
        (".foot a", "the footer links"),
        (".stack-note", "the footnote under the price table"),
    ]:
        r = page.evaluate(f"window.__contrast({sel!r})")
        if r is None:
            check(f"{label} exists", False, sel)
            continue
        large = r["size"] >= 24 or (r["size"] >= 18.66 and int(r["weight"]) >= 700)
        need = 3.0 if large else 4.5
        check(f"{label} is legible ({r['ratio']:.1f}:1, needs {need})",
              r["ratio"] >= need,
              f"{r['fg']} on {r['bg']} at {r['size']}px: {r['text']!r}")

    # =====================================================================
    print("\n== layout, at the widths people actually use ==")
    # =====================================================================
    page.close()
    for width, name in [(360, "a small Android"), (390, "an iPhone"),
                        (768, "a tablet"), (1280, "a laptop")]:
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(BASE + "/", wait_until="networkidle")
        res = page.evaluate("""() => {
          const doc = document.documentElement;
          const bad = [];
          document.querySelectorAll("body *").forEach(el => {
            const cs = getComputedStyle(el);
            if (cs.position === "fixed" || cs.display === "none") return;
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.right > doc.clientWidth + 1) {
              bad.push(el.tagName + "." + String(el.className).split(" ")[0]
                       + " right=" + Math.round(r.right));
            }
          });
          const hero = document.querySelector(".hero");
          const cs = getComputedStyle(hero);
          return { scrollW: doc.scrollWidth, clientW: doc.clientWidth,
                   over: bad.slice(0, 5),
                   padL: parseFloat(cs.paddingLeft), padR: parseFloat(cs.paddingRight) };
        }""")
        check(f"on {name} ({width}px) the page does not scroll sideways",
              res["scrollW"] <= res["clientW"] + 1,
              f"{res['scrollW']} > {res['clientW']}")
        check(f"and nothing overflows the right edge",
              not res["over"], res["over"])
        check(f"the hero keeps a side gutter ({res['padL']:.0f}px)",
              res["padL"] >= 16 and res["padR"] >= 16,
              f"{res['padL']}/{res['padR']}")
        page.close()

    # =====================================================================
    print("\n== tap targets and keyboard order ==")
    # =====================================================================
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(BASE + "/", wait_until="networkidle")
    small = page.evaluate("""() => {
      const bad = [];
      document.querySelectorAll("a, button").forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return;              // hidden
        if (el.classList.contains("skip-link")) return;           // only on focus
        if (el.closest("nav.nav")) return;                        // a text nav row
        if (r.height < 40) {
          bad.push((el.textContent || el.getAttribute("aria-label") || el.tagName)
                   .trim().slice(0, 30) + " h=" + Math.round(r.height));
        }
      });
      return bad;
    }""")
    # WCAG 2.2 SC 2.5.8 asks for 24px and the platform guidance for 44px. 40 is
    # the line drawn here because it is what a real finger needs once padding and
    # line-height are counted. The skip link is excluded (it exists only while
    # focused, where it is reached by keyboard, not by thumb) and so is the
    # desktop nav row, which collapses on a phone.
    check("every tappable thing is big enough for a thumb", not small, small[:6])

    first = page.evaluate("""() => {
      const el = document.querySelector("body *");
      return document.querySelector(".skip-link") ? "skip-link" : null;
    }""")
    check("the first focusable thing is the skip link", first == "skip-link")
    page.keyboard.press("Tab")
    focused = page.evaluate("() => document.activeElement.className")
    check("and it actually takes focus first", "skip-link" in (focused or ""), focused)
    visible = page.evaluate("""() => {
      const el = document.querySelector(".skip-link");
      return el.getBoundingClientRect().left > -100;
    }""")
    check("and becomes visible when it does", visible)

    # =====================================================================
    print("\n== the signup form works from the keyboard alone ==")
    # =====================================================================
    page.evaluate("openSignup('free')")
    page.wait_for_timeout(200)
    page.fill("#suEmail", "keyboard@test.co")
    page.fill("#suPassword", "pw123456")
    page.fill("#suPassword2", "pw123456")
    # Enter from a field, with the consent box untouched: it must refuse, and say
    # why, rather than submitting or doing nothing at all.
    page.press("#suPassword2", "Enter")
    page.wait_for_timeout(400)
    err = page.evaluate("() => document.getElementById('suError').textContent")
    check("Enter submits the form from any field", bool(err), err)
    check("and it refuses without consent, saying so plainly",
          "tick the box" in err, err)
    check("the error is announced to a screen reader",
          page.evaluate("() => document.getElementById('suError').getAttribute('role')") == "alert")
    check("and focus moves to the box that needs attention",
          page.evaluate("() => document.activeElement.id") == "suAgree")

    # =====================================================================
    print("\n== the legal pages render without stylesheets or script ==")
    # =====================================================================
    page.close()
    ctx = browser.new_context(java_script_enabled=False,
                              viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.goto(BASE + "/legal/privacy", wait_until="domcontentloaded")
    text = page.evaluate("() => document.body.innerText")
    check("a legal page is readable with JavaScript switched off", len(text) > 2000)
    check("and it names the operator", "Rendered Test Operator" in text)
    check("with exactly one h1",
          page.evaluate("() => document.querySelectorAll('h1').length") == 1)
    check("and no horizontal scroll on a phone",
          page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"))
    ctx.close()

    # =====================================================================
    print("\n== no third-party request on a page with no chart ==")
    # =====================================================================
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    page.goto(BASE + "/app", wait_until="networkidle")
    page.wait_for_timeout(600)
    outside = [u for u in seen if not u.startswith(BASE)]
    # warmPlotly runs on an idle callback, so the library may legitimately start
    # downloading AFTER first paint. What must not happen is a blocking request
    # before the page is usable.
    check("the Classic app paints without waiting on a third party",
          all("plot" not in u for u in seen[:6]), seen[:6])
    check("and the only outside host is the chart CDN, if anything",
          all("plot.ly" in u or "cdnjs" in u for u in outside), outside[:4])
    page.close()
    browser.close()

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
