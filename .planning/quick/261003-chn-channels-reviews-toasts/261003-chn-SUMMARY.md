---
quick_id: 261003-chn
slug: channels-reviews-toasts
status: complete
date: 2026-10-03
commit: 85b9f63, e8c94b2 (local, not pushed)
---

# Summary: sales channels, website reviews, rectangular pop-ups; Shiprocket brief

## What changed

- `85b9f63` sales channels + pop-ups:
  - Every source owns its slice of the sales data (uploads, website,
    Shopify, Amazon, WooCommerce, Wix, POS). Fixed: a platform pull used to
    replace the whole dataset.
  - Sales and Sub-Category Analytics: channel chips to filter, "Sales by
    channel" donut + monthly stacked bars; nothing drawn with one channel.
  - Pop-ups: ios.css toast (999px pill), app toast, work strip and storefront
    toast are 12-14px rounded rectangles with padding; text wraps.
- `e8c94b2` reviews:
  - Verified-buyer reviews on the storefront product page (one per customer
    per product, editable); seller can hide.
  - Review data gained sources (site / woocommerce / wix / upload) with the
    same slice rules; columns normalised so every source shares Review/
    Rating/Date.
  - Orders pull also pulls WooCommerce and Wix reviews. Shopify and Amazon
    have no reviews API (Shopify reviews live in apps like Judge.me; SP-API
    does not expose reviews): stated on screen.
  - Review Analytics shows where reviews came from and a "Reviews on your
    website" card with Hide/Show.

## Evidence

- test_sales_channels 19, test_store_reviews 22, storefront render 16,
  marketing 176, winback_auto 79, publisher 247, onboarding 116, gate1 221,
  upload_resilience 35, shop_address 29, storefront_seo 83: all green;
  website_builder fails only its pre-existing "3 channels" check.
- Browser: Sales Analytics with upload + website channels shows chips,
  donut and stacked months; filtering to the website shows its ₹3,294 /
  3 orders; a long toast wraps inside a rounded rectangle; the product page
  shows the verified review.

## Shiprocket brief (not implemented)

Flow per order, triggered when the seller marks it Packed:
auth (`POST /v1/external/auth/login`, API user, token valid 10 days) ->
`POST /orders/create/adhoc` (order + package weight/size) -> courier check
`GET /courier/serviceability` -> `POST /courier/assign/awb` -> label
`POST /courier/generate/label` -> pickup `POST /courier/generate/pickup`.
Status back via Shiprocket webhooks -> our Shipped / Delivered / RTO.
Batching: one daily cut-off (e.g. 1pm) generates AWBs, one pickup request and
one manifest for every Packed order. Needs per product weight/dimensions and
a pickup address. Details in the chat reply of 2026-10-03.
