"""
Auth + rate limiting.

Storage backend is pluggable:
  * When Supabase is configured (see backend/core/db.py) accounts, login
    sessions and usage logs live in Supabase — so logins survive restarts and
    rebuilds, and everything is keyed to the account email.
  * Otherwise everything falls back to the original local files
    (user.csv / usage_logs.csv + an in-memory session dict), so the app still
    runs in development with nothing configured.

Public function signatures are unchanged — callers elsewhere in the app don't
need to know which backend is active.

- Users:        email, password (hash), plan
- Usage logs:   email, feature, timestamp — MAX_USAGE uses per calendar day.
"""
import hashlib
import hmac as _hmac
import os
import secrets
from datetime import datetime, timedelta

import pandas as pd

from backend.core import db


# ---------- password hashing ----------
# New passwords are stored as "pbkdf2$<salt>$<hash>" — never plaintext.
# Old plaintext rows still verify (and are silently upgraded to a hash on
# the next successful login), so no existing account breaks.
_HASH_PREFIX = "pbkdf2$"
_PBKDF2_ITERATIONS = 100_000

SESSION_TTL_DAYS = 30


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                 _PBKDF2_ITERATIONS).hex()
    return f"{_HASH_PREFIX}{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith(_HASH_PREFIX):
        try:
            _, salt, digest = stored.split("$", 2)
            calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                       _PBKDF2_ITERATIONS).hex()
            return _hmac.compare_digest(calc, digest)
        except (ValueError, TypeError):
            return False
    return _hmac.compare_digest(stored, password)  # legacy plaintext row


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE_DIR = os.environ.get("CAFEX_DATA_DIR", os.path.join(_ROOT, "data"))


def _find_users_file() -> str:
    """user.csv may live in data/, the project root, or the working dir."""
    candidates = [
        os.path.join(BASE_DIR, "user.csv"),
        os.path.join(_ROOT, "user.csv"),
        os.path.join(os.getcwd(), "user.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


USERS_FILE = _find_users_file()
USAGE_FILE = os.path.join(os.path.dirname(USERS_FILE), "usage_logs.csv")
MAX_USAGE = 5          # free uses per feature per calendar day (resets at midnight)

# token -> email (in-memory session store, used only in local/fallback mode)
_sessions: dict[str, str] = {}


# ---------- users ----------
def users_file_exists() -> bool:
    if db.SUPABASE_ENABLED:
        return True
    return os.path.exists(_find_users_file())


def _read_users_df():
    """Read user.csv, adding the plan column if an older file lacks it. (local mode)"""
    users_file = _find_users_file()
    if not os.path.exists(users_file):
        os.makedirs(os.path.dirname(users_file), exist_ok=True)
        df = pd.DataFrame(columns=["email", "password", "plan"])
        df.to_csv(users_file, index=False)
        return df, users_file
    df = pd.read_csv(users_file)
    if "plan" not in df.columns:
        df["plan"] = "free"
    return df, users_file


def register(email: str, password: str, plan: str = "free") -> None:
    """Create an account. Raises ValueError on invalid input / duplicate."""
    email_clean = (email or "").strip().lower()
    password_clean = (password or "").strip()
    if "@" not in email_clean or "." not in email_clean.split("@")[-1]:
        raise ValueError("Please enter a valid email address")
    if len(password_clean) < 6:
        raise ValueError("Password must be at least 6 characters")
    if plan not in ("free", "pro", "chain"):
        plan = "free"

    if db.SUPABASE_ENABLED:
        if db.fetch_one("users", {"email": email_clean}):
            raise ValueError("An account with this email already exists — just log in from the app")
        db.insert("users", {
            "email": email_clean,
            "password_hash": hash_password(password_clean),
            "plan": plan,
        })
        return

    df, users_file = _read_users_df()
    if email_clean in df["email"].astype(str).str.strip().str.lower().values:
        raise ValueError("An account with this email already exists — just log in from the app")
    df = pd.concat([df, pd.DataFrame([{
        "email": email_clean, "password": hash_password(password_clean), "plan": plan
    }])], ignore_index=True)
    df.to_csv(users_file, index=False)


def get_plan(email: str) -> str:
    email = (email or "").strip().lower()
    if db.SUPABASE_ENABLED:
        row = db.fetch_one("users", {"email": email})
        plan = str((row or {}).get("plan", "free")).strip().lower()
        return plan if plan in ("free", "pro", "chain") else "free"
    df, _ = _read_users_df()
    row = df[df["email"].astype(str).str.strip().str.lower() == email]
    if len(row):
        plan = str(row.iloc[-1].get("plan", "free")).strip().lower()
        return plan if plan in ("free", "pro", "chain") else "free"
    return "free"


def set_plan(email: str, plan: str) -> None:
    email = (email or "").strip().lower()
    if db.SUPABASE_ENABLED:
        db.upsert("users", {"email": email, "plan": plan}, on_conflict="email")
        return
    df, users_file = _read_users_df()
    mask = df["email"].astype(str).str.strip().str.lower() == email
    df.loc[mask, "plan"] = plan
    df.to_csv(users_file, index=False)


def load_users() -> dict:
    """email -> stored password hash."""
    if db.SUPABASE_ENABLED:
        rows = db.fetch_all("users")
        return {
            str(r.get("email", "")).strip().lower(): str(r.get("password_hash", "")).strip()
            for r in rows if r.get("email")
        }
    users_file = _find_users_file()
    if not os.path.exists(users_file):
        return {}
    df = pd.read_csv(users_file)
    if "email" not in df.columns or "password" not in df.columns:
        return {}
    df["email"] = df["email"].astype(str).str.strip().str.lower()
    df["password"] = df["password"].astype(str).str.strip()
    return dict(zip(df["email"], df["password"]))


def _upgrade_plaintext(email_clean: str, pw: str) -> None:
    """Transparently replace a legacy plaintext password row with a hash."""
    new_hash = hash_password(pw)
    if db.SUPABASE_ENABLED:
        db.upsert("users", {"email": email_clean, "password_hash": new_hash}, on_conflict="email")
        return
    df, users_file = _read_users_df()
    mask = df["email"].astype(str).str.strip().str.lower() == email_clean
    df.loc[mask, "password"] = new_hash
    df.to_csv(users_file, index=False)


def login(email: str, password: str) -> str | None:
    """Return a session token on success, None on bad credentials."""
    users = load_users()
    email_clean = (email or "").strip().lower()
    pw = (password or "").strip()
    if email_clean in users and verify_password(pw, users[email_clean]):
        if not users[email_clean].startswith(_HASH_PREFIX):
            _upgrade_plaintext(email_clean, pw)
        token = secrets.token_urlsafe(32)
        if db.SUPABASE_ENABLED:
            th = _token_hash(token)
            expires = (datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)).isoformat()
            db.upsert("sessions", {"token_hash": th, "email": email_clean,
                                   "expires_at": expires}, on_conflict="token_hash")
            db.cache_session(th, email_clean)
        else:
            _sessions[token] = email_clean
        return token
    return None


def logout(token: str) -> None:
    if db.SUPABASE_ENABLED:
        th = _token_hash(token)
        db.delete("sessions", {"token_hash": th})
        db.drop_cached_session(th)
        return
    _sessions.pop(token, None)


def user_from_token(token: str | None) -> str | None:
    if not token:
        return None
    if not db.SUPABASE_ENABLED:
        return _sessions.get(token)

    th = _token_hash(token)
    cached = db.cached_session(th)
    if cached:
        return cached
    row = db.fetch_one("sessions", {"token_hash": th})
    if not row:
        return None
    expires = row.get("expires_at")
    if expires:
        try:
            exp = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if exp.tzinfo is not None:
                exp = exp.replace(tzinfo=None)
            if datetime.utcnow() > exp:
                db.delete("sessions", {"token_hash": th})
                return None
        except (ValueError, TypeError):
            pass
    email = str(row.get("email", "")).strip().lower()
    if email:
        db.cache_session(th, email)
    return email or None


# ---------- rate limiting (per calendar day) ----------
def _init_usage_file() -> None:
    if not os.path.exists(USAGE_FILE):
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        pd.DataFrame(columns=["email", "feature", "timestamp"]).to_csv(USAGE_FILE, index=False)


def _recent_logs(df: pd.DataFrame, email: str, feature: str) -> pd.DataFrame:
    """Rows for this user+feature from TODAY (calendar day). (local mode)"""
    if df.empty:
        return df
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    today = datetime.now().date()
    return df[(df["email"] == email) & (df["feature"] == feature)
              & (df["timestamp"].dt.date == today)]


def _usage_count_today(email: str, feature: str) -> int:
    """Supabase: how many times this feature was used by this email today."""
    c = db.client()
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    res = (c.table("usage_logs").select("id", count="exact")
           .eq("email", email).eq("feature", feature).gte("ts", start).execute())
    if getattr(res, "count", None) is not None:
        return int(res.count)
    return len(res.data or [])


def check_usage_limit(email: str, feature: str) -> bool:
    """Consume one usage credit. Returns False when the limit is hit."""
    if db.SUPABASE_ENABLED:
        if _usage_count_today(email, feature) >= MAX_USAGE:
            return False
        db.insert("usage_logs", {"email": email, "feature": feature})
        return True

    _init_usage_file()
    df = pd.read_csv(USAGE_FILE)
    if len(_recent_logs(df, email, feature)) >= MAX_USAGE:
        return False
    df = pd.concat(
        [df, pd.DataFrame([{"email": email, "feature": feature, "timestamp": datetime.now()}])],
        ignore_index=True,
    )
    df.to_csv(USAGE_FILE, index=False)
    return True


def get_remaining_usage(email: str, feature: str) -> int:
    if db.SUPABASE_ENABLED:
        return max(0, MAX_USAGE - _usage_count_today(email, feature))
    _init_usage_file()
    df = pd.read_csv(USAGE_FILE)
    return MAX_USAGE - len(_recent_logs(df, email, feature))
