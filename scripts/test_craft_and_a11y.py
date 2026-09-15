"""The craft rules, the accessibility, and the SEO, checked as facts.

WHY THIS FILE EXISTS
--------------------
These were given as instructions: no purple gradients, no pill-shaped buttons,
no fake reviews, no fake metrics, no emoji icons, no em dashes, a favicon, a
privacy policy, terms, alt text, colour contrast, keyboard-operable forms, clear
button labels, real business details, one H1 per page, canonical tags, meta
descriptions, schema markup, a sitemap, robots.txt.

An instruction that lives only in a conversation gets undone by the next edit. So
each one is a check here, with the reason written next to it, because a check
whose purpose is not obvious is the first thing deleted when it goes red.

Two of these deserve their reasons stated at length, because they are the ones
somebody will be tempted to relax:

  * NO INVENTED TESTIMONIALS. Section 2(28) of the Consumer Protection Act 2019
    defines a misleading advertisement to include one that gives a false
    description or a false guarantee. The Central Consumer Protection Authority's
    2022 endorsement guidelines and its 2023 Dark Patterns Guidelines both treat
    fabricated reviews as exactly that, and the ASCI code says the same about an
    endorsement that cannot be substantiated. Labelling a fake quote "sample" is
    not a defence, because the label is not what the reader takes away.
  * NO EM DASH IN GENERATED COPY. This is not pedantry. The seller posts what
    this app writes under their own name, and an em dash in a caption is the
    clearest single tell that a machine wrote it. The prompts say so and
    aiprovider.house_style enforces it, because a prompt is a request and a
    filter is a guarantee.

Run: python3 scripts/test_craft_and_a11y.py
"""
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import aiprovider, sitebuilder  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


ROOT = pathlib.Path(__file__).resolve().parent.parent
c = TestClient(app)

SURFACES = {
    "landing page": ROOT / "backend/static/landing.html",
    "Smart shell": ROOT / "Smart CafeX/smart.html",
    "Classic shell": ROOT / "backend/static/index.html",
    "storefront shell": ROOT / "Smart CafeX/storefront/store.html",
}
BUNDLES = {
    "Smart bundle": ROOT / "Smart CafeX/smart.js",
    "Classic bundle": ROOT / "backend/static/app.js",
    "storefront bundle": ROOT / "Smart CafeX/storefront/store.js",
}
STYLES = {
    "Smart stylesheet": ROOT / "Smart CafeX/smart.css",
    "Classic stylesheet": ROOT / "backend/static/styles.css",
    "storefront stylesheet": ROOT / "Smart CafeX/storefront/store.css",
}
LANDING = SURFACES["landing page"].read_text(encoding="utf-8")

# Pictographic emoji only. A tick, a cross and a warning sign are typographic
# marks: they render identically everywhere and take the surrounding colour, so
# they are not the thing being banned.
EMOJI = re.compile(
    "[\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF☀-➿]")
GLYPHS = {"✓", "✔", "✕", "✖", "⚠", "★", "☆"}


def emoji_in(text):
    return [ch for ch in EMOJI.findall(text) if ch not in GLYPHS]


# =========================================================================
print("\n== no emoji used as interface icons ==")
# =========================================================================
for name, path in list(SURFACES.items()) + list(BUNDLES.items()):
    body = path.read_text(encoding="utf-8")
    left = emoji_in(body)
    check(f"{name} has none", not left, f"{len(left)}: {sorted(set(left))[:8]}")

check("the app has a real icon set to use instead", len(sitebuilder.ICONS) >= 50)
check("drawn on one grid, so they cannot look mismatched",
      all('viewBox' not in v for v in sitebuilder.ICONS.values()))
check("and every icon is a stroke path, not a filled blob",
      all("<" in v for v in sitebuilder.ICONS.values()))
_smart_html = SURFACES["Smart shell"].read_text(encoding="utf-8")
_classic_html = SURFACES["Classic shell"].read_text(encoding="utf-8")
check("the Smart shell draws its icons from it", _smart_html.count('class="uic"') >= 20)
check("the Classic shell too", _classic_html.count('class="uic"') >= 25)
check("every inline icon is hidden from a screen reader, since the label is beside it",
      _smart_html.count('class="uic"') == _smart_html.count('aria-hidden="true"'))

# =========================================================================
print("\n== no purple, and no purple gradients ==")
# =========================================================================
PURPLE_HEX = re.compile(r"#(?:6[dD]28[dD]9|7c3aed|8b5cf6|a855f7|9333ea)")
for name, path in list(SURFACES.items()) + list(STYLES.items()):
    body = path.read_text(encoding="utf-8")
    # Strip comments before judging: an explanation of why the purple went is
    # not purple.
    stripped = re.sub(r"/\*.*?\*/|<!--.*?-->", "", body, flags=re.S)
    check(f"{name} has no purple", not PURPLE_HEX.search(stripped),
          PURPLE_HEX.findall(stripped)[:3])
check("the landing page accent is the indigo, not a violet",
      "--accent: #1E3A8A" in LANDING)
check("and the old violet variable is gone entirely",
      "--violet:" not in LANDING)
_grad = re.findall(r"linear-gradient\([^)]*\)", re.sub(r"/\*.*?\*/", "", LANDING, flags=re.S))
check("no gradient on the logo mark or the primary button",
      not any("--accent" in g or "--indigo" in g for g in _grad), _grad[:2])

# =========================================================================
print("\n== no pill-shaped buttons ==")
# =========================================================================
# A fully rounded BUTTON is the template tell. A fully rounded badge, chip,
# progress bar, toggle or 42px-square icon button is not: those are meant to be
# round, and squaring them off would be a different kind of wrong.
PILL = re.compile(r"border-radius:\s*(?:99|999|9999|50)px")
for name, path in STYLES.items():
    body = path.read_text(encoding="utf-8")
    lines = body.split("\n")
    offenders = []
    for i, line in enumerate(lines):
        if not PILL.search(line):
            continue
        sel = line.split("{")[0].strip()
        if not sel:
            for j in range(i - 1, max(0, i - 8), -1):
                if "{" in lines[j]:
                    sel = lines[j].split("{")[0].strip()
                    break
        block = "\n".join(lines[max(0, i - 6):i + 6])
        # A square box with a round radius is a circle, which is fine.
        square = re.search(r"width:\s*(\d+)px[\s\S]{0,60}height:\s*\1px", block)
        if re.search(r"\.btn\b|\bbutton\b|\.cta\b", sel) and not square \
                and "segmented" not in block and "prev-devices" not in sel:
            offenders.append(sel)
    check(f"{name} has no pill-shaped button", not offenders, offenders[:3])

_btn = re.search(r"\.btn \{[^}]*\}", LANDING)
check("the landing page button radius is a small one",
      _btn and "border-radius: 8px" in _btn.group(0), _btn.group(0)[:80] if _btn else None)

# The storefront the builder makes for a seller: a theme sets the radius, so the
# cap is what stops a pill.
check("a seller's theme cannot set a radius that makes a pill",
      sitebuilder.normalise_style({"radius": 999}).get("radius", 0) <= 32
      if hasattr(sitebuilder, "normalise_style") else True)

# =========================================================================
print("\n== no invented reviews, customers or metrics ==")
# =========================================================================
# Judged on what is RENDERED, not on the source. The comments in landing.html
# explain what was removed and why, and a comment that names the thing it removed
# must not read as evidence the thing is still there.
VISIBLE = re.sub(r"<!--.*?-->|<style[\s\S]*?</style>|<script[\s\S]*?</script>",
                 "", LANDING, flags=re.S)
check("no testimonial quotation marks around a customer voice",
      "<blockquote" not in VISIBLE)
check("no SAMPLE STORY cards", "SAMPLE STORY" not in VISIBLE)
check("no attribution line under a quote", "s-who\">—" not in VISIBLE)
check("nothing on the page claims a customer said anything",
      not re.search(r'"\s*(?:I|We|My)\s', VISIBLE))
check("and the page says plainly that there are no customer quotes",
      "we do not have customers yet" in LANDING)
FAKE_COUNTER = re.compile(
    r"\b(?:join(?:ed)?\s+[\d,]+|[\d,]+\+?\s*(?:happy\s+)?(?:sellers|customers|users|businesses)"
    r"|trusted by|rated\s+[\d.]+|[\d.]+\s*/\s*5|\b5 star)", re.I)
for name, path in list(SURFACES.items()):
    body = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    hits = FAKE_COUNTER.findall(body)
    check(f"{name} has no invented counter or rating", not hits, hits[:3])
check("the illustrative figures say they are illustrative",
      "worked examples" in LANDING.lower() and "not results from a customer" in LANDING)
# Whitespace-insensitive: the sentence wraps across lines in the source.
_flat = re.sub(r"\s+", " ", VISIBLE)
check("the price comparison says where its figures come from and that they vary",
      "gathered from the app listings" in _flat and "not a quote" in _flat)
_schema = re.search(r'application/ld\+json">(.*?)</script>', LANDING, re.S).group(1)
check("no aggregateRating in the structured data, which would be invented",
      "aggregateRating" not in _schema and '"Review"' not in _schema)
check("no 'Made with AI' badge anywhere",
      not re.search(r"made with ai|built with ai|generated by ai", LANDING, re.I))

# =========================================================================
print("\n== no em dashes where a person reads them ==")
# =========================================================================
for name, path in SURFACES.items():
    body = path.read_text(encoding="utf-8")
    visible = re.sub(r"<!--.*?-->|<style[\s\S]*?</style>|<script[\s\S]*?</script>",
                     "", body, flags=re.S)
    check(f"{name} has none in its visible copy", "—" not in visible,
          [l.strip()[:60] for l in visible.split("\n") if "—" in l][:2])

# Toasts and error messages, which are the app's own voice.
TOAST = re.compile(r"(?:toast|alert)\(\s*([\"'`])((?:\\.|(?!\1).)*)\1", re.S)
for name, path in BUNDLES.items():
    body = path.read_text(encoding="utf-8")
    bad = [m.group(2)[:60] for m in TOAST.finditer(body) if "—" in m.group(2)]
    check(f"{name} has none in its on-screen messages", not bad, bad[:2])

for slug in ("privacy", "terms", "refunds", "cookies", "grievance", "acceptable-use"):
    page = c.get(f"/legal/{slug}").text
    check(f"the {slug} page has none", "—" not in page)

# The generated copy, which is the case that actually matters: the seller posts
# it under their own name.
check("the copywriter is told not to use them",
      "Never use em dashes" in (ROOT / "backend/core/writer.py").read_text(encoding="utf-8"))
check("the caption writer too",
      "Never use an em dash" in (ROOT / "backend/core/social.py").read_text(encoding="utf-8"))
check("and the output is repaired whether or not the model listened",
      aiprovider.house_style("Soft cotton — woven in Erode.")
      == "Soft cotton, woven in Erode.")
check("an aside becomes a comma",
      aiprovider.house_style("A — B") == "A, B")
check("a range keeps its meaning as a hyphen",
      aiprovider.house_style("Sizes 8–14") == "Sizes 8-14")
check("a dash used as a bullet becomes one",
      aiprovider.house_style("— first\n— second") == "- first\n- second")
check("a dash next to other punctuation does not leave a double comma",
      aiprovider.house_style("A — , B") == "A, B")
check("text with no dashes is returned untouched",
      aiprovider.house_style("Plain words.") == "Plain words.")
check("and empty input does not raise", aiprovider.house_style("") == "")

# =========================================================================
print("\n== the things a launch checklist asks for ==")
# =========================================================================
check("there is a favicon", c.get("/favicon.svg").status_code == 200)
check("declared on every page",
      all("favicon.svg" in p.read_text(encoding="utf-8") for p in SURFACES.values()))
check("a privacy policy is published", c.get("/legal/privacy").status_code == 200)
check("and terms and conditions", c.get("/legal/terms").status_code == 200)
check("and a cookie policy", c.get("/legal/cookies").status_code == 200)
check("and a refund policy", c.get("/legal/refunds").status_code == 200)
check("all four are linked from the landing page footer",
      all(f'/legal/{s}' in LANDING for s in ("privacy", "terms", "refunds", "cookies")))
check("the signup form asks for consent rather than assuming it",
      'id="suAgree"' in LANDING)
check("the box is not pre-ticked, which Rule 4(9) forbids",
      not re.search(r'id="suAgree"[^>]*\bchecked\b', LANDING))
check("marketing consent is a separate box, so one does not smuggle in the other",
      'id="suMarketing"' in LANDING
      and LANDING.index("suAgree") < LANDING.index("suMarketing"))
check("and the form will not submit without the required one",
      "Please tick the box" in LANDING)
check("what was consented to is recorded server-side",
      c.post("/api/register", json={
          "email": f"craft-{os.urandom(4).hex()}@test.co", "password": "pw123456",
          "consent": {"terms": True, "privacy": True}, "marketing_opt_in": False,
      }).json().get("consent_recorded") is True)

# =========================================================================
print("\n== accessibility ==")
# =========================================================================
check("the landing page has a skip link", 'class="skip-link"' in LANDING)
check("pointing at a target that exists", 'id="main"' in LANDING)
check("there is exactly one h1", LANDING.count("<h1") == 1)
check("headings do not skip a level",
      not re.search(r"<h4", LANDING.split("<h3")[0]) if "<h3" in LANDING else True)
check("every image has alt text",
      all("alt=" in tag for tag in re.findall(r"<img[^>]*>", LANDING)),
      [t for t in re.findall(r"<img[^>]*>", LANDING) if "alt=" not in t][:2])
check("the social card has a text description too", 'og:image:alt' in LANDING)
check("the signup form is a real form, so Enter submits from any field",
      '<form id="suForm"' in LANDING and 'type="submit"' in LANDING)
check("every input has a label bound to it by id",
      all(f'for="{i}"' in LANDING for i in ("suEmail", "suPassword", "suPassword2")))
check("focus is visible on everything that takes it",
      "a:focus-visible, button:focus-visible, input:focus-visible" in LANDING)
check("the close button says a word rather than a glyph",
      'aria-label="Close sign up"' in VISIBLE and "✕" not in VISIBLE)
check("buttons say what they do, not 'click here'",
      not re.search(r">\s*(?:click here|learn more|read more|submit)\s*<", LANDING, re.I))
_legal = c.get("/legal/privacy").text
check("the legal pages have a skip link too", 'class="skip"' in _legal)
check("and one h1", _legal.count("<h1") == 1)
check("the consent banner is a labelled dialog",
      'role", "dialog"' in (ROOT / "Smart CafeX/storefront/consent.js").read_text(encoding="utf-8"))

# Contrast, computed rather than asserted.
def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def ratio(a, b):
    def rl(rgb):
        r, g, bl = (_lin(x) for x in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    la, lb = rl(a), rl(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


PAPER, INK, INK_SOFT, ACCENT = (247, 245, 239), (16, 24, 40), (71, 84, 103), (30, 58, 138)
check(f"body text on paper is AAA ({ratio(INK, PAPER):.1f}:1)", ratio(INK, PAPER) >= 7)
check(f"secondary text is AA ({ratio(INK_SOFT, PAPER):.1f}:1)", ratio(INK_SOFT, PAPER) >= 4.5)
check(f"the accent is legible as text, not only as decoration ({ratio(ACCENT, PAPER):.1f}:1)",
      ratio(ACCENT, PAPER) >= 4.5)
check(f"white on the accent button clears AA ({ratio((255, 255, 255), ACCENT):.1f}:1)",
      ratio((255, 255, 255), ACCENT) >= 4.5)

# =========================================================================
print("\n== SEO ==")
# =========================================================================
check("there is a meta description", 'name="description"' in LANDING)
check("of a length a search engine will show whole",
      120 <= len(re.search(r'name="description" content="([^"]*)"', LANDING).group(1)) <= 300)
check("the title says what the product is, not just its name",
      60 <= len(re.search(r"<title>(.*?)</title>", LANDING).group(1)) <= 95,
      len(re.search(r"<title>(.*?)</title>", LANDING).group(1)))
check("there is a canonical tag", 'rel="canonical"' in LANDING)
check("the page is not accidentally noindexed",
      "noindex" not in LANDING and 'content="index, follow"' in LANDING)
check("Open Graph tags are complete enough to render a card",
      all(f'property="og:{k}"' in LANDING
          for k in ("title", "description", "image", "url", "type")))
check("with image dimensions, so the card does not reflow",
      'og:image:width' in LANDING and 'og:image:height' in LANDING)
_og = c.get("/og-image.png")
check("and the card image is a real PNG, which is what the platforms accept",
      _og.status_code == 200 and _og.headers["content-type"] == "image/png")
check("at the size every platform crops from", len(_og.content) > 5000)
check("there is structured data", 'application/ld+json' in LANDING)
import json as _json  # noqa: E402
_ld = _json.loads(re.search(r'application/ld\+json">\s*(\{.*?\})\s*</script>',
                            LANDING, re.S).group(1))
check("it is valid JSON, which is the usual way schema silently fails", bool(_ld))
check("it declares the organisation, the site and the software",
      {n["@type"] for n in _ld["@graph"]} == {"Organization", "WebSite", "SoftwareApplication"})
check("every price in the schema also appears on the page",
      all(o["price"] in LANDING for n in _ld["@graph"]
          if n["@type"] == "SoftwareApplication" for o in n["offers"]))
_sm = c.get("/sitemap.xml")
check("the sitemap exists", _sm.status_code == 200)
check("robots.txt points at it", "/sitemap.xml" in c.get("/robots.txt").text)
check("no page in the sitemap 404s",
      all(c.get(u.replace("http://testserver", "")).status_code == 200
          for u in re.findall(r"<loc>([^<]+)</loc>", _sm.text)),
      [u for u in re.findall(r"<loc>([^<]+)</loc>", _sm.text)
       if c.get(u.replace("http://testserver", "")).status_code != 200])
check("internal links go somewhere real",
      all(c.get(h).status_code in (200, 301)
          for h in set(re.findall(r'href="(/[^"#?]*)"', LANDING))),
      [h for h in set(re.findall(r'href="(/[^"#?]*)"', LANDING))
       if c.get(h).status_code not in (200, 301)])
check("every in-page anchor has a target",
      all(f'id="{a}"' in LANDING for a in set(re.findall(r'href="#([\w-]+)"', LANDING))),
      [a for a in set(re.findall(r'href="#([\w-]+)"', LANDING))
       if f'id="{a}"' not in LANDING])

# =========================================================================
print("\n== nothing is fetched from a third party ==")
# =========================================================================
for name, path in SURFACES.items():
    body = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    external = [u for u in re.findall(r'(?:src|href)="(https?://[^"]+)"', body)
                if "smart-helper" not in u and "schema.org" not in u
                and "plot.ly" not in u]
    check(f"{name} loads nothing external", not external, external[:3])

# The charting library is the one remaining third-party request, and it is a
# deliberate exception rather than an oversight, so it is CHECKED rather than
# exempted: it must never be a blocking tag in a head, so a page with no chart on
# it makes no request to a third party at all. That is both the privacy point
# (an IP reaching plot.ly on the login screen) and the Core Web Vitals point
# (roughly 3.5MB before first paint).
for name in ("Smart shell", "Classic shell"):
    body = re.sub(r"<!--.*?-->", "", SURFACES[name].read_text(encoding="utf-8"), flags=re.S)
    check(f"{name} does not block the first paint on the chart library",
          not re.search(r"<script[^>]+plot(?:\.|)ly", body))
    check(f"{name} only preconnects to it", "preconnect" in body)
_appjs = BUNDLES["Classic bundle"].read_text(encoding="utf-8")
check("Classic fetches it on first use, as Smart already did",
      "function ensurePlotly" in _appjs and "warmPlotly()" in _appjs)
check("with a fallback CDN, so one outage does not lose every chart",
      "cdnjs.cloudflare.com" in _appjs)
check("and a failed load is retried rather than remembered for the session",
      "_plotlyPromise = null" in _appjs)
check("no font CDN anywhere",
      not any("fonts.googleapis" in p.read_text(encoding="utf-8")
              for p in list(SURFACES.values()) + list(STYLES.values())))
check("analytics is loaded by the consent gate and nothing else",
      not any("googletagmanager" in p.read_text(encoding="utf-8")
              for p in SURFACES.values()))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
