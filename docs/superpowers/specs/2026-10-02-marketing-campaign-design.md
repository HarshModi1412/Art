# Marketing Campaign — design (2026-10-02)

Turns the old Win Back module into a campaign pipeline good enough to onboard
trial sellers with: pick a reason, set one offer, every customer gets a code
that actually works at checkout, messages go out on WhatsApp and email with one
campaign image, and it repeats itself every second Monday.

## What was broken

1. Favourite product read badly. Templates were café copy ("the *Chikankari
   Kurta, White* machine keeps asking where you went") and variant suffixes
   (", White", ", 6 ml") were pasted mid-sentence. SKU-looking values were used
   raw.
2. Nobody was reachable. The mapper never captured phone or email, so every
   send reported "skipped — no email or phone".
3. Discounts were random (10/15/20% by spend tier) and codes were never stored,
   so a shopper typing one at checkout got nothing.
4. WhatsApp sending was a stub; the default message referenced `{coupon}` while
   rows carried `coupon_code` ("here's  off").

## Decisions (seller-facing)

| Topic | Decision |
|---|---|
| Contact data | Mapping gains two optional fields: **Customer phone** and **Customer email**. Auto-detected; may share a column with Customer ID. Website orders carry them automatically. |
| Offer | Set once at the top: **flat amount or %**, optional minimum order. Same for everyone. |
| Codes | **Unique per customer, single use, 14-day expiry**, stored server-side, redeemed on the seller's One Tap Manager website checkout. Message links carry `?code=` so it applies itself. A redeemed code is counted as a proven win-back. |
| Campaign reason | **Win back quiet customers** → At-Risk segment. **Festival offer** → Champions + Loyal + top-20% spenders + At-Risk (deduped, highest value first). Festival defaults to the next one on the calendar within 30 days; seller can type their own occasion. |
| Message writing | One AI call per campaign (seller's ChatGPT plan → OpenAI → Cloudflare → … via `aiprovider.generate`), writing a template with `{name} {product} {offer} {code} {expiry} {link} {brand}`. No customer data goes to the AI. Hand-written retail templates are the fallback. WhatsApp and email get separate copy. |
| Image | One per campaign via OpenAI images (seller key first, else app key). **Pro Max**: existing monthly picture allowance. **Every other plan incl. trial: 2 campaign images per calendar month**, regardless of campaign count. Over the limit or OpenAI exhausted/unavailable → ask the seller to upload one. |
| WhatsApp | Accounts → WhatsApp card. Step 1: the number they send from (tap-to-send works immediately: each message opens WhatsApp pre-typed). Step 2 (optional, auto-send): connect **Meta WhatsApp Cloud API** (Phone Number ID, Business Account ID, access token). We verify it, submit the campaign template for Meta approval automatically, and once approved, approving a campaign sends on WhatsApp by itself. |
| Schedule | **Every second Monday 10:00** (seller's timezone): if a festival starts within the next 21 days and has not had a campaign yet → festival campaign, else win-back. It lands in the Approval panel with the seller's saved offer; approving sends it. Never sends without a yes. |
| Safety | Cooldown: win-back 45 days, festival 14 days. Sample-data addresses (`example.com`, `.test`) are never actually mailed. |

## Components

- `mapper.py` — `CONTACT_ROLES` (`customer_phone`, `customer_email`) assigned after the greedy pass; allowed to reuse a column.
- `analytics.py` — profiles carry `phone`, `email`, `product_display`; `campaign_audience(txns, reason)`.
- `products.clean_product_name` — strip variant suffix; resolve SKU → catalogue name.
- `discounts.py` (new) — issue / check / redeem / stats.
- `storefront.price_cart(..., coupon)` + `place_order(..., coupon)`; `/api/shop/{h}/cart|pay|order` accept `coupon`; `/api/shop/{h}/coupon` checks one.
- `campaign_writer.py` (new) — AI brief → templates, fallback copy, fill per row.
- `campaign_image.py` (new) — allowance + OpenAI generation + upload.
- `whatsapp.py` (new) — per-seller config (token in `secrets_store`), verify, template submit/status, send.
- `campaigns.py` — `build()` the full draft; `send()` uses per-row codes, WhatsApp API when approved, tap-to-send otherwise.
- `winback_auto.py` — biweekly, chooses festival vs win-back, stores the offer.
- UI: Marketing Campaign composer, Accounts → WhatsApp, mapping labels, storefront code field.

## Testing

`scripts/test_marketing_campaign.py`: mapper contact roles, name cleaning,
code issue/redeem/expiry/single-use, cart pricing with a code, audience
selection, writer fallback + placeholder validation, image allowance, biweekly
trigger, WhatsApp template payload (HTTP mocked). Existing suites
`test_winback_auto.py`, `test_marketing_module.py` must stay green.
