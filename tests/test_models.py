"""Tests for gakido.models module."""

import json
import pytest
from gakido.models import Response


class TestResponse:
    """Tests for the Response class."""

    def test_response_basic_attributes(self):
        """Test basic response attributes."""
        resp = Response(
            status_code=200,
            reason="OK",
            http_version="1.1",
            headers=[("Content-Type", "text/html")],
            body=b"Hello World",
        )
        assert resp.status_code == 200
        assert resp.reason == "OK"
        assert resp.http_version == "1.1"
        assert resp.content == b"Hello World"

    def test_response_headers_case_insensitive(self):
        """Test headers dict is case-insensitive."""
        resp = Response(
            200, "OK", "1.1",
            headers=[("Content-Type", "text/html"), ("X-Custom-Header", "value")],
            body=b"",
        )
        assert resp.headers["content-type"] == "text/html"
        assert resp.headers["x-custom-header"] == "value"

    def test_response_headers_last_write_wins(self):
        """Test that duplicate headers use last value."""
        resp = Response(
            200, "OK", "1.1",
            headers=[("X-Header", "first"), ("X-Header", "second")],
            body=b"",
        )
        assert resp.headers["x-header"] == "second"

    def test_response_raw_headers_preserved(self):
        """Test raw_headers preserves original order and case."""
        headers = [("Content-Type", "text/html"), ("X-Custom", "value")]
        resp = Response(200, "OK", "1.1", headers=headers, body=b"")
        assert resp.raw_headers == headers

    def test_response_text_default_utf8(self):
        """Test text property defaults to UTF-8."""
        resp = Response(200, "OK", "1.1", headers=[], body=b"Hello")
        assert resp.text == "Hello"

    def test_response_text_with_charset(self):
        """Test text property respects charset in content-type."""
        resp = Response(
            200, "OK", "1.1",
            headers=[("Content-Type", "text/html; charset=latin-1")],
            body="Hëllo".encode("latin-1"),
        )
        assert resp.text == "Hëllo"

    def test_response_text_invalid_charset_fallback(self):
        """Test text falls back to UTF-8 for invalid charset."""
        resp = Response(
            200, "OK", "1.1",
            headers=[("Content-Type", "text/html; charset=invalid-charset")],
            body=b"Hello",
        )
        assert resp.text == "Hello"

    def test_response_text_decodes_with_errors_replace(self):
        """Test text handles invalid bytes gracefully."""
        resp = Response(200, "OK", "1.1", headers=[], body=b"\xff\xfe")
        # Should not raise, uses errors="replace"
        assert isinstance(resp.text, str)

    def test_response_json(self):
        """Test json method parses JSON body."""
        data = {"key": "value", "number": 42}
        resp = Response(
            200, "OK", "1.1",
            headers=[("Content-Type", "application/json")],
            body=json.dumps(data).encode(),
        )
        assert resp.json() == data

    def test_response_json_invalid_raises(self):
        """Test json method raises on invalid JSON."""
        resp = Response(200, "OK", "1.1", headers=[], body=b"not json")
        with pytest.raises(json.JSONDecodeError):
            resp.json()

    def test_response_repr(self):
        """Test response repr format."""
        resp = Response(200, "OK", "1.1", headers=[], body=b"12345")
        assert repr(resp) == "<Response [200] 5 bytes>"

    def test_response_empty_body(self):
        """Test response with empty body."""
        resp = Response(204, "No Content", "1.1", headers=[], body=b"")
        assert resp.content == b""
        assert resp.text == ""

    def test_response_content_property(self):
        """Test content property returns body bytes."""
        body = b"\x00\x01\x02\x03"
        resp = Response(200, "OK", "1.1", headers=[], body=body)
        assert resp.content == body
        assert isinstance(resp.content, bytes)
