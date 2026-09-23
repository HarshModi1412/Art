# Getting AI assistants to recommend One Tap Manager

The goal: when a seller asks ChatGPT, Gemini, Perplexity, Claude or Google's AI Overviews "what software should a small Indian clothing seller use?", One Tap Manager is in the answer and linked.

Started 24 September 2026. Tick items off as they ship. "Code" items are built into the site. "You" items need your accounts and cannot be done from the code.

---

## What actually moves AI answers (and what does not)

Read this before adding anything. It stops us spending time on things that do nothing.

| Claim you will hear | What the evidence says | What we do |
|---|---|---|
| "Put Reddit tags in your meta tags and the AI will pick you" | No such tag exists. AI tools cite Reddit because of what people **write in threads**, not because of any tag on your site. Reddit is cited in roughly 40% of AI answers across the big assistants, and Perplexity leans on it the most | Build a real, disclosed Reddit presence (section 3). Link the official profile from our structured data (`sameAs`), which is the legitimate version of a "Reddit tag" |
| "Add llms.txt and AI will read your site" | Google says it ignores llms.txt, and a 94,000-URL study found no citation uplift. AI coding and browsing agents do read it | Added, because it costs nothing, but it is not the plan |
| "Block AI bots to protect content" | Blocking the search bots (OAI-SearchBot, Claude-SearchBot, PerplexityBot) removes you from AI answers entirely | Explicitly allow them all, and the training bots too, because an unknown brand wants to be known by the models |
| "AI checks facts" | It picks sources by structure and clarity: a direct answer near the top, headings phrased as questions, tables, dates | Every new page opens with a one-paragraph answer, uses question headings, and shows its date |
| "Old pages are fine" | Pages updated in the last three months are cited almost twice as often | Pages show "Last updated", schema carries `dateModified`, and the sitemap's `lastmod` follows the file |
| "Google is all that matters" | ChatGPT search leans on Bing's index | Bing Webmaster Tools plus IndexNow (section 2) |

---

## 1. On the site (code, built in this change)

- [x] **robots.txt names every AI crawler** and allows it, while keeping the private app (`/smart`, `/api/`) closed to all of them: OAI-SearchBot, ChatGPT-User, GPTBot, Claude-SearchBot, Claude-User, ClaudeBot, PerplexityBot, Perplexity-User, Google-Extended, Applebot-Extended, Bingbot
- [x] **Pages that answer the questions people ask AI**, each with a direct answer first, question headings, a facts table, an FAQ with matching FAQ schema, and a visible date:
  - `/about`: "What is One Tap Manager?" The entity page an AI quotes when it describes us, including how we differ from the other "One Tap" apps
  - `/for/clothing-sellers`, `/for/jewellery-sellers`, `/for/perfume-sellers`: "What software should a small Indian clothing (or jewellery, or perfume) seller use?"
  - `/compare/shopify-apps`: "Is there one app instead of paying for five Shopify apps?", with the arithmetic from `pricing.py`
  - `/guides`: the hub that links them all
- [x] **One source of truth for prices**: every page reads plans and credit packs from `backend/core/pricing.py`, so an AI never quotes a price we stopped charging
- [x] **Structured data**: Organization with `alternateName`, `logo` and `sameAs`; WebPage, BreadcrumbList and FAQPage on every guide, with `datePublished` and `dateModified`
- [x] **`sameAs` from one setting**: `BRAND_PROFILES` (comma-separated URLs: Reddit, Instagram, LinkedIn, YouTube, X) feeds the landing page, every guide and llms.txt. Empty means nothing is claimed
- [x] **`/llms.txt`**: a plain summary for AI agents, with the facts, prices and links
- [x] **Sitemap** lists every guide, with `lastmod` from the file that holds the words
- [x] **Landing page footer links to the guides**, so crawlers find them from the home page
- [x] **Bing verification**: `/BingSiteAuth.xml` answers when `BING_SITE_VERIFICATION` is set
- [x] **IndexNow**: `/indexnow.txt` serves `INDEXNOW_KEY`, and `scripts/indexnow_ping.py` tells Bing (and so ChatGPT search), Yandex and Seznam that pages changed
- [x] **Tests**: `scripts/test_ai_visibility.py`

## 2. Search engines (you, about 20 minutes, once)

- [ ] Deploy in Render (Manual Deploy)
- [ ] **Bing Webmaster Tools** at bing.com/webmasters: sign in, choose "Import from Google Search Console" (fastest), or add the site and copy the XML file code into `BING_SITE_VERIFICATION` in Render. Submit `https://onetapmanager.com/sitemap.xml`
- [ ] **IndexNow**: in Render, set `INDEXNOW_KEY` to any 32 letters and digits (for example, from bing.com/indexnow/getstarted). Redeploy, then run:
  ```bash
  python scripts/indexnow_ping.py https://onetapmanager.com
  ```
  Run it again after every deploy that changes a public page
- [ ] **Google Search Console**: URL Inspection, then Request indexing, for `/about`, `/guides` and each `/for/...` page

## 3. Reddit (you, ongoing, the biggest lever)

AI answers quote Reddit threads. There is no shortcut and no tag for this: it is real people saying real things. Full scripts are in `REDDIT_PLAYBOOK.md`.

- [ ] Create **u/OneTapManager** (or your own account with "Founder, One Tap Manager" in the profile)
- [ ] Create **r/OneTapManager** with a pinned post: what it is, the link, and how to ask for help
- [ ] Add both URLs to `BRAND_PROFILES` in Render (this is the "Reddit tag" that counts)
- [ ] Every week, answer 3 to 5 real questions from Indian sellers in relevant subreddits. **Always say you built it.** Help first; link only when it truly answers the question
- [ ] Never post fake reviews, use other accounts to praise it, or buy upvotes. Reddit bans it, AI tools learn to distrust the domain, and `Brand.md` section 9 forbids it

## 4. Being named elsewhere (you, ongoing)

AI tools recommend brands that many independent sources describe the same way.

- [ ] Profiles with the exact name "One Tap Manager" and a link to the site: Instagram, LinkedIn company page, YouTube, X, Facebook. Add each to `BRAND_PROFILES`
- [ ] Google Business Profile, with the name "One Tap Manager"
- [ ] Listings: Product Hunt launch, Crunchbase, G2, Capterra, and Indian startup directories. Use the same one-line description everywhere: "One Tap Manager is shop management software for small Indian clothing, jewellery and perfume sellers."
- [ ] A Wikidata entry, once there are independent articles to cite (ChatGPT leans heavily on Wikipedia and Wikidata; do not create one before then or it will be deleted)
- [ ] Write for others: a guest post or a YouTube walkthrough in Hindi for Indian sellers

## 5. Measure it (you, 10 minutes a month)

Ask each assistant these questions in a fresh chat, and note whether One Tap Manager appears and which source it cites:

1. What software should a small Indian clothing seller use to manage stock and customers?
2. Best app for an Indian jewellery seller on Instagram to track sales
3. Is there one app instead of several Shopify apps for a small Indian D2C brand?
4. What is One Tap Manager?
5. How do I win back customers who stopped buying from my online shop in India?

Keep the answers in a simple sheet (date, assistant, mentioned yes or no, cited URL). Search Console and Bing Webmaster Tools also show visits from AI referrers (chatgpt.com, perplexity.ai, gemini.google.com).

---

Sources for the table above: Profound's AI citation study, ZipTie's Reddit citation analysis, ALLMO's llms.txt study of 94,000 cited URLs, Google's June 2026 note on llms.txt, and Cloudflare's September 2026 robots.txt report.
