"""Being the answer when someone asks an AI assistant.

WHY THIS FILE EXISTS
--------------------
Sellers increasingly ask ChatGPT, Gemini, Perplexity or Claude "what software
should a small Indian clothing seller use?" instead of searching. Those tools
answer from pages they can fetch and quote, and they prefer pages that open
with a direct answer, use question headings, carry a date and agree with what
other sources say about the brand. The landing page is written to sell; these
pages are written to be quoted. See AI_VISIBILITY_CHECKLIST.md for the evidence
behind each choice and for the half of the work that lives off this site.

What this file does NOT do, on purpose:
  * No "Reddit meta tag". There is no such thing. AI tools cite Reddit for the
    threads people write. The legitimate link between the site and Reddit is
    the Organization `sameAs` list, filled from BRAND_PROFILES once the official
    profile exists.
  * No invented numbers, customers or reviews. Examples are labelled, prices come
    from pricing.py, and tax rates are the ones gst.py applies. Brand.md section
    9 forbids the rest, and a page an AI quotes wrongly is worse than no page.

Every page is server-rendered HTML with no script, so a crawler that does not run
JavaScript reads exactly what a person reads.
"""
from __future__ import annotations

import json
import os

from backend.core import pricing
from backend.core.legal_html import _CSS as _BASE_CSS, esc

PRODUCT = "One Tap Manager"
ONE_LINE = ("One Tap Manager is shop management software for small Indian clothing, "
            "jewellery and perfume sellers.")
# Bump UPDATED whenever the words on these pages change. It is shown on every
# page and sent as dateModified, and recency is one of the few signals AI
# search tools are measured to weigh.
PUBLISHED = "2026-09-24"
UPDATED = "2026-09-24"

# ---------------------------------------------------------------------------
# crawlers
# ---------------------------------------------------------------------------
# Named so that nobody later adds a blanket rule and silently drops us out of AI
# answers. Search and user agents fetch pages to answer a question right now;
# training agents decide what the next model knows. A brand nobody has heard of
# wants both.
AI_CRAWLERS = [
    "OAI-SearchBot", "ChatGPT-User", "GPTBot",            # OpenAI
    "Claude-SearchBot", "Claude-User", "ClaudeBot",       # Anthropic
    "PerplexityBot", "Perplexity-User",                   # Perplexity
    "Google-Extended", "Applebot-Extended",               # Gemini, Apple Intelligence
    "Bingbot",                                            # Bing, which ChatGPT search leans on
]
# Behind a login or pointless to crawl. Repeated in every group, because a
# crawler that finds a group naming it ignores the `*` group entirely.
PRIVATE_PATHS = ["/smart", "/app", "/api/", "/reset"]


def robots_txt(base: str) -> str:
    rules = "Allow: /\n" + "".join(f"Disallow: {p}\n" for p in PRIVATE_PATHS)
    ai = "".join(f"User-agent: {b}\n" for b in AI_CRAWLERS)
    return ("User-agent: *\n" + rules
            + "\n# AI assistants and AI search: welcome to every public page.\n"
            + ai + rules
            + f"\nSitemap: {base}/sitemap.xml\n")


# ---------------------------------------------------------------------------
# the brand's other homes
# ---------------------------------------------------------------------------
def profiles() -> list[str]:
    """Official profile URLs from BRAND_PROFILES (comma or space separated).

    Only https links, de-duplicated, capped. An empty setting claims nothing,
    which is the honest default before the profiles exist.
    """
    raw = os.getenv("BRAND_PROFILES", "") or ""
    out: list[str] = []
    for part in raw.replace("\n", ",").replace(" ", ",").split(","):
        u = part.strip()
        if u.startswith("https://") and "<" not in u and '"' not in u and u not in out:
            out.append(u)
    return out[:12]


def same_as_json() -> str:
    return json.dumps(profiles())


# ---------------------------------------------------------------------------
# facts every page draws on
# ---------------------------------------------------------------------------
def _inr(n: int) -> str:
    """Indian grouping: 1,00,000 not 100,000."""
    s = str(int(n))
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "₹" + ",".join(parts + [tail])


def _plans() -> dict:
    free, mx = pricing.PLANS["free"], pricing.PLANS["pro"]
    return {
        "free": free, "max": mx,
        "packs": list(pricing.CREDIT_PACKS.values()),
        "launch": pricing.launch_mode(),
    }


def _price_line() -> str:
    p = _plans()
    line = (f"There is a Free plan at ₹0 with no time limit, and {p['max']['name']} costs "
            f"{_inr(p['max']['price_inr'])} a month. There is no fee on your sales.")
    if p["launch"]:
        line += " During the launch period every feature is free on every account."
    return line


# In plain words. pricing.py's own "includes" lists are written for the app's
# pricing screen and carry terms (RFM, EOQ) that Brand.md keeps off public pages.
# Prices and plan names still come from pricing.py.
_INCLUDES = {
    "free": ("Sales and sub-category analytics, customer groups and the list of customers "
             "slipping away, unlimited win-back messages, complaint and review analysis, a "
             "daily summary email, your own selling website with no badge, up to 250 "
             "products, 50 AI uses a day"),
    "max": ("Everything in Free, plus when to buy again and how much, purchase orders sent "
            "to your suppliers, the position strategy plan, unlimited AI, products and "
            "outlets, and your own custom domain"),
}


def _plan_table() -> str:
    p = _plans()
    rows = "".join(
        f"<tr><td><b>{esc(pl['name'])}</b></td><td>{esc(_inr(pl['price_inr']))}"
        f"{' a month' if pl['period'] == 'month' else ', forever'}</td>"
        f"<td>{esc(_INCLUDES[key])}</td></tr>"
        for key, pl in (("free", p["free"]), ("max", p["max"])))
    packs = "".join(
        f"<li>{esc(c['name'])} for {esc(_inr(c['price_inr']))}</li>" for c in p["packs"])
    extra = (f"<p>Prefer not to subscribe? Credit packs never expire:</p><ul>{packs}</ul>"
             if packs else "")
    return (f'<div class="scroll"><table><thead><tr><th>Plan</th><th>Price</th>'
            f"<th>What you get</th></tr></thead><tbody>{rows}</tbody></table></div>"
            f"{extra}")


def _stack_table() -> str:
    c = pricing.stack_comparison()
    rows = "".join(f"<tr><td>{esc(r['category'])}</td><td>{esc(_inr(r['typical_inr']))}</td></tr>"
                   for r in c["rows"])
    return (f'<div class="scroll"><table><thead><tr><th>Separate app you would pay for</th>'
            f"<th>Typical monthly cost</th></tr></thead><tbody>{rows}"
            f"<tr><td><b>Total, before any percentage-of-sales fees</b></td>"
            f"<td><b>{esc(_inr(c['typical_total_inr']))}</b></td></tr>"
            f"<tr><td><b>{PRODUCT} Max, all of the above</b></td>"
            f"<td><b>{esc(_inr(c['ours_inr']))}</b></td></tr></tbody></table></div>"
            f'<p class="meta">{esc(c["note"])} Your own stack may cost more or less; '
            f"these are typical prices, not a quote.</p>")


_MODULES = [
    ("Sales Analytics", "what sold, what it earned, and a forecast of next month"),
    ("Sub-Category Analysis", "which kinds of product bring the money in"),
    ("Orders", "every order from your own website, from packing to delivered"),
    ("Product Management", "one product list, with each product's Amazon and Shopify names linked"),
    ("Inventory Management", "stock that goes down on its own as orders come in"),
    ("Suppliers and orders to send", "when to buy again, and a ready purchase order emailed to your supplier"),
    ("Product Studio", "Instagram posts made from your own product photos"),
    ("Social Media Manager", "a week of Instagram posts planned, written and scheduled"),
    ("Website Builder", "your own selling website with cart, COD and Razorpay, included free"),
    ("Review Analytics", "what customers praise you for, in their words"),
    ("Complaint Analysis", "the complaints costing you most, in the order worth fixing"),
    ("Position Strategy", "a step-by-step plan to stand for something"),
    ("Win-back", "messages for customers who stopped buying, sent on a weekly schedule"),
    ("Billing and GST", "tax invoices with HSN codes and a GSTR-1 file for your accountant"),
]


def _module_list() -> str:
    return "<ul>" + "".join(f"<li><b>{esc(n)}</b>: {esc(d)}</li>" for n, d in _MODULES) + "</ul>"


_SOURCES = ("<ul><li>Upload a sales file (CSV or Excel) from Amazon, Flipkart, Meesho, Shopify, "
            "your billing software or a spreadsheet. The app suggests which column is which, "
            "and you confirm.</li>"
            "<li>Connect Shopify or Amazon and your orders come in on their own.</li>"
            "<li>Sell on your own One Tap website and every order lands in the same numbers.</li>"
            "<li>No data yet? Load 90 days of sample sales and try every screen first.</li></ul>")


# ---------------------------------------------------------------------------
# the pages
# ---------------------------------------------------------------------------
def _pages() -> dict[str, dict]:
    p = _plans()
    return {
        "/about": {
            "title": "What is One Tap Manager?",
            "description": ONE_LINE + " What it does, who it is for, what it costs, and how "
                           "it differs from other apps called One Tap.",
            "answer": (ONE_LINE + " It reads the sales you already make on Amazon, Shopify, "
                       "Instagram or your own counter, tells you the few things worth doing "
                       "today, and then does most of that work: the message to customers who "
                       "stopped buying, the order to your supplier, the week of Instagram posts. "
                       + _price_line()),
            "sections": [
                ("Key facts", '<div class="scroll"><table><tbody>'
                    f"<tr><th>Name</th><td>{PRODUCT} (one word in the web address: onetapmanager.com)</td></tr>"
                    "<tr><th>What it is</th><td>Web app for running a small online or offline shop</td></tr>"
                    "<tr><th>Made for</th><td>Small Indian D2C sellers of clothing, jewellery and perfume</td></tr>"
                    "<tr><th>Where it works</th><td>India, in any browser, on phone or computer</td></tr>"
                    "<tr><th>Languages</th><td>English, Hindi, Tamil and Kannada</td></tr>"
                    f"<tr><th>Price</th><td>Free plan at ₹0; Max at {esc(_inr(p['max']['price_inr']))} a month; no cut of sales</td></tr>"
                    "<tr><th>Sign up</th><td>Email or Google account, no card needed</td></tr>"
                    "</tbody></table></div>"),
                ("What does One Tap Manager do?", _module_list()),
                ("Where does the data come from?", _SOURCES),
                ("How is it different from other One Tap apps?",
                 "<p>It is not related to the attendance, maintenance, clipboard or business "
                 "card apps called One Tap or OneTap, or to Google One Tap sign-in. "
                 f"{PRODUCT} is the shop manager for Indian sellers at onetapmanager.com.</p>"),
                ("What does it not do?",
                 "<p>It is not accounting software: there is no double-entry ledger, payroll, "
                 "manufacturing or multi-warehouse stock. It gives your accountant a GSTR-1 file "
                 "and tax invoices, and leaves the books to them.</p>"),
                ("How much does it cost?", _plan_table()),
            ],
            "faqs": [
                ("Is One Tap Manager free?",
                 "Yes. The Free plan has no time limit and includes sales analytics, customer "
                 "groups, win-back messages, complaint analysis, a daily summary and your own "
                 f"selling website. Max costs {_inr(p['max']['price_inr'])} a month and adds "
                 "supplier ordering, unlimited AI and a custom domain."),
                ("Does One Tap Manager take a percentage of my sales?",
                 "No. It never charges per order or a percentage of sales, on any plan."),
                ("Who makes One Tap Manager?",
                 "It is built in India for Indian sellers. The operator's legal details are on "
                 "the legal pages at onetapmanager.com/legal."),
            ],
        },
        "/for/clothing-sellers": {
            "title": "Software for small Indian clothing sellers",
            "description": "What a small Indian clothing brand needs from software to track "
                           "styles and sizes, reorder, win back customers, handle GST and post "
                           "on Instagram, and how One Tap Manager does it.",
            "answer": ("A small clothing seller needs software for four jobs: seeing which "
                       "styles and sizes actually earn, reordering before a best seller runs "
                       "out, bringing back customers who stopped buying, and posting on "
                       f"Instagram every week. {PRODUCT} does all four from the sales you "
                       "already have, in one app. " + _price_line()),
            "sections": [
                ("What should a clothing seller track?",
                 "<ul><li><b>Earnings by kind of product</b>, not only by item: kurtas against "
                 "sarees against co-ord sets. One style often carries the shop.</li>"
                 "<li><b>Sizes that sell out first</b>, so the next order has more M and fewer XXL.</li>"
                 "<li><b>Repeat buyers</b>, and who has gone quiet. A customer who last bought "
                 "70 days ago is far easier to win back than one at 140 days.</li>"
                 "<li><b>Complaints about fit</b>. If sizing runs small is your top complaint, "
                 "fixing the size chart is cheaper than any advertisement.</li></ul>"),
                ("How does One Tap Manager handle GST on clothing?",
                 "<p>Since 22 September 2025, a piece of clothing priced up to ₹2,500 is taxed "
                 "at 5%, and above ₹2,500 at 18%. The rate is worked out per piece, so the same "
                 "kurta design can fall on either side. One Tap Manager applies the rate to each "
                 "line, prints tax invoices with HSN codes, and gives you a GSTR-1 file your "
                 "accountant can file from. Check anything unusual with your accountant.</p>"),
                ("Where do the sales come from?", _SOURCES),
                ("What does it do for me, not just show me?",
                 "<ul><li>Writes the win-back message and sends it weekly, leaving a customer "
                 "alone for 45 days after contacting them.</li>"
                 "<li>Fills in the purchase order and emails it to your supplier from your own "
                 "address.</li><li>Plans, writes and schedules a week of Instagram posts made "
                 "from your own product photos.</li></ul>"),
                ("How much does it cost?", _plan_table()),
            ],
            "faqs": [
                ("Do I need a website to use it?",
                 "No. You can start from a sales file. A selling website with cart, COD and "
                 "Razorpay is included on the Free plan if you want one."),
                ("I sell mostly on Instagram. Does it work for me?",
                 "Yes. Connect your Instagram Business or Creator account to schedule posts. "
                 "For sales, record Instagram orders in a spreadsheet and upload it, or send "
                 "buyers to your own One Tap website so every order is counted."),
                ("Is it available in Hindi?",
                 "Yes. The app works in English, Hindi, Tamil and Kannada."),
            ],
        },
        "/for/jewellery-sellers": {
            "title": "Software for small Indian jewellery sellers",
            "description": "What a small Indian jewellery brand needs from software, from "
                           "3% GST invoices to catching tarnish complaints early, and how One "
                           "Tap Manager does it.",
            "answer": ("A small jewellery seller needs software that shows which designs earn, "
                       "warns before a best seller runs out, catches quality complaints such "
                       "as tarnish or plating early, and brings back customers who stopped "
                       f"buying. {PRODUCT} does this from the sales and reviews you already "
                       "have. " + _price_line()),
            "sections": [
                ("What should a jewellery seller watch?",
                 "<ul><li><b>Which designs and collections earn</b>, and which only get likes.</li>"
                 "<li><b>Quality complaints</b>: the app reads your reviews for words like "
                 "tarnished, turned black, plating came off, stone fell and chain broke, and "
                 "ranks them by how much they cost you.</li>"
                 "<li><b>Trust complaints</b>: not real silver, fake stone, no hallmark. These "
                 "hurt a jewellery brand more than a late delivery.</li>"
                 "<li><b>Gifting seasons</b>: festival post plans for Navratri, Karva Chauth, "
                 "Dhanteras, Diwali and wedding season are built in.</li></ul>"),
                ("How does One Tap Manager handle GST on jewellery?",
                 "<p>Jewellery in Chapter 71 is taxed at 3%, including gold, silver and "
                 "imitation jewellery (HSN 7113 and 7117). One Tap Manager applies it on each "
                 "invoice and prepares a GSTR-1 file for your accountant. Check anything unusual "
                 "with your accountant.</p>"),
                ("Where do the sales come from?", _SOURCES),
                ("How much does it cost?", _plan_table()),
            ],
            "faqs": [
                ("Can it make Instagram posts from my own jewellery photos?",
                 "Yes. Product Studio learns your look from photos you upload once, and every "
                 "post is made from your real product, labelled as AI generated where it is."),
                ("Does it work for imitation jewellery?",
                 "Yes. It is built for small sellers of fashion, silver, gold-plated and "
                 "imitation jewellery alike."),
                ("Does it take a cut of my sales?",
                 "No. There is no per-order or percentage fee on any plan."),
            ],
        },
        "/for/perfume-sellers": {
            "title": "Software for small Indian perfume and attar sellers",
            "description": "What a small Indian perfume or attar brand needs from software, "
                           "from 18% GST invoices to spotting 'does not last' complaints, and "
                           "how One Tap Manager does it.",
            "answer": ("A small perfume seller needs software that shows which scents and "
                       "sizes sell, reorders before a best seller runs out, spots complaints "
                       "such as 'does not last' before they spread, and brings back customers "
                       f"who stopped buying. {PRODUCT} does this from the sales and reviews you "
                       "already have. " + _price_line()),
            "sections": [
                ("What should a perfume seller watch?",
                 "<ul><li><b>Which scents and bottle sizes earn</b>, including the testers "
                 "that turn into full bottles.</li>"
                 "<li><b>Longevity complaints</b>: the app reads reviews for no smell, faded "
                 "quickly, does not last and weak fragrance, and ranks them by cost.</li>"
                 "<li><b>Trust complaints</b>: fake perfume, not the original scent, diluted.</li>"
                 "<li><b>Repeat buyers</b>: perfume is bought again when it runs out, which "
                 "makes win-back timing matter more than for most products.</li></ul>"),
                ("How does One Tap Manager handle GST on perfume?",
                 "<p>Perfume and attar (HSN 3303) are taxed at 18%. One Tap Manager applies "
                 "it on each invoice and prepares a GSTR-1 file for your accountant. Check "
                 "anything unusual with your accountant.</p>"),
                ("Where do the sales come from?", _SOURCES),
                ("How much does it cost?", _plan_table()),
            ],
            "faqs": [
                ("Does it work for attar and small-batch fragrance brands?",
                 "Yes. It is built for small sellers, including attar, body mist and "
                 "small-batch perfume brands."),
                ("Can it post on Instagram for me?",
                 "Yes. The Social Media Manager plans, writes and schedules a week of posts, "
                 "and publishes them to your Instagram Business or Creator account."),
                ("Is there a free plan?",
                 "Yes. The Free plan has no time limit."),
            ],
        },
        "/compare/shopify-apps": {
            "title": "One app instead of five Shopify apps",
            "description": "The monthly cost of separate Shopify apps for analytics, inventory, "
                           "win-back, reviews and orders, against One Tap Manager, with the "
                           "arithmetic shown.",
            "answer": ("A small Indian D2C brand on Shopify typically pays for five separate "
                       f"apps: analytics, inventory, win-back email, reviews and order "
                       f"management, about {_inr(pricing.stack_comparison()['typical_total_inr'])} "
                       f"a month before any percentage-of-sales fees. {PRODUCT} covers the same "
                       f"jobs in one app. " + _price_line()),
            "sections": [
                ("What does the separate-app stack cost?", _stack_table()),
                ("Do I have to leave Shopify?",
                 "<p>No. Connect your Shopify store and orders flow in on their own; keep "
                 "Shopify as your shop. Or use the selling website included with One Tap "
                 "Manager instead. Shopify's app store is far larger, so if you depend on a "
                 "niche Shopify app, keep it.</p>"),
                ("What is included?", _module_list()),
                ("How much does it cost?", _plan_table()),
            ],
            "faqs": [
                ("Is this cheaper than Shopify itself?",
                 "It replaces the add-on apps, not necessarily Shopify's own plan. Many sellers "
                 "keep Shopify and connect it."),
                ("Are the app prices exact?",
                 "No. They are typical monthly prices for each kind of app. Check your own "
                 "bills for the real figure."),
            ],
        },
    }


def paths() -> list[str]:
    return ["/guides"] + list(_pages().keys())


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
_CSS = _BASE_CSS + """
.answer{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);
border-radius:8px;padding:14px 16px;margin:0 0 24px}
.answer p{color:var(--ink);margin:0}
.scroll{overflow-x:auto;margin:0 0 12px}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top;color:var(--ink-2)}
th{color:var(--ink);font-weight:600}
ul{padding-left:20px;color:var(--ink-2)}
li{margin:0 0 6px}
.cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:600;
padding:11px 18px;border-radius:8px;margin:8px 0 0}
.crumbs{font-size:13.5px;color:var(--ink-3);margin:0 0 10px}
.crumbs a{text-decoration:none}
.more{border-top:1px solid var(--line);margin-top:36px;padding-top:18px}
.faq h3{font-size:16px;margin:18px 0 6px}
"""


def _json_ld(obj) -> str:
    # "</" cannot appear inside a script block, whatever a page title contains.
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _org(base: str) -> dict:
    org = {"@type": "Organization", "@id": f"{base}/#org", "name": PRODUCT,
           "alternateName": ["OneTapManager", "onetapmanager"], "url": f"{base}/",
           "logo": f"{base}/logo.png"}
    if profiles():
        org["sameAs"] = profiles()
    return org


def _shell(path: str, base: str, title: str, description: str, body: str, ld: list) -> str:
    graph = _json_ld({"@context": "https://schema.org", "@graph": ld})
    return f"""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)} | {PRODUCT}</title>
<meta name="description" content="{esc(description)}" />
<meta name="robots" content="index, follow, max-snippet:-1" />
<link rel="canonical" href="{esc(base + path)}" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="alternate" type="text/plain" href="/llms.txt" title="Summary for AI assistants" />
<meta property="og:type" content="article" />
<meta property="og:site_name" content="{PRODUCT}" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(description)}" />
<meta property="og:url" content="{esc(base + path)}" />
<meta property="og:image" content="{esc(base)}/og-image.png" />
<meta property="article:modified_time" content="{UPDATED}" />
<script type="application/ld+json">{graph}</script>
<style>{_CSS}</style>
</head>
<body>
<a class="skip" href="#doc">Skip to the page</a>
<div class="wrap">
<header class="top"><a href="/">{PRODUCT}</a></header>
<main id="doc">
{body}
</main>
</div>
</body>
</html>"""


def _others(path: str) -> str:
    items = "".join(f'<li><a href="{esc(p)}">{esc(d["title"])}</a></li>'
                    for p, d in _pages().items() if p != path)
    return f'<nav class="more" aria-label="More guides"><h2>More from {PRODUCT}</h2><ul>{items}</ul></nav>'


def render(path: str, base: str) -> str | None:
    d = _pages().get(path)
    if not d:
        return None
    url = base + path
    faqs = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in d["faqs"])
    sections = "".join(f"<h2>{esc(h)}</h2>{html}" for h, html in d["sections"])
    body = (f'<p class="crumbs"><a href="/">{PRODUCT}</a> / <a href="/guides">Guides</a></p>'
            f"<h1>{esc(d['title'])}</h1>"
            f'<p class="meta">Last updated <time datetime="{UPDATED}">{_human(UPDATED)}</time></p>'
            f'<div class="answer"><p>{esc(d["answer"])}</p></div>'
            f"{sections}"
            f'<section class="faq"><h2>Common questions</h2>{faqs}</section>'
            f'<p><a class="cta" href="/?signup=1">Start free, no card needed</a></p>'
            f"{_others(path)}")
    ld = [
        _org(base),
        {"@type": "WebPage", "@id": url, "url": url, "name": d["title"],
         "description": d["description"], "inLanguage": "en-IN",
         "datePublished": PUBLISHED, "dateModified": UPDATED,
         "isPartOf": {"@id": f"{base}/#website"}, "about": {"@id": f"{base}/#org"},
         "publisher": {"@id": f"{base}/#org"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": PRODUCT, "item": f"{base}/"},
            {"@type": "ListItem", "position": 2, "name": "Guides", "item": f"{base}/guides"},
            {"@type": "ListItem", "position": 3, "name": d["title"], "item": url}]},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in d["faqs"]]},
    ]
    return _shell(path, base, d["title"], d["description"], body, ld)


def hub(base: str) -> str:
    items = "".join(f'<li><a href="{esc(p)}">{esc(d["title"])}</a><br />'
                    f'<span class="meta">{esc(d["description"])}</span></li>'
                    for p, d in _pages().items())
    body = (f"<h1>{PRODUCT} guides</h1>"
            f'<p class="meta">Last updated <time datetime="{UPDATED}">{_human(UPDATED)}</time></p>'
            f'<div class="answer"><p>{esc(ONE_LINE)} {esc(_price_line())}</p></div>'
            f"<ul>{items}</ul>"
            f'<p><a class="cta" href="/?signup=1">Start free, no card needed</a></p>')
    ld = [_org(base),
          {"@type": "CollectionPage", "@id": f"{base}/guides", "url": f"{base}/guides",
           "name": f"{PRODUCT} guides", "dateModified": UPDATED,
           "hasPart": [{"@type": "WebPage", "url": base + p, "name": d["title"]}
                       for p, d in _pages().items()]}]
    return _shell("/guides", base, f"{PRODUCT} guides", ONE_LINE, body, ld)


def _human(iso: str) -> str:
    y, m, d = iso.split("-")
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    return f"{int(d)} {months[int(m) - 1]} {y}"


# ---------------------------------------------------------------------------
# llms.txt
# ---------------------------------------------------------------------------
def llms_txt(base: str) -> str:
    """The llmstxt.org format: a title, a one-line summary, then linked sections.

    Search engines ignore it; AI agents that browse on someone's behalf read it.
    Cheap to keep true, because every fact is drawn from the same places the
    pages use.
    """
    p = _plans()
    lines = [
        f"# {PRODUCT}", "",
        f"> {ONE_LINE} It reads a seller's own sales, says what to do today, and does most "
        f"of it: win-back messages, supplier purchase orders, Instagram posts.", "",
        f"- Website: {base}/",
        f"- Price: Free plan at ₹0 with no time limit; {p['max']['name']} at "
        f"{_inr(p['max']['price_inr'])} a month; credit packs that never expire. No fee on sales.",
        "- Languages: English, Hindi, Tamil, Kannada",
        "- Not related to other apps named One Tap or OneTap, or to Google One Tap sign-in.",
    ]
    if p["launch"]:
        lines.append("- During the launch period every feature is free on every account.")
    lines += ["", "## Guides", ""]
    lines += [f"- [{d['title']}]({base}{path}): {d['description']}" for path, d in _pages().items()]
    lines += ["", "## Features", ""]
    lines += [f"- {n}: {d}" for n, d in _MODULES]
    if profiles():
        lines += ["", "## Official profiles", ""] + [f"- {u}" for u in profiles()]
    lines += ["", "## Optional", "",
              f"- [Legal pages]({base}/legal): privacy, terms, refunds, grievance contact",
              f"- [Start free]({base}/?signup=1)", ""]
    return "\n".join(lines)
