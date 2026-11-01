"""Tests for gakido.redirects module."""

import pytest

from gakido.errors import CircularRedirectError, TooManyRedirectsError
from gakido.models import Response
from gakido.redirects import (
    RedirectTracker,
    is_redirect,
    prepare_redirect,
    redirect_method,
    strip_sensitive_headers,
)


def make_redirect(status_code, location):
    return Response(status_code, "", "1.1", [("Location", location)], b"")


class TestIsRedirect:
    """Tests for is_redirect helper."""

    @pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
    def test_redirect_statuses_with_location(self, status_code):
        """Test 3xx responses with Location header are redirects."""
        assert is_redirect(make_redirect(status_code, "/next")) is True

    def test_redirect_status_without_location(self):
        """Test 3xx response without Location header is not followed."""
        response = Response(301, "Moved", "1.1", [], b"")
        assert is_redirect(response) is False

    @pytest.mark.parametrize("status_code", [200, 204, 304, 400, 404, 500])
    def test_non_redirect_statuses(self, status_code):
        """Test non-redirect statuses are not redirects."""
        assert is_redirect(make_redirect(status_code, "/next")) is False


class TestRedirectMethod:
    """Tests for redirect_method helper."""

    def test_303_switches_to_get(self):
        """Test 303 switches POST/PUT to GET."""
        assert redirect_method("POST", 303) == "GET"
        assert redirect_method("PUT", 303) == "GET"

    def test_303_preserves_head(self):
        """Test 303 keeps HEAD as HEAD."""
        assert redirect_method("HEAD", 303) == "HEAD"

    @pytest.mark.parametrize("status_code", [301, 302])
    def test_301_302_downgrade_post_to_get(self, status_code):
        """Test 301/302 downgrade POST to GET like browsers."""
        assert redirect_method("POST", status_code) == "GET"

    @pytest.mark.parametrize("status_code", [301, 302])
    def test_301_302_preserve_other_methods(self, status_code):
        """Test 301/302 keep non-POST methods."""
        assert redirect_method("GET", status_code) == "GET"
        assert redirect_method("PUT", status_code) == "PUT"

    @pytest.mark.parametrize("status_code", [307, 308])
    def test_307_308_preserve_method(self, status_code):
        """Test 307/308 always preserve the method."""
        assert redirect_method("POST", status_code) == "POST"
        assert redirect_method("DELETE", status_code) == "DELETE"


class TestPrepareRedirect:
    """Tests for prepare_redirect helper."""

    def test_relative_location_resolved(self):
        """Test relative Location is resolved against the current URL."""
        response = make_redirect(302, "/other")
        method, url, keep_body = prepare_redirect(
            "GET", "https://example.com/start", response
        )
        assert method == "GET"
        assert url == "https://example.com/other"
        assert keep_body is True

    def test_absolute_location_used_verbatim(self):
        """Test absolute Location replaces the URL entirely."""
        response = make_redirect(301, "https://other.com/path")
        _, url, _ = prepare_redirect("GET", "https://example.com/start", response)
        assert url == "https://other.com/path"

    def test_body_dropped_when_method_changes(self):
        """Test body is dropped when POST is downgraded to GET."""
        response = make_redirect(303, "/done")
        method, _, keep_body = prepare_redirect(
            "POST", "https://example.com/form", response
        )
        assert method == "GET"
        assert keep_body is False

    def test_body_kept_for_307(self):
        """Test 307 keeps the method and body."""
        response = make_redirect(307, "/retry")
        method, _, keep_body = prepare_redirect(
            "POST", "https://example.com/form", response
        )
        assert method == "POST"
        assert keep_body is True


class TestStripSensitiveHeaders:
    """Tests for strip_sensitive_headers helper."""

    def test_same_host_keeps_headers(self):
        """Test headers are untouched when the host does not change."""
        headers = {"Authorization": "Bearer x", "X-Custom": "1"}
        result = strip_sensitive_headers(
            headers, "https://example.com/a", "https://example.com/b"
        )
        assert result == headers

    def test_cross_host_drops_credentials(self):
        """Test Authorization/Cookie are dropped on cross-host redirects."""
        headers = {"Authorization": "Bearer x", "Cookie": "a=b", "X-Custom": "1"}
        result = strip_sensitive_headers(
            headers, "https://example.com/a", "https://other.com/b"
        )
        assert result == {"X-Custom": "1"}

    def test_none_headers_pass_through(self):
        """Test None headers stay None."""
        assert (
            strip_sensitive_headers(None, "https://a.com", "https://b.com") is None
        )


class TestRedirectTracker:
    """Tests for RedirectTracker."""

    def test_follows_within_limit(self):
        """Test hops within the limit are recorded without error."""
        tracker = RedirectTracker("GET", "https://example.com/0", max_redirects=3)
        for i in range(1, 4):
            tracker.follow(
                "GET", f"https://example.com/{i}", make_redirect(302, f"/{i}")
            )
        assert len(tracker.history) == 3

    def test_too_many_redirects_raises(self):
        """Test exceeding max_redirects raises TooManyRedirectsError."""
        tracker = RedirectTracker("GET", "https://example.com/0", max_redirects=2)
        tracker.follow("GET", "https://example.com/1", make_redirect(302, "/1"))
        tracker.follow("GET", "https://example.com/2", make_redirect(302, "/2"))
        with pytest.raises(TooManyRedirectsError, match="maximum of 2"):
            tracker.follow("GET", "https://example.com/3", make_redirect(302, "/3"))

    def test_zero_max_redirects_rejects_first_hop(self):
        """Test max_redirects=0 rejects any redirect."""
        tracker = RedirectTracker("GET", "https://example.com/0", max_redirects=0)
        with pytest.raises(TooManyRedirectsError):
            tracker.follow("GET", "https://example.com/1", make_redirect(302, "/1"))

    def test_circular_redirect_to_origin_raises(self):
        """Test redirecting back to the original URL raises CircularRedirectError."""
        tracker = RedirectTracker("GET", "https://example.com/a", max_redirects=10)
        tracker.follow("GET", "https://example.com/b", make_redirect(302, "/b"))
        with pytest.raises(CircularRedirectError, match="Circular redirect"):
            tracker.follow("GET", "https://example.com/a", make_redirect(302, "/a"))

    def test_circular_redirect_between_hops_raises(self):
        """Test a loop between intermediate hops is detected."""
        tracker = RedirectTracker("GET", "https://example.com/a", max_redirects=10)
        tracker.follow("GET", "https://example.com/b", make_redirect(302, "/b"))
        tracker.follow("GET", "https://example.com/c", make_redirect(302, "/c"))
        with pytest.raises(CircularRedirectError):
            tracker.follow("GET", "https://example.com/b", make_redirect(302, "/b"))

    def test_same_url_different_method_allowed(self):
        """Test revisiting a URL with a different method is not circular."""
        tracker = RedirectTracker("POST", "https://example.com/a", max_redirects=10)
        # 303 turns POST /a into GET /a: same URL, different method.
        tracker.follow("GET", "https://example.com/a", make_redirect(303, "/a"))
        assert len(tracker.history) == 1
