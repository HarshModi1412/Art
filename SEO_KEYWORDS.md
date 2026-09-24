# Keyword to page map

Which search each public page is written to rank for. The pages live in
`backend/core/geo.py` (the `seo_title` is the `<title>`; the H1 is written for the
person who lands). Volumes are estimated tiers from the September 2026 keyword
research, not measured figures. Check them in Google Keyword Planner (India) or
Semrush before spending money on ads, and replace the tiers with real numbers
once Search Console has a month of data.

## Pages and their keywords

| Page | Main searches it targets |
|---|---|
| `/` | shop management app, shop management software, business management app for small business india, one tap manager |
| `/hi` | dukan ka hisab kitab app, stock register app, GST bill kaise banaye, purane customer wapas kaise laye (Hindi and Hinglish) |
| `/pricing` | one tap manager pricing, free business management app, flat price ecommerce software no transaction fee |
| `/about` | one tap manager, what is one tap manager, one tap manager review |
| `/features/sales-analytics` | sales analytics software for small business, upload sales csv get insights, analyse sales from excel free, daily sales summary on whatsapp |
| `/features/win-back` | customer win-back app, whatsapp win-back campaign, find customers who stopped buying, customer retention software india |
| `/features/stock-reorder` | low stock alert app, app that tells me what to restock, purchase order software for small business |
| `/features/gst-invoices` | GST invoice for online seller, gst invoice and stock tracking for small shop, GST export file for CA |
| `/features/ai-product-photos` | AI product photography india, AI jewellery product photography, AI perfume product photos, how to take jewellery photos with phone |
| `/features/instagram-planner` | instagram post scheduler india, weekly instagram content plan, instagram content ideas for clothing / jewellery / perfume brand |
| `/features/review-analysis` | analyse customer reviews, review analysis tool, sizing complaints fix |
| `/features/online-store` | no commission online store india, free online store for indian sellers, online store for instagram sellers |
| `/for/clothing-sellers` | clothing shop management software, boutique management software india, size-wise stock tracking for clothes |
| `/for/jewellery-sellers` | imitation / artificial jewellery business software, inventory app for jewellery business |
| `/for/perfume-sellers` | perfume shop software, attar business inventory software |
| `/for/instagram-sellers` | instagram seller management app |
| `/compare/shopify-apps` | shopify alternative india, free shopify alternative india, shopify apps too expensive india, replace multiple shopify apps with one |
| `/compare/odoo` | odoo alternative for small business, odoo too complicated |
| `/compare/billing-apps` | billing app vs shop manager, vyapar alternative, mybillbook alternative |
| `/guides/win-back-old-customers` | how to get old customers back, whatsapp message to bring back old customers |
| `/guides/when-to-reorder-stock` | reorder point calculator, how to calculate reorder point, when to reorder stock, safety stock |
| `/guides/sales-up-profit-down` | why are my sales up but profit down |
| `/guides/gst-rate-clothes-jewellery-perfume` | GST rate on clothes, GST rate on jewellery, GST rate on perfume |
| `/guides/analyse-sales-excel` | how to analyse sales data in excel |

## Left out on purpose

- **Head terms** ("GST billing software", "billing software", "inventory management
  software", "jewellery software"). Vyapar, myBillBook, Zoho, Tally and the review
  sites own them. Go after them once the site has reviews and links.
- **"best ..." pages.** Brand.md section 9: no claim we cannot back. Revisit once
  there are real customers and reviews.
- **Café and "Smart Cafex" pages.** Not the target seller, and the name is used by
  unrelated brands.
- **Bengali, Telugu and Marathi pages.** The app writes in English, Hindi, Tamil and
  Kannada only (`core/i18n.py`). The home page used to show example output in the
  other three; it no longer does. Add a Tamil or Kannada page next if Hindi works.
- **City pages** (Surat, Jaipur, Kannauj). Only worth it with real local sellers to
  write about; otherwise they are thin doorway pages Google penalises.
- **RFM, EOQ.** Brand.md keeps this jargon off public pages, so "RFM segmentation"
  is not targeted.
- **Named comparisons with Vyapar, myBillBook or Zoho** beyond `/compare/billing-apps`.
  Each needs facts about the other product checked at its source first.

## Next pages worth writing

- `/guides/shopify-store-cost-india`, once Shopify's current India prices are checked
  on shopify.com/in/pricing
- `/guides/start-clothing-business-online-india` (and jewellery, perfume): big
  top-of-funnel searches
- `/guides/reduce-returns-size-issues`
- A Tamil or Kannada home page, then hreflang it like `/hi`
