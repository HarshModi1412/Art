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
