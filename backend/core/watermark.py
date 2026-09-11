"""
Watermark remover — every AI picture and clip passes through here before it
is saved against a post.

WHY THIS EXISTS
---------------
The reel route sends a seller to Google Flow (free, ~5 clips a day) and the
clip comes back with the tool's visible mark in a corner. Other tools do the
same: Kling stamps its logo on free clips, some image apps put a sparkle in
the corner. On a shop's own feed that reads as "this came from somewhere
else", which is the opposite of what a brand post is for. So the approval flow
runs every generated image, every clip we generate, and every clip a seller
uploads for a reel through `clean_image()` / `clean_video_bytes()`.

WHAT IT REMOVES, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------
Only the VISIBLE corner mark. Invisible provenance (SynthID, C2PA) is not
something this touches or tries to defeat, and the post keeps its
`image_generated` / AI flag in the app — the seller is still told which
pictures are generated, and should still switch on Instagram's AI label for
photorealistic ones. Flow itself lets a signed-in user turn the visible mark
off (Settings → Media Watermark); this is the safety net for when they did not.

HOW IT FINDS THE MARK
---------------------
Visible marks share three properties, and the detector needs all three before
it touches a pixel:

  1. **Position.** They hug a corner, a small margin in from the edge.
  2. **Look.** Light, low-saturation strokes (white text or a white logo at
     partial opacity) that are brighter than whatever is directly behind them.
  3. **Shape.** Small and stroke-like — text or a glyph, not a solid block, and
     isolated from the rest of the picture rather than part of a bright area.

For a VIDEO there is a much stronger fourth cue: the mark does not move while
the picture behind it does. The detector samples frames across the clip and
keeps only the pixels that are brighter than their surroundings in almost every
frame. A handheld product clip has nothing that behaves like that except the
overlay. When the scene itself is static (a locked-off shot) that cue is
meaningless, so the median frame is judged by the single-image rules instead.

Anything that fails a check is left alone. A missed watermark is an annoyance;
a smudge rubbed into the seller's real product is a lie in their own feed, so
the thresholds lean towards leaving the picture untouched.

HOW IT REMOVES IT
-----------------
OpenCV's Telea inpainting on a small region around the mask (fast — only the
corner is processed). Video frames are inpainted one by one and re-encoded to
H.264 with ffmpeg so the result still plays in every browser; the original
audio track is carried over. Without OpenCV, images fall back to a plain
neighbour-fill in numpy, and videos are returned untouched with the reason.

Nothing here raises. A failure returns the original bytes and a report that
says why, because cleaning is a nicety and must never cost a seller their clip.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile

import numpy as np

log = logging.getLogger("watermark")

# How much of each corner is examined. Every mainstream visible mark sits well
# inside this box; anything larger than a fraction of it is not a watermark.
CORNER_W = 0.28
CORNER_H = 0.18

# Engines known to return pictures with no visible mark. Their output still
# goes through the remover (the rule is "every generated picture"), but with
# stricter limits, so a white stitch near the corner of a re-shoot is safe.
KNOWN_CLEAN_ENGINES = {"openai", "cloudflare", "huggingface"}

# A clip longer than this is not a reel and is not worth re-encoding here.
MAX_VIDEO_FRAMES = 3600          # ~2 minutes at 30fps
SAMPLE_FRAMES = 36


# ---------------------------------------------------------------- helpers
def _cv2():
    try:
        import cv2  # noqa: WPS433 — optional dependency
        return cv2
    except Exception:  # noqa: BLE001
        return None


def ffmpeg_exe() -> str | None:
    """System ffmpeg, or the static binary imageio-ffmpeg ships in its wheel."""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg  # noqa: WPS433
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def capabilities() -> dict:
    """What this server can clean — surfaced so the UI never over-promises."""
    cv = _cv2() is not None
    ff = ffmpeg_exe() is not None
    return {"images": True, "image_method": "opencv" if cv else "basic",
            "videos": cv and ff,
            "video_note": "" if (cv and ff) else
            ("Video cleaning needs OpenCV and ffmpeg on the server "
             "(opencv-python-headless and imageio-ffmpeg in requirements.txt).")}


def _blur(gray: np.ndarray, sigma: float) -> np.ndarray:
    cv2 = _cv2()
    if cv2 is not None:
        return cv2.GaussianBlur(gray, (0, 0), sigmaX=max(0.8, sigma))
    from PIL import Image, ImageFilter
    im = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius=max(0.8, sigma))),
                      dtype=np.float32)


def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
    if r <= 0:
        return mask.copy()
    cv2 = _cv2()
    if cv2 is not None:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        return cv2.dilate(mask.astype(np.uint8), k) > 0
    from scipy import ndimage  # scipy ships with most pandas installs
    return ndimage.binary_dilation(mask, iterations=r)


def _label(mask: np.ndarray):
    """Connected components -> (n, labels, stats[x, y, w, h, area])."""
    cv2 = _cv2()
    if cv2 is not None:
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
        return n, labels, stats
    from scipy import ndimage
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    stats = [[0, 0, mask.shape[1], mask.shape[0], int((labels == 0).sum())]]
    for sl, i in zip(ndimage.find_objects(labels), range(1, n + 1)):
        ys, xs = sl
        stats.append([xs.start, ys.start, xs.stop - xs.start, ys.stop - ys.start,
                      int((labels[sl] == i).sum())])
    return n + 1, labels, np.array(stats)


def _corners(w: int, h: int) -> list[tuple[str, int, int, int, int]]:
    cw, ch = max(24, int(w * CORNER_W)), max(24, int(h * CORNER_H))
    return [("bottom-right", w - cw, h - ch, cw, ch),
            ("bottom-left", 0, h - ch, cw, ch),
            ("top-right", w - cw, 0, cw, ch),
            ("top-left", 0, 0, cw, ch)]


def _saturation(rgb: np.ndarray) -> np.ndarray:
    mx = rgb.max(axis=2).astype(np.float32)
    mn = rgb.min(axis=2).astype(np.float32)
    return (mx - mn) / np.maximum(mx, 1.0)


# ---------------------------------------------------------------- detection
def _accept_group(cand: np.ndarray, box: tuple, W: int, H: int,
                  strict: bool) -> tuple[np.ndarray | None, str]:
    """Given raw candidate pixels in one corner box, decide whether they form a
    watermark and return the (box-local) mask if so. Returns (None, reason)
    when they do not, which is the common case."""
    name, bx, by, bw, bh = box
    raw_area = int(cand.sum())
    min_area = (0.00025 if strict else 0.00012) * W * H
    if raw_area < min_area:
        return None, "nothing mark-like"

    # Join the strokes of one mark (letters of a word, points of a sparkle)
    # into one group, then look at groups rather than single specks.
    join = max(2, int(min(W, H) * 0.008))
    grouped = _dilate(cand, join)
    n, labels, stats = _label(grouped)
    keep = np.zeros_like(cand, dtype=bool)
    edge_gap = max(2, int(min(W, H) * 0.004))
    for i in range(1, n):
        x, y, w, h, _ = [int(v) for v in stats[i]]
        gx0, gy0 = bx + x, by + y
        # Must sit clear of the picture's own border — every real mark has a
        # margin — and must not run off the inner edge of the corner box, or it
        # is part of something bigger than a corner mark.
        if gx0 <= edge_gap or gy0 <= edge_gap or gx0 + w >= W - edge_gap or gy0 + h >= H - edge_gap:
            continue
        if x <= 0 and name.endswith("right"):
            continue
        if x + w >= bw and name.endswith("left"):
            continue
        if y <= 0 and name.startswith("bottom"):
            continue
        if y + h >= bh and name.startswith("top"):
            continue
        # Must hug its corner: the far side of the group sits near the corner.
        near_x = (W - (gx0 + w)) if name.endswith("right") else gx0
        near_y = (H - (gy0 + h)) if name.startswith("bottom") else gy0
        if near_x > 0.10 * W or near_y > 0.09 * H:
            continue
        if w > 0.24 * W or h > 0.11 * H:
            continue
        comp = (labels[y:y + h, x:x + w] == i) & cand[y:y + h, x:x + w]
        area = int(comp.sum())
        if area < min_area * 0.5:
            continue
        fill = area / max(1, w * h)
        # Text and glyphs are strokes. A solid bright block is a highlight, a
        # white product, a sticker — leave it alone.
        if not (0.04 <= fill <= (0.55 if strict else 0.7)):
            continue
        keep[y:y + h, x:x + w] |= comp

    if not keep.any():
        return None, "candidates did not look like a corner mark"
    area = int(keep.sum())
    if area > 0.02 * W * H:
        return None, "too large to be a watermark"
    # Isolation: the ring around the group must not be full of the same kind
    # of pixel. A mark sits on the picture; bright texture IS the picture.
    ys, xs = np.nonzero(keep)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    pad = max(4, int(min(W, H) * 0.02))
    ry0, ry1 = max(0, y0 - pad), min(bh, y1 + pad)
    rx0, rx1 = max(0, x0 - pad), min(bw, x1 + pad)
    ring = cand[ry0:ry1, rx0:rx1].copy()
    ring[y0 - ry0:y1 - ry0, x0 - rx0:x1 - rx0] = False
    ring_area = max(1, (ry1 - ry0) * (rx1 - rx0) - (y1 - y0) * (x1 - x0))
    if ring.sum() / ring_area > (0.06 if strict else 0.12):
        return None, "part of a bright textured area, not an overlay"
    return keep, "ok"


def _image_candidates(rgb: np.ndarray, gray: np.ndarray, strict: bool) -> np.ndarray:
    H, W = gray.shape
    sigma = max(2.5, min(W, H) / 110.0)
    contrast = gray - _blur(gray, sigma)
    sat = _saturation(rgb)
    c_thr, g_thr, s_thr = (22, 165, 0.16) if strict else (16, 120, 0.26)
    return (contrast > c_thr) & (gray > g_thr) & (sat < s_thr)


def detect_image(rgb: np.ndarray, strict: bool = False) -> tuple[np.ndarray, list[dict]]:
    """Full-frame boolean mask of the visible mark(s), plus where they are."""
    H, W = rgb.shape[:2]
    gray = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    cand_full = _image_candidates(rgb, gray, strict)
    mask = np.zeros((H, W), dtype=bool)
    regions = []
    for box in _corners(W, H):
        name, bx, by, bw, bh = box
        local, why = _accept_group(cand_full[by:by + bh, bx:bx + bw], box, W, H, strict)
        if local is None:
            continue
        mask[by:by + bh, bx:bx + bw] |= local
        ys, xs = np.nonzero(local)
        regions.append({"corner": name, "x": int(bx + xs.min()), "y": int(by + ys.min()),
                        "w": int(xs.max() - xs.min() + 1), "h": int(ys.max() - ys.min() + 1)})
    return mask, regions


def detect_video_frames(frames: list[np.ndarray]) -> tuple[np.ndarray, list[dict], str]:
    """Mask of an overlay that stays put while the picture behind it moves.

    `frames` are BGR/RGB uint8 arrays of the same size, sampled across the clip.
    Returns (mask, regions, mode) where mode says which cue decided it."""
    H, W = frames[0].shape[:2]
    mask = np.zeros((H, W), dtype=bool)
    regions: list[dict] = []
    modes = []
    sigma = max(2.5, min(W, H) / 110.0)
    for box in _corners(W, H):
        name, bx, by, bw, bh = box
        stack = np.stack([f[by:by + bh, bx:bx + bw] for f in frames]).astype(np.float32)
        gray = stack @ np.array([0.299, 0.587, 0.114], dtype=np.float32)   # n,h,w
        motion = gray.std(axis=0)
        moving_frac = float((motion > 6.0).mean())
        med_rgb = np.median(stack, axis=0).astype(np.uint8)
        if moving_frac >= 0.18:
            # The strong cue: brighter than its own surroundings in nearly
            # every frame, while the corner around it moves.
            contrast = np.stack([g - _blur(g, sigma) for g in gray])
            persistent = np.percentile(contrast, 20, axis=0) > 8.0
            sat = _saturation(med_rgb)
            steady = motion < np.percentile(motion, 60) + 1e-3
            cand = persistent & (sat < 0.3) & (np.median(gray, axis=0) > 95) & steady
            local, why = _accept_group(cand, box, W, H, strict=False)
            mode = "static-overlay"
        else:
            # Locked-off shot (or a slow pan over something smooth): nothing
            # moves enough for persistence to prove anything, so the median
            # frame is judged as a still, by the same rules as a picture from
            # an unknown source. Video compression softens a thin mark, which
            # is why these are not the strict limits.
            med_gray = np.median(gray, axis=0)
            cand = _image_candidates(med_rgb, med_gray, strict=False)
            local, why = _accept_group(cand, box, W, H, strict=False)
            mode = "still-rules"
        if local is None:
            continue
        modes.append(mode)
        mask[by:by + bh, bx:bx + bw] |= local
        ys, xs = np.nonzero(local)
        regions.append({"corner": name, "x": int(bx + xs.min()), "y": int(by + ys.min()),
                        "w": int(xs.max() - xs.min() + 1), "h": int(ys.max() - ys.min() + 1),
                        "mode": mode})
    return mask, regions, (modes[0] if modes else "")


# ---------------------------------------------------------------- inpainting
def _roi(mask: np.ndarray, pad: int):
    ys, xs = np.nonzero(mask)
    H, W = mask.shape
    return (max(0, ys.min() - pad), min(H, ys.max() + 1 + pad),
            max(0, xs.min() - pad), min(W, xs.max() + 1 + pad))


def _basic_fill(img: np.ndarray, mask: np.ndarray, iters: int = 60) -> np.ndarray:
    """Neighbour-average fill for when OpenCV is not installed. Crude, but
    only ever applied to a mark-sized patch."""
    out = img.astype(np.float32).copy()
    known = ~mask
    out[mask] = 0
    for _ in range(iters):
        acc = np.zeros_like(out)
        cnt = np.zeros(mask.shape, dtype=np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(out, dy, 0), dx, 1)
            k = np.roll(np.roll(known, dy, 0), dx, 1)
            acc += sh * k[..., None]
            cnt += k
        fill = mask & (cnt > 0)
        out[fill] = acc[fill] / cnt[fill][:, None]
        known = known | fill
        if known.all():
            break
    return np.clip(out, 0, 255).astype(np.uint8)


def inpaint(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fill the masked pixels from their surroundings. `img` is uint8 HxWx3."""
    if not mask.any():
        return img
    H, W = mask.shape
    grow = max(2, int(min(H, W) * 0.004))
    m = _dilate(mask, grow)
    pad = max(8, grow * 4)
    y0, y1, x0, x1 = _roi(m, pad)
    patch = np.ascontiguousarray(img[y0:y1, x0:x1])
    mp = m[y0:y1, x0:x1]
    cv2 = _cv2()
    if cv2 is not None:
        fixed = cv2.inpaint(patch, (mp * 255).astype(np.uint8),
                            max(3, grow * 2), cv2.INPAINT_TELEA)
    else:
        fixed = _basic_fill(patch, mp)
    out = img.copy()
    out[y0:y1, x0:x1] = fixed
    return out


# ---------------------------------------------------------------- public: images
def clean_image(data: bytes, source: str = "") -> tuple[bytes, dict]:
    """Remove a visible corner mark from one picture.

    Returns (bytes, report). When nothing is found the ORIGINAL bytes come back
    untouched — no re-encode, no quality loss — and report["removed"] is False.
    """
    report = {"checked": False, "removed": False, "regions": [], "kind": "image",
              "method": "", "reason": ""}
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        fmt = (im.format or "PNG").upper()
        has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
        rgba = im.convert("RGBA") if has_alpha else None
        rgb = np.asarray(im.convert("RGB"))
        report["checked"] = True
        strict = (source or "").lower() in KNOWN_CLEAN_ENGINES
        mask, regions = detect_image(rgb, strict=strict)
        if not regions:
            report["reason"] = "no visible watermark found"
            return data, report
        fixed = inpaint(rgb, mask)
        out_im = Image.fromarray(fixed)
        if rgba is not None:
            out_im.putalpha(rgba.getchannel("A"))
        buf = io.BytesIO()
        if fmt in ("JPEG", "JPG") and rgba is None:
            out_im.save(buf, format="JPEG", quality=95)
        else:
            out_im.save(buf, format="PNG")
        report.update(removed=True, regions=regions,
                      method="opencv-telea" if _cv2() is not None else "basic-fill",
                      reason=f"removed {len(regions)} mark(s)")
        return buf.getvalue(), report
    except Exception as e:  # noqa: BLE001 — cleaning must never cost the picture
        log.warning("image watermark pass failed: %s", e)
        report["reason"] = f"could not check: {e}"
        return data, report


# ---------------------------------------------------------------- public: videos
def _encode_cmd(ff: str, w: int, h: int, fps: float, src: str, dst: str, codec: str) -> list[str]:
    return [ff, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps:.4f}",
            "-i", "-", "-i", src,
            "-map", "0:v:0", "-map", "1:a:0?",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", codec, "-pix_fmt", "yuv420p"]  + (
        ["-preset", "veryfast", "-crf", "20"] if codec == "libx264" else []) + [
            "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k", "-shortest", dst]


def clean_video_file(src: str, dst: str, source: str = "") -> dict:
    """Clean `src` into `dst`. On any failure `dst` is not written and the
    report says why; callers then keep the original."""
    report = {"checked": False, "removed": False, "regions": [], "kind": "video",
              "method": "", "reason": ""}
    cv2 = _cv2()
    ff = ffmpeg_exe()
    if cv2 is None or not ff:
        report["reason"] = capabilities()["video_note"]
        return report
    cap = None
    try:
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            report["reason"] = "could not open the clip"
            return report
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 24.0
        if n > MAX_VIDEO_FRAMES:
            report["reason"] = "clip is longer than a reel — left as it is"
            return report
        # Pass 1: sample frames across the clip for detection.
        step = max(1, (n or SAMPLE_FRAMES) // SAMPLE_FRAMES)
        samples, i = [], 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if i % step == 0:
                samples.append(frame)
            i += 1
        cap.release()
        cap = None
        total = i
        if len(samples) < 3:
            report["reason"] = "too few frames to judge"
            return report
        report["checked"] = True
        # OpenCV decodes to BGR; detection weighs channels as RGB.
        mask, regions, mode = detect_video_frames(
            [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in samples])
        if not regions:
            report["reason"] = "no visible watermark found"
            return report

        # Pass 2: inpaint every frame and pipe it to ffmpeg as H.264.
        h, w = samples[0].shape[:2]
        grow = max(2, int(min(h, w) * 0.004))
        m = _dilate(mask, grow)
        y0, y1, x0, x1 = _roi(m, max(8, grow * 4))
        mroi = (m[y0:y1, x0:x1] * 255).astype(np.uint8)
        radius = max(3, grow * 2)
        last_err = ""
        for codec in ("libx264", "libopenh264"):
            cap = cv2.VideoCapture(src)
            proc = subprocess.Popen(_encode_cmd(ff, w, h, fps, src, dst, codec),
                                    stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    patch = np.ascontiguousarray(frame[y0:y1, x0:x1])
                    frame[y0:y1, x0:x1] = cv2.inpaint(patch, mroi, radius, cv2.INPAINT_TELEA)
                    proc.stdin.write(frame.tobytes())
                proc.stdin.close()
                err = proc.stderr.read().decode(errors="replace")
                rc = proc.wait(timeout=300)
            except (BrokenPipeError, OSError) as e:
                rc, err = 1, str(e)
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
            finally:
                cap.release()
                cap = None
            if rc == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
                report.update(removed=True, regions=regions, method=f"opencv-telea+{codec}",
                              reason=f"removed {len(regions)} mark(s) from {total} frames",
                              mode=mode)
                return report
            last_err = (err or "")[-300:]
        report["reason"] = f"re-encode failed: {last_err}"
        try:
            if os.path.exists(dst):
                os.remove(dst)
        except OSError:
            pass
        return report
    except Exception as e:  # noqa: BLE001
        log.warning("video watermark pass failed: %s", e)
        report["reason"] = f"could not check: {e}"
        return report
    finally:
        if cap is not None:
            cap.release()


def clean_video_bytes(data: bytes, filename_hint: str = "clip.mp4",
                      source: str = "") -> tuple[bytes, dict]:
    """Bytes in, bytes out. The original comes back when nothing was removed."""
    ext = os.path.splitext(filename_hint or "")[1].lower() or ".mp4"
    tmp = tempfile.mkdtemp(prefix="wm_")
    src, dst = os.path.join(tmp, "in" + ext), os.path.join(tmp, "out.mp4")
    try:
        with open(src, "wb") as fh:
            fh.write(data)
        rep = clean_video_file(src, dst, source)
        if rep.get("removed"):
            with open(dst, "rb") as fh:
                return fh.read(), rep
        return data, rep
    except Exception as e:  # noqa: BLE001
        return data, {"checked": False, "removed": False, "kind": "video",
                      "regions": [], "reason": f"could not check: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- public: stored media
def clean_media_url(url: str, email: str = "", source: str = "") -> dict:
    """Clean a file already in the media store and return where the clean copy
    lives. The clean copy is saved under a NEW name, so the original upload is
    kept (a wrong guess can be undone) and no cached copy of the old bytes can
    be served under the new address."""
    from backend.core import media
    import uuid
    name = os.path.basename((url or "").split("?", 1)[0])
    out = {"url": url, "report": {"checked": False, "removed": False,
                                  "reason": "not a stored file"}}
    if not name:
        return out
    got = media.read(name)
    if not got:
        return out
    data, _ctype = got
    if media.is_video(name):
        new, rep = clean_video_bytes(data, name, source)
        ext = ".mp4"
    else:
        new, rep = clean_image(data, source)
        ext = os.path.splitext(name)[1].lower() or ".png"
        if rep.get("removed") and ext not in (".jpg", ".jpeg"):
            ext = ".png"
    out["report"] = rep
    if rep.get("removed") and new is not data:
        saved = media.save(f"{uuid.uuid4().hex}{ext}", new, email)
        out["url"] = saved["url"]
        out["original_url"] = url
    return out
