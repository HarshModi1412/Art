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
