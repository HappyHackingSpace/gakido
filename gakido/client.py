from __future__ import annotations

import urllib.parse

from gakido import gakido_core

from gakido.headers import canonicalize_headers
from gakido.multipart import build_multipart
from gakido.impersonation import (
    get_profile,
    apply_ja3_overrides,
    apply_tls_configuration_options,
)
from gakido.models import Response
from gakido.pool import ConnectionPool
from gakido.utils import parse_url


class Client:
    """
    Minimal synchronous client optimized for deterministic header/TLS behavior.
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

    def request(
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

        # Proxy handling (HTTP proxy only for now).
        target_host, target_port, target_path = host, port, path
        if proxy or self.proxies:
            proxy_url = proxy or self.proxies[0]
            p = urllib.parse.urlparse(proxy_url)
            if p.scheme not in ("http",):
                raise ValueError("Only http proxies are supported in sync client")
            target_host, target_port = p.hostname or "", p.port or 80
            target_path = url  # absolute-form for proxy

        conn = self.pool.acquire(parsed.scheme, target_host, target_port)
        try:
            if (
                self.use_native
                and parsed.scheme == "http"
                and not proxy
                and not self.proxies
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

    def get(self, url: str, headers: dict[str, str] | None = None) -> Response:
        return self.request("GET", url, headers=headers, data=None)

    def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | str | dict[str, str] | None = None,
    ) -> Response:
        return self.request("POST", url, headers=headers, data=data)

    def close(self) -> None:
        self.pool.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
