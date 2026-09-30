# SEO audit: onetapmanager.com for the US market

26 September 2026, after the US pivot (US home at `/`, India home at `/in`, new pricing).
Crawled on the local build with a US visitor's headers. No SEO tool is connected, so
difficulty and demand are judgement calls from the live search results, not measured
volumes. Connect Ahrefs or Semrush (both are listed as available connectors) to replace
them with real numbers.

## Summary

The technical base is strong: one H1 on every page, self-canonicals, a sitemap with honest
`lastmod`, FAQ and SoftwareApplication schema with offers in USD, a working hreflang set
(en-US, en-IN, hi-IN, x-default), and robots.txt that keeps the app private and lets every
search and AI crawler read the public pages. **The weakness is content, not plumbing.** The US
home page is written for the US, but 22 of the 24 guide and feature pages are still written
for India. Their titles say "in India", and their text talks about GST, WhatsApp and
"jewellery", while they are served to Googlebot in dollars. Google US will read them as
Indian pages.

Top 3 priorities:
1. Rewrite the 7 `/features/*` pages for the US and drop "India" from their titles, keeping India copy under `/in/...`.
2. Build a US comparison and "alternatives" cluster around the Shopify apps sellers actually search for: low stock alerts, win-back email and AI product photos.
3. Earn the first backlinks and reviews. The domain is new, and every US head term is owned by Shopify, the app store and review sites.

**Verdict: strong foundation, but the content needs work before US rankings are realistic.**

## Keyword opportunities (US)

| Keyword | Est. difficulty | Opportunity | Current ranking | Intent | Recommended content |
|---|---|---|---|---|---|
| low stock alert app for shopify | Moderate | High | none | Commercial | `/features/stock-reorder` rewritten for US |
| reorder point formula / calculator | Moderate | High | none (India page exists) | Informational | Keep the calculator, US copy |
| shopify inventory forecasting small store | Hard | Medium | none | Commercial | Feature page section and a comparison |
| purchase order app for small business | Moderate | High | none | Commercial | Stock feature page |
| win back lapsed customers email | Moderate | High | none | Informational | `/guides/win-back-email-examples` |
| win-back email examples | Moderate | High | none | Informational | Guide with 5 to 7 examples |
| customers who stopped buying shopify | Easy | High | none | Informational | Guide section and win-back feature |
| AI product photos from my own photo | Moderate | High | none | Commercial | `/features/ai-product-photos` US |
| AI jewelry product photography | Moderate | High | none | Commercial | Section, US spelling |
| photoroom alternative for small brands | Moderate | Medium | none | Commercial | `/compare/photoroom` |
| instagram content planner small business | Hard | Medium | none | Commercial | `/features/instagram-planner` US |
| what to post on instagram for a clothing brand | Easy | Medium | none | Informational | Guide |
| shopify apps too expensive | Easy | High | none | Commercial | `/compare/shopify-apps` US rewrite |
| all in one shopify app analytics inventory email | Moderate | High | none | Commercial | Home page and compare page |
| analyze customer reviews for complaints | Easy | Medium | none | Commercial | `/features/review-analysis` |
| sales up profit down small business | Easy | Medium | none (page exists) | Informational | Keep, remove ₹ examples |
| how to analyze sales data in excel | Hard | Low | none (page exists) | Informational | Retitle "Analyze" |
| boutique inventory management software | Moderate | Medium | none | Commercial | `/for/clothing-sellers` US |
| jewelry business inventory software | Moderate | Medium | none | Commercial | `/for/jewelry-sellers` |
| small fragrance brand software | Easy | Low | none | Commercial | `/for/perfume-sellers` US |
| one tap manager | Easy | High (brand) | not yet indexed as US | Navigational | Home, about |

## On-page issues

| Page | Issue | Severity | Recommended fix |
|---|---|---|---|
| All 7 `/features/*` | Titles say "India", copy uses GST, WhatsApp, Flipkart and "jewellery", served to US visitors | Critical (for US) | US copy at the same URLs, India copy at `/in/features/*`, with hreflang pairs |
| `/for/*` (4 pages) | Titles and copy are India-only (for example "Imitation Jewellery Businesses in India", "Attar") | High | US versions; move India versions under `/in/for/*` |
| `/compare/shopify-apps` | "Shopify Alternative in India", ₹ stack table, Razorpay and COD | High | US rewrite naming Stockbot, Klaviyo and Photoroom with prices checked on the day |
| `/compare/billing-apps` | Vyapar, myBillBook: India-only | Medium | Keep for India only, and leave it out of US internal links (already done on `/`) |
| `/guides/gst-rate-*` | India-only guide in the US crawl set | Low | Move under `/in/guides/` or leave; mark India in the title (it already is) |
| 17 of 24 guide pages | `<title>` is 70 to 84 characters including " \| One Tap Manager" | Medium | Keep the keyword part under 45 characters, or drop the suffix on long titles |
| `/features/online-store` | Promises Razorpay and COD; US sellers cannot take card payments on the store yet | High (trust) | Mark it as India-only until a US payment option exists |
| `/about`, `/guides` | Titles 80 characters | Low | Shorten |
| `/`, `/in`, `/about` | Meta descriptions 200+ characters | Medium | **Fixed today** (154, 153, 128) |
| `/pricing` | Title repeated the brand, 86 characters | Medium | **Fixed today** (74, keyword first) |
| Guide pages | `html lang` was en-IN on US-served pages | Medium | **Fixed today** (plain `en`, `en-US` in schema, `og:locale` en_US) |

## Content gaps

| Topic | Why it matters | Format | Priority | Effort |
|---|---|---|---|---|
| Win-back email examples | Heavily searched and informational, the entry point to the win-back feature. Competitors (Seguno, PushOwl, AiTrillion) all have one | Guide with real examples | High | Half day |
| Low stock alerts for Shopify, compared | Shopify's own roundup and the app store rank; a small site wins on "for a one-person shop" angle | Comparison page | High | Half day |
| AI product photos from your own photo | Tools cost $10 to $15 a month alone (Photoroom $12.99, Pixelcut $9.99, Pixora $9.90); Pro Max at $12.99 includes it plus the rest | Feature page and comparison | High | Half day |
| The Shopify app stack, priced | "What a small store pays for apps each month": link-worthy, and it sells the $10 plan | Data page | Medium | Multi-day (prices checked at source) |
| Black Friday and holiday stock planning | US seasonal demand; the India page covers Diwali instead | Guide | Medium | Half day |
| Sales tax honesty note | US sellers will ask; saying clearly that it does not file sales tax prevents bad signups | FAQ entry | Low | 1 hour |

## Technical checklist

| Check | Status | Details |
|---|---|---|
| Title tags present and unique | Pass | 26 pages, all unique |
| Title length | Warning | 17 of 26 over 70 characters with the brand suffix |
| Meta descriptions | Pass | Fixed the three long ones today |
| One H1 per page | Pass | Every page |
| Canonicals | Pass | Every page self-canonical; `/in` canonical to `/in` |
| hreflang | Pass | `/`, `/in` and `/hi` carry the same four; tests enforce it |
| Currency-varying pages | Warning | Guide pages vary by region at one URL, with `Vary` sent. Googlebot crawls from the US, so the indexed version is USD, which is intended. The India copy on those pages still sits at US URLs (see above) |
| Sitemap | Pass | Includes `/in`; `lastmod` from source file dates |
| robots.txt | Pass | App and API disallowed; AI crawlers allowed |
| Structured data | Pass | Organization, WebSite, SoftwareApplication with USD offers, FAQPage, BreadcrumbList, Article |
| Images and alt text | Pass | No images without alt; OG image 1200x630 PNG |
| Mobile | Pass | No horizontal scroll at 375px; tap targets 40px+ (tested) |
| HTTPS | Pass (production) | Check once `PUBLIC_BASE_URL` is live on the US domain |
| Page weight | Warning | The home page is 74 KB of HTML with inline CSS. Fine for LCP; do not add hero images without sizing |
| Reviews or ratings markup | Pass (correctly absent) | No customers yet; do not add until real |

## Competitor comparison (estimated)

| Dimension | One Tap Manager | Stockbot / Merchbees (Shopify apps) | Photoroom |
|---|---|---|---|
| Keywords ranked (US) | Near zero, new domain | Strong inside the Shopify App Store | Very strong |
| Content depth | 24 pages, 400 to 900 words each, mostly India | App listing pages | Large blog and templates |
| Backlinks | None yet | App store authority | Very high |
| SERP features | FAQ schema ready | App store rich results | Image packs, knowledge panel |
| Price story | $10 does analytics, reorder, win-back and Instagram together | Free to about $10 each, one job each | $12.99 for photos only |
| Winner | Price and breadth | Distribution | Authority |

## Action plan

**Quick wins (this week)**
- Done today: US home, `/in`, hreflang, USD schema, meta descriptions, the pricing title, and `html lang` on guide pages.
- Shorten the 17 long titles, keyword first (1 hour, medium impact).
- Mark `/features/online-store` and `/compare/billing-apps` as India, and keep them out of US internal links (1 hour, high trust impact).
- Verify `onetapmanager.com` in Google Search Console, submit the sitemap, and set no country target (hreflang does it) (30 minutes, high impact).
- Submit to Bing Webmaster Tools. `BING_SITE_VERIFICATION` and IndexNow are already built in; set the env vars on Render (30 minutes).

**Strategic (this quarter)**
- US rewrite of the 7 feature pages and 4 "for" pages. India copy moves to `/in/...` with hreflang pairs (multi-day, high impact). Dependency: decide one URL set per market.
- US comparison cluster: `/compare/shopify-apps` US, `/compare/photoroom`, "low stock alert apps for Shopify" (multi-day, high).
- Guides: win-back email examples, the reorder point formula US version, holiday stock planning (half day each, high).
- Listing on the Shopify App Store and in directories (G2, Capterra, Product Hunt launch) for links and first reviews (multi-day, high; dependency is having real users).

Sources: [Shopify inventory apps roundup](https://www.shopify.com/blog/inventory-management-app), [Shopify App Store: inventory optimization](https://apps.shopify.com/categories/orders-and-shipping-inventory-inventory-optimization/all), [Stockbot](https://apps.shopify.com/inventory-alerts), [Merchbees](https://apps.shopify.com/merchbees-low-stock-alert), [Shopify email apps for win-back](https://www.shopifyemailapps.com/use-cases/winback), [Seguno win-back examples](https://www.seguno.com/blog/7-winback-email-examples), [PushOwl win-back](https://www.pushowl.com/blog/winback-campaigns-example), [Nightjar AI product photo tools](https://nightjar.so/blog/ai-product-photography-best-tools), [Pixora comparison](https://www.usepixora.com/resource/best-ai-product-photography-tools).
