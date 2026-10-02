# One Tap Manager: go-to-market plan, version 3

Written 2 October 2026. Version 3 replaces versions 1 and 2.

**The premise (Harsh's call):** a website is not a moat. Anyone can sell a website. The moat is **a system that runs the business**: it knows every customer, notices who went quiet, writes the message, tracks stock, plans the posts, and gets smarter every month. So we lead with the system, not the website.

- **The entry is a free Win-Back Session**, done on the seller's screen, with them.
- **If they have order data**, the session shows the system working on their own shop. We sell the system.
- **If they have no data**, the session shows them what they are missing. We sell the website as the way into the system, because a website captures every order.

Built from `Product.md`, `Brand.md`, the code, Harsh's CV, the lead list, and the Hormozi playbooks named in brackets. Numbers marked **(assumption)** are planning guesses: replace them with your own after week 1.

---

## 1. The short answer

| | What happens |
|---|---|
| **The hook** | "Customers who bought once and went quiet: let's find them and bring them back. Free, 20 minutes, on your screen, with me." |
| **Branch A: has data** | Upload their orders. The app finds the quiet customers and writes a message for each. **They send the first 5 to 10 messages on WhatsApp while we're on the call.** Then we show what else the system does. Sell: the system |
| **Branch B: no data** | Show a sample shop with data, labelled as a sample. Ask: "Could you list your 20 quiet customers right now?" Send 5 by hand from their chats. Sell: website + system, so every order is captured from now on |
| **The moat** | The longer a shop uses the system, the more it knows about their customers and stock. Leaving means losing that |
| **Markets** | India: both branches ready. US: Branch A ready to test; Branch B on hold (card checkout off) |

**Why this is a strong Hormozi entry offer:**

- It is the **"reveal the problem" free offer** (the chiropractor's posture check): it shows a problem only the paid product fixes. [lesson03]
- It **gives a result before they buy**: replies, sometimes an order, during the call. That is the strongest proof there is. [Proof Checklist]
- **Win-back is the cheapest growth play there is**: selling to people who already bought. It is Hormozi's own "Fast Cash" and "follow up" play, aimed at their shop. [Fast Cash, LTV #3]
- **Branch B's realisation is a built-in close**: "The reason you can't do this is the reason you need it." [Closing, "Reason" close]

---

## 2. Why the system is the moat

A website is a commodity. Shopify, Dukaan, Wix and any freelancer can build one. Competing on websites means competing on price.

A system that **acts on the data** every week is different:

1. **It compounds.** Every order teaches it more about who buys what, when, and who is slipping away. Month 6 is more useful than month 1. [Retention: "provide on-going value to get on-going customers"]
2. **It creates a weekly habit.** The weekly win-back list arrives; the seller approves and sends. Repeat purchases for them, renewals for us. [LTV #3, "add recurring"]
3. **Leaving costs something.** Their customer history, stock levels and post plans live in it.
4. **It is the "team" in your brand promise.** `Brand.md`: "You already have the team's knowledge in your data. You are missing the team."

So the free session sells the system. The website is only the pipe for sellers who don't have one yet.

---

## 3. What the app does today (so you only promise what ships)

Checked in the code on 2 October 2026:

| In the session you can say | Where it comes from |
|---|---|
| "Upload any order file; the app suggests which column is what" | `backend/core/mapper.py` needs at least a date and an amount; customer, phone and email are picked up when present |
| "These are the customers slipping away, ranked by what they spent" | `analytics.at_risk_customers`: customers grouped by how recently and often they buy and how much they spend; the "At Risk" group, highest spenders first |
| "Each message is written for that customer: their favourite item, and what usually goes with it" | Customer profiles feed the AI message writer (favourite item, cross-sell item) |
| "Tap Send on WhatsApp: it opens WhatsApp with the message already typed" | `campaigns.py`: while WhatsApp sending is off, every customer with a phone gets a `wa.me` link with the message filled in |
| "It counts who came back" | `winback_proof` logs every send and measures returns against it |
| "It can prepare this every week for you to approve" | `winback_auto.py`: a weekly batch, skipping anyone messaged recently |

**Never say:**

- "We message your customers automatically on WhatsApp." The seller taps send for each one.
- Any result you have not seen. Say "let's see who replies," not "you'll get 5 orders."
- "We run your ads." Ad figures are demo data until platform review.

**What a seller needs for Branch A (assumption, check after 10 sessions):** at least about 40 customers over 3+ months, with a name or phone for each. With fewer, the "slipping away" group is too small to be convincing. Treat it as Branch B with some data.

**Test before your first call:**

- Upload a real **Shiprocket** export, a **Razorpay** payments export, a **Meesho** order report, a **Dukaan** export and a **Shopify** export. Confirm each maps and produces a win-back list. Indian DM sellers often have one of the first three even without a website.
- Tap "Send on WhatsApp" on a phone and confirm the message arrives typed.
- Check that an AI message is generated for a real-looking customer row.

---

## 4. The offer stack

### Free entry: the Win-Back Session (20 to 30 minutes, on their screen)

> "Let's find the customers who bought from you and went quiet, and bring a few back today. Free, on your screen, with me. You send the first messages while we're on the call."

### Core product: the One Tap system

What they buy is **the system**: the weekly win-back list, stock and reorder alerts, the Instagram planner, sales analytics, GST invoices (India). Founding sellers (first 20 per market):

| | India | US |
|---|---|---|
| Free period | 60 days | 60 days |
| Then (locked for life) | ₹1,299 a month (Pro Max) or ₹700 (Pro) | $12.99 (Pro Max) or $10 (Pro) |
| Annual option | ₹12,990 a year (2 months free) [Pricing play #5, Retention #6] | $129 a year |
| The exchange | Honest feedback, permission to share results, a short video if it helped [lesson03, "the 4 Rs"] | Same |

### Branch B add-on: the website, sold as the way into the system

Never pitch it as "a website". Pitch it as: **"Your website is how the system sees every order."**

| Branch B sellers | Website setup (done with you, about 2 hours) |
|---|---|
| 1 to 10 | Free (they become your proof that the system works for DM shops) |
| 11 to 20 | ₹1,999 |
| 21+ | ₹2,999, then raise about 20% every 10 sales until sales drop [LTV: "nudge the price 20% every 10 sales"] |

Setup includes a **5-day launch sale** to their followers and WhatsApp contacts. It brings first orders, and every order fills the system with data (section 9).

### Premium anchor: Analyst on call (cap: 3 per market)

A monthly 45-minute numbers review with you, festival and holiday campaigns planned for them, and the weekly win-back reviewed before it goes out. **India ₹14,999 a month, US $149 a month**, about 10x the core price. [Pricing play #9] Mention it once on every call. It makes the core offer feel easy. Only keep it if you are happy when someone buys it.

### Downsell (only for people who don't qualify)

Self-serve 7-day trial, no session follow-up. Never offer it to a qualified seller. [LTV #7]

### Quarterly add-on (later)

"Festival Win-Back, done for you": you plan and write a Diwali or Black Friday win-back campaign for them. Sold to existing customers once a quarter. [Fast Cash, "run them every 90 days"]

---

## 5. The Win-Back Session, step by step

Hormozi's selling structure: understand what they want, put it next to their options, help them reach a real decision. [Closing, "Power"]

**The day before**, send:

> "Looking forward to it! Before we talk, find any file with your past orders: Shopify / Dukaan / Instamojo export, Shiprocket or courier report, Razorpay payments, Meesho orders, an Excel sheet or Google Form. If orders only live in WhatsApp, that's fine too, we'll work with that. You'll upload it yourself; I never handle your customers' data."

### 0:00 Frame (1 minute)

> "Plan: a couple of questions, then we find your quiet customers and you send a few messages. At the end you decide if you want the app to do this every week. Fair?"

### 1:00 Discovery (4 minutes): write down their exact words

1. "Roughly how many customers have bought from you, ever?"
2. "When a regular stops buying, what happens?"
3. "Who bought from you last Diwali [US: last Black Friday]? Have you messaged them this year?"
4. "Where do your orders get recorded?"
5. "If you could bring back 1 in 10 of your old customers this month, what would that mean?" [lesson04, "magic question"]

### 5:00 Find the data (3 minutes)

They open their file and upload it on their own screen. The app suggests the column mapping; they confirm it. **This decides the branch.**

### Branch A: they have data (15 minutes)

1. **Open Today.** Point at the win-back card: "[X] customers who used to buy are slipping away. Together they spent [₹Y]." Use their real numbers only.
2. **Open the list.** Scroll it with them: names they recognise, last bought, favourite item. Let them react. ("Oh, Priya used to order every month!")
3. **Show one written message.** Read it out. Let them edit the tone.
4. **They send 5 to 10 now.** They tap "Send on WhatsApp" for each, on their phone. **This is the activation moment.** [Retention #1]
5. **While waiting for replies, show two more things**, briefly:
   - best sellers and what is running low (stock, reorder);
   - "Every week this list builds itself. You approve, you send."
6. **Check WhatsApp.** If someone already replied, stop and enjoy it with them. It sells better than anything you can say.

### Branch B: no usable data (15 minutes)

1. **Show the sample shop**, clearly labelled: "This is a sample shop, not real customers." Load the app's sample data and open Today: the win-back card, the list, a written message, the low-stock alert.
2. **The question:**
   > "This shop can see exactly who went quiet. Could you list your 20 quiet customers right now?"
   Let the silence work.
3. **Win-back by hand.** "Let's do 5 anyway." Open their WhatsApp, scroll to people who bought 2 to 6 months ago, and write a short personal message together. They send it.
4. **The realisation** [Closing, "Reason" close]:
   > "That took 10 minutes for 5 people. You have maybe [200] past customers. The reason you can't do this for all of them is that your orders live in chats, where no system can see them. The fix is simple: take orders on your own site. Every order then lands in the system, and in a month or two it can do what you saw in the sample shop, every week, by itself."
5. **Offer:** website + system, with the launch sale to fill it fast.
6. **US Branch B:** card checkout is not live yet. Say so honestly, offer the 5-by-hand win-back as a gift, and put them on a "tell me when it's ready" list.

### 25:00 Close (3 minutes)

- "On a scale of 1 to 10, how useful was that?" If under 10: "What would make it a 10?" [Closing, "1 to 10"]
- Anything that isn't yes: "What's your main concern?" [Closing]
- Mention Analyst on call once, as the anchor. Then confirm the founding offer.
- Once they say yes, **stop selling.** [Closing, rule 26]

### After yes

- **Branch A:** switch on the weekly win-back. Book a 10-minute day-4 check-in: "How many replied? Any orders?"
- **Branch B:** book the website setup session within 72 hours. [Lead Nurture] Pick the launch-sale date.

**With permission, record the session.** The "before" (no idea who went quiet), the "during" (sending), and the "after" (replies, orders) make a complete customer-journey ad. [Marketing Machine, "lifecycle ads"]

---

## 6. Who to contact: lead rules for version 3

Version 3 changes what "a good lead" means. We no longer want sellers *without* websites. We want **sellers with past customers worth winning back.** The link in bio now predicts the **branch**, not whether to contact them.

### Hard excludes (never contact)

- Not a product seller: services, salons, makeup artists, agencies, coaches, meme pages
- Private, or no post in 45 days
- Under 300 followers, or over 150,000 followers
- **Selling for under 6 months** (not enough past customers to win back)
- Wholesale only, "MOQ" or "resellers welcome" (parked for a later offer)
- Anyone who said "not interested" (keep a do-not-contact list forever)

### Final score (100 points, after enrichment)

| Group | Signal | Points |
|---|---|---|
| **Fit (30)** | Core niche: clothing, jewellery, fragrance (beauty 10, lifestyle 6, food 2) | 15 |
| | 1,000 to 50,000 followers (300 to 1,000 or 50k to 150k: 7) | 10 |
| | Business account with a shop category | 5 |
| **Past customers (35): the new core** | Selling 12+ months (first post a year ago, or 150+ posts); 6 to 12 months: 5 | 10 |
| | "Reviews", "feedback" or "customer love" highlight, or "ordered again" / "repeat customer" in posts | 10 |
| | Ships pan-India / US-wide, or offers COD (a courier export probably exists) | 5 |
| | 3+ "price?", "pp" or "available?" comments across the last 12 posts (live demand) | 10 |
| **Activity (25)** | 8+ posts in the last 30 days (4 to 7: 5) | 10 |
| | Reel in the last 30 days | 5 |
| | Average 5+ comments on the last 12 posts | 5 |
| | Replies to customers in comments | 5 |
| **Reach (10)** | Public business email or phone | 5 |
| | Bio in a language you can write naturally (English, Hindi, Hinglish) | 5 |

**Tiers:** A is 70+ (DM this week). B is 50 to 69 (DM after A). C is under 50 (follow and engage; re-score in 30 days).

**Red flags (drop a tier):** engagement under 0.3% with 10,000+ followers (bought followers); the same photos on many accounts (catalogue reseller).

### Predict the branch from the link in bio

| Link | Likely branch | Why |
|---|---|---|
| Shopify, WooCommerce, Wix, Dukaan, Instamojo, own domain | **A** | Orders are exportable |
| Meesho, Amazon, Flipkart | **A** (marketplace report) | Order reports exist, but often without customer phones. Check on the call |
| `wa.me`, WhatsApp number, Linktree, Google Form, nothing | **B, or A if they use Shiprocket or Razorpay** | Ask before the call |

**Week 1 priority: likely-A leads first.** A shows the system working on real data during the call, which is the fastest proof. [lesson03] Mix in B leads from week 1 so you learn both scripts.

### What to scrape for every lead

Followers, following, total posts, **first post date**, business account and category, **bio text**, **link in bio**, last 12 posts (date, likes, comments, reel or not), **highlight titles**, public email and phone, location. Optional (costs more): comments on the last 12 posts, to count price questions and "ordered again" mentions.

### Better sources than broad hashtags

- **Repeat-customer signals:** `#happycustomer`, `#customerreview`, `#customerlove`, `#repeatcustomer`, `#thankyouforshopping`, `#feedbackfriday`. Sellers who post reviews **have customers to win back.**
- **Shipping and COD signals (India):** `#codavailable`, `#shippingallindia`, `#panindiadelivery`, `#cashondelivery`
- **Niche plus city:** `#suratkurtis`, `#jaipurijewellery`, `#bangaloreboutique`, `#lucknowchikankari`, `#attarlucknow`
- **Lookalikes:** the "suggested accounts" and followers of your 10 best-fit sellers
- **US:** `#boutiqueowner`, `#shopsmall`, `#handmadejewelry`, `#indieperfume`, plus a Shopify link and a US location
- **Bio search:** "DM to order", "COD available", "worldwide shipping", "since 2019"

### Data rules

- Business accounts and public business data only.
- Keep only what outreach needs. Delete a seller's data when asked (India's DPDP Act).
- Scraping is against Instagram's terms. Never scrape while logged in with your own or the brand's account.
- **The seller always uploads their customers' data themselves, into their own account.** Never collect customer files by DM or email.

### Your current list

`D:\Claude\leads\OTM_Leads_Triaged_v3.xlsx` holds all 1,094 leads with a rough pre-score: **168 A, 413 B, 462 C, 51 wholesale parked.** Its columns match version 3: likely branch, where orders are recorded, and session results (messages sent, replies, orders, weekly win-back on). It replaces `OTM_Leads_Triaged.xlsx`. The pre-score comes from weak scrape data. Enrich the 581 A and B leads first (Apify Instagram Profile Scraper), then re-score with the table above.

---

## 7. Outreach scripts

### Channels, in order

1. **Instagram DM** to scored leads: engage first, 30 a day rising slowly (India); 15 a day (US)
2. **Warm network:** "Do you know a shop owner who sells on Instagram?" [lesson03]
3. **In person, weekends:** Bengaluru boutiques; run the session on their phone at the counter [Proof Checklist: in person beats virtual]
4. **WhatsApp:** only after they reply on Instagram or share their number
5. **Cold email (US, week 2+):** separate sending domain, postal address and opt-out line in every email

### Step 0: engage before you DM

Follow, like 2 or 3 posts, one real comment about a product. DM a day or two later.

### DM 1: the win-back offer (English)

> Hi [Name], the [specific product] in your last post is lovely.
>
> Quick question: when a customer buys once and goes quiet, does anyone message them?
>
> I built an app that finds those customers and writes the message to bring each one back. I'm doing free 20-minute win-back sessions for 20 shops before Diwali: on your screen, with me, and you send the first messages while we're on the call. Want one?

### DM 1 (Hinglish)

> Hi [Name], aapka [product] bahut sundar hai.
>
> Ek sawaal: jo customer ek baar khareed ke wapas nahi aata, use koi message karta hai?
>
> Maine ek app banaya hai jo aise customers dhoondta hai aur har ek ke liye wapas bulane ka message likh deta hai. Diwali se pehle 20 shops ke saath free win-back session kar raha hoon: aapki screen pe, mere saath, 20 minute. Call pe hi aap pehle messages bhej denge. Karna hai?

### The festival opener (from mid-October)

> India: "Hi [Name], [compliment]. Quick question: the customers who bought from you last Diwali, has anyone messaged them this year?"
>
> US: "Hi [Name], [compliment]. Quick one: the people who bought from you last Black Friday, has anyone messaged them this year?"

If they reply, send the last paragraph of DM 1.

### When they say yes: the branch question

> "Amazing. Where do your orders get recorded? Shopify / Dukaan, Shiprocket, Razorpay, Meesho, an Excel sheet, or mostly WhatsApp? Any of those works. [Today 8 pm] or [tomorrow 7 pm]?"

Book inside 72 hours. Reply to every message within minutes during your evening window. [Lead Nurture: 78% of customers buy from whoever responds first]

### Rules for every DM

- The first line is about them. Your day job goes in the **second** line, never the first.
- No link in DM 1. Under 70 words. One question.
- Write in their language. Never paste the same message twice.
- Never claim a result you haven't seen.

### Follow-ups (only if no reply)

- **Day 3:** "Hi [Name], bumping this in case it got buried. Happy to do the session any evening this week."
- **Day 7 (value, no ask):** "Small tip that works: message a customer 60 to 90 days after their last order, about the exact thing they bought, not a generic discount. After about 4 to 5 months most have moved on."
- **Day 14 (last):** "Last message from me. If you ever want to find your quiet customers, just reply 'session'."

### Replies to pushback [Closing]

| They say | You say |
|---|---|
| "Mere paas data nahi hai" / "I don't track orders" | "Perfect, that's exactly what the session will show you. Bring your WhatsApp; we'll do it by hand and you'll see what you're missing." |
| "Price kitna hai?" / "How much?" | "The session is free, full stop. If you want the app to do it every week: 60 days free for founding shops, then ₹1,299 a month [US: $12.99], locked for life. No cut of your sales, ever." |
| "I already message my customers" | "Love that. The session will show who you missed. Most shops miss the ones who bought once." |
| "Time nahi hai" / "No time" | "That's exactly why. 20 minutes, and after that the list builds itself every week." [Closing, "Reason" close] |
| "Is my data safe?" | "You upload it yourself, into your own account. I never see the file. You can delete everything from the Account tab any time." |
| "Sochke batati hoon" / "Let me think" | "Of course. What's your main concern?" [Closing] |
| "Not interested" | "No problem at all, thank you for replying. All the best for the season." Mark do-not-contact |

---

## 8. Your resume: how to use it

> "By day I'm a supply chain analyst. I analyze inventory for a $4 billion portfolio and spot which customers are slipping away. I built One Tap Manager to do that for small shops."

Customer grouping and forecasting are literally on your CV. Use the line in your bio, the **second** line of a DM, at the start of each session, and in the "analyst" ad. Before naming Lam Research in public, check its outside-work and social media policy and your IP clause. Until then, say "a semiconductor company".

---

## 9. After the session: making the first win stick

### Branch A activation [Retention #1 and #2]

| When | What |
|---|---|
| On the call | 5 to 10 win-back messages sent (activation 1) |
| Day 1 to 3 | They send the rest of the list |
| Day 4 check-in | "How many replied? Any orders?" Capture screenshots, with permission |
| Day 7 | Weekly win-back switched on (activation 2: the habit) |
| Day 14 | Ask for a 60-second video: before, doubt, after [Marketing Machine, 6-point script] |
| Day 45 to 60 | Convert to paid before the free period ends. Show them the "brought back" numbers from `winback_proof` |

### Branch B activation: the launch sale fills the system

The website goes live in the setup session. Then a 5-day launch sale to their warmest audience brings first orders, and **every order becomes data for the system.** [Fast Cash, aimed at their followers]

| Day | Instagram | WhatsApp (their own phone) |
|---|---|---|
| -2 | Story: "Something big is coming" | Status teaser |
| 0 | Post + Story link sticker: "We're live! Launch offer for the first 50 orders" | Broadcast to past buyers, Status with link |
| 1 | Story: a product with its price and link | Answer every "price?" with the product link |
| 2 | Story: "[X] orders already" (real number only) | Status update |
| 4 | Story: "Last day of the launch offer" | Final broadcast |

From then on every "price?" gets the product link, so every order lands in the system. **Day 30 to 60: their first real win-back from their own data.** That is the "aha" from the session, now with their own customers, and the moment they decide to pay.

**Risk:** Branch B sellers reach the "aha" late. Keep them engaged until then with the Instagram planner and stock tracking, and a check-in on day 7, 21 and 45.

---

## 10. Market readiness

| | Branch A | Branch B |
|---|---|---|
| **India** | Ready. Test real Shiprocket, Razorpay, Meesho and Dukaan exports first | Ready. Test UPI checkout on GPay, PhonePe and Paytm |
| **US** | Ready to test. Shopify API pinned to `2024-07` (`backend/core/commerce.py:124`). Win-back **email** has no unsubscribe link yet (required by US law), so US sellers use the WhatsApp links or export the list to Shopify Email / Klaviyo | **On hold.** Card checkout off: `"charge_ready": {"razorpay": True, "stripe": False, "paypal": False}` (`backend/core/store_payments.py:196`). Checkout asks for a "PIN code" |

**October split (assumption):** about 70% India, 30% US. Diwali (around 8 November) and Black Friday (27 November) both make the win-back timely: "message last year's festive buyers."

**Shared fixes still open:** `Brand.md` still says "Free forever" and "Max ₹999"; nothing renews automatically; no per-account trial extension for 60-day founders.

---

## 11. Content and ads

### Organic (start now, 3 to 4 posts a week)

- **Series: "Win-back Wednesday."** Each week, one real session (with permission): how many quiet customers, how many messages sent, how many replied. Real numbers only, labelled with the shop's permission.
- **Build in public:** "20 shops, 20 win-back sessions before Diwali," with a daily Story counter.
- **India** in Hinglish; **US** from the existing US scripts, win-back posts first.
- Every Friday, check 3-second hold, shares and saves. Make more of the top one. [Hooks, 70-20-10]

### Hooks [Hooks, GOATed Ads]

| # | Hook | Type | Market |
|---|---|---|---|
| 1 | "Who bought from you last Diwali? Has anyone messaged them this year?" | Question | IN |
| 2 | "Your next 10 orders are sitting in your old chats." | Statement | IN |
| 3 | "Naye customers ke peeche bhaagne se pehle, purane customers ko yaad karo." | Command | IN |
| 4 | "The cheapest customer you'll ever get is one who already bought from you." | Statement | IN, US |
| 5 | "Stop posting more. Message the people who already bought." | Command | IN, US |
| 6 | "She sent 10 messages on our call. Watch what happened." (real session only) | Story | IN, US |
| 7 | "Could you name your 20 customers who stopped buying? Most shop owners can't." | Question | IN, US |
| 8 | "By day I analyze a $4 billion inventory. At night I find small shops' lost customers." | Story | IN, US |
| 9 | "Who bought from you last Black Friday? Have you messaged them this year?" | Question | US |
| 10 | "A website doesn't run your shop. This does." | Statement | IN, US |

### Four ad scripts (30 to 45 seconds) [GOATed Ads: hook, meat, CTA]

**Ad A: "The live win-back" (demonstration, once you have one)**
- Hook: hook 6.
- Meat: screen recording from a real session (with permission): the list of quiet customers, the written message, the seller tapping send, a customer's reply.
- CTA: "I'm doing free win-back sessions for 20 shops before Diwali. Comment WINBACK."

**Ad B: "Last Diwali's buyers" (problem-aware, India, 15 October to 5 November)**
- Hook: hook 1.
- Meat: "Most shops spend Diwali chasing new followers. Your easiest orders are from people who already bought from you. One Tap Manager finds them, writes a message for each one, and you send it from your own WhatsApp." Sample shop, tagged SAMPLE SHOP DATA.
- CTA: "Comment WINBACK and I'll do it with you, free."

**Ad C: "What's in your chats" (for DM sellers, education)**
- Hook: hook 7.
- Meat: "If your orders live in WhatsApp, no app can see who went quiet. Here's what a shop that records every order sees each morning..." (sample shop). "The fix isn't working harder. It's getting every order into one place."
- CTA: "Comment SESSION and I'll show you on your own shop."

**Ad D: "The analyst" (story, both markets)**
- Hook: hook 8.
- Meat: "Big brands have a team watching every customer and every stock level. A small shop has one person doing six jobs. One Tap Manager is that team: it finds who's slipping away, writes the message, tracks stock and plans the posts. You approve. No cut of your sales."
- CTA: India: "Comment WINBACK." US: "Comment AUDIT."

Set up the auto-DM for every comment keyword (WINBACK, SESSION, AUDIT) and test each from a second account before posting.

### What to boost, and when

**No spend until all four are true:** (1) 3 real sessions with replies or orders you can show; (2) the auto-DM works; (3) a post beat your average on 3-second hold and shares; (4) a seller can sign up and pay without you.

| Rule | India | US |
|---|---|---|
| What | Only top 10% organic posts [Marketing Machine] | Same |
| Where | Meta Ads Manager, objective Messages or Leads | Same |
| Audience first | Profile engagers, last 90 days [GOATed Ads: warmest first] | Same |
| Audience then | Women 22 to 45; online boutique, ethnic wear, jewellery, small business | 25 to 54; Shopify, boutique, small business owner |
| Daily budget (assumption) | ₹300 to ₹500 per ad, 3 to 5 days | $5 to $10 per ad, 3 to 5 days |
| First-month cap (assumption) | ₹10,000 | $150 |
| Kill rule | No session requests after ₹1,500: change the hook | No requests after $50: change the hook |

---

## 12. What to do, when

Today is Friday 2 October 2026.

### This weekend (3 and 4 October): get ready

- [ ] Test real exports: Shiprocket, Razorpay, Meesho, Dukaan, Shopify (section 3)
- [ ] Test "Send on WhatsApp" links on your phone, and an AI message for a real-looking customer
- [ ] Test UPI checkout on GPay, PhonePe and Paytm (Branch B)
- [ ] Per-account trial extension for 60-day founders (needs a small code change)
- [ ] Enrich the 168 Tier A leads; re-score; mark the likely branch
- [ ] Instagram bio with your analyst line; auto-DM for WINBACK
- [ ] Update `Brand.md` pricing
- [ ] Check your employer's outside-work policy

### Week 1 (5 to 11 October): first sessions

- [ ] India: 30 DMs a day, likely-A leads first, plus 10 warm-network messages a day
- [ ] US: 15 DMs a day to Shopify sellers
- [ ] Goal: 10 sessions, 6 of them Branch A with messages sent on the call
- [ ] Start the "20 sessions before Diwali" Story counter

### Week 2 (12 to 18 October): first proof

- [ ] DMs up to 40 a day; start Tier B
- [ ] Day-4 check-ins: count replies and orders; screenshots with permission
- [ ] First Branch B website setups and launch sales
- [ ] Fix the single biggest stall you saw in sessions. Only that one [lesson03]
- [ ] Goal: 15 sessions total, 3 sellers with a customer reply or order from win-back

### Weeks 3 and 4 (19 October to 1 November): the Diwali win-back

- [ ] Every Branch A seller: a "last Diwali's buyers" win-back in the week of 19 October
- [ ] Run Ad B organically; boost if the four conditions are met
- [ ] First "Win-back Wednesday" with a real seller
- [ ] Goal: 20 founding sellers, 3 video testimonials

### November

- [ ] India: support sellers through Diwali week; close the founding 20
- [ ] US: "last Black Friday's buyers" win-back for every US seller, week of 9 November
- [ ] Day 45 to 60: convert founders to paid. Lead with their own "brought back" numbers

### Day 30 decision (about 1 November)

| Result | Next step |
|---|---|
| 60%+ of Branch A sellers got a reply or order within 7 days, and half came back unprompted on day 2 or 3 | The entry works. Raise volume; test Analyst on call |
| Sessions stalled on file upload | Fix mapping for the formats that failed before booking more |
| Branch A sellers sent messages but got no replies | Look at the message, the timing, and which customers were picked. Ask sellers "what would make customers reply?" [lesson04, "what would it take?"] |
| Branch B sellers don't buy the website | Sharpen the realisation step, or put them on the list and focus on A |

---

## 13. Numbers to track every Friday

| Number | India, by week 4 (assumption) | US, by week 4 (assumption) |
|---|---|---|
| DMs sent | 700 | 300 |
| Reply rate | 15%+ | 10%+ |
| Sessions held | 30 | 10 |
| Share that were Branch A | 50%+ | 80%+ |
| Messages sent on the call (average) | 8 | 8 |
| Sellers with a customer reply within 24 hours | 60% of Branch A | 50% |
| Orders from win-back within 7 days | track it; no target yet | same |
| Weekly win-back switched on | 70% of Branch A | 70% |
| Branch B websites live, and first website order | 8, 5 | on hold |
| Founding sellers | 20 | 5 to 10 |
| Video testimonials | 3+ | 1+ |

---

## 14. Sources used

- `$100M Playbook: Fast Cash` (selling to the warmest audience: the win-back, the launch sale, festival campaigns)
- `$100M Playbook: Lifetime Value` (Crazy 8: recurring, follow-up reactivation, downsell only to the unqualified, price nudges)
- `$100M Playbook: Pricing` (play #9 ultra high ticket anchor, play #5 annual billing)
- `$100M Playbook: Retention` (activation points, onboarding, on-going value)
- `$100M Playbook: Closing` (power, the "Reason", "Main concern" and "1 to 10" closes, rules of closing)
- `$100M Playbook: Proof Checklist` (results before they buy, in person over virtual)
- `$100M Playbook: Marketing Machine` (lifecycle ads, 6-point testimonial script)
- `$100M Playbook: Hooks` and `GOATed Ads` (hook types, hooks x meat x CTA, warmest audiences first)
- `$100M Playbook: Lead Nurture` (speed to contact, calls inside 72 hours)
- Acquisition Scaling Course, lesson 03 (Improvise: the "reveal the problem" free offer) and lesson 04 (Monetize: proof over promise, "what would it take?")
