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
    check(f"{path} shows a last-updated date", f'<time datetime="{geo.UPDATED}">' in h)
    title = re.search(r"<title>(.*?)</title>", h, re.S).group(1)
    check(f"{path} title fits a search result", len(title.split(" | ")[0]) <= 70, title)
    check(f"{path} has a description",
          re.search(r'<meta name="description" content="[^"]{60,}"', h) is not None)
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
check("an unknown feature 404s", c.get("/features/nothing").status_code == 404)
check("an unknown question guide 404s", c.get("/guides/nothing").status_code == 404)
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

check("the imitation jewellery rate is hedged wherever it is stated",
      all("accountant" in c.get(p).text for p in ("/for/jewellery-sellers",
          "/guides/gst-rate-clothes-jewellery-perfume", "/features/gst-invoices")))
check("no page claims to show profit per product",
      "shows profit" not in c.get("/features/sales-analytics").text)
check("win-back is honest about WhatsApp", "click-to-chat" in c.get("/features/win-back").text)
check("no page calls itself the best",
      not any(re.search(r"\b(the best (app|software|tool|choice|option)|best (app|software) for|#1|number one)\b",
                        c.get(p).text, re.I) for p in geo.paths()))
check("stock reordering says it is Max", "Max plan" in c.get("/features/stock-reorder").text)

print("\n== reorder point calculator ==")
calc = "/guides/when-to-reorder-stock"
h = c.get(calc).text
check("the form works with no script", '<form class="calc" method="get"' in h)
check("the plain page is indexable", 'content="index, follow' in h)
h = c.get(calc + "?sold=4&lead=10").text
check("4 a day, 10 days, 20% = 48", "Reorder point: 48 units." in h,
      re.findall(r"Reorder point: \d+", h))
check("an answered page stays out of the index", 'content="noindex, follow"' in h)
check("canonical still points at the plain page", f'rel="canonical" href="http://testserver{calc}"' in h)
check("stock under the point says order now", "order now" in c.get(calc + "?sold=4&lead=10&stock=30").text)
check("stock above the point says when",
      "Order when it falls to 48" in c.get(calc + "?sold=4&lead=10&stock=200").text)
h = c.get(calc + "?sold=abc&lead=%3Cscript%3E").text
check("bad input asks again, and is not echoed",
      "plain numbers" in h and "<script>" not in h.split("</head>")[1])
check("the safety margin is honoured",
      "Reorder point: 60 units." in c.get(calc + "?sold=4&lead=10&buffer=50").text)

print("\n== Hindi page and hreflang ==")
hi = c.get("/hi").text
check("/hi is Hindi", '<html lang="hi-IN">' in hi)
main._LANDING_CACHE.clear()
land = c.get("/").text
for code in ("en-IN", "hi-IN", "x-default"):
    check(f"/hi carries hreflang {code}", f'hreflang="{code}"' in hi)
    check(f"/ carries hreflang {code}", f'hreflang="{code}"' in land)
check("the home page links the Hindi page", 'href="/hi"' in land)
check("only /hi carries hreflang among the guides",
      all('hreflang="hi-IN"' not in c.get(p).text for p in geo.paths() if p != "/hi"))

print("\n== the home page ==")
check("title names the category", "Shop Management App" in re.search(r"<title>(.*?)</title>", land).group(1))
check("one h1", land.count("<h1") == 1)
from backend.core import i18n  # noqa: E402
langs = set(re.findall(r'<div class="story" lang="([a-z]+)"', land))
check("example output only in languages the app writes", langs <= set(i18n.LANGUAGES), langs)
check("the nav links the guides", '<a href="/guides">Guides</a>' in land)
app_ld = next(g for g in ld_blocks(land)[0]["@graph"] if g["@type"] == "SoftwareApplication")
check("schema lists the features", len(app_ld.get("featureList", [])) >= 6)
check("every feature card links its page",
      all(f'class="f-more" href="{p}"' in land for p in geo.paths() if p.startswith("/features/")
          and p not in ("/features/review-analysis", "/features/online-store")))

print("\n== the new paths can never be a shop address ==")
for seg in ("guides", "about", "for", "compare", "features", "pricing", "hi"):
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
