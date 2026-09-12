"""
Uploaded media — logos, hero art, hero clips, story stills, lookbook clips and
product photos.

WHY THIS MODULE EXISTS
----------------------
Uploads used to be written to `backend/../data/generated_images/`, i.e. a folder
inside the checked-out repository. On Render that filesystem is rebuilt from git
on every deploy, so every image and video a seller had ever uploaded disappeared
the next time the service restarted — while the site document kept pointing at
`/generated_images/<name>`, leaving broken slots everywhere. That is the bug
behind "the site images all got cleared", and no amount of re-uploading fixes it
because the next deploy wipes them again.

WHERE FILES GO NOW, in order of durability:

  1. **Supabase Storage** (`SUPABASE_URL` + service key configured) — the
     durable copy. Survives redeploys, restarts and moving host entirely. This
     is the one that matters.
  2. **A local cache** under `CAFEX_DATA_DIR` (a mounted Render disk when one
     is attached, otherwise a temp dir). Serves bytes without a round-trip and
     is re-filled from Storage on a miss, so a wiped cache costs latency, never
     data.

The URL a seller's site stores never changes: `/generated_images/<filename>`.
Everything already saved keeps working, and nothing has to be migrated — an old
file still on local disk is served from there and copied up to Storage the first
time it is read, so the estate heals itself as it is used.

If neither is available the write still succeeds locally and the caller is told
the file is not durable, so the UI can say so rather than pretending.
"""
from __future__ import annotations

import logging
import mimetypes
import os

from backend.core import db, user_store

log = logging.getLogger("media")

PREFIX = "media"          # folder inside the Supabase Storage bucket
URL_BASE = "/generated_images"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}

# The old, doomed location. Read from it so nothing already uploaded is lost;
# never write to it.
_LEGACY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "generated_images"))


def cache_dir() -> str:
    """Local cache, under the writable data dir rather than the repo."""
    d = os.path.join(user_store.root(), "media")
    os.makedirs(d, exist_ok=True)
    return d


def durable() -> bool:
    """True when writes reach storage that survives a redeploy."""
    return bool(db.SUPABASE_ENABLED)


def content_type_for(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def is_video(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in VIDEO_EXT


def url_for(filename: str) -> str:
    return f"{URL_BASE}/{filename}"


def _storage_path(filename: str) -> str:
    return f"{PREFIX}/{filename}"


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------
def ensure_bucket() -> dict:
    """Make sure the Storage bucket actually exists.

    Without this, everything looks configured — SUPABASE_URL is set, the client
    connects, `durable()` returns True — and every upload silently fails with a
    404 on a bucket nobody created. The seller only finds out after the next
    deploy, when the local cache is rebuilt empty and the images vanish again.
    That is precisely the failure this whole module was written to end, so the
    bucket is checked rather than assumed."""
    if not durable():
        return {"ok": False, "reason": "Supabase is not configured on this deployment."}
    c = db.client()
    if not c:
        return {"ok": False, "reason": "Supabase client could not be created."}
    try:
        existing = {b.name if hasattr(b, "name") else b.get("name")
                    for b in (c.storage.list_buckets() or [])}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"Could not list buckets: {e}"}
    if db.BUCKET in existing:
        return {"ok": True, "created": False, "bucket": db.BUCKET}
    try:
        c.storage.create_bucket(db.BUCKET, options={"public": False})
        return {"ok": True, "created": True, "bucket": db.BUCKET}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"Bucket '{db.BUCKET}' is missing and could "
                                       f"not be created automatically: {e}"}


def health() -> dict:
    """One honest answer to 'will my images survive the next deploy?'"""
    if not durable():
        return {
            "durable": False,
            "headline": "Uploads will be lost on the next deploy",
            "detail": "This deployment has no Supabase Storage configured, so "
                      "uploaded images and video live only on the server's local "
                      "disk. Render rebuilds that disk from git on every deploy. "
                      "Set SUPABASE_URL and the service key to fix this.",
            "cache_dir": cache_dir(),
        }
    b = ensure_bucket()
    if not b.get("ok"):
        return {"durable": False,
                "headline": "Storage is configured but not working",
                "detail": b.get("reason", ""), "cache_dir": cache_dir()}
    return {"durable": True,
            "headline": "Uploads are safe",
            "detail": f"Images and video are copied to Supabase Storage "
                      f"(bucket '{b['bucket']}') as well as the local cache, so "
                      f"they survive redeploys, restarts and changing host."
                      + (" The bucket was created just now." if b.get("created") else ""),
            "cache_dir": cache_dir()}


def save(filename: str, data: bytes, email: str = "") -> dict:
    """Store one uploaded file. Always writes the local cache; also pushes to
    Supabase Storage when configured. Never raises for a storage failure — a
    seller's upload must not be lost because the bucket had a bad minute."""
    path = os.path.join(cache_dir(), os.path.basename(filename))
    with open(path, "wb") as fh:
        fh.write(data)

    stored = False
    if durable():
        try:
            stored = bool(db.upload_blob(_storage_path(filename), data,
                                         content_type_for(filename)))
        except Exception as e:  # noqa: BLE001
            log.warning("media upload to storage failed for %s: %s", filename, e)
        if stored:
            try:
                db.upsert("media", {
                    "id": filename, "email": (email or "").strip().lower(),
                    "kind": "video" if is_video(filename) else "image",
                    "content_type": content_type_for(filename),
                    "bytes": len(data),
                }, on_conflict="id")
            except Exception:  # noqa: BLE001 — the index is a convenience, not the file
                pass

    return {"url": url_for(filename), "filename": filename,
            "durable": stored,
            "warning": "" if stored or not durable() else
                       "Saved, but the durable copy failed — re-upload if it disappears."}


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------
def _local_hit(filename: str) -> str | None:
    for base in (cache_dir(), _LEGACY_DIR):
        p = os.path.join(base, filename)
        if os.path.isfile(p):
            return p
    return None


def local_path(filename: str) -> str | None:
    """A path on this box, fetching from Storage into the cache if needed.

    Serving from a path lets the web server stream the file (sendfile) instead
    of the app reading every byte into memory on every request — which is what
    it was doing for every photo on every storefront page.
    """
    filename = os.path.basename(filename or "")
    if not filename:
        return None
    hit = _local_hit(filename)
    if hit:
        if durable() and os.path.dirname(hit) == _LEGACY_DIR:
            read(filename)          # rescues it into storage + cache
            hit = _local_hit(filename) or hit
        return hit
    got = read(filename)            # pulls from storage and fills the cache
    if not got:
        return None
    return _local_hit(filename)


def read(filename: str) -> tuple[bytes, str] | None:
    """Bytes + content type for one file, or None. Order: local cache, the old
    repo folder, then Storage. A file found only in the old folder is copied up
    to Storage on the way past, so the estate heals as it is used."""
    filename = os.path.basename(filename or "")
    if not filename:
        return None
    ctype = content_type_for(filename)

    local = _local_hit(filename)
    if local:
        with open(local, "rb") as fh:
            data = fh.read()
        # rescue anything still living only in the repo folder
        if durable() and os.path.dirname(local) == _LEGACY_DIR:
            try:
                if db.upload_blob(_storage_path(filename), data, ctype):
                    with open(os.path.join(cache_dir(), filename), "wb") as out:
                        out.write(data)
                    log.info("rescued %s from the old repo folder into storage", filename)
            except Exception:  # noqa: BLE001
                pass
        return data, ctype

    if durable():
        try:
            data = db.download_blob(_storage_path(filename))
        except Exception as e:  # noqa: BLE001
            log.warning("media download failed for %s: %s", filename, e)
            data = None
        if data:
            try:                     # fill the cache for next time
                with open(os.path.join(cache_dir(), filename), "wb") as out:
                    out.write(data)
            except OSError:
                pass
            return data, ctype
    return None


def exists(filename: str) -> bool:
    return read(filename) is not None


def delete(filename: str) -> None:
    filename = os.path.basename(filename or "")
    for base in (cache_dir(),):
        p = os.path.join(base, filename)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
    if durable():
        try:
            db.remove_blob(_storage_path(filename))
            db.delete("media", {"id": filename})
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# migration helper
# ---------------------------------------------------------------------------
def backfill() -> dict:
    """Push every file still sitting only in the old repo folder up to Storage.

    Idempotent, and safe to call on boot: it is the one-shot rescue for media
    uploaded before this module existed and not yet wiped by a redeploy.
    """
    if not durable():
        return {"ran": False, "reason": "no durable storage configured"}
    if not os.path.isdir(_LEGACY_DIR):
        return {"ran": True, "moved": 0, "reason": "nothing in the old folder"}
    moved, failed = 0, 0
    for name in sorted(os.listdir(_LEGACY_DIR)):
        src = os.path.join(_LEGACY_DIR, name)
        if not os.path.isfile(src):
            continue
        try:
            with open(src, "rb") as fh:
                data = fh.read()
            if db.upload_blob(_storage_path(name), data, content_type_for(name)):
                moved += 1
            else:
                failed += 1
        except Exception:  # noqa: BLE001
            failed += 1
    return {"ran": True, "moved": moved, "failed": failed}


# ---------------------------------------------------------------------------
# Making a picture Instagram will actually accept
# ---------------------------------------------------------------------------
# THE BUG THIS FIXES, and it is a big one: every picture this app generates is
# saved as PNG (studio.py, content_gen.py), and Meta's content-publishing
# documentation is unambiguous — "JPEG is the only image format supported."
# A PNG is refused at container creation with error subcode 2207005 before the
# post exists, so EVERY scheduled photo post would have failed, on every
# account, forever, with an error nobody would have connected to the file
# format.
#
# The PNG is left exactly where it is: the storefront, the editor and every
# saved URL still use it, and rewriting those would break links that are
# already out in the world. What happens instead is that a JPEG twin is made
# the first time a picture is published, cached beside the original, and it is
# that twin's URL that Instagram is given.
#
# The other three rules are enforced in the same pass, because each of them is
# its own silent rejection:
#   * aspect ratio must sit between 4:5 and 1.91:1   (subcode 2207009)
#   * width between 320 and 1440                     (subcode 36001)
#   * under 8 MB                                     (subcode 2207004)
IG_MIN_RATIO = 4 / 5          # 0.8  — taller than this is refused
IG_MAX_RATIO = 1.91           #      — wider than this is refused
IG_MIN_WIDTH = 320
IG_MAX_WIDTH = 1440
IG_MAX_BYTES = 8 * 1024 * 1024
_IG_SUFFIX = "_ig.jpg"


def _fit_for_instagram(img):
    """Pad (never crop) into a ratio Instagram accepts, then size it.

    PADDING, NOT CROPPING, on purpose. These are product photographs. A crop
    that satisfies Instagram by removing the top of a kurta has published the
    wrong picture, and the seller finds out from a customer. Bars in a sampled
    background colour are honest and look deliberate."""
    from PIL import Image

    if img.mode != "RGB":
        # JPEG has no alpha. Flattening onto white rather than black, because a
        # transparent product cut-out on black looks like a mistake.
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg

    w, h = img.size
    ratio = w / h if h else 1.0
    if ratio < IG_MIN_RATIO or ratio > IG_MAX_RATIO:
        target = min(max(ratio, IG_MIN_RATIO), IG_MAX_RATIO)
        if ratio < target:                      # too tall -> widen
            new_w, new_h = int(round(h * target)), h
        else:                                   # too wide -> heighten
            new_w, new_h = w, int(round(w / target))
        # The corner pixel is the most reliable cheap read of the backdrop.
        canvas = Image.new("RGB", (new_w, new_h), img.getpixel((0, 0)))
        canvas.paste(img, ((new_w - w) // 2, (new_h - h) // 2))
        img = canvas
        w, h = img.size

    if w > IG_MAX_WIDTH:
        img = img.resize((IG_MAX_WIDTH, max(1, int(round(h * IG_MAX_WIDTH / w)))),
                         Image.LANCZOS)
    elif w < IG_MIN_WIDTH:
        img = img.resize((IG_MIN_WIDTH, max(1, int(round(h * IG_MIN_WIDTH / w)))),
                         Image.LANCZOS)
    return img


def instagram_jpeg(filename: str, email: str = "") -> str:
    """The filename of a JPEG twin Instagram will accept, or "" if it cannot
    be made. Cached — built once, then reused on every later publish."""
    import io

    name = str(filename or "").strip()
    if not name or is_video(name):
        return ""
    if name.lower().endswith(_IG_SUFFIX):
        return name                               # already a twin

    stem = os.path.splitext(os.path.basename(name))[0]
    twin = f"{stem}{_IG_SUFFIX}"
    if local_path(twin):
        return twin
    try:
        got = read(name)
        if not got:
            return ""
        from PIL import Image
        img = _fit_for_instagram(Image.open(io.BytesIO(got[0])))
        buf = io.BytesIO()
        quality = 88
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        # 8 MB is generous for a 1440px photo, but a noisy one can exceed it.
        while buf.tell() > IG_MAX_BYTES and quality > 55:
            quality -= 10
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() > IG_MAX_BYTES:
            return ""
        save(twin, buf.getvalue(), email)
        return twin
    except Exception:  # noqa: BLE001 — a conversion problem must not crash a post
        return ""


_IG_MP4_SUFFIX = "_ig.mp4"


def instagram_mp4(filename: str, email: str = "") -> tuple[str, dict]:
    """(filename Instagram will accept, report). The same twin idea as
    `instagram_jpeg`, for clips.

    A clip only gets re-encoded when the probe says Instagram would refuse it.
    Re-encoding a good file would cost a minute of CPU, lose a generation of
    quality, and change nothing — so a clip that is already H.264/AAC/MP4 with
    its metadata at the front is sent exactly as it is."""
    import os
    import tempfile

    from backend.core import videotools

    name = str(filename or "").strip()
    if not name or not is_video(name):
        return name, {}
    if name.lower().endswith(_IG_MP4_SUFFIX):
        return name, {}

    src = local_path(name)
    if not src:
        got = read(name)
        if not got:
            return name, {}
        tmpdir = tempfile.mkdtemp(prefix="igmp4_")
        src = os.path.join(tmpdir, os.path.basename(name))
        with open(src, "wb") as fh:
            fh.write(got[0])

    report = videotools.reel_report(src)
    if report.get("ok") or report.get("unknown"):
        return name, report                      # nothing to fix
    if not report.get("fixable"):
        return name, report                      # too long, or too short — say so

    stem = os.path.splitext(os.path.basename(name))[0]
    twin = f"{stem}{_IG_MP4_SUFFIX}"
    if local_path(twin):
        return twin, report
    out = os.path.join(tempfile.mkdtemp(prefix="igmp4_"), twin)
    res = videotools.make_reel_ready(src, out)
    if not res.get("ok"):
        return name, {**report, "convert_error": res.get("error", "")}
    try:
        with open(out, "rb") as fh:
            save(twin, fh.read(), email)
    except Exception:  # noqa: BLE001
        return name, report
    return twin, {**report, "converted": True}
