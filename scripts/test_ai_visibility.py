"""AI visibility: crawler rules, the guide pages, llms.txt, sameAs, Bing and IndexNow.

Run: python scripts/test_ai_visibility.py   (prints "N passed, M failed")
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
for k in ("BRAND_PROFILES", "INDEXNOW_KEY", "BING_SITE_VERIFICATION"):
    os.environ.pop(k, None)

from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.core import geo, pricing, sitebuilder  # noqa: E402

c = TestClient(main.app)
passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  <-- {detail}")


def ld_blocks(html):
    out = []
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        out.append(json.loads(raw))
    return out


EM = "—"

print("\n== robots.txt ==")
r = c.get("/robots.txt")
txt = r.text
check("answers 200", r.status_code == 200, r.status_code)
for bot in ("OAI-SearchBot", "ChatGPT-User", "GPTBot", "Claude-SearchBot", "ClaudeBot",
            "PerplexityBot", "Google-Extended", "Bingbot"):
    check(f"names {bot}", f"User-agent: {bot}" in txt)
groups = txt.split("\n\n")
check("every group keeps the app private",
      all("Disallow: /smart" in g and "Disallow: /api/" in g for g in groups if "User-agent" in g))
check("no group blocks the whole site", "Disallow: /\n" not in txt)
check("still points at the sitemap", "Sitemap: " in txt and txt.strip().endswith("/sitemap.xml"))

print("\n== guide pages ==")
for path in geo.paths():
    r = c.get(path)
    h = r.text
    check(f"{path} answers 200 as HTML", r.status_code == 200 and "text/html" in r.headers["content-type"], r.status_code)
    check(f"{path} has exactly one h1", h.count("<h1") == 1)
    check(f"{path} has a canonical tag", 'rel="canonical"' in h)
    check(f"{path} is indexable", 'content="index, follow' in h)
    check(f"{path} shows a last-updated date", "Last updated" in h and geo.UPDATED in h)
    check(f"{path} opens with a direct answer", '<div class="answer">' in h)
    check(f"{path} has no em dash", EM not in h, h[max(0, h.find(EM) - 60):h.find(EM) + 20])
    check(f"{path} loads no script but its schema",
          len(re.findall(r"<script(?! type=\"application/ld\+json\")", h)) == 0)
    try:
        blocks = ld_blocks(h)
        graph = blocks[0]["@graph"]
        types = {g["@type"] for g in graph}
        check(f"{path} schema parses", True)
    except Exception as e:  # noqa: BLE001
        graph, types = [], set()
        check(f"{path} schema parses", False, e)
    check(f"{path} schema names the organisation", "Organization" in types)
    if path != "/guides":
        check(f"{path} schema has WebPage, breadcrumbs and FAQ",
              {"WebPage", "BreadcrumbList", "FAQPage"} <= types, types)
        faq = next((g for g in graph if g["@type"] == "FAQPage"), {"mainEntity": []})
        visible = re.findall(r'<section class="faq">.*?</section>', h, re.S)[0]
        check(f"{path} every FAQ in the schema is on the page",
              all(f"<h3>{geo.esc(q['name'])}</h3>" in visible for q in faq["mainEntity"]))
        page = next(g for g in graph if g["@type"] == "WebPage")
        check(f"{path} schema carries dateModified", page.get("dateModified") == geo.UPDATED)

check("an unknown guide 404s", c.get("/for/cafes").status_code == 404)
check("an unknown comparison 404s", c.get("/compare/nothing").status_code == 404)

print("\n== the facts are the app's facts ==")
about = c.get("/about").text
mx = pricing.PLANS["pro"]
check("Max price comes from pricing.py", f"₹{mx['price_inr']}" in about)
check("the plan is called Max, never Pro or Semi Pro",
      "Max" in about and "Semi Pro" not in about and ">Pro<" not in about)
cmp = c.get("/compare/shopify-apps").text
total = pricing.stack_comparison()["typical_total_inr"]
check("the Shopify stack total is pricing.py's", geo._inr(total) in cmp, geo._inr(total))
check("Indian grouping", geo._inr(272721) == "₹2,72,721" and geo._inr(999) == "₹999"
      and geo._inr(100000) == "₹1,00,000")
check("no page uses the RFM or EOQ jargon",
      all(w not in c.get(p).text for p in geo.paths() for w in ("RFM", "EOQ")))
check("clothing GST is the post-September 2025 rule",
      "₹2,500" in c.get("/for/clothing-sellers").text and "18%" in c.get("/for/clothing-sellers").text)
check("the about page tells us apart from other One Tap apps",
      "not related" in about and "One Tap sign-in" in about)

print("\n== the new paths can never be a shop address ==")
for seg in ("guides", "about", "for", "compare"):
    check(f"'{seg}' is reserved", sitebuilder.handle_reserved(seg))

print("\n== sitemap ==")
sm = c.get("/sitemap.xml").text
for path in geo.paths():
    check(f"sitemap lists {path}", f"{path}</loc>" in sm)
check("guides carry a lastmod", re.search(r"/about</loc><lastmod>\d{4}-\d\d-\d\d</lastmod>", sm) is not None)

print("\n== llms.txt ==")
r = c.get("/llms.txt")
check("answers 200 as text", r.status_code == 200 and r.headers["content-type"].startswith("text/plain"))
check("starts with the product name", r.text.startswith("# One Tap Manager"))
check("has the one-line summary", "> One Tap Manager is shop management software" in r.text)
check("links every guide", all(p in r.text for p in geo.paths() if p != "/guides"))
check("no em dash", EM not in r.text)
check("claims no profiles while none are set", "Official profiles" not in r.text)

print("\n== sameAs from BRAND_PROFILES ==")
check("empty by default", geo.profiles() == [])
main._LANDING_CACHE.clear()
land = c.get("/").text
org = ld_blocks(land)[0]["@graph"][0]
check("landing schema still parses with an empty list", org.get("sameAs") == [])
os.environ["BRAND_PROFILES"] = ("https://www.reddit.com/r/OneTapManager, https://www.instagram.com/onetapmanager "
                                "http://insecure.example javascript:alert(1) https://www.reddit.com/r/OneTapManager")
check("only https, de-duplicated", geo.profiles() == ["https://www.reddit.com/r/OneTapManager",
                                                     "https://www.instagram.com/onetapmanager"], geo.profiles())
main._LANDING_CACHE.clear()
org = ld_blocks(c.get("/").text)[0]["@graph"][0]
check("landing Organization lists the profiles", "https://www.reddit.com/r/OneTapManager" in org["sameAs"])
guide_org = next(g for g in ld_blocks(c.get("/about").text)[0]["@graph"] if g["@type"] == "Organization")
check("guide pages list them too", guide_org.get("sameAs") == geo.profiles())
check("llms.txt lists them", "https://www.reddit.com/r/OneTapManager" in c.get("/llms.txt").text)
os.environ.pop("BRAND_PROFILES")
main._LANDING_CACHE.clear()

print("\n== landing links the guides ==")
land = c.get("/").text
check("footer links every guide", all(f'href="{p}"' in land for p in geo.paths()))
check("points AI agents at llms.txt", 'href="/llms.txt"' in land)

print("\n== Bing and IndexNow ==")
check("/indexnow.txt 404s with no key", c.get("/indexnow.txt").status_code == 404)
os.environ["INDEXNOW_KEY"] = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
r = c.get("/indexnow.txt")
check("/indexnow.txt serves the key", r.status_code == 200 and r.text == os.environ["INDEXNOW_KEY"])
os.environ["INDEXNOW_KEY"] = "<script>"
check("a malformed key is not served", c.get("/indexnow.txt").status_code == 404)
os.environ.pop("INDEXNOW_KEY")
check("/BingSiteAuth.xml 404s with no code", c.get("/BingSiteAuth.xml").status_code == 404)
os.environ["BING_SITE_VERIFICATION"] = "ABCDEF0123456789ABCDEF0123456789"
r = c.get("/BingSiteAuth.xml")
check("/BingSiteAuth.xml serves the code",
      r.status_code == 200 and "<user>ABCDEF0123456789ABCDEF0123456789</user>" in r.text)
os.environ.pop("BING_SITE_VERIFICATION")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
