from __future__ import annotations

import socket
import ssl
import time
from collections.abc import Iterable

from .compression import decode_body
from .errors import ConnectionError, ProtocolError, TLSNegotiationError
from .models import Response
from .streaming import StreamingResponse
from .http2 import HTTP2Connection
from .socks5 import socks5_handshake


class Connection:
    """
    Single TCP/TLS connection that can be reused for multiple HTTP/1.1 requests.
    """

    def __init__(
        self,
        host: str,
        port: int,
        scheme: str,
        profile: dict,
        timeout: float = 10.0,
        verify: bool = True,
        proxy_url: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.scheme = scheme
        self.profile = profile
        self.timeout = timeout
        self.verify = verify
        self.proxy_url = proxy_url
        self.sock: socket.socket | ssl.SSLSocket | None = None
        self.negotiated_protocol: str | None = None
        self.created_at = time.time()
        self.closed = True

    def connect(self) -> None:
        raw = self._open_tcp()

        # Perform SOCKS5 handshake if applicable
        if self.proxy_url and self.proxy_url.lower().startswith(("socks5://", "socks5h://")):
            socks5_handshake(raw, self.proxy_url, self.host, self.port)

        if self.scheme == "https":
            context = ssl.create_default_context()
            if not self.verify:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            tls = self.profile.get("tls", {})
            ciphers = tls.get("ciphers")
            if ciphers:
                try:
                    context.set_ciphers(ciphers)
                except ssl.SSLError:
                    # Fallback to platform defaults if the configured suite list
                    # is unsupported by the local OpenSSL/LibreSSL build.
                    try:
                        context.set_ciphers("DEFAULT:@SECLEVEL=1")
                    except ssl.SSLError:
                        # As a last resort, leave defaults untouched.
                        pass
            alpn = tls.get("alpn")
            if not alpn:
                # Try http2 preference if provided in http2 profile.
                alpn = self.profile.get("http2", {}).get("alpn")
            if alpn:
                try:
                    context.set_alpn_protocols(alpn)
                except NotImplementedError:
                    # Older Python/OpenSSL builds may not support ALPN.
                    pass
            curves = tls.get("curves")
            if curves:
                try:
                    # Use the first curve; ordering is limited in stdlib.
                    context.set_ecdh_curve(curves[0])
                except Exception:
                    pass
            try:
                wrapped = context.wrap_socket(raw, server_hostname=self.host)
            except ssl.SSLError:
                # Retry once with a fresh TCP socket and clean default context (no custom ciphers).
                raw.close()
                raw = self._open_tcp()
                fallback_ctx = ssl.create_default_context()
                if not self.verify:
                    fallback_ctx.check_hostname = False
                    fallback_ctx.verify_mode = ssl.CERT_NONE
                try:
                    wrapped = fallback_ctx.wrap_socket(raw, server_hostname=self.host)
                except ssl.SSLError as exc:
                    raw.close()
                    raise TLSNegotiationError(f"TLS handshake failed: {exc}") from exc
            self.negotiated_protocol = wrapped.selected_alpn_protocol()
            self.sock = wrapped
        else:
            self.sock = raw

        self.sock.settimeout(self.timeout)
        self.closed = False

    def request(
        self,
        method: str,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None = None,
    ) -> Response:
        if self.closed or self.sock is None:
            self.connect()

        request_bytes = self._build_request(method, path, headers, body)
        try:
            assert self.sock is not None
            self.sock.sendall(request_bytes)
        except OSError as exc:
            self.close()
            raise ConnectionError(f"Send failed: {exc}") from exc

        if self.negotiated_protocol == "h2":
            h2conn = HTTP2Connection(self.sock)  # type: ignore[arg-type]
            response = h2conn.request(method.upper(), self.host, path, headers, body)
        else:
            response = self._read_response()
        # Respect Connection: close
        if response.headers.get("connection", "").lower() == "close":
            self.close()
        return response

    def stream(
        self,
        method: str,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None = None,
        auto_decompress: bool = True,
        chunk_size: int = 8192,
    ) -> StreamingResponse:
        """
        Send request and return a streaming response.

        The caller is responsible for closing the StreamingResponse.
        The connection will NOT be reused after streaming.
        """
        if self.closed or self.sock is None:
            self.connect()

        request_bytes = self._build_request(method, path, headers, body)
        try:
            assert self.sock is not None
            self.sock.sendall(request_bytes)
        except OSError as exc:
            self.close()
            raise ConnectionError(f"Send failed: {exc}") from exc

        if self.negotiated_protocol == "h2":
            raise NotImplementedError("Streaming not supported for HTTP/2 in sync client")

        return self._read_streaming_response(auto_decompress, chunk_size)

    def _build_request(
        self,
        method: str,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None,
    ) -> bytes:
        lines = [f"{method} {path} HTTP/1.1\r\n".encode("ascii")]
        for name, value in headers:
            lines.append(f"{name}: {value}\r\n".encode("latin-1"))
        lines.append(b"\r\n")
        if body:
            lines.append(body)
        return b"".join(lines)

    def _readline(self) -> bytes:
        assert self.sock is not None
        buf = bytearray()
        while True:
            ch = self.sock.recv(1)
            if not ch:
                break
            buf.extend(ch)
            if buf.endswith(b"\r\n"):
                break
        return bytes(buf)

    def _read_exact(self, n: int) -> bytes:
        assert self.sock is not None
        remaining = n
        chunks: list[bytes] = []
        while remaining > 0:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise ProtocolError("Unexpected EOF while reading body")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_response(self) -> Response:
        status_line = self._readline()
        if not status_line:
            raise ProtocolError("Empty response")
        try:
            # e.g., HTTP/1.1 200 OK
            parts = status_line.decode("latin-1").strip().split(" ", 2)
            version = parts[0].split("/", 1)[1]
            status_code = int(parts[1])
            reason = parts[2] if len(parts) > 2 else ""
        except Exception as exc:
            raise ProtocolError(f"Malformed status line: {status_line!r}") from exc

        headers: list[tuple[str, str]] = []
        while True:
            line = self._readline()
            if line in (b"\r\n", b"\n", b""):
                break
            try:
                name, value = line.split(b":", 1)
            except ValueError as exc:
                raise ProtocolError(f"Malformed header line: {line!r}") from exc
            headers.append(
                (name.decode("latin-1").strip(), value.decode("latin-1").strip())
            )

        header_map = {k.lower(): v for k, v in headers}
        body: bytes
        transfer_encoding = header_map.get("transfer-encoding", "").lower()
        if "chunked" in transfer_encoding:
            body = self._read_chunked_body()
        elif "content-length" in header_map:
            try:
                length = int(header_map["content-length"])
            except ValueError as exc:
                raise ProtocolError("Invalid Content-Length") from exc
            body = self._read_exact(length)
        else:
            body = self._read_until_close()

        decoded_body = decode_body(body, header_map.get("content-encoding", ""))
        return Response(status_code, reason, version, headers, decoded_body)

    def _read_until_close(self) -> bytes:
        assert self.sock is not None
        chunks: list[bytes] = []
        while True:
            try:
                data = self.sock.recv(4096)
            except TimeoutError:
                break
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks)

    def _read_chunked_body(self) -> bytes:
        chunks: list[bytes] = []
        while True:
            line = self._readline()
            if not line:
                break
            try:
                size = int(line.strip(), 16)
            except ValueError as exc:
                raise ProtocolError(f"Invalid chunk size line: {line!r}") from exc
            if size == 0:
                # Consume trailing CRLF after last chunk and optional trailers
                self._readline()
                break
            chunks.append(self._read_exact(size))
            # Discard CRLF
            _ = self._read_exact(2)
        return b"".join(chunks)

    def _read_streaming_response(
        self, auto_decompress: bool, chunk_size: int
    ) -> StreamingResponse:
        """Parse response headers and return a StreamingResponse for body iteration."""
        status_line = self._readline()
        if not status_line:
            raise ProtocolError("Empty response")
        try:
            parts = status_line.decode("latin-1").strip().split(" ", 2)
            version = parts[0].split("/", 1)[1]
            status_code = int(parts[1])
            reason = parts[2] if len(parts) > 2 else ""
        except Exception as exc:
            raise ProtocolError(f"Malformed status line: {status_line!r}") from exc

        headers: list[tuple[str, str]] = []
        while True:
            line = self._readline()
            if line in (b"\r\n", b"\n", b""):
                break
            try:
                name, value = line.split(b":", 1)
            except ValueError as exc:
                raise ProtocolError(f"Malformed header line: {line!r}") from exc
            headers.append(
                (name.decode("latin-1").strip(), value.decode("latin-1").strip())
            )

        header_map = {k.lower(): v for k, v in headers}
        transfer_encoding = header_map.get("transfer-encoding", "").lower()
        chunked = "chunked" in transfer_encoding
        content_length: int | None = None
        if not chunked and "content-length" in header_map:
            try:
                content_length = int(header_map["content-length"])
            except ValueError:
                pass
        content_encoding = header_map.get("content-encoding", "")

        # Transfer socket ownership to StreamingResponse
        assert self.sock is not None
        sock = self.sock
        self.sock = None
        self.closed = True

        return StreamingResponse(
            status_code=status_code,
            reason=reason,
            http_version=version,
            headers=headers,
            sock=sock,
            content_length=content_length,
            chunked=chunked,
            content_encoding=content_encoding,
            auto_decompress=auto_decompress,
            chunk_size=chunk_size,
        )

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None
        self.closed = True

    def _open_tcp(self) -> socket.socket:
        # If using SOCKS5 proxy, connect to the proxy instead of the target
        if self.proxy_url and self.proxy_url.lower().startswith(("socks5://", "socks5h://")):
            from .socks5 import _parse_socks5_url
            proxy_host, proxy_port, _, _ = _parse_socks5_url(self.proxy_url)
            target_host, target_port = proxy_host, proxy_port
        else:
            target_host, target_port = self.host, self.port
        try:
            return socket.create_connection(
                (target_host, target_port), timeout=self.timeout
            )
        except OSError as exc:
            raise ConnectionError(f"TCP connection failed: {exc}") from exc
