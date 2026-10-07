# Pain, FOMO and Offer Map (Sellers With a Website)

**Three steps, in order:**
1. The pains, as sellers say them (from the sourced list, `OTM-ICP-Real-Pain-Points-Sourced.pdf`)
2. Each pain turned into FOMO, with a fact behind it
3. Each pain connected to what we actually offer, including where we have **no** answer

---

## 0. Two corrections to my earlier documents

* **"70% of customers never return" is wrong for us.** I called it an ecommerce stat. I traced it to its source and it is about **physical retail visitors** (Zenreach data via a retail blog, no year). Do not use it.
* **"21% of customers, 44% of revenue" had the wrong source.** I credited Sender. It is not in that article. It comes from **Gorgias**, based on its 12,000+ merchants (undated, probably 2023).

---

## 1. The pains, clearly (10)

Ordered by how strongly sellers voiced them. Evidence IDs (S1, S4 and so on) point to the source list in the sourced pain-point PDF.

| # | Pain, in plain words | Who said it |
|---|---|---|
| **P1** | "Customers buy once and never come back" | 3 threads read, 2023 to 2026 (S1, S2, S3) |
| **P2** | "I get traffic and nobody buys" | S4, S5 and many more (new stores) |
| **P3** | "A new store doesn't feel trustworthy to first-time buyers" | S6 (clothing), jewelry threads |
| **P4** | "I can't keep my content consistent without a designer" | S7 (fragrance brand) |
| **P5** | "Email marketing tools are too complicated or too expensive" | S8 |
| **P6** | "Apps cost too much for what they do" | S9, S10 |
| **P7** | "I don't know what I actually keep after costs" | S11, S12 |
| **P8** | "Returns and exchanges are confusing and eat my margin" | S13 and clothing threads |
| **P9** | "My stock numbers can't be trusted" | S14 and many more |
| **P10** | "Customer messages never stop and I'm doing support alone" | S15, S16 |
| **P11** | "I already sell, but my sales are stuck. I can't get to the next level" | Founder observation, 7 Oct 2026: sellers who have made sales but cannot scale. Their posts look generic or home-grown, and big-city buyers do not buy. **Not yet sourced from seller threads.** Backed by our own data test (section 2) |

**Left out on purpose:** cash-on-delivery and fake orders (India, not US), Etsy sales slumps (not our core), "wearing every hat" (only a vendor survey), "ads cost more" (numbers in sources disagree).

---

## 2. Turning each pain into FOMO

**The FOMO formula:** *what the seller does today* + *what the data says they are missing* + *who gets it instead (or what it costs them)*.
**US ad safety:** every line says "studies show" or "on average". We never promise a result for their store. The proof is their own free week.

### The facts, with how far I traced each one

| Fact | Source | Traced? |
|---|---|---|
| Repeat customers are about 21% of a store's customers but about 44% of its revenue and 46% of its orders | [Gorgias](https://www.gorgias.com/blog/repeat-customer-rate), 12,000+ merchants | **Opened the page.** Company data, undated, merchants on its own platform |
| You have a 20 to 40% chance of selling to a customer who went quiet, vs 5 to 20% for a cold prospect | Paul Farris, *Marketing Metrics*, quoted by [Propello](https://propellocloud.com/blog/win-back-campaigns/) | **Opened the page.** Book is the source; Propello only quotes it |
| 3 to 5 posts a week gives about 12% more reach per post and more than double the follower growth of 1 to 2 posts a week | [Buffer](https://buffer.com/resources/how-often-to-post-on-instagram/), 2.1M posts from 102,000+ accounts, Aug 2025 | **Opened the page.** Primary study. Shows a link, not cause |
| A product with 5 reviews is 270% more likely to be bought than one with none | [Spiegel Research Center](https://spiegel.medill.northwestern.edu/how-online-reviews-influence-sales/), 2017 | **Opened the page.** Older, general retail |
| Repeat purchase rate near 18.8% across 156K DTC customers; apparel brands 15 to 17% | [BS&Co](https://bsandco.us/blog-post/repeat-purchase-rate-benchmarks), Feb 2026 | **Opened the page.** An agency's own client data. Apparel exchanges may be counted as new orders |
| Online apparel returns run about 24%; size and fit is the top cause | NRF and Appriss Retail data via [3PL Insider](https://3plinsider.com/research/cost-of-ecommerce-returns) and similar | **Not opened.** Secondary |
| Stockouts cut annual revenue about 2 to 5% | [OpenSend](https://www.opensend.com/post/inventory-stock-out-rate-statistics) | **Not opened.** Secondary |
| Small sellers with a brand are 4 to 6 times more likely to have a product break out than sellers with no brand (full table under P11 below) | [Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023), McAuley Lab, UC San Diego. 1.1M products, data to Sept 2023 | **Our own analysis of the raw data, 7 Oct 2026.** Primary. Amazon US. Shows a link, not cause |

### P11 proof: branded products are 4 to 6 times more likely to break out

| | 50+ ratings: brand vs no brand | 100+ ratings: brand vs no brand |
|---|---|---|
| Fashion | 5.8% vs 1.4% → **4.0×** | 2.8% vs 0.5% → **5.7×** |
| Beauty / fragrance | 17.9% vs 4.7% → **3.8×** | 9.6% vs 2.0% → **4.7×** |
| Handmade | 11.6% vs 6.9% → **1.7×** | 6.1% vs 2.8% → **2.2×** |

**How it was measured:**
* **Data:** three categories of Amazon Reviews 2023 that match our sellers: Amazon Fashion (826,108 products), All Beauty (112,590) and Handmade (164,817). Every product in it has at least one rating, so these are sellers who already sell, which is exactly the P11 seller.
* **Brand vs no brand:** "no brand" = the store is blank, "Generic", "Unbranded", "Unknown" or similar. "Brand" = a named store with **20 or fewer products** in the category, so big companies are left out. Small brand vs small no-brand seller.
* **Sales measure:** the number of customer ratings, the usual public stand-in for units sold. Handmade counts only products still on sale. Products that are no longer listed flip the Handmade result, because many small handmade shops stopped selling.
* **Hypothesis test:** one-sided Welch t-test on log(1 + ratings). H₀: branded sellers do no better than unbranded. H₁: branded sellers sell more. α = 0.05.

| Category | t | p (one-sided) | Effect size (Cohen's d) | Sales vs no brand | Decision |
|---|---|---|---|---|---|
| Fashion | 75.27 | < 10⁻³⁰⁰ | 0.36 | 1.49× | Reject H₀ |
| Beauty / fragrance | 75.75 | < 10⁻³⁰⁰ | 0.62 | 2.33× | Reject H₀ |
| Handmade (products still on sale) | 19.92 | 6×10⁻⁸⁸ | — | 1.29× | Reject H₀ |

* **Same price band:** small brands beat no brand in all 15 tests (3 categories × 5 price bands), by 1.15× to 3.4×. Price does not explain the gap.
* **Other stats from the same data:** half (50%) of unbranded fashion products never pass 2 ratings, against 37% of branded ones. In beauty it is 37% against 17%. Branded beauty products are 4.4× more likely to be in the category's top 10%.

**What we can and cannot say:**
* **Say:** "Small sellers with a brand sell 1.5 to 2.3 times more than sellers without one, at the same price." Also say where it comes from: "in Amazon data covering 1.1 million products".
* **Do not say:** "Creating a brand grows your sales." This is a link, not proof of cause. More serious sellers may be the ones who build brands.
* **It tests "has a brand", not "has a clear brand statement and consistent styling".** The data has no measure of styling. One pointer: small brands use more product photos (beauty 5.0 vs 4.0) and are 3 to 5 times more likely to include a video.
* **To prove cause:** randomly give half of our selling sellers the brand setup and compare 8 to 12 week sales growth with a t-test. That needs about 96 sellers per group if the effect is as big as in fashion (d = 0.36), or about 310 per group if it is small (d = 0.2).

### The FOMO lines

| # | FOMO type | The FOMO (what they are losing) | Draft line for the ad | Fact quality |
|---|---|---|---|---|
| **P1** Customers don't come back | **Money left behind** and **who gets it instead** | Repeat buyers are a fifth of customers but over 40% of revenue, and a quiet customer is far likelier to buy than a stranger. If you never follow up, you keep paying to find strangers | "Repeat customers: 21% of buyers, 44% of revenue. Are you chasing the other 79%?" / "A customer who went quiet is 20 to 40% likely to buy again. A stranger, 5 to 20%. So who are you paying Meta to find?" | **Strong.** Two opened sources |
| **P2** Traffic, no sales | **Wasted spend** | You paid or worked to get the visit. Most visitors leave and you never hear from them | "You got the click. Then 97 of 100 left and you never knew who they were." | **Weak.** The 2 to 3% conversion figure came from a forum reply, not a study. Do not use until sourced |
| **P3** Trust | **Lost first sale** | Products with reviews sell far more than products without | "Five reviews makes a product 270% more likely to sell. How many does your best seller have?" | **Medium.** Real study, 2017 |
| **P4** Content consistency | **Reach you never earn** | Accounts posting 3 to 5 times a week get more reach per post and grow faster than 1 to 2 a week | "Post 3 to 5 times a week and you get more reach per post and over double the follower growth. How many did you post this week?" | **Strong.** Primary study, 2.1M posts |
| **P5** Email too hard/costly | **Wasted tool and time** | Many pay for or sign up to an email tool, then never build the flows | "You're paying for an email tool you never set up. That's $0 return, every month." | **Weak as a fact, strong as a feeling** (S8). No stat |
| **P6** App costs | **Paying a cut of your business** | Fees stack up on top of the plan, sometimes charged per click or per sale | "Apps that charge a monthly fee and a cut of your sales. We charge $10 a month and no cut." | **Qualitative** (S9, S10). Check our claim: Pro is $10, no cut of sales |
| **P7** Profit blind spot | **Decisions made on a guess** | Dashboard shows revenue, not what you keep. You can back the wrong product | "Your best seller might be your worst earner. Do you know?" | **Weak.** No stat; and we do **not** show net profit (see section 3) |
| **P8** Returns | **Margin leak** | Clothing returns are common and costly, mostly from size and fit | "About 1 in 4 online clothing orders comes back. Do you know what yours cost you?" | **Medium.** Secondary source, not opened |
| **P9** Stock trust | **Lost sales and lost buyers** | A stockout loses the sale and sometimes the customer | "Sold out on your best seller. How many buyers went to someone else?" | **Weak to medium.** Not opened |
| **P10** Support alone | **Lost evenings and lost sales** | Customers write at midnight, and replies are slow | "Your customers message at midnight. Who answers?" | **Qualitative** (S15, S16) |
| **P11** Sales stuck, no brand | **The next level goes to someone else** | Their products sell, but they look like everyone else's. Branded small sellers are 4 to 6 times more likely to have a product break out, and unbranded products stall far more often | "In 1.1 million products, unbranded sellers were 4× less likely to get a product past 50 sales." / "Same price, same category. The branded seller outsold the unbranded one in every price band." | **Strong.** Our own test on primary data. Amazon US, and a link, not cause |

---

## 3. Connecting each pain to what we actually offer

Status comes from `Product.md` and `GO_TO_MARKET.md`. **Strong** = a direct, shipping answer. **Partial** = helps, but not the whole pain. **Gap** = we do not solve it. **Verify** = I could not confirm it from the docs.

| # | Pain | Our answer | What exactly ships | Fit |
|---|---|---|---|---|
| **P1** | Customers don't come back | **Win-back + Today list + customer groups** | Finds customers slipping away, ranked by what they spent; writes a message with their favourite item and what goes with it; counts who came back; prepares a weekly batch. Works on Shopify/Amazon connect, file upload, or email intake. **The seller taps send for each one. No automatic sending** | **Strong** |
| **P2** | Traffic, no sales | Indirect only | We do not fix conversion on their Shopify site. We can turn visitors who bought once into repeat buyers | **Partial** |
| **P3** | Trust | Nothing for their Shopify store | Review Analytics reads a reviews file they upload. It does **not** collect or display reviews. The "designer-level" themes only apply to a One Tap site | **Gap** |
| **P4** | Content consistency | **Social Media Manager + Product Studio** | A week of posts planned, captioned and scheduled, published to Instagram; learns their look from their own photos; AI photos and clips on Pro Max | **Strong** |
| **P5** | Email too hard/costly | **Written win-back messages** | The message is written and the list is ready. No flow builder, and email send depends on setup (WhatsApp sending is off; links open WhatsApp with the message typed) | **Partial** |
| **P6** | App costs | **Price and no-cut model** | Pro $10 a month, Pro Max $12.99, no cut of sales, custom domain included | **Strong on the claim**. But it only replaces apps if it truly does their job, so be specific about which |
| **P7** | Profit blind spot | **Sales Analytics + Sub-Category Analysis** | Shows what sold, what it earned and which categories bring the money. **It does not subtract product cost, shipping, fees or ad spend**, so we cannot claim "your real profit" | **Partial** |
| **P8** | Returns | Nothing for returns | Cancellation analysis exists but is in rupees and is not returns/exchanges | **Gap** |
| **P9** | Stock trust | **Inventory + reorder levels + purchase orders** | Stock falls on its own as **our** orders come in; buy-again alerts; supplier PDF. **Verify** whether stock decrements from **Shopify or Amazon orders**. The docs only say website (One Tap site) orders trigger the stock check | **Verify** |
| **P10** | Support alone | Nothing | No customer inbox or support bot. The AI chatbot is for the seller's own analysis | **Gap** |
| **P11** | Sales stuck, no brand | **A brand, made from what they already sell** | **Position Strategy** sets where the brand sits (value or premium, product-led or look-led) and a plan to stand for something. **Product Studio** keeps their look, voice and reference photos and makes posts in that look. **Social Media Manager** keeps the posts on-brand every week. **Website Builder** gives a designer-level site (8 themes, 20 fonts) and writes all the site copy from their brief. **Nothing for packaging** | **Strong** for statement, posts and site. **Gap** for packaging |

### What this tells us about which pains to build ads on

| Tier | Pains | Why |
|---|---|---|
| **Lead with** | **P1** (they don't come back), **P4** (content) | Strong evidence, strong fact, strong offer match. P1 is the clear winner: two opened sources, direct product fit |
| **Support with** | **P6** (app cost), **P5** (email), **P7** (partial) | Real pain, honest partial answer |
| **Do not advertise yet** | **P3, P8, P10** | We have no answer. An ad would promise something we don't ship |
| **Check first** | **P9** | Need to confirm Shopify/Amazon stock sync |
| **Don't use** | **P2** | No fact, only indirect fit |
| **Strong candidate, decide** | **P11** (sales stuck, no brand) | The strongest fact we have (our own test on 1.1M products) and a real offer for the brand, posts and site. Two limits: Amazon US data, and we ship nothing for packaging |

---

## 4. The idea your example pointed at, written out

> **Pain (P1):** my customers don't come back
> **FOMO:** repeat customers are about 44% of revenue for the average store, and a quiet customer is 20 to 40% likely to buy again vs 5 to 20% for a stranger. You're leaving that on the table and paying for strangers instead
> **Offer:** One Tap Manager finds the customers slipping away from your own order data, writes the message, and counts who comes back
> **Proof (theirs, not ours):** a free 7-day trial, no card. They find out their own number on their own data

That is the whole chain for the first ad. P4 is the second. Both have a verified fact and a real feature.

### The P11 chain: from stuck sales to the end goal

> **Pain (P11):** I already sell, but my sales are stuck. My posts look generic or home-grown, and big-city buyers scroll past
> **Solution: a brand.** A clear brand statement, then styling that follows it, then every post, product photo and page in that style. One Tap Manager sets the position (Position Strategy), keeps the look and voice (Product Studio), posts in that look every week (Social Media Manager), and puts it on a designer-level site (Website Builder)
> **Proof:** in 1.1 million Amazon products, small sellers with a brand were **4 to 6 times more likely** to have a product break out (table under P11 in section 2). Fashion: 5.8% vs 1.4% past 50 ratings. Beauty and fragrance: 17.9% vs 4.7%. The same held in every price band
> **End goal:** the goals in `Pain_Journey.md` section 1:
> * **G1 Money:** more of their products reach the level where sales add up. A branded product is 4 to 6 times more likely to get there
> * **G2 A customer base:** a brand is something buyers remember, follow and come back to. "Generic" gives them nothing to come back to, which also feeds P1
> * **G5 Pride:** a shop that looks like a real brand, not a side project
> * **G7 To be taken seriously:** the big-city buyer who scrolled past a home-grown post stops for a brand
>
> **Their own proof:** the free 7-day trial. Day 1 they write their brand statement and pick a look. By day 7 they see a week of on-brand posts and a site in the same style. Sales growth takes longer than 7 days, so the trial proves the look, not the sales

**Guardrails for P11:** never "a brand will grow your sales" (that is an earnings claim, and the data shows a link, not cause). Always name the source as Amazon data. Do not mention packaging in ads until we ship something for it.

---

## 5. Decisions for our discussion

1. **Lead with P1?** Is "the money you left behind" the story you want, with the Farris and Gorgias facts?
2. **P4 as the second ad:** are you comfortable with the Buffer post-frequency fact, given it shows a link and not cause?
3. **Gaps (P3, P8, P10):** do any of these belong on the roadmap? Or do we stay silent on them in ads?
4. **P9 stock:** can you confirm whether stock updates from Shopify and Amazon orders? I could not tell from the docs.
5. **P7 wording:** are we OK saying "what sells and what earns" and **not** "profit"?
6. **P2 and P3 facts:** do you want me to hunt for a solid, sourced conversion-rate fact and a review fact for jewelry and clothing, in case we use them later?
7. **P11 brand:** lead with it, or keep it third after P1 and P4? And do we build anything for packaging (for example, label and box designs in the brand's look from Product Studio), or stay silent on packaging?
8. **P11 proof on our own sellers:** run the randomised brand test (about 96 sellers per group) so the claim comes from our customers and not only from Amazon data?
