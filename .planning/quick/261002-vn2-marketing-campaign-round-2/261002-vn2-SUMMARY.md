---
quick_id: 261002-vn2
slug: marketing-campaign-round-2
status: complete
date: 2026-10-02
commit: ccf0eb5, 6be100a, ca85837 (local, not pushed)
---

# Summary: Marketing Campaign round 2

## What changed

- `ccf0eb5` fix(mapping): Confirm & save shows "Saving your data…" with a
  spinner; button, Cancel, close and every field are locked until it returns.
- `6be100a` backend:
  - `analytics.association_rules` (pairwise Apriori: support, confidence,
    lift; chunked co-occurrence; 0.05s on 62k rows) and `recommend_for`.
  - `campaign_writer`: 10 hand-written voices per reason (win-back, festival),
    each built from parts so a missing product or suggestion never breaks a
    sentence; dealt round-robin per campaign (no two neighbours alike);
    subjects rotate; no AI call. Per-customer message override must keep the
    code.
  - `campaign_engine`: contact book merge, Apriori picks (never something the
    customer owns), 10% holdout when 20+, lasting campaign records,
    `analyze()` (funnel, money, lift vs holdout, diagnosis) and `ideas()`.
  - `contacts.py`: per-seller phone/email book.
  - `discounts.track`: click and applied stamps; `/api/shop/{h}/visit`;
    storefront reports the click once per visit.
  - `whatsapp`: Embedded Signup (code exchange, subscribe, register with an
    encrypted PIN, or coexistence syncs), `/api/whatsapp/embedded`.
- `ca85837` UI + fixes:
  - Draft: every customer row opens to their exact message, phone/email
    fields, "write this customer's message yourself", leave out. No-contact
    customers first, flagged "Add phone".
  - Results view (from "Track the results" and each past campaign): KPI tiles,
    drop-off funnel, lift vs held back, what to do next, customer by customer,
    copy shop link. Tap-to-send counts as reached only after "I have sent
    them".
  - "More campaigns that work": 5 ideas sized from the seller's sales.
  - WhatsApp: "Connect WhatsApp" (Embedded Signup) with tester note and
    "keep using the WhatsApp Business app"; pasting IDs under Advanced.
  - fix(mapper): a phone column with blanks is read as decimals; the ".0"
    would have become a wrong WhatsApp number. Fixed at mapping and at
    profile build (for data already saved).

## Evidence

- `scripts/test_marketing_campaign.py`: 152 passed (voices, picks, holdout,
  contact edits, tracker funnel and money, Embedded Signup with Meta mocked,
  decimal phone regression).
- Regression: winback_auto 79, marketing_module 7, publisher 247,
  onboarding 116, gate1 221, upload_resilience 35, shop_address 29,
  storefront_seo 83 all green. website_builder fails on its pre-existing
  "3 channels" check (unchanged from before this task).
- Browser (local): built a campaign from an uploaded POS file; 10 customers
  got 10 different voices with picks; edited one customer's message; sent
  (tap-to-send); results view rendered; WhatsApp setup rendered in both
  states.

## Needs the user

- Meta app for WhatsApp: set `WHATSAPP_APP_ID`, `WHATSAPP_APP_SECRET`,
  `WHATSAPP_CONFIG_ID` on Render; create the Facebook Login for Business
  configuration (WhatsApp Embedded Signup); add the app domain; add sellers
  as testers until Tech Provider approval. Coexistence officially needs Tech
  Provider status; until then sellers can untick it and use a new number.
- Not pushed. `data/*` changes in the working tree are local QA accounts.
