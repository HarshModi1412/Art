"""One answer to "what is this seller's brand called?".

GATE 1 BLOCKER #2.

The bug, exactly as a seller met it: they signed up as
sunshine.creations1214@gmail.com, generated a win-back campaign, and the
message that came out said

    "Hi Meera, it's been a while since your last order with
     sunshine.creations1214."

That is worse than leaving it blank. It tells the customer the shop does not
know its own name, and it exposes the seller's raw email handle to people who
never had it. One message like that is enough for a seller to stop trusting
everything else the app writes.

The cause was `email.split("@")[0]`, repeated as an inline fallback in five
places, so fixing one left four. There is now exactly one resolver, and it
NEVER invents a name from an email address. If it has no real name it says so,
and the caller's job is to ask for one — which is a two-second form, not a
guess published to customers.

Order of truth:
  1. Product Studio brand name    -- what they typed when setting up content
  2. Storefront brand             -- what shoppers see on their own site
  3. Registered business name     -- from the storefront trust block
  4. nothing                      -- and the UI must ask
"""
from __future__ import annotations

# A handle that looks like an email local part, a phone number, or a bare
# "user123". Never usable as a brand name in front of a customer.
def _looks_like_a_handle(v: str) -> bool:
    """True when this string is an account handle, not a shop name.

    Deliberately narrow. The real defence is that resolve() never derives a
    name from an email address at all — this is only a second net for a value
    that got stored earlier by the old code, or that the seller pasted in by
    mistake. Being narrow matters: "Studio 21" and "Atelier 9" are real brand
    names and must survive.
    """
    s = (v or "").strip()
    if not s:
        return True
    if "@" in s:                                   # an email, whole or partial
        return True
    if not any(c.isalpha() for c in s):            # "9876543210"
        return True
    tail = s.rstrip("0123456789")
    if len(s) - len(tail) >= 4 and " " not in s:   # "harshmodi1214", "creations1214"
        return True
    return False


def resolve(email: str) -> dict:
    """{'name': str, 'source': str, 'ready': bool}.

    `ready` False means: do not put this in front of a customer, ask instead.
    """
    from backend.core import studio, sitebuilder

    tried: list[tuple[str, str]] = []
    try:
        tried.append(("studio", str((studio.get_brand(email) or {}).get("name") or "")))
    except Exception:
        pass
    try:
        site = sitebuilder.get_site(email) or {}
        b = site.get("brand")
        tried.append(("site", str((b.get("name") if isinstance(b, dict) else b) or "")))
        trust = site.get("trust") if isinstance(site.get("trust"), dict) else {}
        tried.append(("business", str((trust or {}).get("business_name") or "")))
    except Exception:
        pass

    for source, value in tried:
        v = (value or "").strip()
        if v and not _looks_like_a_handle(v):
            return {"name": v[:60], "source": source, "ready": True}

    return {"name": "", "source": "", "ready": False}


def name(email: str) -> str:
    """The brand name, or "" — never an email prefix."""
    return resolve(email)["name"]


def require(email: str) -> str:
    """The brand name, or raise so the caller can ask for one.

    Used on the paths that write to a CUSTOMER (campaigns, order emails). A
    clear "add your shop name first" is a five-second fix; a message signed
    with an email handle cannot be taken back.
    """
    r = resolve(email)
    if not r["ready"]:
        raise ValueError(
            "Add your shop name before sending anything to customers — "
            "otherwise the message goes out unsigned. You can set it in "
            "Product Studio (Brand) or in Site Management, and it takes a moment.")
    return r["name"]


# What to show INSIDE the app, where the seller is the only reader and a
# placeholder is honest rather than embarrassing.
def display(email: str) -> str:
    return resolve(email)["name"] or "Your shop"
