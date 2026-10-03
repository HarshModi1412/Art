# Marketing activities for a small social seller, and what One Tap Manager covers

Written 3 October 2026 from a scan of `backend/core/`. The campaign code is still changing in an uncommitted parallel task (`261002-wg2`), marked **in progress** below.

**Status key:**
- **Yes:** the app does it today.
- **Partly:** some of it works, with a gap.
- **No:** nothing in the app.

A status reflects what the code contains, not how well it works for a seller.

## 1. Brand foundations

| # | Activity | Status | Where / what's missing |
|---|---|---|---|
| 1 | Positioning: who it's for, value or premium | Yes | Position Strategy (`positioning.py`, `position_strategy.py`). Needs a reviews file |
| 2 | Brand look: logo, colours, fonts | Partly | Website themes and fonts; Product Studio learns the seller's photo style. No logo or brand kit |
| 3 | Instagram profile set-up: bio, highlights, link in bio, pinned posts | No | Only "Copy for Instagram bio" after the website goes live |
| 4 | Watching competitors | No | Only light mentions in content planning |

## 2. Content (getting attention)

| # | Activity | Status | Where / what's missing |
|---|---|---|---|
| 5 | Product photos | Yes | Product Studio, AI product photos (Pro Max) |
| 6 | Short videos and reels | Yes | AI clips (Pro Max), reel publishing |
| 7 | Weekly post plan, captions, hashtags | Yes | Social Media Manager (`social.py`, `autoplan.py`) |
| 8 | Festival and occasion calendar | Yes | Festival library (`playbook.py`) |
| 9 | Auto-publishing to Instagram | Yes | Single photos and reels (`publisher.py`) |
| 10 | Instagram Stories | No | Publisher posts feed photos and reels only |
| 11 | Carousels | No | Not published |
| 12 | Reposting customer photos and videos (UGC) | No | UGC exists only as a video style, with no collection |
| 13 | Reviews and testimonials turned into posts | Partly | Review analysis exists; the thank-you campaign asks for a review (in progress); nothing turns them into posts |

## 3. Reach (getting found)

| # | Activity | Status | Where / what's missing |
|---|---|---|---|
| 14 | Keywords and hashtags in captions | Partly | Hashtags in captions; no keyword research |
| 15 | Website found on Google | Partly | The seller's site has SEO title and description fields |
| 16 | Google Business Profile / Maps | No | |
| 17 | Marketplace listings (Meesho, Amazon) | No | Connectors only read sales |
| 18 | WhatsApp Status posts | No | |
| 19 | Influencer and creator collabs, Instagram Collab posts | No | |
| 20 | Giveaways and contests | No | |
| 21 | Paid ads: create, boost, budget | No | |
| 22 | Ad results | Partly | Connections are real; figures are demo data until platform review |
| 23 | Cross-posting to Facebook, YouTube Shorts, Pinterest | No | |

## 4. Turning interest into orders

| # | Activity | Status | Where / what's missing |
|---|---|---|---|
| 24 | Own website with cart, UPI, cash on delivery | Yes | Website Builder, storefront |
| 25 | Answering "price?" comments and DMs | No | The app can't read Instagram comments or DMs |
| 26 | Sharing product links | Partly | Share on WhatsApp, copy for bio; no per-product link kit for posts and replies |
| 27 | Abandoned-cart reminders | No | |
| 28 | "Notify me when back in stock" waitlist | No | The restock campaign is for repeat buyers, not shoppers waiting on a sold-out item |
| 29 | Discount codes | Yes | `discounts.py` |
| 30 | Bundles and combos | Partly | The app finds "bought together" pairs; no bundle price on the site |
| 31 | Reviews on product pages | No | The storefront shows no reviews |
| 32 | Trust signals: COD, policies, owner details | Yes | Legal pages, owner details in setup |

## 5. Keeping customers and repeat orders

| # | Activity | Status | Where / what's missing |
|---|---|---|---|
| 33 | Customer list and contact book | Yes | Customer groups; `contacts.py` (numbers added by hand) |
| 34 | Customer groups: best, slipping, new | Yes | `analytics.py` |
| 35 | Thank-you and review request | Yes (in progress) | `thank_you` campaign |
| 36 | Second-order nudge, "goes well with", refill reminder, VIP early access | Yes (in progress) | `second_order`, `cross_sell`, `restock`, `vip` |
| 37 | Win-back | Yes | `winback_auto.py`, `campaign_engine.py` |
| 38 | Festival campaigns to past buyers | Yes | `festival` campaign |
| 39 | Opt-in record ("Reply YES for new drops") | No | Nothing stores who agreed |
| 40 | Referral: "refer a friend" | No | |
| 41 | Loyalty points or rewards | No | |
| 42 | Birthday and anniversary messages | No | |
| 43 | Complaint insights | Yes | Complaint Analysis (needs a reviews file) |

## 6. Measuring what works

| # | Activity | Status | Where / what's missing |
|---|---|---|---|
| 44 | Instagram insights: reach, saves, per post | Yes | `iginsights.py` |
| 45 | Campaign results, with a comparison group | Yes | Holdout in `campaign_engine.py`, `winback_proof.py` |
| 46 | Sales by product and category, with forecast | Yes | Sales Analytics, Sub-Category Analysis |
| 47 | Which Instagram post brought which order | Partly | Campaign links are tracked; post links are not |

## Count

| | Yes | Partly | No |
|---|---:|---:|---:|
| Brand foundations | 1 | 1 | 2 |
| Content | 5 | 1 | 3 |
| Reach | 0 | 3 | 7 |
| Turning interest into orders | 3 | 2 | 4 |
| Keeping customers | 7 | 0 | 4 |
| Measuring | 3 | 1 | 0 |
| **Total (47)** | **19** | **8** | **20** |
