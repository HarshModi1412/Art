# One Tap Manager product inventory

What the app does today, written from the code as of 24 September 2026. Use it to answer "do we have X?", to brief anyone new, and to check marketing copy against what actually ships. How it should sound lives in `Brand.md`. What is still left before launch lives in `LAUNCH_PLAN.md` and `TODOS.md`.

---

## 1. The product in one paragraph

One Tap Manager is a web app for small online sellers of clothing, jewelry and fragrance. Since September 2026 the primary market is the United States (onetapmanager.com, prices in USD); India is the second market (onetapmanager.com/in, prices in INR). A seller brings in the sales they already make (a file from Amazon, Shopify, a POS or a spreadsheet, a live connector, or orders from their own One Tap website). The app reads it and answers "what should I do this morning?" on the home screen, then does most of the work: the win-back message is written, the purchase order is filled in, the week of Instagram is planned and scheduled. It lives at onetapmanager.com, and the app itself is at onetapmanager.com/smart.

### 1a. The first pain it fixes: selling through chats

Most of our sellers do not have a shop yet. They have a chat. They post on Instagram, and every sale happens in DMs or on WhatsApp: "price?", "is this available?", "size M?", "send the link", a screenshot of the payment, an address typed out by hand. Nothing is structured. There is no catalog, no cart, no order list, no customer list, and no sales file, so every other part of One Tap Manager has nothing to read. Buyers drop off at every reply they wait for (the "DM for price" problem, Shop Doctor episode 1).

The fix, in the seller's words: **add your products, pick a theme, and your designer-level website is ready to sell.** What is real in the code:

- **Add products**: the first-run journey asks for just 3 products (photo, name, price) to get a live site; the rest go in Product Management later.
- **Pick a theme**: 8 themes, each a different layout, not a recolor, plus 20 fonts sold as ready-made pairings (Quiet Modern, Editorial, Gallery, Atelier and more) and a live click-to-edit canvas. "Designer-level" means these hand-built layouts and font pairings, not a template with a logo swapped in.
- **Ready to sell**: a cart, shopper accounts and checkout, with payments into the seller's own account (Razorpay; USD needs International Payments switched on), at onetapmanager.com/<shop name> or their own domain.
- **Back to the chat**: the journey ends on the live link with Share on WhatsApp and Copy for Instagram bio. The chat stays the place people discover you; the website becomes where they buy. Every order placed there flows straight into Orders, Inventory, analytics, customer groups and win-back, so the rest of the app starts working on real data.
- **Price**: included in Pro ($10 a month), custom domain too. There is no cut of sales.

Keep the claim honest: the website does not take orders inside Instagram or WhatsApp, and WhatsApp sending is still switched off (section 9). We replace the chat *checkout*, not the chat.

---

## 2. Plans and money

Source: `backend/core/pricing.py`, `billing.py`, `region.py`, `credits.py`.

| Plan | US price | India price | What it includes |
|---|---|---|---|
| Free trial | $0 for 14 days | ₹0 for 14 days | Every Pro Max feature, no card. When it ends nothing is free: the app shows the plan picker until a plan is bought. Data is kept |
| Pro | $10 a month | ₹700 a month | Everything except AI image and video generation: analytics, customer groups, win-back, stock, suppliers and purchase orders, the Instagram planner, review and complaint analysis, the website and custom domain, unlimited AI writing |
| Pro Max | $12.99 a month | ₹1,299 a month | Everything in Pro, plus AI product photos and short product clips |

- **The trial start date** is saved on the account at signup (`billing.start_trial`, stored under `billing_account` in the user store), along with the billing currency. The trial cannot be restarted. Accounts made before this pricing get their 14 days from the first time the app checks them. The trial went from 7 to 14 days on 4 October 2026 (`pricing.TRIAL_DAYS`).
- **Currency** is chosen by region (`region.py`): `?region=in|us`, then a cookie, then the edge country header (`CF-IPCountry` and similar), then Accept-Language, then USD. A seller is billed in the currency saved at signup. Prices are set by hand in each currency, never converted.
- **After the trial**, a middleware in `main.py` answers every seller API with a 402 `trial_ended`, except sign-in, account, pricing and payment routes. The app turns that into the plan picker. Scheduled jobs (autoplan, win-back, digest) skip locked accounts. Public pages and the storefront keep working.
- **Image and video generation** is gated in `aicaps.require_generation`, so every generate route (including a seller's own OpenAI key) needs Pro Max or the trial.
- **A paid month** runs 30 days from payment (`paid_until`). Nothing renews automatically: the seller pays again from the Account tab ("Renew" in the last week). Cancel stops renewal and the plan runs to the end of the paid month.
- **Credit packs** (₹299, ₹749, ₹1,999) are sold to rupee accounts only and top up the monthly credit meter. They have no dollar price yet.
- **Launch mode** (`LAUNCH_MODE`) now defaults to off. Set it to `true` to open everything for a demo.
- **No cut of sales, ever.** There are no per-order or percentage fees.
- **Payments** go through Razorpay, in INR or USD. USD needs International Payments switched on in the Razorpay dashboard.
- Legacy plan ids: "max" and "chain" read as Pro Max, "semipro" as the trial.

---

## 3. Getting in

- **Sign up and log in** with email and password, or with "Continue with Google" (`google_auth.py`). The landing page opens the signup form directly at `onetapmanager.com/?signup=1`, and the app's login card links there with "Create a free account".
- **Password reset** by email. If the mail server is not set up, the app says so rather than pretending an email went out.
- **Login guard** (`loginguard.py`) slows down repeated wrong passwords. Rate limits are per route and per method (`ratelimit.py`).
- **Sample data**: a new seller can load 90 days of realistic clothing sales (726 orders, 359 customers, about a third of them repeat buyers, 11 kinds of product) and see every screen working before uploading anything. The Reviews modules stay empty with an upload button, because we do not invent reviews.

---

## 4. The home screen

- **Today** (`today.py`) lists the few things worth doing right now, each one a button straight into the action ("72 customers are slipping away", "4 items are below their buy-again level"). The daily digest email uses the same list, so the two never disagree.
- **Set up your shop in 3 parts** (`onboarding.py`, `Smart CafeX/journey.js`, design in `docs/designs/first-run-journey.md`). A new seller is asked one question first: do you already have a website? "Yes" connects it (Shopify, WooCommerce, Wix, Amazon, or a sales file). "No" builds one, one small screen at a time: shop name and what they sell, 3 products (photo, name, price), a look, the web address, WhatsApp, the owner details the law requires, delivery, a preview, publish, then their UPI ID. Part 1 ends on their live link with Share on WhatsApp and Copy for Instagram bio. Part 2 (brand, style photos, product photos, Instagram) and Part 3 (supplier and stock) arrive as tasks. Every screen is in English and Hindi. A step is done only when the real data says so. Skip asks "Are you sure?" and puts the step on the task list, where it ticks itself once done. Existing accounts get a Start card, never a pop-up. It replaces the old five-step setup card on home (`setup_steps.py` still feeds the API).
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
| Website Builder | The seller's own selling website: 8 themes (each a different layout, not a recolour), 20 fonts, a live click-to-edit canvas, shopper accounts, cart, COD, UPI straight to the seller's own UPI ID (the shopper copies the ID or opens their UPI app with the order number as the note; the order waits as "Payment to check" until the seller taps Money received or Not received in Orders), and Razorpay payments into the seller's own account |

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
- **Pages for AI assistants and search** (`geo.py`): `/about`, `/for/clothing-sellers`, `/for/jewellery-sellers`, `/for/perfume-sellers`, `/compare/shopify-apps` and the `/guides` hub. Each opens with a direct answer and a date, and carries FAQ schema. Prices come from `pricing.py`. `/llms.txt` summarises the product for AI agents. robots.txt names and allows every AI crawler while keeping the app private. See `AI_VISIBILITY_CHECKLIST.md` and `REDDIT_PLAYBOOK.md`.
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
| "Open UPI app" at checkout | Not yet tested on real phones. Some UPI apps may refuse a link with a preset amount to a personal (non-merchant) UPI ID, so copying the ID is the main path and the link is only a shortcut. Test on GPay, PhonePe and Paytm before promoting it |
| UPI orders | The shopper is not told when the seller marks a UPI payment received. A "to check" order never expires on its own |

---

## 10. Switches an operator sets (Render)

| Variable | What it does |
|---|---|
| `LAUNCH_MODE` | Off by default (14-day trial, then paid). `true` makes everything free |
| `AI_LABEL` | `on`, `images` or `off`, as above |
| `META_APP_SECRET` | Needed to verify Instagram webhooks |
| `BRAND_PROFILES` | Official profile URLs (Reddit, Instagram, LinkedIn and so on), comma separated. Listed as `sameAs` in the structured data and in `/llms.txt` |
| `INDEXNOW_KEY` | Serves `/indexnow.txt`, so `scripts/indexnow_ping.py` can tell Bing that pages changed |
| `BING_SITE_VERIFICATION` | Serves `/BingSiteAuth.xml` for Bing Webmaster Tools |
| `GA4_MEASUREMENT_ID` | Google Analytics id. With none set, no tracker and no cookie banner |
| `SMTP_*` | The app's own mail, for password resets and the digest |
| `OPENAI_API_KEY` | The AI analyst, chatbot and writing |
| `WHATSAPP_ENABLED` | Off until WhatsApp is set up |
| Supabase keys | Main storage. Without them the app falls back to local files |

The live service is **Smart_Helper** on Render (created by hand, not from `render.yaml`). It auto-deploys on every commit to `main`, so a push goes live. Its environment variables, `LAUNCH_MODE` included, are set in the Render dashboard; on 4 October 2026 `/api/pricing` showed `launch_mode: false`.

---

## 11. Where things live

| Area | Files |
|---|---|
| Server and routes | `backend/main.py` |
| Business logic | `backend/core/*.py` (one file per area, named as above) |
| Seller app | `Smart CafeX/smart.html`, `smart.js`, `smart.css`, `ios.css` |
| Shopper website | `Smart CafeX/storefront/` |
| Landing pages | `backend/static/landing-us.html` (served at `/`), `backend/static/landing.html` (India, served at `/in`) |
| Database migrations | `supabase/*.sql` |
| Tests | `scripts/test_*.py` (each prints "N passed, M failed") |
| Sample data | `data/sample_transactions.csv`, made by `scripts/make_sample_data.py` |
