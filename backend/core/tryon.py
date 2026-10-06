"""
"Wearing it": put the seller's garment on a model, free.

The only way to show a garment truly WORN (cloth following shoulders, arms,
folds) is a virtual try-on model, and those need a GPU. This uses IDM-VTON,
the open try-on model, through its free public Hugging Face Space
(yisol/IDM-VTON, ZeroGPU). No card, no per-image charge.

WHAT TO KNOW BEFORE RELYING ON IT
  * Free GPU time is rationed per account per day. With HF_API_TOKEN (or
    HF_TOKEN) set, the ration is the token owner's; without one it is shared
    by everyone behind the server's IP. A spent ration is reported plainly.
  * It is someone else's public service: it can queue, be slow, or be down.
    Callers fall back to a free scene (mannequin, hanger) for scheduled posts.
  * It is trained on TOPS: t-shirts, shirts, blouses, kurtis, jackets. Dresses
    come out partly right; sarees, lehengas and trousers do not work.
  * One try-on takes 20 to 60 seconds, so results are cached: one garment
    photo on one model is generated once and reused for every post after.
  * The result is a generated picture (the model is AI-made, the garment
    re-rendered), so it carries the "AI generated" label.

TRYON=off switches it off; TRYON_SPACE points at another IDM-VTON Space.
"""
from __future__ import annotations

import io
import logging
import os
import tempfile

from PIL import Image

log = logging.getLogger("tryon")

SPACE = os.environ.get("TRYON_SPACE", "yisol/IDM-VTON")
TIMEOUT = int(os.environ.get("TRYON_TIMEOUT", "180"))


def enabled() -> bool:
    if os.environ.get("TRYON", "on").lower() in ("off", "0", "false"):
        return False
    try:
        import gradio_client  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _token() -> str | None:
    return (os.environ.get("HF_API_TOKEN") or os.environ.get("HF_TOKEN") or "").strip() or None


def garment_card(cut: Image.Image) -> Image.Image:
    """The garment on plain white at 3:4, which is what the model was trained
    on (catalogue product shots). A busy background in the seller's photo
    otherwise leaks into the result."""
    w, h = cut.size
    W = int(max(w * 1.2, h * 1.2 * 3 / 4))
    H = int(W * 4 / 3)
    card = Image.new("RGB", (W, H), (255, 255, 255))
    card.paste(cut, ((W - w) // 2, (H - h) // 2), cut)
    return card


def wear(garment: Image.Image, model_path: str, description: str = "") -> Image.Image:
    """The model at `model_path` wearing `garment` (an RGBA cut-out).

    Raises RuntimeError with a seller-readable reason when it cannot."""
    if not enabled():
        raise RuntimeError("The AI try-on is switched off on this server.")
    from gradio_client import Client, handle_file
    with tempfile.TemporaryDirectory() as d:
        g = os.path.join(d, "garment.jpg")
        garment_card(garment).save(g, quality=95)
        try:
            try:
                client = Client(SPACE, token=_token(), verbose=False)
            except TypeError:                       # older gradio_client
                client = Client(SPACE, hf_token=_token(), verbose=False)
            job = client.submit(
                dict={"background": handle_file(model_path), "layers": [], "composite": None},
                garm_img=handle_file(g), garment_des=(description or "a top")[:120],
                is_checked=True, is_checked_crop=True, denoise_steps=30, seed=42,
                api_name="/tryon")
            out = job.result(timeout=TIMEOUT)
        except Exception as e:  # noqa: BLE001 — the service's own errors are not seller-readable
            msg = str(e).lower()
            log.warning("try-on failed: %s", e)
            if "quota" in msg or ("gpu" in msg and "exceed" in msg):
                raise RuntimeError("The free try-on has used up today's GPU allowance. "
                                   "It resets daily; the mannequin and hanger shots work meanwhile.") from e
            if "timeout" in msg or "timed out" in msg:
                raise RuntimeError("The free try-on service is busy and did not answer in time. "
                                   "Try again in a few minutes.") from e
            raise RuntimeError("The free try-on service could not do this one just now. "
                               "Try again later, or use the mannequin shot.") from e
        path = out[0] if isinstance(out, (list, tuple)) else out
        img = Image.open(path)
        img.load()
        return img.convert("RGB")


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
