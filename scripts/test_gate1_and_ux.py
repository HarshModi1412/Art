"""
The Gate 1 blockers, and the usability work that shipped with them.

Every check here maps to something a seller actually met and was defeated by.
The four Gate 1 items were found in a readiness audit that scored the product
6/10 sellable; each one is the kind of failure that ends a trial on its own,
which is why they are guarded here rather than trusted to stay fixed.

  1. A NaN anywhere in a response was a 500 — Sales Analytics dying with
     "Server error" the day after a file with one blank amount went in.
  2. Win-back messages signed with the seller's email handle, so a customer
     got "your last order with sunshine.creations1214".
  3. Campaigns recorded as SENT when the app had only made tap-to-send links,
     so "₹ recovered from win-backs" counted money from messages nobody wrote.
  4. Password reset promising an email on a server with no mail configured —
     a seller locked out of their entire catalogue with no way back.

Run: python3 scripts/test_gate1_and_ux.py
"""
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app, SafeJSONResponse  # noqa: E402
from backend.core import (analytics, brandname, campaigns, winback_proof,  # noqa: E402
                          password_reset, setup_steps, studio, social, supply)
import pandas as pd  # noqa: E402

# Unique per run: the account store is file-backed, so a fixed address
# accumulates campaigns and brand records across runs, and the totals stop
# meaning anything the second time the suite is run.
import uuid as _uuid  # noqa: E402
_TAG = _uuid.uuid4().hex[:8]

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


c = TestClient(app)
JS = pathlib.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
CSS = pathlib.Path("Smart CafeX/smart.css").read_text(encoding="utf-8")
CLASSIC_CSS = pathlib.Path("backend/static/styles.css").read_text(encoding="utf-8")
LANDING = pathlib.Path("backend/static/landing.html").read_text(encoding="utf-8")

# =========================================================================
print("\n== GATE 1 #1: a NaN is a missing number, not a 500 ==")
# =========================================================================
check("NaN becomes null", SafeJSONResponse._clean(float("nan")) is None)
check("so does +inf", SafeJSONResponse._clean(float("inf")) is None)
check("and -inf", SafeJSONResponse._clean(float("-inf")) is None)
check("real numbers pass through untouched", SafeJSONResponse._clean(2.5) == 2.5)
check("nested in a dict", SafeJSONResponse._clean({"a": float("nan")})["a"] is None)
check("nested in a list", SafeJSONResponse._clean([1.0, float("nan")])[1] is None)
check("deeply nested",
      SafeJSONResponse._clean({"a": [{"b": float("nan")}]})["a"][0]["b"] is None)
check("integers are left alone", SafeJSONResponse._clean(7) == 7)
check("strings are left alone", SafeJSONResponse._clean("nan") == "nan")

# The real guard: this is wired app-wide, not endpoint by endpoint. Every new
# division in the codebase is otherwise a new outage.
check("it is the app's DEFAULT response class, so one fix covers every endpoint",
      app.router.default_response_class is SafeJSONResponse
      or getattr(app, "default_response_class", None) is SafeJSONResponse
      or "default_response_class=SafeJSONResponse" in
      pathlib.Path("backend/main.py").read_text(encoding="utf-8"))

_r = SafeJSONResponse({"pct": float("nan"), "revenue": 1200.0})
check("and it renders valid JSON rather than raising",
      b'"pct":null' in _r.body and b'"revenue":1200' in _r.body, _r.body[:80])

# =========================================================================
print("\n== GATE 1 #2: never sign a customer's message with an email handle ==")
# =========================================================================
check("an email address is not a brand name", brandname._looks_like_a_handle("a@b.com"))
check("nor is an email local part", brandname._looks_like_a_handle("harshmodi1214"))
check("nor a phone number", brandname._looks_like_a_handle("9876543210"))
check("nor nothing at all", brandname._looks_like_a_handle(""))
# Deliberately narrow: real brands must survive.
check("but 'Studio 21' is a real brand name", not brandname._looks_like_a_handle("Studio 21"))
check("and so is 'Atelier 9'", not brandname._looks_like_a_handle("Atelier 9"))
check("and 'Level 9 Leather'", not brandname._looks_like_a_handle("Level 9 Leather"))
check("and a plain one-word name", not brandname._looks_like_a_handle("Kaya"))

_r = brandname.resolve(f"nothing-set-{_TAG}@test.co")
check("with nothing set, the resolver reports NO name rather than inventing one",
      _r["name"] == "" and _r["ready"] is False, _r)
check("display() gives the UI something honest to show instead",
      brandname.display(f"nothing-set-{_TAG}@test.co") == "Your shop")
try:
    brandname.require(f"nothing-set-{_TAG}@test.co")
    check("and the customer-facing path REFUSES to send", False, "no error")
except ValueError as e:
    check("and the customer-facing path refuses, with the fix in the message",
          "Add your shop name" in str(e) and "Product Studio" in str(e), str(e)[:90])

_src = pathlib.Path("backend/core/sitebuilder.py").read_text(encoding="utf-8")
check("the site no longer builds a brand out of the email local part",
      'email.split("@")[0]' not in _src, "still there")
check("nor a public web address out of it",
      "normalise_handle((email or \"\").split" not in _src)
check("a site with no brand gets a neutral placeholder, flagged for the UI to fix",
      "brand_placeholder" in _src)
check("and the frontend does not do it either either",
      'split("@")[0]' not in JS or 'never the email handle' in JS)

# =========================================================================
print("\n== GATE 1 #3: 'sent' has to mean sent ==")
# =========================================================================
EM = f"gate1-campaigns-{_TAG}@test.co"
_rows = [{"customer_id": "c1", "customer_name": "A", "phone": "9876543210", "monetary": 1200},
         {"customer_id": "c2", "customer_name": "B", "monetary": 900}]
res = campaigns.send(EM, _rows, "Kaya", channels=("email", "whatsapp"))
check("a WhatsApp link is PREPARED, not delivered",
      res["prepared"] == 1 and res["delivered"] == 0, res)
check("a customer with no contact details is reported, not dropped", res["skipped"] == 1)
check("no campaign is recorded as sent", not res["campaign_id"])
check("one is recorded as pending instead", bool(res["pending_campaign_id"]))
check("and the summary says so in words the seller will read",
      "not counted as sent until you confirm" in res["summary"], res["summary"])

_sum = winback_proof.summary(EM)
check("the recovered-value total counts nobody it did not reach",
      _sum["totals"]["contacted"] == 0, _sum["totals"])
check("but the pending ones are visible rather than hidden",
      _sum["totals"]["pending_customers"] == 1)
check("the headline asks for the step that is missing",
      "ready to send" in _sum["headline"], _sum["headline"])
check("and it is grammatical for one message",
      "1 message is ready" in _sum["headline"], _sum["headline"])
_pending = next(r for r in _sum["campaigns"] if r["state"] == "pending")
check("a pending campaign is explicitly not measurable", _pending["measurable"] is False)
check("and says why", "confirm" in (_pending.get("note_state") or ""))

winback_proof.confirm_sent(EM, res["pending_campaign_id"])
_sum2 = winback_proof.summary(EM)
check("confirming it is what makes it count", _sum2["totals"]["contacted"] == 1)
check("and nothing is left pending", _sum2["totals"]["pending_customers"] == 0)

# Nothing at all happened -> nothing is written. An empty history is honest.
EM2 = f"gate1-nothing-{_TAG}@test.co"
res2 = campaigns.send(EM2, [{"customer_id": "x", "customer_name": "X"}], "Kaya")
check("a campaign where nobody could be reached records NOTHING",
      not campaigns.history(EM2), campaigns.history(EM2))
check("and says plainly that nothing went out",
      "Nothing went out" in res2["summary"], res2["summary"])

# =========================================================================
print("\n== GATE 1 #4: a locked-out seller has a real way back ==")
# =========================================================================
_was = os.environ.pop("SMTP_HOST", None)
_ans = password_reset.request_seller("anyone@test.co", "http://x")
check("with no mail server, it does NOT claim a link is on its way",
      _ans["ok"] is False and _ans["email_ready"] is False, _ans)
check("it says why", "cannot send email" in _ans["message"])
check("gives a route that actually works", bool(_ans.get("support_email")))
check("and reassures them nothing is lost",
      "Nothing in your account is lost" in _ans["message"])

# The answer must still not reveal whether an account exists.
_a = password_reset.request_seller("definitely-not-a-user@test.co", "http://x")
check("and the answer is identical for an address with no account",
      _a["message"] == _ans["message"])

check("support can mint a link for a real account",
      hasattr(password_reset, "admin_reset_link"))
_main = pathlib.Path("backend/main.py").read_text(encoding="utf-8")
check("that path is gated on an admin token", "ADMIN_TOKEN" in _main)
check("and refuses everyone when no token is configured",
      "Admin recovery is not enabled" in _main)
check("compared in constant time, not with ==", "secrets.compare_digest" in _main)
if _was:
    os.environ["SMTP_HOST"] = _was

check("the seller login now HAS a forgot-password link at all",
      "forgotLink" in JS and "forgotLink" in
      pathlib.Path("Smart CafeX/smart.html").read_text(encoding="utf-8"))
check("and shows the honest answer as a caution, not as success",
      'r.email_ready === false ? "err"' in JS)
_store = pathlib.Path("Smart CafeX/storefront/store.js").read_text(encoding="utf-8")
check("the storefront does the same for shoppers",
      "r.email_ready === false" in _store)

# =========================================================================
print("\n== the home screen leads with ONE next step ==")
# =========================================================================
_p = setup_steps.progress(f"brand-new-seller-{_TAG}@test.co")
check("a brand-new seller has steps to do", _p["total"] == 5 and _p["done"] == 0)
check("and exactly one of them is next", bool(_p["next"]))
check("the first is the sales file, because everything comes from it",
      _p["next"]["id"] == "sales", _p["next"])
check("every step says what the seller GETS, not what the software needs",
      all(len(s["why"]) > 40 for s in _p["steps"]))
check("and how long it takes", all(s["minutes"] > 0 for s in _p["steps"]))
check("it is not complete yet", _p["complete"] is False)
check("the API hands it to the home screen", '"setup": setup_steps.progress' in _main)
check("the home screen renders it", "function setupCard" in JS)
check("it disappears when there is nothing left to do",
      "if (!setup || setup.complete || !setup.next) return \"\";" in JS)
check("and every button on it goes somewhere real", "function wireSetupCard" in JS)

check("the busy sections of the home screen are folded away by default",
      'details class="fold"' in JS and 'id="chanFold"' in JS)
check("and the folded platform strip is fetched only when opened",
      'chanFold.dataset.loaded' in JS)

# =========================================================================
print("\n== apps: the seller's order, and two hidden but reachable ==")
# =========================================================================
_ids = [ln.split('id: "')[1].split('"')[0]
        for ln in JS.split("const MODULES = [")[1].split("\n];")[0].splitlines()
        if 'id: "' in ln]
check("the order is the one the seller asked for",
      _ids[:8] == ["sales", "subcategory", "orders", "products", "inventory",
                   "supply", "studio", "social"], _ids[:8])
check("Marketing is off the home grid", 'id: "marketing"' in JS and
      JS.split('id: "marketing"')[1].split("},")[0].count("offGrid") == 1)
check("so is Billing & GST", JS.split('id: "gst"')[1].split("},")[0].count("offGrid") == 1)
check("but the grid filters on offGrid rather than deleting them",
      "!m.offGrid" in JS)
check("and both are still routed", 'if (id === "marketing")' in JS and 'if (id === "gst")' in JS)
check("reachable by URL — #/module/marketing and #/module/gst",
      "#\\/module\\/([a-z]+)" in JS or "/^#\\/module\\/([a-z]+)$/" in JS)
check("tiles are grouped under plain-language headings", "MODULE_GROUPS" in JS)
check("and a locked tile says what to do, not just 'Locked'",
      "Add your sales file first" in JS)

# =========================================================================
print("\n== headline cards show at any volume ==")
# =========================================================================
_df = pd.DataFrame({
    "date": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-02-07"]),
    "amount": [1200, 800, 1500], "category": ["Wallets", "Belts", "Wallets"],
    "customer_id": ["a", "b", "c"], "product": ["w1", "b1", "w2"], "quantity": [1, 1, 1]})
_sc = analytics.subcategory_trends(_df)
check("sub-category analysis returns headline cards", len(_sc.get("cards") or []) == 4, _sc.get("cards"))
check("they are counts and sums of the seller's own rows, true at 3 orders",
      _sc["cards"][0]["value"] == "2" and _sc["cards"][3]["value"] == "₹3,500", _sc["cards"])
check("the biggest earner is named", _sc["cards"][1]["value"] == "Wallets")
check("with its share", _sc["cards"][2]["value"] == "77%", _sc["cards"][2])
check("a file with no category column explains itself instead of going blank",
      "map one column to" in analytics.subcategory_trends(
          _df.drop(columns=["category"])).get("reason", ""))
check("Sales Analytics builds the cards before deciding about thin data",
      JS.index("const cards = `") < JS.index("if (thin) {"))
check("and only the INFERENCES are held back",
      "your best days of the week" in JS and "thinData(rowCount, THIN_DATA_ROWS" in JS)
check("the thin-data notice can drop its ghost cards when real ones sit above it",
      "function thinData(rows, need, what, withKpis = true)" in JS)

# =========================================================================
print("\n== running low means one order form per supplier ==")
# =========================================================================
check("there is a per-supplier builder at all", hasattr(supply, "create_pos_by_supplier"))
_ssrc = __import__("inspect").getsource(supply.create_pos_by_supplier)
check("it groups by supplier", "groups.setdefault" in _ssrc)
check("items with no supplier still get a list rather than silence",
      "__none__" in _ssrc and "unassigned_supplier" in _ssrc)
check("the order is deterministic, so it does not reshuffle between refreshes",
      "sorted(groups" in _ssrc)
check("approving 'running low' no longer passes the insight id as item_ids",
      "supply.create_po(email, insight_id)" not in _main, "the old bug is back")
check("it calls the per-supplier builder instead",
      "supply.create_pos_by_supplier(email, insight_id=insight_id)" in _main)
check("the endpoint returns one entry per supplier",
      'payload["orders"]' in _main and '"supplier_name": p.get' in _main)
check("each with a way to actually send it",
      '"supplier_phone"' in _main and '"download_url"' in _main)
check("the UI offers WhatsApp and email per supplier",
      "wa.me/" in JS and "function showSupplierOrders" in JS)

# =========================================================================
print("\n== no supply-chain jargon in front of the seller ==")
# =========================================================================
for word, where in (("EOQ", "the suggestion card"), ("Reorder pt", "the table"),
                    ("Avg/day", "the table"), ("MOQ", "the form")):
    # One comment in the source explains WHY these words are gone; that is the
    # only place they may appear.
    hits = [ln for ln in JS.splitlines() if word in ln and not ln.strip().startswith("//")]
    check(f"'{word}' is gone from {where}", not hits, hits[:1])
_rsrc = __import__("inspect").getsource(supply._reason_text)
check("the reason a seller reads has no jargon either",
      not any(w in _rsrc for w in ("Economic order quantity", "Reorder point {rop}",
                                   "safety{", "EOQ is")), "jargon remains")
check("it explains itself in units the seller counts in",
      "and your supplier takes" in _rsrc and "buy again once" in _rsrc,
      _rsrc[_rsrc.find("base = (f\"You use"):][:160])
check("and it never blocks — a missing number is worked out, not demanded",
      "you will not have to set anything" in _rsrc)
check("the status badge says what to do", '● Buy now' in JS)

# =========================================================================
print("\n== dark mode you can actually read ==")
# =========================================================================
def _lin(v):
    v /= 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _lum(h):
    h = h.lstrip("#")
    return (0.2126 * _lin(int(h[0:2], 16)) + 0.7152 * _lin(int(h[2:4], 16))
            + 0.0722 * _lin(int(h[4:6], 16)))


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _token(css, name, block='[data-theme="dark"] {'):
    """One custom property's value out of a theme block.

    Regex rather than line splitting, because several tokens share a line
    (--chart-1 through --chart-4 are declared together) and every value carries
    a trailing semicolon.
    """
    import re
    body = css.split(block)[1].split("\n}")[0]
    m = re.search(rf"--{re.escape(name)}\s*:\s*([^;]+);", body)
    return m.group(1).strip().split()[0] if m else ""


for css, label in ((CSS, "Smart"), (CLASSIC_CSS, "Classic")):
    bg = _token(css, "bg")
    check(f"{label}: the dark ground is a dark grey, not pure black",
          bg.lower() == "#12151c", bg)
    for name, floor in (("text", 13.0), ("text-2", 7.0), ("muted", 4.5)):
        got = _token(css, name)
        r = _ratio(got, bg) if got.startswith("#") else 0
        check(f"{label}: --{name} ({got}) clears {floor}:1 on the ground — {r:.2f}:1",
              r >= floor, f"{r:.2f}:1")
    # The one that was actually broken: muted was 4.4:1, below AA, and it is
    # every hint and helper line in the app.
    check(f"{label}: --muted is comfortably above AA now, not scraping under it",
          _ratio(_token(css, "muted"), bg) >= 6.0,
          f"{_ratio(_token(css, 'muted'), bg):.2f}:1")
    # WCAG 2.2 SC 1.4.11 — the most-violated dark-mode rule.
    check(f"{label}: input borders meet the 3:1 non-text rule",
          _ratio(_token(css, "border-strong"), bg) >= 3.0,
          f"{_ratio(_token(css, 'border-strong'), bg):.2f}:1")
    check(f"{label}: there is a focus ring token, and it is visible",
          _ratio(_token(css, "focus"), bg) >= 3.0,
          _token(css, "focus"))
    check(f"{label}: nothing sits at maximum contrast (the harsh-dark-mode look)",
          _ratio(_token(css, "text"), bg) < 17.0)
    for sem in ("green", "amber", "red", "blue"):
        r = _ratio(_token(css, sem), bg)
        check(f"{label}: --{sem} passes AA as text — {r:.2f}:1", r >= 4.5, f"{r:.2f}:1")
    for n in range(1, 9):
        got = _token(css, f"chart-{n}")
        check(f"{label}: --chart-{n} is defined and readable",
              got.startswith("#") and _ratio(got, bg) >= 4.5, got)

check("the accent is split into a text colour and a fill colour",
      "--primary-fill:" in CSS and "--accent-fill:" in CLASSIC_CSS)
check("because one value cannot be both readable text and a button behind white",
      _ratio("#ffffff", _token(CSS, "primary-fill")) >= 4.5,
      f'{_ratio("#ffffff", _token(CSS, "primary-fill")):.2f}:1')
check("buttons use the fill", ".btn.primary { background: var(--primary-fill)" in CSS)
check("every focusable thing gets a ring", ":focus-visible" in CSS)
check("charts read their series from the theme rather than hard-coded hexes",
      "colorway: SERIES()" in JS and 'cssVar(`--chart-${i + 1}`' in JS)
check("and the old light-mode chart hexes are gone from the dark path",
      '"#0ea5e9"' not in JS and '"#10b981"' not in JS)
check("light mode defines the same tokens, so nothing is undefined there",
      "--chart-1:" in CSS.split('[data-theme="dark"]')[0])

# =========================================================================
print("\n== brand aesthetics actually reach the image ==")
# =========================================================================
check("there is a step between the essay and the camera",
      hasattr(studio, "distil_aesthetic"))
_dsrc = __import__("inspect").getsource(studio.distil_aesthetic)
_ssrc = __import__("inspect").getsource(studio)
check("it exists because a 900-word essay is TRUNCATED by image models",
      "77" in _ssrc and "truncat" in _ssrc.lower())
check("the result is short enough to survive", "DIRECTIVE_WORDS = (70, 110)" in _ssrc)
check("and it is cached against the essay, so it costs one call not one per image",
      "directive_from" in _dsrc and "_fingerprint" in _dsrc)

_essay = """LIGHT - Soft north window light from camera-left, roughly 10 o'clock, near 5400K. It stays low, which is why every shadow runs long.
PALETTE - Kraft brown (#A9835C) over about forty percent of frame, against a bone off-white (#EFE9DF).
SURFACES AND PROPS - Raw linen and untreated oak. Never marble, never glass.
FRAMING - Square, camera at product height, subject left of centre.
LENS AND DEPTH - 50mm at f/2.8, background falling soft.
GRADE - Low contrast, blacks lifted to about 12, warm cast in the highlights.
RULES - 1. Key light always from camera-left, never frontal. 2. The product never touches the frame edge. 3. No more than two props in frame.
WHERE THEY VARY - Packaging shots go tighter and darker."""
_fb = studio._directive_fallback(_essay)
check("with no AI reachable it still compresses deterministically", bool(_fb))
check("to a length a model will actually read", 40 <= len(_fb.split()) <= 140, len(_fb.split()))
check("keeping the lighting", "camera-left" in _fb)
check("the hex values", "#A9835C" in _fb)
check("the lens", "50mm" in _fb)
check("and the hard rules, which are the most shootable part",
      "never frontal" in _fb and "frame edge" in _fb)
check("headings themselves do not leak into the prompt",
      "LIGHT" not in _fb and "RULES" not in _fb, _fb[:80])

_brief = studio.build_brief({"name": "Kaya", "look": "warm", "aesthetic": "x" * 3000},
                            {"name": "Wallet", "category": "accessories"}, {})
_long = studio.image_prompt(_brief, studio.guidance_for("new", "carousel", "", "warm"), True)
check("without a directive the essay is capped rather than pasted whole",
      len(_long) < 2200, len(_long))
_brief2 = {**_brief, "aesthetic_directive": _fb}
_short = studio.image_prompt(_brief2, studio.guidance_for("new", "carousel", "", "warm"), True)
check("with one, the prompt is short and every clause is an instruction",
      len(_short.split()) < 190, len(_short.split()))
check("and the brand's look is near the FRONT, where truncation cannot reach it",
      _short.index("camera-left") < len(_short) // 2, _short.index("camera-left"))
check("build_brief carries the directive through", "aesthetic_directive" in _brief)
check("generation distils it first if it is missing",
      "distil_aesthetic(email)" in __import__("inspect").getsource(studio.generate_image))
check("and so does video, which has an even tighter prompt budget",
      "distil_aesthetic(email, brand)" in __import__("inspect").getsource(studio.generate_video))

# =========================================================================
print("\n== the seller can see the prompt before spending anything ==")
# =========================================================================
check("there is a preview that does not generate", hasattr(studio, "preview_prompt"))
_psrc = __import__("inspect").getsource(studio.preview_prompt)
check("it exists so 'it ignored my brand' becomes an answerable question",
      "look identical" in _psrc)
check("it reports where each part of the prompt came from", '"sources"' in _psrc)
check("and names what is MISSING, with the fix",
      "upload a few reference images" in _psrc)
check("the endpoint costs nothing", "/api/studio/prompt-preview" in _main)
check("the editor offers it", "smShowPrompt" in JS and "/api/studio/prompt-preview" in JS)
check("showing the words and whether a real photo was the starting point",
      "d.words" in JS and "starting from your own photo" in JS)

# =========================================================================
print("\n== post or reel, said before the seller taps ==")
# =========================================================================
_soc = __import__("inspect").getsource(social)
check("a card knows which kind it is", '"kind": "reel",' in _soc and "_card_kind" in _soc)
check("and says so in words, not a format code",
      "REEL · you film it" in _soc and "PHOTO POST · we draw it" in _soc)
check("the button says what will actually happen",
      "Approve & get the shot list" in _soc and "Approve & make the picture" in _soc)
check("and what is still needed from the seller", '"needs_from_you"' in _soc)
check("the panel renders that badge", "ins-kind" in JS and "ins-kind" in CSS)
check("the persona layer passes those words through instead of overwriting them",
      'card.get("cta") or "Approve' in
      __import__("inspect").getsource(__import__("backend.core.personas", fromlist=["x"])))

# The worse mistake, and the one that only appears on a deployment with no image
# AI connected: a card that promises "we draw it" and then cannot.
_kind = social._card_kind({"format": "carousel"}, can_draw=True)
check("with an engine connected, a photo card promises the picture",
      _kind["kind_label"].endswith("we draw it"), _kind)
_kind = social._card_kind({"format": "carousel"}, can_draw=False)
check("with NO engine, it does not promise one",
      "we draw it" not in _kind["kind_label"], _kind)
check("it asks for the seller's own photo instead",
      "add a photo" in _kind["kind_label"].lower()
      and "one of your own photos" in _kind["needs_from_you"], _kind)
check("and says plainly why, rather than failing later",
      "will not pretend" in _kind["needs_from_you"], _kind["needs_from_you"])
_kind = social._card_kind({"format": "carousel", "image_url": "/x.png"}, can_draw=False)
check("a post that already has its picture is not asked for another",
      "picture ready" in _kind["kind_label"], _kind)
_kind = social._card_kind({"format": "reel"}, can_draw=True)
check("a reel is a reel whatever engines exist", _kind["kind"] == "reel")
check("the capability is asked once per list, not per card",
      "can_draw = bool(studio.image_engines())" in
      __import__("inspect").getsource(social))
check("and the two kinds are visually different", ".ins-kind.reel" in CSS)
check("a reel's handover offers the upload directly, not a route to an editor",
      "rpUpload" in JS and "rpFile" in JS)
check("with the size checked before a slow phone uploads 60MB",
      "48 * 1024 * 1024" in JS)
check("and a numbered 'what happens next'", "rp-next" in JS and ".rp-next" in CSS)

# =========================================================================
print("\n== which AI, chosen by the seller, priced before the click ==")
# =========================================================================
check("Gemini/Veo is a clip engine now",
      "gemini" in [e["id"] for e in studio.VIDEO_ENGINES])
check("Hugging Face is still one", "huggingface" in [e["id"] for e in studio.VIDEO_ENGINES])
check("both animate the seller's own photo rather than inventing a product",
      all(e["reshoot"] for e in studio.VIDEO_ENGINES))
check("each carries a real price", all(e.get("cost_usd") for e in studio.VIDEO_ENGINES))
check("and the 6x price gap is stated, not buried",
      {e["cost_usd"] for e in studio.VIDEO_ENGINES} == {1.2, 0.2})
_vsrc = __import__("inspect").getsource(studio.video_engine)
check("a named engine that is not connected is refused, never substituted",
      "not connected" in _vsrc)
check("because a charge nobody asked for is worse than a refusal that explains itself",
      "worse than a refusal" in _vsrc or "quiet substitution" in _vsrc, _vsrc[:200])
_gv = __import__("inspect").getsource(studio.generate_video)
check("Veo failing names the real cause rather than shrugging",
      "Veo access" in _gv)
check("HF failing points at the other engine", "Google Veo" in _gv, _gv[-400:])
check("the picker is a real choice, not a confirm box", "function pickVideoEngine" in JS)
check("it shows each engine's cost before the seller commits", "eng-cost" in JS and ".eng-cost" in CSS)
check("and one engine still just asks for a yes", "if (opts.length === 1)" in JS)

# =========================================================================
print("\n== the landing page says what it is for ==")
# =========================================================================
check("the promise is the big-brand team, run by one person",
      "the way a big brand runs theirs" in LANDING)
check("and it names the three pillars, not just analytics",
      "One Tap Manager is that team" in LANDING)
check("there is a section on what NOT having it costs", 'id="opportunity"' in LANDING)
check("with money attached", "miss-worth" in LANDING and "₹1.2 lakh" in LANDING)
check("and the arithmetic shown, so a seller can check it",
      "at ₹900 a\n          sale and two sales a day" in LANDING
      or "two sales a day" in LANDING)
check("every illustrative figure is labelled as illustrative",
      "not results from a customer" in LANDING and "tickets-label" in LANDING)
check("the hero example cards are labelled too", "EXAMPLE · STOCK" in LANDING)
check("the AI that is genuinely new is on the page at all",
      "works out what your brand looks like" in LANDING)
for word in ("RFM", "EOQ", "reorder point", "GSTR-1", "chart of accounts",
             "double-entry", "SKUs", "data model", "lifetime value"):
    check(f"'{word}' is gone — a first-time seller does not know it", word not in LANDING)

# =========================================================================
print("\n== the first thing a seller does: never guess the columns wrongly ==")
# =========================================================================
# The failure this guards, found by probing rather than by a report: a file whose
# headers we do not recognise ("Tarikh, Grahak, Saman, Rakam", or an export whose
# header row sat one line low so the columns came through as Column1..Column4)
# came back mapped as {"date": "Tarikh", "amount": "Tarikh"} — the SAME column in
# both required roles — and build_transactions() then reported zero dropped rows.
# A seller's first experience was a dashboard of confident numbers computed from
# nonsense. Two causes: pandas parses bare small integers as nanosecond
# timestamps so ANY integer column looks like valid dates, and the date fallback
# never claimed its column so the amount fallback could take it too.
from backend.core import mapper  # noqa: E402
import warnings  # noqa: E402
warnings.filterwarnings("ignore")

_CASES = {
    "a plain export": pd.DataFrame({"Order Date": ["2026-01-05"], "Total (INR)": [1200],
                                    "Customer Name": ["Meera"], "Item": ["Wallet"], "Qty": [1]}),
    "a Shopify export": pd.DataFrame({"Name": ["#1"], "Created at": ["2026-01-05"],
                                      "Lineitem name": ["W"], "Lineitem quantity": [1],
                                      "Lineitem price": [1200], "Billing Name": ["M"]}),
    "a hand-kept book": pd.DataFrame({"date": ["2026-01-05"], "customer": ["M"],
                                      "product": ["W"], "amount": [1200]}),
    "Hinglish headers": pd.DataFrame({"Tarikh": ["2026-01-05"], "Grahak": ["M"],
                                      "Saman": ["W"], "Rakam": [1200]}),
    "numbers with no meaning": pd.DataFrame({"Tarikh": [1], "Grahak": [2], "Saman": [3], "Rakam": [4]}),
    "a header row one line low": pd.DataFrame({"Column1": ["x"], "Column2": ["a"],
                                               "Column3": [1], "Column4": [3]}),
    "a YYYYMMDD date column": pd.DataFrame({"A": [20260105], "B": [1200], "C": ["W"]}),
}
for _label, _df in _CASES.items():
    _m = mapper.suggest_mapping(_df)
    _real = [v for k, v in _m.items() if v and not k.startswith("_")]
    check(f"{_label}: no column is given two roles at once",
          len(_real) == len(set(_real)), _m)
    check(f"{_label}: it reports which fields it had to guess",
          isinstance(_m.get("_guessed"), list) and isinstance(_m.get("_needs_confirmation"), list), _m)

_m = mapper.suggest_mapping(_CASES["a plain export"])
check("a readable header row is mapped without needing confirmation",
      _m["_needs_confirmation"] == [], _m["_needs_confirmation"])
_m = mapper.suggest_mapping(_CASES["a Shopify export"])
check("a recognised export needs no confirmation at all", _m["_needs_confirmation"] == [])
_m = mapper.suggest_mapping(_CASES["Hinglish headers"])
check("unfamiliar headers with real dates still get mapped correctly",
      _m["date"] == "Tarikh" and _m["amount"] == "Rakam", _m)
check("but they are flagged, because the names told us nothing",
      set(_m["_needs_confirmation"]) == {"date", "amount"}, _m["_needs_confirmation"])
_m = mapper.suggest_mapping(_CASES["numbers with no meaning"])
check("a column of 1,2,3 is NOT accepted as dates just because pandas parses it",
      _m["date"] is None, _m)
_m = mapper.suggest_mapping(_CASES["a header row one line low"])
check("an unnamed-column file says it cannot tell rather than inventing a mapping",
      "date" in _m["_needs_confirmation"], _m)
_m = mapper.suggest_mapping(_CASES["a YYYYMMDD date column"])
check("but a real YYYYMMDD column IS recognised as dates", _m["date"] == "A", _m)
check("and the amount is a different column from the date", _m["amount"] == "B", _m)

check("the mapping screen highlights the fields it guessed",
      "map-check" in JS and "please check" in JS)
check("and styles them so they cannot be missed", ".map-check > select" in CSS)
check("a recognised export says so instead of asking",
      "We have filled it in" in JS)
check("and an unrecognised one explains what is at stake",
      "makes every number afterwards correct" in JS)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
