# Sign in with ChatGPT

Sellers can sign in with their ChatGPT account and, if they allow it, have the
app's AI writing run on their own ChatGPT Plus or Pro plan instead of ours.

Source: OpenAI's developer docs at <https://developers.openai.com/siwc> and the
help articles <https://help.openai.com/articles/20001410> and
<https://help.openai.com/articles/20001542>, read on 30 September 2026.

## Status: waiting on OpenAI

The code is finished, but it does nothing until OpenAI issues a client ID. For a
paid, hosted app like this one there is no self-serve key. The self-serve
open-source flow only works for tools running on the user's own machine,
because it needs a `127.0.0.1` callback.

1. Apply at <https://openai.com/form/sign-in-with-chatgpt-interest/> as a
   commercial partner, and ask for **Sign in with ChatGPT with token sharing**
   (ChatGPT plan usage) on your website.
2. Register this callback URL with OpenAI, exactly:
   `https://onetapmanager.com/api/auth/chatgpt/callback`
3. When OpenAI sends the client ID (it starts with `oaiapp_`), set these in
   Render and trigger a manual deploy:

| Variable | Value |
| --- | --- |
| `CHATGPT_CLIENT_ID` | the `oaiapp_...` ID OpenAI issued |
| `CHATGPT_CLIENT_SECRET` | only if OpenAI issued a confidential client |
| `CHATGPT_REDIRECT_URI` | `https://onetapmanager.com/api/auth/chatgpt/callback` |
| `CHATGPT_PLAN_USAGE` | leave unset. Set `off` only if OpenAI approved sign-in without plan usage |

Optional: `CHATGPT_PLAN_MODEL` (default `gpt-6-luna`), `CHATGPT_PLAN_REASONING`
(default `low`), and `CHATGPT_FORCE_RECONSENT=on` once OpenAI confirms
`force_reconsent` for the client.

Until `CHATGPT_CLIENT_ID` is set, no button appears and every AI call works
exactly as it did before.

## What runs on the seller's ChatGPT plan

All AI writing, whenever the seller is connected:

- captions, hashtags and reel scripts (Social Media Manager, weekly auto-planner, Product Studio)
- the image-prompt directive (`studio.distil_aesthetic`) and product-photo descriptions
- every "Write with AI" field, website copy, product copy
- supplier purchase-order emails and cancellation emails
- the business analyst, the data chatbot, and Content Creator suggestions

Model: GPT-6 Luna, OpenAI's most efficient model, at low reasoning effort, so
each request uses as little of the seller's plan as possible. It is checked
against the seller's own model list; if Luna is missing, the cheapest listed
model is used.

## What does not

- **AI pictures and clips.** OpenAI does not allow image generation on a
  ChatGPT plan: its "Preview limitations" page lists image generation as an
  unsupported tool, and only `POST /v1/responses` is allowed. Pictures stay on
  the image engines, on Pro Max and app credits. A seller can still add their
  own OpenAI API key in Account for pictures only.
- **The brand aesthetic** (`studio.read_aesthetic`), by the owner's decision.
  It stays on Gemini and the rest of the app's chain.

## When the seller's plan cannot be used

This covers: not connected, a free ChatGPT account, the seller declined
sharing, or OpenAI having a bad minute. Today's AI chain writes instead.

## When their usage runs out

- With the seller waiting, a limit screen opens. **Manage usage** is the primary
  action and opens <https://chatgpt.com/settings/usage>, where ChatGPT shows
  when usage resets and where apps can be allowed to use ChatGPT credits.
  **Use One Tap Manager AI this time** repeats the request on our AI. We never
  guess a reset time, because OpenAI says it cannot be inferred from the error.
  If OpenAI sends a `Retry-After`, the screen says how long.
- Plan requests for that seller pause for the `Retry-After` time, or 10 minutes
  if none is given. The Account tab shows the pause and has a **Try again**
  button.
- With nobody waiting (the Monday planner, the cron at `/api/admin/tick`),
  our AI writes, so one seller's spent plan never stops anyone's week being
  planned.

## Security

- Authorization Code with PKCE and OpenID Connect. `state`, `nonce` and the PKCE
  verifier are fresh for every attempt, held on the server, tied to the browser
  by an HttpOnly cookie, single use, and expire after 10 minutes.
- The ID token is verified locally: RS256, OpenAI's JWKS, exact issuer,
  audience equal to our client ID, expiry and nonce.
- Tokens are encrypted in `secrets_store`. They are never in the browser, a URL
  or a log.
- Signing in with a ChatGPT account whose email matches an existing password
  account asks for that password once, the same rule as Google.
- Access tokens refresh one at a time per account. Refresh tokens rotate.
- Revocation: Account's **Stop using my ChatGPT plan** revokes the session at
  OpenAI, and deleting the account revokes it too.

## Known limits

- Transactions, one-time tickets and the refresh lock live in process memory.
  That is correct for the single Render instance this runs on. If the service is
  ever scaled out to several instances, move them to shared storage.
- OpenAI does not tell apps when a seller disconnects in ChatGPT. The next
  request or refresh finds out, and Account then asks the seller to connect
  again.

## Code

- `backend/core/chatgpt_auth.py`: discovery, PKCE, callback, ID-token check,
  token storage, refresh, revocation, the sign-in index
- `backend/core/chatgpt_plan.py`: Responses API requests on the seller's plan,
  streaming, model choice, limits and pauses
- `backend/core/aiprovider.py`: `plan_text()` tries the seller's plan before the
  chain, and `request_context()` records whether a person is waiting
- `backend/main.py`: `/api/auth/chatgpt/*`, `/api/account/chatgpt*`, and the 429
  `chatgpt_limit` handler
- `Smart CafeX/smart.js`: the button, the return from OpenAI, the Account card,
  the limit screen, the welcome note, the Home invitation
- `scripts/test_chatgpt_signin.py`: the tests
