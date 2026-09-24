# Build plan: first-run journey

Design (reviewed, source of truth): `docs/designs/first-run-journey.md`.
This file records how the build settles the 15 concerns the spec review left open
(R2-1 to R2-15), plus the facts checked in the code.

## Decisions for the open review concerns

| # | Decision |
|---|---|
| R2-1 | One rule. The journey card replaces the old `setup_steps` card on home for every account. Accounts with no record see "Set up your shop: 3 parts" with Start; the first tap creates the record (no pop-up, `welcomed_at` set) and asks the welcome question. `setup_steps` stays in the API payload and its tests, but home no longer renders it. |
| R2-2 | When `active` is false: if any step is skipped and still not done, the card shows a compact line ("2 skipped steps left. Finish them"). If everything is done, the card is hidden. "Hide this" dismisses it. A "Setup guide" button in the home header (next to "How this works") always reopens the journey and undoes `dismiss`. |
| R2-3 | Parts are guided in order, but not locked. After Part 1 is finished once, Parts 2 and 3 both count as unlocked, and the home card lists all three with an Open button each. The Part 2 task is created when Part 1 finishes; the Part 3 task is created when Part 2 finishes, or when Part 1 finishes if Part 2 was already finished. |
| R2-4 | The UPI branch of the `payment` check also needs the store currency to be INR (`currency.normalize` defaults to INR). The Payment screen checks the currency. If it's not INR, it says "UPI works only for shops in rupees" and offers "Switch my shop to rupees" or the Razorpay/Stripe/PayPal screen. |
| R2-5 | "Want a free One Tap shop too?" means `choose_path("create")`. Connect steps keep their state and no tasks are removed, because they are done. The create steps then run in order. Imported products count as active, so `products` may already be done. The Website step asks once, "Show your N products in the shop?", which lists them. |
| R2-6 | Path switch: Part 1 is recomputed from the new path's steps, and `parts.1.done_at` stays as history. Parts 2 and 3 stay unlocked if Part 1 was ever finished (`parts.1.done_at` set). Part tasks are kept. |
| R2-7 | "Active product" means any product whose `status` is not `archived`, imported or not. The `photos` and `stock` checks need max(1, min(3, n)), so zero products never counts as done. With no products, those screens say "Add a product first" with a button to the quick-add card. |
| R2-8 | Product type is `user_store` key `product_type` (set by `smart.set_product_type`, the same call `/api/product-type` makes). Own words go in `PRODUCT_LABEL_KEY`. `shop` counts as done only when the raw `product_type` key is present, meaning the seller chose it (never the default). |
| R2-9 | The `/api/smart/state` summary carries `needs_sync`. Home sends `POST /api/onboarding {action:"sync"}` when it's true, so a step finished inside a real module closes its task the next time home loads. `done_at` means "first observed done", as the docstring says. |
| R2-10 | The web address is suggested from the Latin letters in the shop name. If none are left (a Devanagari name), the field starts empty with the example "priya-kurtis" and a hint in the seller's language: "only a to z, 0 to 9 and -". |
| R2-11 | The storefront shows "Send payment screenshot on WhatsApp" only when a seller number is saved. The Payment screen asks for the WhatsApp number when it's missing. |
| R2-12 | The app runs one uvicorn worker (`render.yaml` startCommand has no `--workers`). One module-level lock, `smart.TASK_LOCK`, guards every `smart_tasks` read-modify-write: add, toggle, delete, progress, and onboarding reconcile. If workers are ever added, this becomes a per-account file lock (noted in the code). |
| R2-13 | The 2-second memo is used only by `/api/smart/state` and the ETag fingerprint. `GET /api/onboarding` and every POST compute fresh and clear the memo. |
| R2-14 | Upload destinations. Quick-add product photo: `/api/site/image`, then the product's `image_url` (the `photos` check reads `image_url` or `images`). Style photos: `/api/site/image`, then `/api/studio/design-language/add`, which lands in `brand.refs` (the `style` check reads it). Product photos in Part 2: same as quick-add. "Read my look" is an optional button after 3 style photos. It uses AI, is labelled as such, and isn't needed for the step. |
| R2-15 | Checkpoint: stages are built and verified in order (engine, then Part 1 and UPI, then connect, then Parts 2 and 3), each with tests before the next. The founder asked for a second /office-hours pass after the build: that pass is the checkpoint, and The Assignment's findings can reorder or cut work after it. |

## Facts checked in the code
- `brandname.resolve(email)["ready"]` is true only for a name the seller set, never
  a handle-like fallback (`backend/core/brandname.py:55`).
- `instagram.is_connected(email)` reads stored credentials only (`backend/core/instagram.py:287`).
- `user_store.set_key` locks a single write (`backend/core/user_store.py:71`), not a
  read followed by a write, hence `TASK_LOCK`.
- The store currency defaults to INR (`backend/core/currency.py:40`).
- The storefront has cash on delivery on by default and no UPI (`backend/core/sitebuilder.py:790`).
- Studio style photos are added with `POST /api/studio/design-language/add {url}`.
