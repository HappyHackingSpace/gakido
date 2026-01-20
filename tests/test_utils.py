"""Tests for gakido.utils module."""

import pytest
from gakido.utils import parse_url


class TestParseUrl:
    """Tests for parse_url function."""

    def test_parse_https_url(self):
        """Test parsing HTTPS URL."""
        parsed, host, port, path = parse_url("https://example.com/path")
        assert host == "example.com"
        assert port == 443
        assert path == "/path"
        assert parsed.scheme == "https"

    def test_parse_http_url(self):
        """Test parsing HTTP URL."""
        parsed, host, port, path = parse_url("http://example.com/path")
        assert host == "example.com"
        assert port == 80
        assert path == "/path"
        assert parsed.scheme == "http"

    def test_parse_url_custom_port(self):
        """Test parsing URL with custom port."""
        parsed, host, port, path = parse_url("https://example.com:8443/api")
        assert host == "example.com"
        assert port == 8443
        assert path == "/api"

    def test_parse_url_with_query_string(self):
        """Test parsing URL with query string."""
        parsed, host, port, path = parse_url("https://example.com/search?q=test&page=1")
        assert host == "example.com"
        assert port == 443
        assert path == "/search?q=test&page=1"

    def test_parse_url_empty_path(self):
        """Test parsing URL with empty path defaults to /."""
        parsed, host, port, path = parse_url("https://example.com")
        assert path == "/"

    def test_parse_url_root_path(self):
        """Test parsing URL with root path."""
        parsed, host, port, path = parse_url("https://example.com/")
        assert path == "/"

    def test_parse_url_invalid_scheme_raises(self):
        """Test invalid scheme raises ValueError."""
        with pytest.raises(ValueError, match="Only http and https"):
            parse_url("ftp://example.com")

    def test_parse_url_no_scheme_raises(self):
        """Test URL without scheme raises."""
        with pytest.raises(ValueError):
            parse_url("example.com/path")

    def test_parse_url_file_scheme_raises(self):
        """Test file:// scheme raises ValueError."""
        with pytest.raises(ValueError, match="Only http and https"):
            parse_url("file:///etc/passwd")

    def test_parse_url_with_fragment(self):
        """Test parsing URL with fragment (fragment not included in path)."""
        parsed, host, port, path = parse_url("https://example.com/page#section")
        assert host == "example.com"
        # Fragment is not part of path sent to server
        assert path == "/page"

    def test_parse_url_complex_path(self):
        """Test parsing URL with complex path."""
        url = "https://api.example.com:9000/v1/users/123/posts?limit=10&offset=20"
        parsed, host, port, path = parse_url(url)
        assert host == "api.example.com"
        assert port == 9000
        assert path == "/v1/users/123/posts?limit=10&offset=20"

    def test_parse_url_ipv4_host(self):
        """Test parsing URL with IPv4 host."""
        parsed, host, port, path = parse_url("http://192.168.1.1:8080/api")
        assert host == "192.168.1.1"
        assert port == 8080
        assert path == "/api"
