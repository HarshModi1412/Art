"""Being the answer when someone searches, or asks an AI assistant.

WHY THIS FILE EXISTS
--------------------
Sellers increasingly ask ChatGPT, Gemini, Perplexity or Claude "what software
should a small Indian clothing seller use?" instead of searching. Those tools
answer from pages they can fetch and quote, and they prefer pages that open
with a direct answer, use question headings, carry a date and agree with what
other sources say about the brand. The landing page is written to sell; these
pages are written to be quoted. See AI_VISIBILITY_CHECKLIST.md for the evidence
behind each choice and for the half of the work that lives off this site.

THE SHAPE OF THE SITE
---------------------
The landing page is one long page, and Google ranks a URL, not an #anchor. So
every job the product does gets its own URL, each aimed at the searches a
seller actually types (SEO_KEYWORDS.md maps keyword to page):

  * /features/<job>   one page per feature: "low stock alert app", "customer
                      win-back WhatsApp", "GST invoice for online seller"
  * /for/<seller>     one page per kind of seller: boutiques, imitation
                      jewellery, attar, Instagram sellers
  * /compare/<other>  the honest comparison a buyer is already making
  * /guides/<topic>   the question a seller asks before they know we exist
  * /pricing, /about  the branded questions
  * /hi               the Hindi page, linked to / by hreflang

Each page has a short <title> aimed at the search (seo_title) and a longer H1
written for the person who landed.

What this file does NOT do, on purpose:
  * No "Reddit meta tag". There is no such thing. AI tools cite Reddit for the
    threads people write. The legitimate link between the site and Reddit is
    the Organization `sameAs` list, filled from BRAND_PROFILES once the official
    profile exists.
  * No invented numbers, customers or reviews, and no "best". Examples are
    labelled, prices come from pricing.py, and tax rates are the ones gst.py
    applies. Brand.md section 9 forbids the rest, and a page an AI quotes wrongly
    is worse than no page.
  * No claim the app cannot back. It has no cost price, so no page says it
    shows profit per product; WhatsApp sends through a click-to-chat link until
    a provider is connected, and the pages say so.

Every page is server-rendered HTML with no script, so a crawler that does not run
JavaScript reads exactly what a person reads. The reorder calculator is a plain
GET form the server answers, for the same reason.
"""
from __future__ import annotations

import json
import math
import os
import re

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


# The English and Hindi home pages point at each other. hreflang only counts
# when both sides carry the same set, so both read it from here.
HREFLANG = [("en-IN", "/"), ("hi-IN", "/hi"), ("x-default", "/")]


def hreflang_links(base: str) -> str:
    return "".join(f'<link rel="alternate" hreflang="{h}" href="{esc(base + p)}" />\n'
                   for h, p in HREFLANG)


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


def _max_price() -> str:
    return _inr(_plans()["max"]["price_inr"])


def _price_line() -> str:
    p = _plans()
    line = (f"There is a Free plan at ₹0 with no time limit, and {p['max']['name']} costs "
            f"{_max_price()} a month. There is no fee on your sales.")
    if p["launch"]:
        line += " During the launch period every feature is free on every account."
    return line


def _price_line_hi() -> str:
    line = (f"Free प्लान ₹0 का है और इसकी कोई समय-सीमा नहीं है। Max प्लान {_max_price()} "
            "महीना है। आपकी बिक्री पर कोई कमीशन नहीं लगता।")
    if _plans()["launch"]:
        line += " लॉन्च के दौरान हर खाते पर हर सुविधा मुफ़्त है।"
    return line


def _max_only() -> str:
    """How a Max-only feature is described, honest about launch mode."""
    s = f"on the Max plan at {_max_price()} a month"
    if _plans()["launch"]:
        s += " (free on every account during the launch period)"
    return s


# In plain words. pricing.py's own "includes" lists are written for the app's
# pricing screen and carry terms (RFM, EOQ) that Brand.md keeps off public pages.
# Prices and plan names still come from pricing.py.
_INCLUDES = {
    "free": ("Sales and sub-category analytics, customer groups and the list of customers "
             "slipping away, unlimited win-back messages, complaint and review analysis, GST "
             "invoices, a daily summary email, your own selling website with no badge, up to "
             "250 products, 50 AI uses a day"),
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
            f"{extra}"
            f'<p><a href="/pricing">Full pricing and what each plan includes</a></p>')


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


# name, what it does, the page that explains it (or "")
_MODULES = [
    ("Sales Analytics", "what sold, what it earned, and a forecast of next month",
     "/features/sales-analytics"),
    ("Sub-Category Analysis", "which kinds of product bring the money in",
     "/features/sales-analytics"),
    ("Orders", "every order from your own website, from packing to delivered",
     "/features/online-store"),
    ("Product Management", "one product list, with each product's Amazon and Shopify names linked, "
     "and stock by size and colour", ""),
    ("Inventory Management", "stock that goes down on its own as orders come in",
     "/features/stock-reorder"),
    ("Suppliers and orders to send", "when to buy again, and a ready purchase order emailed to your supplier",
     "/features/stock-reorder"),
    ("Product Studio", "Instagram posts made from your own product photos",
     "/features/ai-product-photos"),
    ("Social Media Manager", "a week of Instagram posts planned, written and scheduled",
     "/features/instagram-planner"),
    ("Website Builder", "your own selling website with cart, COD and Razorpay, included free",
     "/features/online-store"),
    ("Review Analytics", "what customers praise you for, in their words",
     "/features/review-analysis"),
    ("Complaint Analysis", "the complaints costing you most, in the order worth fixing",
     "/features/review-analysis"),
    ("Position Strategy", "a step-by-step plan to stand for something", ""),
    ("Win-back", "messages for customers who stopped buying, sent on a weekly schedule",
     "/features/win-back"),
    ("Billing and GST", "tax invoices with HSN codes and a GSTR-1 file for your accountant",
     "/features/gst-invoices"),
]


def _module_list() -> str:
    def item(n, d, href):
        name = f'<a href="{href}">{esc(n)}</a>' if href else esc(n)
        return f"<li><b>{name}</b>: {esc(d)}</li>"
    return "<ul>" + "".join(item(*m) for m in _MODULES) + "</ul>"


_SOURCES = ("<ul><li>Upload a sales file (CSV or Excel) from Amazon, Flipkart, Meesho, Shopify, "
            "your billing software or a spreadsheet. The app suggests which column is which, "
            "and you confirm.</li>"
            "<li>Connect Shopify or Amazon and your orders come in on their own.</li>"
            "<li>Sell on your own One Tap website and every order lands in the same numbers.</li>"
            "<li>No data yet? Load 90 days of sample sales and try every screen first.</li></ul>")

_VARIANTS = ("<p>A product can carry up to two options, usually size and colour, and every "
             "combination is its own record with its own stock count, SKU and, if you want, its "
             "own price. One shirt in four sizes and three colours is twelve things to count, and "
             "the app counts all twelve. An order on your One Tap website takes the right one out "
             "of stock on its own.</p>")

# GST as gst.py applies it. Imitation jewellery sits on gst.NEEDS_CA_REVIEW, so
# every page that states it says the same careful thing.
_GST_TABLE = ('<div class="scroll"><table><thead><tr><th>What you sell</th><th>HSN</th>'
              "<th>GST rate</th><th>Note</th></tr></thead><tbody>"
              "<tr><td>Clothing, priced up to ₹2,500 a piece</td><td>61, 62, 63</td><td>5%</td>"
              "<td>Decided per piece, not per bill</td></tr>"
              "<tr><td>Clothing, priced above ₹2,500 a piece</td><td>61, 62, 63</td><td>18%</td>"
              "<td>Was 12% before 22 September 2025</td></tr>"
              "<tr><td>Footwear</td><td>64</td><td>5% up to ₹2,500 a pair, 18% above</td>"
              "<td>Decided per pair</td></tr>"
              "<tr><td>Gold and silver jewellery</td><td>7113</td><td>3%</td><td>Unchanged in 2025</td></tr>"
              "<tr><td>Imitation (artificial) jewellery</td><td>7117</td><td>3%</td>"
              "<td>Published sources have disagreed; confirm with your accountant</td></tr>"
              "<tr><td>Perfume, attar, body mist</td><td>3303</td><td>18%</td><td></td></tr>"
              "<tr><td>Kajal, kumkum, bindi, sindur, alta</td><td>3304</td><td>5%</td>"
              "<td>Other make-up in 3304 is 18%</td></tr>"
              "<tr><td>Hair oil, shampoo, mehendi</td><td>3305</td><td>5%</td>"
              "<td>Other hair products in 3305 are 18%</td></tr>"
              "</tbody></table></div>")


# ---------------------------------------------------------------------------
# the reorder point calculator
# ---------------------------------------------------------------------------
def _num(params: dict, key: str, lo: float, hi: float) -> float | None:
    raw = (params.get(key) or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if lo <= v <= hi and math.isfinite(v) else None


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _reorder_tool(params: dict) -> str:
    """A GET form the server answers: works with no script, and the maths shown."""
    sold = _num(params, "sold", 0.01, 100000)
    lead = _num(params, "lead", 1, 365)
    buf = _num(params, "buffer", 0, 200)
    stock = _num(params, "stock", 0, 10000000)
    if buf is None:
        buf = 20.0

    def field(name, label, value, hint):
        v = "" if value is None else _fmt(value)
        return (f'<label for="rp-{name}">{label}</label>'
                f'<input id="rp-{name}" name="{name}" inputmode="decimal" value="{esc(v)}" />'
                f'<span class="hint">{hint}</span>')

    form = ('<form class="calc" method="get" action="/guides/when-to-reorder-stock#reorder-point-calculator">'
            + field("sold", "Units sold in an average day", sold, "Last 30 days of sales divided by 30")
            + field("lead", "Days your supplier takes to deliver", lead, "From placing the order to stock on your shelf")
            + field("buffer", "Safety margin, %", buf, "20% is a sensible start; raise it before festivals")
            + field("stock", "Stock you have now (optional)", stock, "Leave empty to see only the reorder point")
            + '<button type="submit">Work it out</button></form>')

    if params and (sold is None or lead is None):
        return form + ('<p class="result">Enter how many you sell in a day and how many days '
                       "your supplier takes, as plain numbers.</p>")
    if sold is None or lead is None:
        return form

    point = math.ceil(sold * lead * (1 + buf / 100))
    out = (f'<div class="result"><p><b>Reorder point: {point} units.</b> '
           f"{_fmt(sold)} a day × {_fmt(lead)} days × {1 + buf / 100:g} "
           f"(a {_fmt(buf)}% margin) = {sold * lead * (1 + buf / 100):.1f}, rounded up.</p>")
    if stock is not None:
        days = stock / sold
        if stock <= point:
            out += (f"<p>You have {_fmt(stock)}, which lasts about {days:.0f} days. That is at or "
                    "below the reorder point: <b>order now</b>.</p>")
        else:
            out += (f"<p>You have {_fmt(stock)}, about {days:.0f} days of sales. Order when it "
                    f"falls to {point}, roughly {max(0, (stock - point) / sold):.0f} days from now "
                    "at today's pace.</p>")
    return form + out + "</div>"


# ---------------------------------------------------------------------------
# the pages
# ---------------------------------------------------------------------------
# kind -> (hub anchor, hub heading, sitemap priority)
KINDS = {
    "product": ("about", "About and pricing", "0.8"),
    "feature": ("features", "What it does", "0.8"),
    "for": ("sellers", "Who it is for", "0.8"),
    "compare": ("compare", "Comparisons", "0.7"),
    "guide": ("guides", "Guides for sellers", "0.7"),
    "hi": ("hindi", "हिंदी में", "0.8"),
}


def _core_pages() -> dict[str, dict]:
    p = _plans()
    return {
        "/about": {
            "kind": "product",
            "title": "What is One Tap Manager?",
            "seo_title": "What is One Tap Manager? Shop manager app for Indian sellers",
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
                    f"<tr><th>Price</th><td>Free plan at ₹0; Max at {esc(_max_price())} a month; no cut of sales</td></tr>"
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
                 f"selling website. Max costs {_max_price()} a month and adds "
                 "supplier ordering, unlimited AI and a custom domain."),
                ("Does One Tap Manager take a percentage of my sales?",
                 "No. It never charges per order or a percentage of sales, on any plan."),
                ("Does One Tap Manager have reviews?",
                 "Not yet. It is new, and it will not publish reviews or customer numbers it does "
                 "not have. Every figure on this site is labelled as a worked example."),
                ("Who makes One Tap Manager?",
                 "It is built in India for Indian sellers. The operator's legal details are on "
                 "the legal pages at onetapmanager.com/legal."),
            ],
        },
        "/pricing": {
            "kind": "product",
            "title": f"One Tap Manager pricing: a Free plan, and Max at {_max_price()} a month",
            "seo_title": f"One Tap Manager Pricing: Free Plan, Max at {_max_price()}/month",
            "description": f"One Tap Manager costs ₹0 on the Free plan and {_max_price()} a month "
                           "on Max, with credit packs that never expire and no commission on "
                           "your sales.",
            "answer": (_price_line() + " You start without a card, on the Free plan, and only "
                       "pay if you want what Max adds: supplier ordering, unlimited AI and your "
                       "own domain. Credit packs that never expire cover a busy month without a "
                       "subscription."),
            "sections": [
                ("What does each plan include?", _plan_table()),
                ("What is free forever?",
                 "<ul><li>Sales analytics and sub-category analysis</li>"
                 "<li>Customer groups and the list of customers slipping away</li>"
                 "<li>Win-back messages, unlimited, with the Excel file</li>"
                 "<li>Complaint and review analysis with the fix-first plan</li>"
                 "<li>GST tax invoices and the GSTR-1 file</li>"
                 "<li>The daily summary by email</li>"
                 "<li>Your own selling website, no badge, up to 250 products</li>"
                 "<li>50 AI uses a day</li></ul>"
                 "<p>These stay free when the launch period ends. Only the Max rows move behind "
                 "the subscription.</p>"),
                ("Why is there no commission?",
                 "<p>Most selling software takes a slice of every order, through a transaction "
                 "fee or a percentage. Sellers already pay that to marketplaces and payment "
                 "gateways, and it grows exactly when the shop does well. One Tap Manager charges "
                 "a flat price, or nothing, and never a share of sales. Razorpay, if you use it on "
                 "your website, charges its own payment fee; we add nothing on top.</p>"),
                ("What does it replace?", _stack_table()),
                ("What happens if I stop paying?",
                 "<p>Moving from Max back to Free never deletes anything. Your data, products, "
                 "invoices and website stay; only the Max actions, such as sending a new purchase "
                 "order, stop until you upgrade again or use credits. See the "
                 '<a href="/legal/refunds">refund policy</a> for payments.</p>'),
            ],
            "faqs": [
                ("Is One Tap Manager really free?",
                 "Yes. The Free plan has no time limit and needs no card. It includes analytics, "
                 "win-back messages, complaint analysis, GST invoices and your own website."),
                ("How much is the Max plan?",
                 f"{_max_price()} a month, flat, per outlet. It adds stock reordering, purchase "
                 "orders to suppliers, unlimited AI and products, and a custom domain."),
                ("Do you take a percentage of my sales?",
                 "No. Never, on any plan, and no per-order fee."),
                ("Can I pay only when I need something?",
                 "Yes. Credit packs never expire, and a credit can buy an extra AI use or a "
                 "purchase order without a subscription."),
            ],
            "schema": _software_schema,
        },
    }


def _feature_pages() -> dict[str, dict]:
    return {
        "/features/sales-analytics": {
            "kind": "feature",
            "title": "Sales analytics for small shops, from the sales file you already have",
            "seo_title": "Sales Analytics Software for Small Business in India",
            "description": "Upload a sales CSV or Excel file and see what sold, what earned, which "
                           "days are slow and a forecast of next month, in plain sentences. Free "
                           "for small Indian sellers.",
            "answer": ("One Tap Manager turns a sales file you already have into plain answers: "
                       "what sold, what earned the money, which weekday is quiet, who your repeat "
                       "buyers are, and what next month looks like. Upload a CSV or Excel export "
                       "from Amazon, Flipkart, Meesho, Shopify, your billing software or a "
                       "spreadsheet, confirm which column is which, and the first answers appear "
                       "in about two minutes. Sales analytics is on the Free plan, with no time "
                       "limit."),
            "sections": [
                ("What does it show you?",
                 "<ul><li><b>The totals</b>: money in, orders, customers and the average order, "
                 "for any dates you pick.</li>"
                 "<li><b>The trend</b>: month by month, your best and weakest month, and a "
                 "forecast of next month.</li>"
                 "<li><b>What carries the shop</b>: your top products and how much of the money "
                 "the top three bring in.</li>"
                 "<li><b>Kinds of product</b>: kurtas against sarees against co-ord sets, or rings "
                 "against earrings, so you see which line is growing.</li>"
                 "<li><b>Slow days</b>: which weekday runs below your average, and by how much.</li>"
                 '<li><b>Customers</b>: who buys often, who spends most, and who has gone quiet. '
                 'The quiet ones feed <a href="/features/win-back">win-back</a>.</li></ul>'),
                ("How do I analyse sales from an Excel or CSV file?",
                 "<ol><li>Export your sales from wherever you record them. One row per sale or per "
                 "line of a bill is ideal.</li>"
                 "<li>Upload it. There is no template to copy your data into.</li>"
                 "<li>The app suggests which column is the date, the amount, the customer, the "
                 "product, the category and the quantity. Confirm or correct any it had to "
                 "guess.</li>"
                 "<li>Read the findings, written as sentences with the next step attached.</li></ol>"
                 '<p>Doing it by hand first? The <a href="/guides/analyse-sales-excel">guide to '
                 "analysing sales in Excel</a> shows the five tables worth building.</p>"),
                ("What is the morning summary?",
                 "<p>Every morning the app picks the three things worth your time today, such as "
                 "stock about to run out, customers slipping away or a complaint getting louder, "
                 "and sends them as a daily summary by email, and on WhatsApp once you connect it. "
                 "The summary and the home screen come from the same place, so they never "
                 "disagree.</p>"),
                ("Can I ask questions about my own numbers?",
                 "<p>Yes. The AI analyst answers questions about your own sales in plain words, "
                 "such as which product fell most since last month. The Free plan includes 50 AI "
                 "uses a day; Max is unlimited.</p>"),
                ("What does it not do?",
                 "<p>It does not know what each product cost you, so it reports sales, not profit "
                 "per product. If sales are rising and profit is not, the guide to "
                 '<a href="/guides/sales-up-profit-down">why sales are up but profit is down</a> '
                 "shows how to check.</p>"),
            ],
            "faqs": [
                ("Is the sales analytics free?",
                 "Yes. Sales and sub-category analytics are on the Free plan with no time limit."),
                ("Which files can I upload?",
                 "CSV or Excel files from Amazon, Flipkart, Meesho, Shopify, billing software or "
                 "your own spreadsheet. The app works out which column is which."),
                ("Do I have to connect my store?",
                 "No. A file is enough. Shopify and Amazon can also be connected so orders come in "
                 "on their own."),
                ("Can I try it without my own data?",
                 "Yes. Load 90 days of sample sales and try every screen first."),
            ],
        },
        "/features/win-back": {
            "kind": "feature",
            "title": "Win back customers who stopped buying, on WhatsApp and email",
            "seo_title": "Customer Win-Back App: WhatsApp Messages for Old Customers",
            "description": "Find the customers who stopped buying, send them a written win-back "
                           "message on WhatsApp or email, and count how many came back. Free for "
                           "small Indian sellers.",
            "answer": ("One Tap Manager finds the customers who used to buy from you and have gone "
                       "quiet, writes the message to bring them back, sends it by email or opens "
                       "WhatsApp with it already typed, and then counts how many actually bought "
                       "again. It works from the sales you already have, and win-back is unlimited "
                       "on the Free plan."),
            "sections": [
                ("How does it find customers who stopped buying?",
                 "<p>It groups every customer by how recently they bought, how often and how much "
                 "they spent. A customer who used to buy every month and has not bought in two is "
                 "flagged while there is still time; a one-time buyer from a year ago is not "
                 "treated the same way. The list is ranked by what each customer used to spend, "
                 "so the first message goes to the people worth the most.</p>"),
                ("How is the message sent?",
                 "<ul><li><b>Email</b> goes out from the app.</li>"
                 "<li><b>WhatsApp</b>: until a WhatsApp Business provider is connected, each "
                 "customer gets a click-to-chat link that opens WhatsApp with the message already "
                 "typed, so you only press send. For forty customers that takes a few minutes.</li>"
                 "<li><b>Excel</b>: prefer to send it your own way? Download the list and the "
                 "messages as a file.</li></ul>"
                 "<p>Campaigns can run every week on their own, and a customer who was just "
                 "contacted is left alone for 45 days, so nobody gets the same message twice.</p>"),
                ("How do I know it worked?",
                 "<p>Every send is logged per customer, with the channel and the date. The app "
                 "then counts who bought again after their message, so you see whether the "
                 "campaign earned its keep instead of guessing.</p>"),
                ("What should the message say?",
                 "<p>Short, personal, one reason to come back and one easy next step. The "
                 '<a href="/guides/win-back-old-customers">win-back message guide</a> has ready '
                 "templates in English and Hindi.</p>"),
            ],
            "faqs": [
                ("Do I need the WhatsApp Business API?",
                 "No. Without it, the app gives you a link per customer that opens WhatsApp with "
                 "the message typed. Connecting a provider later lets it send on its own."),
                ("Is win-back free?",
                 "Yes. Win-back messages are unlimited on the Free plan, including the Excel file."),
                ("Will it annoy my customers?",
                 "It only messages customers who have gone quiet, and leaves each one alone for "
                 "45 days after contacting them."),
            ],
        },
        "/features/stock-reorder": {
            "kind": "feature",
            "title": "Low stock alerts and purchase orders, before a best seller runs out",
            "seo_title": "Low Stock Alert and Reorder App for Small Shops in India",
            "description": "One Tap Manager warns you before stock runs out, based on how fast "
                           "each item sells and how long your supplier takes, and drafts the "
                           "purchase order for you to approve.",
            "answer": ("One Tap Manager works out how fast each item sells and how long each "
                       "supplier takes to deliver, warns you before stock runs out, and drafts "
                       "the purchase order for that supplier. You check it and approve it, and it "
                       "is emailed to the supplier with the order attached as a PDF. Stock "
                       f"reordering and purchase orders are {_max_only()}."),
            "sections": [
                ("How does it decide when to reorder?",
                 "<p>For every item it divides the stock you have by what you sell on an average "
                 "day. That is how many days the stock will last. When that falls below your "
                 "supplier's delivery time plus a 20% safety margin, it is time to order.</p>"
                 '<p class="meta">Worked example, not a customer: an item that sells 4 a day, from '
                 "a supplier who takes 10 days, is flagged when fewer than 48 are left "
                 "(4 × 10 × 1.2).</p>"
                 '<p>Want to work it out yourself? Use the free <a href="/guides/when-to-reorder-stock">'
                 "reorder point calculator</a>.</p>"),
                ("How much does it order?",
                 "<p>At first, the supplier's minimum order. Once you enter what placing an order "
                 "costs you and what holding stock costs you, and there is a month of sales, it "
                 "works out the order size that keeps those two costs lowest together. You can "
                 "always type your own quantity, and yours wins.</p>"),
                ("What happens to the purchase order?",
                 "<ul><li>Items that need ordering are grouped by supplier into one draft each.</li>"
                 "<li>Something already on an order that has not arrived is not ordered twice.</li>"
                 "<li>You see the lines, the maths behind each quantity and the email, and can "
                 "change any of it.</li>"
                 "<li>Approve, and the email is written and sent with the purchase order as a PDF, "
                 "from your own address.</li></ul>"),
                ("Stock by size and colour", _VARIANTS),
            ],
            "faqs": [
                ("Is there a free way to work out a reorder point?",
                 "Yes. The reorder point calculator in the guide to when to reorder stock is free "
                 "and needs no sign-up."),
                ("Is stock reordering on the Free plan?",
                 f"No. It is {_max_only()}. A single purchase order can also be bought with "
                 "credits, without a subscription."),
                ("Does stock go down on its own?",
                 "Yes, for orders on your One Tap website. Sales you upload from other channels "
                 "count towards how fast each item sells."),
            ],
        },
        "/features/gst-invoices": {
            "kind": "feature",
            "title": "GST invoices, and a GSTR-1 file for your accountant",
            "seo_title": "GST Invoice Software for Small Online Sellers in India",
            "description": "GST tax invoices with HSN codes and the September 2025 rates, one "
                           "unbroken number series, and a GSTR-1 file your accountant can file "
                           "from. Free for small Indian sellers.",
            "answer": ("One Tap Manager issues GST tax invoices with HSN codes and the right rate "
                       "on each line, numbers them in one unbroken series, and gives your "
                       "accountant a GSTR-1 file for the month. It applies the rates in force "
                       "since 22 September 2025, including the rule that makes the same kurta 5% "
                       "or 18% depending on its price. Invoices are on every plan, including Free. "
                       "It is not accounting software: the books stay with your accountant."),
            "sections": [
                ("What goes on each invoice?",
                 "<ul><li>A number from one consecutive series, given when the invoice is issued, "
                 "not when a cart is opened, so abandoned carts never leave gaps.</li>"
                 "<li>The HSN code and GST rate for each line, worked out per piece where the law "
                 "says so.</li>"
                 "<li>CGST and SGST, or IGST, depending on where the buyer is.</li>"
                 "<li>The right document for the seller: a tax invoice, a bill of supply for "
                 "composition sellers, or a plain receipt.</li></ul>"),
                ("Which rates does it apply?", _GST_TABLE +
                 '<p>The <a href="/guides/gst-rate-clothes-jewellery-perfume">GST rate guide</a> '
                 "explains each line. Check anything unusual with your accountant.</p>"),
                ("What happens when I cancel an invoice?",
                 "<p>It is marked cancelled, never deleted. GSTR-1 asks for the range of numbers "
                 "issued and how many were cancelled, and a deleted invoice would make that "
                 "impossible to report for the rest of the year.</p>"),
                ("What does my accountant get?",
                 "<p>A GSTR-1 file for the period, built from the invoices themselves, so nobody "
                 "re-types a bill.</p>"),
            ],
            "faqs": [
                ("Is One Tap Manager GST billing software?",
                 "It issues GST invoices and prepares the GSTR-1 file, which is what most small "
                 "online sellers need. It does not keep ledgers or file returns; your accountant "
                 "does that from the file."),
                ("Does it work for composition sellers?",
                 "Yes. A composition seller issues a bill of supply instead of a tax invoice, and "
                 "the app does that."),
                ("Are the rates up to date?",
                 "They follow the GST changes that took effect on 22 September 2025. Check anything "
                 "unusual with your accountant."),
            ],
        },
        "/features/ai-product-photos": {
            "kind": "feature",
            "title": "AI product photos from your own product photo, in your brand's look",
            "seo_title": "AI Product Photography for Clothing, Jewellery and Perfume",
            "description": "Product Studio makes Instagram-ready pictures starting from your own "
                           "product photo, in your brand's light, colours and framing, labelled "
                           "as AI generated.",
            "answer": ("Product Studio in One Tap Manager makes Instagram-ready pictures starting "
                       "from your own product photo, so the item in the picture is really yours, "
                       "not a lookalike. You describe your brand once and upload a few photos you "
                       "like; it follows that light, colour and framing in every picture it makes. "
                       "Anything generated is labelled as AI generated."),
            "sections": [
                ("How does it keep my brand's look?",
                 "<p>You fill in a short brand profile once: what the brand stands for, who buys "
                 "it, the look in four or five words, the colours, the voice, and what never to "
                 "say. That profile is what keeps twenty pictures looking like one brand instead "
                 "of twenty different ones.</p>"),
                ("What does it use for each product?",
                 "<p>Your photos and clips, and anything you know about the piece: the story "
                 "behind it, the materials, who it is for and the occasions it suits. All of it "
                 "is optional, and the app tells you which missing detail would help most.</p>"),
                ("Taking the starting photo on a phone",
                 "<ul><li>Shoot near a window in daylight, not under a tube light.</li>"
                 "<li>Use a plain background: a white sheet or a wall is enough.</li>"
                 "<li>Fill the frame with the product and keep it sharp; tap to focus.</li>"
                 "<li>Jewellery: shoot close, turn the piece until the shine shows, and add one "
                 "photo on a hand or neck for size.</li>"
                 "<li>Perfume: stand the bottle straight, avoid your reflection in the glass, and "
                 "show the label clearly.</li>"
                 "<li>Clothing: lay it flat or hang it, and add a close shot of the fabric.</li></ul>"),
                ("What does it cost?",
                 "<p>The Free plan includes 50 AI uses a day and Max is unlimited. Heavy jobs can "
                 "use credits, which never expire.</p>"),
            ],
            "faqs": [
                ("Is the product in the picture really mine?",
                 "Yes. Each picture starts from your own product photo, so the piece is yours, "
                 "not an invented one."),
                ("Will people know it is AI?",
                 "Yes. Generated pictures are labelled as AI generated."),
                ("Do I need a photographer?",
                 "No. A clear phone photo in daylight is enough to start from."),
            ],
        },
        "/features/instagram-planner": {
            "kind": "feature",
            "title": "A week of Instagram posts, planned, written and scheduled",
            "seo_title": "Instagram Post Planner and Scheduler for Small Brands in India",
            "description": "Plan a week of Instagram posts as one story, with captions written, "
                           "times chosen and pictures made from your own products, then publish "
                           "to your Instagram Business account.",
            "answer": ("The Social Media Manager in One Tap Manager plans a whole week of "
                       "Instagram posts as one story (the tease, the reveal, the proof, the "
                       "close), writes the captions, picks the times, makes the pictures from "
                       "your own product photos, and publishes them to your Instagram Business "
                       "or Creator account once you approve."),
            "sections": [
                ("Why plan a week as one story?",
                 "<p>Seven unrelated posts ask a follower to care seven separate times. A week "
                 "built as one story, where each post leads to the next, gives them a reason to "
                 "come back tomorrow and ends with a clear ask.</p>"),
                ("What kind of posts does it plan?",
                 "<p>Mostly posts that tell people about the product: fabric, fit, care, how to "
                 "wear it, what it smells like after four hours. A 2023 review in the Journal of "
                 "Marketing, pooling 86 studies, found that the posts that win the most likes are "
                 "close to the opposite of the posts that lead to sales, and that informative "
                 "product posts are the ones linked to sales. So the planner is weighted that "
                 "way, and offers are kept to about one post in twenty, with the reason "
                 "shown.</p>"),
                ("Festivals and seasons",
                 "<p>Festival plans for Navratri, Karva Chauth, Dhanteras, Diwali and wedding "
                 "season are built in, so the week before a festival is planned before you "
                 "remember it.</p>"),
                ("Post ideas for clothing, jewellery and perfume brands",
                 "<ul><li><b>Clothing</b>: one piece styled three ways; a fit guide on two body "
                 "types; a close-up of the fabric moving; what is behind a new drop.</li>"
                 "<li><b>Jewellery</b>: the piece on a hand for size; how to store it so it does "
                 "not tarnish; a gifting guide by budget; one set stacked three ways.</li>"
                 "<li><b>Perfume</b>: the notes explained in plain words; how it smells after an "
                 "hour and after four; which scent for which occasion; why a tester is worth "
                 "buying.</li></ul>"),
                ("What does it report back?",
                 "<p>Reach, saves, shares and messages: the numbers linked to buying. Follower "
                 "count is shown, but it is not the goal.</p>"),
            ],
            "faqs": [
                ("Does it post automatically?",
                 "Yes, after you approve. It needs your Instagram Business or Creator account "
                 "connected."),
                ("Does it write the captions?",
                 "Yes. Captions are written in your brand's voice from the brand profile, and you "
                 "can edit any of them before they go out."),
                ("Is it free?",
                 "Planning and writing use AI, and the Free plan includes 50 AI uses a day. Max "
                 "is unlimited."),
            ],
        },
        "/features/review-analysis": {
            "kind": "feature",
            "title": "Customer review and complaint analysis, with a fix-first plan",
            "seo_title": "Customer Review Analysis Tool: Find the Complaint to Fix First",
            "description": "Upload your reviews and see which complaints cost you most, grouped "
                           "into themes such as sizing, quality and delivery, with the one to fix "
                           "first. Free for small Indian sellers.",
            "answer": ("Upload your reviews from Amazon, Flipkart, Google or your own website, and "
                       "One Tap Manager finds the complaints, groups them into themes such as "
                       "sizing, quality or delivery, ranks them by how often they come up and how "
                       "much they hurt, and tells you which one to fix first. It also shows what "
                       "customers praise, in their own words. It is on the Free plan."),
            "sections": [
                ("How does it read reviews?",
                 "<p>A review is a complaint when its rating is three stars or lower, or, when "
                 "there is no rating, when its wording is negative. Each complaint is tagged with "
                 "a theme using words sellers in your trade actually see: sizing runs small for "
                 "clothing, tarnished or plating came off for jewellery, does not last for "
                 "perfume.</p>"),
                ("What is the fix-first plan?",
                 "<p>Every theme is placed by how common it is and how much damage it does. The "
                 "common and damaging ones are fix first; rare but serious ones are contain; "
                 "common but minor ones are streamline; the rest are watch. Each theme comes "
                 "with the specific step to take, shown before the charts.</p>"),
                ("Is it getting better or worse?",
                 "<p>Complaints are counted month by month against all reviews, with a "
                 "three-month average, so you can see whether a fix worked.</p>"),
            ],
            "faqs": [
                ("What file do I need?",
                 "A CSV or Excel file with the review text. A rating and a date column help, but "
                 "are not required."),
                ("Does it work without star ratings?",
                 "Yes. It reads the wording to decide which reviews are complaints."),
                ("Is it free?",
                 "Yes. Complaint and review analysis are on the Free plan."),
            ],
        },
        "/features/online-store": {
            "kind": "feature",
            "title": "Your own online store, with no commission on your sales",
            "seo_title": "Free Online Store for Indian Sellers, No Commission on Sales",
            "description": "A selling website with cart, cash on delivery and Razorpay, included "
                           "free with One Tap Manager, with no badge and no fee on your sales.",
            "answer": ("Every One Tap Manager account includes its own selling website: products, "
                       "a cart, cash on delivery and Razorpay payments, with no badge and no fee "
                       "on your sales. Orders take items out of stock, count in your sales "
                       "numbers and add the buyer to your customer list for win-back. The Free "
                       "plan covers up to 250 products; Max adds your own domain."),
            "sections": [
                ("What is included?",
                 "<ul><li>Themes that change the layout and type, not only the colour.</li>"
                 "<li>Products from your one product list, with sizes, colours and stock.</li>"
                 "<li>A cart priced on the server, cash on delivery and Razorpay.</li>"
                 "<li>Your shipping fee, a free-shipping threshold and GST on the bill.</li>"
                 "<li>Customer accounts that belong to your shop and nobody else's.</li>"
                 "<li>Your own sitemap, so search engines find your products.</li></ul>"),
                ("For Instagram sellers",
                 "<p>Put the store in your link in bio. Every order placed there is counted in "
                 "your numbers, instead of living in DMs and a notebook, and every buyer can be "
                 'won back later. See <a href="/for/instagram-sellers">software for Instagram '
                 "sellers</a>.</p>"),
                ("How is it different from Shopify?",
                 "<p>There is no app store to buy the rest from: analytics, stock, win-back and "
                 "reviews are already joined to the store. There is also no per-order fee from "
                 'us. See <a href="/compare/shopify-apps">the Shopify comparison</a> for what '
                 "Shopify does better.</p>"),
            ],
            "faqs": [
                ("Is the online store really free?",
                 "Yes. It is on the Free plan, with no badge, for up to 250 products."),
                ("Do you take a commission on orders?",
                 "No. Razorpay charges its usual payment fee if you use it; One Tap Manager adds "
                 "nothing."),
                ("Can I use my own domain?",
                 "Yes, on the Max plan."),
            ],
        },
    }


def _for_pages() -> dict[str, dict]:
    return {
        "/for/clothing-sellers": {
            "kind": "for",
            "title": "Software for small Indian clothing sellers and boutiques",
            "seo_title": "Clothing Shop and Boutique Management Software for India",
            "description": "What a small Indian clothing brand or boutique needs from software to "
                           "track styles and sizes, reorder, win back customers, handle GST and "
                           "post on Instagram, and how One Tap Manager does it.",
            "answer": ("A small clothing seller or boutique needs software for four jobs: seeing "
                       "which styles and sizes actually earn, reordering before a best seller "
                       "runs out, bringing back customers who stopped buying, and posting on "
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
                ("Size-wise and colour-wise stock", _VARIANTS),
                ("How does One Tap Manager handle GST on clothing?",
                 "<p>Since 22 September 2025, a piece of clothing priced up to ₹2,500 is taxed "
                 "at 5%, and above ₹2,500 at 18%. The rate is worked out per piece, so the same "
                 "kurta design can fall on either side. One Tap Manager applies the rate to each "
                 "line, prints tax invoices with HSN codes, and gives you a GSTR-1 file your "
                 "accountant can file from. Check anything unusual with your accountant.</p>"),
                ("Where do the sales come from?", _SOURCES),
                ("What does it do for me, not just show me?",
                 '<ul><li>Writes the <a href="/features/win-back">win-back message</a> and sends '
                 "it weekly, leaving a customer alone for 45 days after contacting them.</li>"
                 '<li>Fills in the <a href="/features/stock-reorder">purchase order</a> and emails '
                 "it to your supplier from your own address.</li>"
                 '<li>Plans, writes and schedules <a href="/features/instagram-planner">a week of '
                 "Instagram posts</a> made from your own product photos.</li></ul>"),
                ("How much does it cost?", _plan_table()),
            ],
            "faqs": [
                ("Is One Tap Manager boutique management software?",
                 "Yes. It is built for small clothing shops and boutiques run by one owner: "
                 "stock by size and colour, customers, win-back, GST invoices and Instagram, in "
                 "one app."),
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
            "kind": "for",
            "title": "Software for small Indian jewellery sellers, including imitation jewellery",
            "seo_title": "Software for Imitation and Small Jewellery Businesses in India",
            "description": "What a small Indian jewellery brand, including artificial and imitation "
                           "jewellery sellers, needs from software, from 3% GST invoices to "
                           "catching tarnish complaints early, and how One Tap Manager does it.",
            "answer": ("A small jewellery seller, whether gold-plated, silver or imitation, needs "
                       "software that shows which designs earn, warns before a best seller runs "
                       "out, catches quality complaints such as tarnish or plating early, and "
                       f"brings back customers who stopped buying. {PRODUCT} does this from the "
                       "sales and reviews you already have. " + _price_line()),
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
                ("Imitation and artificial jewellery",
                 "<p>Most jewellery software in India is built for gold shops: weight, purity, "
                 "making charges and old-gold exchange. A seller of artificial, oxidised or "
                 "gold-plated pieces needs something else: many low-priced designs, fast "
                 "reordering, photos that sell on Instagram, and a close watch on quality "
                 "complaints. That is the seller One Tap Manager is built for. It does not do "
                 "gold rates or karat billing.</p>"),
                ("How does One Tap Manager handle GST on jewellery?",
                 "<p>Gold and silver jewellery (HSN 7113) is taxed at 3%. One Tap Manager applies "
                 "3% to imitation jewellery (HSN 7117) too, but published sources have disagreed "
                 "on that rate, so confirm it with your accountant. It prints each invoice and "
                 "prepares a GSTR-1 file.</p>"),
                ("Photos that look like your brand",
                 '<p><a href="/features/ai-product-photos">Product Studio</a> makes Instagram '
                 "pictures starting from your own jewellery photo, so the piece is really yours, "
                 "in your brand's light and colours.</p>"),
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
                ("Does it handle gold rates and karat billing?",
                 "No. It is built for small fashion and imitation jewellery brands, not for gold "
                 "shops that bill by weight and purity."),
                ("Does it take a cut of my sales?",
                 "No. There is no per-order or percentage fee on any plan."),
            ],
        },
        "/for/perfume-sellers": {
            "kind": "for",
            "title": "Software for small Indian perfume and attar sellers",
            "seo_title": "Perfume and Attar Shop Software for Small Indian Brands",
            "description": "What a small Indian perfume or attar brand needs from software, "
                           "from 18% GST invoices to spotting 'does not last' complaints, and "
                           "how One Tap Manager does it.",
            "answer": ("A small perfume or attar seller needs software that shows which scents "
                       "and bottle sizes sell, reorders before a best seller runs out, spots "
                       "complaints such as 'does not last' before they spread, and brings back "
                       f"customers who stopped buying. {PRODUCT} does this from the sales and "
                       "reviews you already have. " + _price_line()),
            "sections": [
                ("What should a perfume seller watch?",
                 "<ul><li><b>Which scents and bottle sizes earn</b>, including the testers "
                 "that turn into full bottles.</li>"
                 "<li><b>Longevity complaints</b>: the app reads reviews for no smell, faded "
                 "quickly, does not last and weak fragrance, and ranks them by cost.</li>"
                 "<li><b>Trust complaints</b>: fake perfume, not the original scent, diluted.</li>"
                 "<li><b>Repeat buyers</b>: perfume is bought again when it runs out, which "
                 "makes win-back timing matter more than for most products.</li></ul>"),
                ("Bottle sizes and scents as one product",
                 "<p>Sell a scent in 3 ml, 6 ml and 12 ml, or as an attar and a spray, as one "
                 "product with options. Each size keeps its own stock and price, and the numbers "
                 "show which size people actually buy.</p>"),
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
        "/for/instagram-sellers": {
            "kind": "for",
            "title": "Software for Instagram sellers in India",
            "seo_title": "Instagram Seller Management App for Small Indian Brands",
            "description": "What a brand that sells through Instagram needs from software: a place "
                           "where every order is counted, a week of posts planned, and a way to "
                           "bring back past buyers.",
            "answer": ("A seller who sells through Instagram needs three things that rarely come "
                       "in one app: a place where every order is counted, a plan for what to post, "
                       f"and a way to bring back buyers who went quiet. {PRODUCT} does all three: "
                       "a free selling website for your link in bio, a week of posts planned and "
                       "scheduled, and win-back messages to past buyers. " + _price_line()),
            "sections": [
                ("Where do DM orders go?",
                 "<p>Two ways. Send buyers to your own One Tap website from your bio, and every "
                 "order is counted, stocked and invoiced on its own. Or keep taking orders in DMs, "
                 "note them in a spreadsheet, and upload it once a week. Either way, the sales "
                 "end up in one set of numbers.</p>"),
                ("What to post, and when",
                 '<p>The <a href="/features/instagram-planner">Social Media Manager</a> plans a '
                 "week as one story, writes the captions, makes the pictures from your own "
                 "product photos and publishes to your Instagram Business or Creator account "
                 "after you approve.</p>"),
                ("Bringing past buyers back",
                 "<p>Instagram buyers are easy to forget once the chat scrolls away. The app keeps "
                 'the list, flags who has gone quiet and <a href="/features/win-back">writes the '
                 "message</a> to send on WhatsApp.</p>"),
                ("How much does it cost?", _plan_table()),
            ],
            "faqs": [
                ("Do I need a website?",
                 "No, but one is included free, and it is the easiest way to have every order "
                 "counted."),
                ("Does it read my Instagram DMs?",
                 "No. It schedules and publishes posts and reports how they did. Orders come from "
                 "your website or a file you upload."),
                ("Does it take a cut of my sales?",
                 "No. There is no per-order or percentage fee on any plan."),
            ],
        },
    }


def _compare_pages() -> dict[str, dict]:
    total = _inr(pricing.stack_comparison()["typical_total_inr"])
    return {
        "/compare/shopify-apps": {
            "kind": "compare",
            "title": "A Shopify alternative for India: one app instead of five Shopify apps",
            "seo_title": "Shopify Alternative in India: One App Instead of Five Shopify Apps",
            "description": "The monthly cost of separate Shopify apps for analytics, inventory, "
                           "win-back, reviews and orders, against One Tap Manager, with the "
                           "arithmetic shown, and when to keep Shopify.",
            "answer": ("A small Indian D2C brand on Shopify typically pays for five separate "
                       f"apps: analytics, inventory, win-back email, reviews and order "
                       f"management, about {total} a month before any percentage-of-sales fees. "
                       f"{PRODUCT} covers the same jobs in one app, and includes its own selling "
                       "website, so it can replace the apps, or Shopify as well. "
                       + _price_line()),
            "sections": [
                ("What does the separate-app stack cost?", _stack_table()),
                ("What else does a Shopify store cost in India?",
                 "<p>Three things add up: Shopify's own monthly plan, the apps above, and payment "
                 "fees. Shopify Payments is not offered in India, so Indian stores take payments "
                 "through a third-party gateway such as Razorpay, and Shopify adds its own "
                 "transaction fee on those orders on top of the gateway's fee. The current plan "
                 "prices and fee are on Shopify's India pricing page; check them there, because "
                 "they change.</p>"),
                ("Is One Tap Manager a Shopify alternative?",
                 "<p>For a small seller, it can be. It includes a selling website with a cart, "
                 "cash on delivery and Razorpay, with no fee on your sales, and the analytics, "
                 "stock, win-back and reviews are already joined to it. For a larger store that "
                 "needs a big theme marketplace, many sales channels or a niche app, Shopify is "
                 "the stronger choice.</p>"),
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
                 "keep Shopify and connect it. Those who move to the included website stop paying "
                 "both."),
                ("Are the app prices exact?",
                 "No. They are typical monthly prices for each kind of app. Check your own "
                 "bills for the real figure."),
                ("Is there a free Shopify alternative in India?",
                 "One Tap Manager's Free plan includes a selling website with cart, COD and "
                 "Razorpay for up to 250 products, with no badge and no fee on sales."),
            ],
        },
        "/compare/odoo": {
            "kind": "compare",
            "title": "An Odoo alternative for small Indian sellers",
            "seo_title": "Odoo Alternative for Small Business in India",
            "description": "When Odoo is the right choice, when it is more than a small seller "
                           "needs, and what One Tap Manager keeps from it.",
            "answer": ("Odoo is a full business system, with modules for manufacturing, "
                       "warehouses, payroll and accounting, usually set up with a partner. "
                       f"{PRODUCT} keeps the part a small seller needs, joined up the same way "
                       "(products, stock, suppliers, orders, invoices and GST in one place), and "
                       "drops the setup. If you run a factory floor and several godowns, choose "
                       "Odoo. If you sell 40 to 400 products and your accountant wants one clean "
                       f"tax file, {PRODUCT} is built for you."),
            "sections": [
                ("How do they compare?",
                 '<div class="scroll"><table><thead><tr><th></th><th>Odoo</th>'
                 f"<th>{PRODUCT}</th></tr></thead><tbody>"
                 "<tr><th>Built for</th><td>Businesses of any size, often with staff to run it</td>"
                 "<td>One owner running a small shop</td></tr>"
                 "<tr><th>Setup</th><td>Choose and configure modules, often with a partner</td>"
                 "<td>Upload a sales file; first answers in about two minutes</td></tr>"
                 "<tr><th>Accounting</th><td>Full double-entry accounting</td>"
                 "<td>GST invoices and a GSTR-1 file; the books stay with your accountant</td></tr>"
                 "<tr><th>Manufacturing, warehouses, payroll</th><td>Yes</td><td>No</td></tr>"
                 "<tr><th>Tells you what to do today</th><td>Reports you read</td>"
                 "<td>Three suggested actions each morning, with the work started</td></tr>"
                 "<tr><th>Instagram posts and product photos</th><td>Not its focus</td>"
                 "<td>Built in</td></tr>"
                 "<tr><th>Price</th><td>See odoo.com; depends on apps and users</td>"
                 f"<td>Free plan; Max at {esc(_max_price())} a month</td></tr>"
                 "</tbody></table></div>"),
                ("What does joined up mean here?",
                 "<p>An order on your website takes the item out of stock, uses up the materials "
                 "it needed, writes a proper tax invoice and shows up in your numbers, without "
                 "anything being entered twice. That is what Odoo does well, and what separate "
                 "apps rarely do.</p>"),
                ("When should I choose Odoo?",
                 "<p>When you manufacture, run more than one warehouse, pay salaries through the "
                 "system or want full accounting in the same place. One Tap Manager does none of "
                 "those and does not pretend to.</p>"),
            ],
            "faqs": [
                ("Is Odoo too complicated for a small shop?",
                 "It can be. It is built to be configured, and a small seller often does not get "
                 "through the setup. One Tap Manager starts from a sales file instead."),
                ("Can One Tap Manager replace Odoo?",
                 "For a small seller who needs stock, suppliers, orders, invoices and GST, yes. "
                 "For manufacturing, payroll or full accounting, no."),
            ],
        },
        "/compare/billing-apps": {
            "kind": "compare",
            "title": "Billing app or shop manager: what is the difference?",
            "seo_title": "Billing App vs Shop Manager: Vyapar, myBillBook, Zoho and One Tap",
            "description": "What billing and accounting apps such as Vyapar, myBillBook, Zoho "
                           "Books and TallyPrime do, what a shop manager does, and when a small "
                           "seller needs each.",
            "answer": ("A billing app records what happened: bills, payments, stock in and out, "
                       "and the accounts. Vyapar, myBillBook, Zoho Books and TallyPrime are "
                       "examples. A shop manager reads those records and tells you what to do "
                       f"next: what to reorder, who to win back, what to fix. {PRODUCT} is a shop "
                       "manager built to sit next to your billing app, not to replace it."),
            "sections": [
                ("Which one do I need?",
                 "<ul><li><b>Only bills and accounts</b>: a billing app is enough.</li>"
                 "<li><b>You bill at a counter and want to grow</b>: keep your billing app, "
                 "export its sales once a week and upload them to One Tap Manager.</li>"
                 "<li><b>You sell only online</b>: One Tap Manager issues GST invoices for "
                 "orders on your own website and prepares the GSTR-1 file, so you may not need "
                 "a separate billing app. Ask your accountant.</li></ul>"),
                ("What a shop manager adds",
                 "<ul><li>Which products and kinds of product carry the shop.</li>"
                 "<li>Who has stopped buying, with the message to bring them back.</li>"
                 "<li>When to reorder, with the purchase order written.</li>"
                 "<li>Which complaint is costing you most.</li>"
                 "<li>A week of Instagram posts from your own photos.</li></ul>"),
                ("What it does not do",
                 "<p>No ledgers, no bank reconciliation, no payroll, no filing of returns. Those "
                 "stay with your billing app and your accountant.</p>"),
            ],
            "faqs": [
                ("Is One Tap Manager a Vyapar or myBillBook alternative?",
                 "Not really. Those are billing and accounting apps. One Tap Manager reads the "
                 "sales they record and tells you what to do next. Many sellers will use both."),
                ("Can I upload sales from my billing app?",
                 "Yes. Export sales as CSV or Excel and upload them; the app works out which "
                 "column is which."),
            ],
        },
    }


def _guide_pages() -> dict[str, dict]:
    return {
        "/guides/win-back-old-customers": {
            "kind": "guide",
            "title": "How to get old customers back: WhatsApp messages that work, in English and Hindi",
            "seo_title": "How to Get Old Customers Back: WhatsApp Win-Back Messages",
            "description": "Who counts as an old customer, what the message should say, ready "
                           "templates in English and Hindi, and how to tell whether it worked.",
            "answer": ("Find the customers who used to buy regularly and have stopped, send each "
                       "one a short personal message with one reason to come back (something new, "
                       "something like what they bought before, or a small thank-you), send it "
                       "once, and count who buys again. A message to the right forty people costs "
                       "less than a discount for everyone."),
            "sections": [
                ("Who counts as an old customer?",
                 "<p>Compare how long it has been since each customer's last order with how often "
                 "they used to buy. Someone who bought every month and has not bought in two "
                 "months is slipping. Someone who bought once, a year ago, is a different case "
                 "and needs a different message, or none. Start with the regular buyers who "
                 "spent the most: they are worth the most and the easiest to bring back.</p>"),
                ("What should the message say?",
                 "<ul><li>Their name, and what they bought, so it is clearly for them.</li>"
                 "<li>One reason to come back: a new arrival, a restock of something they liked, "
                 "or a thank-you.</li>"
                 "<li>One easy next step: a link, or reply to this message.</li>"
                 "<li>A way to say no more messages, and respect it.</li>"
                 "<li>No fake deadline. Customers can tell.</li></ul>"),
                ("Templates in English",
                 '<div class="tpl"><p>Hi Priya, it has been a while since your cotton kurta. We have '
                 "just got new block prints in the same fabric. Want me to send you a few photos?</p></div>"
                 '<div class="tpl"><p>Hi Rahul, thank you for buying from us last season. The '
                 "oxidised earrings you picked are back in stock, and I kept a pair aside for you "
                 "until Sunday. Reply YES and I will send the link.</p></div>"
                 '<div class="tpl"><p>Hi Ananya, your oud attar should be running low by now. Same '
                 "size again, or would you like to try the new rose one first? Reply and I will "
                 "send a small tester with your order.</p></div>"
                 '<p class="meta">Names and products are examples. Reply STOP to any message '
                 "should mean no more messages.</p>"),
                ("Templates in Hindi",
                 '<div class="tpl" lang="hi"><p>नमस्ते प्रिया जी, आपने पिछली बार हमसे कॉटन कुर्ता लिया '
                 "था। उसी कपड़े में नए ब्लॉक प्रिंट आए हैं। क्या मैं आपको कुछ फ़ोटो भेजूँ?</p></div>"
                 '<div class="tpl" lang="hi"><p>नमस्ते राहुल जी, पिछली बार हमसे ख़रीदारी के लिए धन्यवाद। '
                 "आपके पसंद किए झुमके फिर से आ गए हैं, और एक जोड़ी मैंने रविवार तक आपके लिए रख दी "
                 "है। हाँ लिखिए, मैं लिंक भेज देता हूँ।</p></div>"
                 '<div class="tpl"><p>Namaste Ananya ji, aapka attar ab khatam hone wala hoga. Wahi '
                 "size dobara bhejein, ya pehle naya gulab wala try karengi? Reply kijiye, order ke "
                 "saath ek chhota tester bhi bhej denge.</p></div>"
                 '<p class="meta">The last one is in Hinglish, which many customers find easier '
                 "to read on WhatsApp than Devanagari.</p>"),
                ("When and how often should I send it?",
                 "<p>Once, at a time people read messages: late morning or early evening, not "
                 "late at night. Then leave that customer alone for about six weeks. A second "
                 "message a week later reads as spam and gets your number blocked.</p>"),
                ("WhatsApp rules worth knowing",
                 "<ul><li>Message only people who bought from you and gave you their number.</li>"
                 "<li>A broadcast list in the WhatsApp Business app only reaches people who have "
                 "saved your number; the rest need a personal message or an approved WhatsApp "
                 "Business provider.</li>"
                 "<li>If people block or report you, WhatsApp can limit your account. Fewer, "
                 "better messages protect your number.</li></ul>"),
                ("How do I know it worked?",
                 "<p>Write down who you messaged and the date, then count who ordered in the next "
                 "30 days. Compare that with a few similar customers you did not message. "
                 '<a href="/features/win-back">One Tap Manager\'s win-back</a> keeps this log '
                 "and does the counting for you.</p>"),
            ],
            "faqs": [
                ("Should I offer a discount to old customers?",
                 "Not first. A personal message with something new or a thank-you often works "
                 "without one, and a discount teaches customers to wait for the next."),
                ("How many win-back messages is too many?",
                 "More than one in about six weeks to the same person. Send once, then wait."),
                ("Purane customer wapas kaise laye?",
                 "Jo customer pehle regular kharidte the aur ab ruk gaye hain, unhe ek chhota "
                 "personal WhatsApp message bhejiye: unka naam, unhone kya kharida tha, aur wapas "
                 "aane ki ek wajah. Ek baar bhejiye, aur 30 din mein kitne wapas aaye, gin lijiye."),
            ],
        },
        "/guides/when-to-reorder-stock": {
            "kind": "guide",
            "title": "When to reorder stock: the reorder point formula, with a free calculator",
            "seo_title": "Reorder Point Calculator and Formula for Small Shops",
            "description": "Reorder point = units sold a day × supplier delivery days × a safety "
                           "margin. A free calculator, a worked example and the mistakes small "
                           "shops make.",
            "answer": ("Reorder when the stock you have left will only last as long as your "
                       "supplier takes to deliver, plus a safety margin. As a formula: reorder "
                       "point = units sold a day × delivery days × 1.2, where 1.2 is a 20% "
                       "safety margin. An item that sells 4 a day from a supplier who takes 10 "
                       "days should be reordered when 48 are left."),
            "sections": [
                ("Reorder point calculator", _reorder_tool),
                ("Where do the numbers come from?",
                 "<ul><li><b>Units sold a day</b>: take the last 30 days of sales for that item "
                 "and divide by 30. Leave out days when it was out of stock, or the average comes "
                 "out too low.</li>"
                 "<li><b>Delivery days</b>: from the day you place the order to the day the stock "
                 "is on your shelf, including transit and the time you take to check it.</li>"
                 "<li><b>Safety margin</b>: extra for the week sales jump or the supplier is "
                 "late. 20% is a sensible start.</li></ul>"),
                ("Why add a safety margin?",
                 "<p>Without one, you reorder exactly on time only if nothing goes wrong. Sales "
                 "rise before festivals and suppliers are late in the wedding season. Raise the "
                 "margin for best sellers and festival months, and lower it for slow items where "
                 "running out costs little.</p>"),
                ("How much should I order?",
                 "<p>At least the supplier's minimum order. Beyond that, it is a trade-off: "
                 "bigger orders mean fewer orders to place but more money sitting on shelves; "
                 "smaller orders mean the opposite. If placing an order costs you little and "
                 "stock ties up cash, order smaller and more often.</p>"),
                ("Mistakes small shops make",
                 "<ul><li>Averaging over days when the item was sold out.</li>"
                 "<li>One reorder point for a product sold in six sizes. M and L run out long "
                 "before XXL; each size needs its own.</li>"
                 "<li>Forgetting festival demand until the week of the festival.</li>"
                 "<li>Counting the supplier's dispatch date, not the day stock is on the shelf.</li></ul>"),
                ("Letting the app do it",
                 '<p><a href="/features/stock-reorder">One Tap Manager\'s stock reordering</a> '
                 "works this out for every item from your own sales, warns you before stock runs "
                 f"out and drafts the purchase order. It is {_max_only()}.</p>"),
            ],
            "faqs": [
                ("What is a reorder point?",
                 "The stock level at which you place the next order, so new stock arrives before "
                 "the old runs out."),
                ("What is safety stock?",
                 "Extra stock kept for the days sales run higher or the supplier is late. In the "
                 "formula here it is the 20% margin."),
                ("What is lead time?",
                 "The days from placing an order to having the stock ready to sell."),
            ],
        },
        "/guides/sales-up-profit-down": {
            "kind": "guide",
            "title": "Why are my sales up but profit down? Six places to look",
            "seo_title": "Sales Up but Profit Down? Six Places Small Sellers Should Look",
            "description": "When sales rise and profit falls, the cause is usually one of six "
                           "things. How to check each one in a spreadsheet in twenty minutes.",
            "answer": ("When sales rise and profit falls, the extra sales usually come from "
                       "lower-margin items, bigger discounts, more returns, or costs that grow "
                       "with every order such as shipping, marketplace fees and payment fees. "
                       "Check each against last month, and the leak normally shows up in one or "
                       "two of them."),
            "sections": [
                ("1. The mix moved to cheaper items",
                 "<p>If the extra sales are low-priced or low-margin items, you sell more and "
                 "keep less. Compare sales by product this month and last, and look at which "
                 "items grew.</p>"),
                ("2. Discounts grew",
                 "<p>A sale that brings in orders at 30% off can lose money on every one of them. "
                 "Add up the discount given this month and compare it with last month.</p>"),
                ("3. Returns and cancellations rose",
                 "<p>Online, a return costs the shipping both ways and sometimes the item. If "
                 "returns grew, check which products and which complaint: sizing is the usual "
                 "one for clothing.</p>"),
                ("4. Costs that grow with every order",
                 "<p>Marketplace commission, payment gateway fees, packaging and shipping all rise "
                 "with sales. A new channel with higher fees can make every sale there worth "
                 "less.</p>"),
                ("5. A GST rate changed",
                 "<p>Since 22 September 2025, clothing above ₹2,500 a piece is taxed at 18% "
                 "instead of 12%. If you kept the same tax-inclusive price, you keep less of every "
                 "such sale. Pieces between ₹1,000 and ₹2,500 moved the other way, from 12% to "
                 '5%. See the <a href="/guides/gst-rate-clothes-jewellery-perfume">GST rate '
                 "guide</a>.</p>"),
                ("6. Your purchase price went up",
                 "<p>Suppliers raise prices quietly. Compare the last two invoices for your top "
                 "ten items.</p>"),
                ("How to check in twenty minutes",
                 "<ol><li>Put this month's and last month's sales side by side by product.</li>"
                 "<li>Add a column with what each item costs you.</li>"
                 "<li>Work out what you keep per item: price, minus discount, minus cost, minus "
                 "fees and shipping.</li>"
                 "<li>Sort by the change in what you keep. The top of that list is your "
                 "answer.</li></ol>"),
                ("What One Tap Manager can and cannot tell you",
                 '<p><a href="/features/sales-analytics">Sales analytics</a> shows which products '
                 "and kinds of product grew, and complaint analysis shows why returns rose. It "
                 "does not know your purchase prices, so the margin column is yours to add.</p>"),
            ],
            "faqs": [
                ("Can sales grow while profit falls?",
                 "Yes, often. More sales of low-margin items, deeper discounts or higher fees per "
                 "order all do it."),
                ("What should I check first?",
                 "Discounts and the product mix. Those two explain it most of the time for a "
                 "small seller."),
            ],
        },
        "/guides/gst-rate-clothes-jewellery-perfume": {
            "kind": "guide",
            "title": "GST rate on clothes, jewellery and perfume in India (2026)",
            "seo_title": "GST Rate on Clothes, Jewellery and Perfume in India (2026)",
            "description": "GST on clothing is 5% up to ₹2,500 a piece and 18% above; jewellery "
                           "is 3%; perfume and attar are 18%. The full table, with HSN codes and "
                           "what changed in September 2025.",
            "answer": ("Since 22 September 2025: clothing is taxed at 5% for a piece priced up to "
                       "₹2,500 and 18% above it; gold and silver jewellery at 3%; perfume and "
                       "attar at 18%. The clothing rate is decided per piece, so two kurtas on "
                       "the same bill can carry different rates. Imitation jewellery is generally "
                       "treated as 3%, but confirm it with your accountant."),
            "sections": [
                ("The rates, with HSN codes", _GST_TABLE),
                ("What changed in September 2025?",
                 "<p>GST moved to two main rates, 5% and 18%, with 40% for a short list of luxury "
                 "and harmful goods. For clothing, the line between the low and high rate moved "
                 "from ₹1,000 to ₹2,500 a piece, and the rate above it went from 12% to 18%. "
                 "Jewellery stayed at 3%.</p>"),
                ("How is the clothing rate decided?",
                 "<p>Per piece, on the price of that piece. A ₹2,200 kurta and a ₹2,800 lehenga "
                 "on one bill are taxed at 5% and 18%. How discounts and multi-piece packs near "
                 "the ₹2,500 line should be treated is not settled in any source we found, so "
                 "ask your accountant about those cases.</p>"),
                ("What about imitation jewellery?",
                 "<p>Imitation jewellery (HSN 7117) is generally taxed at 3%, like gold and "
                 "silver. Published sources have disagreed on it, so confirm the rate with your "
                 "accountant before relying on it.</p>"),
                ("Getting it right on every bill",
                 '<p><a href="/features/gst-invoices">One Tap Manager\'s GST invoices</a> apply '
                 "these rates line by line, including the per-piece clothing rule, and prepare "
                 "the GSTR-1 file for your accountant.</p>"),
            ],
            "faqs": [
                ("What is the GST rate on clothes in 2026?",
                 "5% for a piece priced up to ₹2,500 and 18% above ₹2,500, since 22 September 2025."),
                ("What is the GST rate on jewellery?",
                 "3% for gold and silver jewellery. Imitation jewellery is generally 3% as well; "
                 "confirm with your accountant."),
                ("What is the GST rate on perfume and attar?",
                 "18% (HSN 3303)."),
                ("Is this tax advice?",
                 "No. It is how the rates read after the September 2025 changes. Check anything "
                 "unusual with your accountant."),
            ],
        },
        "/guides/analyse-sales-excel": {
            "kind": "guide",
            "title": "How to analyse your sales in Excel: five tables every small shop should build",
            "seo_title": "How to Analyse Sales Data in Excel for a Small Shop",
            "description": "Five pivot tables that answer what is growing, what carries the shop, "
                           "which day is slow, who your best buyers are and who has stopped coming.",
            "answer": ("Put one row per sale with the date, product, category, customer, quantity "
                       "and amount, then build five pivot tables: money by month, by product, by "
                       "weekday, by customer, and each customer's last order date. Those five "
                       "answer most of what a small seller needs to know: what is growing, what "
                       "carries the shop, which day is slow, who the best buyers are and who has "
                       "stopped coming."),
            "sections": [
                ("Get the data into one sheet",
                 "<p>One row per sale, or per line of a bill. Columns: Date, Order, Customer (a "
                 "phone number works), Product, Category, Quantity, Amount. Make sure Date is a "
                 "real date and Amount a number, not text.</p>"),
                ("1. Money by month",
                 "<p>Insert, PivotTable. Date in Rows (group by Months and Years), Amount in "
                 "Values. Is the shop growing, flat or seasonal?</p>"),
                ("2. Money by product and category",
                 "<p>Product in Rows, Amount in Values, sorted largest first. Then the same by "
                 "Category. Usually a handful of products bring in most of the money.</p>"),
                ("3. Money by weekday",
                 '<p>Add a column with =TEXT(A2,"dddd") to get the weekday, then pivot on it. '
                 "The slow day is where a small offer does the most good.</p>"),
                ("4. Money by customer",
                 "<p>Customer in Rows, Amount and a count of Order in Values. Your top twenty "
                 "customers are worth a personal thank-you.</p>"),
                ("5. Who has stopped coming",
                 "<p>Customer in Rows, Date in Values set to Max. That is each customer's last "
                 "order. Sort oldest first: regular buyers near the top have gone quiet, and they "
                 'are the ones to <a href="/guides/win-back-old-customers">win back</a>.</p>'),
                ("When a spreadsheet stops being enough",
                 "<p>When you rebuild these every week, or the file comes from three places. "
                 '<a href="/features/sales-analytics">One Tap Manager</a> reads the same file, '
                 "builds all five and more in about two minutes, and writes the next step next "
                 "to each finding.</p>"),
            ],
            "faqs": [
                ("Can I analyse sales in Excel for free?",
                 "Yes. Pivot tables do most of it. The five above are a good start."),
                ("Which columns do I need?",
                 "Date, product and amount at the least. Customer, category and quantity make it "
                 "far more useful."),
            ],
        },
    }


def _hindi_pages() -> dict[str, dict]:
    return {
        "/hi": {
            "kind": "hi",
            "lang": "hi",
            "title": "दुकान का हिसाब-किताब, स्टॉक और GST बिल, एक ऐप में",
            "seo_title": "दुकान का हिसाब-किताब ऐप: स्टॉक, GST बिल और बिक्री रिपोर्ट",
            "description": "कपड़े, गहने और परफ़्यूम बेचने वाले छोटे विक्रेताओं के लिए One Tap Manager: "
                           "बिक्री की रिपोर्ट, स्टॉक खत्म होने से पहले चेतावनी, GST बिल, पुराने ग्राहकों "
                           "को WhatsApp संदेश और अपनी मुफ़्त ऑनलाइन दुकान।",
            "answer": ("One Tap Manager कपड़े, गहने और परफ़्यूम बेचने वाले छोटे भारतीय विक्रेताओं के "
                       "लिए दुकान चलाने का ऐप है। आप अपनी बिक्री की Excel या CSV फ़ाइल डालते हैं, और "
                       "यह बताता है कि क्या दोबारा मँगाना है, कौन-से पुराने ग्राहक लौटकर नहीं आए और "
                       "पहले क्या ठीक करना है। फिर ज़्यादातर काम भी करता है: पुराने ग्राहकों के लिए "
                       "WhatsApp संदेश, सप्लायर को ऑर्डर और हफ़्ते भर की Instagram पोस्ट। "
                       + _price_line_hi()),
            "sections": [
                ("यह क्या-क्या करता है?",
                 "<ul><li><b>बिक्री की रिपोर्ट</b>: क्या बिका, किससे कितना पैसा आया, कौन-सा दिन "
                 "धीमा है, और अगले महीने का अंदाज़ा।</li>"
                 "<li><b>पुराने ग्राहक</b>: कौन लौटकर नहीं आया, उसके लिए संदेश तैयार, और कितने "
                 "वापस आए इसकी गिनती।</li>"
                 "<li><b>स्टॉक</b>: साइज़ और रंग के हिसाब से स्टॉक; वेबसाइट पर ऑर्डर आते ही स्टॉक "
                 "अपने आप घटता है; Max में कम स्टॉक की चेतावनी और सप्लायर को ऑर्डर।</li>"
                 "<li><b>GST बिल</b>: HSN कोड और सही दर के साथ टैक्स इनवॉइस, और आपके CA के लिए "
                 "GSTR-1 फ़ाइल।</li>"
                 "<li><b>शिकायतें</b>: रिव्यू पढ़कर बताता है कि सबसे पहले कौन-सी शिकायत ठीक करनी है।</li>"
                 "<li><b>Instagram</b>: हफ़्ते भर की पोस्ट, कैप्शन और आपकी अपनी फ़ोटो से बनी तस्वीरें।</li>"
                 "<li><b>अपनी ऑनलाइन दुकान</b>: कार्ट, कैश ऑन डिलीवरी और Razorpay के साथ, मुफ़्त।</li></ul>"),
                ("रोमन में",
                 "<p lang=\"en\">Dukan ka hisab-kitab, stock register, GST bill aur purane customer "
                 "ko WhatsApp message: sab ek app mein. App Hindi mein bhi chalta hai. Free plan "
                 "hamesha free hai, aur aapki bikri par koi commission nahi.</p>"),
                ("कपड़ों, गहनों और परफ़्यूम पर GST",
                 "<ul><li>कपड़े: ₹2,500 तक के एक पीस पर 5%, उससे ऊपर 18% (22 सितंबर 2025 से)।</li>"
                 "<li>सोने-चाँदी के गहने: 3%। नकली (इमिटेशन) गहनों पर भी आम तौर पर 3%, पर अपने "
                 "CA से पक्का कर लें।</li>"
                 "<li>परफ़्यूम और इत्र: 18%।</li></ul>"),
                ("कितना खर्च?",
                 '<div class="scroll"><table><tbody>'
                 "<tr><th>Free</th><td>₹0, हमेशा के लिए: रिपोर्ट, पुराने ग्राहकों को संदेश, "
                 "शिकायतों का विश्लेषण, GST बिल, अपनी वेबसाइट, 250 प्रोडक्ट तक</td></tr>"
                 f"<tr><th>Max</th><td>{esc(_max_price())} महीना: स्टॉक दोबारा मँगाने की चेतावनी, "
                 "सप्लायर को ऑर्डर, असीमित AI और अपना डोमेन</td></tr>"
                 "</tbody></table></div>"),
            ],
            "faqs": [
                ("पुराने ग्राहक वापस कैसे लाएँ?",
                 "जो ग्राहक पहले नियमित ख़रीदते थे और अब रुक गए हैं, उन्हें एक छोटा, निजी WhatsApp "
                 "संदेश भेजें: उनका नाम, उन्होंने क्या ख़रीदा था, और लौटने की एक वजह। एक बार भेजें, "
                 "और 30 दिन में कितने लौटे, यह गिनें। One Tap Manager यह सूची बनाता है और संदेश "
                 "लिख देता है।"),
                ("GST बिल कैसे बनाएँ?",
                 "हर लाइन पर प्रोडक्ट का HSN कोड और सही दर लगाएँ, बिल नंबर एक ही क्रम में रखें, और "
                 "ख़रीदार के राज्य के हिसाब से CGST और SGST या IGST लगाएँ। One Tap Manager यह अपने "
                 "आप करता है और महीने के अंत में GSTR-1 फ़ाइल देता है।"),
                ("क्या यह स्टॉक रजिस्टर की तरह काम करता है?",
                 "हाँ। हर प्रोडक्ट का स्टॉक साइज़ और रंग के हिसाब से रहता है, और अपनी वेबसाइट पर "
                 "ऑर्डर आते ही अपने आप घटता है।"),
                ("क्या यह हिंदी में चलता है?",
                 "हाँ। ऐप अंग्रेज़ी, हिंदी, तमिल और कन्नड़ में चलता है।"),
                ("क्या यह मुफ़्त है?",
                 "हाँ। Free प्लान की कोई समय-सीमा नहीं है और शुरू करने के लिए कार्ड नहीं चाहिए।"),
            ],
        },
    }


def _pages() -> dict[str, dict]:
    return {**_core_pages(), **_feature_pages(), **_for_pages(), **_compare_pages(),
            **_guide_pages(), **_hindi_pages()}


def paths() -> list[str]:
    return ["/guides"] + list(_pages().keys())


def sitemap_entries() -> list[tuple[str, str, str]]:
    """(path, priority, changefreq) for every page here, for main.sitemap."""
    out = [("/guides", "0.7", "weekly")]
    out += [(p, KINDS[d["kind"]][2], "monthly") for p, d in _pages().items()]
    return out


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
ul,ol{padding-left:20px;color:var(--ink-2)}
li{margin:0 0 6px}
.cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:600;
padding:11px 18px;border-radius:8px;margin:8px 0 0}
.crumbs{font-size:13.5px;color:var(--ink-3);margin:0 0 10px}
.crumbs a{text-decoration:none}
.more{border-top:1px solid var(--line);margin-top:36px;padding-top:18px}
.faq h3{font-size:16px;margin:18px 0 6px}
header.top{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline}
header.top nav{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:14px}
header.top nav a{font-weight:500;color:var(--ink-2)}
.tpl{background:var(--surface);border:1px solid var(--line);border-radius:12px 12px 12px 2px;
padding:10px 14px;margin:0 0 10px;max-width:560px}
.tpl p{margin:0;color:var(--ink)}
.calc{display:grid;gap:4px;background:var(--surface);border:1px solid var(--line);border-radius:8px;
padding:16px;margin:0 0 12px;max-width:520px}
.calc label{font-weight:600;color:var(--ink);font-size:14.5px;margin-top:8px}
.calc input{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:6px;
background:var(--bg);color:var(--ink);max-width:200px}
.calc .hint{font-size:13px;color:var(--ink-3)}
.calc button{justify-self:start;margin-top:12px;font:inherit;font-weight:600;background:var(--accent);
color:#fff;border:0;border-radius:8px;padding:10px 16px;cursor:pointer}
.result{border-left:4px solid var(--accent);padding:4px 0 4px 14px;margin:0 0 12px}
.hub h2{font-size:19px}
h2[id]{scroll-margin-top:72px}
"""

# Words the page chrome uses, per language.
_LABELS = {
    "en": {"guides": "Guides", "features": "Features", "pricing": "Pricing",
           "updated": "Last updated", "faq": "Common questions",
           "cta": "Start free, no card needed", "more": "Related", "all": "All guides",
           "skip": "Skip to the page", "hindi": "हिंदी"},
    "hi": {"guides": "गाइड", "features": "सुविधाएँ", "pricing": "कीमत",
           "updated": "आख़िरी बदलाव", "faq": "आम सवाल",
           "cta": "मुफ़्त शुरू करें, कार्ड की ज़रूरत नहीं", "more": "और पढ़ें",
           "all": "सभी गाइड", "skip": "पेज पर जाएँ", "hindi": "English"},
}
_HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
              "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]


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


def _software_schema(base: str) -> list[dict]:
    """The product and its two prices, from pricing.py. Used on /pricing."""
    p = _plans()
    return [{
        "@type": "SoftwareApplication", "@id": f"{base}/#app", "name": PRODUCT,
        "applicationCategory": "BusinessApplication", "operatingSystem": "Web browser",
        "url": f"{base}/", "publisher": {"@id": f"{base}/#org"},
        "inLanguage": ["en-IN", "hi-IN", "ta-IN", "kn-IN"],
        "offers": [
            {"@type": "Offer", "name": p["free"]["name"], "price": "0", "priceCurrency": "INR",
             "description": _INCLUDES["free"]},
            {"@type": "Offer", "name": p["max"]["name"], "price": str(p["max"]["price_inr"]),
             "priceCurrency": "INR", "description": _INCLUDES["max"]},
        ],
    }]


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


def _date(iso: str, lang: str = "en") -> str:
    y, m, d = iso.split("-")
    if lang == "hi":
        return f"{int(d)} {_HI_MONTHS[int(m) - 1]} {y}"
    return _human(iso)


def _shell(path: str, base: str, title: str, description: str, body: str, ld: list,
           lang: str = "en", robots: str = "index, follow, max-snippet:-1",
           alternates: bool = False, og_type: str = "article") -> str:
    graph = _json_ld({"@context": "https://schema.org", "@graph": ld})
    L = _LABELS[lang]
    other = "/" if lang == "hi" else "/hi"
    alt = hreflang_links(base) if alternates else ""
    return f"""<!DOCTYPE html>
<html lang="{'hi-IN' if lang == 'hi' else 'en-IN'}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)} | {PRODUCT}</title>
<meta name="description" content="{esc(description)}" />
<meta name="robots" content="{robots}" />
<link rel="canonical" href="{esc(base + path)}" />
{alt}<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="alternate" type="text/plain" href="/llms.txt" title="Summary for AI assistants" />
<meta property="og:type" content="{og_type}" />
<meta property="og:site_name" content="{PRODUCT}" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(description)}" />
<meta property="og:url" content="{esc(base + path)}" />
<meta property="og:image" content="{esc(base)}/og-image.png" />
<meta property="og:locale" content="{'hi_IN' if lang == 'hi' else 'en_IN'}" />
<meta property="article:modified_time" content="{UPDATED}" />
<script type="application/ld+json">{graph}</script>
<style>{_CSS}</style>
</head>
<body>
<a class="skip" href="#doc">{L['skip']}</a>
<div class="wrap">
<header class="top"><a href="/">{PRODUCT}</a>
<nav aria-label="Site"><a href="/guides#features">{L['features']}</a><a href="/pricing">{L['pricing']}</a><a href="/guides">{L['guides']}</a><a href="{other}" lang="{'en' if lang == 'hi' else 'hi'}">{L['hindi']}</a></nav></header>
<main id="doc">
{body}
</main>
</div>
</body>
</html>"""


def _others(path: str, d: dict) -> str:
    L = _LABELS[d.get("lang", "en")]
    same = [(p, x) for p, x in _pages().items() if x["kind"] == d["kind"] and p != path]
    if d["kind"] == "hi":
        same = [(p, x) for p, x in _pages().items() if x["kind"] in ("for", "product")]
    items = "".join(f'<li><a href="{esc(p)}">{esc(x["title"])}</a></li>' for p, x in same)
    items += f'<li><a href="/guides">{L["all"]}</a></li>'
    return f'<nav class="more" aria-label="{L["more"]}"><h2>{L["more"]}</h2><ul>{items}</ul></nav>'


def render(path: str, base: str, params: dict | None = None) -> str | None:
    d = _pages().get(path)
    if not d:
        return None
    params = {k: v for k, v in (params or {}).items() if isinstance(v, str)}
    lang = d.get("lang", "en")
    L = _LABELS[lang]
    url = base + path
    has_tool = any(callable(h) for _, h in d["sections"])
    faqs = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in d["faqs"])
    sections = "".join(
        f'<h2 id="{_slug(h)}">{esc(h)}</h2>{html(params) if callable(html) else html}'
        for h, html in d["sections"])
    body = (f'<p class="crumbs"><a href="/">{PRODUCT}</a> / <a href="/guides">{L["guides"]}</a></p>'
            f"<h1>{esc(d['title'])}</h1>"
            f'<p class="meta">{L["updated"]} <time datetime="{UPDATED}">{_date(UPDATED, lang)}</time></p>'
            f'<div class="answer"><p>{esc(d["answer"])}</p></div>'
            f"{sections}"
            f'<section class="faq"><h2>{L["faq"]}</h2>{faqs}</section>'
            f'<p><a class="cta" href="/?signup=1">{L["cta"]}</a></p>'
            f"{_others(path, d)}")
    in_lang = "hi-IN" if lang == "hi" else "en-IN"
    ld = [
        _org(base),
        {"@type": "WebPage", "@id": url, "url": url, "name": d["title"],
         "description": d["description"], "inLanguage": in_lang,
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
    if d["kind"] == "guide":
        ld.append({"@type": "Article", "headline": d["title"], "description": d["description"],
                   "inLanguage": in_lang, "datePublished": PUBLISHED, "dateModified": UPDATED,
                   "author": {"@id": f"{base}/#org"}, "publisher": {"@id": f"{base}/#org"},
                   "mainEntityOfPage": {"@id": url}, "image": f"{base}/og-image.png"})
    if d.get("schema"):
        ld += d["schema"](base)
    # A calculator answer is the same page with numbers in the address. Keep it
    # out of the index so those copies never compete with the page itself.
    robots = ("noindex, follow" if has_tool and params
              else "index, follow, max-snippet:-1")
    return _shell(path, base, d.get("seo_title") or d["title"], d["description"], body, ld,
                  lang=lang, robots=robots, alternates=(path == "/hi"))


def hub(base: str) -> str:
    pages = _pages()
    groups = ""
    for kind, (anchor, heading, _) in KINDS.items():
        items = "".join(f'<li><a href="{esc(p)}">{esc(d["title"])}</a><br />'
                        f'<span class="meta">{esc(d["description"])}</span></li>'
                        for p, d in pages.items() if d["kind"] == kind)
        if items:
            groups += f'<h2 id="{anchor}">{esc(heading)}</h2><ul>{items}</ul>'
    body = (f"<h1>{PRODUCT} guides</h1>"
            f'<p class="meta">Last updated <time datetime="{UPDATED}">{_human(UPDATED)}</time></p>'
            f'<div class="answer"><p>{esc(ONE_LINE)} {esc(_price_line())}</p></div>'
            f'<div class="hub">{groups}</div>'
            f'<p><a class="cta" href="/?signup=1">Start free, no card needed</a></p>')
    ld = [_org(base),
          {"@type": "CollectionPage", "@id": f"{base}/guides", "url": f"{base}/guides",
           "name": f"{PRODUCT} guides", "dateModified": UPDATED,
           "hasPart": [{"@type": "WebPage", "url": base + p, "name": d["title"]}
                       for p, d in pages.items()]}]
    return _shell("/guides", base, "Guides for Indian sellers: features, pricing and how-tos",
                  ONE_LINE + " Every feature, who it is for, comparisons and practical guides.",
                  body, ld, og_type="website")


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
        f"{_max_price()} a month; credit packs that never expire. No fee on sales.",
        "- Languages: English, Hindi, Tamil, Kannada",
        "- Not related to other apps named One Tap or OneTap, or to Google One Tap sign-in.",
    ]
    if p["launch"]:
        lines.append("- During the launch period every feature is free on every account.")
    pages = _pages()
    for kind, (_, heading, _) in KINDS.items():
        if kind == "hi":
            heading = "Hindi"
        rows = [f"- [{d['title']}]({base}{path}): {d['description']}"
                for path, d in pages.items() if d["kind"] == kind]
        if rows:
            lines += ["", f"## {heading}", ""] + rows
    lines += ["", "## Features", ""]
    lines += [f"- {n}: {d}" for n, d, _ in _MODULES]
    if profiles():
        lines += ["", "## Official profiles", ""] + [f"- {u}" for u in profiles()]
    lines += ["", "## Optional", "",
              f"- [Legal pages]({base}/legal): privacy, terms, refunds, grievance contact",
              f"- [Start free]({base}/?signup=1)", ""]
    return "\n".join(lines)
