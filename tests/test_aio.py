"""Tests for gakido.aio module (AsyncClient)."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
import ssl

from gakido.aio import AsyncClient
from gakido.models import Response
from gakido.errors import ProtocolError


class TestAsyncClientInit:
    """Tests for AsyncClient initialization."""

    @patch('gakido.aio.get_profile')
    def test_default_init(self, mock_get_profile):
        """Test AsyncClient initialization with defaults."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient()

        mock_get_profile.assert_called_with("chrome_120")
        assert client.timeout == 10.0
        assert client.verify is True
        assert client.auto_decompress is True
        assert client.http3_enabled is False

    @patch('gakido.aio.get_profile')
    def test_custom_impersonate(self, mock_get_profile):
        """Test AsyncClient with custom impersonate profile."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        AsyncClient(impersonate="firefox_133")
        mock_get_profile.assert_called_with("firefox_133")

    @patch('gakido.aio.get_profile')
    def test_force_http1_modifies_alpn(self, mock_get_profile):
        """Test force_http1=True modifies ALPN."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient(force_http1=True)

        assert client.profile["tls"]["alpn"] == ["http/1.1"]

    @patch('gakido.aio.get_profile')
    def test_http3_enabled_when_available(self, mock_get_profile):
        """Test http3=True with available aioquic."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        with patch('gakido.aio.is_http3_available', return_value=True):
            client = AsyncClient(http3=True)
            assert client.http3_enabled is True

    @patch('gakido.aio.get_profile')
    def test_http3_disabled_when_unavailable(self, mock_get_profile):
        """Test http3=True with unavailable aioquic."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        with patch('gakido.aio.is_http3_available', return_value=False):
            client = AsyncClient(http3=True)
            assert client.http3_enabled is False

    @patch('gakido.aio.get_profile')
    def test_http3_fallback_default(self, mock_get_profile):
        """Test http3_fallback defaults to True."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient()
        assert client.http3_fallback is True

    @patch('gakido.aio.get_profile')
    def test_auto_decompress_false(self, mock_get_profile):
        """Test auto_decompress=False."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient(auto_decompress=False)
        assert client.auto_decompress is False

    @patch('gakido.aio.get_profile')
    def test_proxy_pool_stored(self, mock_get_profile):
        """Test proxy_pool is stored."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient(proxy_pool=["http://proxy:8080"])
        assert client.proxy_pool == ["http://proxy:8080"]

    @patch('gakido.aio.get_profile')
    def test_ja3_overrides_applied(self, mock_get_profile):
        """Test ja3 overrides are applied."""
        mock_get_profile.return_value = {"headers": {"default": []}, "tls": {}}
        client = AsyncClient(ja3={"ciphers": "custom"})
        assert client.profile["tls"]["ciphers"] == "custom"

    @patch('gakido.aio.get_profile')
    def test_tls_configuration_options_applied(self, mock_get_profile):
        """Test tls_configuration_options are applied."""
        mock_get_profile.return_value = {"headers": {"default": []}, "tls": {}}
        client = AsyncClient(tls_configuration_options={"curves": ["X25519"]})
        # apply_tls_configuration_options should be called


class TestAsyncClientRequest:
    """Tests for AsyncClient.request method."""

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_http11(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test HTTP/1.1 request."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        # Mock reader/writer
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        # Mock response
        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Length: 5\r\n",
            b"\r\n",
        ])
        mock_reader.readexactly = AsyncMock(return_value=b"hello")

        client = AsyncClient()
        response = await client.request("GET", "http://example.com/path")

        assert response.status_code == 200
        assert response.content == b"hello"

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_with_data_dict(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test request with dict data is form-encoded."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Length: 0\r\n",
            b"\r\n",
        ])
        mock_reader.readexactly = AsyncMock(return_value=b"")

        client = AsyncClient()
        await client.request("POST", "http://example.com", data={"key": "value"})

        # Check writelines was called with form-encoded body
        call_args = mock_writer.writelines.call_args[0][0]
        request_str = b"".join(call_args).decode()
        assert "key=value" in request_str

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_with_string_data(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test request with string data."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient()
        await client.request("POST", "http://example.com", data="string data")

        # Verify data was sent
        mock_writer.writelines.assert_called()

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_with_bytes_data(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test request with bytes data."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient()
        await client.request("POST", "http://example.com", data=b"bytes data")

        mock_writer.writelines.assert_called()

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    async def test_request_invalid_data_type_raises(self, mock_get_profile):
        """Test request with invalid data type raises TypeError."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        client = AsyncClient()
        with pytest.raises(TypeError, match="Unsupported data type"):
            await client.request("POST", "http://example.com", data=12345)

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_chunked_response(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test handling chunked transfer encoding."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"Transfer-Encoding: chunked\r\n",
            b"\r\n",
            b"5\r\n",  # chunk size
            b"0\r\n",  # end chunk
            b"\r\n",   # final CRLF after 0 chunk
        ])
        mock_reader.readexactly = AsyncMock(side_effect=[
            b"hello",  # chunk data
            b"\r\n",   # chunk trailer
        ])

        client = AsyncClient()
        response = await client.request("GET", "http://example.com")

        assert response.content == b"hello"

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_empty_response_raises(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test empty response raises ProtocolError."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(return_value=b"")

        client = AsyncClient()
        with pytest.raises(ProtocolError, match="Empty response"):
            await client.request("GET", "http://example.com")

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_malformed_status_raises(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test malformed status line raises ProtocolError."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(return_value=b"INVALID\r\n")

        client = AsyncClient()
        with pytest.raises(ProtocolError, match="Malformed status line"):
            await client.request("GET", "http://example.com")

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_malformed_header_raises(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test malformed header line raises ProtocolError."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"InvalidHeaderWithoutColon\r\n",
        ])

        client = AsyncClient()
        with pytest.raises(ProtocolError, match="Malformed header"):
            await client.request("GET", "http://example.com")

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.build_multipart')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_request_with_files(self, mock_wait_for, mock_open_conn, mock_build_multipart, mock_get_profile):
        """Test request with files uses multipart."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_build_multipart.return_value = ("multipart/form-data; boundary=xxx", b"multipart body")

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient()
        await client.request("POST", "http://example.com", files={"file": b"content"})

        mock_build_multipart.assert_called()


class TestAsyncClientMethods:
    """Tests for AsyncClient convenience methods."""

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    async def test_close_clears_h3_protocols(self, mock_get_profile):
        """Test close() clears HTTP/3 protocols cache."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient()
        client._h3_protocols["test"] = MagicMock()
        client._h3_protocols["test"].close = AsyncMock()

        await client.close()

        assert len(client._h3_protocols) == 0
        assert len(client._h3_failed_hosts) == 0

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    async def test_context_manager(self, mock_get_profile):
        """Test async context manager."""
        mock_get_profile.return_value = {"headers": {"default": []}}

        async with AsyncClient() as client:
            assert isinstance(client, AsyncClient)

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_get_method(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test get() convenience method."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient()
        response = await client.get("http://example.com")

        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_post_method(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test post() convenience method."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 201 Created\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient()
        response = await client.post("http://example.com", data={"key": "value"})

        assert response.status_code == 201


class TestAsyncClientProxy:
    """Tests for AsyncClient proxy handling."""

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    async def test_invalid_proxy_scheme_raises(self, mock_open_conn, mock_get_profile):
        """Test non-http proxy raises ValueError."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        client = AsyncClient()
        with pytest.raises(ValueError, match="Only http proxy"):
            await client.request("GET", "http://example.com", proxy="socks5://proxy:1080")

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_proxy_uses_absolute_url(self, mock_wait_for, mock_open_conn, mock_get_profile):
        """Test proxy request uses absolute URL form."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient()
        await client.request("GET", "http://example.com/path", proxy="http://proxy:8080")

        # Check absolute URL in request line
        call_args = mock_writer.writelines.call_args[0][0]
        request_line = call_args[0].decode()
        assert "http://example.com/path" in request_line


class TestAsyncClientHTTPS:
    """Tests for AsyncClient HTTPS handling."""

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.ssl.create_default_context')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_https_creates_ssl_context(self, mock_wait_for, mock_open_conn, mock_ssl_ctx, mock_get_profile):
        """Test HTTPS creates SSL context."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {"ciphers": "TLS_AES_128_GCM_SHA256"},
        }
        mock_ctx = MagicMock()
        mock_ssl_ctx.return_value = mock_ctx

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient()
        await client.request("GET", "https://example.com")

        mock_ssl_ctx.assert_called()

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.ssl.create_default_context')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_https_verify_false(self, mock_wait_for, mock_open_conn, mock_ssl_ctx, mock_get_profile):
        """Test HTTPS with verify=False."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_ctx = MagicMock()
        mock_ssl_ctx.return_value = mock_ctx

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ])
        mock_reader.read = AsyncMock(return_value=b"")

        client = AsyncClient(verify=False)
        await client.request("GET", "https://example.com")

        assert mock_ctx.check_hostname is False
        assert mock_ctx.verify_mode == ssl.CERT_NONE


class TestAsyncClientH3FailedHosts:
    """Tests for HTTP/3 failed hosts tracking."""

    @patch('gakido.aio.get_profile')
    def test_h3_failed_hosts_initially_empty(self, mock_get_profile):
        """Test _h3_failed_hosts starts empty."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient()
        assert len(client._h3_failed_hosts) == 0

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    async def test_close_clears_failed_hosts(self, mock_get_profile):
        """Test close() clears failed hosts set."""
        mock_get_profile.return_value = {"headers": {"default": []}}
        client = AsyncClient()
        client._h3_failed_hosts.add("example.com")

        await client.close()

        assert len(client._h3_failed_hosts) == 0


class TestAsyncClientHTTP2:
    """Tests for AsyncClient HTTP/2 handling."""

    @pytest.mark.asyncio
    @patch('gakido.aio.get_profile')
    async def test_h2_alpn_set_when_force_http1_false(self, mock_get_profile):
        """Test HTTP/2 ALPN is set when force_http1=False."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {"alpn": ["h2", "http/1.1"]},
            "http2": {"alpn": ["h2", "http/1.1"]},
        }

        client = AsyncClient(force_http1=False)

        # When force_http1=False, ALPN should not be overwritten to http/1.1 only
        assert client.profile["tls"]["alpn"] == ["h2", "http/1.1"]


class TestAsyncClientDecompression:
    """Tests for AsyncClient auto decompression."""

    @pytest.mark.asyncio
    @patch('gakido.aio.decode_body')
    @patch('gakido.aio.get_profile')
    @patch('gakido.aio.asyncio.open_connection')
    @patch('gakido.aio.asyncio.wait_for')
    async def test_auto_decompress_enabled(self, mock_wait_for, mock_open_conn, mock_get_profile, mock_decode):
        """Test auto decompression when enabled."""
        mock_get_profile.return_value = {
            "headers": {"default": [], "order": []},
            "tls": {},
        }
        mock_decode.return_value = b"decompressed"

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()
        mock_writer.get_extra_info = MagicMock(return_value=None)
        mock_wait_for.return_value = (mock_reader, mock_writer)

        mock_reader.readline = AsyncMock(side_effect=[
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Encoding: gzip\r\n",
            b"Content-Length: 10\r\n",
            b"\r\n",
        ])
        mock_reader.readexactly = AsyncMock(return_value=b"compressed")

        client = AsyncClient(auto_decompress=True)
        response = await client.request("GET", "http://example.com")

        mock_decode.assert_called_with(b"compressed", "gzip")
        assert response.content == b"decompressed"
