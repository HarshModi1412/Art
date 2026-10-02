"""
Hand memory back to the operating system after a big request.

WHY THIS EXISTS
---------------
The live server is a 512MB Render instance, and Render kills the process the
moment it goes over. A sales upload parses a whole spreadsheet into pandas,
which leaves hundreds of thousands of small Python objects (every string cell
is one). When the request is done CPython frees them, but glibc keeps the
freed pages inside the process for reuse, so the resident size Render measures
stays at the high-water mark. The next big upload then starts from there, not
from idle, and that ratchet is how an instance that idles at ~260MB ends up
killed by a file that alone needed ~150MB.

`release()` runs a GC pass (pandas frames can sit in reference cycles) and then
asks glibc to return free pages with malloc_trim(0). On anything that is not
glibc (Windows, macOS, musl) the trim is skipped and only the GC runs.

Cheap enough to call after a request that handled a dataset; do not call it on
every request.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import gc
import sys

_trim = None
if sys.platform.startswith("linux"):
    try:
        _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        _trim = _libc.malloc_trim
        _trim.argtypes = [ctypes.c_size_t]
        _trim.restype = ctypes.c_int
    except (OSError, AttributeError):  # musl has no malloc_trim
        _trim = None


def release() -> None:
    """Collect garbage and return freed heap pages to the OS. Never raises."""
    try:
        gc.collect()
        if _trim is not None:
            _trim(0)
    except Exception:  # noqa: BLE001 — housekeeping must never fail a request
        pass


# ---------------------------------------------------------------------------
# One heavy dataset request at a time.
#
# The home screen fires its first requests together, and each of them that
# works on the seller's whole sales table (the Approval panel, Today, Sales
# Analytics) needs its own working memory on top of the table. Side by side on
# a 512MB instance that is what got the server OOM-killed on 2 October 2026,
# when a seller opened Sales Analytics right after a deploy: measured locally,
# a 300k-row file cost +220MB with the three running at once against +151MB
# one after another. They are short (a second or two each), so queueing them
# costs a little latency and saves the process.
#
# Re-entrant per thread, so a gated endpoint that calls another gated function
# does not wait on itself. A request never waits more than HEAVY_WAIT_SECONDS:
# past that it runs anyway, slower to crash than to hang.
# ---------------------------------------------------------------------------
import functools as _functools
import os as _os
import threading as _threading

_HEAVY = _threading.BoundedSemaphore(max(1, int(_os.environ.get("HEAVY_CONCURRENCY", "1") or 1)))
_HEAVY_WAIT_SECONDS = float(_os.environ.get("HEAVY_WAIT_SECONDS", "120") or 120)
_held = _threading.local()


class _Heavy:
    def __enter__(self):
        depth = getattr(_held, "depth", 0)
        self._got = False
        if depth == 0:
            self._got = _HEAVY.acquire(timeout=_HEAVY_WAIT_SECONDS)
        _held.depth = depth + 1
        return self

    def __exit__(self, *exc):
        _held.depth -= 1
        if self._got:
            _HEAVY.release()
        return False


def heavy() -> _Heavy:
    """`with memory.heavy():` around work on a whole dataset."""
    return _Heavy()


def one_at_a_time(fn):
    """Decorator form of heavy() for sync FastAPI endpoints. functools.wraps
    keeps the signature FastAPI reads its parameters from."""
    @_functools.wraps(fn)
    def inner(*a, **k):
        with heavy():
            return fn(*a, **k)
    return inner
