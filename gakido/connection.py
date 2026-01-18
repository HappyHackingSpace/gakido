from __future__ import annotations

import gzip
import io
import socket
import ssl
import time
import zlib
from collections.abc import Iterable

import brotli

from .errors import ConnectionError, ProtocolError, TLSNegotiationError
from .models import Response
from .http2 import HTTP2Connection


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
    ) -> None:
        self.host = host
        self.port = port
        self.scheme = scheme
        self.profile = profile
        self.timeout = timeout
        self.verify = verify
        self.sock: socket.socket | ssl.SSLSocket | None = None
        self.negotiated_protocol: str | None = None
        self.created_at = time.time()
        self.closed = True

    def connect(self) -> None:
        raw = self._open_tcp()

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

        decoded_body = self._decode_body(body, header_map.get("content-encoding", ""))
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

    def _decode_body(self, body: bytes, encoding: str) -> bytes:
        encoding = encoding.lower()
        if encoding == "gzip":
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as f:
                    return f.read()
            except Exception:
                return body
        if encoding == "deflate":
            try:
                return zlib.decompress(body, -zlib.MAX_WBITS)
            except Exception:
                return body
        if encoding == "br" and brotli is not None:
            try:
                return brotli.decompress(body)
            except Exception:
                return body
        return body

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None
        self.closed = True

    def _open_tcp(self) -> socket.socket:
        try:
            return socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
        except OSError as exc:
            raise ConnectionError(f"TCP connection failed: {exc}") from exc
