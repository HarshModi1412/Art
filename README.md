# Cafe_X — Standalone Web Application

Migration of the Streamlit app to an independent FastAPI + HTML/JS application.
No Streamlit dependency anywhere.

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

**Themes.** Basic, Luxury, Fitness, Fashion & Apparel, Jewellery, Food &
Beverage, Beauty & Skincare, Tech & Gadgets. Each is a different site — its own
layout, type scale and motion (fade-up reveals, vertical parallax, horizontal
collection rails, pinned sections, a scrolling band, image zoom), not a recolour.
The seller then overrides fonts, accent colours per mode, corner radius, product
layout, animation strength and page width in the **Design** tab; a preview tab
renders the real site at desktop / tablet / phone width, published or not.

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
throwaway data directory.

## Site structure

- `/` — marketing landing page (MSME positioning, multilingual sample-story wall, pricing)
- `/s/<handle>` — a seller's own storefront (Website Builder)
- `/app` — the analytics application

## Pricing model (GTM: à-la-carte, not subscription)

Everything is controlled by `backend/core/pricing.py` + the `LAUNCH_MODE` env var.

**While `LAUNCH_MODE=true` (default): everything is free.** The pricing UI is
visible (labelled "Free during launch") but no paywall ever fires and Razorpay
is never called. When you hit ~30-50 active cafes, set `LAUNCH_MODE=false` and
redeploy — no code changes.

Once live:

| Offering | Price | Gate |
|---|---|---|
| Analytics, category trends, RFM, at-risk list | Free forever | never gated |
| AI Analyst / Chatbot | 5 free uses per day per feature | daily quota (usage_logs.csv) |
| Win-Back Campaign (messages + Excel) | ₹199 / campaign | 1 credit per generate |
| Market Position & Reputation Report | ₹349 / report | 1 credit per analysis |
| AI Top-Up (10 extra uses, shared pool) | ₹99 | consumed automatically after daily quota |
| Chain plan (2+ outlets) | ₹999 / month | plan column in user.csv; unlimited everything |

Purchases are a ledger in `data/purchases.csv` (email, product, credits_total,
credits_used, amount, order/payment ids). Legacy `pro` accounts are treated as
Chain so early users keep access. Gated endpoints return **HTTP 402** with
`{code:"paywall", product, message}` — the frontend opens the pricing modal.

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
