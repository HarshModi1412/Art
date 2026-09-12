# One Tap Manager

**Connect what you already sell on. Get told what to fix.**

An operations tool for small Indian sellers — clothing, jewellery, perfume.
It reads the sales they already make (marketplace exports, POS files, their own
storefront) and answers the one question a seller opens a dashboard with: *what
should I do this morning?* Restock these four. Win back these twelve. Fix this
complaint theme. Then it does most of it for them.

FastAPI + vanilla-JS SPA. No Streamlit dependency anywhere.

Internal identifiers (`cx_*` storage keys, `CAFEX_DATA_DIR`, folder names) still
carry the old CafeX name on purpose — renaming them would break every existing
login, saved dataset and deployment.

## Architecture

```
backend/
  main.py            FastAPI app — all REST endpoints + serves the frontend
  core/
    auth.py          Login (user.csv) + rate limiting (usage_logs.csv, 5 uses / 5h)
    mapper.py        Column mapping: suggest -> user confirms -> Transactions df
    analytics.py     Sales analytics, subcategory trends, RFM segmentation
    ai.py            GPT Business Analyst (BA.py) + Chatbot (chatbot2.py) ports
  static/
    index.html       Single-page app (Instructions/Mapping/Analytics/SubCategory/RFM/Analyst AI/Chatbot)
    app.js           Routing, upload, Plotly.js rendering, auth, chat
    styles.css       Original dark-navy identity, rebuilt as a design system
data/
  user.csv           email,password  (demo@cafex.com / demo123 included)
  usage_logs.csv     created automatically
```

## What changed from Streamlit

| Streamlit | Web app |
|---|---|
| `st.session_state` | Browser session id header + login bearer token; data held server-side per session |
| `st.file_uploader` | `POST /api/upload` with drag-and-drop UI |
| Sidebar radio pages + `st.rerun()` | Client-side SPA router — no full-page reruns |
| `st.secrets["OPENAI_API_KEY"]` | `OPENAI_API_KEY` environment variable |
| `st.plotly_chart(fig)` | Backend returns JSON chart data; Plotly.js renders it |
| `@st.cache_data` on LLM calls | `functools.lru_cache` keyed on the same prompt/df-hash |

All business logic is preserved: same login flow, same 5-per-5-hour rate limits,
same GPT models (`gpt-4.1-mini`), same prompts, same JSON-extraction and chart-spec
logic from BA.py, same first-message "3 profit tips" behavior and "X vs Y"
auto-chart detection from chatbot2.py.

## Website Builder (each seller gets one storefront)

A seller builds their own selling website from the **Website Builder** app in
Smart mode, and every order it takes flows back into the same analytics that
uploads and marketplace connectors feed.

```
backend/core/
  sitebuilder.py   8 themes, 20 fonts, the site document, handle index
  storefront.py    shopper accounts, cart pricing, orders, the sales mirror
Smart CafeX/storefront/
  store.html/.css/.js   the public shop — one page app, theme-driven
supabase/site.sql       migration (additive; safe to re-run)
```

**Themes.** Eight, each a different website rather than a recolour — Studio,
Maison, Charge, Atelier, Lustre, Counter, Bloom and Obsidian — with their own
layout, type scale, palette and motion: fade-up reveals, headline word-rise,
mask reveals, vertical parallax, horizontal collection rails, pinned sections,
a scrolling claims band, image zoom, a shine sweep and drifting gradients.
Icons are a shared stroke set (`sitebuilder.ICONS`) rendered identically in the
storefront and the builder — no emoji anywhere.

**The editor.** Step three of the builder is the live site on the left and an
inspector on the right. Click a photo, a headline, the promise strip or the
footer on the site and the matching controls open beside it; change a control
and the canvas repaints in place — no reload, nothing saved until you say so.
The bridge is `postMessage` in both directions, and the canvas repaints from
`POST /api/site/resolve`, the same resolver the published site uses, so the
preview can never drift from the real thing. Entering this step saves the draft
once, silently, so the canvas always has an address to load — a seller never has
to publish just to see their own site.

**Motion.** A brand curtain with a counter on first visit (once per session, and
never in the editor), a hairline down the left edge that fills as you read, a
spotlight product whose photo sticks while its copy scrolls past, figures that
count themselves up, a statement that brightens word by word tied to scroll
position, a scarcity bar that reads real stock, product cards that play their
clip on hover, and buttons that lean towards the cursor. All of it is opt-in per
theme and collapses cleanly under `prefers-reduced-motion` or the seller's
"Animation: none".

**Media.** One upload endpoint takes stills *and* video — hero clips, lookbook
clips and a per-product clip that plays on card hover (48MB for video, 10MB for
images). The builder nudges for the ones that matter most rather than leaving
empty slots unexplained.

**Type.** Three roles, each with its own family and a live preview: display,
body, and the small uppercase face on eyebrows, buttons and prices. Display size,
weight and letter-spacing plus body size are sliders on top. Every fixed label on
the page — section eyebrows and headings, the newsletter copy, the shop page
title — is editable text, not a string in the source.

**Layout.** The page width tracks the viewport (`min(1660px, 92vw)`, or edge to
edge) instead of stranding a fixed column on a wide monitor, with a real mobile
pass: a full-screen nav drawer, collapsed grids and rails, and stacked product
and checkout pages.

**Products.** The storefront sells the Product Management catalogue — the same
records, extended with a photo, gallery, description, key points, MRP and stock.
Every product carries a **List on my website** switch, on by default.

**Shoppers.** Accounts are per store: a shopper who signs up on one seller's site
is that seller's customer and nobody else's, and they appear in that seller's RFM
and Win-Back modules. A shopper must be signed in to place an order.

**Money.** The cart is priced server-side at checkout — flat shipping with a
free-shipping threshold, GST inclusive or added, optional minimum order, cash on
delivery. Orders deduct product stock and, where a product is linked to inventory
in Supply Management, the materials behind it.

**Orders.** The separate **Orders** app lists every order with its customer,
address and items, moves it through New → Confirmed → Packed → Shipped →
Delivered (or Cancelled, which returns the stock), and exports CSV.

**Listed Platforms.** The home screen opens with one strip for every place the
seller sells: their own site, Shopify and Amazon (live connectors), and Flipkart
and Myntra marked *Yet to come*. The switch on each live channel decides whether
its sales count in analytics — turning the site off removes its rows and turning
it back on restores them, with no double-counting either way.

Run `python scripts/test_website_builder.py` to exercise the whole loop against a
throwaway data directory, and `node scripts/test_storefront_render.js` to render
the storefront's own views (signed in, and as a guest) with a minimal DOM — the
guest-checkout crash was in the browser bundle, where no server-side test could
have seen it.

## Site structure

- `/` — marketing landing page (MSME positioning, multilingual sample-story wall, pricing)
- `/s/<handle>` — a seller's own storefront (Website Builder)
- `www.theirshop.com` — the same storefront on the seller's own domain
- `/app` — the analytics application

## Their own domain

A shop at `/s/kora-studio` reads as somebody's sub-page. The same shop at
`korastudio.com` is a business, and it is the address that goes on a card, a
label and a bio.

The seller types the domain they bought into step one of the builder.
`sitebuilder.normalise_domain()` strips the `https://`, the trailing slash and
the path people paste, refuses an IP or a bare word, and `claim_domain()` writes
it to a global index — one domain, one shop, checked before it is saved, so two
accounts cannot claim the same name. The bare domain and its `www` twin are
registered together and both resolve.

Serving it is a Host-header middleware in `main.py`: a request whose Host is not
the app's own looks the domain up, and a hit renders that storefront at `/`
(paths the app owns — `/api`, `/app`, `/static`, `/s` — are excluded first).
`window.__STORE_HANDLE__` is injected into the page, so `store.js` knows which
shop it is without a handle in the URL.

The builder shows the two DNS records to add (CNAME on `www`, ALIAS/ANAME on the
bare domain) and a **Check it** button that says what is actually wrong:
not resolving yet, resolving somewhere else, or resolving here but not accepted
by the host. On Render the last step is Settings → Custom Domains; DNS being
correct while the host has never heard of the domain is the failure that wastes
an afternoon, so it is named.

## Pricing model — two ways to pay, offered side by side

Everything is controlled by `backend/core/pricing.py` + the `LAUNCH_MODE` env var.

**While `LAUNCH_MODE=true` (default): nothing is gated.** Every account behaves
as Pro and the UI labels paid rows "Free during launch". The permanent free tier
is already written down, so flipping `LAUNCH_MODE=false` later is a non-event
rather than a surprise bill.

### 1. Subscription — three tiers, flat monthly, per outlet

| Tier | Price | What it adds |
|---|---|---|
| **Free** | ₹0 forever | Sales analytics, category + sub-category trends, RFM segments, the at-risk list, **your own selling website + orders** (with our footer line), 25 products, 5 AI uses/day |
| **Semi Pro** | ₹499 / month | Unlimited win-back campaigns, complaint analysis, positioning reports, the morning digest, 250 products, footer line removed, 50 AI uses/day |
| **Pro** | ₹999 / month | Supply Management (ROP, EOQ, safety stock, waste), PDF purchase orders, Position Strategy, unlimited AI/products/outlets, custom domain |

Gating lives in `FEATURE_MIN_PLAN`. Legacy `pro` / `chain` rows in `user.csv`
normalise to the Pro tier, so no existing account loses access.

### 2. Usage — credits that never expire

For sellers who work in bursts. `CREDIT_PACKS`: ₹299 / 100, ₹749 / 300,
₹1,999 / 1000. `CREDIT_COST` prices the heavy actions — a win-back campaign is
10, a positioning report 15, a complaint analysis 12, one AI run 1. Analytics,
the storefront and Orders stay free on either path.

Deliberately **not** priced per order and never a percentage of sales: that is
the tax sellers already pay their app stack, and the thing they complain about
loudest.

### What it replaces

`pricing.stack_comparison()` is the honest comparison the pricing page renders:
analytics ₹1,600 + inventory ₹2,500 + win-back ₹1,500 + reviews ₹1,200 + order
management ₹800 ≈ **₹7,600/month across four to six separate apps**, against
₹999 for Pro.

Gated endpoints return **HTTP 402** with a body from `billing.paywall()` that
names *both* routes past it — the tier that includes the feature, and what it
costs in credits — so a seller is never told a subscription is the only option.

## Payments (Razorpay)

1. Create an account at dashboard.razorpay.com -> Settings -> API Keys (start with **test mode** keys `rzp_test_...`)
2. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` env vars alongside `OPENAI_API_KEY`
3. `pip install razorpay`
4. Any "Buy" button in the in-app pricing modal -> `POST /api/pay/create-order {product}` ->
   Razorpay checkout opens -> on success the backend verifies the HMAC signature and
   records the purchase (or activates Chain). Test card: 4111 1111 1111 1111, any future expiry/CVV.
5. Switch to live keys + complete Razorpay KYC before charging real money.

Note: `chain_monthly` is a monthly-price checkout as a one-time payment. For
auto-recurring billing use Razorpay Subscriptions (create a Plan in the dashboard
and swap order.create for subscription.create).

## Today, and the morning digest

`backend/core/today.py` builds one ranked list of what needs the seller now —
new orders, items below their reorder point, customers slipping away, a rising
complaint theme, an unpublished site, unlinked platform names. Every item names
a module and a route, so each row is one click from the doing.

Two surfaces render that same list, which is why they can never disagree:

* the **Today** strip above the home tiles (`GET /api/today`)
* the **morning digest** (`POST /api/digest`, `/api/digest/test`, `/api/digest/run`)

Delivery goes through `backend/core/messaging.py`: **email works now** (set
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`; add
`SMTP_TLS=false` for a plain relay), and **WhatsApp is stubbed behind
`WHATSAPP_ENABLED`** — every message already carries a WhatsApp-shaped variant,
so connecting a BSP is one function (`_send_whatsapp`) and no caller changes.
With no SMTP configured, sends land in an in-memory outbox readable at
`GET /api/dev/outbox`, so password reset is testable on a fresh deploy.

Point a cron at `POST /api/digest/run` hourly; it sends only the sellers whose
chosen hour is now.

## Where uploaded media is saved

`backend/core/media.py`. Logos, hero art, hero clips, story stills, lookbook
clips and product photos.

**The bug this replaced.** Uploads were written to
`backend/../data/generated_images/` — a folder inside the checked-out
repository. Render rebuilds that from git on every deploy, so every image and
video a seller had ever uploaded was deleted on the next restart, while their
site document kept pointing at `/generated_images/<name>` and showed broken
slots. Re-uploading never fixed it, because the next deploy wiped those too.

**Where files go now**, in order of durability:

1. **Supabase Storage** — `SUPABASE_BUCKET` (default `user-datasets`) under a
   `media/` prefix. Survives redeploys, restarts and changing host. The bucket
   can stay private: bytes are served through the app, never by a public link.
2. **A local cache** under `CAFEX_DATA_DIR` (a mounted Render disk when one is
   attached, otherwise a temp dir), re-filled from Storage on a miss. Losing
   the cache costs a round-trip, never data.

The URL never changed — still `/generated_images/<filename>` — so every site
document and product row already saved keeps working. A file still sitting in
the old repo folder is served from there **and copied up to Storage as it is
read**, so the estate heals itself; `POST /api/media/backfill` does the whole
folder in one go.

`GET /api/media/status` reports whether uploads are actually durable on this
deployment, and the app shows a warning above every upload control when they
are not — rather than letting a seller find out from their own storefront.

Run `supabase/variants.sql` once: it adds the `video_url`, `options` and
`variants` columns plus a `media` index table.

## Payments on seller storefronts

`backend/core/store_payments.py`. **Each seller connects their own Razorpay
account** — money moves from the shopper straight into the seller's bank. We
never hold it, which keeps this out of payment-aggregator territory (collecting
on someone else's behalf and settling later means RBI licensing, KYC and a
settlement ledger).

Credentials live in `secrets_store` (Fernet-encrypted, same vault as the
marketplace connectors). The secret is write-only: the settings screen only ever
learns that a key exists and its last four characters.

**Partial COD.** A store can require a flat advance paid online, with the balance
in cash on delivery — the seller sets the rupee amount in the Checkout step.
This is the cheapest lever a small Indian seller has: Shipway's FY25 data puts
return-to-origin at 26% on COD against under 2% prepaid. `split_due()` is the
one place that decides what is owed now versus later, and it is recomputed
server-side at order time from the app's own prices, never from anything the
browser sent. An order with an unpaid advance is refused.

The signature is verified against the seller's own secret before any order is
created, so a forged callback cannot produce an order.

Run `pip install razorpay` (already in requirements.txt).

## Product Studio

`backend/core/studio.py`. The Content Creator generates a post from a topic and
a product *type*, which produces a stock-looking picture of "a perfume" rather
than of *their* perfume. Studio starts from what the seller actually has.

* **A brand profile, once per account** — what they make and why, who buys it,
  the look, the voice, the palette, what to never say. This is what keeps twenty
  generated posts feeling like one brand.
* **Per-product material** — photos, clips, the story, the materials, what makes
  it different, who it's for. `completeness()` scores it and names the single
  missing piece worth adding next, with the reason ("one photo makes one post;
  three makes a week of them") rather than an unexplained empty box.
* **`build_brief()`** assembles brand + product into one brief, so the caption
  and the image are generated against the same instructions. `image_prompt()`
  carries the brand's look, palette and refusals; `caption_prompt()` carries its
  voice.
* **Post angles** are derived from the material actually supplied — writing a
  story unlocks a story angle — so a seller can see why each was suggested.

Generated images are always flagged `image_is_generated` and labelled in the UI.
A seller should always know which of their pictures is a photograph of a real
object. Without an OpenAI key, captions fall back to a written template and
image generation is off — Studio is never a dead screen.

## Win-back campaigns that actually send

`backend/core/campaigns.py`. The app used to produce a list and an Excel file
and stop. Now it sends: **email over SMTP today**, and WhatsApp through a
provider the moment one is connected. Until then every recipient with a phone
number comes back as a **click-to-chat link** (`wa.me/<number>?text=…`) that
opens WhatsApp with the message already written — which genuinely works for a
seller with forty at-risk customers, and means the feature is honest on day one.

Sending records the campaign in `winback_proof` automatically, so "did you send
it" stops being something the seller has to remember to tick. A customer with
neither an email nor a phone is reported as skipped, not silently dropped.

## Inventory and Suppliers, split

They were one module, which meant changing a supplier's phone number required
opening every item they stock.

* **Inventory Management** — what you hold, what each sold product uses up
  (the recipe links), and waste.
* **Suppliers & Purchase Orders** — who you buy from, when to reorder, the PO PDF.

`supply.get_suppliers()` derives the supplier list from the items they stock and
`upsert_supplier()` writes an edit back across all of them, so there is one place
to change a phone number and no migration was needed. `detach_supplier()` returns
the item ids it cleared so the undo can put them back — once the last item is
cleared there is no supplier left to look up by name. Removing a supplier never
removes stock.

## Automatic replenishment (DOS → PO → supplier)

Every raw material is judged on **days of supply**:

    DOS = current stock ÷ average daily consumption

Consumption comes from product sales (website orders included, or the past
sales uploaded under Suppliers) over the last 30 days, converted to raw
material through the recipe links (`qty_per_unit` in *What each product
uses*). Each item stores its supplier's **lead time**.

**The trigger.** Every order placed (`storefront.place_order` →
`replenish.after_order`) re-checks the materials that order used; *Check stock
now* re-checks everything. The rule is `DOS ≥ 1.2 × lead time`. If it holds,
nothing happens. If not, a **draft PO** is made for that material at its DOQ,
grouped one PO per supplier; an item already on a draft/open/sent/shipped PO
is never ordered twice.

**DOQ (default order quantity)**, per item, saved in `supply_doq_table`:

1. the seller's own DOQ, if typed in the table — always wins;
2. else, once ordering cost (S) and holding cost (H) are entered **and** there
   is at least a month of sales: annual demand D = monthly consumption × 12,
   `EOQ = √(2DS/H)`; DOQ = EOQ if EOQ > MOQ, otherwise MOQ;
3. else the supplier's MOQ;
4. with no MOQ either, enough to cover 1.2 × lead time.

**Approval panel.** Each draft PO is a card with *Approve*, *Details* and
*Cancel*. Details shows every line with its DOS, lead time and editable
quantity, plus the email the content writer drafted (editable, *Rewrite with
AI*). Approve renders the PO PDF (`po_pdf.py`, supplier copy) and emails it as an
attachment to the address saved in the Supplier module — **from the seller's own
mailbox** once they connect it (`seller_mail.py`), otherwise from the server's
SMTP account with Reply-To set to the seller. With neither, the PO is marked
approved and the seller gets the PDF plus a ready-filled `mailto:` to send it
themselves.

Behaviour changes worth knowing: "below reorder" now means the DOS rule above
(the old safety-stock field is gone from the form), and approving the reorder
insight drafts POs through this same path instead of making order sheets.

## Forms are step-by-step

*Add item* lives only in Inventory Management. It is a three-step form
(item → supplier → how much to order), with Next/Back and the submit button on
the last step only; the product is picked from Product Management and its name
can then be edited. *Add product* is the same shape in four steps (basics → photos &
copy → sizes & stock → on my site).

## Storefront sections

Featured, Spotlight and the product grid all used to slice the top of the same
list, so a ten-product catalogue looked like it was repeating itself down the
page. Products now carry `featured` and `spotlight` flags, set per product in
Product Management. If the seller has picked none, the site falls back to
automatic — and the spotlight avoids whatever the featured rail is already
showing, so the two blocks can never show the same thing.

## Where this product sits

Shopify has the right customer and sells the thinking as apps. Odoo has the
right depth and is built for a business with an implementation partner. This is
Shopify's customer served to Odoo's standard: one connected data model, entered
through a front door a jewellery seller with 40 SKUs can actually get through.

We do not have manufacturing, multi-warehouse, payroll or double-entry
accounting, and the landing page says so rather than implying otherwise.

## GST and billing

`backend/core/gst.py` holds the rates and rules, `invoices.py` holds the
records, `invoice_pdf.py` draws the document.

Rates reflect **GST 2.0** (Notification 09/2025-CT(R), effective 22 September
2025). Two numbers changed in a way that catches anyone working from older
knowledge: the apparel threshold moved from ₹1,000 to **₹2,500**, and above it
the rate is now **18%**, not 12%.

Rate resolution is deliberately **not** an HSN lookup table:

* apparel (Ch. 61/62/63) and footwear (Ch. 64) are **price-banded** per piece
  or pair, so ten ₹800 shirts on one bill are each 5%;
* Chapter 33 has **named carve-outs inside a heading** — 3304 is 18% but kajal,
  kumkum, bindi and face powder are 5%; 3305 is 18% but hair oil and shampoo
  are 5%.

Other decisions worth knowing before changing anything:

* **Money is integer paise.** Indian MRP is tax-inclusive by law (Legal
  Metrology (Packaged Commodities) Rules, 2011), so tax is backed out of the
  displayed price. In floats the total drifts off the printed MRP.
* **Section 170 rounding is per tax head, half-up.** CGST and SGST round
  independently and can legitimately land ₹1 apart. The invoice carries a note
  saying so, because it looks like a bug.
* **Numbers are allocated at issue, never at checkout.** Rule 46(b) requires a
  consecutive series; reserving a number per cart would punch permanent holes
  in it from abandoned checkouts.
* **Invoices are never hard-deleted.** GSTR-1 Table 13 needs the number range
  issued and the count cancelled. Cancelling sets a status.
* **There are three documents, not one.** Tax Invoice (registered), Bill of
  Supply (registered but exempt or composition), and a plain Receipt for an
  unregistered seller. The common mistake is giving an unregistered seller a
  Bill of Supply — that is a *registered* person's document, and CGST Sec 32(1)
  bars an unregistered person from collecting any amount as tax at all.
* **The registration warning is the most valuable thing in the module.**
  Section 24(i) compels GST registration for inter-state supply of goods from
  the first rupee — no turnover floor. Since D2C ships nationwide by default,
  the ₹40 lakh threshold protects almost nobody, and a seller who believes it
  does is in breach from their first order.

`gst.NEEDS_CA_REVIEW` lists three things a chartered accountant should confirm
before a seller files from this, the most important being imitation jewellery
(HSN 7117) at 3% — sources disagreed and the primary CBIC schedule could not be
read at source. It is in the code and surfaced in the UI, not buried here.

## Shipping labels

`labels.py` draws a 4×6" thermal label. Payment mode is the largest element
after the address, because a rider who misses "COD ₹1,499" either fails to
collect or wrongly demands money from a prepaid customer. The return address is
mandatory: an undeliverable parcel without one is destroyed rather than
returned, and RTO runs around a quarter of COD orders.

## Cancellation as a conversation

`cancel_requests.py`. A shopper tapping Cancel raises a **request**, not a
cancellation. The seller is notified, the shopper is handed to WhatsApp, and
only the seller approving actually cancels.

This is a deliberate product decision. Most Indian D2C cancellations are
recoverable — a wrong size, a delivery date, or anxiety about whether the
parcel is moving. A one-click cancel converts every one of those into a lost
sale. Each reason carries a suggested save shown to the seller when the request
arrives, because the difference between saving and losing the order is usually
whether they knew what to offer in the first thirty seconds.

The same shape covers purchase orders, where the counterparty is a supplier.

## Social Media Manager

`social.py`. Built on Liadeli, Sotgiu & Verlegh (*Journal of Marketing*, 2023),
a meta-analysis of 1,641 elasticities across 95M observations. The finding that
shapes the module: **the content mix that maximises engagement is close to the
inverse of the mix that maximises sales.** Informational product content has a
+0.580 elasticity to sales; emotional content has −0.073; deals content is
negatively associated with sales.

Consequences you will see in the code:

* pillar mix weighted 60% informational, with offers **capped at 5%** and the
  cap explained rather than silently applied;
* "What's working" features reach rate, saves, sends and DMs. Followers and
  likes are shown small and labelled as not sales signals — only 21% of
  sub-10K accounts grew at all last year, so a seller measuring themselves on
  followers concludes they are failing while selling fine;
* **exactly 5 hashtags** — Instagram capped them in January 2026, and they are
  worth about +2% reach now. Caption keywords do what hashtags used to;
* captions under 30 words, hook capped at the 125-character truncation point,
  and a mandatory comment-CTA question (worth roughly +202% comments);
* Reels and carousels only — single-image reach is down 22% year on year;
* Hinglish in Roman script by default (76% of Indian festive shoppers prefer
  local-language advertising), and every CTA ends in a DM or WhatsApp, because
  that is where Indian D2C actually converts;
* the Shoot List matters more than the scheduler: reach per post *rises* with
  frequency, so the binding constraint is production capacity, not the
  algorithm. One 20-minute shoot atomises into nine assets.

Festival dates in `FESTIVALS_2026` are lunisolar and **must be refreshed each
year, never extrapolated** — marketing blogs routinely get them a week wrong.

## Automatic weekly planning

`backend/core/autoplan.py`. The Social Media Manager plans next week on its own,
once a week, and the seller only has to say yes.

1. **Trigger** — every Saturday at 9am India time by default; the day and hour
   are the seller's choice (Social → Setup). An in-process ticker checks every
   15 minutes, `POST /api/social/autoplan/run` (admin token) is there for a cron,
   and opening the app catches up a run the server slept through. Each week is
   planned at most once. A new account is *armed* on first look and fires at
   the next trigger — deploying on a Friday does not plan everyone's weekend.
2. **Occasions** — festivals whose run-up or day falls in the week (or starts
   soon after), wedding season, the weather season, salary week.
3. **What is already planned** — posts on the calendar for that week count
   towards it; cancelled and skipped ones do not.
4. **Sales** — the last four weeks against the four before, anchored on the
   last date in the data. Winners get the proof beats (a real person using it,
   someone already bought it); strugglers get the reveal and the detail/answer
   beats, because informational content is what moves a sale. No sales data →
   stock level, labelled as such.
5. **Decide** — the week's total is the cadence (2 / 4 / 6) and is never
   exceeded: 2 of 4 already planned means exactly 2 are added, on the best free
   days, one a day, in arc order. Max two posts per product.
6. **Product Studio** — each photo post carries the exact image prompt built
   from the product's own photo and the brand aesthetic (`studio.preview_prompt`);
   each reel carries its shot list and a paste-ready video prompt. No picture is
   drawn at plan time.
7. **Approval panel** — a header card for the week (Approve all / Details /
   Cancel) and one card per post (Approve / Details / Cancel).

**Approve** (`POST /api/social/approve-ready`): a photo post gets its picture
generated, cleaned and scheduled. A reel is marked `approved` and a task goes to
the **top of Home**: copy the prompt → open Google Flow → paste, generate,
download → upload the clip here → Save & schedule
(`POST /api/social/schedule-ready`). A picture that cannot be made (no engine,
cap reached) leaves the post `approved` with a photo task — never scheduled
with an empty frame. Tasks close themselves when their post is scheduled or
cancelled.

## The video prompt

`social.build_video_prompt()`. The prompt is pasted into Google Flow, and a
video model does exactly what the prompt says — so everything wrong in the
output was written in the prompt.

Three things were, and are fixed:

* **It described a post, not a video.** Saying "Instagram Reel, 9:16" made the
  model draw the app: a phone frame, a caption bar, a username. The prompt now
  asks for a video and states the framing as *vertical, fills the frame*
  — no platform named anywhere.
* **It asked for on-screen text.** Every clip came back with a line of white
  type across the middle, in the model's own font, usually misspelled. The line
  is now `TEXT: none` and the words live in the caption, where they can be
  edited.
* **Every clip was cinematic.** A slow push-in on a hero object is the right
  film for one post out of eight and a parody by the third. `REEL_STYLES` holds
  eight: hands demonstrating, quick cuts, making it, packing an order, styling,
  before/after, a customer's story, talking to camera — each with its own brief
  and pace. `_reel_style()` picks one from a hash of product, pillar and date,
  so a week's plan varies by itself and the same post always re-renders the
  same way.

The shot list is capped at three beats and the prompt says to fit all of it into
`AI_CLIP_SECONDS` (8) — a six-beat list in an eight-second clip is why generated
video comes back as a slideshow.

## Watermark remover

`backend/core/watermark.py`. Every generated picture, every clip we generate and
every clip uploaded for a reel goes through it. It removes only the *visible*
corner mark (Flow/Veo, Kling, a sparkle): position (hugs a corner), look (light,
low-saturation strokes brighter than what is behind them) and shape (small,
stroke-like, isolated) must all agree — and for video, the mark must stay put
while the picture moves. Anything else is left untouched; a picture with no mark
comes back byte-for-byte. Removal is OpenCV Telea inpainting on the corner only;
clips are re-encoded to H.264 with ffmpeg (`imageio-ffmpeg` ships one) keeping the
audio. The clean copy is saved under a new name and the original upload kept.
Invisible provenance (SynthID/C2PA) is not touched, and posts keep their AI flag.

**Video cleaning cannot take the server down.** Cleaning a clip used to run
inside the web server and peaked at ~730 MB for an 8-second 1080×1920 reel, plus
~340 MB in ffmpeg — more than a 512 MB Render instance has. The server was
killed mid-request, the host answered 502, the app showed "the server is waking
up", and retrying the same upload did it again. Now:

* detection keeps only the four corner crops of the sampled frames, built one
  frame at a time;
* decoder, OpenCV and x264 are capped at 2 threads (`WATERMARK_THREADS`), and
  x264 runs `ultrafast` with no look-ahead (`WATERMARK_X264` to change);
* the whole job runs in a **child process** (`python -m backend.core.watermark`)
  that puts itself first in line for the out-of-memory killer, with a timeout
  (`WATERMARK_TIMEOUT`, 240 s);
* before starting it checks the container's free memory against what a clip
  of that size needs (`video_need_mb`, ~306 MB for 1080p) and skips with a
  plain reason if there is not enough;
* the app attaches the clip unchanged (`clean: false`) if the cleaning step
  fails for any reason, and tells the seller the mark was not checked.

Measured: the web server stays at its normal ~140 MB during a clean; the
cleaner and encoder together peak at ~275 MB. Uploads are read in 1 MB pieces
and stopped at the size cap (48 MB for video).

**Filled icons, and shots that barely move.** The first version knew text-like
marks. Gemini's four-point sparkle is mostly interior, and video compression
softens its edges: on a moving shot only its rim came off, and on a locked-off
product shot — most AI clips — nothing was found at all. Now detection also
takes a coarse pass (brighter than its surroundings at the scale of the mark
itself, not just at an edge), fills the inside of what it finds and grows the
mask a little further, so tips and middle go with it.

**"Still see a watermark? Show us where."** Under the clip, in the reel task
and in the post editor. The seller picks a corner, `POST /api/social/reclean-video`
runs the remover again on the ORIGINAL upload (kept as `video_original_url`)
with `corner=` — which relaxes what counts as a mark in that corner only:
fainter, smaller, and judged as less colourful than its surroundings rather
than grey. A corner with nothing in it is left exactly as it was and says so.

## The purchase order, end to end

**Raising one.** Two ways in, one shape out. The replenishment check raises
drafts by itself; *Create purchase order* is the seller writing one — supplier,
then each line picked from a dropdown of **their own inventory** (name, unit and
last rate fill themselves, the quantity starts at that item's DOQ), terms, and
either *Create & send* or *Save as draft*. A line keeps its `inventory_id`, so
receiving the order later can post the stock against it; a free-typed line is
still allowed for a first order from a new supplier and simply cannot restock.

**Approving one.** Approve SENDS: the email the content writer drafted, the PO
as a PDF attachment, to the address in the Supplier module. No draft to read
first — *Details* is where the mail is, editable, for the times that matters.
Every waiting PO is its own card in the Approval panel, hand-written drafts
included.

**Tracking one.** `draft → mailed → replied → confirmed → received`, plus
`open` (approved, but no mailbox is connected) and `cancelled`. `PO_NEXT` in
supply.py says which move is legal from where; the Suppliers page gathers POs
under those headings and shows only the moves that apply. Receiving posts the
ordered quantities back into stock. The old `sent`/`shipped` names still read
correctly (`PO_STATUS_ALIASES`).

Marking *Replied* is a button today. Detecting it automatically needs to read
the mailbox the supplier replies into — the seller's own inbox, since the order
now goes out from their address — and reading a seller's mail is a bigger
permission than sending on their behalf. It waits for that decision rather than
a half-working guess.

**Cancelling one.** Any PO that has not been received can be called off
(`replenish.cancel_po`). If it already went to the supplier the dialog offers to
tell them, and the content writer writes that mail with the PO number in it; the
history line records both the cancellation and whether the supplier was actually
told, because "cancelled" on a screen means nothing if a crate still arrives on
Thursday. A PO that never left the shop says so instead.

**The signature.** Optional, uploaded on the Suppliers page, drawn above
"authorised signatory" on every PO PDF. Without one the PO still carries the
shop's name.

## The purchase order comes from the seller, not from us

`backend/core/seller_mail.py`. A PO that arrives from `no-reply@someapp` is an
order from a stranger. The supplier already knows the shop's address — it is on
their WhatsApp, their invoices, the last twenty orders — so that is the address
the order has to come from, or it lands in spam and nobody rings to confirm.

The seller connects their mailbox once, on the Suppliers page: address plus an
app password. `guess()` fills the host and port from the domain (Gmail, Outlook,
Yahoo, Zoho, iCloud, Rediffmail; a business domain gets `smtp.<domain>` as an
editable suggestion). Connecting performs a real login and sends a real test
mail to the seller's own address — "connected" is something they can see in
their inbox, not a claim this app makes. Credentials are encrypted with the same
Fernet key as every other third-party credential (`secrets_store`) and are never
shown again.

`replenish._deliver()` then tries the seller's mailbox first and falls back to
the server's SMTP account, and records which one carried it, so `from` on the PO
is the address the supplier will actually reply to. Send-only: this never opens
the seller's inbox. Failures come back as instructions ("Gmail refused that
password — Security → App passwords"), not as SMTP exception text.

Setting `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` is
still worth doing: it covers password resets and digests, and it is the fallback
for accounts that have not connected a mailbox of their own.

## Local time, by country

`backend/core/localtime.py`. Every `scheduled_at` in this app is naive
wall-clock time, and the server is not where the seller is (Render runs UTC).
The account picks a country; that maps to one IANA zone, and the weekly planner
(`autoplan.now_local`) and the slots `social.build_week` writes both run on it.
One zone per country on purpose — picking a state is an extra question for a
difference that matters in five countries, and the zone chosen for those is
named in the list. Changing country does not move posts already scheduled:
7:00 pm stays 7:00 pm.

## Purchase orders on Supabase

`purchase_orders` in supabase/schema.sql has eleven columns; a PO carries more
than that — the supplier it goes to, its note, its history, whether it was
raised automatically. PostgREST refuses a row with any column the table does
not have, so writing the whole PO failed on every live account (a 500,
`TransportProblem at db.py:201`) while passing every local test, where POs are
JSON with no columns at all. `supply._po_insert()` / `_po_patch()` now write
the table's own columns to the table and keep the rest of each PO with the
account's other data (`smart_po_extra`), merged back in `get_purchase_orders`.
No migration is needed; adding the columns later changes nothing.

`scripts/test_supabase_mode.py` runs the app against a fake Supabase whose
tables have exactly the columns in schema.sql and which refuses NaN — the two
things local JSON mode cannot catch. Any row the app writes to a real table is
covered by it.

Tests: `python scripts/test_autoplan.py`, `python scripts/test_watermark.py`.

## The approval panel, staffed

`personas.py`. Every insight is attributed to one of five managers — Social
Media, Operations, Supply Chain, Marketing, Brand — and the copy is rewritten
in that manager's voice: recommendation first, reasoning second.

The point is not decoration. A card that says "Reorder 4 items below reorder
point" makes the seller work out who would have told them that and what happens
if they ignore it. A card headed **Operations Manager** saying *"Place an order
for 4 items before we run out — the tightest is down to 11 days of cover"*
answers both before it is read.

The copy is written, not generated. Sending each card through an LLM would be
slower, non-deterministic, cost money on every panel render, and produce worse
sentences than writing them once by hand.

`dress()` only ADDS fields. The original `title` and `detail` survive untouched,
because History, the email digest and the Today strip still render those.

Three new cards exist so that every desk has something real to say:

* **overstock** — the mirror of the reorder card, and the one nobody builds.
  Running out is loud; a customer complains. Overstock is silent: the money
  simply is not there when the seller wants to buy what IS selling. Skips items
  with no sales history rather than guessing.
* **supplier_risk** — items with a single supplier and no alternative on file.
  Also the only honest price benchmark a small seller has.
* **festival** — fires on the campaign START date, not the festival date. A
  Diwali card that appears on Diwali is useless.

## Design language

Product Studio has a second image bucket, separate from product photos: pictures
whose *look* the seller wants. Their packaging, their shop, shots they admire.

A seller can rarely write "soft north light, warm sand, generous negative space"
— but every one of them can point at five pictures and say "like this". The
vision model reads those references and writes the aesthetic; that text then
outranks the preset `look` dropdown in every generated image.

Each product's own photographs get the same treatment, into `material.seen`.
This is the step that decides whether a generated image resembles the item that
actually ships or a plausible invention of one — the model is told "deep maroon
Banarasi silk with gold zari butis and a scalloped hem" instead of "a lehenga".

`image_prompt()` stacks three sources in decreasing authority:

1. what the product actually looks like (`seen`),
2. the brand's aesthetic (`aesthetic`),
3. the Social Media Manager's pillar and format, translated into camera
   direction — a "product in detail" carousel slide and a "behind the scenes"
   reel cover are not the same photograph.

The preset look is the fallback, used only when nothing has been read.

Generation runs through Cloudflare Flux Schnell when configured: about 500
images a day free, then roughly Rs 0.04 each against gpt-image-1's Rs 3.70. On
an unlimited Pro plan that difference is the whole margin — 200 images a month
costs Rs 740 of a Rs 999 subscription on OpenAI, and Rs 8 on Flux.

`generate_image_only()` exists separately from `make_post()` because the two are
wanted at different moments: a seller planning a week wants pictures for slots
that already have captions, and writing a second caption over the first is
actively unhelpful. Planned posts carry an empty image slot filled on demand —
generating four images every time someone presses "Plan my week" would spend the
free daily allowance on posts they may skip.

## Free AI

`aiprovider.py` puts a provider chain behind every text call: **Puter**
(when `PUTER_AUTH_TOKEN` is set) → Cloudflare Workers AI (10,000 neurons/day
free) → Groq (1,000 req/day) → Gemini (1,500 req/day) → Hugging Face →
OpenAI → a deterministic template that needs no network.

Puter ([github.com/heyputer/puter](https://github.com/heyputer/puter)) is
reached through its OpenAI-compatible endpoint
`https://api.puter.com/puterai/openai/v1` with an auth token from the Puter
dashboard; one token reaches GPT, Claude and Gemini models, billed to that
token's Puter account. `PUTER_MODEL` sets the everyday model and
`PUTER_WRITER_MODEL` the one used for customer-facing copy. When the server has
no provider, the browser can fall back to `puter.js` (the seller's own Puter
account signs in and pays); turn that off with `AI_BROWSER_PUTER=off`.
`AI_PROVIDER_FIRST=<name>` moves any provider to the front.

Every call declares a `sensitivity`. `"public"` is copy written to be
published, so free tiers are fine. `"private"` is anything derived from a
seller's own sales or customers (a PO email included), and may only reach
providers marked `trains=False` — which excludes Gemini's free tier. It is a
required argument rather than an optional flag because getting it wrong leaks
a seller's revenue into somebody else's training set.

**The content writer** (`writer.py`) is one system prompt used everywhere text
is written for the seller: plain, specific, no invented facts, a list of banned
filler phrases, and the brand voice from Product Studio and the site. It backs:

* **Website** — the seller writes a sentence or two about the shop (*About your
  shop*), and *Write my website* drafts the tagline, hero, story, promises,
  newsletter line and SEO/WhatsApp text; each line is ticked on or off before
  anything changes.
* **Product description** — description and key points from the name, category,
  price and optional notes.
* **Every other text box** marked `data-ai` gets a ✨ *Write with AI* / *Improve
  with AI* button with Use / Try again / Shorter / More detail.
* **PO emails** to suppliers.

Environment: `PUTER_AUTH_TOKEN`, `CF_ACCOUNT_ID` + `CF_API_TOKEN`,
`GROQ_API_KEY`, `GEMINI_API_KEY`, `HF_API_TOKEN`, `OPENAI_API_KEY`. None are
required — the app writes usable copy with none set.

## Media storage

`media.health()` **probes** Storage and creates the bucket if missing, rather
than inferring safety from `SUPABASE_URL` being set. "Configured but the bucket
does not exist" looks identical to "working" from outside and loses every
upload — which is the original vanished-images bug wearing a different hat.

## Cancellations

`backend/core/cancellations.py`, computed from the seller's own storefront
Orders (`GET /api/cancellations`), surfaced as a KPI beside Revenue on Sales
Analytics with a breakdown behind it.

**Cancelled orders are excluded from the sales dataset and from every insight
built on it** — `storefront.SALES_STATUSES` has always dropped them. This page
is the only place they are counted, so its numbers deliberately do not tie to
Sales Analytics.

The design follows what actually costs money in Indian e-commerce rather than
just counting rows:

* **Stage, not just count.** An order killed before packing costs the sale; the
  same order cancelled after dispatch costs freight out, freight back and a
  week of blocked stock. Stage is derived from the order's own status history,
  so the seller never has to record it.
* **Reason captured at the moment of cancelling.** Asking later never works. A
  cancellation with no reason is counted as "Not recorded" and shown as its own
  bar, and `reason_coverage` reports how much of the picture exists — a reason
  Pareto built on half the data is a confident lie.
* **Whose side it was on** (seller / buyer / courier), because only seller-fault
  is directly fixable.
* **COD vs prepaid**, the most informative cut in India: Shipway's FY25 data
  (Unicommerce subsidiary, cities with ≥5,000 non-prepaid orders) puts COD
  return-to-origin at **26%** against **under 2%** for prepaid.
* **`MIN_DENOMINATOR = 20`.** Below that it reports counts and rupees only. At
  50–500 orders a month, "this product has a 40% cancellation rate" usually
  means two out of five.
* **Rupees beside every percentage**, and weekly buckets rather than daily.

Not yet built, and the natural next steps: RTO as a stage of its own (an order
that shipped and came back is not the same as one cancelled at the door),
marketplace cancellations via the column mapper, and a repeat-offender list
keyed on phone number.

## Password reset

`backend/core/password_reset.py`, for sellers (`/api/forgot`, `/api/reset`) and
for shoppers on a seller's store (`/api/shop/<handle>/forgot`, `.../reset`).
Only a SHA-256 hash of each token is stored, single use, one-hour expiry, and
the reply is identical whether or not the address exists. A shopper reset also
revokes every live session for that shopper.

## Product variants

A shirt is not one thing to count. `products.py` carries up to two option axes
(`options`: Size, Colour) whose cross product is the `variants` matrix — each
cell a real record with its own SKU, stock, and optional price override.

* Editing the axes rebuilds the matrix and **carries over every cell already
  filled in** (`build_matrix`), so adding XL never wipes twelve rows.
* Product-level `stock` becomes the roll-up of the matrix, so every existing
  caller (Supply, analytics, the tiles) keeps reading a correct total.
* A cart line for a variant product **must** name a variant — `price_cart`
  returns `reason: "choose_variant"` rather than guessing a size.
* Orders decrement the individual cell; `name` on the line stays the canonical
  product name so every roll-up keeps matching, with `display_name` for humans.

## Guest checkout

Forcing a first-time cash-on-delivery buyer to invent a password was the most
expensive rule in the codebase. `storefront.guest_customer()` creates — or
reuses — a real customer keyed on the phone number the parcel needs anyway, with
no password set. Guests appear in RFM and Win-Back like anyone else, get a
session back so "your orders" works, and can claim the account later by setting
a password (`register()` upgrades a guest row instead of refusing it).

## Link previews

`sitebuilder.seo_meta()` + `_meta_tags()` in `main.py` render real `<title>`,
description, canonical and Open Graph tags per store and per product, so a link
pasted into WhatsApp arrives as a card rather than grey text. Each product has
its own address at `/s/<handle>/p/<id>`, and each store a `sitemap.xml`.

## Win-back proof loop

`backend/core/winback_proof.py`. The seller ticks "I've sent it"; the campaign's
target ids and date are snapshotted; every later refresh of the sales data
answers how many came back and what they spent in the following 30 days. The
headline lands on the home screen. The method is stated on screen rather than
implied — it is not a controlled test, it is what their own sales data says.

## Performance

The home screen used to take about half a second of server work before it drew
anything, and it got worse as an account's history grew. Four changes, in order
of how much they mattered:

1. **`market_basket_pairs` was the single slowest call in the app** (~143 ms on
   90 days of data) because it built its baskets with a `groupby(...).apply()`
   running a Python callable per order, then walked every ordered pair twice.
   It now de-duplicates `(order, item)` vectorised, drops single-line orders
   before the loop, and counts each unordered pair once with
   `itertools.combinations`. Same output, byte for byte — **143 ms → 14 ms**.
2. **`at_risk_customers` profiled every at-risk customer and then threw all but
   `limit` away**, finding each one's rows with a full-frame scan and their RFM
   row with a linear search. It now ranks by spend first, profiles only the
   survivors, slices them from one `groupby`, and looks rows up in a dict.
3. **The same work was being done twice per page.** `/api/smart/state` and
   `/api/today` each loaded the dataset and each ran the at-risk pass.
   `analytics.at_risk_cached()` computes one pool per account per data version
   and every caller slices it to its own limit.
4. **`backend/core/cache.py`** — a small in-process cache keyed on a
   *fingerprint of the account's data* (dataset row counts, `updated_at`, order
   count), not on a timer. Uploads, orders, product edits and channel toggles
   change the fingerprint or call `cache.clear(email)`, so a seller never waits
   out a TTL to see their own change. Loaded dataframes are cached the same
   way, which matters most on Supabase where every load is a download plus a
   decrypt plus a parse.

Measured on 2,615 rows / 60 customers:

| | before | after (cold) | after (warm) |
|---|---|---|---|
| `GET /api/smart/state` | 348 ms | 58 ms | 5 ms |
| `GET /api/today` | 184 ms | 7 ms | 3 ms |
| whole home screen | ~530 ms | — | 15 ms |

On the client: uploaded media is served with `FileResponse` (streamed, not read
into memory) plus an immutable cache header and ETag/304, so a storefront stops
re-downloading its own photos; picking a size repaints one column instead of
re-rendering the whole page; and the app's home screen fires its independent
reads together rather than in sequence.

## Security & trust

- Passwords are stored as salted PBKDF2-SHA256 hashes ("pbkdf2$salt$hash") — never
  plain text. Legacy plaintext rows in user.csv still log in and are upgraded to a
  hash automatically on the next successful login.
- Signup asks for the password twice (double protection) on both the landing page
  and the in-app modal.
- Uploaded data lives in the user's private server-side session only — the UI says
  so at every upload point.

## Growth features

- **Sample café demo** (`POST /api/demo`): one click loads 90 days of realistic
  pre-mapped transactions (data/sample_transactions.csv) so visitors see full value
  before uploading anything.
- **Blurred previews**: guests can open the AI Analyst and Chatbot pages and see a
  blurred sample of the output with a "Log in free to unlock" overlay.
- **Pricing feedback** (`POST /api/feedback`): every pricing-modal item has a
  one-tap "Would you pay this? 👍/👎" logged to data/feedback.csv — review weekly;
  this is the GTM pricing-validation dataset.

## Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...        # Windows: set OPENAI_API_KEY=sk-...
uvicorn backend.main:app --reload
```

Open http://localhost:8000 — upload a transactions CSV, confirm the mapping,
and explore. Log in (demo@cafex.com / demo123, or add rows to data/user.csv)
to use Analyst AI and the Chatbot.

## Deploy (Render)

Build command: `pip install -r requirements.txt`
Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
Set `OPENAI_API_KEY` in the environment settings.

## What's new (v16.1)

**Mobile & tablet friendly.** The classic app (`/app`) now uses an off-canvas
drawer + top bar below 900px instead of cramming the sidebar into a strip, and
tables/charts/KPIs reflow down to phone widths.

**Position Strategy** (`/app` → "🧭 Position Strategy", login required). Detects
the café's current position from its reviews (reuses the Positioning engine),
shows pros/cons of the current vs a chosen target position, lists what stays the
same ("keep these"), and generates a phased checklist to move A→B. The position
and every ticked checkbox are saved to the account (`data/user_data/`) so the
owner resumes where they left off, on any device.

**Smart CafeX** (`/smart`) — an Odoo-style workspace on the same backend:
- Module tiles: Sales Analytics, Review Analytics, Complaint Analysis,
  Position Strategy + AI.
- Separate **Sales** and **Review** uploads (multiple files, with a mapping
  step). Uploaded data is saved to the account and reused until "Update".
- A per-account **task list**.
- A right-hand **Approval panel** of actionable insights. **Approve** executes
  the action (today: downloads the ready Excel — win-back list + messages, menu
  combos, positioning/complaint action plans — and adds a task). **Dismiss**
  hides it. **Details** opens the relevant module.

New backend modules: `core/user_store.py` (per-account persistence),
`core/position_strategy.py`, `core/smart.py`. New endpoints live under
`/api/position-strategy/*` and `/api/smart/*`. A numpy→JSON encoder is
registered in `main.py` so analytics/RFM responses serialize on any FastAPI
version (a fresh unpinned `pip install` pulls a newer FastAPI that would
otherwise 500 on the forecast series).

### Desktop app (.exe)?
Yes — this can be packaged as a Windows `.exe`. It's a normal FastAPI app, so
the practical route is **PyInstaller** (bundle `uvicorn` + the app into one
executable) paired with **pywebview** (a native window) or just auto-opening
the browser at `127.0.0.1`. Expect a large binary (~150–250 MB, because pandas
+ matplotlib + reportlab ship inside), and you'd point `CAFEX_DATA_DIR` at a
per-user writable folder (e.g. `%LOCALAPPDATA%\CafeX`) and set `OPENAI_API_KEY`
locally. Alternatives: **Tauri/Electron** wrapping the web UI, or **Docker**
for a self-contained server. Not built here — this note answers the question
only.

## Supabase backend (accounts, sessions & per-user data)

The backend can store everything in **Supabase** instead of local files, so
logins survive restarts/redeploys and every account's data is tied to its
login. It's controlled entirely by environment variables — with none set, the
app keeps using the original local files (`user.csv`, `state.json`, pickles), so
development is unchanged.

**What moves to Supabase**

| Local (before)              | Supabase (after)                          |
|-----------------------------|-------------------------------------------|
| `data/user.csv`             | `users` table                             |
| in-memory session dict      | `sessions` table (hashed token + expiry)  |
| `data/usage_logs.csv`       | `usage_logs` table                        |
| `state.json` per user       | `user_state` table (jsonb)                |
| `df_*.pkl` per user         | `user-datasets` Storage bucket (encrypted)|
| `data/purchases.csv`        | `purchases` table                         |
| `data/feedback.csv`         | `feedback` table                          |

Passwords stay pbkdf2-hashed; session tokens are stored only as a SHA-256 hash;
the uploaded Sales/Review tables are Fernet-encrypted before upload (on top of
Supabase's own at-rest encryption).

**Setup**

1. Create a Supabase project. In the SQL editor, run `supabase/schema.sql`.
2. Confirm a **private** Storage bucket named `user-datasets` exists
   (the schema creates it; if not, make it under Storage → New bucket).
3. Set env vars (see `.env.example`): `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
   and `CS_SECRET_KEY` (generate a stable Fernet key).
4. Migrate existing data (optional, one-time):

   ```bash
   pip install -r requirements.txt
   python -m scripts.migrate_to_supabase
   ```

**Add vs Replace on re-upload**

In Smart CafeX, once Sales/Review data is saved, the data card shows
**➕ Add records** alongside **↻ Update**. Re-uploading asks whether to *add*
the new rows to what's saved or *replace* everything; the choice is sent to
`POST /api/smart/map` as `mode: "append" | "replace"`.
