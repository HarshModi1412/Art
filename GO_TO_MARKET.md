# One Tap Manager: go-to-market and outreach plan

Written 2 October 2026 from `Product.md`, `Brand.md`, `LAUNCH_PLAN.md`, `docs/designs/us-pivot-five-seller-test.md`, the US Instagram scripts, the code, and Harsh's CV. Every tactic is tied to a Hormozi playbook or course lesson, named in brackets.

Funnel numbers marked **(assumption)** are planning guesses, not measured results. Replace them with your own numbers after week 1.

---

## 1. The short answer

You are at **Stage 0, Improvise**: a finished product, zero customers, zero proof. At this stage, Hormozi says the job is to **learn more than you earn**. Give the thing away to get feedback and proof, then charge. [lesson03, lesson04]

Your plan has the right idea (the five-seller test) but three problems:

1. **`LAUNCH_PLAN.md` is not a launch plan.** It is an engineering readiness review. It fixes the first ten minutes in the app. It says nothing about who you contact, what you say, or how you get proof. The real go-to-market lives in `us-pivot-five-seller-test.md`, and its target date (5 sellers connected by 3 October) is tomorrow.
2. **Your docs disagree with each other.** `Brand.md` and `REDDIT_PLAYBOOK.md` still say India-first, rupees, "Free forever" and "Max ₹999". `Product.md` and the code say US first, a 7-day trial, Pro $10 and Pro Max $12.99. Any copy written from `Brand.md` today would be wrong.
3. **A US seller can still hit Indian parts of the app.** Details in section 2.

The five moves that matter most, in order:

1. Fix the US blockers in section 2 that a seller would see on the first call (2 to 3 days).
2. Launch a **Founding Seller program**: 20 spots, a free "Shop Leak Audit", free setup, 60 days free in exchange for feedback and an honest review. [lesson03, lesson04, Fast Cash]
3. **Send 30 to 50 personal DMs a day** to US Instagram sellers who run a Shopify store, plus a warm-network track. Book 15-minute audit calls inside 72 hours. [lesson03, Lead Nurture]
4. **Capture proof from every seller** from day one (screenshots, short videos, numbers). [Marketing Machine, Proof Checklist]
5. **Do not pay for ads until you have proof.** Post organically now. Boost only posts that already beat your average, starting in week 3 or 4. [lesson04, GOATed Ads, Marketing Machine]

---

## 2. Is the launch plan good?

### What is right

- **The wedge.** "The morning list that does the work" (win-back and reorder) is narrow, concrete and easy to show. Good.
- **Testing with five sellers before building more.** This is exactly Stage 0. [lesson03: "our objective at this point is really to learn more than it is to earn"]
- **Measuring from records, not memory.** Qualifying action, unprompted return and payment are the right three signals.
- **The honesty rules in `Brand.md`.** No fake reviews, no fake counters, label every example. With zero customers, honesty is your proof. Keep them.

### What is wrong or missing

| # | Problem | Why it matters | Fix |
|---|---|---|---|
| 1 | No outreach plan, script, lead list or daily target anywhere | The test needs about 100 messages to book 5 calls (your own estimate). Nothing says who, where, or what to say | Sections 4 to 7 below |
| 2 | `Brand.md` says India-first, ₹, "Free forever", "Max ₹999"; `REDDIT_PLAYBOOK.md` pinned post says the same | Anyone writing copy from these docs will promise a free plan that no longer exists | Rewrite `Brand.md` sections 1, 2, 4 (India-first), 5 (pillar 2 and 3), 8 (plan names). Update the Reddit pinned post |
| 3 | Sample data is still Indian: `data/sample_transactions.csv` shows "Kundan Studs" and "Block Print Kurta", priced in rupees | A US seller's first look at the app is someone else's country | Make a US sample shop (dollar prices, US names) |
| 4 | Storefront checkout asks for a 6-digit "PIN code" (`Smart CafeX/storefront/store.js:1030`) | A US shopper expects "ZIP code" | Label by region; allow ZIP+4 |
| 5 | Shopify connector is pinned to API version `2024-07` (`backend/core/commerce.py:124`, `:140`) | That version is well past Shopify's 12-month support window. Shopify has also been moving custom-app creation out of the store admin. Your own precondition 1 says to verify this first | Run precondition 1 today. Until it passes, use the **Shopify orders CSV export** path, which needs no token |
| 6 | No unsubscribe handling in the win-back send path | US commercial email needs an opt-out link and a postal address (CAN-SPAM) | Until built, sellers export the list and send from Shopify Email or Klaviyo (your doc already says this) |
| 7 | Nothing renews automatically: a seller must pay again every 30 days (`Product.md` section 2) | Every month is a new buying decision. Retention suffers [Retention #6, Pricing play #8 "automatic continuity"] | Add auto-renew or an annual plan before seller 10 |
| 8 | Founders need more than 7 days free, but there is no per-account trial extension | You will need it for every founding seller | Add a small admin action to extend one account's trial |
| 9 | Post 12 in the US Instagram scripts pitches "websites for 20 Instagram sellers" | Your wedge is win-back and reorder for sellers who already have a Shopify store. Selling them a website is off-wedge | Change the mission to "20 sellers send their first win-back in 7 days" |
| 10 | Razorpay USD charging is not yet proven with a real US card | If the one seller who wants to pay cannot, the test fails on plumbing, not demand | One real USD test payment before the first call |

### A note on the US bet

Hormozi's fastest path at Stage 0 is **warm outreach**: people who already know you. [lesson03: "if you have no money, you should have no shame... knock, call, email, text, DM"] Your warm network is mostly in India. If your family and school network in Gujarat includes clothing, jewelry or fragrance sellers (Surat is India's textile hub), that is the fastest place to get your first 5 to 10 real users and testimonials, at ₹700.

This does not replace the US decision. Run it as a **parallel track** for speed of learning. India proof will persuade US sellers less (proof works best when the person in it looks like the buyer [lesson04]), but it gives you product feedback and conviction this week.

---

## 3. Your offer: the Founding Seller program

At Stage 0 you are not selling software. You are selling **a result plus your personal attention**. That attention is the "unscalable value" Hormozi says to lead with. [lesson03, Fast Cash: "Attention, Personalization, Speed"]

### Value equation for a busy US shop owner [lesson04, copywriting-frameworks.md]

| Lever | Today (status quo) | With the Founding Seller program |
|---|---|---|
| Dream outcome | "Make more from the shop I already have" | Past buyers come back; best sellers never run out |
| Perceived likelihood | "Another app I won't use" | You see **your own** numbers in a free audit before signing up |
| Time delay | Weeks to set up tools | Answers on screen in the first 15-minute call |
| Effort and sacrifice | Learn software, connect stuff, write emails | Harsh sets it up with you. The email is already written. You press send |

### The offer, in one sentence

> "I'll find the customers your shop has lost and the best sellers about to run out, for free, in 15 minutes. If it's useful, I'll set everything up for you and you use it free for 60 days. All I ask is honest feedback, and a short review if it earns one."

### The pieces

1. **Free Shop Leak Audit** (the "reveal the problem" free offer [lesson03]). On a 15-minute screen share, the seller uploads their own Shopify orders export (Shopify admin: Orders, Export, CSV) into a One Tap Manager account. You walk them through three numbers:
   - customers who bought once and have gone quiet for 60+ days, and what they spent before;
   - how many customers are repeat buyers;
   - their best sellers by revenue over 90 days.
   The seller uploads the file themselves. **Never ask for a CSV of their customers by DM or email.** It is their customers' personal data.
2. **Done-with-you setup**: you connect the store, set reorder levels for their top 5 products, and draft the first win-back email together.
3. **60 days free** instead of 7 (needs the trial extension in section 2, row 8).
4. **Founding price locked for life**: $10 a month (Pro) for as long as they stay.
5. **The exchange** [lesson03, the "4 Rs"]: honest feedback, a review or a 1-minute video if it helped, and an introduction to one other seller if they love it.
6. **The cap: 20 sellers.** This is real, not fake scarcity. You can personally onboard about 20 sellers around a full-time job. `Brand.md` bans fake scarcity, and this is not that.
7. **Promise you can keep**: "If the audit doesn't show you one thing worth fixing, you've lost 15 minutes and I'll say thanks for your time." No result claims you cannot back up. [Proof Checklist: "claim your proof"]

### Price ladder after the first 20 [lesson04]

Hormozi raises price every 5 sales once proof exists: free, then 80% off, 60%, 40%, 20%, full. Your price is already very low ($10), so ladder the **free period** instead:

| Sellers | What they get |
|---|---|
| 1 to 20 | Free audit, free setup, 60 days free, $10 locked for life |
| 21 to 40 | Free audit, 30 days free, then $10 |
| 41+ | Standard 7-day trial, then $10 or $12.99 |

**Later, after 10 testimonials**: test a premium tier, "Pro with an analyst", around $99 a month, capped at 10 sellers. It includes a 30-minute monthly numbers review with you. One in ten sellers on a 10x tier doubles revenue. [Fast Cash, "10x the 10%"] At $10 a month, paid ads will struggle to pay back, so a premium tier is what eventually funds ads.

---

## 4. Who to reach, and where

### Who (filters for your lead list)

- **Sells**: clothing, jewelry or fragrance. Physical products.
- **Store**: Shopify (check the link in bio: a `myshopify.com` address, or "Powered by Shopify" in the footer, or `/cart` on the site).
- **Size**: 1,000 to 50,000 Instagram followers. Posting in the last 7 days. Looks like 1 to 3 people run it.
- **Location**: US (bio, shipping page, or store currency in USD).
- **Not**: big brands with a team, dropshippers with no repeat customers, Etsy-only shops (no Shopify data to connect yet).

### Where to find them

- Instagram hashtags: #boutiqueowner #shopsmall #smallbusinessowner #handmadejewelry #jewelrybusiness #indieperfume #perfumeoil #womenownedbusiness. Open recent posts, not top posts.
- "Suggested for you" after you follow 10 good fits. Instagram will show you more like them.
- US boutique and Shopify-owner Facebook groups. Join, help, do not pitch in posts (read each group's rules).

### The lead sheet (your CRM)

One Google Sheet, one row per seller:

`Handle | Name | Store URL | Sells | Followers | Last post | Engaged on (date) | DM1 | DM2 | DM3 | Replied | Call booked | Audit done | Activated (first win-back sent) | Paid | Notes and exact words they used`

Build 20 to 30 rows a day. Write one specific thing about each seller in Notes (a product you liked, a recent post). You will use it in the first line of the DM.

### Channels, ranked for you right now [lesson03, "Core Four"]

| Rank | Channel | Why | Daily target |
|---|---|---|---|
| 1 | **Instagram DMs** (cold, engage first) | Your ICP lives here. You chose it. It suits short, human messages | 30 to 50, rising slowly |
| 2 | **Warm network** (WhatsApp, LinkedIn, Great Lakes alumni, family) | Fastest yes. Ask for sellers or for introductions to sellers | 10 a day until you run out |
| 3 | **Cold email to store contact addresses** | Higher volume, works with a short personal note | Start in week 2, 20 a day |
| 4 | **Organic Instagram content** | Makes your DMs credible when sellers check your profile | 3 posts a week |
| 5 | **Facebook groups, Reddit** | Help-first answers; slow but they compound | 2 helpful answers a day |
| 6 | **Paid ads** | Only after proof (section 8) | Week 3 or later |

**Instagram safety**: new accounts that send many identical DMs get limited. Start around 20 a day, add about 5 a day each week, and never paste the same message twice. Personal first lines solve both problems.

**Email rules**: send cold email from a separate domain (for example a `get`-prefixed version of your domain) so your main domain's reputation stays clean. Every email needs your postal address and a one-line way to opt out.

---

## 5. How to use your resume

Your CV is a real advantage. You do this job for a living at a scale no small seller has seen:

- "Owned analysis of a $4B+ global inventory portfolio" = reorder and stock health.
- "Inventory Optimization (EOQ/ROP)", "Customer Segmentation (RFM Analysis)", forecasting that cut error by up to 74% in a case study = exactly what the app does.
- "Business Intelligence tool for independent cafes" = you have built for small shops before.

**How to say it** (plain, no jargon, which `Brand.md` requires):

> "By day I'm a senior business analyst in semiconductor supply chain. I analyze inventory for a $4 billion portfolio. I built One Tap Manager to give small shops the same kind of analysis, without the team."

**Where to use it**

- **Instagram bio** (founder account or brand account): "Founder. Day job: inventory analyst for a $4B portfolio. I help small shops win back customers and never run out."
- **Second sentence of the DM**, never the first. The first sentence is always about them. [Hooks: "make them feel important"]
- **The start of the audit call**, in one line, then move on.
- **One founder-story reel** (ad script B in section 8).

**What to check first**

- Read Lam Research's policy on outside business work and on naming the company in public posts. To be safe, say "a semiconductor company" in public and only name Lam in 1:1 conversations if the policy allows.
- Check your employment contract's IP clause. Make sure One Tap Manager was built on your own time and equipment.

**Time zones work for you**: in October, 9 am to 1 pm US Eastern is 6:30 pm to 10:30 pm in Bengaluru (after 1 November, 7:30 pm to 11:30 pm). Book audit calls in your evening. Reply to DMs fast during that window. [Lead Nurture, "Speed": 78% of customers buy from whoever responds first]

---

## 6. Outreach scripts

### Step 0: engage before you DM

Follow the account. Like 2 or 3 recent posts. Leave one real comment about a product (not "love this!"). DM 24 to 48 hours later. Your name is then familiar when the DM arrives.

### DM 1 (pick one, personalize the first line every time)

**A. The audit offer (default)**

> Hi [Name], the [specific product] in your last post is gorgeous.
>
> Quick one: I'm an inventory analyst (day job: a $4B portfolio at a semiconductor company) and I built a free tool for small Shopify shops. It shows which customers bought once and went quiet, and which best sellers are about to run out.
>
> I'm doing free 15-minute audits for 20 US shops this month. Want me to run one on yours?

**B. The question opener (shorter, for busy-looking accounts)**

> Hi [Name], love the [product]. Honest question from a fellow small-business nerd: do you know how many of your customers bought once and never came back?

If they reply with anything, send A's middle and last paragraph.

**C. Black Friday angle (use from mid-October)**

> Hi [Name], [specific compliment]. Black Friday is [X] weeks out. The cheapest orders you'll get are from people who already bought from you. I'm doing free 15-minute audits for 20 US shops to find those customers and draft the email. Want one?

Rules for every DM [Hooks, Closing]:

- First line is about them. Never "Hi, I'm Harsh from...".
- One question. No link in DM 1 (links in cold DMs get filtered and look like spam).
- Under 60 words.
- No claims you cannot prove ("sellers see 40% more revenue" is banned by `Brand.md` and by honesty).

### Follow-ups (only if no reply)

- **Day 3**: "Hi [Name], bumping this in case it got buried. Happy to run the audit on a call or just send you the 3 numbers. Either works."
- **Day 7**: something useful with no ask. Example: "Saw you restocked the [product]. Tip from my day job: set your 'buy again' point at (average daily sales × supplier days) + a few days spare. Running out of a best seller costs you the customer, not just the sale."
- **Day 14 (last one)**: "Last message from me, I promise. If the timing's wrong, no worries at all. If you ever want those 3 numbers for your shop, just reply 'audit'."

Then stop. Mark the row closed.

### When they reply

| They say | You say |
|---|---|
| "Sure" / "How does it work?" | "Great. It's a 15-min screen share. You upload your Shopify orders export (I'll show you where) and we look at your numbers together. Are you free [today at X] or [tomorrow at Y]?" Offer slots inside 72 hours. [Lead Nurture: same-day and next-day calls show up far more] |
| "Is it free?" | "The audit is free, full stop. If you want to keep using the app, founding shops get 60 days free and $10/month after, locked for life. No cut of your sales, ever." |
| "I already use Klaviyo / Shopify Email" | "Perfect, keep it. This tells you *who* to send to and drafts the message. You can export the list straight into Klaviyo." |
| "No time" | "Totally get it, that's the exact reason I built it. It's 15 minutes, and after that it does the work each morning." [Closing, "Reason" close] |
| "Is my data safe?" | "Your store connection is read-only and encrypted, I never see your password, and you can delete your account and data from the Account tab any time." (True per `Product.md` section 7) |
| "Not interested" | "No worries, thanks for replying. Good luck with the [product] launch." Close the row. Be gracious. |

### Warm-network message (WhatsApp / LinkedIn)

> Hi [Name], hope you're well. I've built an app for small online shops (clothing, jewelry, fragrance) that finds lost customers and stops best sellers running out. I'm looking for 20 shop owners to try it free with my personal help. Do you run a shop, or know one or two people who do? An intro would mean a lot.

---

## 7. The 15-minute audit call

Hormozi's structure: understand what they want, put it next to their options, help them reach a real decision. [Closing, "Power"] Your research protocol also says to watch signup silently, so the first part is silent.

**0:00 Frame (30 seconds)**
> "Here's the plan: I'll ask a few quick questions, then you upload your orders file and we look at your numbers together. At the end you decide if it's useful. Fair?"

**0:30 Discovery (4 minutes)** Ask, then write down their exact words.
1. "Roughly how many orders a month, and where do they come from?"
2. "Who does what in the shop?"
3. "Last time a regular stopped buying, what did you do?"
4. "How do you decide when to reorder?"
5. "What apps do you pay for right now, and what does that add up to?"
6. "If this worked perfectly, what would it do for you?" [lesson04, "magic question"]

**4:30 Silent signup (up to 5 minutes)**
They sign up on their own device and upload the CSV while you watch and say nothing. Note every stall. If stuck for 2 minutes, help, and mark "onboarding stall" in your sheet. (This answers your doc's open question R2-18.)

**9:30 The gap (3 minutes)** Show their Today screen.
> "So 47 of your customers haven't ordered in 60+ days. Before they went quiet they spent [$X]. And nobody has messaged them. Want to draft the email right now?"

(Use their real numbers. Never invent.)

**12:30 The offer (1 minute)** Read section 3's one-sentence offer.

**13:30 Close**
- "On a scale of 1 to 10, how useful was that?" If under 10: "What would make it a 10?" [Closing, "1 to 10"]
- Anything that is not yes: "What's your main concern?" [Closing]
- Once they say yes: **stop selling.** [Closing rule 26] Go straight to activation.

**14:00 Activation, on the call**
Send (or export) the first win-back email together. This is your **activation point**: sellers who get value in the first session stay. [Retention #1 and #2] Book a 10-minute check-in for day 4 (your doc says message on day 4, never earlier).

**Before every call**, send this message so the disclosures are not spoken during the silent part (answers R2-18):

> "Looking forward to it. Two things before we talk: (1) you'll upload your own orders file, I never handle your customers' data; (2) if you ever approve a purchase order in the app, it emails your real supplier, so only approve ones you mean. You can delete your account and data from the Account tab any time."

---

## 8. Proof, content and ads

### Capture proof from seller number 1 [Marketing Machine, Proof Checklist]

Proof beats promise. [lesson04] Hormozi does not sell until he has 10+ testimonials. Build the machine now:

- **Ask permission once**: "Can I share your numbers (with or without your shop name) in my posts?"
- **Screenshot** every win: a reply from a customer who came back, an order from a win-back, a reorder that arrived on time.
- **Day 14 video**: ask for a 60-second phone video using the 6-point script: before (feeling), before (numbers), doubt, why they tried anyway, after (numbers), after (feeling). [Marketing Machine]
- **Folder**: `proof/` with subfolders `screenshots`, `videos`, `quotes`. Name files `seller-date-what.png`.
- Raw phone video beats polished video. [Proof Checklist: "Raw > Processed"]

### Organic content (start now, 3 posts a week)

You already have 12 US scripts. Run them in this order and change two things:

1. **First**: Post 1 ("You do 6 people's jobs") and Shop Doctor Ep 01. Both work before you have customers.
2. **Rewrite Post 12** to the wedge: "0 / 20: twenty shops send their first win-back email in 7 days." Then post daily Story updates of the real counter. Honest build-in-public is the strongest content you have with zero customers.
3. **Make "Shop Doctor" your weekly series** using real audits (with permission, numbers labeled as that shop's). This is a demonstration ad that films itself. [GOATed Ads, "Demonstration"]
4. Post at 7 pm Eastern (your own doc's rule).
5. Every Friday, list each post's 3-second hold, shares and saves. Make more of the top one. [Hooks, "70-20-10"]

### Hooks to test (write 50, start with these) [Hooks, GOATed Ads]

Spread across awareness levels so you reach more than the people already looking:

| # | Hook | Type | Awareness |
|---|---|---|---|
| 1 | "Shopify store owners: your next orders might already be in your customer list." | Label | Solution |
| 2 | "How many of your customers bought once and never came back? Most shop owners can't answer that." | Question | Problem |
| 3 | "By day I analyze a $4 billion inventory. Then I looked at a small boutique's numbers." | Story | Unaware |
| 4 | "Stop posting more. Message the people who already bought from you." | Command | Problem |
| 5 | "You're not bad at marketing. You're doing six people's jobs alone." | Statement | Unaware |
| 6 | "The cheapest customer you'll ever get is one who already bought from you." | Statement | Problem |
| 7 | "Black Friday is [X] weeks away. Here's who you should email first." | Statement | Problem |
| 8 | "If you sell jewelry on Instagram, watch this before your next reorder." | Conditional | Solution |
| 9 | "Your best seller runs out in 9 days. Would you know?" | Question | Unaware |
| 10 | "3 numbers every small shop should check every Monday." | List | Solution |
| 11 | "I'm auditing 20 US shops for free. Here's what I found in the first one." | Statement | Solution |
| 12 | "Wrong answers only: what do you do when a regular stops buying?" | Question | Unaware |

Hook 9 must use a real shop's real number, labeled as that shop's. Hook 11 only once you have done audits.

### Three ad scripts (30 to 45 seconds) [GOATed Ads: hook, meat, CTA]

**Ad A: "The Shop Leak Audit" (education plus demonstration)**
- **Hook** (founder to camera): "How many of your customers bought once and never came back?"
- **Meat** (screen recording of the US sample shop, tagged SAMPLE SHOP DATA): "Most shop owners never check. Here's a sample shop. 90 days of orders. Upload the file and in two minutes you see this: 47 customers who went quiet, what they used to spend, and the email to bring them back, already written. You press send. That's it."
- **CTA**: "I'm doing free audits for 20 US shops. Comment AUDIT and I'll send you the link."

**Ad B: "The analyst" (story)**
- **Hook**: "By day I analyze inventory for a $4 billion portfolio."
- **Meat**: "Big companies have a whole team watching stock and customers. A small shop has one person doing six jobs. So I built One Tap Manager. Every morning it tells you the three things worth doing, and it does most of them: the win-back email, the reorder, the week of posts. No cut of your sales. $10 a month."
- **CTA**: "Try it free for 7 days. Link in bio." (After the founding 20: switch to this standard offer.)

**Ad C: "Before Black Friday" (problem-aware, run 26 Oct to 25 Nov)**
- **Hook**: "Black Friday is 4 weeks away and most shops will spend money chasing strangers."
- **Meat**: "Your cheapest sales are from people who already bought from you. Here's how to find them: export your orders, look for anyone who bought 60 to 180 days ago, and send them something specific to what they bought. Or let One Tap Manager make the list and write the email for you."
- **CTA**: "Comment BFCM and I'll send you the free checklist."

The free checklist for Ad C is a 1-page PDF of the manual method. It is useful even if they never sign up, which makes it a fair lead magnet.

**Later (after proof): Ad D, testimonial.** A real seller's raw video using the 6-point script. This will likely beat everything above. [Marketing Machine: 40 of Hormozi's top 50 ads did not have his face in them]

### CTA rules [GOATed Ads, "Clear > Clever"]

Say what to do, how, when, and what they get. Show the next screen. Set up the Instagram auto-DM for every comment keyword (AUDIT, BFCM, STORE) and test it from a second account before posting. An unanswered keyword costs trust.

### Where to post

- **Instagram**: Reels, carousels, Stories (Story every day during the 0 to 20 challenge).
- **Facebook**: cross-post Reels. Boutique owners skew older on Facebook than Instagram.
- **Facebook groups and Reddit**: helpful answers only, with "Disclosure: I built One Tap Manager" when relevant (`REDDIT_PLAYBOOK.md` rules).
- **Not yet**: TikTok, YouTube, LinkedIn ads. One platform done well beats four done badly.

### What to boost, and when

**Do not spend on ads until all four are true**: (1) a US seller can sign up and pay; (2) you have at least 3 real audits to show; (3) the auto-DM works; (4) at least one post beat your average on 3-second hold and shares.

Then:

| Rule | Detail |
|---|---|
| What | Only posts in your top 10% organically. Good organic performance predicts good ad performance [Marketing Machine] |
| Where | Meta Ads Manager (not the in-app Boost button, which optimizes for likes). Objective: Messages or Leads |
| Audience, first | Warm first [GOATed Ads: "ads start profitably with the warmest audience"]: people who engaged with your profile in 90 days, and site visitors |
| Audience, second | US, 25 to 54, interests: Shopify, boutique, small business owner, Etsy, jewelry making |
| Budget | $5 to $10 a day per ad, 3 to 5 days, max about $150 in the first month (assumption: a sensible cap for a test, not a target) |
| Kill rule | No audit requests after $50 spent on an ad: stop it, change the hook, not the meat [Hooks: 80% of the effort is the hook] |
| Scale rule | An ad that books audits for under what one paying seller is worth to you: keep it, and make 10 new hooks for the same meat [GOATed Ads, "50 hooks × 3 meats"] |
| Free money | Several ad platforms give new advertisers starter credits; claim them [lesson04] |

---

## 9. What to do, when

Today is Friday 2 October 2026.

### This weekend (2 to 4 October): unblock

- [ ] Run precondition 1 (Shopify token path) on a development store. If it fails, the **CSV upload path** is your connection for the test.
- [ ] Make the US sample shop (dollars, US names) and record your app screens from it.
- [ ] ZIP code label on the storefront checkout for US shops.
- [ ] One real USD Razorpay payment, end to end.
- [ ] Per-account trial extension (60 days for founders).
- [ ] Deploy to Render and run the 5-minute checklist in `LAUNCH_PLAN.md` section 9.
- [ ] Update `Brand.md` and the Reddit pinned post to US pricing (7-day trial, $10, $12.99, no free plan).
- [ ] Instagram: bio with your analyst line, link to `onetapmanager.com`, auto-DM for AUDIT.
- [ ] Build the lead sheet with the first 50 rows.
- [ ] Check your employer's outside-work and social media policy.
- [ ] Move the five-seller target date from 3 October to 17 October. The date was set before any outreach existed.

### Week 1 (5 to 11 October): first conversations

- [ ] 20 to 30 personal DMs a day (engage first), plus 10 warm-network messages a day.
- [ ] Book every "yes" inside 72 hours, in your 6:30 to 10:30 pm window.
- [ ] Goal: 5 audits done, 3 founding sellers activated (first win-back sent).
- [ ] Post Post 1, Shop Doctor Ep 01, and the rewritten Post 12. Story every day.
- [ ] Write down every seller's exact words. They become your ad copy.

### Week 2 (12 to 18 October): learn and fix

- [ ] DMs up to 40 a day. Start cold email (20 a day).
- [ ] Day-4 check-ins with week-1 sellers. Day-7 scoring per your decision table.
- [ ] Fix the single biggest stall you saw on calls. Only that one. [lesson03: "find the thing preventing you from doing more of what works, solve it, repeat"]
- [ ] Goal: 10 audits, 6 founding sellers activated.

### Weeks 3 and 4 (19 October to 1 November): proof, then a little paid

- [ ] Ask the happiest sellers for the 60-second video.
- [ ] First Shop Doctor with a real shop.
- [ ] If the four conditions in section 8 are true, start boosting your best organic post at $5 to $10 a day.
- [ ] Launch Ad C (Black Friday) on 26 October.
- [ ] Goal: 15 founding sellers, 3 testimonials.

### November: Black Friday and Cyber Monday (27 and 30 November 2026)

- [ ] Help every founding seller run a pre-Black Friday win-back to past buyers. This is a Fast Cash play for *their* shop: a limited-time offer to their warmest audience. [Fast Cash] Their results become your best proof.
- [ ] Close out the founding 20. Move to the 21 to 40 tier.
- [ ] Decide on Approach B (rewrite the US home page around the wedge) using your own pass criteria.

### Day 30 decision (about 1 November)

Use the thresholds from your pivot doc, judged on sellers with no confound:

- **Pass** (at least 60% act by day 7, half return unprompted, at least 1 pays at full price): keep the wedge, raise volume, start the premium tier test.
- **Fail with confounds** (stalls, thin data, payment failures): fix the confound, recruit more, re-test.
- **Fail clean** (they reached Today, saw cards, did nothing): the wedge is wrong. Go back to your call notes and ask "what would it take?" [lesson04]

---

## 10. Numbers to track every Friday

| Number | Target by week 4 (assumption) |
|---|---|
| DMs sent | 800 total |
| Reply rate | 10% or more |
| Audit calls booked | 40 total (about 5% of DMs, your pivot doc's estimate) |
| Show rate | 70% or more (calls inside 72 hours) |
| Activated (first win-back sent) | 50% of audits |
| Founding sellers | 15 to 20 |
| Return on day 2 or 3 unprompted | half of activated |
| Paid at full price | at least 1 |
| Testimonials (video or written with numbers) | 3 or more |

---

## 11. Sources used

- `$100M Playbook: Fast Cash` (unscalable value, 10x the 10%, limited spots, warm-audience promotions)
- `$100M Playbook: Marketing Machine` (proof capture, 6-point testimonial script, "work for free, get testimonials")
- `$100M Playbook: Hooks` (call-out plus value, 70-20-10, hook types)
- `$100M Playbook: GOATed Ads` (awareness levels, hooks × meat × CTA, five ad formats, CTA rules)
- `$100M Playbook: Closing` (power and blame, all-purpose closes, rules of closing)
- `$100M Playbook: Lead Nurture` (speed to contact, appointments inside 72 hours)
- `$100M Playbook: Proof Checklist` (claim your proof, raw over processed)
- `$100M Playbook: Retention` (activation points, onboarding, annual plans)
- `$100M Playbook: Pricing` (automatic continuity, annual billing)
- Acquisition Scaling Course, lesson 03 (Stage 0, Improvise) and lesson 04 (Stage 1, Monetize)
- `frameworks/copywriting-frameworks.md` (value equation, persona call-outs)
