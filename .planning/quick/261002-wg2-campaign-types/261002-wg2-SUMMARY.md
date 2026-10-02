---
quick_id: 261002-wg2
slug: campaign-types
status: complete
date: 2026-10-02
commit: 06659c1, 1f11518 (local, not pushed)
---

# Summary: campaign type dropdown, seven campaigns, real sent counts

## What changed

- `06659c1` backend:
  - Seven types: win-back, festival, second-order nudge, goes-well-with
    (Apriori pairs, lift >= 1.2), restock (past the usual reorder gap), VIP
    early access (note required), thank you + review request. Each has its
    own audience (`analytics.campaign_audience`), cooldown, product focus and
    10 voices (70 in all) with no-discount lines and subjects.
  - Campaigns read the full RFM table: the 500-customer display cap was
    hiding first-time buyers in bigger shops.
  - Offer "No discount": tracking-only codes, `ref=` links, applied quietly
    at 0 off so orders are still attributed.
  - Mid-task request from the user: count only messages actually sent.
    Tap-to-send links are not contacts until the seller taps that customer
    (`/api/campaign/{id}/tapped`); cooldown, results and history use the real
    count. The bulk "I have sent them" is gone.
  - WhatsApp: a no-discount template is submitted with the offer one.
- `1f11518` UI: dropdown with audience sizes, who/why text, per-type
  defaults; "No discount" button; "X of Y sent" counter and "Still to send"
  list; campaign totals exclude customers with no phone or email (reported
  separately); idea cards start a type.

## Evidence

- test_marketing_campaign: 176 passed (each type builds with the right
  audience and its own voices, no-discount ref codes price at 0 with no
  error, taps counted once, cooldown holds back only tapped customers).
- Regression green except test_website_builder's pre-existing "3 channels".
- Browser: dropdown lists 7 types with counts on sample data; VIP switches to
  No discount + required note; thank-you campaign with two phones sent,
  one tapped: "1 of 2 sent" on the results page and in history.
