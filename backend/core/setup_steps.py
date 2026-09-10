"""What the seller still has to do, in the order that pays off soonest.

WHY THIS EXISTS
---------------
The home screen shows a Today strip, a data section, a platform strip, twelve
app tiles and a task list. Every one of those earned its place for a seller who
already has data in the system. For a seller on their first morning it is a wall,
and the one thing they actually need to do — upload a sales file — has the same
visual weight as "Position Strategy + AI".

This turns that into a single answer to "what do I do now?". Four rules it
follows, all learned the hard way from onboarding flows that get abandoned:

  * Ordered by payoff, not by how the code is organised. Sales data first,
    because every number in the app comes from it.
  * Each step says what the seller GETS, not what the software needs. "So we can
    tell you which products actually make you money" beats "Required for
    analytics".
  * It disappears when it is done. A permanent checklist becomes furniture.
  * Nothing here blocks anything. A seller who wants to go straight to the
    website builder can; this is a suggestion, not a gate.
"""
from __future__ import annotations


def progress(email: str) -> dict:
    from backend.core import smart, products, studio, sitebuilder, brandname

    data = smart.data_status(email) or {}
    sales_ready = bool((data.get("sales") or {}).get("ready"))
    sales_rows = int((data.get("sales") or {}).get("rows") or 0)

    try:
        catalogue = products.get_products(email) or []
    except Exception:
        catalogue = []
    try:
        brand = studio.get_brand(email) or {}
    except Exception:
        brand = {}
    try:
        site = sitebuilder.get_site(email) or {}
    except Exception:
        site = {}

    named = brandname.resolve(email)
    refs = len(brand.get("refs") or [])
    published = bool(site.get("published") or site.get("live"))

    steps = [
        {"id": "sales", "title": "Add your sales file",
         "why": "Every number in this app comes from it — what sells, what earns, "
                "who is slipping away. One CSV or Excel export from wherever you "
                "sell is enough.",
         "done": sales_ready, "action": "upload_sales", "action_label": "Upload it",
         "minutes": 2},
        {"id": "brand", "title": "Name your shop",
         "why": "It goes on your invoices, your website and every message a "
                "customer gets. Until it is set we will not send anything out "
                "signed with a guess.",
         "done": named["ready"], "action": "set_brand", "action_label": "Add the name",
         "minutes": 1},
        {"id": "products", "title": "List what you sell",
         "why": "So sales from Amazon, your own site and everywhere else roll up "
                "to the same product instead of looking like three products.",
         "done": len(catalogue) > 0, "action": "open_products",
         "action_label": "Add products", "minutes": 5},
        {"id": "photos", "title": "Show us your style",
         "why": "Upload five photos you are proud of. We read your lighting, "
                "colours and framing out of them, and then everything we make "
                "for you looks like your brand instead of like stock.",
         "done": refs >= 3, "action": "open_studio", "action_label": "Upload photos",
         "minutes": 4},
        {"id": "site", "title": "Put your shop online",
         "why": "Your own selling website, with your products already on it. "
                "No commission on anything it sells.",
         "done": published, "action": "open_site", "action_label": "Build it",
         "minutes": 10},
    ]

    done = [s for s in steps if s["done"]]
    todo = [s for s in steps if not s["done"]]
    return {
        "steps": steps,
        "done": len(done),
        "total": len(steps),
        "complete": not todo,
        # The ONE thing to do next. Everything else on the home screen can wait.
        "next": todo[0] if todo else None,
        "sales_rows": sales_rows,
    }
