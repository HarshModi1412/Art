"""Is this deployment actually wired up, or quietly running on fallbacks?

WHY THIS EXISTS
---------------
Every optional dependency in this app degrades gracefully, which is right — the
app should not refuse to start because Supabase is unconfigured. But graceful
degradation has a failure mode: a deploy that is missing one table, or a storage
bucket, or a writable disk, works perfectly in testing and then loses the
seller's data on the next redeploy, because the fallback was a local file on a
filesystem Render rebuilds from git.

That has already happened twice on this project. Once when uploads were written
into a gitignored folder inside the repo, so every redeploy deleted all the
seller's images. Once when a column that did not exist was written to the
products table, so every product save 500'd. Both were invisible until a seller
hit them.

This turns "invisible until a seller hits it" into one request. It answers three
questions in the order they bite:

  1. Will the data survive a redeploy?
  2. Which of the SQL files still needs running?
  3. Which features are silently unavailable because a key is missing?

Every check is read-only and wrapped: a health check that throws is worse than no
health check.
"""
from __future__ import annotations

import os

# Every table the app writes to, and which .sql file creates it. Kept as data so
# the answer names the file to run rather than saying "a table is missing".
TABLES = {
    "users": "supabase/schema.sql",
    "sessions": "supabase/schema.sql",
    "usage_logs": "supabase/schema.sql",
    "user_state": "supabase/schema.sql",
    "purchases": "supabase/schema.sql",
    "feedback": "supabase/schema.sql",
    "app_config": "supabase/schema.sql",
    "inventory": "supabase/inventory.sql",
    "product_inventory_map": "supabase/inventory.sql",
    "inventory_waste": "supabase/inventory.sql",
    "purchase_orders": "supabase/inventory.sql",
    "products": "supabase/products.sql",
    "product_aliases": "supabase/products.sql",
    "sites": "supabase/site.sql",
    "media": "supabase/variants.sql",
}

# Which seller-facing capability each key turns on, in the seller's terms rather
# than the vendor's.
CAPABILITIES = [
    ("Drawing pictures", ["OPENAI_API_KEY", "GEMINI_API_KEY", "CF_ACCOUNT_ID", "HF_API_TOKEN"],
     "Sellers can still upload their own photos, and the app says so instead of "
     "promising a picture it cannot draw."),
    ("Reading reference photos", ["GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
                                  "CF_ACCOUNT_ID", "HF_API_TOKEN"],
     "Without one, Product Studio cannot learn a brand's look and every generated "
     "image falls back to a preset."),
    ("Making video clips here", ["GEMINI_API_KEY", "HF_API_TOKEN"],
     "Not a problem: the app hands the seller a prompt and a link to Google Flow, "
     "which is free for about five clips a day and better anyway."),
    ("Sending email", ["SMTP_HOST"],
     "Password reset says honestly that it cannot send, and the morning digest "
     "does not go out. THIS is the one to fix first."),
    ("Telling you about crashes by email", ["OPERATOR_EMAIL"],
     "Failures are still written to the error log and readable at "
     "/api/admin/errors — you just have to go and look."),
    ("Crash reporting to Sentry", ["SENTRY_DSN"], "Optional. The built-in log covers it."),
    ("Admin and recovery endpoints", ["ADMIN_TOKEN"],
     "Without this you cannot read the error log or recover a locked-out seller."),
]


def _table_state() -> dict:
    from backend.core import db
    if not db.SUPABASE_ENABLED:
        return {"mode": "local files", "checked": False, "missing": [], "present": [],
                "note": "No Supabase configured, so everything is stored in local "
                        "files. On Render those are wiped by every redeploy unless "
                        "CAFEX_DATA_DIR points at an attached disk. Fine for trying "
                        "the app out; not fine for a real seller's data."}
    c = db.client()
    if c is None:
        return {"mode": "unknown", "checked": False, "missing": [], "present": [],
                "note": "Supabase is configured but the client would not start."}
    present, missing = [], []
    for table, sql_file in TABLES.items():
        try:
            c.table(table).select("*").limit(1).execute()
            present.append(table)
        except Exception:  # noqa: BLE001 — a missing table is the answer, not an error
            missing.append({"table": table, "run": sql_file})
    return {
        "mode": "Supabase", "checked": True, "present": present, "missing": missing,
        "note": ("Every table is there." if not missing else
                 "Run the .sql files named below in the Supabase SQL editor. They "
                 "are idempotent, so running one twice is safe. Until then those "
                 "features fall back to local files that a redeploy will erase."),
    }


def _storage_state() -> dict:
    from backend.core import auth, db
    out = {"data_dir": auth.BASE_DIR, "writable": False, "durable": False, "note": ""}
    try:
        os.makedirs(auth.BASE_DIR, exist_ok=True)
        probe = os.path.join(auth.BASE_DIR, ".health-probe")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        out["writable"] = True
    except Exception as e:  # noqa: BLE001
        out["note"] = f"Cannot write to the data directory: {e}"
        return out

    # "Durable" means it survives a redeploy. Supabase Storage does. A path inside
    # the checked-out repo does not, whatever the disk says right now.
    inside_repo = os.path.abspath(auth.BASE_DIR).startswith(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    out["durable"] = bool(db.SUPABASE_ENABLED) or not inside_repo
    if not out["durable"]:
        out["note"] = ("Uploads are being written inside the app folder, which Render "
                       "rebuilds from git on every deploy — so every image a seller "
                       "uploads will disappear at the next deploy. Attach a Render "
                       "disk and point CAFEX_DATA_DIR at it, or configure Supabase.")
    return out


def runtime_state() -> dict:
    """The Python version, and whether it is one this app has been run on.

    A REAL OUTAGE, 10 September 2026: Render installs the newest Python when
    nothing pins it, which was 3.14.3. On 3.14, httpcore's synchronous HTTP/2
    backend failed reading from Supabase with "[Errno 11] Resource temporarily
    unavailable", and /api/smart/state returned 500 — the home screen of the live
    app was broken and nothing said so. The version is pinned now, in both
    .python-version and render.yaml, and checked here so a drift shows up in one
    request instead of as a mystery 500 a week later.
    """
    import sys
    v = f"{sys.version_info.major}.{sys.version_info.minor}"
    known_good = ("3.11", "3.12", "3.13")
    return {
        "python": sys.version.split()[0],
        "series": v,
        "supported": v in known_good,
        "known_good": list(known_good),
        "note": ("" if v in known_good else
                 f"Python {v} has not been tested with this app's dependencies. "
                 f"Python 3.14 specifically broke Supabase reads and returned 500 "
                 f"from the home screen. Pin PYTHON_VERSION to 3.12.11 (and keep "
                 f".python-version in the repo)."),
    }


def report() -> dict:
    """One request that says whether this deployment is safe to sell from."""
    tables = _table_state()
    storage = _storage_state()
    runtime = runtime_state()

    caps = []
    for name, keys, consequence in CAPABILITIES:
        have = [k for k in keys if (os.environ.get(k) or "").strip()]
        caps.append({"capability": name, "on": bool(have), "using": have,
                     "needs_one_of": keys, "if_off": consequence})

    blockers, warnings = [], []
    if not runtime["supported"]:
        blockers.append(runtime["note"])
    # Supabase reads degrade rather than 500 now (see db._read), which means a
    # broken connection is survivable AND invisible. This is where it becomes
    # visible again.
    try:
        from backend.core import db
        bad = db.degraded()
    except Exception:  # noqa: BLE001
        bad = {}
    if bad:
        blockers.append(
            f"Supabase reads are currently failing on: {', '.join(sorted(bad))}. "
            f"The app is serving from local fallbacks, so it looks fine and is "
            f"quietly not saving to the database. First failure: "
            f"{list(bad.values())[0]}")
    if not storage["writable"]:
        blockers.append("The data directory is not writable, so nothing can be saved. "
                        + storage["note"])
    if not storage["durable"]:
        blockers.append(storage["note"])
    if tables.get("missing"):
        files = sorted({m["run"] for m in tables["missing"]})
        blockers.append(f"{len(tables['missing'])} Supabase table(s) missing. "
                        f"Run: {', '.join(files)}")
    if tables["mode"] == "local files":
        warnings.append(tables["note"])
    if not (os.environ.get("SMTP_HOST") or "").strip():
        warnings.append("No mail server, so password reset cannot send a link and the "
                        "morning digest will not go out.")
    if not (os.environ.get("ADMIN_TOKEN") or "").strip():
        warnings.append("ADMIN_TOKEN is unset, so you cannot read the error log or "
                        "recover a locked-out seller.")
    if not any(c["on"] for c in caps if c["capability"] == "Drawing pictures"):
        warnings.append("No image AI connected. The app handles this honestly — it "
                        "asks the seller for their own photo — but the headline "
                        "feature is off.")
    launch = (os.environ.get("LAUNCH_MODE") or "").strip().lower() in ("1", "true", "yes", "on")
    if launch:
        warnings.append("LAUNCH_MODE is on, so paid-plan gates are no-ops and every "
                        "account gets everything. The per-day AI caps still apply.")

    return {
        "ok": not blockers,
        "verdict": ("Safe to put a seller on." if not blockers else
                    "Do NOT put a seller on this deployment yet."),
        "blockers": blockers,
        "warnings": warnings,
        "database": tables,
        "degraded_tables": bad,
        "storage": storage,
        "runtime": runtime,
        "capabilities": caps,
        "launch_mode": launch,
    }
