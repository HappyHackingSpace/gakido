"""Tests for gakido.headers module."""

import pytest
from gakido.headers import canonicalize_headers


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
