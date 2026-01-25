from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import ssl
import struct
from collections.abc import Iterable


class AsyncWebSocket:
    """
    Async WebSocket client (RFC6455) over asyncio streams.
    Supports text/binary recv and send; no extensions; no permessage-deflate.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False

    @classmethod
    async def connect(
        cls,
        host: str,
        port: int,
        resource: str,
        headers: Iterable[tuple[str, str]],
        tls: bool = False,
        timeout: float = 10.0,
        ssl_context: ssl.SSLContext | None = None,
    ) -> AsyncWebSocket:
        """Connect to a WebSocket server asynchronously."""
        if tls and ssl_context is None:
            ssl_context = ssl.create_default_context()

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host=host,
                port=port,
                ssl=ssl_context if tls else None,
                server_hostname=host if tls else None,
            ),
            timeout=timeout,
        )

        key = base64.b64encode(os.urandom(16)).decode()
        req_lines = [
            f"GET {resource} HTTP/1.1\r\n",
            f"Host: {host}\r\n",
            "Upgrade: websocket\r\n",
            "Connection: Upgrade\r\n",
            f"Sec-WebSocket-Key: {key}\r\n",
            "Sec-WebSocket-Version: 13\r\n",
        ]
        for name, value in headers:
            req_lines.append(f"{name}: {value}\r\n")
        req_lines.append("\r\n")

        writer.write("".join(req_lines).encode("ascii"))
        await writer.drain()

        # Read response headers
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            if not chunk:
                break
            resp += chunk

        if b" 101 " not in resp.split(b"\r\n", 1)[0]:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            raise RuntimeError(f"WebSocket upgrade failed: {resp!r}")

        accept = hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
        ).digest()
        if (
            f"Sec-WebSocket-Accept: {base64.b64encode(accept).decode()}"
            not in resp.decode(errors="ignore")
        ):
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            raise RuntimeError("WebSocket accept mismatch")

        return cls(reader, writer)

    async def send_text(self, text: str) -> None:
        """Send a text message."""
        await self._send_frame(0x1, text.encode("utf-8"))

    async def send_bytes(self, data: bytes) -> None:
        """Send a binary message."""
        await self._send_frame(0x2, data)

    async def recv(self) -> tuple[int, bytes]:
        """Receive a message and return (opcode, payload)."""
        if self._closed:
            raise RuntimeError("WebSocket is closed")
        opcode, payload = await self._recv_frame()
        return opcode, payload

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._closed:
            return
        try:
            await self._send_frame(0x8, b"")
        except Exception:
            pass
        self._closed = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    async def _send_frame(self, opcode: int, payload: bytes) -> None:
        """Send a WebSocket frame."""
        if self._closed:
            raise RuntimeError("WebSocket is closed")

        fin_opcode = 0x80 | opcode
        mask_bit = 0x80
        length = len(payload)
        header = bytearray([fin_opcode])

        if length < 126:
            header.append(mask_bit | length)
        elif length < (1 << 16):
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", length))

        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

        self.writer.write(header + masked)
        await self.writer.drain()

    async def _recv_frame(self) -> tuple[int, bytes]:
        """Receive a WebSocket frame."""
        if self._closed:
            raise RuntimeError("WebSocket is closed")

        header = await self._recv_exact(2)
        b1, b2 = header
        fin = (b1 & 0x80) != 0  # noqa: F841
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F

        if length == 126:
            length = struct.unpack("!H", await self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", await self._recv_exact(8))[0]

        mask_key = await self._recv_exact(4) if masked else None
        payload = await self._recv_exact(length)

        if masked and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        return opcode, payload

    async def _recv_exact(self, n: int) -> bytes:
        """Read exactly n bytes."""
        buf = bytearray()
        while len(buf) < n:
            chunk = await self.reader.read(n - len(buf))
            if not chunk:
                raise RuntimeError("Connection closed")
            buf.extend(chunk)
        return bytes(buf)

    async def __aenter__(self) -> AsyncWebSocket:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
