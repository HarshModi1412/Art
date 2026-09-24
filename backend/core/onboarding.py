"""The first-run journey: "Set up your shop in 3 parts".

Design: docs/designs/first-run-journey.md (reviewed and approved), with the
build decisions in docs/onboarding-plan.md.

WHAT THIS IS
------------
A seller who signs up lands on twelve module tiles. This walks them, one small
question at a time, from "just signed up" to a shop that sells:

  Part 1  create path:  shop name, 3 products, website, UPI     -> live shop link
          connect path: connect Shopify/Woo/Wix/Amazon or a file -> their sales in
  Part 2  brand, style photos, product photos, Instagram        -> posts made for them
  Part 3  supplier, stock                                        -> warned before it runs out

THE RULES THIS FILE ENFORCES
----------------------------
* A step is done only when the real data says so. Every check below reads the
  same stored state the modules read; nothing is "done" because a button was
  pressed, and a step whose data goes away shows as not done again.
* Every check is local. No check calls a third party, because this runs on
  every home screen load of a 512MB server.
* Skipping is allowed, never silent. A skipped step becomes one task on the
  seller's list (one per step, however often they skip it), and that task ticks
  itself the moment the step is really done.
* progress() is a pure read. reconcile() is the only writer of derived state
  (done times, tasks), and it runs under smart.TASK_LOCK because it rewrites
  the same task list the seller is ticking.

THE RECORD (user_store key "onboarding")
----------------------------------------
Created at sign-up, so "new account" means "signed up after this shipped", not
"has no data". An existing account has no record: it never gets the pop-up,
and gets one the first time it opens the journey from the home card.

    v, created_at, lang, path, welcomed_at, dismissed_at,
    skipped {step: iso}, steps {step: {first_seen, done_at}},
    parts {"1": {opened_at, done_at}}, tasks {tag: task_id}, finished_at
"""
from __future__ import annotations

import datetime as _dt
import threading
import time

from backend.core import user_store

KEY = "onboarding"
VERSION = 1
LANGS = ("en", "hi")
PATHS = ("create", "connect")

# (id, part, paths). Order is the order the journey walks them.
STEPS: list[tuple[str, int, tuple[str, ...]]] = [
    ("shop", 1, ("create",)),
    ("products", 1, ("create",)),
    ("site", 1, ("create",)),
    ("payment", 1, ("create",)),
    ("connect", 1, ("connect",)),
    ("catalogue", 1, ("connect",)),
    ("brand", 2, PATHS),
    ("style", 2, PATHS),
    ("photos", 2, PATHS),
    ("instagram", 2, PATHS),
    ("suppliers", 3, PATHS),
    ("stock", 3, PATHS),
]
STEP_IDS = [s[0] for s in STEPS]
PRODUCTS_NEEDED = 3
STYLE_NEEDED = 3

# What a skipped step's task says. The task list is not translated, so the
# words are picked in the seller's language at the moment the task is made.
TASK_TEXT = {
    "en": {
        "shop": "Set up: name your shop",
        "products": "Set up: add 3 products",
        "site": "Set up: put your shop online",
        "payment": "Set up: add your UPI ID so customers can pay",
        "connect": "Set up: connect your website",
        "catalogue": "Set up: add your products to your list",
        "brand": "Set up: tell us about your brand",
        "style": "Set up: add 3 photos of your style",
        "photos": "Set up: add photos of your products",
        "instagram": "Set up: connect Instagram",
        "suppliers": "Set up: add who you buy from",
        "stock": "Set up: tell us how much stock you have",
        "part:2": "Set up Part 2: let us make your Instagram posts (about 10 minutes)",
        "part:3": "Set up Part 3: never run out of stock (about 5 minutes)",
    },
    "hi": {
        "shop": "सेटअप: अपनी दुकान का नाम रखें",
        "products": "सेटअप: 3 प्रोडक्ट जोड़ें",
        "site": "सेटअप: अपनी दुकान ऑनलाइन करें",
        "payment": "सेटअप: अपनी UPI ID जोड़ें ताकि ग्राहक पैसे दे सकें",
        "connect": "सेटअप: अपनी वेबसाइट जोड़ें",
        "catalogue": "सेटअप: अपने प्रोडक्ट सूची में जोड़ें",
        "brand": "सेटअप: अपने ब्रांड के बारे में बताएँ",
        "style": "सेटअप: अपने स्टाइल की 3 फ़ोटो जोड़ें",
        "photos": "सेटअप: प्रोडक्ट की फ़ोटो जोड़ें",
        "instagram": "सेटअप: Instagram जोड़ें",
        "suppliers": "सेटअप: जिनसे आप माल खरीदते हैं उन्हें जोड़ें",
        "stock": "सेटअप: बताएँ आपके पास कितना स्टॉक है",
        "part:2": "सेटअप भाग 2: हम आपकी Instagram पोस्ट बनाएँ (लगभग 10 मिनट)",
        "part:3": "सेटअप भाग 3: स्टॉक कभी खत्म न हो (लगभग 5 मिनट)",
    },
}

_LOCK = threading.RLock()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _email(email: str) -> str:
    return (email or "").strip().lower()


# ---------------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------------
def _blank(new_account: bool) -> dict:
    return {"v": VERSION, "created_at": _now(), "lang": "en", "path": None,
            "new_account": bool(new_account), "welcomed_at": None,
            "dismissed_at": None, "skipped": {}, "steps": {}, "parts": {},
            "tasks": {}, "finished_at": None}


def get_record(email: str) -> dict | None:
    rec = user_store.get_key(_email(email), KEY, None)
    return rec if isinstance(rec, dict) and rec.get("v") else None


def _save(email: str, rec: dict) -> None:
    user_store.set_key(_email(email), KEY, rec)
    _forget(email)


def create_for_new_account(email: str) -> dict:
    """Called from sign-up (password and Google). Never overwrites a record."""
    with _LOCK:
        rec = get_record(email)
        if rec:
            return rec
        rec = _blank(new_account=True)
        _save(email, rec)
        return rec


def ensure_record(email: str) -> dict:
    """An existing account opening the journey from its home card."""
    with _LOCK:
        rec = get_record(email)
        if rec:
            return rec
        rec = _blank(new_account=False)
        rec["welcomed_at"] = _now()          # no pop-up: they asked for it
        _save(email, rec)
        return rec


# ---------------------------------------------------------------------------
# the facts every check reads (local stored state only)
# ---------------------------------------------------------------------------
def _safe(fn, default):
    try:
        return fn()
    except Exception:  # noqa: BLE001 - one broken module must not break the journey
        return default


def facts(email: str) -> dict:
    from backend.core import (brandname, commerce, instagram, products,
                              secrets_store, sitebuilder, store_payments, studio,
                              supply)
    email = _email(email)
    prods = _safe(lambda: products.get_products(email), []) or []
    active = [p for p in prods if p.get("status") != "archived"]
    site = _safe(lambda: sitebuilder.get_site(email), {}) or {}
    c = site.get("commerce") or {}
    brand = _safe(lambda: studio.get_brand(email), {}) or {}
    inv = _safe(lambda: supply.get_inventory(email), []) or []
    data = user_store.get_key(email, "smart_data", {}) or {}
    named = _safe(lambda: brandname.resolve(email), {}) or {}
    connectors = [x["id"] for x in _safe(commerce.catalog, [])
                  if _safe(lambda x=x: secrets_store.is_connected(email, x["id"]), False)]
    gateway = _safe(lambda: store_payments.connected(email), False)
    return {
        "shop_name": named.get("name") if named.get("ready") else "",
        "shop_named": bool(named.get("ready")),
        # the raw key, not get_product_type(): that one falls back to a default,
        # and a default is not the seller's answer
        "type_chosen": user_store.get_key(email, "product_type", None) is not None,
        "products": active,
        "active_count": len(active),
        "with_photo": len([p for p in active if p.get("image_url") or (p.get("images") or [])]),
        "site": site,
        "published": bool(site.get("published") and site.get("handle")),
        "upi_ready": store_payments.upi_ready(c),
        "gateway_on": bool(gateway and c.get("online_enabled")),
        "currency": str(c.get("currency") or "INR").upper(),
        "connectors": connectors,
        "sales_in": bool(data.get("sales")),
        "brand_about": bool(str(brand.get("about") or "").strip()),
        "style_count": len([r for r in (brand.get("refs") or []) if r]),
        "instagram": bool(_safe(lambda: instagram.is_connected(email), False)),
        "inventory": inv,
    }


def _stock_done(f: dict) -> bool:
    """Enough products have a stock item with a supplier and delivery days, and
    the shop has told us it holds some stock."""
    linked = [it for it in f["inventory"]
              if str(it.get("supplier_name") or "").strip()
              and float(it.get("lead_time_days") or 0) > 0]
    need = max(1, min(PRODUCTS_NEEDED, f["active_count"]))
    return (len(linked) >= need
            and any(float(it.get("current_stock") or 0) > 0 for it in linked))


def step_done(step: str, f: dict) -> bool:
    need = max(1, min(PRODUCTS_NEEDED, f["active_count"]))
    return {
        "shop": f["shop_named"] and f["type_chosen"],
        "products": f["active_count"] >= PRODUCTS_NEEDED,
        "site": f["published"],
        "payment": f["upi_ready"] or f["gateway_on"],
        "connect": bool(f["connectors"]) or f["sales_in"],
        "catalogue": f["active_count"] >= 1,
        "brand": f["brand_about"],
        "style": f["style_count"] >= STYLE_NEEDED,
        "photos": f["active_count"] >= 1 and f["with_photo"] >= need,
        "instagram": f["instagram"],
        "suppliers": any(str(it.get("supplier_name") or "").strip() for it in f["inventory"]),
        "stock": f["active_count"] >= 1 and _stock_done(f),
    }.get(step, False)


# ---------------------------------------------------------------------------
# progress: the pure read
# ---------------------------------------------------------------------------
def _steps_for(part: int, path: str | None) -> list[str]:
    path = path or "create"
    return [sid for sid, p, paths in STEPS if p == part and path in paths]


def _task_tag(step_or_part) -> str:
    return f"part:{step_or_part}" if isinstance(step_or_part, int) else str(step_or_part)


def progress(email: str, f: dict | None = None) -> dict:
    email = _email(email)
    rec = get_record(email)
    f = f if f is not None else facts(email)
    path = (rec or {}).get("path")
    skipped = (rec or {}).get("skipped") or {}
    parts_rec = (rec or {}).get("parts") or {}

    parts = []
    for n in (1, 2, 3):
        rows = [{"id": sid, "done": step_done(sid, f), "skipped": sid in skipped}
                for sid in _steps_for(n, path)]
        finished_now = all(r["done"] or r["skipped"] for r in rows)
        parts.append({"n": n, "steps": rows, "finished": finished_now,
                      "opened": bool((parts_rec.get(str(n)) or {}).get("opened_at")),
                      "ever_finished": bool((parts_rec.get(str(n)) or {}).get("done_at"))})
    # Guided in order, never locked: once Part 1 has been finished even once,
    # Parts 2 and 3 are both open.
    p1_ever = parts[0]["finished"] or parts[0]["ever_finished"]
    for p in parts:
        p["unlocked"] = p["n"] == 1 or p1_ever

    open_steps = [(p["n"], r["id"]) for p in parts if p["unlocked"]
                  for r in p["steps"] if not (r["done"] or r["skipped"])]
    skipped_left = [r["id"] for p in parts for r in p["steps"]
                    if r["skipped"] and not r["done"]]
    all_rows = [r for p in parts for r in p["steps"]]
    dismissed = bool((rec or {}).get("dismissed_at"))

    # A finished part the seller has not been shown the finish screen for yet.
    unseen_done = [p["n"] for p in parts
                   if p["finished"] and not (parts_rec.get(str(p["n"])) or {}).get("seen_at")
                   and path]

    return {
        "has_record": rec is not None,
        "new_account": bool(rec and rec.get("new_account") and not rec.get("welcomed_at")),
        "path": path,
        "lang": (rec or {}).get("lang") or "en",
        "dismissed": dismissed,
        "active": bool(rec) and not dismissed and bool(open_steps) and bool(path),
        "parts": parts,
        "next": {"part": open_steps[0][0], "step": open_steps[0][1]} if open_steps else None,
        "unseen_done": unseen_done,
        "skipped_left": skipped_left,
        "done_count": len([r for r in all_rows if r["done"]]),
        "total": len(all_rows),
        "needs_sync": _needs_sync(email, rec, parts),
        "finished": bool(path) and all(p["finished"] for p in parts),
    }


def _needs_sync(email: str, rec: dict | None, parts: list[dict]) -> bool:
    """True when reconcile() has something to write: a done time to record, or
    an open journey task whose step or part is now done."""
    if not rec:
        return False
    steps = rec.get("steps") or {}
    for p in parts:
        if p["finished"] and not (rec.get("parts") or {}).get(str(p["n"]), {}).get("done_at"):
            return True
        for r in p["steps"]:
            if r["done"] and not (steps.get(r["id"]) or {}).get("done_at"):
                return True
    if rec.get("tasks"):
        from backend.core import smart
        open_ids = {t["id"] for t in smart.get_tasks(email) if not t.get("done")}
        done = {r["id"] for p in parts for r in p["steps"] if r["done"]}
        finished = {f"part:{p['n']}" for p in parts if p["finished"]}
        for tag, tid in rec["tasks"].items():
            if tid in open_ids and (tag in done or tag in finished):
                return True
    return False


# The home screen reads progress on every load; one page load asks for it from
# /api/smart/state and the ETag fingerprint. A two-second memo makes that one
# computation. Only those two readers use it: the journey's own GET and every
# POST compute fresh and clear it, so a save always shows its result.
_MEMO: dict[str, tuple[float, dict]] = {}
_MEMO_TTL = 2.0


def _forget(email: str) -> None:
    _MEMO.pop(_email(email), None)


def summary(email: str) -> dict:
    email = _email(email)
    hit = _MEMO.get(email)
    if hit and time.monotonic() - hit[0] < _MEMO_TTL:
        return hit[1]
    p = _safe(lambda: progress(email), None)
    if p is None:
        p = {"has_record": False, "active": False, "parts": [], "needs_sync": False}
    if len(_MEMO) > 2000:
        _MEMO.clear()
    _MEMO[email] = (time.monotonic(), p)
    return p


def fingerprint(email: str) -> list:
    """What the home ETag needs: only the step booleans and the switches."""
    p = summary(email)
    return [p.get("path"), p.get("dismissed"), p.get("new_account"),
            [[r["done"], r["skipped"]] for part in p.get("parts") or [] for r in part["steps"]],
            p.get("unseen_done")]


# ---------------------------------------------------------------------------
# reconcile: the only writer of derived state
# ---------------------------------------------------------------------------
def reconcile(email: str) -> dict:
    """Record done times, create the next part's task, tick journey tasks whose
    step or part is now really done. Idempotent; safe to call any time."""
    from backend.core import smart
    email = _email(email)
    with smart.TASK_LOCK, _LOCK:
        rec = get_record(email)
        if not rec:
            return progress(email)
        p = progress(email)
        now = _now()
        changed = False
        steps = rec.setdefault("steps", {})
        parts_rec = rec.setdefault("parts", {})
        for part in p["parts"]:
            for r in part["steps"]:
                if r["done"] and not (steps.get(r["id"]) or {}).get("done_at"):
                    steps.setdefault(r["id"], {})["done_at"] = now
                    changed = True
            if part["finished"] and not (parts_rec.get(str(part["n"])) or {}).get("done_at"):
                parts_rec.setdefault(str(part["n"]), {})["done_at"] = now
                changed = True
                # Finishing a part puts the next one on the task list, so the
                # seller is told there is more, and nothing depends on memory.
                nxt = part["n"] + 1
                while nxt <= 3 and p["parts"][nxt - 1]["finished"]:
                    nxt += 1
                if nxt <= 3:
                    _ensure_task(email, rec, nxt)
        if p["path"] and all(x["finished"] for x in p["parts"]) and not rec.get("finished_at"):
            rec["finished_at"] = now
            changed = True

        # tick journey tasks whose work is done
        done = {r["id"] for part in p["parts"] for r in part["steps"] if r["done"]}
        finished = {f"part:{x['n']}" for x in p["parts"] if x["finished"]}
        tasks = smart.get_tasks(email)
        by_id = {t["id"]: t for t in tasks}
        ticked = False
        for tag, tid in (rec.get("tasks") or {}).items():
            t = by_id.get(tid)
            if t and not t.get("done") and (tag in done or tag in finished):
                t["done"] = True
                ticked = True
        if ticked:
            user_store.set_key(email, "smart_tasks", tasks)
        if changed:
            _save(email, rec)
        _forget(email)
        return progress(email)


def _ensure_task(email: str, rec: dict, step_or_part) -> None:
    """One open task per tag. Reuses the open one; a task the seller ticked or
    deleted themselves is their choice, and a new one is made only when the
    journey asks again (a fresh skip, or a newly finished part)."""
    from backend.core import smart
    tag = _task_tag(step_or_part)
    tid = (rec.get("tasks") or {}).get(tag)
    if tid and any(t["id"] == tid and not t.get("done") for t in smart.get_tasks(email)):
        return
    lang = rec.get("lang") if rec.get("lang") in LANGS else "en"
    text = TASK_TEXT[lang].get(tag) or TASK_TEXT["en"].get(tag) or tag
    ob = f"part:{step_or_part}" if isinstance(step_or_part, int) else f"step:{step_or_part}"
    tasks = smart.add_task(email, text, ob=ob)
    rec.setdefault("tasks", {})[tag] = tasks[-1]["id"]


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
class OnboardingError(ValueError):
    pass


def act(email: str, action: str, **kw) -> dict:
    """Every change the journey makes to its own record. Returns fresh progress."""
    from backend.core import smart
    email = _email(email)
    if action not in ("start", "choose_path", "skip", "open_part", "seen_part_done",
                      "welcomed", "set_lang", "dismiss", "undismiss", "seen_step", "sync"):
        raise OnboardingError("Unknown action.")
    if action == "sync":
        return reconcile(email)
    with smart.TASK_LOCK, _LOCK:
        rec = ensure_record(email) if action == "start" else (get_record(email) or ensure_record(email))
        now = _now()
        if action == "choose_path":
            path = kw.get("path")
            if path not in PATHS:
                raise OnboardingError("Choose create or connect.")
            old = rec.get("path")
            rec["path"] = path
            rec["welcomed_at"] = rec.get("welcomed_at") or now
            if old and old != path:
                # Skip tasks for steps that are not on the new path go away;
                # steps on both paths keep their state. Part 1's done time stays
                # as history and Parts 2 and 3 stay open if it was ever finished.
                gone = {sid for sid, _, paths in STEPS if path not in paths}
                keep_tasks = {}
                for tag, tid in (rec.get("tasks") or {}).items():
                    if tag in gone:
                        smart.delete_task(email, tid)
                        rec.get("skipped", {}).pop(tag, None)
                    else:
                        keep_tasks[tag] = tid
                rec["tasks"] = keep_tasks
        elif action == "skip":
            step = kw.get("step")
            if step not in STEP_IDS:
                raise OnboardingError("Unknown step.")
            # Skipping something already done changes nothing: there is no
            # work to put on the list.
            if not step_done(step, facts(email)):
                rec.setdefault("skipped", {})[step] = now
                _ensure_task(email, rec, step)
        elif action == "open_part":
            n = str(int(kw.get("part") or 1))
            rec.setdefault("parts", {}).setdefault(n, {}).setdefault("opened_at", now)
        elif action == "seen_part_done":
            n = str(int(kw.get("part") or 1))
            rec.setdefault("parts", {}).setdefault(n, {})["seen_at"] = now
        elif action == "seen_step":
            step = kw.get("step")
            if step in STEP_IDS:
                rec.setdefault("steps", {}).setdefault(step, {}).setdefault("first_seen", now)
        elif action == "welcomed":
            rec["welcomed_at"] = rec.get("welcomed_at") or now
        elif action == "set_lang":
            lang = kw.get("lang")
            if lang not in LANGS:
                raise OnboardingError("Language must be en or hi.")
            rec["lang"] = lang
        elif action == "dismiss":
            rec["dismissed_at"] = now
        elif action == "undismiss":
            rec["dismissed_at"] = None
        _save(email, rec)
    return reconcile(email)


# ---------------------------------------------------------------------------
# the journey's own saves (simple screens that write the real data)
# ---------------------------------------------------------------------------
def save_shop(email: str, name: str, product_type: str, label: str = "") -> None:
    """Shop name goes on the site's brand, and on Studio's brand when that is
    empty. What they sell goes where /api/product-type puts it."""
    from backend.core import smart, sitebuilder, studio
    name = " ".join(str(name or "").split())[:60]
    if len(name) < 2:
        raise OnboardingError("Type your shop's name.")
    site = sitebuilder.get_site(email)
    site["brand"] = name
    tr = site.get("trust") or {}
    if not str(tr.get("business_name") or "").strip():
        tr["business_name"] = name
    site["trust"] = tr
    sitebuilder.save_site(email, site)
    brand = studio.get_brand(email) or {}
    if not str(brand.get("name") or "").strip():
        studio.save_brand(email, {"name": name})
    if product_type:
        smart.set_product_type(email, product_type, (label or "").strip() or None)
    _forget(email)


def save_site(email: str, body: dict) -> None:
    """Look, address, WhatsApp, delivery and the legal details the law needs
    before a shop may go live. Only fields that were sent are touched."""
    from backend.core import products, sitebuilder
    site = sitebuilder.get_site(email)
    if body.get("theme"):
        if body["theme"] not in {t["id"] for t in sitebuilder.theme_catalog()}:
            raise OnboardingError("Pick one of the looks shown.")
        site["theme"] = body["theme"]
    if "handle" in body:
        h = sitebuilder.normalise_handle(body.get("handle") or "")
        if len(h) < 3:
            raise OnboardingError("Use at least 3 letters or numbers.")
        if not sitebuilder.handle_available(h, email):
            raise OnboardingError("That address is taken.")
        site["handle"] = h
    if "whatsapp" in body:
        digits = "".join(ch for ch in str(body.get("whatsapp") or "") if ch.isdigit())
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) != 10:
            raise OnboardingError("Enter 10 digits.")
        contact = site.get("contact") or {}
        contact["whatsapp"] = "+91" + digits
        if not contact.get("phone"):
            contact["phone"] = "+91" + digits
        site["contact"] = contact
        tr = site.get("trust") or {}
        if not str(tr.get("support_phone") or "").strip():
            tr["support_phone"] = "+91 " + digits
        site["trust"] = tr
    if "delivery_fee" in body:
        fee = max(0.0, float(body.get("delivery_fee") or 0))
        c = site.get("commerce") or {}
        c["shipping_fee"] = fee
        # "Free" and "this fee on every order" are both taken literally; the
        # site's built-in "free above ₹999" was never something they chose.
        c["free_shipping_above"] = 0.0
        site["commerce"] = c
    if "legal_name" in body or "address" in body:
        tr = site.get("trust") or {}
        who = " ".join(str(body.get("legal_name") or "").split())[:120]
        addr = " ".join(str(body.get("address") or "").split())[:300]
        if len(who) < 2:
            raise OnboardingError("Type your full name.")
        if len(addr) < 8:
            raise OnboardingError("Type your full address.")
        tr["business_name"] = tr.get("business_name") or who
        tr["grievance_name"] = who
        tr["address"] = addr
        tr["support_email"] = tr.get("support_email") or _email(email)
        site["trust"] = tr
    sitebuilder.save_site(email, site)
    if body.get("list_all"):
        for p in products.get_products(email):
            if p.get("status") != "archived" and not p.get("listed"):
                products.upsert_product(email, {**p, "listed": True})
    _forget(email)


def save_payment(email: str, upi_id: str, rupees: bool = False) -> None:
    from backend.core import sitebuilder, store_payments
    clean = store_payments.clean_upi(upi_id)
    if not clean:
        raise OnboardingError("That does not look like a UPI ID. It looks like name@okaxis.")
    site = sitebuilder.get_site(email)
    c = site.get("commerce") or {}
    if str(c.get("currency") or "INR").upper() != "INR":
        if not rupees:
            raise OnboardingError("UPI works only for shops in rupees.")
        c["currency"] = "INR"
    c["upi_id"] = clean
    c["upi_enabled"] = True          # cash on delivery is left exactly as it was
    site["commerce"] = c
    sitebuilder.save_site(email, site)
    _forget(email)


def set_product_photo(email: str, product_id: str, url: str) -> None:
    from backend.core import products
    url = str(url or "").strip()[:500]
    if not url:
        raise OnboardingError("No photo was uploaded.")
    p = products.get_product(email, product_id)
    if not p:
        raise OnboardingError("That product no longer exists.")
    imgs = [u for u in (p.get("images") or []) if u and u != url]
    products.upsert_product(email, {**p, "image_url": url, "images": [url] + imgs})
    _forget(email)


def save_stock(email: str, supplier: dict, counts: dict) -> None:
    """One supplier, and a stock count per product. Each product gets a stock
    item of the same name, linked to it, carrying the supplier and the delivery
    days: exactly what Supply's reorder rule reads (stock lasts less than
    delivery days plus 20%)."""
    from backend.core import products, supply
    name = " ".join(str((supplier or {}).get("name") or "").split())[:120]
    phone = "".join(ch for ch in str((supplier or {}).get("phone") or "") if ch.isdigit() or ch == "+")[:16]
    try:
        days = float((supplier or {}).get("days") or 0)
    except (TypeError, ValueError):
        days = 0
    if len(name) < 2:
        raise OnboardingError("Type your supplier's name.")
    if not 1 <= days <= 120:
        raise OnboardingError("Delivery days must be between 1 and 120.")
    by_id = {p["id"]: p for p in products.get_products(email)}
    inv = {str(it.get("name") or "").strip().lower(): it for it in supply.get_inventory(email)}
    for pid, raw in (counts or {}).items():
        p = by_id.get(pid)
        if not p or p.get("status") == "archived":
            continue
        try:
            n = max(0, int(float(raw)))
        except (TypeError, ValueError):
            continue
        if not p.get("variants"):
            products.upsert_product(email, {**p, "stock": n, "track_stock": True})
        existing = inv.get(p["name"].strip().lower())
        item = {**(existing or {}), "name": p["name"], "current_stock": n,
                "lead_time_days": days, "supplier_name": name, "supplier_phone": phone,
                "unit_label": (existing or {}).get("unit_label") or "unit"}
        if existing:
            item["id"] = existing.get("id")
        before = {it["id"] for it in supply.get_inventory(email)}
        items = supply.upsert_item(email, item)
        saved = (next((it for it in items if it["id"] == item.get("id")), None)
                 if item.get("id") else
                 next((it for it in items if it["id"] not in before), None))
        if saved:
            try:
                supply.upsert_map(email, p["name"], saved["id"], 1)
            except ValueError:
                pass
    _forget(email)


def import_sales_products(email: str) -> int:
    """Connect path: turn product names found in their sales into products.
    Not listed on a One Tap website; that is the seller's choice later."""
    from backend.core import products
    made = 0
    for n in products.unmatched_sales_names(email)[:200]:
        try:
            products.upsert_product(email, {"name": str(n)[:160], "listed": False,
                                            "status": "active", "stock": 0})
            made += 1
        except ValueError:
            continue
    _forget(email)
    return made


def journey_facts(email: str) -> dict:
    """What the screens need beyond progress: names, counts, the shop link."""
    from backend.core import products as _p, sitebuilder
    f = facts(email)
    site = f["site"]
    handle = site.get("handle") or ""
    public = ""
    if handle:
        public = f"/s/{handle}" if sitebuilder.handle_reserved(handle) else f"/{handle}"
    c = site.get("commerce") or {}
    tr = site.get("trust") or {}
    top = []
    orders = customers = 0
    rec = get_record(email) or {}
    try:
        from backend.core import smart
        # Only the connect path's finish screen shows these, and reading the
        # sales file is the one heavy thing here.
        tx = smart.load_sales(email) if rec.get("path") == "connect" and f["sales_in"] else None
        if tx is not None and len(tx):
            top = (tx.groupby("product")["amount"].sum().sort_values(ascending=False)
                   .head(3).index.astype(str).tolist())
            orders = int(tx["order_id"].nunique()) if "order_id" in tx else int(len(tx))
            customers = int(tx["customer_id"].nunique()) if "customer_id" in tx else 0
        else:
            orders = customers = 0
    except Exception:  # noqa: BLE001
        orders = customers = 0
    return {
        "shop_name": f["shop_name"],
        "handle": handle,
        "suggested_handle": handle or sitebuilder.suggest_handle(f["shop_name"] or "", email),
        "public_path": public,
        "published": f["published"],
        "theme": site.get("theme") or "",
        "whatsapp": (site.get("contact") or {}).get("whatsapp") or "",
        "delivery_fee": c.get("shipping_fee"),
        "cod_enabled": bool(c.get("cod_enabled", True)),
        "currency": f["currency"],
        "upi_id": c.get("upi_id") or "",
        "legal_name": tr.get("grievance_name") or "",
        "address": tr.get("address") or "",
        "product_type_chosen": f["type_chosen"],
        "products": [{"id": p["id"], "name": p.get("name"), "price": p.get("price"),
                      "image_url": p.get("image_url") or ((p.get("images") or [None])[0]),
                      "stock": p.get("stock"), "listed": bool(p.get("listed")),
                      "has_variants": bool(p.get("variants"))}
                     for p in f["products"][:60]],
        "unlisted": len([p for p in f["products"] if not p.get("listed")]),
        "unmatched": len(_safe(lambda: _p.unmatched_sales_names(email), [])),
        "style_count": f["style_count"],
        "connectors": f["connectors"],
        "sales_in": f["sales_in"],
        "sales": {"orders": orders, "customers": customers, "top": top},
        "suppliers": sorted({str(it.get("supplier_name") or "").strip()
                             for it in f["inventory"] if str(it.get("supplier_name") or "").strip()}),
    }
