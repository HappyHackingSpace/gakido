"""Tests for gakido.cookies module."""

import pytest
from gakido.cookies import CookieJar


class TestCookieJar:
    """Tests for CookieJar class."""

    def test_empty_jar(self):
        """Test empty cookie jar returns None for header."""
        jar = CookieJar()
        assert jar.cookie_header("example.com") is None

    def test_set_single_cookie(self):
        """Test setting a single cookie."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123")]
        jar.set_from_headers(headers, "example.com")

        assert jar.cookie_header("example.com") == "session=abc123"

    def test_set_multiple_cookies(self):
        """Test setting multiple cookies."""
        jar = CookieJar()
        headers = [
            ("Set-Cookie", "session=abc123"),
            ("Set-Cookie", "user=john"),
        ]
        jar.set_from_headers(headers, "example.com")

        cookie = jar.cookie_header("example.com")
        assert "session=abc123" in cookie
        assert "user=john" in cookie

    def test_cookies_are_host_scoped(self):
        """Test cookies are scoped to host."""
        jar = CookieJar()
        jar.set_from_headers([("Set-Cookie", "a=1")], "example.com")
        jar.set_from_headers([("Set-Cookie", "b=2")], "other.com")

        assert jar.cookie_header("example.com") == "a=1"
        assert jar.cookie_header("other.com") == "b=2"
        assert jar.cookie_header("unknown.com") is None

    def test_cookie_overwrite(self):
        """Test setting same cookie name overwrites."""
        jar = CookieJar()
        jar.set_from_headers([("Set-Cookie", "session=old")], "example.com")
        jar.set_from_headers([("Set-Cookie", "session=new")], "example.com")

        assert jar.cookie_header("example.com") == "session=new"

    def test_ignores_non_set_cookie_headers(self):
        """Test non Set-Cookie headers are ignored."""
        jar = CookieJar()
        headers = [
            ("Content-Type", "text/html"),
            ("Set-Cookie", "session=abc"),
            ("X-Custom", "value"),
        ]
        jar.set_from_headers(headers, "example.com")

        assert jar.cookie_header("example.com") == "session=abc"

    def test_cookie_with_attributes(self):
        """Test cookie with attributes (Path, Expires, etc)."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc; Path=/; HttpOnly; Secure")]
        jar.set_from_headers(headers, "example.com")

        # Only the name=value should be in the header
        assert jar.cookie_header("example.com") == "session=abc"

    def test_repr(self):
        """Test CookieJar repr."""
        jar = CookieJar()
        jar.set_from_headers([("Set-Cookie", "a=1")], "example.com")

        repr_str = repr(jar)
        assert "Cookies" in repr_str
        assert "example.com" in repr_str

    def test_multiple_hosts_isolated(self):
        """Test cookies for different hosts don't mix."""
        jar = CookieJar()
        jar.set_from_headers([("Set-Cookie", "token=xyz")], "api.example.com")
        jar.set_from_headers([("Set-Cookie", "token=abc")], "www.example.com")

        assert jar.cookie_header("api.example.com") == "token=xyz"
        assert jar.cookie_header("www.example.com") == "token=abc"

    def test_empty_headers_list(self):
        """Test empty headers list doesn't raise."""
        jar = CookieJar()
        jar.set_from_headers([], "example.com")
        assert jar.cookie_header("example.com") is None

    def test_cookie_header_format(self):
        """Test cookie header format with multiple cookies."""
        jar = CookieJar()
        jar.set_from_headers([
            ("Set-Cookie", "a=1"),
            ("Set-Cookie", "b=2"),
            ("Set-Cookie", "c=3"),
        ], "example.com")

        cookie = jar.cookie_header("example.com")
        # Should be semicolon-separated
        assert "; " in cookie
        parts = cookie.split("; ")
        assert len(parts) == 3
