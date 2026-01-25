"""Tests for gakido.headers module."""

import pytest
from gakido.headers import canonicalize_headers, _sanitize_header


class TestCanonicalizeHeaders:
    """Tests for canonicalize_headers function."""

    def test_header_ordering_merges_and_respects_order(self):
        """Test headers are merged and ordered correctly."""
        default = [("User-Agent", "ua"), ("Accept", "*/*")]
        user = {"Accept": "json", "X-Test": "1"}
        order = ["Accept", "User-Agent", "X-Test"]
        merged = canonicalize_headers(default, user, order)
        assert merged == [
            ("Accept", "json"),
            ("User-Agent", "ua"),
            ("X-Test", "1"),
        ]

    def test_empty_defaults(self):
        """Test with empty default headers."""
        merged = canonicalize_headers([], {"X-Test": "1"}, ["X-Test"])
        assert merged == [("X-Test", "1")]

    def test_empty_user_headers(self):
        """Test with no user headers."""
        default = [("User-Agent", "ua")]
        merged = canonicalize_headers(default, None, ["User-Agent"])
        assert merged == [("User-Agent", "ua")]

    def test_empty_dict_user_headers(self):
        """Test with empty dict user headers."""
        default = [("User-Agent", "ua")]
        merged = canonicalize_headers(default, {}, ["User-Agent"])
        assert merged == [("User-Agent", "ua")]

    def test_empty_order(self):
        """Test with empty order list."""
        default = [("A", "1"), ("B", "2")]
        user = {"C": "3"}
        merged = canonicalize_headers(default, user, [])
        # All headers should be present but unordered
        keys = [h[0] for h in merged]
        assert "A" in keys
        assert "B" in keys
        assert "C" in keys

    def test_case_insensitive_merge(self):
        """Test header names are merged case-insensitively."""
        default = [("Content-Type", "text/html")]
        user = {"content-type": "application/json"}
        merged = canonicalize_headers(default, user, ["Content-Type"])
        # User value should win
        assert len(merged) == 1
        assert merged[0][1] == "application/json"

    def test_case_insensitive_ordering(self):
        """Test ordering is case-insensitive."""
        default = [("ACCEPT", "text/html")]
        merged = canonicalize_headers(default, None, ["accept"])
        assert merged == [("ACCEPT", "text/html")]

    def test_preserves_original_case(self):
        """Test original header name case is preserved."""
        default = [("X-Custom-Header", "value")]
        merged = canonicalize_headers(default, None, ["x-custom-header"])
        assert merged[0][0] == "X-Custom-Header"

    def test_user_overrides_default(self):
        """Test user headers override defaults."""
        default = [("Accept", "text/html")]
        user = {"Accept": "application/json"}
        merged = canonicalize_headers(default, user, ["Accept"])
        assert merged[0][1] == "application/json"

    def test_unordered_headers_appended(self):
        """Test headers not in order list are appended."""
        default = [("A", "1")]
        user = {"B": "2", "C": "3"}
        order = ["A"]
        merged = canonicalize_headers(default, user, order)
        # A should be first, B and C after
        assert merged[0] == ("A", "1")
        remaining = merged[1:]
        keys = [h[0] for h in remaining]
        assert "B" in keys
        assert "C" in keys

    def test_multiple_defaults_same_key(self):
        """Test multiple defaults with same key use last."""
        default = [("Accept", "first"), ("Accept", "second")]
        merged = canonicalize_headers(default, None, ["Accept"])
        # Last one wins
        assert merged == [("Accept", "second")]

    def test_complex_ordering(self):
        """Test complex ordering scenario."""
        default = [
            ("Host", "example.com"),
            ("User-Agent", "test"),
            ("Accept", "text/html"),
        ]
        user = {
            "Accept": "application/json",
            "X-Custom": "value",
        }
        order = ["Host", "Accept", "User-Agent", "X-Custom"]
        merged = canonicalize_headers(default, user, order)

        expected_order = ["Host", "Accept", "User-Agent", "X-Custom"]
        actual_order = [h[0] for h in merged]
        assert actual_order == expected_order

    def test_order_with_missing_headers(self):
        """Test order list with headers not present."""
        default = [("A", "1")]
        order = ["Z", "A", "Y"]  # Z and Y don't exist
        merged = canonicalize_headers(default, None, order)
        # Should only have A
        assert merged == [("A", "1")]


class TestSanitizeHeader:
    """Tests for the _sanitize_header function."""

    def test_clean_header_unchanged(self):
        """Clean headers should pass through unchanged."""
        name, value = _sanitize_header("Content-Type", "application/json")
        assert name == "Content-Type"
        assert value == "application/json"

    def test_crlf_in_value_stripped(self):
        """CRLF sequences in header values should be stripped."""
        name, value = _sanitize_header("User-Agent", "test\r\nX-Injected: pwned")
        assert name == "User-Agent"
        assert value == "testX-Injected: pwned"
        assert "\r" not in value
        assert "\n" not in value

    def test_crlf_in_name_stripped(self):
        """CRLF sequences in header names should be stripped."""
        name, value = _sanitize_header("User-Agent\r\nX-Injected", "pwned")
        assert name == "User-AgentX-Injected"
        assert value == "pwned"
        assert "\r" not in name
        assert "\n" not in name

    def test_lf_only_stripped(self):
        """LF-only sequences should be stripped."""
        name, value = _sanitize_header("User-Agent", "test\nX-Injected: pwned")
        assert value == "testX-Injected: pwned"
        assert "\n" not in value

    def test_cr_only_stripped(self):
        """CR-only sequences should be stripped."""
        name, value = _sanitize_header("User-Agent", "test\rX-Injected: pwned")
        assert value == "testX-Injected: pwned"
        assert "\r" not in value

    def test_null_byte_stripped(self):
        """Null bytes should be stripped."""
        name, value = _sanitize_header("User-Agent", "test\x00X-Injected: pwned")
        assert value == "testX-Injected: pwned"
        assert "\x00" not in value

    def test_multiple_crlf_stripped(self):
        """Multiple CRLF sequences should all be stripped."""
        name, value = _sanitize_header(
            "Header",
            "value1\r\nHeader2: value2\r\nHeader3: value3"
        )
        assert value == "value1Header2: value2Header3: value3"
        assert "\r" not in value
        assert "\n" not in value

    def test_mixed_injection_chars_stripped(self):
        """Mixed injection characters should all be stripped."""
        name, value = _sanitize_header(
            "Header\r\n\x00Evil",
            "value\r\n\x00\r\ninjected"
        )
        assert "\r" not in name
        assert "\n" not in name
        assert "\x00" not in name
        assert "\r" not in value
        assert "\n" not in value
        assert "\x00" not in value

    def test_empty_header_unchanged(self):
        """Empty headers should remain empty."""
        name, value = _sanitize_header("", "")
        assert name == ""
        assert value == ""

    def test_only_crlf_becomes_empty(self):
        """Header with only CRLF chars should become empty."""
        name, value = _sanitize_header("\r\n", "\r\n\r\n")
        assert name == ""
        assert value == ""


class TestCanonicalizeHeadersInjection:
    """Tests for header injection prevention in canonicalize_headers."""

    def test_user_header_crlf_sanitized(self):
        """User-provided headers with CRLF should be sanitized."""
        default_headers = [("Accept", "text/html")]
        user_headers = {"User-Agent": "test\r\nX-Injected: pwned"}
        order = ["Accept", "User-Agent"]

        result = canonicalize_headers(default_headers, user_headers, order)

        # Find User-Agent in result
        ua_value = None
        for name, value in result:
            if name == "User-Agent":
                ua_value = value
                break

        assert ua_value is not None
        assert "\r" not in ua_value
        assert "\n" not in ua_value
        assert ua_value == "testX-Injected: pwned"

    def test_default_header_crlf_sanitized(self):
        """Default headers with CRLF should be sanitized."""
        default_headers = [("User-Agent", "test\r\nX-Injected: pwned")]
        user_headers = None
        order = ["User-Agent"]

        result = canonicalize_headers(default_headers, user_headers, order)

        ua_value = result[0][1]
        assert "\r" not in ua_value
        assert "\n" not in ua_value

    def test_header_name_injection_sanitized(self):
        """Header names with CRLF should be sanitized."""
        default_headers = []
        user_headers = {"X-Custom\r\nX-Injected": "value"}
        order = []

        result = canonicalize_headers(default_headers, user_headers, order)

        # Check that no header name contains CRLF
        for name, value in result:
            assert "\r" not in name
            assert "\n" not in name

    def test_no_separate_injected_header(self):
        """CRLF injection should not create separate headers."""
        default_headers = []
        user_headers = {"User-Agent": "Mozilla\r\nX-Injected: pwned\r\nX-Another: header"}
        order = []

        result = canonicalize_headers(default_headers, user_headers, order)

        # Should only have one header, not three
        assert len(result) == 1

        # Check no header named X-Injected or X-Another exists
        header_names = [name.lower() for name, _ in result]
        assert "x-injected" not in header_names
        assert "x-another" not in header_names


class TestInjectionPayloads:
    """Test various known injection payloads."""

    @pytest.mark.parametrize("payload,description", [
        # Basic CRLF
        ("test\r\nX-Injected: pwned", "Basic CRLF injection"),
        ("test\r\n\r\n<html>body</html>", "CRLF with body injection"),

        # LF only (Unix-style)
        ("test\nX-Injected: pwned", "LF-only injection"),
        ("test\n\n<html>body</html>", "LF-only with body"),

        # CR only
        ("test\rX-Injected: pwned", "CR-only injection"),

        # Null byte
        ("test\x00X-Injected: pwned", "Null byte injection"),

        # Multiple injections
        ("test\r\nHeader1: val1\r\nHeader2: val2", "Multiple header injection"),

        # URL encoded (should NOT be decoded - these are literal chars)
        ("test%0d%0aX-Injected: pwned", "URL encoded CRLF (literal)"),

        # Mixed
        ("test\r\n\x00\nX-Injected: pwned", "Mixed injection chars"),

        # At start
        ("\r\nX-Injected: pwned", "CRLF at start"),

        # At end
        ("test\r\n", "CRLF at end"),

        # Only CRLF
        ("\r\n\r\n", "Only CRLF chars"),

        # Unicode variations (should pass through - not injection)
        ("test\u000d\u000aX-Injected: pwned", "Unicode CRLF"),

        # HTTP/2 pseudo-header injection attempt
        (":path\r\n:authority: evil.com", "HTTP/2 pseudo-header injection"),

        # Cookie injection
        ("session=abc\r\nSet-Cookie: evil=value", "Cookie injection attempt"),

        # Host header injection
        ("example.com\r\nHost: evil.com", "Host header injection"),

        # Content-Length injection
        ("100\r\nContent-Length: 0", "Content-Length injection"),

        # Transfer-Encoding injection
        ("gzip\r\nTransfer-Encoding: chunked", "Transfer-Encoding injection"),
    ])
    def test_injection_payload_sanitized(self, payload, description):
        """Test that various injection payloads are properly sanitized."""
        name, value = _sanitize_header("Test-Header", payload)

        assert "\r" not in value, f"CR found in sanitized value for: {description}"
        assert "\n" not in value, f"LF found in sanitized value for: {description}"
        assert "\x00" not in value, f"Null byte found in sanitized value for: {description}"

    @pytest.mark.parametrize("header_name,description", [
        ("X-Custom\r\nX-Injected", "CRLF in header name"),
        ("X-Custom\nX-Injected", "LF in header name"),
        ("X-Custom\rX-Injected", "CR in header name"),
        ("X-Custom\x00X-Injected", "Null in header name"),
        ("\r\nX-Injected", "CRLF at start of name"),
        ("X-Custom\r\n", "CRLF at end of name"),
    ])
    def test_header_name_injection_sanitized(self, header_name, description):
        """Test that header name injection payloads are sanitized."""
        name, value = _sanitize_header(header_name, "value")

        assert "\r" not in name, f"CR found in sanitized name for: {description}"
        assert "\n" not in name, f"LF found in sanitized name for: {description}"
        assert "\x00" not in name, f"Null byte found in sanitized name for: {description}"


class TestRealWorldScenarios:
    """Test real-world attack scenarios."""

    def test_response_splitting_prevented(self):
        """HTTP response splitting attack should be prevented."""
        # Attacker tries to inject a complete HTTP response
        payload = "legitimate\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>evil</html>"
        name, value = _sanitize_header("X-Redirect", payload)

        assert "HTTP/1.1" not in value or "\r" not in value
        assert "\r" not in value
        assert "\n" not in value

    def test_cache_poisoning_prevented(self):
        """Cache poisoning via header injection should be prevented."""
        payload = "value\r\nX-Cache-Status: HIT\r\nAge: 0"
        name, value = _sanitize_header("X-Custom", payload)

        assert "\r" not in value
        assert "\n" not in value

    def test_session_fixation_prevented(self):
        """Session fixation via Set-Cookie injection should be prevented."""
        payload = "value\r\nSet-Cookie: session=attacker_controlled"
        name, value = _sanitize_header("X-Custom", payload)

        assert "\r" not in value
        assert "\n" not in value

    def test_xss_via_header_prevented(self):
        """XSS via header injection should be prevented."""
        payload = "value\r\nContent-Type: text/html\r\n\r\n<script>alert(1)</script>"
        name, value = _sanitize_header("X-Custom", payload)

        assert "\r" not in value
        assert "\n" not in value

    def test_smuggling_attempt_prevented(self):
        """HTTP request smuggling attempt should be prevented."""
        payload = "value\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\nGET /admin HTTP/1.1"
        name, value = _sanitize_header("X-Custom", payload)

        assert "\r" not in value
        assert "\n" not in value
