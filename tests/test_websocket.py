"""Tests for gakido.websocket module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import socket
import ssl
import struct
import base64
import hashlib
import os

from gakido.websocket import WebSocket


class TestWebSocketConnect:
    """Tests for WebSocket.connect class method."""

    @patch('gakido.websocket.ssl.create_default_context')
    @patch('gakido.websocket.socket.create_connection')
    @patch('gakido.websocket.os.urandom')
    def test_connect_ws(self, mock_urandom, mock_create_conn, mock_ssl_ctx):
        """Test WebSocket connection without TLS."""
        mock_urandom.return_value = b"1234567890123456"  # 16 bytes for key
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        # Simulate successful upgrade response
        key = base64.b64encode(b"1234567890123456").decode()
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        response = f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"
        mock_sock.recv.return_value = response.encode()

        ws = WebSocket.connect(
            host="example.com",
            port=80,
            resource="/ws",
            headers=[("Origin", "http://example.com")],
            tls=False,
        )

        assert isinstance(ws, WebSocket)
        mock_create_conn.assert_called_once_with(("example.com", 80), timeout=10.0)

    @patch('gakido.websocket.ssl.create_default_context')
    @patch('gakido.websocket.socket.create_connection')
    @patch('gakido.websocket.os.urandom')
    def test_connect_wss(self, mock_urandom, mock_create_conn, mock_ssl_ctx):
        """Test WebSocket connection with TLS."""
        mock_urandom.return_value = b"1234567890123456"
        mock_sock = MagicMock()
        mock_wrapped = MagicMock()
        mock_create_conn.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_ssl_ctx.return_value = mock_ctx

        key = base64.b64encode(b"1234567890123456").decode()
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        response = f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"
        mock_wrapped.recv.return_value = response.encode()

        ws = WebSocket.connect(
            host="example.com",
            port=443,
            resource="/ws",
            headers=[],
            tls=True,
        )

        assert isinstance(ws, WebSocket)
        mock_ctx.wrap_socket.assert_called_once_with(mock_sock, server_hostname="example.com")

    @patch('gakido.websocket.socket.create_connection')
    @patch('gakido.websocket.os.urandom')
    def test_connect_upgrade_failed_raises(self, mock_urandom, mock_create_conn):
        """Test connect raises on failed upgrade."""
        mock_urandom.return_value = b"1234567890123456"
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        # Non-101 response
        mock_sock.recv.return_value = b"HTTP/1.1 400 Bad Request\r\n\r\n"

        with pytest.raises(RuntimeError, match="WebSocket upgrade failed"):
            WebSocket.connect(
                host="example.com",
                port=80,
                resource="/ws",
                headers=[],
            )

        mock_sock.close.assert_called()

    @patch('gakido.websocket.socket.create_connection')
    @patch('gakido.websocket.os.urandom')
    def test_connect_accept_mismatch_raises(self, mock_urandom, mock_create_conn):
        """Test connect raises on accept key mismatch."""
        mock_urandom.return_value = b"1234567890123456"
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        # Response with wrong accept key
        response = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: wrongkey\r\n\r\n"
        mock_sock.recv.return_value = response.encode()

        with pytest.raises(RuntimeError, match="WebSocket accept mismatch"):
            WebSocket.connect(
                host="example.com",
                port=80,
                resource="/ws",
                headers=[],
            )

    @patch('gakido.websocket.socket.create_connection')
    @patch('gakido.websocket.os.urandom')
    def test_connect_with_custom_headers(self, mock_urandom, mock_create_conn):
        """Test connect sends custom headers."""
        mock_urandom.return_value = b"1234567890123456"
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock

        key = base64.b64encode(b"1234567890123456").decode()
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        response = f"HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"
        mock_sock.recv.return_value = response.encode()

        WebSocket.connect(
            host="example.com",
            port=80,
            resource="/ws",
            headers=[
                ("Authorization", "Bearer token"),
                ("X-Custom", "value"),
            ],
        )

        # Check sendall was called with custom headers
        sent_data = mock_sock.sendall.call_args[0][0].decode()
        assert "Authorization: Bearer token" in sent_data
        assert "X-Custom: value" in sent_data


class TestWebSocketSend:
    """Tests for WebSocket send methods."""

    def test_send_text(self):
        """Test sending text message."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        with patch('gakido.websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            ws.send_text("hello")

        mock_sock.sendall.assert_called_once()
        sent = mock_sock.sendall.call_args[0][0]

        # Check opcode is 0x81 (FIN + text)
        assert sent[0] == 0x81

    def test_send_bytes(self):
        """Test sending binary message."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        with patch('gakido.websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            ws.send_bytes(b"binary data")

        mock_sock.sendall.assert_called_once()
        sent = mock_sock.sendall.call_args[0][0]

        # Check opcode is 0x82 (FIN + binary)
        assert sent[0] == 0x82


class TestWebSocketSendFrame:
    """Tests for WebSocket._send_frame method."""

    def test_send_frame_small_payload(self):
        """Test sending small payload (< 126 bytes)."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        with patch('gakido.websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            ws._send_frame(0x1, b"hello")

        sent = mock_sock.sendall.call_args[0][0]
        # FIN + opcode
        assert sent[0] == 0x81
        # MASK bit + length
        assert sent[1] == 0x85  # 0x80 | 5

    def test_send_frame_medium_payload(self):
        """Test sending medium payload (126-65535 bytes)."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        payload = b"x" * 200

        with patch('gakido.websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            ws._send_frame(0x1, payload)

        sent = mock_sock.sendall.call_args[0][0]
        # MASK bit + 126 indicator
        assert sent[1] == 0xFE  # 0x80 | 126
        # Extended payload length
        length = struct.unpack("!H", sent[2:4])[0]
        assert length == 200

    def test_send_frame_large_payload(self):
        """Test sending large payload (> 65535 bytes)."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        payload = b"x" * 70000

        with patch('gakido.websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            ws._send_frame(0x1, payload)

        sent = mock_sock.sendall.call_args[0][0]
        # MASK bit + 127 indicator
        assert sent[1] == 0xFF  # 0x80 | 127
        # Extended payload length (8 bytes)
        length = struct.unpack("!Q", sent[2:10])[0]
        assert length == 70000


class TestWebSocketRecv:
    """Tests for WebSocket recv methods."""

    def test_recv(self):
        """Test receiving a message."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        # Simulate receiving a text frame: FIN + opcode=1, no mask, length=5, "hello"
        frame = bytes([0x81, 0x05]) + b"hello"
        idx = [0]

        def recv_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_sock.recv.side_effect = recv_side_effect

        opcode, payload = ws.recv()

        assert opcode == 0x01
        assert payload == b"hello"

    def test_recv_masked_frame(self):
        """Test receiving a masked frame (server shouldn't send masked frames, but test anyway)."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        # Masked frame with mask key and payload
        mask_key = b"\x12\x34\x56\x78"
        payload = b"hello"
        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        frame = bytes([0x81, 0x85]) + mask_key + masked_payload  # 0x85 = 0x80 | 5 (masked + length)
        idx = [0]

        def recv_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_sock.recv.side_effect = recv_side_effect

        opcode, result = ws.recv()

        assert result == b"hello"

    def test_recv_extended_length_16(self):
        """Test receiving frame with 16-bit extended length."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        payload = b"x" * 200
        # FIN + text, length=126 indicator, then 2-byte length
        frame = bytes([0x81, 126]) + struct.pack("!H", 200) + payload
        idx = [0]

        def recv_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_sock.recv.side_effect = recv_side_effect

        opcode, result = ws.recv()

        assert len(result) == 200

    def test_recv_extended_length_64(self):
        """Test receiving frame with 64-bit extended length."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        payload = b"x" * 70000
        # FIN + text, length=127 indicator, then 8-byte length
        frame = bytes([0x81, 127]) + struct.pack("!Q", 70000) + payload
        idx = [0]

        def recv_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_sock.recv.side_effect = recv_side_effect

        opcode, result = ws.recv()

        assert len(result) == 70000


class TestWebSocketClose:
    """Tests for WebSocket.close method."""

    def test_close_sends_close_frame(self):
        """Test close sends close frame."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        with patch('gakido.websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            ws.close()

        # Should send close frame (opcode 0x8) then close socket
        sent = mock_sock.sendall.call_args[0][0]
        assert sent[0] == 0x88  # FIN + close opcode
        mock_sock.close.assert_called_once()


class TestWebSocketRecvExact:
    """Tests for WebSocket._recv_exact method."""

    def test_recv_exact(self):
        """Test _recv_exact reads exact number of bytes."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        mock_sock.recv.side_effect = [b"hell", b"lo"]

        result = ws._recv_exact(5)

        assert result == b"helllo"

    def test_recv_exact_socket_closed_raises(self):
        """Test _recv_exact raises on socket close."""
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""
        ws = WebSocket(mock_sock)

        with pytest.raises(RuntimeError, match="Socket closed"):
            ws._recv_exact(10)


class TestWebSocketInit:
    """Tests for WebSocket initialization."""

    def test_init_stores_socket(self):
        """Test WebSocket stores socket reference."""
        mock_sock = MagicMock()
        ws = WebSocket(mock_sock)

        assert ws.sock is mock_sock
