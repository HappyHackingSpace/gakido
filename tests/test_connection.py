"""Tests for gakido.connection module."""

import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import socket
import ssl

from gakido.connection import Connection
from gakido.models import Response
from gakido.errors import ConnectionError, ProtocolError, TLSNegotiationError


class TestConnectionInit:
    """Tests for Connection initialization."""

    def test_init_sets_attributes(self):
        """Test Connection initializes with correct attributes."""
        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {}},
            timeout=30.0,
            verify=False,
        )

        assert conn.host == "example.com"
        assert conn.port == 443
        assert conn.scheme == "https"
        assert conn.timeout == 30.0
        assert conn.verify is False
        assert conn.sock is None
        assert conn.closed is True

    def test_init_default_values(self):
        """Test Connection initializes with default timeout and verify."""
        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )

        assert conn.timeout == 10.0
        assert conn.verify is True


class TestConnectionConnect:
    """Tests for Connection.connect method."""

    @patch('gakido.connection.socket.create_connection')
    def test_connect_http(self, mock_create_conn):
        """Test HTTP connection (no TLS)."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        mock_create_conn.assert_called_once_with(("example.com", 80), timeout=10.0)
        mock_sock.settimeout.assert_called_once_with(10.0)
        assert conn.sock is mock_sock
        assert conn.closed is False

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_https(self, mock_create_conn, mock_ssl_ctx):
        """Test HTTPS connection with TLS."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = "http/1.1"
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {"ciphers": "TLS_AES_128_GCM_SHA256"}},
        )
        conn.connect()

        assert conn.sock is mock_wrapped
        assert conn.negotiated_protocol == "http/1.1"
        assert conn.closed is False

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_https_verify_false(self, mock_create_conn, mock_ssl_ctx):
        """Test HTTPS connection with verify=False."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = None
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={},
            verify=False,
        )
        conn.connect()

        assert mock_ctx.check_hostname is False
        assert mock_ctx.verify_mode == ssl.CERT_NONE

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_with_alpn(self, mock_create_conn, mock_ssl_ctx):
        """Test HTTPS connection with ALPN protocols."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = "h2"
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {"alpn": ["h2", "http/1.1"]}},
        )
        conn.connect()

        mock_ctx.set_alpn_protocols.assert_called_once_with(["h2", "http/1.1"])

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_with_http2_alpn_fallback(self, mock_create_conn, mock_ssl_ctx):
        """Test HTTPS connection falls back to http2 alpn."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = "h2"
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"http2": {"alpn": ["h2"]}},  # No tls.alpn, use http2.alpn
        )
        conn.connect()

        mock_ctx.set_alpn_protocols.assert_called_once_with(["h2"])

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_with_curves(self, mock_create_conn, mock_ssl_ctx):
        """Test HTTPS connection with TLS curves."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = None
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {"curves": ["X25519", "P-256"]}},
        )
        conn.connect()

        mock_ctx.set_ecdh_curve.assert_called_once_with("X25519")

    @patch('gakido.connection.socket.create_connection')
    def test_connect_tcp_failure_raises(self, mock_create_conn):
        """Test TCP connection failure raises ConnectionError."""
        mock_create_conn.side_effect = OSError("Connection refused")

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )

        with pytest.raises(ConnectionError, match="TCP connection failed"):
            conn.connect()

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_tls_failure_retries_and_raises(self, mock_create_conn, mock_ssl_ctx):
        """Test TLS handshake failure retries then raises TLSNegotiationError."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.side_effect = ssl.SSLError("handshake failure")
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {"ciphers": "invalid"}},
        )

        with pytest.raises(TLSNegotiationError, match="TLS handshake failed"):
            conn.connect()

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_cipher_fallback(self, mock_create_conn, mock_ssl_ctx):
        """Test cipher fallback when custom ciphers fail."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = None
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.set_ciphers.side_effect = [ssl.SSLError("bad cipher"), None]
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {"ciphers": "invalid_cipher"}},
        )
        conn.connect()

        assert mock_ctx.set_ciphers.call_count == 2

    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_connect_alpn_not_implemented(self, mock_create_conn, mock_ssl_ctx):
        """Test ALPN NotImplementedError is handled."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = None
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.set_alpn_protocols.side_effect = NotImplementedError()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {"alpn": ["h2"]}},
        )
        # Should not raise
        conn.connect()
        assert conn.sock is not None


class TestConnectionRequest:
    """Tests for Connection.request method."""

    @patch('gakido.connection.socket.create_connection')
    def test_request_connects_if_closed(self, mock_create_conn):
        """Test request calls connect if socket is closed."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        # Set up response
        mock_sock.recv.side_effect = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Length: 4\r\n",
            b"\r\n",
            b"body",
        ]

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )

        response = conn.request("GET", "/", [("Host", "example.com")])

        assert response.status_code == 200
        mock_create_conn.assert_called()

    @patch('gakido.connection.socket.create_connection')
    def test_request_send_failure_closes_connection(self, mock_create_conn):
        """Test send failure closes connection and raises."""
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = OSError("broken pipe")
        mock_create_conn.return_value = mock_sock

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        with pytest.raises(ConnectionError, match="Send failed"):
            conn.request("GET", "/", [("Host", "example.com")])

        assert conn.closed is True


class TestConnectionReadResponse:
    """Tests for Connection._read_response method."""

    @patch('gakido.connection.socket.create_connection')
    def test_read_response_chunked(self, mock_create_conn):
        """Test reading chunked transfer-encoded response."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        # Chunked response
        response_data = (
            b"HTTP/1.1 200 OK\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
            b"5\r\n"
            b"hello\r\n"
            b"0\r\n"
            b"\r\n"
        )
        mock_sock.recv.side_effect = lambda n: response_data[:n] if n == 1 else response_data

        # Use byte-by-byte recv for _readline
        idx = [0]
        def recv_side_effect(n):
            if n == 1:
                if idx[0] < len(response_data):
                    result = response_data[idx[0]:idx[0]+1]
                    idx[0] += 1
                    return result
                return b""
            else:
                start = idx[0]
                idx[0] += n
                return response_data[start:start+n]

        mock_sock.recv.side_effect = recv_side_effect

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        response = conn.request("GET", "/", [("Host", "example.com")])
        assert response.status_code == 200
        assert response.content == b"hello"

    @patch('gakido.connection.socket.create_connection')
    def test_read_response_content_length(self, mock_create_conn):
        """Test reading response with Content-Length."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        response_data = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 5\r\n"
            b"\r\n"
            b"hello"
        )

        idx = [0]
        def recv_side_effect(n):
            if idx[0] >= len(response_data):
                return b""
            if n == 1:
                result = response_data[idx[0]:idx[0]+1]
                idx[0] += 1
                return result
            else:
                start = idx[0]
                end = min(start + n, len(response_data))
                idx[0] = end
                return response_data[start:end]

        mock_sock.recv.side_effect = recv_side_effect

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        response = conn.request("GET", "/", [("Host", "example.com")])
        assert response.status_code == 200
        assert response.content == b"hello"

    @patch('gakido.connection.socket.create_connection')
    def test_read_response_empty_raises(self, mock_create_conn):
        """Test empty response raises ProtocolError."""
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""
        mock_create_conn.return_value = mock_sock

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        with pytest.raises(ProtocolError, match="Empty response"):
            conn.request("GET", "/", [("Host", "example.com")])

    @patch('gakido.connection.socket.create_connection')
    def test_read_response_malformed_status_raises(self, mock_create_conn):
        """Test malformed status line raises ProtocolError."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        idx = [0]
        response_data = b"INVALID_STATUS\r\n"
        def recv_side_effect(n):
            if idx[0] >= len(response_data):
                return b""
            if n == 1:
                result = response_data[idx[0]:idx[0]+1]
                idx[0] += 1
                return result
            return b""

        mock_sock.recv.side_effect = recv_side_effect

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        with pytest.raises(ProtocolError, match="Malformed status line"):
            conn.request("GET", "/", [("Host", "example.com")])

    @patch('gakido.connection.socket.create_connection')
    def test_read_response_connection_close(self, mock_create_conn):
        """Test Connection: close header closes connection."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        response_data = (
            b"HTTP/1.1 200 OK\r\n"
            b"Connection: close\r\n"
            b"Content-Length: 5\r\n"
            b"\r\n"
            b"hello"
        )

        idx = [0]
        def recv_side_effect(n):
            if idx[0] >= len(response_data):
                return b""
            if n == 1:
                result = response_data[idx[0]:idx[0]+1]
                idx[0] += 1
                return result
            else:
                start = idx[0]
                end = min(start + n, len(response_data))
                idx[0] = end
                return response_data[start:end]

        mock_sock.recv.side_effect = recv_side_effect

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        response = conn.request("GET", "/", [("Host", "example.com")])
        assert conn.closed is True


class TestConnectionClose:
    """Tests for Connection.close method."""

    @patch('gakido.connection.socket.create_connection')
    def test_close_closes_socket(self, mock_create_conn):
        """Test close closes the socket."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()
        conn.close()

        mock_sock.close.assert_called_once()
        assert conn.sock is None
        assert conn.closed is True

    def test_close_when_already_closed(self):
        """Test close when already closed does nothing."""
        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        # Already closed, should not raise
        conn.close()
        assert conn.closed is True


class TestConnectionBuildRequest:
    """Tests for Connection._build_request method."""

    def test_build_request_get(self):
        """Test building GET request."""
        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )

        request = conn._build_request(
            "GET",
            "/path",
            [("Host", "example.com"), ("User-Agent", "test")],
            None,
        )

        assert b"GET /path HTTP/1.1\r\n" in request
        assert b"Host: example.com\r\n" in request
        assert b"User-Agent: test\r\n" in request

    def test_build_request_post_with_body(self):
        """Test building POST request with body."""
        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )

        request = conn._build_request(
            "POST",
            "/submit",
            [("Host", "example.com"), ("Content-Length", "4")],
            b"data",
        )

        assert b"POST /submit HTTP/1.1\r\n" in request
        assert request.endswith(b"\r\n\r\ndata")


class TestConnectionH2:
    """Tests for Connection HTTP/2 path."""

    @patch('gakido.connection.HTTP2Connection')
    @patch('gakido.connection.ssl.create_default_context')
    @patch('gakido.connection.socket.create_connection')
    def test_request_uses_h2_when_negotiated(self, mock_create_conn, mock_ssl_ctx, mock_h2_conn):
        """Test request uses HTTP2Connection when h2 negotiated."""
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_wrapped.selected_alpn_protocol.return_value = "h2"
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        mock_h2_response = Response(200, "OK", "2", [], b"body")
        mock_h2_conn.return_value.request.return_value = mock_h2_response

        conn = Connection(
            host="example.com",
            port=443,
            scheme="https",
            profile={"tls": {"alpn": ["h2", "http/1.1"]}},
        )
        conn.connect()

        response = conn.request("GET", "/", [("Host", "example.com")])

        assert response.http_version == "2"
        mock_h2_conn.assert_called_once_with(mock_wrapped)


class TestConnectionReadHelpers:
    """Tests for Connection read helper methods."""

    @patch('gakido.connection.socket.create_connection')
    def test_read_exact_eof_raises(self, mock_create_conn):
        """Test _read_exact raises on unexpected EOF."""
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"partial", b""]
        mock_create_conn.return_value = mock_sock

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        with pytest.raises(ProtocolError, match="Unexpected EOF"):
            conn._read_exact(100)

    @patch('gakido.connection.socket.create_connection')
    def test_read_until_close_timeout(self, mock_create_conn):
        """Test _read_until_close handles timeout."""
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"data1", b"data2", TimeoutError()]
        mock_create_conn.return_value = mock_sock

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        result = conn._read_until_close()
        assert result == b"data1data2"

    @patch('gakido.connection.socket.create_connection')
    def test_readline(self, mock_create_conn):
        """Test _readline reads until CRLF."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        line_data = b"Hello World\r\n"
        idx = [0]
        def recv_one(n):
            if idx[0] >= len(line_data):
                return b""
            result = line_data[idx[0]:idx[0]+1]
            idx[0] += 1
            return result

        mock_sock.recv.side_effect = recv_one

        conn = Connection(
            host="example.com",
            port=80,
            scheme="http",
            profile={},
        )
        conn.connect()

        result = conn._readline()
        assert result == b"Hello World\r\n"
