"""
Compression utilities for automatic content decompression.

Supports gzip, deflate, and brotli (br) encodings.
"""

from __future__ import annotations

import gzip
import io
import zlib

# Brotli is optional but included in dependencies
try:
    import brotli

    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False


# Default Accept-Encoding value matching modern browsers
DEFAULT_ACCEPT_ENCODING = "gzip, deflate, br" if BROTLI_AVAILABLE else "gzip, deflate"


def decode_body(body: bytes, content_encoding: str) -> bytes:
    """
    Decode response body based on Content-Encoding header.

    Args:
        body: Raw response body bytes
        content_encoding: Value of Content-Encoding header

    Returns:
        Decoded body bytes
    """
    if not content_encoding or not body:
        return body

    encoding = content_encoding.lower().strip()

    # Handle multiple encodings (e.g., "gzip, br")
    # Process in reverse order as per HTTP spec
    encodings = [e.strip() for e in encoding.split(",")]

    result = body
    for enc in reversed(encodings):
        result = _decode_single(result, enc)

    return result


def _decode_single(body: bytes, encoding: str) -> bytes:
    """Decode body with a single encoding."""
    if encoding == "gzip":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as f:
                return f.read()
        except Exception:
            return body

    if encoding == "deflate":
        try:
            # Try raw deflate first (no header)
            return zlib.decompress(body, -zlib.MAX_WBITS)
        except Exception:
            try:
                # Fall back to zlib-wrapped deflate
                return zlib.decompress(body)
            except Exception:
                return body

    if encoding == "br":
        if not BROTLI_AVAILABLE:
            return body
        try:
            return brotli.decompress(body)
        except Exception:
            return body

    # Unknown encoding, return as-is
    return body


def get_accept_encoding(profile: dict, auto_decompress: bool = True) -> str | None:
    """
    Get the Accept-Encoding value based on profile and settings.

    Args:
        profile: Browser impersonation profile
        auto_decompress: Whether automatic decompression is enabled

    Returns:
        Accept-Encoding header value, or None to use profile default
    """
    if not auto_decompress:
        return "identity"

    # Check if profile has custom Accept-Encoding in default headers
    default_headers = profile.get("headers", {}).get("default", [])
    for name, value in default_headers:
        if name.lower() == "accept-encoding":
            return value

    # Use our default
    return DEFAULT_ACCEPT_ENCODING
