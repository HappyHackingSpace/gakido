from __future__ import annotations

import urllib.parse

from gakido import gakido_core

from gakido.compression import decode_body, get_accept_encoding
from gakido.headers import canonicalize_headers
from gakido.multipart import build_multipart
from gakido.impersonation import (
    get_profile,
    apply_ja3_overrides,
    apply_tls_configuration_options,
)
from gakido.models import Response
from gakido.streaming import StreamingResponse
from gakido.pool import ConnectionPool
from gakido.utils import parse_url
from gakido.backoff import retry_with_backoff

class Client:
    """
    Minimal synchronous client optimized for deterministic header/TLS behavior.

    Args:
        impersonate: Browser profile to impersonate (default: "chrome_120")
        timeout: Request timeout in seconds
        verify: Whether to verify SSL certificates
        max_per_host: Maximum connections per host
        use_native: Use native C extension for HTTP (faster)
        proxies: List of proxy URLs
        ja3: Custom JA3 fingerprint overrides
        tls_configuration_options: Custom TLS options
        force_http1: Force HTTP/1.1 only (default: True)
        auto_decompress: Automatically decompress gzip/deflate/br responses (default: True)
    """

    def __init__(
        self,
        impersonate: str = "chrome_120",
        timeout: float = 10.0,
        verify: bool = True,
        max_per_host: int = 4,
        use_native: bool = True,
        proxies: list[str] | None = None,
        ja3: dict | None = None,
        tls_configuration_options: dict | None = None,
        force_http1: bool = True,
        auto_decompress: bool = True,
        max_retries: int = 0,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 60.0,
        retry_jitter: bool = True,
    ) -> None:
        profile = get_profile(impersonate)
        if force_http1:
            profile.setdefault("tls", {})["alpn"] = ["http/1.1"]
            profile.setdefault("http2", {})["alpn"] = ["http/1.1"]
        profile = apply_tls_configuration_options(profile, tls_configuration_options)
        self.profile = apply_ja3_overrides(profile, ja3)
        self.pool = ConnectionPool(
            profile=self.profile,
            timeout=timeout,
            verify=verify,
            max_per_host=max_per_host,
        )
        self.timeout = timeout
        self.verify = verify
        self.use_native = use_native and gakido_core is not None
        self.proxies = proxies or []
        self.auto_decompress = auto_decompress
        # Retry configuration
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.retry_jitter = retry_jitter

    def _make_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        files: dict[str, bytes | tuple[str, bytes, str | None]] | None = None,
        proxy: str | None = None,
    ) -> Response:
        parsed, host, port, path = parse_url(url)
        body: bytes | None = None
        final_headers: dict[str, str] = {"Host": host}

        # Set Accept-Encoding based on profile and auto_decompress setting
        # User-provided headers can override this
        accept_encoding = get_accept_encoding(self.profile, self.auto_decompress)
        if accept_encoding:
            final_headers["Accept-Encoding"] = accept_encoding

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
        else:
            final_headers.setdefault("Content-Length", "0") if method in (
                "POST",
                "PUT",
            ) else None

        default_headers = list(self.profile.get("headers", {}).get("default", []))
        order = self.profile.get("headers", {}).get("order", [])
        # Merge: defaults -> computed (host/content-length/etc) -> user overrides.
        merged_headers = canonicalize_headers(
            default_headers,
            {**final_headers, **(headers or {})},
            order=order,
        )
        # Ensure Connection keep-alive by default.
        seen_conn = any(name.lower() == "connection" for name, _ in merged_headers)
        if not seen_conn:
            merged_headers.insert(1, ("Connection", "keep-alive"))

        # Unified proxy handling (HTTP and SOCKS5)
        proxy_url: str | None = None
        target_path = path
        if proxy or self.proxies:
            proxy_url = proxy or self.proxies[0]
            p = urllib.parse.urlparse(proxy_url)
            if p.scheme.lower() == "http":
                # HTTP proxy: connect to proxy; use absolute-form request path
                target_host, target_port = p.hostname or "", p.port or 80
                target_path = url
            elif p.scheme.lower() in ("socks5", "socks5h"):
                # SOCKS5 proxy: connection logic handled in Connection; keep target host/port for pool key
                target_host, target_port = host, port
            else:
                raise ValueError(f"Unsupported proxy scheme: {p.scheme}")

        else:
            target_host, target_port = host, port

        conn = self.pool.acquire(parsed.scheme, target_host, target_port, proxy_url=proxy_url)
        try:
            if (
                self.use_native
                and parsed.scheme == "http"
                and not proxy_url
            ):
                result = gakido_core.request(
                    method.upper(),
                    target_host,
                    target_port,
                    target_path,
                    merged_headers,
                    body or b"",
                    self.timeout,
                )
                status_code, reason, version, raw_headers, raw_body = result
                # Decompress if auto_decompress is enabled
                if self.auto_decompress:
                    content_encoding = ""
                    for name, value in raw_headers:
                        if name.lower() == "content-encoding":
                            content_encoding = value
                            break
                    raw_body = decode_body(raw_body, content_encoding)
                response = Response(status_code, reason, version, raw_headers, raw_body)
            else:
                response = conn.request(
                    method.upper(), target_path, merged_headers, body
                )
        except Exception:
            conn.close()
            raise

        if not conn.closed:
            self.pool.release(conn)
        return response

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        files: dict[str, bytes | tuple[str, bytes, str | None]] | None = None,
        proxy: str | None = None,
    ) -> Response:
        """
        Make an HTTP request with optional retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Additional headers
            data: Request body
            files: Multipart files
            proxy: Override proxy URL

        Returns:
            Response object
        """
        if self.max_retries <= 0:
            # No retries, call directly
            return self._make_request(method, url, headers, data, files, proxy)

        # Apply retry decorator
        retry_decorator = retry_with_backoff(
            max_attempts=self.max_retries + 1,  # +1 for initial attempt
            base_delay=self.retry_base_delay,
            max_delay=self.retry_max_delay,
            jitter=self.retry_jitter,
        )
        return retry_decorator(self._make_request)(method, url, headers, data, files, proxy)

    def stream(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        proxy: str | None = None,
        chunk_size: int = 8192,
    ) -> StreamingResponse:
        """
        Make a streaming HTTP request without loading entire body into memory.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Additional headers
            data: Request body
            proxy: Override proxy URL
            chunk_size: Size of chunks to yield (default: 8192)

        Returns:
            StreamingResponse object - must be closed after use

        Example:
            with client.stream("GET", url) as response:
                for chunk in response.iter_bytes():
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
        else:
            final_headers.setdefault("Content-Length", "0") if method in (
                "POST",
                "PUT",
            ) else None

        default_headers = list(self.profile.get("headers", {}).get("default", []))
        order = self.profile.get("headers", {}).get("order", [])
        merged_headers = canonicalize_headers(
            default_headers,
            {**final_headers, **(headers or {})},
            order=order,
        )
        seen_conn = any(name.lower() == "connection" for name, _ in merged_headers)
        if not seen_conn:
            merged_headers.insert(1, ("Connection", "keep-alive"))

        # Proxy handling
        proxy_url: str | None = None
        target_path = path
        if proxy or self.proxies:
            proxy_url = proxy or self.proxies[0]
            p = urllib.parse.urlparse(proxy_url)
            if p.scheme.lower() == "http":
                target_host, target_port = p.hostname or "", p.port or 80
                target_path = url
            elif p.scheme.lower() in ("socks5", "socks5h"):
                target_host, target_port = host, port
            else:
                raise ValueError(f"Unsupported proxy scheme: {p.scheme}")
        else:
            target_host, target_port = host, port

        from gakido.connection import Connection
        conn = Connection(
            target_host, target_port, parsed.scheme, self.profile,
            self.timeout, self.verify, proxy_url=proxy_url
        )

        return conn.stream(
            method.upper(), target_path, merged_headers, body,
            auto_decompress=self.auto_decompress, chunk_size=chunk_size
        )

    def get(self, url: str, headers: dict[str, str] | None = None, proxy: str | None = None) -> Response:
        return self.request("GET", url, headers=headers, data=None, proxy=proxy)

    def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
        proxy: str | None = None,
    ) -> Response:
        return self.request("POST", url, headers=headers, data=data, proxy=proxy)

    def close(self) -> None:
        self.pool.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
