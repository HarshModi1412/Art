# One Tap Manager: go-to-market plan, version 2

Written 2 October 2026. Version 2 replaces version 1. It adds the new offer (take a shop from Instagram DMs and WhatsApp chats to a real brand), India alongside the US, and strict rules for choosing and scraping leads.

Built from `Product.md`, `Brand.md`, the code, Harsh's CV, the lead list `OneTapManager_500_Instagram_Leads_1.xlsx`, and the Hormozi playbooks named in brackets.

Numbers marked **(assumption)** are planning guesses. Replace them with your own after week 1.

---

## 1. The short answer

**The offer changed, so the plan has two tracks:**

| | **Launch track** | **Grow track** |
|---|---|---|
| Who | Sells through Instagram DMs and WhatsApp. No website | Already has a website (Shopify, Dukaan, WooCommerce, Wix) |
| What they buy | "Turn my DM shop into a real brand": website, Instagram run properly, the app doing the daily work | "Tell me what to do each morning and do most of it": win-back, reorder, posts |
| First win (activation point) | **First order on their own website** within 7 days | **First win-back message sent** on day 1 |
| India | **Ready now. Lead with this.** | Ready |
| US | **Not ready. Do not sell yet** (section 3) | Ready to test (the five-seller test) |

**Where to spend October** (assumption, revisit on 1 November): about 70% of outreach on **India Launch**, 30% on **US Grow**.

Why India Launch first:

1. **The product is ready for it.** UPI, cash on delivery and Razorpay work. The "no website? build one" setup flow exists, in English and Hindi.
2. **You already have 1,094 Indian leads.**
3. **The calendar.** Diwali (around 8 November 2026) is the biggest selling season for clothing, jewellery and attar. "Get your website live before Diwali" is a real deadline, not fake urgency.
4. **Hormozi Stage 0:** go where you can get proof fastest. [lesson03] Your evenings are India's evenings, and the language is yours.

**The five moves:**

1. Sort the lead list (done: `D:\Claude\leads\OTM_Leads_Triaged.xlsx`), add the missing data to the top 581, and score them with the rules in section 6.
2. Sell a **Founding Brand Launch**: 20 spots, free website preview, setup done with you, 60 days free. [lesson03, lesson04, Fast Cash]
3. Make the first win happen for every seller: a **launch sale** to their own followers and WhatsApp contacts in week 1. [Fast Cash, Retention]
4. **Film the moment** each seller sees their website live. That is your best ad. [Marketing Machine, "upon delivery" ads]
5. No paid ads until 3 sellers have real launch results. Then boost only posts that already beat your average. [lesson04, GOATed Ads]

---

## 2. The new positioning

### What you sell, in one line

> **"From DM shop to real brand, before Diwali."**
> Your own website with UPI and COD, an Instagram that posts itself, and an app that tracks stock and brings customers back. You approve, it does the work. No cut of your sales, ever.

### The Value Equation [lesson04, copywriting-frameworks.md]

| Lever | A DM and WhatsApp seller today | After the Brand Launch |
|---|---|---|
| **Dream outcome** | Wants to look like a "real brand" and sell more without living in DMs | Own website, own domain, steady posts, repeat customers |
| **Perceived likelihood** | "Websites are for big brands. Mine would look bad" | You show them **their own** website preview before they say yes |
| **Time delay** | Freelancer websites take weeks | Live in 1 session; first orders in week 1 |
| **Effort and sacrifice** | Answering "price?" all day, writing captions, guessing stock | Shoppers see prices and order on the site. Posts are planned and scheduled. Stock goes down by itself |

### What you can promise, and what you cannot

Promise only what ships (`Product.md`, section 9, "Honest limits"). The `Brand.md` honesty rules apply to every DM and every ad.

| Say this (it ships) | Never say this (not live yet) |
|---|---|
| Own website, 8 themes, cart, COD, UPI to your own UPI ID, Razorpay | "We run your WhatsApp" (WhatsApp sending is switched off) |
| Instagram posts planned, captioned, scheduled and published | "We manage your ads" (ad figures are demo data until platform review) |
| AI product photos and short clips, labelled "AI generated" | "Shoppers pay in one tap with UPI" (the "Open UPI app" link is not tested on real phones yet) |
| Stock that goes down by itself, reorder alerts, purchase orders | Any sales figure that hasn't happened ("sellers get 40% more orders") |
| Win-back messages written for you | "AI agents run your whole business" (say: "the app does most of the work, you approve") |
| GST invoices and GSTR-1 file | |

When your new `Product.md` lands, update this table from it first.

---

## 3. Market and track readiness

| Track | Status | What blocks it |
|---|---|---|
| **India Launch** | Ready | Test the UPI "Open app" link on GPay, PhonePe and Paytm before promoting it. Tell sellers UPI orders wait as "Payment to check" until they tap "Money received" |
| **India Grow** | Ready | Shopify and Amazon connectors, or sales file upload |
| **US Grow** | Ready to test | Shopify API version pinned to `2024-07` (`backend/core/commerce.py:124`). Win-back emails have no unsubscribe link yet, which US law requires. US sample shop still in rupees |
| **US Launch** | **Not ready** | Card checkout is off: `"charge_ready": {"razorpay": True, "stripe": False, "paypal": False}` (`backend/core/store_payments.py:196`). Checkout asks for a "PIN code". **Do not sell US websites until a US shopper can pay by card end to end** |

**Shared blockers** from version 1 still stand: `Brand.md` still says "Free forever" and "Max ₹999"; nothing renews automatically (a seller re-pays every 30 days); there is no per-account trial extension for founders.

---

## 4. The offer stack (India Launch)

Hormozi's rule: have a free entry, a core offer, a premium anchor at 10x, and a downsell only for people who don't qualify. [LTV "Crazy 8", Pricing play #9]

### Free: the Brand Score and website preview ("reveal the problem" [lesson03])

1. **Brand Score**: a quick score out of 10 on what a shopper sees: bio, link, highlights, price clarity, how hard it is to order, posting consistency. Send 3 fixes, free.
2. **Website preview**: with their permission, you put 3 of their products into a preview shop **in your own demo account** and send them a screen recording or screenshots. Nothing goes live. Their real site gets built in their own account on the call.

Showing them their own website beats any promise. [Proof Checklist: "get results before they buy"]

### Core: the Founding Brand Launch (first 20 sellers)

| Piece | What they get |
|---|---|
| Website | Built with them on a 30 to 45 minute call: their products (up to 25), theme, UPI, COD, Razorpay if they have it, delivery, legal owner details |
| Web address | `onetapmanager.com/<shop name>`, or help connecting their own domain |
| Instagram fix | Bio rewritten, link to the website, "How to order" and "Reviews" highlights |
| 2 weeks of posts | Planned and scheduled in the app, using their own product photos |
| **Launch sale** | You plan their 5-day website launch to their followers and WhatsApp contacts (section 9). This is how they get first orders |
| Check-ins | Day 3, day 7, day 30 |
| Price | **Setup free. 60 days of Pro Max free.** Then ₹1,299 a month (or ₹700 for Pro) |
| The exchange | Honest feedback, permission to film the "first look" at their site, and a short video review if it helped [lesson03, "the 4 Rs"] |

**The cap of 20 is real.** Each launch takes about 2 hours of your time (assumption). 20 launches is about 40 hours over 4 weeks, around a full-time job. Say so. It is honest scarcity.

### After the first 20: price ladder [lesson04; LTV: "nudge price 20% every 10 sales"]

| Sellers | Setup fee | Free period |
|---|---|---|
| 1 to 20 | ₹0 | 60 days |
| 21 to 30 | ₹1,999 | 30 days |
| 31 to 40 | ₹2,499 | 30 days |
| 41+ | ₹2,999, and keep raising until sales drop noticeably | 7-day trial |

### Premium anchor: Brand Partner (cap: 3 sellers)

**₹14,999 a month.** You run it with them each month: a 45-minute numbers review, festival campaigns planned for them, weekly posts approved for them, a product photo plan. About 10x the core offer. [Pricing play #9] Even if few buy it, it makes the core offer feel easy. **Only offer it if you would be happy to do it.** Hormozi: "if you feel stressed when people buy it, keep raising the price."

### Add-ons (cross-sell [LTV #4])

- AI credit packs (₹299, ₹749, ₹1,999), already in the app
- Annual Pro Max: ₹12,990 (two months free). Cash up front, and fewer people leave. [Retention #6, Pricing play #5]

### Downsell (only for people who do not qualify for the core)

Self-serve: the 7-day trial, no setup help. Never offer this to a qualified seller. [LTV #7]

### US Grow offer (unchanged from version 1)

Free 15-minute "Shop Leak Audit", setup done with you, 60 days free, $10 a month locked for life, capped at 20. Later, test "Pro with an analyst" at about $99 a month.

---

## 5. Your lead list: what is wrong with it, and what I did

### What the scrape gives you, and what it misses

`OneTapManager_500_Instagram_Leads_1.xlsx` has 500 primary leads plus 594 buffer leads, found through seller hashtags.

| Problem | Evidence | Why it matters |
|---|---|---|
| No follower count, bio, link in bio, email or phone | The "Read me" tab says enrichment hit the Apify monthly limit | You cannot tell **Launch** sellers (no website) from **Grow** sellers (has a website). That is now the most important field |
| Weak activity signal | 272 of the primary 500 were seen in only 1 post. Median top-post likes: 6. The 594 buffer leads were all seen in 1 post, median 1 like | Many are tiny or inactive |
| No last-post date | | You may DM shops that stopped selling months ago |
| Off-target accounts mixed in | 51 wholesalers ("suratsareewholesaler", "kurtiwholesaler", names with "wholesale"); home bakers and chocolatiers; candles, pottery, resin art | Wholesalers sell to resellers, not shoppers. Food is perishable and local. Both need different offers |

### What I built: `D:\Claude\leads\OTM_Leads_Triaged.xlsx`

All 1,094 leads, sorted, with a rough pre-score based on the data you have (niche, posts seen, likes, name, location):

| Tier | Count | What to do |
|---|---|---|
| **A** | 168 (153 from your primary list) | Enrich first. DM personally this week |
| **B** | 413 | Enrich, re-score, DM after A |
| **C** | 462 | Skip for now. Most are tiny or inactive |
| **Park: wholesale** | 51 | Different business. Hold for a later offer |

The sheet also has:

- **Empty columns to fill**, ready for enrichment (orange headers)
- **CRM columns** (green): DM dates, reply, preview, call, signup, first website order, paid, their exact words, and a Status dropdown
- **"Scoring rules"** tab with the full scoring below

The pre-score is a rough first sort. **The final score needs the enriched data.** Do not treat a pre-score A as a qualified lead until you have opened the profile.

Keep the `leads` folder out of git. It holds other people's data.

---

## 6. Lead rules: who to contact, and how to scrape

### Hard excludes (never contact)

- Not a product seller: services, salons, makeup artists, agencies, coaches, quote or meme pages
- Private account, or no post in the last 45 days
- Under 300 followers (no audience; a launch sale would get no orders)
- Over 150,000 followers (has a team or an agency)
- Only reposts other brands' photos (catalogue reseller or dropshipper)
- Bio says "wholesale only", "MOQ" or "resellers welcome" (move to the wholesale tab)
- Anyone who has told you "not interested" (keep a do-not-contact list forever)

### The final score (100 points)

| Group | Signal | Points |
|---|---|---|
| **Fit (35)** | Core niche: clothing, jewellery, fragrance | 15 (beauty 10, lifestyle 6, food 2) |
| | 1,000 to 50,000 followers | 15 (300 to 1,000 or 50k to 150k: 7) |
| | Business account with a shop category | 5 |
| **Pain (30)** | **Launch:** no website; link is wa.me, Linktree, Google Form, Meesho, or empty | 15 |
| | **Grow:** Shopify, WooCommerce, Wix, Dukaan, Instamojo or own domain | 10 |
| | Bio says "DM to order", "WhatsApp to order" or "COD available" | 10 |
| | 3+ "price?", "pp", "rate?" or "dm" comments across the last 12 posts | 5 |
| **Activity (25)** | 8+ posts in the last 30 days (4 to 7: 5 points) | 10 |
| | Posted a reel in the last 30 days | 5 |
| | Average 5+ comments on the last 12 posts | 5 |
| | Replies to customers in comments | 5 |
| **Reach (10)** | Public business email or phone | 5 |
| | Has a "reviews", "feedback" or "customer love" highlight | 5 |

**Tiers:** A is 70+ (make the preview before you DM). B is 50 to 69 (DM, offer the preview). C is under 50 (follow and engage only; re-score in 30 days).

**Red flags (drop one tier):** engagement under 0.3% with 10,000+ followers (bought followers); the same photos on many accounts (catalogue reseller).

**The best single signal for the Launch track:** lots of "price?" comments plus "DM to order" in the bio. That seller is drowning in DMs and is your perfect customer.

### What to scrape for every lead

| Field | Why |
|---|---|
| Followers, following, total posts | Size band and red flags |
| Business account (Y/N) and business category | Confirms a shop |
| Bio text | "DM to order", "COD", "WhatsApp", "wholesale", city, language |
| **Link in bio (external URL)** | **Decides the track** |
| Last 12 posts: date, likes, comments, reel or not | Activity, engagement rate |
| Public email and phone | Second channel, only after they reply on Instagram |
| Highlight titles | "Reviews" means existing customers and proof |
| Comments on the last 12 posts (optional, costs more) | Count price questions |
| Location or city | India or US, regional language |

**Sort the link into a type:**

| Link contains | Type | Track |
|---|---|---|
| nothing, `wa.me`, `api.whatsapp.com` | WhatsApp only | Launch |
| `linktr.ee`, `bio.link`, `beacons.ai` | Link page | Launch (open it to check) |
| `forms.gle`, `docs.google.com/forms` | Order form | Launch |
| `meesho.com`, `amazon.in`, `flipkart.com` | Marketplace only | Launch (they rent, don't own) |
| `mydukaan.io`, `dukaan.app`, `instamojo` | Light store | Grow, or upgrade to Launch |
| `myshopify.com` or the page loads `cdn.shopify.com` | Shopify | Grow |
| `wp-content` and `woocommerce` in the page | WooCommerce | Grow |
| `wixsite.com` or `wixstatic` | Wix | Grow |

### How to scrape

1. **Enrich what you have first.** Run Apify's Instagram Profile Scraper on the 581 A and B handles before scraping anything new. It returns followers, bio, external URL, business category and recent posts. Doing A and B first saves credits.
2. **Then scrape new leads with better sources than broad hashtags:**
   - **Intent hashtags** (they name the pain): `#dmtoorder`, `#dmforprice`, `#dmfororders`, `#whatsappfororders`, `#codavailable`, `#cashondelivery`, `#shippingallindia`, `#freeshippingindia`
   - **Niche plus city** (local, real shops): `#suratkurtis`, `#jaipurijewellery`, `#bangaloreboutique`, `#hyderabadboutique`, `#mumbaiboutique`, `#lucknowchikankari`, `#attarlucknow`
   - **Lookalikes:** take your 10 best-fit sellers and collect the "suggested accounts" and the accounts that follow them. Fit sellers cluster.
   - **US:** `#boutiqueowner`, `#shopsmall`, `#handmadejewelry`, `#jewelrybusiness`, `#indieperfume`, `#perfumeoil`, then keep only accounts with a Shopify link and a US location
3. **Search bios, not just hashtags.** Keyword search for "DM to order", "COD available", "WhatsApp for orders" finds exactly the Launch seller.
4. **Every 30 days:** re-scrape active leads (last post date, followers), remove duplicates by handle, and never re-add anyone on the do-not-contact list.

### Data rules

- Business accounts and public business data only. No personal accounts.
- Store only what you need for outreach. Delete a seller's data when they ask (India's DPDP Act, and good manners).
- Scraping is against Instagram's terms. Never scrape while logged in with your own or the brand's Instagram account. Use the scraper's own sessions so your selling account is never at risk.

---

## 7. Outreach for the Launch track (India)

### Channels, in order

| Rank | Channel | Notes |
|---|---|---|
| 1 | **Instagram DM** to scored A and B leads | Engage first. 30 a day, rising slowly |
| 2 | **Warm network** (family, school friends in Gujarat, Great Lakes alumni, colleagues) | "Do you know a shop owner who sells on Instagram?" Introductions convert best [lesson03] |
| 3 | **In person, weekends** | Bengaluru boutiques: show a preview on your phone. In-person proof beats virtual [Proof Checklist] |
| 4 | **WhatsApp** | **Only after they reply** on Instagram or share their number. Cold WhatsApp pitches get reported, and reported numbers get banned |
| 5 | Organic content | Section 10 |

### Step 0: engage before you DM

Follow, like 2 or 3 posts, leave one real comment about a product. DM a day or two later.

### DM 1: the preview offer (English)

> Hi [Name], the [specific product] in your last post is lovely.
>
> Quick question: do your orders still come only through DMs and WhatsApp?
>
> I built an app that gives small shops their own website (UPI and COD), keeps Instagram posting and tracks stock. I'm setting up 20 shops for free before Diwali. Can I make a free preview of your website with 3 of your products? Only you see it. Nothing goes live without your OK.

### DM 1 (Hinglish)

> Hi [Name], aapka [product] bahut sundar hai.
>
> Ek sawaal: orders abhi sirf DM aur WhatsApp pe aate hain?
>
> Maine ek app banaya hai jo chhote shops ko apni website deta hai (UPI aur COD ke saath), Instagram posts schedule karta hai aur stock track karta hai. Diwali se pehle 20 shops free mein set up kar raha hoon. Kya main aapke 3 products ke saath aapki website ka free preview bana doon? Sirf aap dekhenge, aapke OK ke bina kuch live nahi hoga.

### Short opener (for busy accounts)

> Hi [Name], love the [product]. How many "price?" messages do you answer in a day?

If they reply, send the middle and last paragraph of DM 1.

### Rules for every DM

- The first line is about them, never about you.
- No link in DM 1. Under 70 words. One question.
- Use their language. If their captions are in Hindi or Hinglish, write in Hinglish.
- Never paste the same message twice. Instagram limits accounts that do.

### Follow-ups (only if no reply)

- **Day 3:** "Hi [Name], bumping this in case it got buried. Happy to send the preview, no strings."
- **Day 7 (give value, no ask):** one specific Brand Score tip. Example: "Small tip: put your price in the first line of each caption. It cuts 'price?' DMs and people who see a price are more likely to order."
- **Day 14 (last):** "Last message from me. If the timing's wrong, no problem at all. If you ever want the free website preview, just reply 'preview'."

### When they say yes

1. Ask for 3 product photos with names and prices (or take them from their posts, with their OK).
2. Build the preview in your demo account. Send a 30-second screen recording **within 24 hours** (speed wins the sale [Lead Nurture]).
3. "Want to make this your real website? 30 minutes on a call, I'll set it up with you. [Today 8 pm] or [tomorrow 7 pm]?" Book inside 72 hours. [Lead Nurture]

### Replies to common pushback [Closing]

| They say | You say |
|---|---|
| "Price kitna hai?" | "Founding shops: setup free, 60 days free. After that ₹1,299 a month, cancel any time. We never take a cut of your sales." |
| "Instagram pe hi sell ho jata hai" | "Totally, and the website doesn't replace that. It means a shopper who sees your post can see the price and order at 2 am without waiting for you to reply. Your Instagram is the shop window; the website is the counter." |
| "Mere paas Meesho / Dukaan hai" | "Great, keep it. On Meesho the customer belongs to Meesho. Your own site keeps the customer, so you can bring them back next festival." |
| "Time nahi hai" | "That's exactly why. It's one 30-minute call, I do most of the setup with you, and after that the app does the daily work." [Closing, "Reason" close] |
| "Sochke batati hoon" | "Of course. What's your main concern? Price, time, or whether customers will actually use it?" [Closing, "Main concern"] |
| "Fraud toh nahi?" | "Fair question. Payments go straight to your own UPI ID or Razorpay account, never through us. No card needed to start, and you can delete everything from the Account tab." |
| "Not interested" | "No problem at all, thank you for replying. All the best for the festive season." Mark do-not-contact. |

### Grow-track DMs (India sellers with a website, and US)

Use the version 1 "Shop Leak Audit" DM, adapted: "do you know how many customers bought once and never came back?" Free 15-minute audit, setup done with you, 60 days free.

---

## 8. The Launch call (30 to 45 minutes)

Hormozi's structure: understand what they want, put it next to their options, help them make a real decision. [Closing, "Power"]

**Before the call**, send: "Looking forward to it. Keep 10 to 25 product photos with names and prices handy, and your UPI ID. Payments always go straight to you."

**1. Frame (1 minute)**
> "Plan: a few questions about the shop, then we build your website together. At the end you decide if you want it live. Fair?"

**2. Discovery (5 minutes)** Write down their exact words. They become your ad copy.
1. "How do orders come in today? How many DMs a day?"
2. "How much time goes on 'price?' and 'available?' messages?"
3. "How do you keep track of who bought and what's in stock?"
4. "What do COD returns cost you?"
5. "When you picture your shop as a real brand, what does it look like?"
6. "If this worked perfectly, what would change for you by Diwali?" [lesson04, "magic question"]

**3. Build part 1 together (20 minutes)**
They sign up on their own phone. The app's setup runs: shop name, products, look, web address, WhatsApp, owner details, delivery, preview, publish, UPI. Let them drive. Help only when stuck, and note every stall.

**4. The reveal (2 minutes): film this, with permission**
Their site goes live. Ask: "Can I record your reaction for 10 seconds?" These reactions are the strongest ads you will ever have. [Marketing Machine, "upon delivery" ads; GOATed Ads, demonstration]

**5. The launch sale plan (5 minutes)** Section 9. Pick the launch date together.

**6. Close**
- "On a scale of 1 to 10, how happy are you with it?" Anything under 10: "What would make it a 10?" [Closing, "1 to 10"]
- Mention the Brand Partner tier once, as the anchor. Then confirm the founding offer.
- Once they say yes, stop selling. [Closing, rule 26]

---

## 9. Making the first win happen: the seller's launch sale

The Launch track's activation point is **the first order on their own website**. Sellers who reach the first win stay. [Retention #1 and #2] So the setup includes a 5-day **launch sale**: a Fast Cash play for *their* shop, aimed at their warmest audience: followers, past WhatsApp buyers, and saved contacts. [Fast Cash]

| Day | Instagram | WhatsApp (from their own phone) |
|---|---|---|
| -2 | Story: "Something big is coming on [day]" | Status: same teaser |
| 0 | Post plus Story with link sticker: "We're live! Order on our website. Launch offer: [free shipping / a gift] for the first 50 orders" | Broadcast list to past buyers, plus Status with the link |
| 1 | Story: a product from the site, with its price | Reply to every question with the product link, not a long chat |
| 2 | Story: "[X] orders already, thank you!" (real number only) | Status update |
| 4 | Story: "Last day for the launch offer" | Final broadcast |
| 5 | Story: "Launch offer closed. Thank you!" | |

From the next day on, every "price?" comment and DM gets the product link. That habit is what moves the shop from chat to brand.

**You capture:** the order count, screenshots of the first orders (with the seller's OK), and a 60-second video on day 7 using the 6-point script: before (feeling), before (numbers), doubt, why they tried anyway, after (numbers), after (feeling). [Marketing Machine]

---

## 10. Content and ads

### Organic content (start now, 3 to 4 posts a week, both markets)

- **India: Hinglish reels.** US: the 12 existing US scripts, run Grow-track posts first.
- **Weekly series: "DM shop to brand"**, one real seller per episode (with permission): their Instagram before, the website after, the first orders.
- **Build in public:** "0 / 20 shops live before Diwali," with a daily Story counter. With zero customers, honesty is your proof.
- Every Friday, check 3-second hold, shares and saves. Make more of the top one. [Hooks, 70-20-10]

### Hooks to test [Hooks, GOATed Ads]

| # | Hook | Type | Market |
|---|---|---|---|
| 1 | "Still taking orders in DMs? Watch this before Diwali." | Command | IN |
| 2 | "'Price?' comment ka reply dete dete din nikal jaata hai?" | Question | IN |
| 3 | "Your Instagram is your shop window. Your DMs are not a checkout." | Statement | IN, US |
| 4 | "I turned this saree shop's DMs into a website in 30 minutes." (real seller only) | Story | IN |
| 5 | "Watch her see her own website for the first time." (real seller only) | Story | IN |
| 6 | "Meesho pe customer Meesho ka hota hai. Apni website pe, aapka." | Statement | IN |
| 7 | "3 things every Instagram shop needs before Diwali." | List | IN |
| 8 | "By day I analyze a $4 billion inventory. At night I build websites for small shops." | Story | IN, US |
| 9 | "How many of your customers bought once and never came back?" | Question | US, IN Grow |
| 10 | "Shopify owners: your next orders might already be in your customer list." | Label | US |

### Four ad scripts (30 to 45 seconds) [GOATed Ads: hook, meat, CTA]

**Ad A: "DM chaos to website" (demonstration, India)**
- Hook: "Still taking orders in DMs?"
- Meat: screen recording of a phone full of "price?" DMs, then the app's setup, then a live shop site with prices, cart, UPI and COD (sample shop, tagged SAMPLE SHOP DATA). "30 minutes. Your products, your prices, your UPI. Shoppers order while you sleep."
- CTA: "I'm setting up 20 shops free before Diwali. Comment WEBSITE and I'll send you the details."

**Ad B: "The reveal" (testimonial, once you have one)**
- Hook: the seller's real reaction to her site going live.
- Meat: her 20-second story: before (DMs all day), after (orders on the site).
- CTA: same as Ad A. Expect this to beat everything else. [Marketing Machine: 40 of Hormozi's top 50 ads didn't feature him]

**Ad C: "Brand Score" (education, India and US)**
- Hook: "3 things every Instagram shop needs before [Diwali / Black Friday]."
- Meat: price in the first line of the caption; a "How to order" highlight; a link that takes the shopper to a product page, not a chat. Show each on a real profile.
- CTA: "Comment SCORE and I'll score your shop for free."

**Ad D: "The analyst" (story, both markets)**
- Hook: hook 8.
- Meat: "Big brands have a team. Small shops have one person doing six jobs. So I built One Tap Manager: your own website, posts that go out on time, stock that tracks itself. You approve, it does the work. No cut of your sales."
- CTA: India: "Comment WEBSITE." US: "Comment AUDIT."

Set up the comment-keyword auto-DM (WEBSITE, SCORE, AUDIT) and test each one from a second account before posting.

### Where to post

- **India:** Instagram Reels and Stories, WhatsApp Status (yours), YouTube Shorts (re-upload the same reels).
- **US:** Instagram Reels and Facebook Reels.
- Facebook groups and Reddit: helpful answers only, with "Disclosure: I built One Tap Manager."

### What to boost, and when

**Do not spend until all four are true:** (1) 3 real seller launches you can show; (2) the auto-DM works; (3) a post beat your average on 3-second hold and shares; (4) the seller can sign up and pay without you.

| Rule | India | US |
|---|---|---|
| What | Only your top 10% organic posts. Good organic posts make good ads [Marketing Machine] | Same |
| Where | Meta Ads Manager, objective Messages or Leads (not the Boost button, which optimizes for likes) | Same |
| Audience, first | People who engaged with your profile in the last 90 days [GOATed Ads: warmest first] | Same |
| Audience, then | India, women 22 to 45, interests: online boutique, ethnic wear, jewellery, small business, Meesho, Instagram shopping | US, 25 to 54: Shopify, boutique, small business owner |
| Daily budget (assumption) | ₹300 to ₹500 per ad, 3 to 5 days | $5 to $10 per ad, 3 to 5 days |
| First-month cap (assumption) | ₹10,000 | $150 |
| Kill rule | No preview requests after ₹1,500: change the hook | No audits after $50: change the hook |
| Scale rule | An ad bringing sellers in for less than one month's subscription: keep it, write 10 new hooks for it [GOATed Ads] | Same |

---

## 11. Your resume: how to use it

Your day job is your credibility: you analyze inventory for a $4B+ portfolio, and you know reorder points, demand forecasting and customer grouping by how recently and often they buy. For a shop owner, say it plainly:

> "By day I'm a supply chain analyst at a semiconductor company. I built One Tap Manager so small shops get the same kind of help without a team."

Put it in your bio, in the **second** line of a DM (never the first), at the start of calls, and in ad D.

Before naming Lam Research in public, check its outside-work and social media policy and your contract's IP clause. Until then, say "a semiconductor company".

---

## 12. What to do, when

Today is Friday 2 October 2026.

### This weekend (3 and 4 October): get ready

- [ ] Enrich the 168 Tier A leads (Apify Profile Scraper), fill the orange columns, apply the final score. Then do the 413 Tier B leads
- [ ] Make a **demo account** for previews with a good theme ready
- [ ] Test UPI checkout on GPay, PhonePe and Paytm with a real ₹1 order
- [ ] Per-account trial extension for 60-day founders (needs a small code change)
- [ ] Update `Brand.md` pricing and plan names (Free and Max ₹999 are gone)
- [ ] Instagram profile: bio with your analyst line, link, "How it works" highlight, auto-DM for WEBSITE
- [ ] Check your employer's outside-work policy
- [ ] US: run the Shopify precondition check from the five-seller test

### Week 1 (5 to 11 October): first previews

- [ ] India: 30 personal DMs a day from Tier A, plus 10 warm-network messages a day
- [ ] US: 15 Grow-track DMs a day
- [ ] Send every preview within 24 hours; book calls inside 72 hours, 7 to 10 pm IST
- [ ] Goal: 10 previews sent, 4 websites live, 2 launch sales started
- [ ] Post the build-in-public "0 / 20" reel; daily Story counter

### Week 2 (12 to 18 October): first wins

- [ ] DMs up to 40 a day; start Tier B
- [ ] Run launch sales with week-1 sellers; capture first orders and reactions
- [ ] Fix the single biggest stall you saw on calls. Only that one [lesson03]
- [ ] Goal: 8 websites live, 3 with a first website order

### Weeks 3 and 4 (19 October to 1 November): Diwali push

- [ ] "Last chance to go live before Diwali" is a real deadline: use it in DMs and Stories
- [ ] First "DM shop to brand" episode with a real seller
- [ ] If the 4 conditions in section 10 are true, start boosting at ₹300 to ₹500 a day
- [ ] Goal: 15 to 20 websites live, 3 video testimonials

### Diwali week (around 2 to 8 November)

- [ ] Help every founding seller run a Diwali offer to past buyers through their website. Their results are your best proof
- [ ] Close the founding 20. Move to the ₹1,999 setup tier

### November, US: Black Friday (27 November) and Cyber Monday (30 November)

- [ ] US Grow sellers: help each one send a pre-Black Friday win-back to past buyers

### Day 30 decision (about 1 November)

| Result | Next step |
|---|---|
| 60%+ of launched sellers got a first website order in 7 days, and at least 1 pays at full price | Keep the Launch track. Raise the setup fee. Start the Brand Partner test |
| Sellers stalled during setup | Fix setup before recruiting more |
| Sites went live but got no orders | The launch sale or the audience is wrong. Raise the minimum follower count and look at what the sellers with orders did differently |
| No one will pay after 60 days | Ask "what would it take?" and change the offer, not just the price [lesson04] |

---

## 13. Numbers to track every Friday

| Number | Launch (India), by week 4 (assumption) | Grow (US), by week 4 (assumption) |
|---|---|---|
| DMs sent | 700 | 300 |
| Reply rate | 15%+ | 10%+ |
| Previews or audits sent | 60 | 15 |
| Calls held | 30 | 10 |
| Live websites, or first win-back sent | 20 | 5 |
| **First website order within 7 days** | 60% of live sites | n/a |
| Returned on day 2 or 3 unprompted | 50% | 50% |
| Paying after the free period | measured from day 60 | at least 1 |
| Video testimonials | 3+ | 1+ |

---

## 14. Sources used

- `$100M Playbook: Fast Cash` (limited offers to the warmest audience: used for the seller's launch sale)
- `$100M Playbook: Lifetime Value` (Crazy 8: cross-sell, downsell only to the unqualified, price nudges)
- `$100M Playbook: Pricing` (play #9 ultra high ticket anchor, play #5 annual billing)
- `$100M Playbook: Marketing Machine` ("upon delivery" reaction ads, 6-point testimonial script)
- `$100M Playbook: Proof Checklist` (results before they buy, in person over virtual)
- `$100M Playbook: Hooks` and `GOATed Ads` (hook types, awareness levels, hooks x meat x CTA)
- `$100M Playbook: Closing` (main concern, reason, 1 to 10, rules of closing)
- `$100M Playbook: Lead Nurture` (speed to contact, calls inside 72 hours)
- `$100M Playbook: Retention` (activation point, onboarding, annual plans)
- Acquisition Scaling Course, lesson 03 (Improvise) and lesson 04 (Monetize)
