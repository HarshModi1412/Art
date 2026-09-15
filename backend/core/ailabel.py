"""AI labelling, and the switch that stops us removing anybody else's label.

WHY THIS FILE EXISTS
--------------------
The Information Technology (Intermediary Guidelines and Digital Media Ethics
Code) Amendment Rules 2026 came into force on 20 February 2026. They bind any
intermediary "offering computer resources enabling creation or modification of
synthetically generated information". That is exactly what this platform is: a
seller types a brief and we hand back a picture that was not photographed.

Two duties follow, and before this file existed we failed both of them in
opposite directions:

  1. Synthetically generated visual content must be **clearly and prominently
     labelled**, and permanent metadata or a provenance identifier that traces
     the computer resource used to generate it must be embedded where feasible.
     We were labelling nothing. The app knew a picture was generated
     (`image_generated`), but that flag lives in our database, not in the file,
     so it vanished the moment the picture was posted anywhere.

  2. An intermediary must ensure that "the modification, suppression or removal
     of the label, permanent metadata shall not be enabled". backend/core/
     watermark.py is a feature whose entire purpose is to remove a visible AI
     label, including from clips a seller uploads that somebody else generated.

The consequence of getting this wrong is not a fine in the first instance. It
is the loss of safe harbour under section 79 of the IT Act, which is the thing
that stops the operator of this platform being personally answerable for what
every seller posts through it. So it is not a nice-to-have.

WHAT THIS DOES INSTEAD, WITHOUT LOSING THE POINT
------------------------------------------------
The reason watermark.py was written is legitimate: a brand post with Google
Flow's mark in the corner reads as borrowed, which is the opposite of what a
brand post is for. The lawful way to get the same clean frame is:

  * Turn the generator's own mark off at the generator. Google Flow has a
    setting for it (Settings, then Media Watermark) and it is available to free
    accounts. Kling's free tier does not, so a seller who wants unmarked clips
    either pays there or uses Flow. We say so plainly in the UI rather than
    quietly rubbing the mark out.
  * Apply OUR OWN label, which we are required to apply anyway. One label in
    the corner, ours, compliant, and no second brand's mark competing with the
    seller's own.

So the visible corner ends up clean of other people's marks and carries one
honest label. The seller gets what they wanted and the platform keeps its safe
harbour.

THE REMOVAL SWITCH
------------------
`removal_enabled()` is False unless WATERMARK_REMOVAL is set to on/1/true/yes.
Nothing in the product turns it on. It exists because the code in watermark.py
is careful, well-tested work that has legitimate uses outside this rule (a
seller's own logo they want gone from their own photograph, say), and deleting
somebody else's 900 lines on my own judgement is not my call. The default is
the compliant one, and the deployment has to opt in to the other.

WHAT WE EMBED
-------------
Three things, in whatever the format supports:

  * A human-readable line, so anyone who opens the file properties sees it.
  * A unique identifier, so a specific picture can be traced back to the
    generation that made it. That is the "unique identifier" the rule asks for.
  * The generating engine and this platform's name, which is the "computer
    resource used to generate" it.

Deliberately NOT attempted: forging C2PA manifests or SynthID. Those are
cryptographic provenance schemes and a hand-rolled imitation is worse than
none, because it claims an assurance it cannot give. Where an engine already
embeds SynthID (Gemini and Flow do), it survives everything here untouched:
nothing in this module or in watermark.py re-encodes in a way that targets it.

Nothing here raises. A picture that could not be labelled is reported as
unlabelled rather than lost, and the caller decides. That matters because the
alternative, failing generation over a cosmetic step, would push a seller
towards posting the unlabelled original by hand.
"""
from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import uuid

log = logging.getLogger(__name__)

# The words on the picture. Short, unambiguous, and in English because the
# label has to be understood by a regulator and a shopper, not only the seller.
# "AI generated" tests better than "Synthetic" or "Made with AI" for plain
# comprehension, and it is what Instagram and YouTube both settled on.
LABEL_TEXT = "AI generated"

# What goes in the file's own metadata. PLATFORM is read from config so a
# rebranded deployment labels itself honestly rather than carrying our name.
PLATFORM = os.getenv("PRODUCT_NAME", "One Tap Manager")

_TRUE = {"1", "true", "yes", "on"}


def removal_enabled() -> bool:
    """Whether the watermark remover is allowed to run at all.

    False by default. See the module docstring: enabling this makes the
    deployment non-compliant with Rule 3 of the IT Rules as amended on
    20 February 2026, because it enables the removal of somebody else's AI
    label. It is a switch rather than a deletion so the decision stays with
    whoever runs the deployment, and so it is visible in the health report.
    """
    return str(os.getenv("WATERMARK_REMOVAL", "")).strip().lower() in _TRUE


def compliance_state() -> dict:
    """For /api/admin/health. Says what is true, not what we would like."""
    removal = removal_enabled()
    return {
        "labelling": True,
        "removal_enabled": removal,
        "ok": not removal,
        "note": (
            "The watermark remover is switched on. Rule 3 of the IT Rules as "
            "amended on 20 February 2026 requires an intermediary that offers "
            "AI generation to ensure the removal of an AI label is not enabled, "
            "and breaking that costs this platform its safe harbour under "
            "section 79 of the IT Act, which is what stops the operator being "
            "personally answerable for what every seller posts. Unset "
            "WATERMARK_REMOVAL to switch it off."
            if removal else
            "Generated pictures and clips are labelled and carry provenance "
            "metadata, and nothing removes another tool's label."),
    }


# ---------------------------------------------------------------- provenance
def provenance(engine: str = "", model: str = "", kind: str = "image") -> dict:
    """The record that goes into the file.

    `gen_id` is the unique identifier. It is random rather than derived from the
    image, because a hash of the pixels changes the moment anybody crops the
    picture and a provenance id that breaks on a crop is not provenance.
    """
    from datetime import datetime, timezone
    return {
        "gen_id": uuid.uuid4().hex,
        "label": LABEL_TEXT,
        "kind": kind,
        "platform": PLATFORM,
        "engine": engine or "unknown",
        "model": model or "",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "notice": (
            "This file was generated or edited by an artificial intelligence "
            "model. Labelled under Rule 3 of the Information Technology "
            "(Intermediary Guidelines and Digital Media Ethics Code) Rules 2021 "
            "as amended in 2026."),
    }


def _human_line(p: dict) -> str:
    bits = [f"{LABEL_TEXT}."]
    if p.get("engine") and p["engine"] != "unknown":
        bits.append(f"Generated with {p['engine']}"
                    + (f" ({p['model']})." if p.get("model") else "."))
    bits.append(f"Made through {p.get('platform') or PLATFORM}.")
    bits.append(f"Reference {p.get('gen_id', '')}.")
    return " ".join(bits)


# ---------------------------------------------------------------- fonts
def _font(size: int):
    """A legible font without shipping a font asset.

    matplotlib is already a hard dependency (the PDF report needs it) and it
    bundles DejaVu Sans Bold, so that is first choice. Pillow's own scalable
    default is the fallback, which means the label renders even on a container
    with no system fonts at all. A label that silently fails to draw would be
    the exact failure this module exists to prevent, so there is no path here
    that ends with no font.
    """
    from PIL import ImageFont
    try:
        import matplotlib
        path = os.path.join(os.path.dirname(matplotlib.__file__),
                            "mpl-data", "fonts", "ttf", "DejaVuSans-Bold.ttf")
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:  # noqa: BLE001
        pass
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        try:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:          # Pillow older than 10.1
        return ImageFont.load_default()


# ---------------------------------------------------------------- images
# The label goes bottom-LEFT. Generators put their marks bottom-right almost
# without exception, and the brand plate from Product Studio is bottom-right
# too, so the left corner is the one place a label cannot end up sitting on top
# of something else and becoming unreadable. "Clearly and prominently" is not
# satisfied by a label nobody can read.
def _draw_label(img, text: str):
    from PIL import Image, ImageDraw
    w, h = img.size
    # Scales with the picture: about 3.4% of the short edge, floored at 13px so
    # it stays legible on a small thumbnail and capped so it does not shout on a
    # 2048px render.
    size = max(13, min(40, int(min(w, h) * 0.034)))
    font = _font(size)
    draw = ImageDraw.Draw(img)
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    pad_x, pad_y = size * 0.62, size * 0.42
    margin = max(12, int(min(w, h) * 0.028))
    plate_w, plate_h = tw + pad_x * 2, th + pad_y * 2
    x0, y0 = margin, h - margin - plate_h

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # A dark plate at 72% behind white text. The opacity is computed, not
    # guessed: the worst case is a pure white product photo behind it, which
    # lifts the plate to #4f4f51, and white text on that is 8.17:1. WCAG asks
    # 4.5:1 for body text and 3:1 for large text, so the label stays legible on
    # any picture an engine can produce. The earlier 62% value cleared 4.5:1 but
    # only just, and "clearly and prominently" is not a thing to clear only just.
    od.rounded_rectangle([x0, y0, x0 + plate_w, y0 + plate_h],
                         radius=plate_h * 0.24, fill=(12, 12, 14, 184))
    od.text((x0 + pad_x - box[0], y0 + pad_y - box[1]), text,
            font=font, fill=(255, 255, 255, 242))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _png_metadata(p: dict):
    from PIL.PngImagePlugin import PngInfo
    meta = PngInfo()
    # Keys chosen to be the ones a file browser and ExifTool both surface.
    meta.add_text("Description", _human_line(p))
    meta.add_text("Software", f"{p.get('platform') or PLATFORM}")
    meta.add_text("Comment", p["notice"])
    # The machine-readable copy, so a later tool can read the fields back
    # without parsing English.
    meta.add_text("ai-provenance", json.dumps(p, separators=(",", ":")))
    meta.add_text("ai-generated", "true")
    return meta


def _jpeg_exif(im, p: dict) -> bytes:
    """EXIF without piexif, which is not a dependency here.

    Pillow can write an Exif object straight back, so ImageDescription and
    Software go in IFD0 and UserComment goes in the Exif IFD. Only the tags
    that every reader understands are used; an exotic tag that half the tools
    ignore is no use for a label meant to be found.
    """
    exif = im.getexif()
    exif[0x010E] = _human_line(p)                       # ImageDescription
    exif[0x0131] = f"{p.get('platform') or PLATFORM}"   # Software
    try:
        ifd = exif.get_ifd(0x8769)                      # Exif IFD
        # UserComment: 8 byte encoding prefix, then ASCII.
        ifd[0x9286] = b"ASCII\x00\x00\x00" + json.dumps(
            p, separators=(",", ":")).encode("ascii", "replace")
    except Exception:  # noqa: BLE001
        pass
    return exif.tobytes()


def label_image(data: bytes, engine: str = "", model: str = "",
                text: str = "") -> tuple[bytes, dict]:
    """Draw the label on a generated picture and embed its provenance.

    Returns (bytes, report). On any failure the original bytes come back and
    report["labelled"] is False, so a caller can decide whether to refuse the
    picture rather than posting something unlabelled by accident.
    """
    p = provenance(engine, model, "image")
    report = {"labelled": False, "gen_id": p["gen_id"], "metadata": False,
              "text": text or LABEL_TEXT, "reason": ""}
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        fmt = (im.format or "PNG").upper()
        out = _draw_label(im, text or LABEL_TEXT)
        buf = io.BytesIO()
        if fmt in ("JPEG", "JPG"):
            rgb = out.convert("RGB")
            try:
                rgb.save(buf, format="JPEG", quality=95, exif=_jpeg_exif(im, p))
                report["metadata"] = True
            except Exception as e:  # noqa: BLE001
                buf = io.BytesIO()
                rgb.save(buf, format="JPEG", quality=95)
                report["reason"] = f"visible label only, EXIF failed: {e}"
        else:
            # PNG keeps alpha, and PngInfo is the reliable place for text.
            out.save(buf, format="PNG", pnginfo=_png_metadata(p))
            report["metadata"] = True
        report["labelled"] = True
        report["provenance"] = p
        return buf.getvalue(), report
    except Exception as e:  # noqa: BLE001 — never lose the picture over the label
        log.warning("AI label failed: %s", e)
        report["reason"] = f"could not label: {e}"
        return data, report


def read_provenance(data: bytes) -> dict:
    """Read the embedded record back. Used by the tests, and by the reshoot
    route to tell whether a picture it is handed was already labelled by us."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        raw = (im.info or {}).get("ai-provenance")
        if raw:
            return json.loads(raw)
        exif = im.getexif()
        ifd = exif.get_ifd(0x8769)
        uc = ifd.get(0x9286)
        if isinstance(uc, bytes) and uc[:5] == b"ASCII":
            return json.loads(uc[8:].decode("ascii", "replace"))
        desc = exif.get(0x010E)
        if desc and LABEL_TEXT.lower() in str(desc).lower():
            return {"label": LABEL_TEXT, "notice": str(desc)}
    except Exception:  # noqa: BLE001
        pass
    return {}


# ---------------------------------------------------------------- video
def _label_png(w: int, h: int, text: str) -> bytes:
    """The label as a transparent PNG, to be overlaid by ffmpeg.

    Rendered with Pillow rather than ffmpeg's drawtext on purpose: drawtext
    needs libfreetype compiled into ffmpeg and a font file on disk, and the
    static ffmpeg that ships with imageio-ffmpeg has neither reliably. An
    overlay of a PNG we drew ourselves works on every build.
    """
    from PIL import Image
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out = _draw_label(canvas, text)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def label_video_file(src: str, dst: str, engine: str = "", model: str = "",
                     text: str = "") -> dict:
    """Burn the label into a clip and write the provenance into its container.

    The label is burned in rather than added as a subtitle track, because a
    track is not shown by Instagram, WhatsApp, or anything else a seller will
    post the clip to, and a label nobody sees is not a label.
    """
    p = provenance(engine, model, "video")
    report = {"labelled": False, "gen_id": p["gen_id"], "metadata": False,
              "text": text or LABEL_TEXT, "reason": ""}
    try:
        from backend.core.watermark import ffmpeg_exe
        ff = ffmpeg_exe()
        if not ff:
            report["reason"] = "ffmpeg is not available, clip left unlabelled"
            return report
        w, h = _video_size(ff, src)
        if not w or not h:
            report["reason"] = "could not read the clip's size"
            return report
        png = _label_png(w, h, text or LABEL_TEXT)
        tmp_png = dst + ".label.png"
        with open(tmp_png, "wb") as fh:
            fh.write(png)
        cmd = [ff, "-y", "-i", src, "-i", tmp_png,
               "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
               "-map", "[v]", "-map", "0:a?",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               "-c:a", "aac", "-b:a", "128k",
               "-metadata", f"comment={p['notice']}",
               "-metadata", f"description={_human_line(p)}",
               "-metadata", f"software={p.get('platform') or PLATFORM}",
               "-metadata", f"ai_provenance={json.dumps(p, separators=(',', ':'))}",
               dst]
        r = subprocess.run(cmd, capture_output=True, timeout=600)
        try:
            os.unlink(tmp_png)
        except OSError:
            pass
        if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
            report["reason"] = (r.stderr or b"")[-300:].decode("utf-8", "replace")
            return report
        report.update(labelled=True, metadata=True, provenance=p)
        return report
    except Exception as e:  # noqa: BLE001
        log.warning("video AI label failed: %s", e)
        report["reason"] = f"could not label: {e}"
        return report


def _video_size(ff: str, src: str) -> tuple[int, int]:
    try:
        from backend.core import videotools
        info = videotools.probe(src) or {}
        w, h = int(info.get("width") or 0), int(info.get("height") or 0)
        if w and h:
            return w, h
    except Exception:  # noqa: BLE001
        pass
    # ffmpeg itself prints the size on stderr even with no output file, which is
    # enough and avoids needing ffprobe to exist separately.
    try:
        r = subprocess.run([ff, "-i", src], capture_output=True, timeout=60)
        import re
        m = re.search(rb"(\d{2,5})x(\d{2,5})", r.stderr or b"")
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:  # noqa: BLE001
        pass
    return 0, 0


def label_video_bytes(data: bytes, filename_hint: str = "clip.mp4",
                      engine: str = "", model: str = "",
                      text: str = "") -> tuple[bytes, dict]:
    """Same as label_video_file, for bytes we already hold."""
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="ailabel-")
    src = os.path.join(tmpdir, "in" + (os.path.splitext(filename_hint)[1] or ".mp4"))
    dst = os.path.join(tmpdir, "out.mp4")
    try:
        with open(src, "wb") as fh:
            fh.write(data)
        rep = label_video_file(src, dst, engine, model, text)
        if rep.get("labelled") and os.path.exists(dst):
            with open(dst, "rb") as fh:
                return fh.read(), rep
        return data, rep
    finally:
        for path in (src, dst):
            try:
                os.unlink(path)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass


# ---------------------------------------------------------------- stored media
def label_media_url(url: str, email: str = "", engine: str = "",
                    kind_hint: str = "") -> dict:
    """Label a file that is already in the media store.

    The labelled copy is saved under a NEW name and the original upload is kept,
    for the same reason the watermark remover did it that way: a seller who says
    "that clip was not AI after all" can be given the original back, and no
    cached copy of the old bytes can be served under the new address.
    """
    from backend.core import media
    name = os.path.basename((url or "").split("?", 1)[0])
    out = {"url": url, "report": {"labelled": False, "reason": "not a stored file"}}
    if not name:
        return out
    got = media.read(name)
    if not got:
        return out
    data, _ctype = got
    if media.is_video(name) or kind_hint == "video":
        new, rep = label_video_bytes(data, name, engine=engine)
        ext = ".mp4"
    else:
        new, rep = label_image(data, engine=engine)
        ext = os.path.splitext(name)[1].lower() or ".png"
        if rep.get("labelled") and ext not in (".jpg", ".jpeg"):
            ext = ".png"
    out["report"] = rep
    if rep.get("labelled") and new is not data:
        saved = media.save(f"{uuid.uuid4().hex}{ext}", new, email)
        out["url"] = saved["url"]
        out["original_url"] = url
    return out
