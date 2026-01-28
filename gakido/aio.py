from __future__ import annotations

import asyncio
import json as json_lib
import ssl
import urllib.parse
from collections.abc import Iterable

import h2.connection
import h2.events

from gakido.compression import decode_body, get_accept_encoding
from gakido.errors import ProtocolError
from gakido.headers import canonicalize_headers
from gakido.multipart import build_multipart
from gakido.impersonation import (
    get_profile,
    apply_ja3_overrides,
    apply_tls_configuration_options,
)
from gakido.models import Response
from gakido.streaming import AsyncStreamingResponse
from gakido.utils import parse_url
from gakido.backoff import aretry_with_backoff
from gakido.http3 import is_http3_available, HTTP3Protocol
from gakido.rate_limit import AsyncTokenBucket, AsyncPerHostRateLimiter

# Re-export for tests
__all__ = ['AsyncClient', 'is_http3_available']

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
        auto_decompress: Automatically decompress gzip/deflate/br responses (default: True)
        rate_limit: Global rate limit (requests per second), None to disable
        rate_limit_capacity: Burst capacity for rate limiter (defaults to rate_limit)
        rate_limit_per_host: Per-host rate limit (requests per second), None to disable
        rate_limit_blocking: If True, wait when rate limited; if False, raise RateLimitExceeded
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
        auto_decompress: bool = True,
        max_retries: int = 0,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 60.0,
        retry_jitter: bool = True,
        rate_limit: float | None = None,
        rate_limit_capacity: float | None = None,
        rate_limit_per_host: float | None = None,
        rate_limit_blocking: bool = True,
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
        self.auto_decompress = auto_decompress
        # Retry configuration
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.retry_jitter = retry_jitter

        # HTTP/3 configuration
        self.http3_enabled = http3 and is_http3_available()
        self.http3_fallback = http3_fallback
        self._h3_protocols: dict[str, HTTP3Protocol] = {}  # Cache per host
        self._h3_failed_hosts: set[str] = set()  # Track hosts where H3 failed
        # Rate limiting configuration
        self._rate_limiter: AsyncTokenBucket | None = None
        self._per_host_limiter: AsyncPerHostRateLimiter | None = None
        if rate_limit is not None:
            self._rate_limiter = AsyncTokenBucket(
                rate=rate_limit,
                capacity=rate_limit_capacity,
                blocking=rate_limit_blocking,
            )
        if rate_limit_per_host is not None:
            self._per_host_limiter = AsyncPerHostRateLimiter(
                rate=rate_limit_per_host,
                capacity=rate_limit_capacity,
                blocking=rate_limit_blocking,
            )

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        json: object | None = None,
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

        # Set Accept-Encoding based on profile and auto_decompress setting
        accept_encoding = get_accept_encoding(self.profile, self.auto_decompress)
        if accept_encoding:
            final_headers["Accept-Encoding"] = accept_encoding

        if files:
            ctype, body = build_multipart(
                data if isinstance(data, dict) else None, files
            )
            final_headers["Content-Type"] = ctype
            final_headers["Content-Length"] = str(len(body))
        elif json is not None:
            body = json_lib.dumps(json).encode("utf-8")
            final_headers.setdefault("Content-Type", "application/json")
            final_headers.setdefault("Content-Length", str(len(body)))
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

        # Unified proxy handling (HTTP and SOCKS5)
        target_path = path
        proxy_url: str | None = None
        if proxy or self.proxy_pool:
            proxy_url = proxy or self.proxy_pool[0]
            p = urllib.parse.urlparse(proxy_url)
            if p.scheme.lower() == "http":
                connect_host = p.hostname
                connect_port = p.port or 80
                target_path = url  # absolute form for HTTP proxy
            elif p.scheme.lower() in ("socks5", "socks5h"):
                connect_host = p.hostname
                connect_port = p.port or 1080
            else:
                raise ValueError(f"Unsupported proxy scheme: {p.scheme}")
        else:
            connect_host = host
            connect_port = port

        # For SOCKS5, we must connect without TLS first, perform handshake, then upgrade if needed
        if proxy_url and proxy_url.lower().startswith(("socks5://", "socks5h://")):
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(connect_host, connect_port),
                timeout=self.timeout,
            )
            from .asyncio_socks5 import socks5_handshake_async
            await socks5_handshake_async(writer, reader, proxy_url, host, port)
            # Now perform TLS wrap if needed
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
                # Upgrade to TLS
                transport = await asyncio.wait_for(
                    writer.start_tls(ssl_ctx, server_hostname=host),
                    timeout=self.timeout,
                )
                # After start_tls, reader/writer are already updated; we can get negotiated protocol
                assert transport is not None  # for type checkers
                ssl_obj = transport.get_extra_info("ssl_object")
                negotiated_protocol = ssl_obj.selected_alpn_protocol() if ssl_obj else None
            else:
                negotiated_protocol = None
        else:
            # HTTP proxy or no proxy: use existing path with optional TLS from the start
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

        # Decompress if auto_decompress is enabled
        if self.auto_decompress:
            content_encoding = header_map.get("content-encoding", "")
            body_bytes = decode_body(body_bytes, content_encoding)

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
        response = await proto.request(method, path, headers, body)

        # Decompress if auto_decompress is enabled
        if self.auto_decompress:
            content_encoding = response.headers.get("content-encoding", "")
            if content_encoding:
                decoded_body = decode_body(response.content, content_encoding)
                response = Response(
                    response.status_code,
                    response.reason,
                    response.http_version,
                    response.raw_headers,
                    decoded_body,
                )

        return response

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        json: object | None = None,
        files: dict[str, bytes | tuple[str, bytes, str | None]] | None = None,
        proxy: str | None = None,
        force_http3: bool | None = None,
    ) -> Response:
        """
        Make an async HTTP request with optional retry logic.

        Args:
            method: HTTP method
            url: Request URL
            headers: Additional headers
            data: Request body
            json: JSON-serializable object to send as request body
            files: Multipart files
            proxy: Override proxy URL
            force_http3: Force HTTP/3 if available

        Returns:
            Response object
        """
        # Apply rate limiting
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()
        if self._per_host_limiter is not None:
            parsed, host, _, _ = parse_url(url)
            await self._per_host_limiter.acquire(host)

        if self.max_retries <= 0:
            # No retries, call directly
            return await self._make_request(method, url, headers, data, json, files, proxy, force_http3)

        # Apply retry decorator
        retry_decorator = aretry_with_backoff(
            max_attempts=self.max_retries + 1,  # +1 for initial attempt
            base_delay=self.retry_base_delay,
            max_delay=self.retry_max_delay,
            jitter=self.retry_jitter,
        )
        return await retry_decorator(self._make_request)(method, url, headers, data, json, files, proxy, force_http3)

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
                    body_bytes = bytes(resp_body)
                    # Decompress if auto_decompress is enabled
                    if self.auto_decompress:
                        h2_header_map = {k.lower(): v for k, v in resp_headers}
                        content_encoding = h2_header_map.get("content-encoding", "")
                        body_bytes = decode_body(body_bytes, content_encoding)
                    return Response(status, reason, "2", resp_headers, body_bytes)
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
        json: object | None = None,
        files: dict[str, bytes | tuple[str, bytes, str | None]] | None = None,
        proxy: str | None = None,
    ) -> Response:
        return await self.request(
            "POST", url, headers=headers, data=data, json=json, files=files, proxy=proxy
        )

    async def stream(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        proxy: str | None = None,
        chunk_size: int = 8192,
    ) -> AsyncStreamingResponse:
        """
        Make an async streaming HTTP request without loading entire body into memory.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Additional headers
            data: Request body
            proxy: Override proxy URL
            chunk_size: Size of chunks to yield (default: 8192)

        Returns:
            AsyncStreamingResponse object - must be closed after use

        Example:
            async with client.stream("GET", url) as response:
                async for chunk in response.aiter_bytes():
                    process(chunk)
        """
        parsed, host, port, path = parse_url(url)
        body: bytes | None = None
        final_headers: dict[str, str] = {"Host": host}

        accept_encoding = get_accept_encoding(self.profile, self.auto_decompress)
        if accept_encoding:
            final_headers["Accept-Encoding"] = accept_encoding

        if data is not None:
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

        # Proxy handling
        target_path = path
        proxy_url: str | None = None
        if proxy or self.proxy_pool:
            proxy_url = proxy or self.proxy_pool[0]
            p = urllib.parse.urlparse(proxy_url)
            if p.scheme.lower() == "http":
                connect_host = p.hostname
                connect_port = p.port or 80
                target_path = url
            elif p.scheme.lower() in ("socks5", "socks5h"):
                connect_host = p.hostname
                connect_port = p.port or 1080
            else:
                raise ValueError(f"Unsupported proxy scheme: {p.scheme}")
        else:
            connect_host = host
            connect_port = port

        # For SOCKS5, connect without TLS first, perform handshake, then upgrade
        if proxy_url and proxy_url.lower().startswith(("socks5://", "socks5h://")):
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(connect_host, connect_port),
                timeout=self.timeout,
            )
            from .asyncio_socks5 import socks5_handshake_async
            await socks5_handshake_async(writer, reader, proxy_url, host, port)
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
                await asyncio.wait_for(
                    writer.start_tls(ssl_ctx, server_hostname=host),
                    timeout=self.timeout,
                )
        else:
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

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    connect_host,
                    connect_port,
                    ssl=ssl_ctx,
                    server_hostname=host if ssl_ctx else None,
                ),
                timeout=self.timeout,
            )

        # Send HTTP/1.1 request
        req_lines = [f"{method} {target_path} HTTP/1.1\r\n".encode("ascii")]
        for name, value in merged_headers:
            req_lines.append(f"{name}: {value}\r\n".encode("latin-1"))
        req_lines.append(b"\r\n")
        if body:
            req_lines.append(body)
        writer.writelines(req_lines)
        await writer.drain()

        # Parse response headers
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
        transfer_encoding = header_map.get("transfer-encoding", "").lower()
        chunked = "chunked" in transfer_encoding
        content_length: int | None = None
        if not chunked and "content-length" in header_map:
            try:
                content_length = int(header_map["content-length"])
            except ValueError:
                pass
        content_encoding = header_map.get("content-encoding", "")

        return AsyncStreamingResponse(
            status_code=status_code,
            reason=reason,
            http_version=version,
            headers=headers_list,
            reader=reader,
            writer=writer,
            content_length=content_length,
            chunked=chunked,
            content_encoding=content_encoding,
            auto_decompress=self.auto_decompress,
            chunk_size=chunk_size,
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
