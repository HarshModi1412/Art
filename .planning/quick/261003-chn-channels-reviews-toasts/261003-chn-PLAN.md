---
quick_id: 261003-chn
slug: channels-reviews-toasts
date: 2026-10-03
mode: quick
---

# Sales channels, website reviews into Review Analytics, rectangular pop-ups; Shiprocket brief

## Requests (from the user)

1. Reviews section on the product website, attached to Review Analytics; same
   for the other connectors (Shopify and the rest).
2. Sellers sell on several places (site, Amazon, Shopify...): show everything
   in Sales and Sub-Category Analytics, show the split, let them filter;
   hide the split with only one platform. Uploaded data is its own source.
3. Pop-ups (uploading, approved...) are ovals and text spills out: rounded
   rectangles with padding.
4. Shiprocket: a brief only (API flow, auto-create on status change, daily
   batching, what other platforms do). Not implemented.

## Found while exploring

- Pulling Shopify/Amazon/WooCommerce/Wix orders REPLACED the whole sales
  dataset: a second platform wiped the first and every upload.

## Tasks

1. smart.save_sales: per-channel slices (replace/append own slice; sample
   dropped when real data arrives); callers pass their channel.
2. analytics.channel_split / filter_channel; `channel` on /api/analytics,
   /api/subcategory, /api/subcategory/detail.
3. UI: channel chips + "Sales by channel" (donut + stacked monthly) only when
   2+ channels; filter refetches; mapping "Replace my uploaded sales".
4. Pop-ups: ios.css toast, app toast, work strip, storefront toast to 12-14px
   radius, padding, wrapping text.
5. Reviews: verified-buyer reviews on the storefront product page; seller can
   hide; synced into the review dataset as source "site"; review dataset
   gains Source/Product columns; uploads are source "upload".
6. Connector reviews: WooCommerce (REST products/reviews) and Wix (Reviews
   API) pulled with orders. Shopify and Amazon have no official review API:
   said so on screen.
7. Tests, browser check, SUMMARY, STATE, Shiprocket brief.
