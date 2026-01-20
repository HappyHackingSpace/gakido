"""Tests for gakido.compression module."""

import pytest
import gzip
import zlib
import io

from gakido.compression import (
    decode_body,
    get_accept_encoding,
    DEFAULT_ACCEPT_ENCODING,
    BROTLI_AVAILABLE,
    _decode_single,
)


class TestDecodeBody:
    """Tests for decode_body function."""

    def test_decode_empty_body(self):
        """Test empty body returns unchanged."""
        result = decode_body(b"", "gzip")
        assert result == b""

    def test_decode_empty_encoding(self):
        """Test empty encoding returns body unchanged."""
        result = decode_body(b"test body", "")
        assert result == b"test body"

    def test_decode_gzip(self):
        """Test gzip decompression."""
        # Create gzip compressed data
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"hello world")
        compressed = buf.getvalue()

        result = decode_body(compressed, "gzip")
        assert result == b"hello world"

    def test_decode_deflate_raw(self):
        """Test raw deflate decompression."""
        # Create raw deflate compressed data (no zlib header)
        compress_obj = zlib.compressobj(level=6, method=zlib.DEFLATED, wbits=-zlib.MAX_WBITS)
        compressed = compress_obj.compress(b"hello world") + compress_obj.flush()

        result = decode_body(compressed, "deflate")
        assert result == b"hello world"

    def test_decode_deflate_zlib_wrapped(self):
        """Test zlib-wrapped deflate decompression."""
        # Create zlib-wrapped compressed data
        compressed = zlib.compress(b"hello world")

        result = decode_body(compressed, "deflate")
        assert result == b"hello world"

    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="brotli not installed")
    def test_decode_brotli(self):
        """Test brotli decompression."""
        import brotli
        compressed = brotli.compress(b"hello world")

        result = decode_body(compressed, "br")
        assert result == b"hello world"

    @pytest.mark.skipif(BROTLI_AVAILABLE, reason="brotli is installed")
    def test_decode_brotli_unavailable(self):
        """Test br returns unchanged when brotli not available."""
        result = decode_body(b"fake brotli data", "br")
        assert result == b"fake brotli data"

    def test_decode_unknown_encoding(self):
        """Test unknown encoding returns body unchanged."""
        result = decode_body(b"test data", "unknown-encoding")
        assert result == b"test data"

    def test_decode_multiple_encodings(self):
        """Test multiple encodings are decoded in reverse order."""
        # First compress with gzip
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"hello world")
        gzipped = buf.getvalue()

        # Per HTTP spec, encodings are applied in order listed and decoded in reverse
        # So "gzip, deflate" means: server applied gzip first, then deflate
        # We decode: deflate first, then gzip
        deflated = zlib.compress(gzipped)

        result = decode_body(deflated, "gzip, deflate")
        assert result == b"hello world"

    def test_decode_gzip_invalid_data(self):
        """Test invalid gzip data returns original."""
        result = decode_body(b"not gzip data", "gzip")
        assert result == b"not gzip data"

    def test_decode_deflate_invalid_data(self):
        """Test invalid deflate data returns original."""
        result = decode_body(b"not deflate data", "deflate")
        assert result == b"not deflate data"

    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="brotli not installed")
    def test_decode_brotli_invalid_data(self):
        """Test invalid brotli data returns original."""
        result = decode_body(b"not brotli data", "br")
        assert result == b"not brotli data"

    def test_decode_case_insensitive(self):
        """Test encoding is case-insensitive."""
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"hello")
        compressed = buf.getvalue()

        result = decode_body(compressed, "GZIP")
        assert result == b"hello"

    def test_decode_whitespace_handling(self):
        """Test whitespace in encoding is handled."""
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"hello")
        compressed = buf.getvalue()

        result = decode_body(compressed, "  gzip  ")
        assert result == b"hello"


class TestDecodeSingle:
    """Tests for _decode_single function."""

    def test_decode_single_gzip(self):
        """Test single gzip decoding."""
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"test")
        compressed = buf.getvalue()

        result = _decode_single(compressed, "gzip")
        assert result == b"test"

    def test_decode_single_deflate(self):
        """Test single deflate decoding."""
        compressed = zlib.compress(b"test")
        result = _decode_single(compressed, "deflate")
        assert result == b"test"

    def test_decode_single_unknown(self):
        """Test unknown encoding returns unchanged."""
        result = _decode_single(b"data", "xyz")
        assert result == b"data"


class TestGetAcceptEncoding:
    """Tests for get_accept_encoding function."""

    def test_auto_decompress_false(self):
        """Test auto_decompress=False returns identity."""
        result = get_accept_encoding({}, auto_decompress=False)
        assert result == "identity"

    def test_auto_decompress_true_no_profile(self):
        """Test auto_decompress=True with no profile returns default."""
        result = get_accept_encoding({}, auto_decompress=True)
        assert result == DEFAULT_ACCEPT_ENCODING

    def test_profile_with_accept_encoding(self):
        """Test profile Accept-Encoding is used."""
        profile = {
            "headers": {
                "default": [
                    ("Accept-Encoding", "gzip, deflate"),
                ]
            }
        }
        result = get_accept_encoding(profile, auto_decompress=True)
        assert result == "gzip, deflate"

    def test_profile_without_headers(self):
        """Test profile without headers returns default."""
        profile = {"tls": {}}
        result = get_accept_encoding(profile, auto_decompress=True)
        assert result == DEFAULT_ACCEPT_ENCODING

    def test_profile_with_other_headers(self):
        """Test profile with other headers returns default."""
        profile = {
            "headers": {
                "default": [
                    ("User-Agent", "Test"),
                ]
            }
        }
        result = get_accept_encoding(profile, auto_decompress=True)
        assert result == DEFAULT_ACCEPT_ENCODING

    def test_accept_encoding_case_insensitive(self):
        """Test Accept-Encoding header name is case-insensitive."""
        profile = {
            "headers": {
                "default": [
                    ("ACCEPT-ENCODING", "gzip"),
                ]
            }
        }
        result = get_accept_encoding(profile, auto_decompress=True)
        assert result == "gzip"


class TestDefaultAcceptEncoding:
    """Tests for DEFAULT_ACCEPT_ENCODING constant."""

    def test_contains_gzip(self):
        """Test default includes gzip."""
        assert "gzip" in DEFAULT_ACCEPT_ENCODING

    def test_contains_deflate(self):
        """Test default includes deflate."""
        assert "deflate" in DEFAULT_ACCEPT_ENCODING

    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="brotli not installed")
    def test_contains_br_when_available(self):
        """Test default includes br when brotli available."""
        assert "br" in DEFAULT_ACCEPT_ENCODING

    @pytest.mark.skipif(BROTLI_AVAILABLE, reason="brotli is installed")
    def test_no_br_when_unavailable(self):
        """Test default does not include br when brotli unavailable."""
        assert "br" not in DEFAULT_ACCEPT_ENCODING


class TestBrotliAvailable:
    """Tests for BROTLI_AVAILABLE constant."""

    def test_is_boolean(self):
        """Test BROTLI_AVAILABLE is boolean."""
        assert isinstance(BROTLI_AVAILABLE, bool)
