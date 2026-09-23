# TODOS

## App copy

### Remove em dashes from server-written messages the app shows

**What:** Replace em dashes in user-facing text that the backend writes and the app displays (error `detail` messages, insight titles and bodies, API-returned toasts), and extend the test gate to cover it.

**Why:** `Brand.md` section 7 bans em dashes on every customer-facing surface. The launch sweep (`LAUNCH_PLAN.md`, row R9) covered the app's own screens in `smart.js` and `smart.html` only. Server messages still break the rule, for example the unhandled-error message in `backend/main.py` ("Try that again in a moment — and it has been reported").

**Context:** The launch added a string-aware sweep script and a test that fails the build if an em dash appears inside a string in `smart.js`. Reuse that approach for Python: only change text inside string literals that reach the user (`HTTPException` details, insight dicts, messages returned in JSON), never comments or docstrings. `backend/main.py` alone has about 157 lines containing an em dash, most of them comments, so the scan must separate strings from comments the same way the JS sweep does. Start with `backend/main.py`, `backend/core/smart.py` and `backend/core/supply.py`.

**Watch out:** task titles are written by the server as "Make the reel for X — goes out Mon", and `smart.js` splits them on that em dash (`split(" — ")`) to put the deadline on its own line. Change both together, or the deadline stops splitting off.

**Effort:** M (human) / S (CC + gstack)
**Priority:** P3
**Depends on:** the launch em dash sweep of `smart.js` landing first (its script and test gate are the template).

## Completed
