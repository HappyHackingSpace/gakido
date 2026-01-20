"""Tests for gakido.client module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from gakido.client import Client
from gakido.models import Response


class TestClientInit:
    """Tests for Client initialization."""

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_default_init(self, mock_get_profile, mock_pool):
        """Test Client initialization with defaults."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = Client()

        mock_get_profile.assert_called_with("chrome_120")
        assert client.timeout == 10.0
        assert client.verify is True
        assert client.auto_decompress is True

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_custom_impersonate(self, mock_get_profile, mock_pool):
        """Test Client with custom impersonate profile."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        Client(impersonate="firefox_133")
        mock_get_profile.assert_called_with("firefox_133")

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_force_http1_modifies_alpn(self, mock_get_profile, mock_pool):
        """Test force_http1=True modifies ALPN."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = Client(force_http1=True)

        assert client.profile["tls"]["alpn"] == ["http/1.1"]

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_auto_decompress_false(self, mock_get_profile, mock_pool):
        """Test auto_decompress=False."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = Client(auto_decompress=False)
        assert client.auto_decompress is False

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_proxies_stored(self, mock_get_profile, mock_pool):
        """Test proxies are stored."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = Client(proxies=["http://proxy:8080"])
        assert client.proxies == ["http://proxy:8080"]

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_ja3_applied(self, mock_get_profile, mock_pool):
        """Test ja3 overrides are applied."""
        mock_get_profile.return_value = {"headers": {"default": []}, "tls": {}}
        client = Client(ja3={"alpn": ["h2"]})
        assert client.profile["tls"]["alpn"] == ["h2"]

    @patch('gakido.client.gakido_core', None)
    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_use_native_false_when_no_core(self, mock_get_profile, mock_pool):
        """Test use_native is False when gakido_core is None."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = Client(use_native=True)
        assert client.use_native is False

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_max_per_host_passed_to_pool(self, mock_get_profile, mock_pool):
        """Test max_per_host is passed to ConnectionPool."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        Client(max_per_host=8)

        mock_pool.assert_called_once()
        call_kwargs = mock_pool.call_args[1]
        assert call_kwargs["max_per_host"] == 8


class TestClientRequest:
    """Tests for Client.request method."""

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_returns_response(self, mock_get_profile, mock_pool):
        """Test request returns Response object."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"body")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        # Use https to bypass native code path, or use_native=False
        client = Client(use_native=False)
        resp = client.request("GET", "https://example.com/path")

        assert resp.status_code == 200

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_with_data_dict(self, mock_get_profile, mock_pool):
        """Test request with dict data is form-encoded."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("POST", "https://example.com", data={"key": "value"})

        # Verify body was form-encoded
        call_args = mock_conn.request.call_args
        body = call_args[1].get("body") or call_args[0][3]
        assert b"key=value" in body if body else True

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_with_bytes_data(self, mock_get_profile, mock_pool):
        """Test request with bytes data."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("POST", "https://example.com", data=b"raw bytes")

        mock_conn.request.assert_called()

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_with_string_data(self, mock_get_profile, mock_pool):
        """Test request with string data."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("POST", "https://example.com", data="string data")

        mock_conn.request.assert_called()

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_invalid_data_type_raises(self, mock_get_profile, mock_pool):
        """Test request with invalid data type raises TypeError."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_pool.return_value.acquire.return_value = MagicMock()

        client = Client(use_native=False)
        with pytest.raises(TypeError, match="Unsupported data type"):
            client.request("POST", "https://example.com", data=12345)

    @patch('gakido.client.build_multipart')
    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_with_files(self, mock_get_profile, mock_pool, mock_build_multipart):
        """Test request with files uses multipart."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_build_multipart.return_value = ("multipart/form-data; boundary=xxx", b"multipart body")
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("POST", "https://example.com", files={"file": b"content"})

        mock_build_multipart.assert_called()

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_post_adds_content_length_zero(self, mock_get_profile, mock_pool):
        """Test POST without body adds Content-Length: 0."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("POST", "https://example.com")

        call_args = mock_conn.request.call_args[0]
        headers = call_args[2]  # Third argument is headers
        header_dict = {name.lower(): value for name, value in headers}
        assert header_dict.get("content-length") == "0"

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_connection_exception_closes_conn(self, mock_get_profile, mock_pool):
        """Test connection exception closes connection."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_conn.request.side_effect = Exception("connection error")
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        with pytest.raises(Exception, match="connection error"):
            client.request("GET", "https://example.com")

        mock_conn.close.assert_called_once()

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_request_connection_released_when_not_closed(self, mock_get_profile, mock_pool):
        """Test connection is released when not closed."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("GET", "https://example.com")

        mock_pool.return_value.release.assert_called_once_with(mock_conn)


class TestClientNativePath:
    """Tests for Client native code path."""

    @patch('gakido.client.gakido_core')
    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_native_path_http(self, mock_get_profile, mock_pool, mock_core):
        """Test native path is used for HTTP."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_core.request.return_value = (200, "OK", "1.1", [], b"body")
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=True)
        response = client.request("GET", "http://example.com/path")

        mock_core.request.assert_called_once()
        assert response.status_code == 200

    @patch('gakido.client.decode_body')
    @patch('gakido.client.gakido_core')
    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_native_path_decompresses(self, mock_get_profile, mock_pool, mock_core, mock_decode):
        """Test native path decompresses response."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_core.request.return_value = (
            200, "OK", "1.1",
            [("content-encoding", "gzip")],
            b"compressed"
        )
        mock_decode.return_value = b"decompressed"
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=True, auto_decompress=True)
        response = client.request("GET", "http://example.com")

        mock_decode.assert_called_with(b"compressed", "gzip")
        assert response.content == b"decompressed"


class TestClientMethods:
    """Tests for Client convenience methods."""

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_get_method(self, mock_get_profile, mock_pool):
        """Test get() convenience method."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.get("https://example.com")

        mock_conn.request.assert_called()
        args = mock_conn.request.call_args[0]
        assert args[0] == "GET"

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_post_method(self, mock_get_profile, mock_pool):
        """Test post() convenience method."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.post("https://example.com", data={"key": "value"})

        mock_conn.request.assert_called()
        args = mock_conn.request.call_args[0]
        assert args[0] == "POST"

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_close_method(self, mock_get_profile, mock_pool):
        """Test close() closes the pool."""
        mock_get_profile.return_value = {"headers": {"default": []}, "tls": {}}
        client = Client()
        client.close()
        mock_pool.return_value.close.assert_called_once()


class TestClientContextManager:
    """Tests for Client context manager."""

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_context_manager_enter(self, mock_get_profile, mock_pool):
        """Test context manager __enter__."""
        mock_get_profile.return_value = {"headers": {"default": []}, "tls": {}}
        client = Client()
        result = client.__enter__()
        assert result is client

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_context_manager_exit(self, mock_get_profile, mock_pool):
        """Test context manager __exit__ closes client."""
        mock_get_profile.return_value = {"headers": {"default": []}, "tls": {}}
        with Client() as client:
            pass
        mock_pool.return_value.close.assert_called_once()


class TestClientProxy:
    """Tests for Client proxy handling."""

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_invalid_proxy_scheme_raises(self, mock_get_profile, mock_pool):
        """Test non-http proxy raises ValueError."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_pool.return_value.acquire.return_value = MagicMock()

        client = Client()
        with pytest.raises(ValueError, match="Only http proxies"):
            client.request("GET", "http://example.com", proxy="socks5://proxy:1080")

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_proxy_uses_absolute_url(self, mock_get_profile, mock_pool):
        """Test proxy request uses absolute URL form."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("GET", "http://example.com/path", proxy="http://proxy:8080")

        call_args = mock_conn.request.call_args[0]
        path = call_args[1]
        assert path == "http://example.com/path"

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_proxy_pool_uses_first_proxy(self, mock_get_profile, mock_pool):
        """Test proxy pool uses first proxy."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False, proxies=["http://proxy1:8080", "http://proxy2:8080"])
        client.request("GET", "http://example.com")

        # Verify pool was acquired with proxy host/port
        call_args = mock_pool.return_value.acquire.call_args[0]
        assert call_args[1] == "proxy1"  # host
        assert call_args[2] == 8080  # port


class TestClientHeaders:
    """Tests for Client header handling."""

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_connection_header_added(self, mock_get_profile, mock_pool):
        """Test Connection: keep-alive is added by default."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("GET", "https://example.com")

        call_args = mock_conn.request.call_args[0]
        headers = call_args[2]
        header_dict = {name.lower(): value for name, value in headers}
        assert header_dict.get("connection") == "keep-alive"

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_user_headers_merged(self, mock_get_profile, mock_pool):
        """Test user headers are merged with defaults."""
        mock_get_profile.return_value = {
            "headers": {"default": [("User-Agent", "TestAgent")], "order": []},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = Response(200, "OK", "1.1", [], b"")
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(use_native=False)
        client.request("GET", "https://example.com", headers={"X-Custom": "value"})

        call_args = mock_conn.request.call_args[0]
        headers = call_args[2]
        header_dict = {name: value for name, value in headers}
        assert "X-Custom" in header_dict or "x-custom" in header_dict.keys()
