from __future__ import annotations

import asyncio
import ssl
import urllib.parse
from collections.abc import Iterable

import h2.connection
import h2.events

from gakido.errors import ProtocolError
from gakido.headers import canonicalize_headers
from gakido.multipart import build_multipart
from gakido.impersonation import (
    get_profile,
    apply_ja3_overrides,
    apply_tls_configuration_options,
)
from gakido.models import Response
from gakido.utils import parse_url
from gakido.http3 import is_http3_available, HTTP3Protocol


class AsyncClient:
    """
    Async HTTP client with support for HTTP/1.1, HTTP/2, and HTTP/3.

    HTTP/3 support requires the optional `h3` extra: pip install gakido[h3]

    Args:
        impersonate: Browser profile to impersonate (default: "chrome_120")
        timeout: Request timeout in seconds
        verify: Whether to verify SSL certificates
        proxy_pool: List of proxy URLs for rotation
        ja3: Custom JA3 fingerprint overrides
        tls_configuration_options: Custom TLS options
        force_http1: Force HTTP/1.1 only (default: True)
        http3: Enable HTTP/3 for compatible targets (default: False)
        http3_fallback: Fall back to HTTP/1.1 or HTTP/2 if HTTP/3 fails (default: True)
    """

    def __init__(
        self,
        impersonate: str = "chrome_120",
        timeout: float = 10.0,
        verify: bool = True,
        proxy_pool: Iterable[str] | None = None,
        ja3: dict | None = None,
        tls_configuration_options: dict | None = None,
        force_http1: bool = True,
        http3: bool = False,
        http3_fallback: bool = True,
    ) -> None:
        profile = get_profile(impersonate)
        if force_http1 and not http3:
            profile.setdefault("tls", {})["alpn"] = ["http/1.1"]
            profile.setdefault("http2", {})["alpn"] = ["http/1.1"]
        profile = apply_tls_configuration_options(profile, tls_configuration_options)
        self.profile = apply_ja3_overrides(profile, ja3)
        self.timeout = timeout
        self.verify = verify
        self.proxy_pool = list(proxy_pool) if proxy_pool else []

        # HTTP/3 configuration
        self.http3_enabled = http3 and is_http3_available()
        self.http3_fallback = http3_fallback
        self._h3_protocols: dict[str, HTTP3Protocol] = {}  # Cache per host
        self._h3_failed_hosts: set[str] = set()  # Track hosts where H3 failed

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        files: dict[str, bytes | tuple[str, bytes, str | None]] | None = None,
        proxy: str | None = None,
        force_http3: bool | None = None,
    ) -> Response:
        """
        Send an HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Target URL
            headers: Optional request headers
            data: Optional request body (bytes, str, or dict for form data)
            files: Optional files for multipart upload
            proxy: Optional proxy URL (overrides proxy_pool)
            force_http3: Force HTTP/3 for this request (None uses client default)

        Returns:
            Response object
        """
        parsed, host, port, path = parse_url(url)
        body: bytes | None = None
        final_headers: dict[str, str] = {"Host": host}
        final_headers.setdefault("Accept-Encoding", "identity")

        if files:
            ctype, body = build_multipart(
                data if isinstance(data, dict) else None, files
            )
            final_headers["Content-Type"] = ctype
            final_headers["Content-Length"] = str(len(body))
        elif data is not None:
            if isinstance(data, bytes):
                body = data
            elif isinstance(data, str):
                body = data.encode("utf-8")
            elif isinstance(data, dict):
                body = urllib.parse.urlencode(data).encode("utf-8")
                final_headers.setdefault(
                    "Content-Type", "application/x-www-form-urlencoded; charset=utf-8"
                )
            else:
                raise TypeError("Unsupported data type for request body")
            final_headers.setdefault("Content-Length", str(len(body)))

        default_headers = list(self.profile.get("headers", {}).get("default", []))
        order = self.profile.get("headers", {}).get("order", [])
        merged_headers = canonicalize_headers(
            default_headers,
            {**final_headers, **(headers or {})},
            order=order,
        )

        # Determine if we should try HTTP/3
        use_http3 = force_http3 if force_http3 is not None else self.http3_enabled
        use_http3 = (
            use_http3
            and parsed.scheme == "https"
            and not proxy
            and not self.proxy_pool
            and host not in self._h3_failed_hosts
        )

        # Try HTTP/3 first if enabled
        if use_http3:
            try:
                return await self._request_h3(method, host, port, path, merged_headers, body)
            except Exception:
                if not self.http3_fallback:
                    raise
                # Mark this host as failed for HTTP/3 and fall back
                self._h3_failed_hosts.add(host)

        # Proxy handling (HTTP proxy only for now).
        target_host, target_port, target_path = host, port, path  # noqa: F841
        if proxy or self.proxy_pool:
            proxy_url = proxy or self.proxy_pool[0]
            p = urllib.parse.urlparse(proxy_url)
            if p.scheme not in ("http",):
                raise ValueError("Only http proxy supported in async client")
            connect_host = p.hostname
            connect_port = p.port or 80
            target_path = url  # absolute form for proxies
        else:
            connect_host = host
            connect_port = port

        ssl_ctx: ssl.SSLContext | None = None
        if parsed.scheme == "https":
            ssl_ctx = ssl.create_default_context()
            if not self.verify:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            tls = self.profile.get("tls", {})
            ciphers = tls.get("ciphers")
            if ciphers:
                try:
                    ssl_ctx.set_ciphers(ciphers)
                except ssl.SSLError:
                    try:
                        ssl_ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
                    except ssl.SSLError:
                        pass
            alpn = tls.get("alpn") or self.profile.get("http2", {}).get("alpn")
            if alpn:
                try:
                    ssl_ctx.set_alpn_protocols(alpn)
                except NotImplementedError:
                    pass

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                connect_host,
                connect_port,
                ssl=ssl_ctx,
                server_hostname=host if ssl_ctx else None,
            ),
            timeout=self.timeout,
        )

        negotiated_protocol = None
        if ssl_ctx and hasattr(
            writer.get_extra_info("ssl_object"), "selected_alpn_protocol"
        ):
            ssl_obj = writer.get_extra_info("ssl_object")
            if ssl_obj:
                negotiated_protocol = ssl_obj.selected_alpn_protocol()

        if negotiated_protocol == "h2":
            return await self._request_h2(
                reader, writer, method, host, target_path, merged_headers, body
            )

        # HTTP/1.1 path
        req_lines = [f"{method} {target_path} HTTP/1.1\r\n".encode("ascii")]
        for name, value in merged_headers:
            req_lines.append(f"{name}: {value}\r\n".encode("latin-1"))
        req_lines.append(b"\r\n")
        if body:
            req_lines.append(body)
        writer.writelines(req_lines)
        await writer.drain()

        status_line = await reader.readline()
        if not status_line:
            raise ProtocolError("Empty response")
        try:
            parts = status_line.decode("latin-1").strip().split(" ", 2)
            version = parts[0].split("/", 1)[1]
            status_code = int(parts[1])
            reason = parts[2] if len(parts) > 2 else ""
        except Exception as exc:
            raise ProtocolError(f"Malformed status line: {status_line!r}") from exc

        headers_list: list[tuple[str, str]] = []
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            try:
                name, value = line.split(b":", 1)
            except ValueError as exc:
                raise ProtocolError(f"Malformed header line: {line!r}") from exc
            headers_list.append(
                (name.decode("latin-1").strip(), value.decode("latin-1").strip())
            )

        header_map = {k.lower(): v for k, v in headers_list}
        body_bytes: bytes
        if header_map.get("transfer-encoding", "").lower().endswith("chunked"):
            body_chunks: list[bytes] = []
            while True:
                line = await reader.readline()
                if not line:
                    break
                size = int(line.strip(), 16)
                if size == 0:
                    await reader.readline()
                    break
                body_chunks.append(await reader.readexactly(size))
                await reader.readexactly(2)
            body_bytes = b"".join(body_chunks)
        elif "content-length" in header_map:
            body_bytes = await reader.readexactly(int(header_map["content-length"]))
        else:
            body_bytes = await reader.read(-1)

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return Response(status_code, reason, version, headers_list, body_bytes)

    async def _request_h3(
        self,
        method: str,
        host: str,
        port: int,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None,
    ) -> Response:
        """Send request using HTTP/3 (QUIC)."""
        # Get or create HTTP/3 protocol for this host
        cache_key = f"{host}:{port}"
        if cache_key not in self._h3_protocols:
            proto = HTTP3Protocol(
                host=host,
                port=port,
                verify=self.verify,
                timeout=self.timeout,
                profile=self.profile,
            )
            await proto.connect()
            self._h3_protocols[cache_key] = proto

        proto = self._h3_protocols[cache_key]
        return await proto.request(method, path, headers, body)

    async def _request_h2(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        method: str,
        authority: str,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None,
    ) -> Response:
        h2conn = h2.connection.H2Connection()
        h2conn.initiate_connection()
        writer.write(h2conn.data_to_send())
        await writer.drain()

        stream_id = h2conn.get_next_available_stream_id()
        pseudo_headers = [
            (":method", method),
            (":authority", authority),
            (":scheme", "https"),
            (":path", path),
        ]
        h2conn.send_headers(
            stream_id, pseudo_headers + list(headers), end_stream=body is None
        )
        if body:
            h2conn.send_data(stream_id, body, end_stream=True)
        writer.write(h2conn.data_to_send())
        await writer.drain()

        resp_headers: list[tuple[str, str]] = []
        resp_body = bytearray()
        status = 0
        reason = ""

        while True:
            data = await reader.read(65536)
            if not data:
                break
            events = h2conn.receive_data(data)
            writer.write(h2conn.data_to_send())
            await writer.drain()
            for event in events:
                if isinstance(event, h2.events.ResponseReceived):
                    status = int(event.headers[0][1]) if event.headers else 0
                    resp_headers.extend(
                        (
                            name.decode() if isinstance(name, bytes) else name,
                            value.decode() if isinstance(value, bytes) else value,
                        )
                        for name, value in event.headers
                        if not name.startswith(b":")
                    )
                elif isinstance(event, h2.events.DataReceived):
                    resp_body.extend(event.data)
                    h2conn.acknowledge_received_data(
                        event.flow_controlled_length, stream_id
                    )
                elif isinstance(event, h2.events.StreamEnded):
                    reason = "OK"
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    return Response(status, reason, "2", resp_headers, bytes(resp_body))
                elif isinstance(event, h2.events.StreamReset):
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    raise ProtocolError(f"Stream reset: {event.error_code}")
        raise ProtocolError("Connection closed before stream ended")

    async def get(
        self, url: str, headers: dict[str, str] | None = None, proxy: str | None = None
    ) -> Response:
        return await self.request("GET", url, headers=headers, data=None, proxy=proxy)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        files: dict[str, bytes | tuple[str, bytes, str | None]] | None = None,
        proxy: str | None = None,
    ) -> Response:
        return await self.request(
            "POST", url, headers=headers, data=data, files=files, proxy=proxy
        )

    async def close(self) -> None:
        """Close all HTTP/3 connections."""
        for proto in self._h3_protocols.values():
            try:
                await proto.close()
            except Exception:
                pass
        self._h3_protocols.clear()
        self._h3_failed_hosts.clear()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
