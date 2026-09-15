"""The legal pages, for One Tap Manager and for every seller's own shop.

WHY THIS IS ONE MODULE
----------------------
Four things pushed every policy into a single generator instead of a folder of
hand-written HTML.

1. **Two audiences, one set of rules.** One Tap Manager needs a privacy policy,
   terms, a refund policy and a grievance contact. So does every seller shop
   the builder publishes, with the SELLER's details rather than ours. Writing
   those twice guarantees they drift apart, and the second copy is always the
   stale one.

2. **A policy that names the wrong person is worse than no policy.** Every
   detail that identifies the operator lives in one config block. Nothing here
   invents a company name, an address or a contact. If a detail is missing the
   page says so plainly and `readiness()` refuses to call the site
   launch-ready, so a placeholder cannot reach a customer.

3. **The obligations are dated and they move.** India's rules changed twice in
   2026 alone, so every requirement below carries the rule it comes from and
   the date it was checked. A policy nobody can trace back to a rule is a
   policy nobody can maintain.

4. **Consistency is itself a compliance property.** Retention periods,
   grievance timelines and cancellation terms appear in several documents. A
   regulator reading two different numbers for the same thing has found a
   finding. Here they are constants, used everywhere.

WHAT THIS IS NOT
----------------
It is not legal advice, and it says so on every page. It is a careful, sourced
draft that covers the obligations research identified, written to be read by a
shopkeeper rather than a lawyer. Have it reviewed before it carries real money.

WHICH RULES THIS IS BUILT AGAINST  (checked 15 September 2026)
-------------------------------------------------------------
Live today:
  * IT Rules 2021, Rule 3(1)(a), as amended 20 Feb 2026. An intermediary must
    prominently publish its rules and regulations, privacy policy AND user
    agreement. Hosting seller shops makes this app an intermediary.
  * IT Rules 2021, Rule 3(2), as amended 20 Feb 2026. A named Grievance Officer,
    acknowledgement within 24 hours, resolution within 7 days. These are the
    strictest of the three overlapping regimes, so the app promises these.
  * IT Rules 2021, Rule 3(3) and 3(4), new on 20 Feb 2026. Synthetically
    generated audio or visual content produced on our own systems must be
    labelled clearly and prominently, with embedded metadata where feasible.
  * SPDI Rules 2011, Rules 4, 5 and 8, under s.43A IT Act. A published privacy
    policy is mandatory TODAY under this rule, not under DPDP. Sensitive
    personal data, which expressly includes passwords, needs consent and
    reasonable security practices.
  * Consumer Protection (E-commerce) Rules 2020, Rules 4 and 5. Legal name,
    address, working contact details, grievance officer, no pre-ticked consent,
    no cancellation charge after confirmation, refunds processed in a reasonable
    period, and for a marketplace the seller's own details on display.
  * Dark Patterns Guidelines 2023. Cancellation must be self-service and take
    no more steps than signing up did.
  * CERT-In Directions, 28 April 2022, under s.70B(6) IT Act. Six hours to
    report an incident, 180 days of logs held in India, clocks synced to NIC or
    NPL. Criminally enforceable, and the one small operators skip.
  * s.32 CGST Act. A person who is not registered under GST must not collect
    anything described as tax. While unregistered, no GST line and no GSTIN
    anywhere.

Dated, and diarised rather than pretended:
  * 1 January 2027. E-Commerce Amendment Rules 2026: annual dark-patterns
    self-audit and a displayed self-declaration, 30-day lowest-prior-price on
    any discount, ranking-factor disclosure.
  * Around May 2027. DPDP Act Phase 3: notice, consent, security safeguards,
    breach reporting, erasure and data-principal rights become enforceable,
    and the SPDI Rules fall away. The privacy policy is written so that day is
    a copy edit rather than a rewrite.

There is no Indian cookie-banner law. The consent banner in this app exists
because GA4 sets cookies and any EU or UK visitor brings the ePrivacy Directive
with them. See `consent_required()`.
"""
from __future__ import annotations

import logging
import os
from datetime import date

# The day the rules above were checked. Shown on every page, because a policy
# with no date is a policy nobody can audit.
_log = logging.getLogger(__name__)

REVIEWED_ON = "15 September 2026"

# ---------------------------------------------------------------------------
# Numbers that must agree everywhere they appear
# ---------------------------------------------------------------------------
# Grievance timelines: the strictest of the three overlapping regimes, so that
# one promise satisfies all of them. IT Rules say 24 hours and 7 days,
# E-commerce Rules say 48 hours and one month, DPDP will say 90 days.
ACK_HOURS = 24
RESOLVE_DAYS = 7

# Refund, as chosen by the operator. There is no statutory cooling-off period
# for digital services in India, so this is a promise rather than a minimum.
REFUND_DAYS = int(os.environ.get("REFUND_WINDOW_DAYS") or 7)
REFUND_PROCESS_DAYS = 7          # working days from approval to money leaving

# Retention. These appear in the privacy policy, the terms and the seller
# agreement, and they must be the same number in all three.
EXPORT_WINDOW_DAYS = 30          # after cancellation, to download your data
PURGE_AFTER_DAYS = 90            # then it is deleted
LOG_RETENTION_DAYS = 180         # CERT-In Directions 2022 require 180 days

# ---------------------------------------------------------------------------
# Who is operating this
# ---------------------------------------------------------------------------
PRODUCT_NAME = "One Tap Manager"

# Every one of these is required somewhere by Consumer Protection (E-commerce)
# Rule 4(2) or IT Rules Rule 3(2). None of them has a default, on purpose: a
# made-up address on a published policy is the single worst outcome here.
FIELDS = [
    ("LEGAL_NAME", "Legal name of the operator",
     "Your own full name if you have not registered a company. This is what "
     "Consumer Protection (E-commerce) Rule 4(2) calls the legal name."),
    ("BUSINESS_ADDRESS", "Full address of your place of business",
     "Rule 4(2) asks for the address of the head office and of any branch. A "
     "PO box is not enough. This will be publicly visible."),
    ("SUPPORT_EMAIL", "Customer care email",
     "Rule 4(2) requires a working email address."),
    ("SUPPORT_PHONE", "Customer care phone",
     "Rule 4(2) requires a telephone number. A mobile number is fine."),
    ("GRIEVANCE_NAME", "Name of the grievance officer",
     "IT Rules Rule 3(2) and E-commerce Rule 4(4) both require a named person. "
     "For a one-person business this is you."),
    ("GRIEVANCE_EMAIL", "Grievance email",
     "Monitored, because the takedown clock can be as short as two hours. A "
     "separate address such as grievance@ is better than your personal inbox."),
]


def business() -> dict:
    """The operator's details, as configured. Missing values come back empty."""
    d = {k.lower(): (os.environ.get(k) or "").strip() for k, _, _ in FIELDS}
    d["product"] = PRODUCT_NAME
    d["entity_type"] = (os.environ.get("ENTITY_TYPE") or "sole proprietorship").strip()
    d["gstin"] = (os.environ.get("GSTIN") or "").strip()
    d["state"] = (os.environ.get("BUSINESS_STATE") or "Karnataka").strip()
    d["city"] = (os.environ.get("BUSINESS_CITY") or "Bengaluru").strip()
    # A grievance officer designation is required but is not a secret, so it has
    # a sensible default for a one-person business.
    d["grievance_role"] = (os.environ.get("GRIEVANCE_ROLE")
                           or "Proprietor and Grievance Officer").strip()
    return d


def missing() -> list[dict]:
    """Which required details are not set yet, and why each one is needed."""
    b = business()
    return [{"key": k, "label": label, "why": why}
            for k, label, why in FIELDS if not b.get(k.lower())]


def ready() -> bool:
    """True when the legal pages can name a real operator."""
    return not missing()


def readiness() -> dict:
    """For /api/admin/health, so an unfinished policy blocks a launch."""
    gaps = missing()
    return {
        "ok": not gaps,
        "missing": gaps,
        "reviewed_on": REVIEWED_ON,
        "documents": [d["slug"] for d in DOCUMENTS],
        "note": ("Every required detail is set." if not gaps else
                 f"{len(gaps)} required detail(s) are not set, so the legal pages "
                 f"would publish with gaps in them. Set these in the environment "
                 f"before taking a payment from anybody."),
    }


# ---------------------------------------------------------------------------
# Cookies and consent
# ---------------------------------------------------------------------------
def analytics_id() -> str:
    return (os.environ.get("GA4_MEASUREMENT_ID") or "").strip()


def consent_required() -> bool:
    """Whether a consent banner has to appear at all.

    Honest answer, and it is narrower than most sites pretend. No Indian law
    requires a cookie banner. What requires one here is the combination of a
    tracker that sets cookies with the possibility of a visitor from the EU or
    UK, where the ePrivacy Directive needs consent BEFORE the tracker loads.

    So the banner is tied to whether a tracker is actually configured. With no
    GA4 id set, nothing non-essential loads, and a banner asking permission for
    nothing would be theatre.
    """
    return bool(analytics_id())


COOKIE_TABLE = [
    {"name": "cx_token", "kind": "Not a cookie. Stored in your browser.",
     "purpose": "Keeps you signed in. Without it you would have to type your "
                "password on every screen.",
     "category": "Strictly necessary", "life": "Until you sign out"},
    {"name": "cx_email", "kind": "Not a cookie. Stored in your browser.",
     "purpose": "Remembers which account this browser is signed into.",
     "category": "Strictly necessary", "life": "Until you sign out"},
    {"name": "cx_consent", "kind": "Not a cookie. Stored in your browser.",
     "purpose": "Remembers what you chose here, so you are not asked again.",
     "category": "Strictly necessary", "life": "12 months"},
    {"name": "cx_home_cache", "kind": "Not a cookie. Stored in your browser.",
     "purpose": "Keeps the last version of your home screen so it appears "
                "instantly instead of reloading. Your figures, on your device, "
                "never sent anywhere.",
     "category": "Strictly necessary", "life": "6 hours"},
    {"name": "_ga, _ga_*", "kind": "Cookie set by Google",
     "purpose": "Counts visits and tells us which pages are used. Only set if "
                "you allow it below.",
     "category": "Analytics", "life": "Up to 2 years"},
]


# ---------------------------------------------------------------------------
# The documents
# ---------------------------------------------------------------------------
# Each document is a list of (heading, [paragraphs]). Structure rather than
# HTML, so the same text can be rendered as a page, printed, or handed to a
# seller's own shop without re-writing it.
def _p(*parts: str) -> list[str]:
    return [x for x in parts if x]


def _identity_block(b: dict) -> list[str]:
    """Consumer Protection (E-commerce) Rule 4(2), in one paragraph."""
    if not ready():
        return ["These details are not configured on this deployment yet. "
                "The site is not ready to be published until they are."]
    tax = (f"GSTIN {b['gstin']}." if b["gstin"] else
           "Not registered under GST. No GST is charged or collected, and no "
           "tax is added to the prices shown.")
    return [
        f"{PRODUCT_NAME} is operated by {b['legal_name']}, a "
        f"{b['entity_type']} based in {b['city']}, {b['state']}, India.",
        f"Place of business: {b['business_address']}",
        f"Email: {b['support_email']}. Phone: {b['support_phone']}.",
        tax,
    ]


def privacy_doc() -> list[tuple[str, list[str]]]:
    b = business()
    return [
        ("Who we are", _identity_block(b)),
        ("What this covers", _p(
            f"This notice explains what {PRODUCT_NAME} does with personal data. "
            "It is published because the Information Technology (Reasonable "
            "Security Practices and Procedures and Sensitive Personal Data or "
            "Information) Rules, 2011 require it, and because Rule 3(1)(a) of "
            "the Information Technology (Intermediary Guidelines and Digital "
            "Media Ethics Code) Rules, 2021 requires an intermediary to publish "
            "a privacy policy.",
            "If you are a shopper who bought something from a shop built with "
            f"{PRODUCT_NAME}, this is not the notice you want. That shop is "
            "responsible for your data and publishes its own notice, linked in "
            "its footer. What we do in that situation is described under "
            "\"Shops built on this platform\" below.")),
        ("What we collect from you, and why", _p(
            "When you create an account: your email address, a password which "
            "is stored only as a one-way hash and never in a readable form, "
            "and your shop name. We need these to give you an account and to "
            "let you back into it.",
            "When you use the app: the sales and review files you upload, the "
            "products you enter, the photographs you upload, and the content "
            "the app generates for you. This is the substance of the service. "
            "Without it there is nothing to analyse.",
            "Automatically: your IP address, browser type, and the pages you "
            "opened, written to server logs. We keep these for "
            f"{LOG_RETENTION_DAYS} days because the CERT-In Directions of 28 "
            "April 2022 require us to, and we use them to find faults and to "
            "investigate abuse.",
            "If you pay us: the payment is handled by our payment gateway. We "
            "receive a confirmation and the last four digits of the instrument. "
            "We never see or store your full card number.")),
        ("What we do not do", _p(
            "We do not sell your data. We do not share it with advertisers. We "
            "do not use your customer lists to market anything to your "
            "customers on our own behalf.",
            "We do not train artificial intelligence models on your data. When "
            "the app generates a caption or a picture for you, your brief is "
            "sent to the model provider named below to produce that one result, "
            "and we do not add your content to any training set. If that ever "
            "changes we will ask you first, separately, and it will be "
            "something you switch on rather than something you fail to switch "
            "off.")),
        ("Who else sees it", _p(
            "The app runs on Render, which hosts the servers. Data is stored "
            "with Supabase. Email is sent through our configured mail provider. "
            "Payments are processed by Razorpay. When you ask the app to "
            "generate text, an image or a video, the brief for that request "
            "goes to the provider you picked at the time, which may be OpenAI, "
            "Google, Cloudflare or Hugging Face.",
            "Some of these providers process data outside India. Indian law "
            "currently permits this. We name them here so you know who is "
            "involved rather than discovering it later.")),
        ("How long we keep it", _p(
            "Your account data and your uploads stay while your account is "
            f"open. If you cancel, you have {EXPORT_WINDOW_DAYS} days to "
            f"download everything, and we delete it {PURGE_AFTER_DAYS} days "
            "after cancellation.",
            f"Server logs are kept for {LOG_RETENTION_DAYS} days as described "
            "above. Records we are required by law to retain, such as invoices, "
            "are kept for as long as that law requires.")),
        ("Your choices", _p(
            "You can ask us for a copy of what we hold about you, ask us to "
            "correct it, or ask us to delete it. You can withdraw any consent "
            "you gave, and withdrawing it is as easy as giving it was. Write to "
            f"{b.get('grievance_email') or 'the grievance officer named below'} "
            f"and we will acknowledge within {ACK_HOURS} hours and answer within "
            f"{RESOLVE_DAYS} days.",
            "Deleting your account data will end the service, because the "
            "service is the analysis of that data. We will tell you plainly "
            "what will stop working before we do it.")),
        ("Security", _p(
            "Passwords are hashed, not stored. Data is encrypted in transit. "
            "Uploaded datasets are encrypted before they are stored. Access to "
            "the production systems is limited and logged.",
            "No system is perfectly safe, and we will not pretend otherwise. If "
            "there is a breach that affects you we will tell you, and we will "
            "report it to CERT-In within six hours of becoming aware of it as "
            "the 2022 Directions require.")),
        ("Shops built on this platform", _p(
            "Sellers use this app to run their own shops. When a seller uploads "
            "their customer list, or a shopper places an order on a seller's "
            "shop, the seller decides why that data is collected and what it is "
            "used for. In the language the law uses, the seller is the data "
            "fiduciary and we handle the data on their instructions.",
            "We hold each seller to a written agreement that requires them to "
            "have a lawful basis for the data they upload, and we keep our own "
            "obligations for the security of it. If you are a shopper with a "
            "question about your order, the shop is the right first contact, and "
            "we will help if they do not.")),
        ("Children", _p(
            "This app is for people running a business and is not intended for "
            "anyone under 18. We do not knowingly collect data from children.")),
        ("Changes", _p(
            f"This notice was last reviewed on {REVIEWED_ON}. If we change it we "
            "will say so in the app, and we review it at least every three "
            "months because Rule 3(1)(f) of the IT Rules 2021 requires us to "
            "tell users about changes that often.")),
        ("Grievance officer", _p(
            f"{b.get('grievance_name') or 'Not configured'}, "
            f"{b.get('grievance_role')}. "
            f"Email {b.get('grievance_email') or 'not configured'}.",
            f"We acknowledge every complaint within {ACK_HOURS} hours and aim to "
            f"resolve it within {RESOLVE_DAYS} days, which is the timeline Rule "
            "3(2) of the IT Rules 2021 sets.")),
    ]


def terms_doc() -> list[tuple[str, list[str]]]:
    b = business()
    return [
        ("Who you are agreeing with", _identity_block(b)),
        ("What this is", _p(
            f"{PRODUCT_NAME} reads the sales data you give it and tells you what "
            "to restock, who to contact and what to fix. It can also build you a "
            "shop, write posts and generate images. By creating an account you "
            "agree to these terms, our privacy policy and our acceptable use "
            "rules, which together are the user agreement that Rule 3(1)(a) of "
            "the IT Rules 2021 requires us to publish.",
            "We record the date and the version of the terms you accepted.")),
        ("What you pay", _p(
            "The free plan is free. Paid plans are charged monthly at the price "
            "shown at the time you subscribe. Prices are all-inclusive. There is "
            "nothing added at checkout that was not on the pricing page.",
            "If we change a price we will tell you before it applies to you, and "
            "you can cancel instead.")),
        ("Cancelling", _p(
            "You can cancel from inside the app, in the same number of steps it "
            "took to subscribe. We will not ask you to telephone us or to email "
            "a request, because the Guidelines for Prevention and Regulation of "
            "Dark Patterns, 2023 treat that as a subscription trap, and because "
            "it is a rude way to treat somebody who has decided to leave.",
            "Cancelling stops the next renewal. Your access continues to the end "
            "of the period you have paid for. There is no cancellation fee.")),
        ("Refunds", _p(
            f"See the refund and cancellation policy. In short: {REFUND_DAYS} "
            "days, no reason needed.")),
        ("Your content stays yours", _p(
            "The products, photographs, customer lists and sales data you upload "
            "remain yours. You give us permission to store, resize and display "
            "them only so far as is needed to run the service for you, and to "
            "comply with the law.",
            "That permission does not extend to marketing, case studies, or "
            "training artificial intelligence models. Those would need you to "
            "agree separately and explicitly.")),
        ("What the app generates for you", _p(
            "As between you and us, you own the captions, images and videos the "
            "app generates for you, and we assign to you whatever rights we have "
            "in them.",
            "We cannot promise more than that, and you should know why. Indian "
            "copyright law does not clearly answer whether purely machine "
            "generated work attracts copyright at all, and the providers whose "
            "models we call impose their own conditions which pass through to "
            "you. So we do not warrant that generated output is protectable, or "
            "that it is original, or that it does not resemble something else.",
            "Generated output is produced automatically and nobody reviews it "
            "before you see it. It can be wrong, out of date, or unsuitable. "
            "Another user asking for something similar may get something "
            "similar. You are responsible for reading it, correcting it and "
            "approving it before you publish it, and for making sure what you "
            "publish is true and lawful.")),
        ("Generated images of real products", _p(
            "If you use the app to generate a picture of something you sell, the "
            "picture must show the thing you will actually ship. An image that "
            "flatters the product, invents a feature, or changes its colour or "
            "contents is a misleading advertisement under the Consumer "
            "Protection Act, 2019, and it is you the customer will complain "
            "about.",
            "Every image the app generates is labelled as generated by "
            "artificial intelligence, and carries that marking in the file as "
            "well as on the picture. Rule 3(3) of the IT Rules 2021, as amended "
            "on 20 February 2026, requires us to do that. You must not remove "
            "the label.")),
        ("The insights are estimates", _p(
            "The figures, forecasts and recommendations the app produces are "
            "statistical estimates from the data you supplied. They are for "
            "information. They are not financial, tax, legal or business advice, "
            "they are not guarantees, and they are only as good as the data "
            "behind them. Decisions you take are yours.")),
        ("Service as it is", _p(
            "We provide the service as it is and as it is available. We do not "
            "promise it will be uninterrupted or free of faults, and we do not "
            "offer an uptime guarantee. We will tell you honestly when something "
            "is broken.")),
        ("Limits on what we owe you", _p(
            "Our total liability to you for anything arising out of these terms "
            "is limited to the fees you paid us in the twelve months before the "
            "claim. We are not liable for lost profits, lost revenue, lost "
            "goodwill, lost data or business interruption.",
            "Those limits do not apply to death or personal injury, to fraud, or "
            "to wilful misconduct or gross negligence, and nothing in these "
            "terms removes a right you have under the Consumer Protection Act, "
            "2019 that cannot be removed by agreement.")),
        ("When we can suspend or close an account", _p(
            "Immediately, if the account is being used for something illegal or "
            "is putting the service or other users at risk, or if we are ordered "
            "to by a court or an authority.",
            "Otherwise with notice and a reasonable chance to put it right: "
            "non-payment after a grace period, or a breach of the acceptable use "
            "rules.",
            f"You can close your account whenever you like. After closure you "
            f"have {EXPORT_WINDOW_DAYS} days to download your data, and we "
            f"delete it after {PURGE_AFTER_DAYS} days.")),
        ("If you sell through a shop built here", _p(
            "Running a shop on this platform makes you responsible for what you "
            "sell and what you say about it. Before your shop goes live you give "
            "us a written undertaking that your descriptions and images "
            "correspond to the actual goods, which Rule 5(1) of the Consumer "
            "Protection (E-commerce) Rules, 2020 requires us to hold.",
            "You must publish your own legal name, address, contact details and "
            "grievance officer on your shop, along with your return, refund and "
            "delivery policies, the total price with every charge broken out, and "
            "the country of origin. The app gives you fields for all of these and "
            "will not let you publish without them, because the omission would be "
            "our violation as much as yours.",
            "You remain responsible for your customers' data. We handle it on "
            "your instructions, and you confirm you have a lawful basis for "
            "everything you upload.")),
        ("Law and where disputes go", _p(
            "These terms are governed by the laws of India, and the courts at "
            f"{b.get('city') or 'Bengaluru'}, {b.get('state') or 'Karnataka'} "
            "have jurisdiction.",
            "If you are a consumer, that does not take away your right to go to "
            "a consumer commission where you live. Before anything formal, "
            "please write to the grievance officer. Most things are a "
            "misunderstanding and can be fixed in a day.")),
        ("Changes to these terms", _p(
            f"Last reviewed {REVIEWED_ON}. We will tell you in the app when "
            "these terms change, and at least once every three months as Rule "
            "3(1)(c) and 3(1)(f) of the IT Rules 2021 require.")),
    ]


def refund_doc() -> list[tuple[str, list[str]]]:
    b = business()
    return [
        ("The short version", _p(
            f"Full refund within {REFUND_DAYS} days of a charge. No reason "
            "needed. Cancel yourself, in the app, any time.")),
        ("How to cancel", _p(
            "Open Settings and choose to cancel your plan. It takes the same "
            "number of steps as subscribing did. You will not be asked to "
            "telephone anyone or to explain yourself.",
            "Cancelling stops the next renewal. You keep access until the end of "
            "the period you already paid for. There is no cancellation charge, "
            "which Rule 4(8) of the Consumer Protection (E-commerce) Rules, 2020 "
            "would not permit in any case.")),
        ("How to get a refund", _p(
            f"Write to {b.get('support_email') or 'support'} within "
            f"{REFUND_DAYS} days of the charge and ask. We do not ask why.",
            f"Approved refunds go back to the way you paid, and we send them "
            f"within {REFUND_PROCESS_DAYS} working days of approving them. Your "
            "bank usually takes a further five to ten working days to show it.")),
        ("What is not refundable", _p(
            f"Charges older than {REFUND_DAYS} days, unless something went wrong "
            "at our end, in which case write to us and we will sort it out.",
            "Credit packs that have already been spent. Unspent credits can be "
            "refunded.")),
        ("The free plan", _p(
            "The free plan is free and does not turn into a paid plan on its "
            "own. We will never start charging you without asking you to choose "
            "a paid plan first.")),
        ("If we cancel", _p(
            "If we close your account for a reason that is not your fault we "
            "will refund the unused part of your period.")),
        ("Complaints", _p(
            f"{b.get('grievance_name') or 'The grievance officer'}, "
            f"{b.get('grievance_email') or 'not configured'}. Acknowledged "
            f"within {ACK_HOURS} hours, resolved within {RESOLVE_DAYS} days.")),
    ]


def cookies_doc() -> list[tuple[str, list[str]]]:
    if consent_required():
        opening = _p(
            "We use a small amount of browser storage to keep you signed in, and "
            "Google Analytics to count visits. The analytics only runs if you "
            "allow it, and nothing is loaded before you choose.",
            "You can change your mind at any time using the cookie settings link "
            "in the footer.")
    else:
        opening = _p(
            "We do not use any analytics, advertising or tracking tools, and we "
            "do not set any cookies at all.",
            "What we do use is your browser's own storage, to keep you signed in "
            "and to make the app open quickly. That information stays on your "
            "device. Because none of it is used to track you, there is nothing "
            "here for you to consent to, and we are not going to interrupt you "
            "with a banner asking permission for nothing.")
    return [
        ("What we use", opening),
        ("The full list", _p(
            "Every item of storage this site uses is listed on this page, with "
            "what it is for and how long it lasts. See the table below.")),
        ("Why there is no Indian cookie law to cite", _p(
            "There is not one. No Indian statute or rule requires a cookie "
            "banner, and neither the Digital Personal Data Protection Act, 2023 "
            "nor its 2025 Rules mention cookies. Anyone who tells you otherwise "
            "is selling you an interpretation.",
            "What does apply: Rule 4(9) of the Consumer Protection (E-commerce) "
            "Rules, 2020 bans pre-ticked consent boxes, and we do not use any. "
            "If you are visiting from the European Union or the United Kingdom, "
            "the ePrivacy Directive requires your permission before a "
            "non-essential cookie is set, which is why the choice appears "
            "before anything loads rather than after.")),
        ("Fonts and other third parties", _p(
            "We serve our own fonts from our own servers. We do not embed "
            "Google Fonts, because doing so would send your IP address to "
            "Google before you had any say in it.")),
    ]


def acceptable_use_doc() -> list[tuple[str, list[str]]]:
    return [
        ("The rules", _p(
            "These are the rules and regulations Rule 3(1)(a) of the IT Rules "
            "2021 requires us to publish. Breaking them can get your account "
            "suspended.")),
        ("Do not host or publish", _p(
            "Anything that belongs to someone else and that you do not have "
            "permission to use. Anything obscene, or involving children. "
            "Anything that invades somebody's privacy, defames them, or "
            "impersonates them. Anything unlawful, or that misleads people about "
            "where it came from. Anything that threatens the unity, integrity or "
            "security of India, or its relations with other states. Software "
            "viruses, or anything designed to damage a computer.",
            "This list is the one set out in Rule 3(1)(b) of the IT Rules 2021, "
            "and we are required to make reasonable efforts to keep it off the "
            "platform.")),
        ("Do not sell", _p(
            "Prescription medicines, drugs, tobacco, alcohol, weapons, wildlife "
            "products, or counterfeits. If your category needs a licence, such "
            "as food under the Food Safety and Standards Act, you must hold it "
            "and give us the number before you list.")),
        ("Do not misuse the generated content", _p(
            "Do not remove the artificial intelligence label from a generated "
            "image. Do not generate a picture of a product you do not sell as "
            "shown. Do not generate synthetic depictions of real people.")),
        ("Do not misuse the platform", _p(
            "No unsolicited bulk messages, which are also a problem under the "
            "Telecom Commercial Communications Customer Preference Regulations. "
            "No scraping, no reverse engineering, no working around rate limits. "
            "Do not upload personal data you have no lawful basis to hold.")),
        ("How we enforce this", _p(
            "We may remove content, suspend a shop, or close an account. Where "
            "we are ordered to remove something by a court or an authority we "
            "must act within three hours, and for intimate imagery or "
            "impersonation within two hours, so we act first and discuss "
            "afterwards. We keep removed content for 180 days, as required.",
            "If you think we got it wrong, write to the grievance officer.")),
    ]


def grievance_doc() -> list[tuple[str, list[str]]]:
    b = business()
    return [
        ("Who to contact", _p(
            f"{b.get('grievance_name') or 'Not configured'}, "
            f"{b.get('grievance_role')}.",
            f"Email: {b.get('grievance_email') or 'not configured'}.",
            f"Post: {b.get('business_address') or 'not configured'}.")),
        ("What happens when you write", _p(
            f"We acknowledge within {ACK_HOURS} hours, with a copy of your "
            "complaint as we recorded it so you can check we understood it.",
            f"We resolve within {RESOLVE_DAYS} days. That is the timeline Rule "
            "3(2) of the IT Rules 2021 sets, and it is shorter than the "
            "Consumer Protection (E-commerce) Rules require, so it is the one we "
            "promise.")),
        ("If it is urgent", _p(
            "Content that impersonates someone, or intimate imagery shared "
            "without consent, is removed within two hours of a valid complaint. "
            "Put URGENT in the subject line.")),
        ("If we do not fix it", _p(
            "You can take a consumer complaint to the National Consumer Helpline "
            "on 1915, or to the consumer commission where you live. We would "
            "much rather you gave us a chance first.")),
    ]


DOCUMENTS = [
    {"slug": "privacy", "title": "Privacy Policy", "build": privacy_doc,
     "summary": "What we collect, why, who else sees it, and how to get it back."},
    {"slug": "terms", "title": "Terms of Use", "build": terms_doc,
     "summary": "What you are agreeing to, and what we owe each other."},
    {"slug": "refunds", "title": "Refund and Cancellation Policy", "build": refund_doc,
     "summary": f"{REFUND_DAYS} days, no reason needed, cancel yourself."},
    {"slug": "cookies", "title": "Cookies and Browser Storage", "build": cookies_doc,
     "summary": "Everything this site stores on your device."},
    {"slug": "acceptable-use", "title": "Acceptable Use", "build": acceptable_use_doc,
     "summary": "What may not be hosted, sold or generated here."},
    {"slug": "grievance", "title": "Grievance Officer", "build": grievance_doc,
     "summary": f"Who to write to, and the {ACK_HOURS} hour and {RESOLVE_DAYS} day promise."},
]


def document(slug: str) -> dict | None:
    d = next((x for x in DOCUMENTS if x["slug"] == slug), None)
    if not d:
        return None
    return {"slug": d["slug"], "title": d["title"], "summary": d["summary"],
            "reviewed_on": REVIEWED_ON, "sections": d["build"](),
            "complete": ready(), "missing": missing(),
            "cookie_table": COOKIE_TABLE if slug == "cookies" else []}


def index() -> dict:
    """The legal hub, and the footer identity block Rule 4(2) asks for."""
    b = business()
    return {
        "product": PRODUCT_NAME,
        "reviewed_on": REVIEWED_ON,
        "documents": [{"slug": d["slug"], "title": d["title"],
                       "summary": d["summary"]} for d in DOCUMENTS],
        "identity": _identity_block(b),
        "complete": ready(),
        "missing": missing(),
    }


# ---------------------------------------------------------------------------
# Seller shops
# ---------------------------------------------------------------------------
# A seller's shop needs its OWN policies naming the SELLER, because the seller
# is who the shopper is buying from. Consumer Protection (E-commerce) Rule 5(4)
# makes displaying those details our duty as the platform, and Rule 6 makes the
# policies the seller's duty. Neither is satisfied by pointing at ours.
SELLER_REQUIRED = [
    ("legal_name", "Your legal name or registered business name"),
    ("address", "Your full business address"),
    ("email", "A customer care email"),
    ("phone", "A customer care phone number"),
    ("grievance_name", "Who handles complaints"),
]

REFUND_CHOICES = [
    {"id": "7day", "label": "7 days, no reason needed",
     "blurb": "Return anything within 7 days of delivery for a full refund. You "
              "pay return shipping only if the item was faulty.",
     "days": 7},
    {"id": "14day", "label": "14 days, no reason needed",
     "blurb": "Return anything within 14 days of delivery for a full refund.",
     "days": 14},
    {"id": "exchange", "label": "Exchange or replace only",
     "blurb": "Exchange or replacement within 7 days. No money back unless the "
              "item arrived faulty or was not what was ordered.",
     "days": 7},
    {"id": "faulty", "label": "Only if faulty or wrong",
     "blurb": "Refund or replacement if the item is faulty, damaged, or not "
              "what was ordered. Tell us within 48 hours of delivery.",
     "days": 2},
]


def refund_choice(choice_id: str) -> dict:
    return next((c for c in REFUND_CHOICES if c["id"] == choice_id),
                REFUND_CHOICES[0])


def seller_missing(legal: dict) -> list[dict]:
    """Which of the seller's required details are still blank."""
    legal = legal or {}
    return [{"key": k, "label": label} for k, label in SELLER_REQUIRED
            if not str(legal.get(k) or "").strip()]


def seller_docs(shop_name: str, legal: dict) -> list[dict]:
    """The three documents a shop must publish, in the shop's own voice.

    Deliberately short. A shopper buying a wallet will not read four thousand
    words, and a policy nobody reads protects nobody. These say the required
    things plainly and stop.
    """
    legal = legal or {}
    shop = shop_name or "This shop"
    who = str(legal.get("legal_name") or "").strip()
    addr = str(legal.get("address") or "").strip()
    email = str(legal.get("email") or "").strip()
    phone = str(legal.get("phone") or "").strip()
    gname = str(legal.get("grievance_name") or "").strip()
    gstin = str(legal.get("gstin") or "").strip()
    refund = refund_choice(str(legal.get("refund_policy") or "7day"))

    identity = _p(
        f"{shop} is run by {who}." if who else "",
        f"Address: {addr}" if addr else "",
        f"Email: {email}" if email else "",
        f"Phone: {phone}" if phone else "",
        (f"GSTIN: {gstin}" if gstin else
         "Not registered under GST. No tax is added to the prices shown."),
    )

    return [
        {"slug": "privacy", "title": "Privacy Policy", "sections": [
            ("Who we are", identity),
            ("What we collect", _p(
                "When you place an order: your name, phone number, email "
                "address and delivery address. We need these to send you what "
                "you bought and to tell you where it is.",
                "If you create an account: the same details, plus a password "
                "stored only as a one-way hash.",
                "We do not collect anything we do not need for your order.")),
            ("Who else sees it", _p(
                "The courier who delivers your order. The payment provider, if "
                "you paid online, which handles your card details directly so "
                "we never see them.",
                f"This shop is built with {PRODUCT_NAME}, which runs the website "
                "and stores the order on our behalf under a written agreement. "
                "They do not use your details for their own marketing.")),
            ("How long we keep it", _p(
                "As long as we need it for your order, our accounts and our tax "
                "records.")),
            ("Your choices", _p(
                f"Write to {email or 'us'} to ask for a copy of what we hold, to "
                "correct it, or to ask us to delete it. We will reply within "
                f"{RESOLVE_DAYS} days.")),
            ("Complaints", _p(
                f"{gname or 'The owner'} handles complaints. "
                f"Write to {email or 'us'}. We acknowledge within "
                f"{ACK_HOURS} hours and aim to resolve within "
                f"{RESOLVE_DAYS} days.")),
        ]},
        {"slug": "terms", "title": "Terms of Sale", "sections": [
            ("Who you are buying from", identity),
            ("Prices", _p(
                "The price shown for each item is the full price. Delivery is "
                "shown separately before you pay, and the total on the checkout "
                "page is what you will be charged. Nothing is added afterwards.")),
            ("Orders", _p(
                "An order is confirmed when we accept it. If something is out of "
                "stock we will tell you and refund you rather than sending a "
                "substitute you did not ask for.")),
            ("Delivery", _p(
                "We dispatch as quickly as we can and will give you a tracking "
                "reference. Delivery times are estimates, not promises, because "
                "the courier is not us.")),
            ("Cancelling and returning", _p(refund["blurb"])),
            ("If something is wrong", _p(
                f"Write to {email or 'us'}. Under the Consumer Protection Act, "
                "2019 you are entitled to a remedy if what arrived is faulty, "
                "not as described, or not what you ordered, and we will provide "
                "one.")),
            ("Complaints", _p(
                f"{gname or 'The owner'}, {email or 'not configured'}. "
                f"Acknowledged within {ACK_HOURS} hours.")),
        ]},
        {"slug": "refunds", "title": "Returns and Refunds", "sections": [
            ("Our policy", _p(refund["blurb"])),
            ("How to start a return", _p(
                f"Write to {email or 'us'} with your order number and what is "
                "wrong. We will tell you where to send it.")),
            ("When you get your money", _p(
                f"Once we have the item back and it is as described, we refund "
                f"to the way you paid within {REFUND_PROCESS_DAYS} working days. "
                "Your bank may take another five to ten working days to show "
                "it.",
                "For cash on delivery orders we will ask for bank details to "
                "send the refund to.")),
            ("What cannot be returned", _p(
                "Items made or personalised to your order, and anything "
                "damaged after delivery.")),
            ("Complaints", _p(
                f"{gname or 'The owner'}, {email or 'not configured'}, within "
                f"{ACK_HOURS} hours.")),
        ]},
    ]

# ---------------------------------------------------------------------------
# Recording consent
# ---------------------------------------------------------------------------
# Both the DPDP Act (s.6, once its substantive provisions commence) and the GDPR
# (Article 7(1), which applies to any EU visitor who signs up) come down to the
# same practical thing: being able to DEMONSTRATE consent rather than assert it.
# "They must have ticked the box, the box is there" is not a record.
#
# So a record is written at signup: who, when, what they agreed to, which version
# of the notice was on screen, and separately whether they opted in to marketing.
# Append-only, one JSON object per line, in the same directory the error ring
# buffer uses. Deliberately plain: a regulator's question is answered by a text
# file that can be read without this application running.
#
# What is NOT recorded here: anything about the person beyond their email and
# their answer. Not their IP address, because logging an IP against a consent
# record turns a compliance artefact into a location history, and nothing in
# either statute asks for it.
CONSENT_NOTICE_VERSION = 1


def consent_log_path() -> str:
    from backend.core import auth
    return os.path.join(auth.BASE_DIR, "consents.jsonl")


def record_consent(email: str, terms: bool, privacy: bool,
                   marketing: bool = False, source: str = "signup") -> dict:
    """Write one consent record. Never raises: a failure here must not stop an
    account being created, because the alternative is a seller who cannot sign
    up at all. It logs loudly instead, and the health report shows the file."""
    import datetime as _dt
    import json as _json
    rec = {
        "email": (email or "").strip().lower(),
        "at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "notice_version": CONSENT_NOTICE_VERSION,
        "source": source,
        "agreed": {"terms": bool(terms), "privacy": bool(privacy)},
        "marketing_opt_in": bool(marketing),
        "documents": {"terms": "/legal/terms", "privacy": "/legal/privacy"},
        "reviewed_on": REVIEWED_ON,
    }
    try:
        path = consent_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps(rec, ensure_ascii=False) + "\n")
        rec["stored"] = True
    except OSError as e:
        _log.warning("could not write the consent record: %s", e)
        rec["stored"] = False
        rec["error"] = str(e)
    return rec


def consents_for(email: str) -> list[dict]:
    """Every consent this person has given, newest last. Used by the data-export
    route, because "what did I agree to" is one of the things a person is
    entitled to be told."""
    import json as _json
    email = (email or "").strip().lower()
    out = []
    try:
        with open(consent_log_path(), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                except ValueError:
                    continue
                if rec.get("email") == email:
                    out.append(rec)
    except OSError:
        pass
    return out
