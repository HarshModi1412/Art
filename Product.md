# One Tap Manager product inventory

What the app does today, written from the code as of 24 September 2026. Use it to answer "do we have X?", to brief anyone new, and to check marketing copy against what actually ships. How it should sound lives in `Brand.md`. What is still left before launch lives in `LAUNCH_PLAN.md` and `TODOS.md`.

---

## 1. The product in one paragraph

One Tap Manager is a web app for small Indian D2C sellers of clothing, jewellery and perfume. A seller brings in the sales they already make (a file from Amazon, Shopify, a POS or a spreadsheet, a live connector, or orders from their own One Tap website). The app reads it and answers "what should I do this morning?" on the home screen, then does most of the work: the win-back message is written, the purchase order is filled in, the week of Instagram is planned and scheduled. It lives at onetapmanager.com, and the app itself is at onetapmanager.com/smart.

---

## 2. Plans and money

Source: `backend/core/pricing.py`, `billing.py`, `credits.py`.

| Plan | Price | What it adds |
|---|---|---|
| Free | ₹0, forever | Sales and sub-category analytics, customer groups and the at-risk list, unlimited win-back campaigns, complaint and reputation reports, the daily digest, your own website with no badge, up to 250 products, 50 AI uses a day |
| Max | ₹999 a month | Supplier management and reorder maths, PDF purchase orders sent to suppliers, Position Strategy checklists, unlimited AI, products and outlets, your own custom domain |

- **Credit packs**, for sellers who do not want a monthly plan: 100 credits for ₹299, 300 for ₹749, 1,000 for ₹1,999. Credits never expire. One AI use costs 1 credit, and one purchase order costs 5.
- **Launch mode** (`LAUNCH_MODE`, on by default) makes every feature free for everyone. Anything that will later need Max is labelled "Free during launch".
- **No cut of sales, ever.** There are no per-order or percentage fees. The pricing page shows the Shopify app stack the seller replaces (about ₹7,600 a month) with the arithmetic.
- **Payments for plans** go through Razorpay.
- **Cancel** is self-serve from the Account tab (`cancel_requests.py`). Downgrading never deletes data.
- "Semi Pro" (₹499) is retired, and accounts still stamped with it read as Free. "pro" is only the internal id for Max.

---

## 3. Getting in

- **Sign up and log in** with email and password, or with "Continue with Google" (`google_auth.py`). The landing page opens the signup form directly at `onetapmanager.com/?signup=1`, and the app's login card links there with "Create a free account".
- **Password reset** by email. If the mail server is not set up, the app says so rather than pretending an email went out.
- **Login guard** (`loginguard.py`) slows down repeated wrong passwords. Rate limits are per route and per method (`ratelimit.py`).
- **Sample data**: a new seller can load 90 days of realistic clothing sales (726 orders, 359 customers, about a third of them repeat buyers, 11 kinds of product) and see every screen working before uploading anything. The Reviews modules stay empty with an upload button, because we do not invent reviews.

---

## 4. The home screen

- **Today** (`today.py`) lists the few things worth doing right now, each one a button straight into the action ("72 customers are slipping away", "4 items are below their buy-again level"). The daily digest email uses the same list, so the two never disagree.
- **Setup steps** (`setup_steps.py`) put the single next thing a new seller must do first. A seller with no data sees "Welcome" with Today at the top; a returning seller sees "Welcome back".
- **Data status** shows where the sales came from (sample, upload or connector) and how fresh they are.
- **The app grid** is grouped as Know what is happening, Run the day, Bring in more customers and Go deeper.
- **Fast return**: the last home screen is painted from the browser at once, then quietly corrected if anything changed.

---

## 5. The modules

Fourteen in `MODULES` in `Smart CafeX/smart.js`. Twelve are on the grid, and two are reached from other screens.

### Know what is happening
| Module | What the seller gets |
|---|---|
| Sales Analytics | What sold, what it earned, trends by category, and a forecast of next month |
| Sub-Category Analysis | Which kinds of product bring the money in (kurtas against sarees, for example) and which quietly do not |

### Run the day
| Module | What the seller gets |
|---|---|
| Orders | Every order from their own website: pack it, ship it, mark it done. Includes cancellation analysis split by the stage the order reached, in rupees |
| Product Management | One product list, with the different names each product has on Amazon, Shopify and the rest, rolled up everywhere |
| Inventory Management | Stock on hand that goes down on its own as orders come in, plus a waste log |
| Suppliers & Orders to Send | Suppliers, when to buy again (reorder level, spare to keep, how much to buy), and a PDF purchase order emailed to the supplier from the seller's own address. Website orders trigger a stock check and draft an order when something is running short (`replenish.py`) |

### Bring in more customers
| Module | What the seller gets |
|---|---|
| Product Studio | The seller uploads their real photos once. The app learns their look and makes posts from their own product, not a stock picture |
| Social Media Manager | A week of Instagram posts planned, captioned and scheduled, then actually published to Instagram (`publisher.py`). Festival content and an Instagram insights view are included |
| Website Builder | The seller's own selling website: 8 themes (each a different layout, not a recolour), 20 fonts, a live click-to-edit canvas, shopper accounts, cart, COD and Razorpay payments into the seller's own account |

### Go deeper (these need a reviews file)
| Module | What the seller gets |
|---|---|
| Review Analytics | What customers praise, in their own words, themed for jewellery, clothes or perfume |
| Complaint Analysis | The complaints costing the most, ranked in the order worth fixing |
| Position Strategy + AI | Where the brand sits (value or premium, product-led or look-led) and a levelled plan to stand for something, plus an AI analyst and chatbot to ask anything |

### Reached from other screens
| Module | What the seller gets |
|---|---|
| Marketing | Win-back messages for customers who have gone quiet, with an Excel list and what the campaign brought back. It also runs on a schedule (`winback_auto.py`), so the card appears when it is timely |
| Billing & GST | Tax invoices with HSN codes, the right tax by place of supply (GST 2.0 rates from 22 September 2025), and a GSTR-1 file the accountant can file from |

---

## 6. Getting the data in

In order of least effort for the seller:

1. **Sample data**: one tap, covered above.
2. **Upload a file** (`mapper.py`, `pos_formats.py`). Common POS and marketplace exports are recognised by their columns and mapped automatically. For anything else the app suggests a mapping and the seller confirms it.
3. **Connect a shop** (`commerce.py`):
   - **Shopify**: the seller pastes an access token from a custom app they create in their Shopify admin.
   - **Amazon**: the seller pastes Selling Partner API keys from Seller Central.

   Orders from either land in the same analytics.
4. **Email intake** (`email_intake.py`): the seller adds our address to a report their POS already emails out, and the file arrives on its own.
5. **Their own website**: every order placed there flows straight into analytics, customer groups and win-back.

---

## 7. The Account tab

One screen for everything set up once (`account.py`). Secrets never come back to the browser: the seller only sees whether something is connected and its last four characters.

- **Profile**: where they are, where they sell, and the currency.
- **Email you send orders from** (`seller_mail.py`, `renderMailGuide` in `smart.js`). The seller picks their provider: Gmail, Google Workspace, Yahoo, Zoho Mail, iCloud, Rediffmail, Outlook or Hotmail, or Other. The app then shows:
  - the steps for that provider;
  - a direct link to the page where the app password is made;
  - what must be switched on first (for example, 2-Step Verification for Gmail);
  - the form.

  The provider is guessed from the address. Zoho tries the other region's server once on its own. The server is chosen for the seller, and it is only visible under Advanced. Outlook and Hotmail show an honest note that Microsoft no longer allows this, with a "Make a free Gmail address" button. A typed server must be a public mail server on a mail port. Every connect attempt is logged without the password.
- **Instagram** connection (`instagram.py`, Instagram Login, no Facebook Page needed).
- **Razorpay keys** for the seller's own website.
- **Their own AI keys** (optional).
- **Custom domain** for their website, and the default short address **onetapmanager.com/<company name>**. Both survive a redeploy.
- **Cookie and privacy settings** (moved off the floating link).
- **Plan, credits and cancel**.

---

## 8. Across the whole app

- **Languages**: English, Hindi, Tamil and Kannada (`i18n.py`).
- **AI labelling** (`ailabel.py`): generated pictures and clips are labelled "AI generated", as the IT Rules amendment of 20 February 2026 requires. `AI_LABEL` sets how much is labelled: `on` (pictures and clips, the default), `images` (pictures only) or `off`. It is turned down on the current 512 MB server. Another tool's label is never removed.
- **Watermark check** (`watermark.py`): a free video tool's corner logo is cleaned off clips before they are posted to the seller's feed. AI labels are never removed.
- **Error handling**: a global handler returns a plain message and reports the error, and `/oops.js` catches front-end errors.
- **Security**:
  - Meta webhook signatures are verified.
  - The app only frames its own pages.
  - Secrets are Fernet-encrypted (`secrets_store.py`).
  - There is a `security.txt`.
- **Search and legal pages**:
  - sitemap.xml and robots.txt;
  - Open Graph images;
  - Google Analytics (G-VMYF7N98B9, set as `GA4_MEASUREMENT_ID`), loaded only after the visitor says yes;
  - Terms, Privacy, Refunds and Cookies pages.
- **Admin health** (`/api/admin/health`): reports launch blockers, such as AI labelling being turned down.

---

## 9. Honest limits (do not market these as live)

| Thing | Where it stands |
|---|---|
| Ad analytics (Google Ads, Meta Ads, Instagram Insights connectors) | Connections and storage are real, but the figures are demo figures until each platform's app review is done |
| WhatsApp sending | Built behind `WHATSAPP_ENABLED`, off. The digest and messages go by email |
| POS API connectors (PetPooja and similar) | Not a public "pull my sales" API. Use file upload or email intake instead |
| Outlook or Hotmail as the order email | Microsoft blocks password sign-in for other apps. The app says so and offers Gmail |
| Video labelling on the current server | Switched to pictures only (`AI_LABEL=images`) for memory. Set it back to `on` after the hosting upgrade |
| Server-written messages | Some still contain em dashes. Tracked in `TODOS.md` |

---

## 10. Switches an operator sets (Render)

| Variable | What it does |
|---|---|
| `LAUNCH_MODE` | `true` (default) makes everything free |
| `AI_LABEL` | `on`, `images` or `off`, as above |
| `META_APP_SECRET` | Needed to verify Instagram webhooks |
| `GA4_MEASUREMENT_ID` | Google Analytics id. With none set, no tracker and no cookie banner |
| `SMTP_*` | The app's own mail, for password resets and the digest |
| `OPENAI_API_KEY` | The AI analyst, chatbot and writing |
| `WHATSAPP_ENABLED` | Off until WhatsApp is set up |
| Supabase keys | Main storage. Without them the app falls back to local files |

Auto-deploy is off on Render, so every push needs a Manual Deploy.

---

## 11. Where things live

| Area | Files |
|---|---|
| Server and routes | `backend/main.py` |
| Business logic | `backend/core/*.py` (one file per area, named as above) |
| Seller app | `Smart CafeX/smart.html`, `smart.js`, `smart.css`, `ios.css` |
| Shopper website | `Smart CafeX/storefront/` |
| Landing page | `backend/static/landing.html` |
| Database migrations | `supabase/*.sql` |
| Tests | `scripts/test_*.py` (each prints "N passed, M failed") |
| Sample data | `data/sample_transactions.csv`, made by `scripts/make_sample_data.py` |
