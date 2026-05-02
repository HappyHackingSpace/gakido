"""Tests for cookie handling and persistence functionality."""

import json
import time

import pytest

from gakido.cookies import CookieJar


class TestCookieJarBasic:
    """Tests for basic CookieJar operations."""

    def test_set_from_headers_simple(self):
        """Test parsing simple Set-Cookie header."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; Path=/")]

        jar.set_from_headers(headers, "example.com")

        header = jar.cookie_header("example.com")
        assert header == "session=abc123"

    def test_set_from_headers_multiple(self):
        """Test parsing multiple Set-Cookie headers."""
        jar = CookieJar()
        headers = [
            ("Set-Cookie", "session=abc123; Path=/"),
            ("Set-Cookie", "user=john; Path=/; HttpOnly"),
        ]

        jar.set_from_headers(headers, "example.com")

        header = jar.cookie_header("example.com")
        assert "session=abc123" in header
        assert "user=john" in header

    def test_cookie_header_no_cookies(self):
        """Test cookie_header returns None when no cookies."""
        jar = CookieJar()
        header = jar.cookie_header("example.com")
        assert header is None

    def test_cookie_header_wrong_host(self):
        """Test cookie_header returns None for wrong host."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123")]
        jar.set_from_headers(headers, "example.com")

        header = jar.cookie_header("other.com")
        assert header is None

    def test_non_set_cookie_headers_ignored(self):
        """Test that non-Set-Cookie headers are ignored."""
        jar = CookieJar()
        headers = [
            ("Content-Type", "text/html"),
            ("Set-Cookie", "session=abc123"),
        ]

        jar.set_from_headers(headers, "example.com")

        header = jar.cookie_header("example.com")
        assert header == "session=abc123"


class TestCookieJarExpiration:
    """Tests for cookie expiration handling."""

    def test_expired_cookies_not_included(self):
        """Test that expired cookies are not included in header."""
        jar = CookieJar()
        # Cookie expired 1 hour ago
        jar.store["example.com"] = {
            "expired_cookie": {
                "value": "old",
                "expires": time.time() - 3600,
                "path": "/",
            }
        }

        header = jar.cookie_header("example.com")
        assert header is None

    def test_expired_cookies_removed_from_store(self):
        """Test that expired cookies are cleaned up."""
        jar = CookieJar()
        jar.store["example.com"] = {
            "valid": {"value": "ok", "expires": time.time() + 3600, "path": "/"},
            "expired": {"value": "old", "expires": time.time() - 3600, "path": "/"},
        }

        jar.cookie_header("example.com")

        assert "expired" not in jar.store.get("example.com", {})
        assert "valid" in jar.store.get("example.com", {})

    def test_max_age_parsed(self):
        """Test that Max-Age directive is parsed correctly."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; Max-Age=3600; Path=/")]

        jar.set_from_headers(headers, "example.com")

        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["expires"] is not None
        # Should expire approximately 1 hour from now
        assert cookie_data["expires"] > time.time() + 3590
        assert cookie_data["expires"] < time.time() + 3610

    def test_expires_parsed(self):
        """Test that Expires directive is parsed correctly."""
        jar = CookieJar()
        # Use RFC 6265 format: <day-name>, <day> <month> <year> <hour>:<minute>:<second> GMT
        # Example: Wed, 21 Oct 2025 07:28:00 GMT
        from datetime import datetime, timezone
        future_time = datetime.fromtimestamp(time.time() + 3600, tz=timezone.utc)
        exp_str = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

        headers = [("Set-Cookie", f"session=abc123; Expires={exp_str}; Path=/")]
        jar.set_from_headers(headers, "example.com")

        assert "example.com" in jar.store
        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["expires"] is not None

    def test_session_cookie_no_expiration(self):
        """Test that session cookies have no expiration."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; Path=/")]

        jar.set_from_headers(headers, "example.com")

        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["expires"] is None


class TestCookieJarDomainHandling:
    """Tests for domain cookie handling."""

    def test_domain_cookie_matches_subdomains(self):
        """Test that domain cookies apply to subdomains."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; Domain=.example.com; Path=/")]

        jar.set_from_headers(headers, "www.example.com")

        # Should match www.example.com
        header = jar.cookie_header("www.example.com")
        assert "session=abc123" in header

        # Should also match other subdomains
        header = jar.cookie_header("api.example.com")
        assert "session=abc123" in header

    def test_host_only_cookie_not_shared(self):
        """Test that host-only cookies don't apply to subdomains."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; Path=/")]

        jar.set_from_headers(headers, "www.example.com")

        # Should match exact host
        header = jar.cookie_header("www.example.com")
        assert header == "session=abc123"

        # Should NOT match subdomains
        header = jar.cookie_header("api.example.com")
        assert header is None

    def test_domain_cookie_host_precedence(self):
        """Test that host-only cookies take precedence over domain cookies."""
        jar = CookieJar()

        # Set domain cookie
        jar.set_from_headers(
            [("Set-Cookie", "session=domain; Domain=.example.com; Path=/")],
            "www.example.com"
        )

        # Set host-only cookie with same name
        jar.set_from_headers(
            [("Set-Cookie", "session=host; Path=/")],
            "www.example.com"
        )

        header = jar.cookie_header("www.example.com")
        # Should use host-only value
        assert "session=host" in header
        assert "session=domain" not in header


class TestCookieJarPersistence:
    """Tests for cookie persistence to/from JSON file."""

    def test_save_creates_file(self, tmp_path):
        """Test that save_cookies creates the file."""
        cookie_file = tmp_path / "cookies.json"
        jar = CookieJar()
        jar.store["example.com"] = {"session": {"value": "abc123", "path": "/", "expires": None}}

        jar.save_cookies(cookie_file)

        assert cookie_file.exists()

    def test_save_and_load(self, tmp_path):
        """Test saving and loading cookies."""
        cookie_file = tmp_path / "cookies.json"

        # Save cookies
        jar1 = CookieJar()
        jar1.store["example.com"] = {"session": {"value": "abc123", "path": "/", "expires": None}}
        jar1.save_cookies(cookie_file)

        # Load cookies
        jar2 = CookieJar()
        jar2.load_cookies(cookie_file)

        header = jar2.cookie_header("example.com")
        assert header == "session=abc123"

    def test_load_from_constructor(self, tmp_path):
        """Test loading cookies from file in constructor."""
        cookie_file = tmp_path / "cookies.json"

        # Create and save cookies
        jar1 = CookieJar()
        jar1.store["example.com"] = {"session": {"value": "abc123", "path": "/", "expires": None}}
        jar1.save_cookies(cookie_file)

        # Load via constructor
        jar2 = CookieJar(cookie_file=cookie_file)

        header = jar2.cookie_header("example.com")
        assert header == "session=abc123"

    def test_save_filters_expired_cookies(self, tmp_path):
        """Test that expired cookies are not saved."""
        cookie_file = tmp_path / "cookies.json"
        jar = CookieJar()

        # Add valid and expired cookies
        jar.store["example.com"] = {
            "valid": {"value": "ok", "path": "/", "expires": time.time() + 3600},
            "expired": {"value": "old", "path": "/", "expires": time.time() - 3600},
        }

        jar.save_cookies(cookie_file)

        # Load and check
        with open(cookie_file) as f:
            data = json.load(f)

        assert "valid" in data["example.com"]
        assert "expired" not in data["example.com"]

    def test_load_filters_expired_cookies(self, tmp_path):
        """Test that expired cookies are filtered when loading."""
        cookie_file = tmp_path / "cookies.json"

        # Create file with valid and expired cookies
        data = {
            "example.com": {
                "valid": {"value": "ok", "path": "/", "expires": time.time() + 3600},
                "expired": {"value": "old", "path": "/", "expires": time.time() - 3600},
            }
        }
        with open(cookie_file, "w") as f:
            json.dump(data, f)

        # Load
        jar = CookieJar()
        jar.load_cookies(cookie_file)

        assert "valid" in jar.store.get("example.com", {})
        assert "expired" not in jar.store.get("example.com", {})

    def test_save_file_permissions(self, tmp_path):
        """Test that saved file has restrictive permissions."""
        cookie_file = tmp_path / "cookies.json"
        jar = CookieJar()
        jar.store["example.com"] = {"session": {"value": "abc123", "path": "/", "expires": None}}

        jar.save_cookies(cookie_file)

        # Check file permissions (0o600 = user read/write only)
        import stat
        mode = stat.S_IMODE(cookie_file.stat().st_mode)
        assert mode == 0o600

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from non-existent file is no-op."""
        cookie_file = tmp_path / "nonexistent.json"
        jar = CookieJar()

        # Should not raise
        jar.load_cookies(cookie_file)

        assert jar.store == {}

    def test_load_corrupted_file(self, tmp_path):
        """Test loading from corrupted JSON file."""
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text("not valid json")

        jar = CookieJar()

        # Should not raise, just start with empty jar
        jar.load_cookies(cookie_file)

        assert jar.store == {}

    def test_clear_cookies(self, tmp_path):
        """Test clearing cookies from memory and file."""
        cookie_file = tmp_path / "cookies.json"
        jar = CookieJar(cookie_file=cookie_file)

        jar.set_from_headers([("Set-Cookie", "session=abc123")], "example.com")
        jar.save_cookies()

        assert cookie_file.exists()

        jar.clear_cookies()

        assert jar.store == {}
        assert not cookie_file.exists()

    def test_expands_user_directory(self, tmp_path, monkeypatch):
        """Test that ~ is expanded in cookie file path."""
        monkeypatch.setenv("HOME", str(tmp_path))

        jar = CookieJar(cookie_file="~/.gakido/cookies.json")

        assert jar._cookie_file == tmp_path / ".gakido" / "cookies.json"

    def test_save_no_file_raises(self):
        """Test that save without file path raises error."""
        jar = CookieJar()

        with pytest.raises(ValueError, match="No cookie file specified"):
            jar.save_cookies()


class TestCookieJarMetadata:
    """Tests for cookie metadata handling."""

    def test_secure_flag_stored(self):
        """Test that Secure flag is stored."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; Secure; Path=/")]

        jar.set_from_headers(headers, "example.com")

        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["secure"] is True

    def test_httponly_flag_stored(self):
        """Test that HttpOnly flag is stored."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; HttpOnly; Path=/")]

        jar.set_from_headers(headers, "example.com")

        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["httponly"] is True

    def test_samesite_stored(self):
        """Test that SameSite attribute is stored."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; SameSite=Strict; Path=/")]

        jar.set_from_headers(headers, "example.com")

        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["samesite"] == "Strict"

    def test_path_stored(self):
        """Test that Path attribute is stored."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123; Path=/api")]

        jar.set_from_headers(headers, "example.com")

        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["path"] == "/api"

    def test_default_path(self):
        """Test that default path is /."""
        jar = CookieJar()
        headers = [("Set-Cookie", "session=abc123")]

        jar.set_from_headers(headers, "example.com")

        cookie_data = jar.store["example.com"]["session"]
        assert cookie_data["path"] == "/"


class TestCookieJarRepresentation:
    """Tests for string representation."""

    def test_repr_empty(self):
        """Test repr of empty jar."""
        jar = CookieJar()
        assert repr(jar) == "<CookieJar hosts=0 cookies=0>"

    def test_repr_with_cookies(self):
        """Test repr with cookies."""
        jar = CookieJar()
        jar.store["example.com"] = {
            "a": {"value": "1", "path": "/"},
            "b": {"value": "2", "path": "/"},
        }
        jar.store["other.com"] = {
            "c": {"value": "3", "path": "/"},
        }

        assert repr(jar) == "<CookieJar hosts=2 cookies=3>"
