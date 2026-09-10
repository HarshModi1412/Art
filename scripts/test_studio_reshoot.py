"""
Guard for the "Re-shoot my photo" bug: when the OpenAI engine was active (no
Cloudflare account configured), generate_image() called images.generate() —
pure text-to-image — no matter what, even for a re-shoot with a reference
photo. images.generate() has no argument for a source image, so the
reference was silently dropped, from_reference was hardcoded False, and
"Re-shoot my photo" produced exactly what "Invent a picture" produces: a
plausible but unrelated image, not the seller's actual product.

This forces the OpenAI engine on (no Cloudflare env vars) and swaps in a
fake `openai.OpenAI` so no real network call happens, then checks which
method actually got called for each button.

Run: python3 scripts/test_studio_reshoot.py
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force the OpenAI branch: no Cloudflare creds, a fake OpenAI key.
os.environ.pop("CF_ACCOUNT_ID", None)
os.environ.pop("CF_API_TOKEN", None)
os.environ["OPENAI_API_KEY"] = "sk-test-not-real"

from backend.core import studio  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


class _FakeImage:
    def __init__(self, b64):
        self.b64_json = b64
        self.url = None


class _FakeResponse:
    def __init__(self, b64):
        self.data = [_FakeImage(b64)]


import base64  # noqa: E402
FAKE_PNG_B64 = base64.b64encode(b"not a real png, just test bytes").decode()


class _FakeImages:
    def __init__(self):
        self.edit_calls = []
        self.generate_calls = []

    def edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        return _FakeResponse(FAKE_PNG_B64)

    def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        return _FakeResponse(FAKE_PNG_B64)


class _FakeOpenAI:
    last_instance = None

    def __init__(self, *a, **k):
        self.images = _FakeImages()
        _FakeOpenAI.last_instance = self


fake_openai_module = types.ModuleType("openai")
fake_openai_module.OpenAI = _FakeOpenAI
sys.modules["openai"] = fake_openai_module

# media.save() actually writes/uploads -- stub it so this test needs no
# storage backend, same trick the rest of the studio tests use.
import backend.core.media as media  # noqa: E402
media.save = lambda name, content, email: {"url": f"/media/{name}", "durable": False}

check("engine resolves to openai with no Cloudflare creds set",
      studio.image_engine()["engine"] == "openai", studio.image_engine())

print("\n== 1. Re-shoot my photo (a reference is supplied) ==")
ref = (b"fake product photo bytes", "image/jpeg")
BRIEF = studio.build_brief(
    {"name": "Test Brand"},
    {"name": "Cotton Kurta", "category": "Clothing", "price": 999},
    {})
result = studio.generate_image("seller@test.co", BRIEF, None, reference=ref)

fake = _FakeOpenAI.last_instance
check("images.edit() was called", len(fake.images.edit_calls) == 1, fake.images.edit_calls)
check("images.generate() was NOT called (that's the bug this fixes)",
      len(fake.images.generate_calls) == 0, fake.images.generate_calls)
if fake.images.edit_calls:
    call = fake.images.edit_calls[0]
    check("the reference photo's actual bytes were sent as the image",
          call.get("image", (None, None, None))[1] == ref[0])
    check("input_fidelity is set to high, so the model holds onto real features",
          call.get("input_fidelity") == "high", call.get("input_fidelity"))
check("the result reports it came from the reference",
      result.get("from_reference") is True, result.get("from_reference"))

print("\n== 2. Invent a picture (no reference) ==")
result2 = studio.generate_image("seller@test.co", BRIEF, None, reference=None)
fake2 = _FakeOpenAI.last_instance  # a fresh OpenAI() client is built per call

check("images.generate() was called", len(fake2.images.generate_calls) == 1,
      fake2.images.generate_calls)
check("images.edit() was NOT called", len(fake2.images.edit_calls) == 0)
check("the result reports it did NOT come from a reference",
      result2.get("from_reference") is False, result2.get("from_reference"))

print("\n== 3. the seller's engine choice is honoured, never substituted ==")
# This section used to assert the opposite: Cloudflare was tried first and a
# failure fell through to OpenAI automatically. That was right while the SERVER
# picked the engine. It became wrong the moment the seller picks one, because
# falling through means drawing on an engine they did not choose at a price
# they did not agree to. A failure now names the engine and stops.
os.environ["CF_ACCOUNT_ID"] = "test-account"
os.environ["CF_API_TOKEN"] = "test-token"
check("with both connected, the default is still ChatGPT",
      studio.image_engine()["engine"] == "openai", studio.image_engine())
check("Cloudflare is offered for inventing a picture",
      "cloudflare" in [e["id"] for e in studio.image_engines()])
check("but NOT for a re-shoot -- its img2img redraws the product",
      "cloudflare" not in [e["id"] for e in studio.image_engines(for_reshoot=True)])
try:
    studio.image_engine("cloudflare", for_reshoot=True)
    check("and asking for it anyway is refused", False, "no error")
except ValueError as e:
    check("and asking for it anyway is refused with the reason",
          "redraw the product" in str(e), str(e)[:80])

import backend.core.aiprovider as aiprovider  # noqa: E402
aiprovider.restyle_image = lambda *a, **k: None   # simulate quota exhaustion / any failure
aiprovider.generate_image = lambda *a, **k: None

result3 = studio.generate_image("seller@test.co", BRIEF, None, reference=ref)
fake3 = _FakeOpenAI.last_instance
check("the default engine drew it", result3.get("url") is not None, result3)
check("using images.edit() (it was a re-shoot, with a reference)",
      len(fake3.images.edit_calls) == 1, fake3.images.edit_calls)
check("and it reports honestly which engine drew",
      result3.get("engine") == "openai", result3.get("engine"))
check("and that it is not the free path", result3.get("free") is False)
check("from_reference stays True", result3.get("from_reference") is True)

print("\n== 4. a failing engine says which one failed ==")
del os.environ["OPENAI_API_KEY"]
try:
    studio.generate_image("seller@test.co", BRIEF, None, reference=ref, engine="huggingface")
    check("an engine with no key is refused before spending anything", False, "did not raise")
except ValueError as e:
    check("an engine with no key is refused before spending anything", True)
    check("and the message says it is not connected, not that it broke",
          "not connected" in str(e), str(e))

os.environ["HF_API_TOKEN"] = "hf-test-not-real"
import importlib
importlib.reload(aiprovider); importlib.reload(studio)
studio_ai = importlib.import_module("backend.core.aiprovider")
studio_ai.hf_image = lambda *a, **k: None    # connected, but comes back empty
try:
    studio.generate_image("seller@test.co", BRIEF, None, reference=ref, engine="huggingface")
    check("a connected-but-failing engine raises", False, "did not raise")
except RuntimeError as e:
    check("a connected-but-failing engine raises", True)
    check("the message names the engine that failed, by its seller-facing label",
          "Hugging Face" in str(e), str(e))
    check("and points at the other engines rather than dead-ending",
          "another engine" in str(e), str(e))
del os.environ["HF_API_TOKEN"]
os.environ["OPENAI_API_KEY"] = "sk-test-not-real"  # restore for anything after this

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
