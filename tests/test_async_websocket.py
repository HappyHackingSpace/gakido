"""Tests for gakido.async_websocket module."""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import asyncio
import ssl
import struct
import base64
import hashlib
import os

from gakido.async_websocket import AsyncWebSocket


class TestAsyncWebSocketConnect:
    """Tests for AsyncWebSocket.connect class method."""

    @patch('gakido.async_websocket.ssl.create_default_context')
    @patch('gakido.async_websocket.asyncio.open_connection')
    @patch('gakido.async_websocket.os.urandom')
    async def test_connect_ws(self, mock_urandom, mock_open_conn, mock_ssl_ctx):
        """Test WebSocket connection without TLS."""
        mock_urandom.return_value = b"1234567890123456"  # 16 bytes for key
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_conn.return_value = (mock_reader, mock_writer)

        # Simulate successful upgrade response
        key = base64.b64encode(b"1234567890123456").decode()
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        response = f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"
        mock_reader.read.return_value = response.encode()

        ws = await AsyncWebSocket.connect(
            host="example.com",
            port=80,
            resource="/ws",
            headers=[("Origin", "http://example.com")],
            tls=False,
        )

        assert isinstance(ws, AsyncWebSocket)
        mock_open_conn.assert_called_once_with(
            host="example.com",
            port=80,
            ssl=None,
            server_hostname=None,
        )

    @patch('gakido.async_websocket.asyncio.open_connection')
    @patch('gakido.async_websocket.os.urandom')
    async def test_connect_wss(self, mock_urandom, mock_open_conn):
        """Test WebSocket connection with TLS."""
        mock_urandom.return_value = b"1234567890123456"
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_conn.return_value = (mock_reader, mock_writer)

        key = base64.b64encode(b"1234567890123456").decode()
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        response = f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"
        mock_reader.read.return_value = response.encode()

        ws = await AsyncWebSocket.connect(
            host="example.com",
            port=443,
            resource="/ws",
            headers=[],
            tls=True,
        )

        assert isinstance(ws, AsyncWebSocket)
        mock_open_conn.assert_called_once()
        args, kwargs = mock_open_conn.call_args
        assert kwargs['host'] == "example.com"
        assert kwargs['port'] == 443
        assert kwargs['server_hostname'] == "example.com"
        assert kwargs['ssl'] is not None

    @patch('gakido.async_websocket.asyncio.open_connection')
    @patch('gakido.async_websocket.os.urandom')
    async def test_connect_upgrade_failed_raises(self, mock_urandom, mock_open_conn):
        """Test connect raises on failed upgrade."""
        mock_urandom.return_value = b"1234567890123456"
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_conn.return_value = (mock_reader, mock_writer)

        # Non-101 response
        mock_reader.read.return_value = b"HTTP/1.1 400 Bad Request\r\n\r\n"

        with pytest.raises(RuntimeError, match="WebSocket upgrade failed"):
            await AsyncWebSocket.connect(
                host="example.com",
                port=80,
                resource="/ws",
                headers=[],
            )

        mock_writer.close.assert_called()
        mock_writer.wait_closed.assert_called()

    @patch('gakido.async_websocket.asyncio.open_connection')
    @patch('gakido.async_websocket.os.urandom')
    async def test_connect_accept_mismatch_raises(self, mock_urandom, mock_open_conn):
        """Test connect raises on accept key mismatch."""
        mock_urandom.return_value = b"1234567890123456"
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_conn.return_value = (mock_reader, mock_writer)

        # Response with wrong accept key
        response = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: wrongkey\r\n\r\n"
        mock_reader.read.return_value = response.encode()

        with pytest.raises(RuntimeError, match="WebSocket accept mismatch"):
            await AsyncWebSocket.connect(
                host="example.com",
                port=80,
                resource="/ws",
                headers=[],
            )


class TestAsyncWebSocketSend:
    """Tests for AsyncWebSocket send methods."""

    async def test_send_text(self):
        """Test sending text message."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        with patch('gakido.async_websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            await ws.send_text("hello")

        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_called_once()
        sent = mock_writer.write.call_args[0][0]

        # Check opcode is 0x81 (FIN + text)
        assert sent[0] == 0x81

    async def test_send_bytes(self):
        """Test sending binary message."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        with patch('gakido.async_websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            await ws.send_bytes(b"binary data")

        mock_writer.write.assert_called_once()
        sent = mock_writer.write.call_args[0][0]

        # Check opcode is 0x82 (FIN + binary)
        assert sent[0] == 0x82


class TestAsyncWebSocketSendFrame:
    """Tests for AsyncWebSocket._send_frame method."""

    async def test_send_frame_small_payload(self):
        """Test sending small payload (< 126 bytes)."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        with patch('gakido.async_websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            await ws._send_frame(0x1, b"hello")

        sent = mock_writer.write.call_args[0][0]
        # FIN + opcode
        assert sent[0] == 0x81
        # MASK bit + length
        assert sent[1] == 0x85  # 0x80 | 5

    async def test_send_frame_medium_payload(self):
        """Test sending medium payload (126-65535 bytes)."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        payload = b"x" * 200

        with patch('gakido.async_websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            await ws._send_frame(0x1, payload)

        sent = mock_writer.write.call_args[0][0]
        # MASK bit + 126 indicator
        assert sent[1] == 0xFE  # 0x80 | 126
        # Extended payload length
        length = struct.unpack("!H", sent[2:4])[0]
        assert length == 200

    async def test_send_frame_large_payload(self):
        """Test sending large payload (> 65535 bytes)."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        payload = b"x" * 70000

        with patch('gakido.async_websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            await ws._send_frame(0x1, payload)

        sent = mock_writer.write.call_args[0][0]
        # MASK bit + 127 indicator
        assert sent[1] == 0xFF  # 0x80 | 127
        # Extended payload length (8 bytes)
        length = struct.unpack("!Q", sent[2:10])[0]
        assert length == 70000


class TestAsyncWebSocketRecv:
    """Tests for AsyncWebSocket recv methods."""

    async def test_recv(self):
        """Test receiving a message."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        # Simulate receiving a text frame: FIN + opcode=1, no mask, length=5, "hello"
        frame = bytes([0x81, 0x05]) + b"hello"
        idx = [0]

        async def read_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_reader.read.side_effect = read_side_effect

        opcode, payload = await ws.recv()

        assert opcode == 0x01
        assert payload == b"hello"

    async def test_recv_masked_frame(self):
        """Test receiving a masked frame (server shouldn't send masked frames, but test anyway)."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        # Masked frame with mask key and payload
        mask_key = b"\x12\x34\x56\x78"
        payload = b"hello"
        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        frame = bytes([0x81, 0x85]) + mask_key + masked_payload  # 0x85 = 0x80 | 5 (masked + length)
        idx = [0]

        async def read_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_reader.read.side_effect = read_side_effect

        opcode, result = await ws.recv()

        assert result == b"hello"

    async def test_recv_extended_length_16(self):
        """Test receiving frame with 16-bit extended length."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        payload = b"x" * 200
        # FIN + text, length=126 indicator, then 2-byte length
        frame = bytes([0x81, 126]) + struct.pack("!H", 200) + payload
        idx = [0]

        async def read_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_reader.read.side_effect = read_side_effect

        opcode, result = await ws.recv()

        assert len(result) == 200

    async def test_recv_extended_length_64(self):
        """Test receiving frame with 64-bit extended length."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        payload = b"x" * 70000
        # FIN + text, length=127 indicator, then 8-byte length
        frame = bytes([0x81, 127]) + struct.pack("!Q", 70000) + payload
        idx = [0]

        async def read_side_effect(n):
            start = idx[0]
            end = min(start + n, len(frame))
            idx[0] = end
            return frame[start:end]

        mock_reader.read.side_effect = read_side_effect

        opcode, result = await ws.recv()

        assert len(result) == 70000


class TestAsyncWebSocketClose:
    """Tests for AsyncWebSocket.close method."""

    async def test_close_sends_close_frame(self):
        """Test close sends close frame."""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.wait_closed = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        with patch('gakido.async_websocket.os.urandom', return_value=b"\x00\x00\x00\x00"):
            await ws.close()

        # Should send close frame (opcode 0x8) then close socket
        sent = mock_writer.write.call_args[0][0]
        assert sent[0] == 0x88  # FIN + close opcode
        mock_writer.close.assert_called()
        mock_writer.wait_closed.assert_called()

    async def test_close_idempotent(self):
        """Test close can be called multiple times."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)
        ws._closed = True

        await ws.close()

        # Should not try to send close frame or close writer again
        mock_writer.write.assert_not_called()


class TestAsyncWebSocketRecvExact:
    """Tests for AsyncWebSocket._recv_exact method."""

    async def test_recv_exact(self):
        """Test _recv_exact reads exact number of bytes."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        mock_reader.read.side_effect = [b"hell", b"lo"]

        result = await ws._recv_exact(5)

        assert result == b"helllo"

    async def test_recv_exact_connection_closed_raises(self):
        """Test _recv_exact raises on connection close."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        mock_reader.read.return_value = b""

        with pytest.raises(RuntimeError, match="Connection closed"):
            await ws._recv_exact(10)


class TestAsyncWebSocketInit:
    """Tests for AsyncWebSocket initialization."""

    def test_init_stores_streams(self):
        """Test AsyncWebSocket stores stream references."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        assert ws.reader is mock_reader
        assert ws.writer is mock_writer
        assert ws._closed is False


class TestAsyncWebSocketContextManager:
    """Tests for AsyncWebSocket context manager support."""

    async def test_async_context_manager(self):
        """Test async context manager functionality."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        ws = AsyncWebSocket(mock_reader, mock_writer)

        async with ws:
            pass

        mock_writer.close.assert_called()
        mock_writer.wait_closed.assert_called()
