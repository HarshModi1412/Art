"""
Cut the seller's product out of their own photograph, on this server, for free.

WHY THIS EXISTS
---------------
Every AI "re-shoot" redraws the product. Even the best edit call repaints every
pixel, so the bottle in the post is a near-copy of the bottle that ships, not
the bottle itself: a stone moves, the lettering wobbles. Scene templates
(backend/core/scenes.py) take the other road: the product is CUT OUT of the
real photo and placed into a scene, so its pixels are the seller's pixels.
That is only as good as the cut, which is what this module is about.

HOW
---
1. A photo that already has transparency (a PNG cut-out the seller made) is
   used as it is.
2. Otherwise a small open-source salient-object model runs on the CPU with
   onnxruntime. No API, no per-image cost. The model file is downloaded once
   from rembg's public release page into data/models/ and reused.
     * isnet-general-use (Apache-2.0, 170 MB) — clean edges, the default.
     * u2netp (Apache-2.0, 4.6 MB) — rougher, for a server short on memory.
   CUTOUT_MODEL picks one. BRIA's RMBG models are deliberately NOT used:
   their licence forbids commercial use.
3. If neither is available, OpenCV's GrabCut runs seeded from the photo's
   border. Fine on a plain background, poor on a busy one — check() says so.

check() then judges the cut before anything is built on it: a product that runs
off the edge of the frame, is tiny in the shot, or came out ragged would make a
scene that looks fake, and the seller is better served by "retake it like this"
than by a bad picture.
"""
from __future__ import annotations

import io
import logging
import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger("cutout")

MODEL_DIR = Path(os.environ.get("CUTOUT_MODEL_DIR")
                 or Path(__file__).resolve().parents[2] / "data" / "models")
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/{name}.onnx"

# name -> (input side, mean, std). Values follow the models' own training
# preprocessing (the same ones rembg uses).
MODELS = {
    "isnet-general-use": (1024, (0.5, 0.5, 0.5), (1.0, 1.0, 1.0)),
    "u2netp": (320, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
}
DEFAULT_MODEL = "isnet-general-use"

# The cut is made at this size at most. A 4000px phone photo would only make
# the model slower; the scene never uses the product larger than this.
WORK_MAX = 1600

_lock = threading.Lock()
_sessions: dict = {}


def model_name() -> str:
    name = (os.environ.get("CUTOUT_MODEL") or DEFAULT_MODEL).strip()
    return name if name in MODELS else DEFAULT_MODEL


def _model_path(name: str) -> Path | None:
    """The model file, downloading it once if it is not here yet."""
    path = MODEL_DIR / f"{name}.onnx"
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    if os.environ.get("CUTOUT_DOWNLOAD", "on").lower() in ("off", "0", "false"):
        return None
    try:
        import requests
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        with requests.get(MODEL_URL.format(name=name), stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        tmp.replace(path)
        log.info("downloaded cutout model %s (%d bytes)", name, path.stat().st_size)
        return path
    except Exception as e:  # noqa: BLE001 — no network: fall back to GrabCut
        log.warning("could not download cutout model %s: %s", name, e)
        return None


def _session(name: str):
    with _lock:
        if name in _sessions:
            return _sessions[name]
        try:
            import onnxruntime as ort
        except Exception:  # noqa: BLE001
            _sessions[name] = None
            return None
        path = _model_path(name)
        if not path:
            return None          # not cached: a later call may have network again
        opts = ort.SessionOptions()
        # One CPU on the server. More threads only fight each other, and the
        # arena allocator keeps peak buffers around long after the cut is done.
        opts.intra_op_num_threads = int(os.environ.get("CUTOUT_THREADS", "1"))
        opts.enable_cpu_mem_arena = False
        sess = ort.InferenceSession(str(path), sess_options=opts,
                                    providers=["CPUExecutionProvider"])
        _sessions[name] = sess
        return sess


def engine() -> str:
    """Which cutter will run: the model's name, or 'grabcut'."""
    return model_name() if _session(model_name()) is not None else "grabcut"


def _model_mask(rgb: Image.Image, name: str) -> np.ndarray | None:
    sess = _session(name)
    if sess is None:
        return None
    side, mean, std = MODELS[name]
    x = np.asarray(rgb.resize((side, side), Image.LANCZOS), dtype=np.float32)
    x = x / max(float(x.max()), 1e-6)
    x = (x - np.array(mean, np.float32)) / np.array(std, np.float32)
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    lo, hi = float(out.min()), float(out.max())
    out = (out - lo) / max(hi - lo, 1e-6)
    m = Image.fromarray((out * 255).astype(np.uint8)).resize(rgb.size, Image.LANCZOS)
    return np.asarray(m)


def _grabcut_mask(rgb: Image.Image) -> np.ndarray:
    import cv2
    img = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    scale = 640 / max(h, w)
    small = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))
    sh, sw = small.shape[:2]
    mask = np.zeros((sh, sw), np.uint8)
    pad = max(2, int(min(sh, sw) * 0.03))
    rect = (pad, pad, sw - 2 * pad, sh - 2 * pad)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(small, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = cv2.GaussianBlur(fg, (5, 5), 0)
    return cv2.resize(fg, (w, h), interpolation=cv2.INTER_LINEAR)


def _refine(alpha: np.ndarray) -> np.ndarray:
    """Keep the product, drop the specks. The model sometimes keeps a scrap of
    shelf or a reflection as a separate island; anything far smaller than the
    main body goes, and a soft 1px edge stops the cut looking stencilled."""
    import cv2
    hard = (alpha > 127).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(hard, 8)
    if n > 2:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = np.zeros(n, bool)
        keep[1:] = areas >= max(areas.max() * 0.08, 50)
        alpha = np.where(keep[labels] | (hard == 0), alpha, 0).astype(np.uint8)
    # Pull the edge in by a hair: the outermost ring of a cut carries the old
    # background's colour, which is the "halo" that gives a composite away.
    eroded = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.GaussianBlur(eroded, (3, 3), 0)


def cut(data: bytes) -> dict:
    """Return {"image": RGBA PIL image trimmed to the product, "engine", "quality"}.

    Raises ValueError when the bytes are not a picture."""
    try:
        src = Image.open(io.BytesIO(data))
        src.load()
    except Exception as e:  # noqa: BLE001
        raise ValueError("That file is not a picture we can read.") from e
    from PIL import ImageOps
    src = ImageOps.exif_transpose(src)          # phone photos arrive sideways
    src.thumbnail((WORK_MAX, WORK_MAX), Image.LANCZOS)

    used = ""
    if src.mode in ("RGBA", "LA") or (src.mode == "P" and "transparency" in src.info):
        rgba = src.convert("RGBA")
        a = np.asarray(rgba.getchannel("A"))
        # Only a REAL cut-out counts: a PNG with an alpha channel that is
        # opaque everywhere is just a photo saved as PNG.
        if (a < 250).mean() > 0.02:
            alpha, used = a, "own-cutout"
    rgb = src.convert("RGB")
    if not used:
        name = model_name()
        alpha = None
        try:
            alpha = _model_mask(rgb, name)
        except Exception as e:  # noqa: BLE001 — a model failure must not stop the post
            log.warning("cutout model %s failed: %s", name, e)
        used = name
        if alpha is None:
            alpha, used = _grabcut_mask(rgb), "grabcut"
        alpha = _refine(alpha)

    quality = check(alpha, engine=used)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(Image.fromarray(alpha))
    box = Image.fromarray(alpha).point(lambda v: 255 if v > 24 else 0).getbbox()
    if box:
        rgba = rgba.crop(box)
    return {"image": rgba, "engine": used, "quality": quality}


def check(alpha: np.ndarray, engine: str = "") -> dict:
    """Is this cut good enough to put in a scene? {ok, problems[], tip}.

    Every problem is phrased as what the seller can do about it, because the
    answer to a bad cut-out is almost always a better photo, not a retry."""
    h, w = alpha.shape[:2]
    fg = alpha > 127
    area = float(fg.mean())
    problems = []
    if area < 0.015:
        problems.append("We could not find the product in this photo. Fill more "
                        "of the frame with it.")
    elif area > 0.92:
        problems.append("We could not tell the product from its background. "
                        "Shoot it against a plain wall or sheet.")
    else:
        # GrabCut treats the outer 3% of the photo as background by design,
        # so with it the band that shows "touches the edge" sits further in.
        edge = max(2, int(min(h, w) * (0.045 if engine == "grabcut" else 0.01)))
        sides = {"top": fg[:edge].mean(), "bottom": fg[-edge:].mean(),
                 "left": fg[:, :edge].mean(), "right": fg[:, -edge:].mean()}
        # A product resting on the bottom edge is normal. One running off the
        # top or a side is cut off and would look amputated in a scene. (The
        # model's mask also fades at the very border, so one side is enough.)
        if any(v > 0.10 for k, v in sides.items() if k != "bottom"):
            problems.append("The product runs off the edge of the photo. Step back "
                            "so all of it is in the frame.")
        ys, xs = np.where(fg)
        bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        if min(bw, bh) < 220:
            problems.append("The product is small in this photo. Move closer, or "
                            "use a sharper picture.")
        soft = ((alpha > 25) & (alpha < 230)).sum() / max(fg.sum(), 1)
        if soft > (0.45 if engine == "grabcut" else 0.30):
            problems.append("The edges came out unsure, usually a busy background. "
                            "A plain background fixes it.")
    return {"ok": not problems, "problems": problems,
            "tip": ("Best results: product alone, plain background, whole thing "
                    "in frame, daylight from one side.") if problems else "",
            "area": round(area, 3), "engine": engine}
