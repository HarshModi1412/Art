"""Tell Bing (and through it ChatGPT search), Yandex and Seznam that pages changed.

Run after a deploy that changes a public page:

    python scripts/indexnow_ping.py https://onetapmanager.com

It reads the live /sitemap.xml and the live /indexnow.txt key, so the site must
be deployed with INDEXNOW_KEY set first. It sends only this site's own URLs and
prints what the IndexNow service answered. Nothing else is sent.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.indexnow.org/indexnow"


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "OneTapManager-IndexNow/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def main(base: str) -> int:
    base = base.rstrip("/")
    host = re.sub(r"^https?://", "", base).split("/")[0]
    try:
        key = _get(f"{base}/indexnow.txt").strip()
    except urllib.error.HTTPError as e:
        print(f"{base}/indexnow.txt answered {e.code}. Set INDEXNOW_KEY in Render and deploy first.")
        return 1
    urls = re.findall(r"<loc>([^<]+)</loc>", _get(f"{base}/sitemap.xml"))
    urls = [u for u in urls if u.startswith(base)]
    if not urls:
        print("The sitemap listed no URLs on this host; nothing sent.")
        return 1
    body = json.dumps({"host": host, "key": key, "keyLocation": f"{base}/indexnow.txt",
                       "urlList": urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"IndexNow accepted {len(urls)} URLs (HTTP {r.status}).")
            return 0
    except urllib.error.HTTPError as e:
        meaning = {400: "bad request", 403: "the key did not match /indexnow.txt",
                   422: "a URL does not belong to this host", 429: "too many requests, try later"}
        print(f"IndexNow answered {e.code}: {meaning.get(e.code, 'see indexnow.org/documentation')}.")
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
        print("Usage: python scripts/indexnow_ping.py https://onetapmanager.com")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
