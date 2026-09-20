#!/usr/bin/env python3
"""
collect_instagram_prospects.py
Build a verified list of Indian D2C Instagram sellers to approach for One Tap Manager.

WHY A SCRIPT AND NOT A READY LIST: Instagram needs a logged-in session for
profile/post data and blocks unauthenticated scraping, and the assistant's cloud
sandbox is network-blocked from instagram.com. So the list is built HERE, on a
machine that can reach Instagram, using your own access. Run it, then paste the
CSV into the Tracker sheet of otm-instagram-prospecting.xlsx.

TWO BACKENDS
------------
A) Apify (recommended — reliable, handles anti-bot, no IG password needed):
     pip install apify-client openpyxl
     export APIFY_TOKEN=apify_api_xxx      # apify.com, free tier covers a first run
     python collect_instagram_prospects.py --backend apify --max 100

B) instaloader (uses YOUR logged-in session; go slow to keep the account safe):
     pip install instaloader openpyxl
     instaloader --login YOUR_IG_USERNAME     # once, creates a session file
     python collect_instagram_prospects.py --backend instaloader --login YOUR_IG_USERNAME --max 100

QUALIFICATION (both gates must pass):
  1. Alive     -> newest post <= --max-age-days (default 30)
  2. Size band -> --min-followers .. --max-followers (default 1000..60000)
  Website is CLASSIFIED, not required: none / linktree / basic / full-store.

Compliance: automated scraping is against Instagram's Terms. Keep volumes low,
respect rate limits, target business accounts only. This is a lead-research aid.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, os, re, sys, time

# Seed hashtags drawn from the ICP in Brand.md (order-signal + niche + city).
SEED_TAGS = [
    "dmtoorder", "whatsapptoorder", "shoponinstagram", "codavailable",
    "boutiqueindia", "kurti", "sareelove", "oxidisedjewellery", "imitationjewellery",
    "handmadejewellery", "attar", "perfumeindia", "candlesindia", "smallbusinessindia",
    "suratboutique", "jaipurjewellery", "ahmedabadboutique", "lucknowchikankari",
]
ORDER_SIGNALS = re.compile(r"(dm to order|dm for order|whatsapp|wa\.me|order on whatsapp|"
                           r"cod available|ships? all over india|price in dm|book your order)", re.I)
FULL_STORE = re.compile(r"(myshopify\.com|/products/|dukaan|mydukaan|instamojo|razorpay\.me|"
                        r"shopify|wixsite|/shop|store\.)", re.I)
LINKTREE = re.compile(r"(linktr\.ee|beacons\.ai|bio\.link|linkin\.bio|wa\.me|instagram\.com)", re.I)

COLUMNS = ["#", "Handle (@)", "Profile URL", "Niche", "City / region", "Followers",
           "Last post date", "Active (<=30d)", "Has website?", "Website type",
           "Website URL", "Order method", "Fit 1-3", "Why a fit", "Outreach note",
           "Status", "Date contacted"]


def classify_site(url: str, biography: str) -> tuple[str, str]:
    """Return (has_website, website_type)."""
    u = (url or "").strip()
    if not u:
        # a wa.me / linktree sometimes lives in the bio text, not the link field
        m = re.search(r"(https?://\S+|linktr\.ee/\S+|wa\.me/\S+)", biography or "")
        u = m.group(0) if m else ""
    if not u:
        return "No", "None"
    if FULL_STORE.search(u):
        return "Full store", u
    if LINKTREE.search(u):
        return "Linktree", u
    return "Basic", u  # some other domain -> basic site


def order_method(biography: str, ext: str) -> str:
    bits = []
    if re.search(r"whatsapp|wa\.me", (biography or "") + (ext or ""), re.I): bits.append("WhatsApp")
    if re.search(r"dm to order|dm for order|price in dm", biography or "", re.I): bits.append("DM")
    if FULL_STORE.search(ext or ""): bits.append("Site")
    return " + ".join(dict.fromkeys(bits)) or "DM (assumed)"


def score(has_site: str, method: str, followers: int) -> tuple[int, str]:
    if has_site in ("No", "Linktree") and "DM" in method or "WhatsApp" in method:
        return 3, "Solo seller, orders via DM/WhatsApp, no real store — core fit"
    if has_site == "Basic":
        return 2, "Sells online on a basic site — back-office + posts are the gap"
    if has_site == "Full store":
        return 1, "Has a full store already — pitch the doing (reorders, win-back, posts)"
    return 2, "Active seller — worth a look"


def make_row(idx, username, followers, last_post, biography, ext_url):
    age_days = (dt.date.today() - last_post).days if last_post else 9999
    has_site, site_url = classify_site(ext_url, biography)
    method = order_method(biography, ext_url + " " + (biography or ""))
    fit, why = score(has_site, method, followers)
    note = ("Lead with free analytics + your own website, no badge"
            if has_site in ("No", "Linktree")
            else "Lead with the doing: reorders, win-back and a week of posts, one flat price")
    return [idx, "@" + username, f"https://instagram.com/{username}", "", "",
            f"{followers:,}", last_post.strftime("%d %b %Y") if last_post else "?",
            "Yes" if age_days <= 30 else "No", has_site, has_site, site_url, method,
            fit, why, note, "To contact", ""]


# ---------------------------------------------------------------- Apify backend
def run_apify(tags, max_n, max_age, lo, hi, token):
    from apify_client import ApifyClient
    client = ApifyClient(token)
    # 1) collect candidate usernames from hashtags
    usernames: set[str] = set()
    for tag in tags:
        run = client.actor("apify/instagram-hashtag-scraper").call(run_input={
            "hashtags": [tag], "resultsLimit": 60})
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            u = item.get("ownerUsername") or (item.get("owner") or {}).get("username")
            if u:
                usernames.add(u)
        if len(usernames) >= max_n * 4:
            break
        time.sleep(1)
    # 2) fetch profile details for each candidate
    usernames = list(usernames)[: max_n * 4]
    run = client.actor("apify/instagram-profile-scraper").call(run_input={"usernames": usernames})
    rows, idx = [], 1
    for p in client.dataset(run["defaultDatasetId"]).iterate_items():
        followers = int(p.get("followersCount") or 0)
        if not (lo <= followers <= hi):
            continue
        posts = p.get("latestPosts") or []
        ts = None
        for post in posts:
            t = post.get("timestamp") or post.get("takenAt")
            if t:
                try:
                    ts = dt.datetime.fromisoformat(str(t).replace("Z", "+00:00")).date(); break
                except Exception:
                    pass
        if ts and (dt.date.today() - ts).days > max_age:
            continue
        rows.append(make_row(idx, p.get("username", ""), followers, ts,
                             p.get("biography", ""), p.get("externalUrl") or p.get("externalUrls", [""])[0] if p.get("externalUrls") else p.get("externalUrl", "")))
        idx += 1
        if len(rows) >= max_n:
            break
    return rows


# ---------------------------------------------------------------- instaloader backend
def run_instaloader(tags, max_n, max_age, lo, hi, login):
    import instaloader
    L = instaloader.Instaloader(download_pictures=False, download_videos=False,
                                download_comments=False, save_metadata=False, quiet=True)
    try:
        L.load_session_from_file(login)
    except Exception:
        print("Log in first:  instaloader --login", login); sys.exit(1)
    seen, rows, idx = set(), [], 1
    cutoff = dt.date.today() - dt.timedelta(days=max_age)
    for tag in tags:
        try:
            for post in instaloader.Hashtag.from_name(L.context, tag).get_posts():
                u = post.owner_username
                if u in seen:
                    continue
                seen.add(u)
                try:
                    prof = instaloader.Profile.from_username(L.context, u)
                except Exception:
                    continue
                f = prof.followers
                if not (lo <= f <= hi):
                    continue
                last = prof.get_posts()
                try:
                    newest = next(last).date_utc.date()
                except StopIteration:
                    continue
                if newest < cutoff:
                    continue
                rows.append(make_row(idx, u, f, newest, prof.biography, prof.external_url or ""))
                idx += 1
                print(f"  [{idx-1}] @{u}  {f} followers  last {newest}")
                time.sleep(3)  # be gentle
                if len(rows) >= max_n:
                    return rows
        except Exception as e:
            print("tag", tag, "->", e)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["apify", "instaloader"], default="apify")
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--max-age-days", type=int, default=30)
    ap.add_argument("--min-followers", type=int, default=1000)
    ap.add_argument("--max-followers", type=int, default=60000)
    ap.add_argument("--login", default="", help="instaloader IG username (session)")
    ap.add_argument("--tags", default="", help="comma-separated hashtags to override the seeds")
    ap.add_argument("--out", default="prospects.csv")
    a = ap.parse_args()
    tags = [t.strip() for t in a.tags.split(",") if t.strip()] or SEED_TAGS

    if a.backend == "apify":
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            sys.exit("Set APIFY_TOKEN (apify.com). Or use --backend instaloader --login <ig_user>.")
        rows = run_apify(tags, a.max, a.max_age_days, a.min_followers, a.max_followers, token)
    else:
        if not a.login:
            sys.exit("Pass --login <ig_username> (run `instaloader --login <ig_username>` once first).")
        rows = run_instaloader(tags, a.max, a.max_age_days, a.min_followers, a.max_followers, a.login)

    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(COLUMNS); w.writerows(rows)
    print(f"\nWrote {len(rows)} qualified prospects to {a.out}")
    print("Paste rows into the Tracker sheet of otm-instagram-prospecting.xlsx.")


if __name__ == "__main__":
    main()
