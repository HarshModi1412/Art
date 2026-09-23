# One Tap Manager: launch readiness plan

Working plan for `/plan-ceo-review`, 23 September 2026. Branch `main`.
Status: **under review.** Nothing below is approved until the decision ledger says so.

## What was asked

1. Write `Brand.md` and `Product.md` from what the app actually does.
2. Account tab, Email box: a link and a step-by-step guide to create the email app password, so a seller can connect their mail for supplier orders without leaving to hunt for it.
3. Walk the whole app as a new seller with a mock account, note every place steps can be cut and anything that blocks launch, fix it, and get a green signal.

## How the walkthrough was done

- **Where:** the latest `main`, run locally. Production is several deploys behind, and creating an account on the live site through a browser is something Claude will not do, so the live site was only checked read-only (public pages, headers, which commits are deployed).
- **Who:** a brand-new seller. Landing page, then signup, then first screen, then sample data, then every one of the 14 modules, then Account, all at 375px phone width.
- **Evidence:** page text, network log, console, screenshots.

## Step 0

### 0A. Premise

The product is fully built. The earlier `/office-hours` learning still stands: **zero demand evidence, validate one paying customer before scaling.** So the launch risk is not missing features. It is a first-time seller hitting a wall in the first ten minutes: a dead end, an error-looking screen, a setup step they cannot finish. This plan should optimise for **the first 10 sellers getting value on day one.** It should not add features.

Cost of doing nothing: visitors dead-end on a login page with no signup. Outlook sellers follow the email steps and fail. A clothing seller's first "wow" is a café's sandwich sales. (The website-builder preview was broken in production; that is now fixed, see R13.)

### 0B. Code that already exists and gets reused

| Need | Reuse |
|---|---|
| Email guide | `seller_mail.PROVIDERS` / `guess()` (provider table), `POST /api/mail/account` (real login + test send), `openMailAccount()` |
| Signup from the app | `POST /api/register`, the landing page's `openSignup` form |
| Empty states | the module empty-state pattern already used by Orders / Inventory |
| Product.md facts | `pricing.py` (plans, gates, credits), `MODULES` in `smart.js`, the 1,944-line `README.md` |

### 0C. Where this is going

```
  CURRENT STATE                      THIS PLAN                           12-MONTH IDEAL
  Fully built, 14 modules,     --->  First-run path with no dead   --->  A seller connects a channel,
  secure, tested. First-run          ends: sign up from anywhere,        never uploads a file, and gets
  has dead ends and café             email connects in one screen        a filled PO, a written win-back
  sample data; zero paying           with the right link, honest         and a week of posts every
  customers.                         empty states, docs that match       Monday. Demand proven with
                                     the code.                           paying sellers first.
```

## Findings from the walkthrough (pending decisions)

| ID | Finding | Evidence | Severity |
|---|---|---|---|
| R1 | Email setup: one button opens a second modal; one line of Gmail-only help, no link; help does not follow the typed address; 5 fields; after connecting it jumps to Suppliers, not back to Account | `smart.js` `openMailAccount`, Account email pane | Requested |
| R2 | Outlook/Hotmail/Live listed as supported, but Microsoft disabled app-password SMTP for personal accounts in Mar/Apr 2026; those sellers will fail | `seller_mail.PROVIDERS`; Microsoft docs | High |
| R3 | Every `@zoho.com` address is sent to `smtp.zoho.in`; global-region Zoho accounts fail login | `seller_mail.PROVIDERS` | Medium |
| R4 | The app's login screen (`/smart`) has **no way to create an account** | `smart.html` login card | **Launch blocker** |
| R5 | Landing CTAs "Open the app" and "Open One Tap Manager free" send new visitors to that login dead end | `landing.html` | **Launch blocker** |
| R6 | A seller who signed up one second ago is greeted "Welcome back" | `renderHome` | Low |
| R7 | Sample data is a café (Sandwiches, Cold Coffee); the ideal customer sells clothes, jewellery, perfume | `data/sample_transactions.csv` | Medium |
| R8 | Reviews / Complaints / Strategy answer a normal empty state with HTTP 400, shown as "Could not load this"; the sample-data toast says "every module is live now", which is false | network log, `smart.js` | Medium |
| R9 | Em dashes and an emoji icon (`🛍️`) in the app's own UI copy; `Brand.md` bans both | home screen text | Low |
| R10 | A new seller's approval badge shows a generic "trending product-content angle for small brands" post before the app knows anything about them | `/api/smart/state` insights | Low |
| R11 | `Brand.md` says plans are Free / Semi Pro / Pro and "₹999 for Pro"; the code and landing page sell Free / Max ₹999 | `Brand.md` vs `pricing.py` | Medium |
| R12 | On a phone, the whole first screen is the explainer; the first action is below the fold | 375px screenshot | Low |
| R13 | **Fixed and pushed (`ae21533`):** `frame-ancestors 'none'` from the last security pass blanked the Website Builder preview in production | console + live headers | Was critical |

## Decision ledger

| ID and owner | Contract and evidence | Current | Proposed | Status | Exact approval and scope |
|---|---|---|---|---|---|
| MODE (user) | Review mode | HOLD SCOPE | none | approved | D4 answer "Hold scope (recommended)", 23 Sept |
| R13 (Claude) | Builder preview must render; clickjacking still blocked | `'self'` / `SAMEORIGIN` | none | approved | Restoring intended behaviour Claude broke; user asked for launch fixes. Pushed `ae21533` |
| R1, R2, R3 (Claude) | Email guide in the Account box; Outlook told the truth; Zoho region right | as found | inline guide per provider, direct links, auto-picked from the address, honest Outlook note, Zoho host by region | approved (stated scope) | User's task 2, plus correctness of that same guide |
| R4, R5 (Claude) | No dead end for a new visitor | as found | "Create a free account" on the login card opening the existing signup form; final landing CTA opens signup | approved (stated scope) | User's task 3, launch blockers |
| R6, R8, R11 (Claude) | First-run honesty | as found | first-visit greeting; empty state instead of HTTP 400 and a truthful sample toast; plan names in Brand.md | approved (stated scope) | User's task 3 and task 1 |
| R7 (user) | Sample data matches the ideal customer | café dataset | clothing / jewellery / perfume dataset, same columns | approved | D5 answer "Keep it in scope (recommended)" |
| R9 (user) | No em dash / emoji in app UI copy | ~264 lines in `smart.js` | sweep with a test gate | approved | D6 answer "Keep it in scope" (user overrode the Defer recommendation) |
| R10 (user) | New seller's first suggestion is specific | generic "trending angle" post | hold it until the app knows the product type | approved | D7 answer "/plan devx use this and think what should we do": user delegated the call; Claude chose Keep (first-run is the whole point of this plan; S effort) |
| R12 (user) | First action visible on a phone | explainer fills first screen | first action above the explainer for a seller with no data | approved | D8 answer "Keep it in scope (recommended)" |
| S3 (user) | The email form must not reach internal addresses | any host:port accepted (`seller_mail._client`); verified reaching loopback | guard: public IPs only, ports 25/465/587/2525, 10 connects/min, fix the dead `SMTPRecipientsRefused` branch | approved | D9 answer "Guard the form (recommended)" |
| S4 (user) | Loading sample data must not open with a chore caused by the sample itself | demo loads sales with no product list, so "18 platform names are not linked" is the first Today task | hide that task while the sales source is the sample; it returns on a real upload | approved | D10 answer "Hide it for sample data (recommended)" |
| T1 (user) | Server-written copy the app shows follows Brand.md too | em dashes remain in server messages (e.g. the 500 handler in `main.py`); the approved R9 sweep covers `smart.js`/`smart.html` only | recorded in TODOS.md as P3; not built in this launch | deferred | D12 answer "Add to TODOS.md (recommended)" |
| S8 (user) | A seller's "my email won't connect" can be diagnosed from logs | connect outcomes are returned to the browser and never logged | one structured log line per connect: account, provider, host, port, ok/failed, error class; never the password or the server reply | approved | D11 answer "Log each attempt (recommended)" |

**Approval readiness: PASS.** Checked rows and their sources: R1, R2, R3 (task 2 of the request:
"Add Link for Email code generation … details steps guide with proper link"); R4, R5, R6, R8, R11,
R13 (task 3: "note down everything … and any changes can be done to make the Webapp launch
ready … make changes"); R7 (D5); R9 (D6); R10 (D7, delegated to Claude, answered Keep);
R12 (D8); S3 (D9); S4 (D10); S8 (D11); T1 (D12, deferred to TODOS.md, not built). Mode (D4) is
setup, not a remedy approval. Unresolved rows: none.

## Answered: deferral decisions (0G, HOLD SCOPE)

All four were kept. Nothing from the stated scope was deferred. Original framing kept below as history.

- **D5 / R7 sample data:** recommended Keep. Effort M (human ~½ day / CC ~30 min). It is the activation moment for every seller without a file ready; the landing page says कपड़े, गहने, परफ़्यूम and the sample says Sandwiches.
- **D6 / R9 em dash + emoji sweep:** recommended Defer. Effort L (human ~1 day / CC ~1 hr). ~264 strings across 12,000 lines, no functional change, better as its own change with a test that fails the build.
- **D7 / R10 generic first suggestion:** recommended Defer. Effort S (human ~1 hr / CC ~10 min). Low impact; the other suggestion (Navratri) is genuinely useful.
- **D8 / R12 first action above the fold:** recommended Keep. Effort S (human ~1 hr / CC ~10 min). Directly the step reduction you asked for, on the very first screen.

## 0I. Build order (temporal interrogation)

```
  HOUR 1  foundations   seller_mail provider guide data (one source of truth), the
                        honest Outlook rule, Zoho by region; icon names in place of
                        emoji in the 6 backend files
  HOUR 2-3 core         Account email box with the inline guide; shared renderer
                        reused by the Suppliers modal; review endpoints return an
                        empty state; D2C sample dataset + generator
  HOUR 4-5 integration  login-card signup link + landing ?signup=1; home order and
                        greeting; generic suggestion gated; em dash sweep via a
                        string-aware script (never by hand)
  HOUR 6+  polish/tests test_launch_readiness.py; the em dash test gate; phone +
                        desktop browser pass; Brand.md, Product.md
```

Effort: human team ~3 days, CC + gstack ~2.5 hrs. Feasibility blockers: none. The only
external facts (provider app-password pages, Outlook's 2026 shutdown) are verified
against provider docs.

Surprise already found: the demo loads sales without a product list, so "18 platform
names are not linked" becomes the first Today task. Raised in Section 4.

## Section 1: Architecture review

```
  BROWSER (smart.js / landing.html)                    SERVER (FastAPI)
  +-------------------------------+                    +----------------------------------+
  | Account > Email box   [R1]    | GET /api/mail/     | main.mail_account                |
  |  provider chips <- providers -|--- account ------->|   + providers[] (NEW, from       |
  |  steps + "Open app passwords" |                    |     seller_mail guide data)      |
  |  address / app password       | POST /api/mail/    | seller_mail.connect              |
  |  Advanced: server / port      |--- account ------->|   refuse Outlook (R2)            |
  | Suppliers "Set up" reuses the |                    |   host guard [pending S3]        |
  |  SAME renderer, no copy       |                    |   Zoho other-region retry (R3)   |
  +-------------------------------+                    |   _friendly: 5.7.139 -> truth    |
  | /smart login card     [R4]    | link /?signup=1    +----------------------------------+
  | landing ?signup=1 opens [R5]  |------------------->| POST /api/register (unchanged)   |
  +-------------------------------+                    +----------------------------------+
  | Home: greeting [R6], Today    | GET /api/smart/    | smart state -> insights, generic |
  |  above explainer if no data   |----- state ------->|   post gated (R10)               |
  |  [R12]                        |                    +----------------------------------+
  | Review / Complaints / Strategy| GET positioning,   | 200 {needs:"review"} instead of  |
  |  empty state [R8]             | complaints, detect>|   400 (R8)                       |
  | "Load sample data" toast [R8] | POST /api/demo --->| data/sample_transactions.csv:    |
  |                               |                    |   D2C dataset (R7)               |
  | ico(): stroke icon or text[R9]|<-- icon names -----| product_config, commerce, smart, |
  +-------------------------------+                    | supply, ad_analytics, main (R9)  |
                                                       +----------------------------------+
```

- **Boundaries.** No new service, class, table or background job. One new response field
  (`providers` on `GET /api/mail/account`) and one changed contract (the three review
  endpoints answer 200 with `needs: "review"` instead of 400).
- **Coupling.** Removes one: the host table is duplicated today (`MAIL_HOSTS` in
  `smart.js` copies `seller_mail.PROVIDERS`). After this the browser only reads what the
  server sends. **OK**
- **Email connect data flow:**
  ```
  happy  address -> guide picked -> app password -> POST -> SMTP login + test mail -> saved -> Account shows Connected
  nil    no address     -> 400 "Enter your email address" (existing) -> toast, form keeps input
  empty  blank password -> 400 (existing) -> toast
  error  provider refuses -> mapped per provider with that provider's link;
         Outlook -> refused before any network call; M365 business domain -> 5.7.139 mapped to the same truth
  ```
- **State machine (seller's sending address):**
  ```
  NOT_CONNECTED --Connect--> TESTING --login+send ok--> CONNECTED --Disconnect--> NOT_CONNECTED
        ^                       |                          |
        +------ any failure ----+                          +--Change--> TESTING
  Invalid: CONNECTED without a successful test. Prevented: seller_mail.connect saves only after the send.
  ```
- **Scaling.** Nothing grows with load. A connect holds one outbound SMTP socket for about
  2 to 25 seconds (existing).
- **Single points of failure.** The seller's mail provider (outside our control, now explained);
  the single Render instance (existing).
- **Security architecture.** No new endpoint. `POST /api/mail/account` already takes a
  user-supplied host and port. See Section 3.
- **Production failure scenarios.** Google moves the app-password page: the link 404s but
  the written steps still name the menu path. Outlook: refused honestly.
- **Rollback.** Render: Rollback to the previous deploy (about 2 minutes), or revert and
  redeploy. No migration, no data rewrite; the sample CSV swap only affects future loads.

**Decision gate:** every item traces to approved rows R1 to R13. No new decision here.

## Section 2: Error and rescue map

```
  METHOD/CODEPATH              | WHAT CAN GO WRONG                   | EXCEPTION CLASS
  -----------------------------|-------------------------------------|-------------------------------
  seller_mail.connect          | wrong or normal password            | SMTPAuthenticationError
                               | Microsoft basic auth off (5.7.139)  | SMTPAuthenticationError
                               | Zoho account in the other region    | SMTPAuthenticationError
                               | wrong host, blocked port, timeout   | SMTPConnectError, OSError, TimeoutError
                               | provider refuses the recipient      | SMTPRecipientsRefused
                               | Outlook consumer domain             | ValueError, before any network call (NEW)
  smart_positioning /          | no reviews uploaded                 | was HTTPException 400 -> 200 needs=review
    smart_complaints /         | too few reviews to find a position  | HTTPException 400 (kept: a real error)
    smart_strategy_detect      |                                     |
  load_demo                    | sample file missing                 | HTTPException 503 (existing)
  landing ?signup=1            | modal markup missing                | none (only opens if found)
  ico()                        | unknown icon name / legacy emoji    | none (falls back to escaped text)

  EXCEPTION                    | RESCUED          | RESCUE ACTION                          | USER SEES
  -----------------------------|------------------|----------------------------------------|-------------------------------------
  SMTPAuthenticationError      | Y                | per-provider message + that link        | "Gmail refused that password. Make an
                               |                  |                                        |  app password here: [link]"
  5.7.139 (Microsoft)          | N <- GAP -> Y R2 | map to the Outlook truth               | "Microsoft stopped allowing this in 2026"
  Zoho other region            | N <- GAP -> Y R3 | retry the other Zoho host once         | nothing, it just connects
  SMTPConnectError / OSError   | Y                | "Could not reach host:port, try 465"   | message
  Outlook ValueError           | NEW Y            | 400 with the honest reason             | note in the guide; button explains
  no reviews                   | was 400 -> R8    | 200 needs=review                       | empty state + "Upload reviews" button
```

- **WARNING:** the last-resort branch of `seller_mail._friendly`
  (`f"{type(exc).__name__}: {exc}"`) repeats the remote server's own words back to the
  caller. That is the leak Section 3 deals with.
- Connect outcomes are returned but never logged. See Section 8.

**Decision gate:** the two GAP rows are the approved R2/R3 remedies. The catch-all goes to Section 3.

## Section 3: Security and threat model

| Threat | Likelihood | Impact | Mitigated by the plan? |
|---|---|---|---|
| **The email form can knock on internal ports.** `POST /api/mail/account` opens a TCP connection to whatever `host:port` the caller types (`seller_mail._client`). **Verified locally:** pointed at a loopback service, the server connected. **Corrected claim:** it does *not* leak the reply. Every `smtplib` error subclasses `OSError`, so all of them collapse into the fixed "Could not reach host:port" message. What remains is a blind probe: open vs closed, SMTP or not, told apart by timing and error type. Pre-existing; this plan redesigns the same form. (Side effect found: the `SMTPRecipientsRefused` branch in `_friendly` can never run, because the `OSError` branch catches it first.) | Low | Low to Medium | **No. WARNING, decision S3 below** |
| Outbound guide links | Low | Low | Yes: fixed `https://` constants with `rel="noopener noreferrer"`, never built from input |
| Zoho retry sending credentials to a guessed host | Low | High | Yes, by design: the retry only swaps `smtp.zoho.in` and `smtp.zoho.com`, never a guessed host |
| `?signup=1` reflected input | Low | Low | Yes: the flag only opens an existing modal; nothing is echoed |
| Review endpoints answering 200 | Low | Low | Yes: still `require_user`, still scoped to the caller's email |
| Secrets | none new | | App passwords stay Fernet-encrypted in `secrets_store` (existing) |

**Decision gate:** S3 answered (D9, guard the form). Remedy: resolve the host, refuse it unless
every address is public (not private, loopback, link-local, reserved or multicast); allow only
ports 25, 465, 587 and 2525; add `/api/mail/account` at 10 per minute to `ratelimit.LIMITS`;
reorder `_friendly` so `SMTPRecipientsRefused` is checked before `OSError`. User sees a 400
"That is not a public mail server" before any socket opens. Test: loopback and a private
address are refused with no connection attempt; a public provider host passes the guard.
Known limit: a DNS-rebinding window between the check and the connect, accepted as
Low/Low because nothing is echoed back.

## Section 4: Data flow and interaction edge cases

```
  EMAIL CONNECT   INPUT --> VALIDATION --------> TRANSFORM ------------> PERSIST ----------> OUTPUT
                  address   format, provider     host from the guide,     only after a real   Account shows
                  password  known, S3 guard      Zoho region swap          login + test mail   Connected
     nil/empty    -> 400 "Enter your email"      -- | --                   nothing saved       toast, input kept
     wrong type   port "abc" -> int() fails -> 400 (server casts, existing)
     too long     address > 254 -> rejected by the email regex (existing)
     timeout/OOM  25 s socket timeout -> "Could not reach" (existing)
     dup/conflict second click while testing -> button disabled during the request (NEW, see table)
```

| Interaction | Edge case | Handled? | How |
|---|---|---|---|
| Connect & send test | double tap | **Partly** | `withBusy` overlay blocks the page; the button itself will also be disabled until the request ends |
| Connect & send test | leave the screen mid-test | Yes | request finishes server-side; Account re-reads the status next time it opens |
| Address typed as `Me@Gmail.com ` | case and spaces | **Gap -> fixed in R1** | guide auto-pick lowercases and trims before matching |
| Business address on Google Workspace (`me@myshop.com`) | domain guess says `smtp.myshop.com`, which is wrong | **Gap -> fixed in R1** | the provider chips let the seller pick "Gmail / Google Workspace", which sets `smtp.gmail.com`; this is why the task asked for a *select* |
| Connected from Suppliers vs Account | where the seller lands afterwards | **Gap -> fixed in R1** | returns to the screen they started from (today it always jumps to Suppliers) |
| `/?signup=1` | visitor already signed in | Yes | the login card is only shown to signed-out visitors, so the link never appears to them |
| Home order (R12) | seller loads sample data | Noted | the order follows "no data yet"; once sample data exists the explainer returns above Today, which R12's approved rule ("for a seller with no data") intends |
| **Load sample data** | **the first Today task is "18 platform names are not linked to a product. Your best-seller list is wrong."** | **Gap: decision S4** | the demo loads sales with no product list, so the sample raises a chore about itself (verified in the browser) |
| Review modules | no reviews | Fixed in R8 | empty state with an upload button, no HTTP error |

Async ordering: no flow here shares mutable state across awaits. Connect is one request
that saves only on success. Sample load replaces the dataset once (existing).

**Decision gate:** S4 answered (D10). The other gaps in the table are already inside R1's approved remedy.

## Section 5: Code quality

- **DRY, CRITICAL for this change:** the mail host table exists twice today,
  `seller_mail.PROVIDERS` and `MAIL_HOSTS` in `smart.js`. R1 must not add a third copy for
  the guide. One table in `seller_mail` holds host, port, name, steps, link and whether it
  still works; the browser reads it from `GET /api/mail/account` and the JS copy is deleted.
- **One renderer, two places:** the Account box and the Suppliers modal call the same
  `mailGuideHtml()` / `bindMailGuide()`; `openMailAccount()` becomes a thin modal around it.
- **One icon helper:** `ico(v)` renders a stroke icon for a known name and escaped text
  otherwise. It replaces the six raw `${x.icon}` interpolations, so an old cached emoji
  still renders as text instead of breaking.
- **The em dash sweep is done by a string-aware script, never by hand.** It tracks code,
  quoted strings, template literals (with `${}` nesting) and comments, and changes only
  text inside strings. Afterwards `node` must parse the file, and the comment-only em dash
  count must be unchanged.
- **Complexity:** `seller_mail.connect` would pass 5 branches with the new rules, so each
  rule gets its own small helper (unsupported-provider refusal, public-host guard,
  region-fallback login). `connect` stays a straight line.
- **Under-engineering to avoid:** the sample generator is seeded, so the dataset and any
  test built on it are reproducible.
- **Over-engineering avoided:** no MX lookup to detect Google Workspace. The provider
  chip already covers it.

**Decision gate:** all within the approved R1, R7 and R9 remedies. No new decision.

## Section 6: Test review

```
  NEW / CHANGED                          TYPE         HAPPY                    FAILURE                      EDGE
  -------------------------------------  -----------  -----------------------  ---------------------------  --------------------------------
  providers list on GET /api/mail/account integration each has https link,     Outlook works=false          unknown domain -> "Other" guide
                                                      >=3 steps
  connect: Outlook refused               unit         -                        refused, no socket opened    hotmail / live aliases too
  connect: Zoho region                   unit         zohomail.in -> .in,      auth fail -> other host once never retried to a guessed host
                                                      zoho.com -> .com
  connect: 5.7.139 message               unit         -                        maps to the Outlook truth    -
  connect: S3 guard                      unit         public host passes       loopback / 10.x / 169.254    port 80 refused; no socket opened
  _friendly order                        unit         -                        RecipientsRefused reachable  -
  review endpoints (R8)                  integration  200 needs=review         "not enough reviews" 400 kept -
  sample dataset (R7)                    unit + int.  D2C categories, demo     no cafe words anywhere       unique order ids, amount > 0
                                                      loads, win-back list
  Today after demo (S4)                  integration  no "not linked" row      real upload -> row returns   -
  generic suggestion (R10)               integration  new seller: absent       -                            product type set -> may appear
  login card link + ?signup=1 (R4, R5)   source+E2E   link present, opens      no modal -> no error         already signed in -> not shown
  home order + greeting (R6, R12)        source+E2E   no data: Today first,    -                            data present: current order
                                                      "Welcome"
  em dash / emoji gate (R9)              source       zero in strings/icons    fails the build if one       comment em dashes untouched
                                                                               comes back
```

All of the above go in `scripts/test_launch_readiness.py`; every existing suite must stay
green. **The 2am-Friday test** is a real Gmail connect with a real app password. It needs a
live credential, so it is a manual post-deploy check (Section 9), not CI. **The hostile-QA
test** is the S3 probe re-run against loopback. **Flakiness:** the dataset is seeded and no
test depends on the clock except "last 30 days", which is relative to the data.

**Decision gate:** tests are the directly required proof of approved remedies. No new decision.

## Section 7: Performance

- Provider guide: a static list, a few KB, served on an endpoint that already exists. **OK**
- S3 guard: one DNS lookup per connect (milliseconds) on a call that already takes seconds. **OK**
- Sample dataset: about the same size as today (~2,600 rows), so demo load time is unchanged. **OK**
- The sweep and the icon names cost nothing at runtime. **OK**

No issues found.

## Section 8: Observability and debuggability

- **Gap:** when a seller says "my email will not connect", nothing on the server records
  what happened. The outcome goes back to the browser and is gone. Three weeks later you
  could not tell a wrong password from Outlook from a blocked port. **Decision S8.**
- Metric that tells you the guide works: the connect success rate per provider (falls
  out of S8's log line if it is approved).
- Signups from the new login-card link: not measured. GA is consent-gated and this is a
  launch-week question, so not proposed here.
- Alerts, dashboards, tracing: nothing new warrants them at this scale.
- Runbook "email will not connect": read the S8 log line, then (1) Outlook: expected,
  point the seller to Gmail or Zoho; (2) auth refused: resend the provider link;
  (3) could not reach: check the port, suggest 465.

**Decision gate:** S8 answered (D11, log each attempt). A test asserts the line is written and never contains the password.

## Section 9: Deployment and rollout

**Rollout order**
```
  NOW    Render > Manual Deploy of ae21533 (builder preview is broken in production today)
         then check: open Website Builder, the preview shows the shop
  NEXT   implement this plan -> all suites green -> push -> Manual Deploy
         healthCheckPath (/healthz) holds the old instance until the new one answers
  THEN   5-minute checklist below, then the manual Gmail connect (the 2am-Friday test)
```

- **Migrations:** none. (Still outstanding from the earlier audit: re-run `supabase/schema.sql`
  for the `feedback` index. Idempotent.)
- **Feature flags:** not needed. Every change is either a fix or copy and is safe to roll back.
- **Deploy-time risk window:** the HTML shell is `no-store` and the JS is versioned, so a fresh
  load always gets matching code. The window is a seller whose tab stayed open across the
  deploy: old JS plus the new review endpoints could draw an empty Reviews card (caught by
  `oops.js`), and product-type icons show as a word until they reload. Transient and cosmetic.
  **WARNING, accepted: fixed by a reload.**
- **Post-deploy, first 5 minutes:** `/healthz` 200 · builder preview renders · `/smart` login
  shows "Create a free account" · `/?signup=1` opens signup · Account > Email shows the chips
  and the Gmail link · Load sample data shows kurtas, not sandwiches · Reviews shows the empty
  state · no em dash on Home.
- **First hour:** the S8 log line appears for your own test connect.
- **Rollback:** Render > your service > Deploys > previous deploy > Rollback (about 2 minutes).
  Nothing to undo in the database.

**Decision gate:** no new decision. The deploy order is operational and in your hands.

## Section 10: Long-term trajectory

- **Debt paid down:** the duplicated host table disappears; the sweep's test gate stops em
  dashes returning to `smart.js`.
- **Debt left, evidenced:** copy the **server** writes and the app shows still has em dashes,
  for example the 500 handler in `main.py` ("Try that again in a moment — and it has been
  reported"). The approved sweep covered the app's own screens. **TODO proposal below.**
- **Path dependency:** good. When a provider changes its rules again (as Microsoft did), the
  fix is one row in one table.
- **Reversibility: 5/5.** UI, copy, a data file and guard logic; no stored data changes shape.
- **The 1-year question:** a new engineer finds the guide in `seller_mail`, the icons in
  `ico()`, and the em dash rule enforced by a test that names itself. Clear.

## Section 11: Design and UX

**The email box, first to last:** (1) "Which email do you use?" chips, pre-selected from
their login address; (2) three to five numbered steps for that provider, with one large
"Open Gmail app passwords" button; (3) address (pre-filled) and the 16-character app
password; (4) "Connect and send a test"; (5) Advanced (server, port) closed. Picking
Outlook replaces 2 to 4 with the honest note and a nudge to Gmail or Zoho.

```
  Account > Email
     |
     v
  [Gmail][Google Workspace][Yahoo][Zoho][iCloud][Rediffmail][Outlook][Other]   <- auto-picked
     |                                                    |
     v                                                    v
  Steps 1-3 + "Open Gmail app passwords" (new tab)     "Microsoft stopped allowing this in
     |   seller copies the 16 characters                2026. Use Gmail or Zoho." (no form)
     v
  address (pre-filled) + app password -> [Connect and send a test]
     |                       |                         |
     v                       v                         v
  TESTING (button off,    CONNECTED card:           ERROR shown under the button with that
   spinner, "you can      "Orders go out from       provider's own fix and link (not a toast
   leave this screen")    you@..." + Change /       that disappears)
                          Disconnect
```

| Feature | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Email box | "Checking…" while status loads | not connected: guide open | inline, provider-specific | connected card | connected but the last test failed: card plus the error line |
| Login card signup | none | none | none | opens signup | none |
| Review modules | existing skeleton | **new** empty state + "Upload reviews" | real errors unchanged | unchanged | "not enough reviews" keeps its message |
| Home, no data | existing skeleton | **Today first**, "Welcome" | unchanged | unchanged | unchanged |

- **Steps, before and after (the ask):** today: open Account, press "Set up sending email"
  (Account closes), read one Gmail-only line, leave the app to *find* the page, return, fill 5
  fields, land on Suppliers. After: open Account > Email, press the button that opens the exact
  page, paste, press Connect, stay in Account. About 4 taps, and no hunting.
- **Brand rules that bind this UI:** provider chips are **rounded rectangles, not pills**;
  no emoji on the chips; sentence case; no em dashes; the error says what to do.
- **Mobile:** chips wrap; the "Open … app passwords" button is full width; it opens a new tab
  so the half-filled form survives the trip.
- **Accessibility:** chips are a `radiogroup` with `aria-checked`; the link names its
  destination; 44px targets (existing phone rules); errors sit next to the control they
  belong to.
- **AI slop risk:** low. Every line is provider-specific and says exactly where to go.
- Recommendation: **consider `/plan-design-review`** for a deeper visual pass, and
  **`/design-review` after implementation** on the rendered screens.

**Decision gate:** all within R1, R6, R8 and R12 as approved. No new decision.

## Outside voice

Codex is not installed, so the review fell back to a Claude subagent. That fallback needs the
`TaskOutput` tool, which this session could not load, so **no second reviewer ran**. Recorded
as unavailable coverage, not as a clean pass. Install Codex (`npm install -g @openai/codex`)
for a real outside read next time.

## NOT in scope

| Item | Disposition | Why |
|---|---|---|
| Server-written messages with em dashes | Deferred to TODOS.md (D12) | the approved sweep covers the app's own screens; server copy is tracked as P3 |
| Outlook / Microsoft 365 sign-in by OAuth | Not proposed (HOLD SCOPE) | a new feature; the approved fix is telling Outlook sellers the truth and pointing them to Gmail or Zoho |
| Sample reviews so Reviews, Complaints and Strategy light up in the demo | Not proposed (HOLD SCOPE) | an optional enhancement; R8's empty state plus a truthful toast fully fixes the finding |

## What already exists (reused, not rebuilt)

`seller_mail` provider table and `connect()` (real login plus test mail); `POST /api/mail/account`;
`openMailAccount()` (becomes a thin wrapper); `POST /api/register` and the landing signup modal;
the module empty-state pattern; `ratelimit.LIMITS`; `oops.js` for the deploy window;
`pricing.py`, `MODULES` and `README.md` as the sources for Product.md.

## Dream state delta

After this plan a new seller can sign up from any page, see a demo that looks like their own
kind of shop, meet no error-looking screens, and connect their email in one box with the right
link. What is still missing for the 12-month ideal: channel connections replacing file uploads,
and proof that sellers pay. That second one is not code.

## Failure modes registry

```
  CODEPATH                    | FAILURE MODE                 | RESCUED? | TEST? | USER SEES?              | LOGGED?
  ----------------------------|------------------------------|----------|-------|-------------------------|--------
  seller_mail.connect         | Outlook consumer domain      | Y        | Y     | honest note             | Y (S8)
  seller_mail.connect         | wrong / normal password      | Y        | Y     | provider fix + link     | Y (S8)
  seller_mail.connect         | Zoho account, other region   | Y retry  | Y     | nothing, it connects    | Y (S8)
  seller_mail.connect         | Microsoft 5.7.139            | Y        | Y     | Outlook truth           | Y (S8)
  seller_mail.connect         | unreachable host / port      | Y        | Y     | "try 465"               | Y (S8)
  seller_mail.connect         | private / loopback host (S3) | Y        | Y     | "not a public server"   | Y (S8)
  review endpoints            | no reviews uploaded          | Y        | Y     | empty state + upload    | N (not an error)
  review endpoints            | too few reviews              | Y        | Y     | existing message        | N
  load_demo                   | sample file missing          | Y (503)  | N     | message                 | N
  landing ?signup=1           | modal not in page            | Y        | Y     | nothing                 | N
  ico()                       | unknown icon name            | Y        | Y     | the word, as text       | N
  deploy window (old JS open) | old renderer, new response   | Y        | N     | oops.js toast           | Y (client-error)
```
No row is unrescued, untested **and** silent: **0 critical gaps.**

## Diagrams produced

System architecture (Section 1), data flow with shadow paths (Sections 1 and 4), state machine
(Section 1), error flow (Section 2), deployment sequence (Section 9), user flow (Section 11), and
the rollback flow below.

```
  deploy looks wrong? --> Render > Deploys > previous deploy > Rollback (about 2 min)
        |                         |
        | no                      v
        v                  /healthz 200 on the old build -> sellers see the old app, no data lost
  run the 5-minute checklist (Section 9)
```

**Stale diagram audit:** the touched files contain no ASCII diagrams (the matches were HTML
comment closers), so nothing is stale.

## Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific finding above.
Run with Claude Code or Codex; checkbox as you ship.

- [ ] **T1 (P1, human: ~4h / CC: ~25min)** — seller_mail — one provider guide table, Outlook refusal, Zoho by region, 5.7.139 message, S3 host guard, `_friendly` order, S8 log line
  - Surfaced by: Sections 2, 3, 5, 8 — R1, R2, R3, S3, S8
  - Files: `backend/core/seller_mail.py`, `backend/core/ratelimit.py`, `backend/main.py`
  - Verify: `scripts/test_launch_readiness.py` (provider, Outlook, Zoho, guard, log cases)
- [ ] **T2 (P1, human: ~6h / CC: ~30min)** — Account email box — inline guide with provider chips and direct links, shared with the Suppliers modal, inline errors, return to where the seller started; delete `MAIL_HOSTS`
  - Surfaced by: Sections 5, 11 — R1
  - Files: `Smart CafeX/smart.js`, `Smart CafeX/smart.css`, `Smart CafeX/smart.html` (version bump)
  - Verify: browser at 375px and desktop; Gmail chip shows the link; Outlook chip shows the note
- [ ] **T3 (P1, human: ~1h / CC: ~10min)** — signup from anywhere — login card link, `/?signup=1` opens the modal, final landing CTA opens signup
  - Surfaced by: walkthrough — R4, R5
  - Files: `Smart CafeX/smart.html`, `backend/static/landing.html`
  - Verify: test + browser: `/smart` shows the link; `/?signup=1` opens signup
- [ ] **T4 (P1, human: ~2h / CC: ~15min)** — review modules — 200 `needs: "review"` with an empty state; truthful sample toast
  - Surfaced by: Section 2 — R8
  - Files: `backend/main.py`, `Smart CafeX/smart.js`
  - Verify: test for the three endpoints; browser shows the empty state, no console 400s
- [ ] **T5 (P1, human: ~4h / CC: ~20min)** — sample data — seeded generator and a clothing / jewellery / perfume dataset with the same columns
  - Surfaced by: walkthrough — R7
  - Files: `scripts/make_sample_data.py`, `data/sample_transactions.csv`
  - Verify: test (categories, no café words, unique ids, win-back list); browser shows kurtas
- [ ] **T6 (P2, human: ~1h / CC: ~10min)** — Today — hide "platform names not linked" while sales are the sample
  - Surfaced by: Section 4 — S4
  - Files: to be determined (where Today builds that task)
  - Verify: test: after demo absent, after a real upload present
- [ ] **T7 (P2, human: ~1h / CC: ~10min)** — suggestions — hold the generic "trending angle" post until the product type is known
  - Surfaced by: walkthrough — R10
  - Files: `backend/core/content_gen.py` (and its caller)
  - Verify: test: a brand-new seller's insights do not include it
- [ ] **T8 (P2, human: ~1h / CC: ~10min)** — home — "Welcome" before any data; Today above the explainer while there is no data
  - Surfaced by: walkthrough — R6, R12
  - Files: `Smart CafeX/smart.js`
  - Verify: browser at 375px: the first action is visible without scrolling
- [ ] **T9 (P2, human: ~1 day / CC: ~45min)** — copy and icons — string-aware em dash sweep of `smart.js` and `smart.html`; icon names instead of emoji in 6 backend files; `ico()`; test gate
  - Surfaced by: Sections 5, 10 — R9
  - Files: `Smart CafeX/smart.js`, `Smart CafeX/smart.html`, `backend/core/product_config.py`, `backend/core/commerce.py`, `backend/core/smart.py`, `backend/core/supply.py`, `backend/core/ad_analytics.py`, `backend/main.py`
  - Verify: `node` parses `smart.js`; comment em dash count unchanged; test gate passes
- [ ] **T10 (P1, human: ~4h / CC: ~20min)** — tests — `scripts/test_launch_readiness.py` for everything above; all existing suites green
  - Surfaced by: Section 6
  - Files: `scripts/test_launch_readiness.py`
  - Verify: `python scripts/test_launch_readiness.py` plus the existing suites
- [ ] **T11 (P2, human: ~3h / CC: ~20min)** — docs — `Brand.md` plan names (Free / Max) and current offer; new `Product.md`
  - Surfaced by: walkthrough — R11, and task 1 of the request
  - Files: `Brand.md`, `Product.md`
  - Verify: plan names and prices match `backend/core/pricing.py`
- [ ] **T12 (P1, ops, you)** — deploy — Manual Deploy of `ae21533` now; after T1–T11, deploy again and run the Section 9 checklist, including a real Gmail connect
  - Surfaced by: Section 9 — R13
  - Files: none
  - Verify: builder preview renders in production

## Completion summary

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY                   |
  +====================================================================+
  | Mode selected        | HOLD SCOPE                                  |
  | System Audit         | 14 modules, fully built; prod several       |
  |                      | deploys behind; frame header broke the      |
  |                      | builder in prod (fixed, ae21533); zero      |
  |                      | paying customers                            |
  | Step 0               | HOLD SCOPE; R1-R13 in scope; 4 deferral     |
  |                      | candidates, all kept                        |
  | Section 1  (Arch)    | 0 issues (host input handled in S3)         |
  | Section 2  (Errors)  | 11 error paths mapped, 2 GAPS (both fixed   |
  |                      | by approved R2/R3)                          |
  | Section 3  (Security)| 1 issue found, 0 High severity              |
  | Section 4  (Data/UX) | 9 edge cases mapped, 0 unhandled after S4   |
  | Section 5  (Quality) | 3 issues found (all folded into remedies)   |
  | Section 6  (Tests)   | Diagram produced, 0 gaps                    |
  | Section 7  (Perf)    | 0 issues found                              |
  | Section 8  (Observ)  | 1 gap found (approved S8)                   |
  | Section 9  (Deploy)  | 2 risks flagged (deploy window; hotfix      |
  |                      | still undeployed)                           |
  | Section 10 (Future)  | Reversibility: 5/5, debt items: 1 (T1)      |
  | Section 11 (Design)  | 3 issues (all folded into R1)               |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (3 items)                           |
  | What already exists  | written                                     |
  | Dream state delta    | written                                     |
  | Error/rescue registry| 11 rows, 0 CRITICAL GAPS                    |
  | Failure modes        | 12 total, 0 CRITICAL GAPS                   |
  | TODOS.md updates     | 1 item proposed (added)                     |
  | Scope proposals      | 0 proposed, 0 accepted (HOLD SCOPE)         |
  | CEO plan             | skipped by mode                             |
  | Outside voice        | codex: not installed; native fallback:      |
  |                      | unavailable                                 |
  | Lake Score           | N/A (every question was kind-only)          |
  | Diagrams produced    | 7 (architecture, data flow, state, error,   |
  |                      | deployment, user flow, rollback)            |
  | Stale diagrams found | 0                                           |
  | Unresolved decisions | 0                                           |
  +====================================================================+
```

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR | mode: HOLD_SCOPE, 0 critical gaps |
| Outside Review | codex (not installed), native fallback | Independent 2nd opinion | 1 | unavailable | codex not installed; fallback could not load TaskOutput; no completed external review |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** codex, plan-review phase, unavailable (CLI not installed; the native fallback could not load TaskOutput). No findings, because no reviewer ran.
- **VERDICT:** CEO CLEARED — ready to implement; eng review required.

NO UNRESOLVED DECISIONS
