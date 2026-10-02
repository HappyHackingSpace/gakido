"""
ctypes bridge to the native TLS backend (Go + uTLS, built from ``native/``).

The backend reproduces a real browser's TLS ClientHello (JA3/JA4) and HTTP/2
framing ("Akamai" fingerprint) byte-for-byte, which the stdlib ``ssl`` path
cannot do. The shared library is optional: when it is not built,
:func:`is_available` returns ``False`` and callers fall back to the pure-Python
path.
"""

from __future__ import annotations

import base64
import ctypes
import json
import sys
import threading
from pathlib import Path

_NATIVE_DIR = Path(__file__).resolve().parent / "_native"
_LIB_STEM = "libgakido_tls"


def _library_path() -> Path | None:
    if sys.platform == "win32":
        ext = "dll"
    elif sys.platform == "darwin":
        ext = "dylib"
    else:
        ext = "so"
    candidate = _NATIVE_DIR / f"{_LIB_STEM}.{ext}"
    return candidate if candidate.exists() else None


_lib: ctypes.CDLL | None = None
_lib_lock = threading.Lock()
_load_attempted = False


def _load() -> ctypes.CDLL | None:
    global _lib, _load_attempted
    if _lib is not None or _load_attempted:
        return _lib
    with _lib_lock:
        if _lib is not None or _load_attempted:
            return _lib
        _load_attempted = True
        path = _library_path()
        if path is None:
            return None
        try:
            lib = ctypes.CDLL(str(path))
            lib.GakidoRequest.argtypes = [ctypes.c_char_p]
            lib.GakidoRequest.restype = ctypes.c_void_p
            lib.GakidoFreeString.argtypes = [ctypes.c_void_p]
            lib.GakidoFreeString.restype = None
            _lib = lib
        except (OSError, AttributeError):
            _lib = None
    return _lib


def is_available() -> bool:
    """Return True if the native backend shared library is loadable."""
    return _load() is not None


class NativeBackendError(RuntimeError):
    """Raised when the native backend reports an error for a request."""


def request(spec: dict) -> dict:
    """
    Execute a single request through the native backend.

    ``spec`` matches the Go ``RequestSpec`` contract; the returned dict matches
    ``ResponseSpec`` with ``body`` decoded to bytes. Raises NativeBackendError
    if the backend is unavailable or reports an error.
    """
    lib = _load()
    if lib is None:
        raise NativeBackendError("native TLS backend is not available")

    payload = json.dumps(spec).encode("utf-8")
    ptr = lib.GakidoRequest(payload)
    if not ptr:
        raise NativeBackendError("native backend returned no response")
    try:
        raw = ctypes.cast(ptr, ctypes.c_char_p).value or b"{}"
    finally:
        lib.GakidoFreeString(ptr)

    result = json.loads(raw.decode("utf-8"))
    if result.get("error"):
        raise NativeBackendError(result["error"])
    result["body"] = base64.b64decode(result.get("body_b64", "") or "")
    return result
