"""
A free product reel from one photograph: no video AI, no per-clip cost.

An image-to-video model animates the product, and the product drifts: by the
third second the label has melted. This moves the CAMERA instead and never
redraws the product. The layers composite.place() returns are animated
separately, which is what makes it read as a shot rather than a zooming JPEG:

  * the set pushes in slowly (6%), the product and its shadow faster (12%),
    both around the point where the product meets the floor, so the two layers
    separate in depth (parallax) without the product ever sliding off its
    shadow;
  * halfway through, a soft band of light sweeps across the product only,
    the "shine" pass of a studio product film.

Output is a 1080x1920 H.264 MP4 with a silent audio track (some apps refuse a
clip with no audio stream at all), encoded by the ffmpeg the server already
ships for the AI label. Frames are streamed straight into ffmpeg, so memory
stays flat however long the clip is.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image

log = logging.getLogger("motion")


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def _zoom(img: Image.Image, z: float, ax: float, ay: float, size) -> Image.Image:
    """`img` scaled by z about (ax, ay), cropped back to `size`."""
    W, H = size
    left, top = ax - ax / z, ay - ay / z
    return img.resize((W, H), Image.BILINEAR, box=(left, top, left + W / z, top + H / z))


def _sweep_frames(product: Image.Image, box, n: int):
    """Precompute the shine band as a per-frame list of additive alpha masks
    over the product's box only (computing it full-frame 180 times would be
    the slowest thing in the clip)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    region = np.asarray(product.crop((x0, y0, x1, y1)).getchannel("A"), np.float32) / 255
    h, w = region.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    diag = (xs / max(w, 1)) * 0.8 + (ys / max(h, 1)) * 0.45   # 0 .. ~1.25 across the box
    out = []
    for i in range(n):
        p = -0.35 + 1.95 * (i / max(n - 1, 1))
        band = np.exp(-((diag - p) / 0.11) ** 2) * region * 0.42
        out.append((band * 255).astype(np.uint8))
    return (x0, y0), out


def render_clip(layers: dict, seconds: float = 6.0, fps: int = 30) -> bytes:
    """MP4 bytes from composite.place()'s layers."""
    from backend.core.watermark import ffmpeg_exe
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg is not available on this server, so a clip cannot be made.")
    bg = layers["background"].convert("RGB")
    W, H = bg.size
    fg = layers["shadow"].copy()
    fg.alpha_composite(layers["product"])
    ax, ay = layers["anchor"]
    n = int(seconds * fps)
    # The shine runs over the middle of the clip, frames 35%..80%.
    s0, s1 = int(n * 0.35), int(n * 0.80)
    (sx, sy), sweep = _sweep_frames(layers["product"], layers["product_box"], s1 - s0)
    white = None

    fd, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    cmd = [exe, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k",
           "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            e = _ease(i / max(n - 1, 1))
            frame = _zoom(bg, 1 + 0.06 * e, ax, ay, (W, H)).convert("RGBA")
            layer = fg
            if s0 <= i < s1:
                mask = Image.fromarray(sweep[i - s0])
                if white is None or white.size != mask.size:
                    white = Image.new("RGBA", mask.size, (255, 250, 240, 0))
                shine = white.copy()
                shine.putalpha(mask)
                layer = fg.copy()
                layer.alpha_composite(shine, (sx, sy))
            frame.alpha_composite(_zoom(layer, 1 + 0.12 * e, ax, ay, (W, H)))
            proc.stdin.write(frame.convert("RGB").tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait(timeout=300) != 0:
            raise RuntimeError("ffmpeg could not encode the clip: " + err[:200])
        with open(out_path, "rb") as fh:
            return fh.read()
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            os.remove(out_path)
        except OSError:
            pass
