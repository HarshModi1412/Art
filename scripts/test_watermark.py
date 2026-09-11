"""
Watermark remover — synthetic pictures and clips with a known mark, so the
test knows exactly which pixels should change and which must not.

Run: python3 scripts/test_watermark.py
"""
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from backend.core import watermark  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


def _font(size):
    try:
        import matplotlib
        p = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts",
                         "ttf", "DejaVuSans-Bold.ttf")
        return ImageFont.truetype(p, size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


rng = np.random.default_rng(7)


def scene(w, h, shift=0):
    """A product-photo-ish scene: warm gradient, soft noise, a dark 'product'."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.stack([90 + 60 * (x + shift) / w, 70 + 40 * y / h,
                     60 + 30 * np.sin((x + shift) / 37.0)], axis=2)
    tex = 18 * np.sin((x + shift) / 5.3) * np.cos(y / 7.1)
    img = base + tex[..., None]
    cx, cy = w * 0.45, h * 0.5
    blob = ((x - cx) ** 2 / (w * 0.18) ** 2 + (y - cy) ** 2 / (h * 0.25) ** 2) < 1
    img[blob] = [40, 30, 35]
    return np.clip(img, 0, 255).astype(np.uint8)


def stamp(rgb, text="Veo", alpha=150, corner="br"):
    im = Image.fromarray(rgb).convert("RGBA")
    w, h = im.size
    size = max(14, w // 26)
    f = _font(size)
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    m = max(12, w // 40)
    if corner == "br":
        xy = (w - m - tw - bb[0], h - m - th - bb[1])
    else:
        xy = (m - bb[0], h - m - th - bb[1])
    d.text(xy, text, font=f, fill=(255, 255, 255, alpha))
    out = np.asarray(Image.alpha_composite(im, lay).convert("RGB"))
    changed = np.abs(out.astype(int) - rgb.astype(int)).sum(axis=2) > 0
    return out, changed


def png(rgb):
    b = io.BytesIO()
    Image.fromarray(rgb).save(b, format="PNG")
    return b.getvalue()


def load(b):
    return np.asarray(Image.open(io.BytesIO(b)).convert("RGB")).astype(int)


# =========================================================================
print("\n== images ==")
# =========================================================================
clean = scene(1024, 1024)
marked, where = stamp(clean)
out, rep = watermark.clean_image(png(marked))
check("a corner mark is found", rep["removed"], rep)
check("in the corner it was actually in",
      rep["regions"] and rep["regions"][0]["corner"] == "bottom-right", rep["regions"])
got = load(out)
before = np.abs(marked.astype(int) - clean.astype(int))[where].mean()
after = np.abs(got - clean.astype(int))[where].mean()
check("and the marked pixels move most of the way back to the real picture",
      after < before * 0.45, f"before {before:.1f} after {after:.1f}")
outside = ~watermark._dilate(where, 40)
check("nothing outside the mark's neighbourhood is touched",
      np.abs(got - clean.astype(int))[outside].max() == 0,
      np.abs(got - clean.astype(int))[outside].max())

b = png(clean)
out2, rep2 = watermark.clean_image(b)
check("a picture with no mark comes back byte-for-byte untouched",
      out2 == b and not rep2["removed"], rep2)

# A big white product sitting in the corner is the picture, not a watermark.
white = clean.copy()
white[700:1000, 760:1000] = [246, 246, 244]
b3 = png(white)
out3, rep3 = watermark.clean_image(b3)
check("a large white object in the corner is left alone", out3 == b3, rep3)

# Bright specular texture all over the corner: part of the photo.
spark = clean.copy()
yy, xx = np.mgrid[0:1024, 0:1024]
spots = ((yy % 23 == 0) & (xx % 19 == 0) & (yy > 760) & (xx > 700))
spark[watermark._dilate(spots, 2)] = [250, 250, 250]
b4 = png(spark)
out4, rep4 = watermark.clean_image(b4)
check("bright texture spread across a corner is left alone", out4 == b4, rep4)

marked_l, _ = stamp(clean, "AI", corner="bl")
_, rep5 = watermark.clean_image(png(marked_l))
check("a mark in the other bottom corner is found too",
      rep5["removed"] and rep5["regions"][0]["corner"] == "bottom-left", rep5)

out6, rep6 = watermark.clean_image(b"not an image")
check("garbage in never raises — the original comes back with a reason",
      out6 == b"not an image" and rep6["reason"], rep6)

jpg = io.BytesIO()
Image.fromarray(marked).save(jpg, format="JPEG", quality=92)
_, rep7 = watermark.clean_image(jpg.getvalue())
check("JPEG compression noise does not hide the mark", rep7["removed"], rep7)

# =========================================================================
print("\n== videos ==")
# =========================================================================
caps = watermark.capabilities()
check("this server can clean videos (OpenCV + ffmpeg present)", caps["videos"], caps)

import cv2  # noqa: E402

tmp = tempfile.mkdtemp()


def write_clip(path, frames, fps=24):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(cv2.cvtColor(f, cv2.COLOR_RGB2BGR))
    vw.release()


W, H, N = 640, 360, 60
wide = scene(W + 3 * N, H)
moving = [wide[:, 3 * i:3 * i + W].copy() for i in range(N)]
_, vmask = stamp(moving[0])
marked_frames = [stamp(f)[0] for f in moving]
src = os.path.join(tmp, "flow.mp4")
write_clip(src, marked_frames)
data = open(src, "rb").read()
cleaned, vrep = watermark.clean_video_bytes(data, "flow.mp4")
check("a static mark on a moving clip is found", vrep["removed"], vrep)
check("by the 'stays put while the picture moves' cue",
      vrep.get("mode") == "static-overlay", vrep.get("mode"))
dst = os.path.join(tmp, "out.mp4")
open(dst, "wb").write(cleaned)
cap = cv2.VideoCapture(dst)
frames_out = []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    frames_out.append(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(int))
cap.release()
check("the cleaned clip still decodes, with every frame", len(frames_out) >= N - 1,
      len(frames_out))
errs_b, errs_a = [], []
for i in (5, 30, 55):
    errs_b.append(np.abs(marked_frames[i].astype(int) - moving[i].astype(int))[vmask].mean())
    errs_a.append(np.abs(frames_out[i] - moving[i].astype(int))[vmask].mean())
check("the mark is mostly gone from frames across the clip",
      np.mean(errs_a) < np.mean(errs_b) * 0.6,
      f"before {np.mean(errs_b):.1f} after {np.mean(errs_a):.1f}")
probe = open(dst, "rb").read(64)
check("it is re-encoded as MP4 a browser can play (H.264)",
      b"ftyp" in probe and watermark.ffmpeg_exe() is not None)

plain = os.path.join(tmp, "plain.mp4")
write_clip(plain, moving)
pdata = open(plain, "rb").read()
pout, prep = watermark.clean_video_bytes(pdata, "plain.mp4")
check("a handheld clip with no mark comes back untouched",
      pout == pdata and not prep["removed"], prep)

still = os.path.join(tmp, "still.mp4")
write_clip(still, [clean[:H, :W].copy() for _ in range(40)])
sdata = open(still, "rb").read()
sout, srep = watermark.clean_video_bytes(sdata, "still.mp4")
check("a locked-off clip with no mark is not 'cleaned' just because nothing moves",
      sout == sdata and not srep["removed"], srep)

bad, brep = watermark.clean_video_bytes(b"\x00\x01nope", "x.mp4")
check("an unreadable clip never raises — the original comes back",
      bad == b"\x00\x01nope" and brep["reason"], brep)

# =========================================================================
print("\n== videos: a reel cannot take the server down ==")
# =========================================================================
# The bug: cleaning an 8-second 1080x1920 reel inside the web server peaked at
# ~730 MB, plus ~340 MB in ffmpeg. On a 512 MB instance the server was killed
# and every request came back 502 ("the server is waking up") — for every
# retry of the same upload, too.
import json as _json  # noqa: E402
import subprocess as _sp  # noqa: E402

RW, RH, RN = 1080, 1920, 48
reel_frames = [stamp(scene(RW, RH, shift=6 * i))[0] for i in range(RN)]
reel = os.path.join(tmp, "reel.mp4")
write_clip(reel, reel_frames)
del reel_frames
probe = (
    "import json,resource,sys;sys.path.insert(0,%r);"
    "from backend.core import watermark as w;"
    "d=open(%r,'rb').read();o,r=w.clean_video_bytes(d,'reel.mp4');"
    "hwm=[int(l.split()[1])//1024 for l in open('/proc/self/status') if l.startswith('VmHWM')][0];"
    "print(json.dumps({'self':hwm,"
    "'child':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss//1024,"
    "'removed':r.get('removed'),'reason':r.get('reason')}))"
) % (os.path.dirname(os.path.dirname(os.path.abspath(__file__))), reel)
out = _sp.run([sys.executable, "-c", probe], capture_output=True, timeout=600)
m = _json.loads(out.stdout.decode().strip().splitlines()[-1]) if out.returncode == 0 else {}
check("a 1080x1920 reel is cleaned", m.get("removed") is True, (m, out.stderr[-300:]))
check("the web-server process stays small while it happens (<150 MB)",
      0 < m.get("self", 0) < 150, m)
check("the cleaner itself stays well inside a 512 MB instance (<320 MB)",
      0 < m.get("child", 0) < 320, m)

# the heavy work happens in a child process
calls = []
_real_run = _sp.run


def _spy(cmd, *a, **k):
    calls.append(cmd)
    return _real_run(cmd, *a, **k)


watermark.subprocess.run = _spy
watermark.clean_video_bytes(data, "flow.mp4")
watermark.subprocess.run = _real_run
check("cleaning runs in a separate process",
      calls and calls[0][1:3] == ["-m", "backend.core.watermark"], calls[:1])


def _killed(cmd, *a, **k):
    return _sp.CompletedProcess(cmd, -9, b"", b"")


watermark.subprocess.run = _killed
kout, krep = watermark.clean_video_bytes(data, "flow.mp4")
watermark.subprocess.run = _real_run
check("if the cleaner is killed for memory, the original clip comes back — nothing raises",
      kout == data and not krep["removed"] and "memory" in krep["reason"], krep)


def _slow(cmd, *a, **k):
    raise _sp.TimeoutExpired(cmd, 1)


watermark.subprocess.run = _slow
tout, trep = watermark.clean_video_bytes(data, "flow.mp4")
watermark.subprocess.run = _real_run
check("a clip that takes too long is attached as it is", tout == data and "longer" in trep["reason"], trep)

_real_free = watermark._cgroup_free_mb
watermark._cgroup_free_mb = lambda: 120.0
os.environ["WATERMARK_INPROCESS"] = "1"
gout, grep_ = watermark.clean_video_bytes(data, "flow.mp4")
os.environ.pop("WATERMARK_INPROCESS")
watermark._cgroup_free_mb = _real_free
check("with too little free memory it does not even start — and says why",
      gout == data and not grep_["removed"] and "not enough free memory" in grep_["reason"], grep_)
check("the estimate for a 1080p reel is what was measured, with room to spare",
      280 <= watermark.video_need_mb(1080, 1920) <= 360, watermark.video_need_mb(1080, 1920))

JS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Smart CafeX", "smart.js"), encoding="utf-8").read()
check("the app attaches the clip unchanged if cleaning fails, instead of losing it",
      "async function attachClip" in JS and "clean: false" in JS
      and JS.count("attachClip(post.id") >= 3)
MAIN = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "backend", "main.py"), encoding="utf-8").read()
check("the upload is read in pieces and stopped at the size cap",
      "await f.read(1024 * 1024)" in MAIN and "clean: bool = True" in MAIN)
shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
