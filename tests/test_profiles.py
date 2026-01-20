"""Tests for gakido.impersonation.profiles module."""

import pytest
from gakido.impersonation import PROFILES, get_profile
from gakido.impersonation.profiles import ALIAS_MAP


class TestProfiles:
    """Tests for profile definitions."""

    def test_get_profile_returns_copy(self):
        """Test get_profile returns a deep copy."""
        profile = get_profile("chrome_120")
        profile["headers"]["default"][0] = ("User-Agent", "modified")
        # Original should be unchanged
        assert PROFILES["chrome_120"]["headers"]["default"][0][0] == "Connection"

    def test_get_profile_unknown_raises(self):
        """Test get_profile raises for unknown profile."""
        with pytest.raises(KeyError, match="Unknown impersonation profile"):
            get_profile("unknown_browser_999")

    def test_chrome_120_profile_exists(self):
        """Test chrome_120 profile exists and has required fields."""
        profile = get_profile("chrome_120")
        assert "tls" in profile
        assert "http2" in profile
        assert "headers" in profile

    def test_firefox_120_profile_exists(self):
        """Test firefox_120 profile exists."""
        profile = get_profile("firefox_120")
        assert "tls" in profile
        assert "headers" in profile

    def test_safari_170_profile_exists(self):
        """Test safari_170 profile exists."""
        profile = get_profile("safari_170")
        assert "tls" in profile

    def test_profile_has_tls_config(self):
        """Test profiles have TLS configuration."""
        for name in ["chrome_120", "firefox_120", "safari_170"]:
            profile = get_profile(name)
            tls = profile.get("tls", {})
            assert "ciphers" in tls or "alpn" in tls

    def test_profile_has_default_headers(self):
        """Test profiles have default headers."""
        for name in ["chrome_120", "firefox_120"]:
            profile = get_profile(name)
            headers = profile.get("headers", {})
            assert "default" in headers
            assert len(headers["default"]) > 0

    def test_profile_has_header_order(self):
        """Test profiles have header order."""
        for name in ["chrome_120", "firefox_120"]:
            profile = get_profile(name)
            headers = profile.get("headers", {})
            assert "order" in headers

    def test_profile_has_http3_config(self):
        """Test modern profiles have HTTP/3 config."""
        for name in ["chrome_120", "firefox_120", "safari_170"]:
            profile = get_profile(name)
            assert "http3" in profile
            h3 = profile["http3"]
            assert "max_stream_data" in h3
            assert "max_data" in h3

    def test_alias_map_resolves(self):
        """Test alias map entries resolve to base profiles."""
        for alias, target in ALIAS_MAP.items():
            assert target in PROFILES

    def test_aliases_accessible_via_get_profile(self):
        """Test aliases work with get_profile."""
        # Test a few aliases
        aliases = ["chrome99", "firefox133", "safari153"]
        for alias in aliases:
            if alias in ALIAS_MAP:
                profile = get_profile(alias)
                assert profile is not None

    def test_chrome_user_agent(self):
        """Test Chrome profile has Chrome user agent."""
        profile = get_profile("chrome_120")
        ua = None
        for name, value in profile["headers"]["default"]:
            if name.lower() == "user-agent":
                ua = value
                break
        assert ua is not None
        assert "Chrome" in ua

    def test_firefox_user_agent(self):
        """Test Firefox profile has Firefox user agent."""
        profile = get_profile("firefox_120")
        ua = None
        for name, value in profile["headers"]["default"]:
            if name.lower() == "user-agent":
                ua = value
                break
        assert ua is not None
        assert "Firefox" in ua

    def test_profile_alpn_values(self):
        """Test profile ALPN values are valid."""
        valid_alpn = {"h2", "http/1.1", "h3"}
        for name in ["chrome_120", "firefox_120"]:
            profile = get_profile(name)
            alpn = profile.get("tls", {}).get("alpn", [])
            for protocol in alpn:
                assert protocol in valid_alpn

    def test_derived_profiles_have_base_config(self):
        """Test derived profiles inherit base config."""
        # chrome_120_android should have same TLS as chrome_120
        base = get_profile("chrome_120")
        derived = get_profile("chrome_120_android")
        assert derived["tls"] == base["tls"]

    def test_ios_profiles_have_mobile_user_agent(self):
        """Test iOS profiles have mobile user agent."""
        profile = get_profile("safari_170_ios")
        ua = None
        for name, value in profile["headers"]["default"]:
            if name.lower() == "user-agent":
                ua = value
                break
        assert "iPhone" in ua or "Mobile" in ua

    def test_all_profiles_in_profiles_dict(self):
        """Test all aliases are materialized in PROFILES."""
        for alias in ALIAS_MAP:
            assert alias in PROFILES
