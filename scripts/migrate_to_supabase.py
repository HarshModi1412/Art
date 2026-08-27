"""
One-time migration: local files  ->  Supabase.

Copies your existing accounts, usage logs, purchases, feedback and each user's
saved Smart CafeX data (state.json + the pickled Sales/Review DataFrames) into
Supabase. Idempotent — safe to re-run (rows are upserted).

Prerequisites
-------------
1. Run supabase/schema.sql in your Supabase SQL editor first.
2. Create the private Storage bucket "user-datasets" (the schema tries to; if
   your project blocks that from SQL, make it in Storage -> New bucket).
3. Set the environment variables, then run from the project root:

       export SUPABASE_URL="https://<project>.supabase.co"
       export SUPABASE_SERVICE_KEY="<service_role key>"
       export CS_SECRET_KEY="<a stable Fernet key>"   # recommended
       python -m scripts.migrate_to_supabase

If CAFEX_DATA_DIR points elsewhere, set it too so the script finds your files.
"""
import os
import sys

import pandas as pd

# Ensure the project root is importable when run as a script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core import auth, db, user_store  # noqa: E402


def _data_dir() -> str:
    return auth.BASE_DIR


def migrate_users():
    path = os.path.join(_data_dir(), "user.csv")
    if not os.path.exists(path):
        # also try project root / cwd via auth's finder
        path = auth._find_users_file()
    if not os.path.exists(path):
        print("• users: no user.csv found — skipping")
        return []
    df = pd.read_csv(path)
    if "plan" not in df.columns:
        df["plan"] = "free"
    emails = []
    for _, r in df.iterrows():
        email = str(r["email"]).strip().lower()
        if not email:
            continue
        db.upsert("users", {
            "email": email,
            "password_hash": str(r["password"]).strip(),
            "plan": str(r.get("plan", "free")).strip().lower() or "free",
        }, on_conflict="email")
        emails.append(email)
    print(f"• users: migrated {len(emails)}")
    return emails


def migrate_usage():
    path = os.path.join(_data_dir(), "usage_logs.csv")
    if not os.path.exists(path):
        print("• usage_logs: none — skipping")
        return
    df = pd.read_csv(path)
    n = 0
    for _, r in df.iterrows():
        row = {"email": str(r["email"]).strip().lower(), "feature": str(r["feature"]).strip()}
        ts = r.get("timestamp")
        if pd.notna(ts):
            row["ts"] = str(ts)
        db.insert("usage_logs", row)
        n += 1
    print(f"• usage_logs: migrated {n}")


def migrate_purchases():
    path = os.path.join(_data_dir(), "purchases.csv")
    if not os.path.exists(path):
        print("• purchases: none — skipping")
        return
    df = pd.read_csv(path)
    n = 0
    for _, r in df.iterrows():
        row = {
            "email": str(r["email"]).strip().lower(),
            "product": str(r["product"]).strip(),
            "credits_total": int(r.get("credits_total", 0) or 0),
            "credits_used": int(r.get("credits_used", 0) or 0),
            "amount_inr": int(r.get("amount_inr", 0) or 0),
            "order_id": None if pd.isna(r.get("order_id")) else str(r.get("order_id")),
            "payment_id": None if pd.isna(r.get("payment_id")) else str(r.get("payment_id")),
        }
        created = r.get("created")
        if pd.notna(created):
            row["created"] = str(created)
        db.insert("purchases", row)
        n += 1
    print(f"• purchases: migrated {n}")


def migrate_feedback():
    path = os.path.join(_data_dir(), "feedback.csv")
    if not os.path.exists(path):
        print("• feedback: none — skipping")
        return
    df = pd.read_csv(path)
    n = 0
    for _, r in df.iterrows():
        row = {"email": str(r.get("email", "")).strip().lower(),
               "product": str(r.get("product", "")).strip(),
               "vote": str(r.get("vote", "")).strip()}
        ts = r.get("timestamp")
        if pd.notna(ts):
            row["ts"] = str(ts)
        db.insert("feedback", row)
        n += 1
    print(f"• feedback: migrated {n}")


def migrate_user_data(emails):
    """For each known email, find its user_data/<hash>/ folder and upload
    state.json + every df_*.pkl. Uses user_store.save_df so the DataFrames are
    Fernet-encrypted and _dataset_keys is populated exactly as the app expects."""
    import json

    local_root = os.path.join(_data_dir(), "user_data")
    if not os.path.isdir(local_root):
        print("• user_data: no folder — skipping")
        return

    # hash -> email map for the accounts we know
    by_hash = {user_store._safe(e): e for e in emails}
    seen_hashes = set()

    for email in emails:
        h = user_store._safe(email)
        folder = os.path.join(local_root, h)
        if not os.path.isdir(folder):
            continue
        seen_hashes.add(h)

        # 1) state.json
        state = {}
        sp = os.path.join(folder, "state.json")
        if os.path.exists(sp):
            try:
                with open(sp, encoding="utf-8") as f:
                    state = json.load(f)
            except Exception as e:
                print(f"    ! {email}: could not read state.json ({e})")
        user_store.save_state(email, state or {})

        # 2) each df_<key>.pkl  ->  encrypted blob in Storage
        dfs = 0
        for fn in os.listdir(folder):
            if fn.startswith("df_") and fn.endswith(".pkl"):
                key = fn[3:-4]
                try:
                    df = pd.read_pickle(os.path.join(folder, fn))
                    user_store.save_df(email, key, df)
                    dfs += 1
                except Exception as e:
                    print(f"    ! {email}: could not migrate {fn} ({e})")
        print(f"    - {email}: state + {dfs} dataframe(s)")

    # warn about orphan folders (hash matches no known account)
    for fn in os.listdir(local_root):
        full = os.path.join(local_root, fn)
        if os.path.isdir(full) and fn not in seen_hashes and fn not in by_hash:
            print(f"    ? orphan user_data folder '{fn}' matches no account in user.csv "
                  f"(left untouched)")


def main():
    if not db.SUPABASE_ENABLED:
        print("SUPABASE_URL / SUPABASE_SERVICE_KEY are not set. Nothing to do.")
        print("Set them (and ideally CS_SECRET_KEY) and re-run.")
        sys.exit(1)
    print("Migrating local data -> Supabase ...")
    emails = migrate_users()
    migrate_usage()
    migrate_purchases()
    migrate_feedback()
    migrate_user_data(emails)
    print("Done.")


if __name__ == "__main__":
    main()
