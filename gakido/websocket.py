from __future__ import annotations

import base64
import hashlib
import os
import socket
import ssl
import struct
from collections.abc import Iterable


class WebSocket:
    """
    Minimal WebSocket client (RFC6455) over a TCP/TLS socket.
    Supports text/binary recv and send; no extensions; no permessage-deflate.
    """

    def __init__(self, sock: socket.socket):
        self.sock = sock

    @classmethod
    def connect(
        cls,
        host: str,
        port: int,
        resource: str,
        headers: Iterable[tuple[str, str]],
        tls: bool = False,
        timeout: float = 10.0,
    ) -> WebSocket:
        raw = socket.create_connection((host, port), timeout=timeout)
        if tls:
            ctx = ssl.create_default_context()
            raw = ctx.wrap_socket(raw, server_hostname=host)
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
        raw.sendall("".join(req_lines).encode("ascii"))

        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = raw.recv(1024)
            if not chunk:
                break
            resp += chunk
        if b" 101 " not in resp.split(b"\r\n", 1)[0]:
            raw.close()
            raise RuntimeError(f"WebSocket upgrade failed: {resp!r}")
        accept = hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        if f"Sec-WebSocket-Accept: {base64.b64encode(accept).decode()}" not in resp.decode(
            errors="ignore"
        ):
            raw.close()
            raise RuntimeError("WebSocket accept mismatch")
        return cls(raw)

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        self._send_frame(0x2, data)

    def recv(self) -> tuple[int, bytes]:
        opcode, payload = self._recv_frame()
        return opcode, payload

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        finally:
            self.sock.close()

    def _send_frame(self, opcode: int, payload: bytes) -> None:
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
        self.sock.sendall(header + masked)

    def _recv_frame(self) -> tuple[int, bytes]:
        header = self._recv_exact(2)
        b1, b2 = header
        fin = (b1 & 0x80) != 0  # noqa: F841
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask_key = self._recv_exact(4) if masked else None
        payload = self._recv_exact(length)
        if masked and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError("Socket closed")
            buf.extend(chunk)
        return bytes(buf)
