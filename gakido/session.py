from __future__ import annotations


from .client import Client
from .aio import AsyncClient
from .cookies import CookieJar
from .models import Response


class Session:
    """
    Simple session that persists cookies per host across requests.

    Args:
        auto_referer: Automatically set Referer header based on previous request URL (default: True)
        **client_kwargs: Arguments passed to the underlying Client
    """

    def __init__(self, auto_referer: bool = True, **client_kwargs) -> None:
        self.client = Client(**client_kwargs)
        self.cookies = CookieJar()
        self.auto_referer = auto_referer
        self._last_url: str | None = None

    def request(
        self, method: str, url: str, headers: dict[str, str] | None = None, **kwargs
    ) -> Response:
        hdrs = dict(headers or {})
        # Attach Cookie header if present for host.
        from .utils import parse_url

        _, host, _, _ = parse_url(url)
        cookie_header = self.cookies.cookie_header(host)
        if cookie_header and "Cookie" not in {k.title() for k in hdrs}:
            hdrs["Cookie"] = cookie_header

        # Auto-set Referer header from previous request
        if self.auto_referer and self._last_url is not None:
            if "Referer" not in {k.title() for k in hdrs}:
                hdrs["Referer"] = self._last_url

        resp = self.client.request(method, url, headers=hdrs, **kwargs)
        # Capture Set-Cookie
        self.cookies.set_from_headers(resp.raw_headers, host)
        # Store current URL for next request's Referer
        self._last_url = url
        return resp

    def get(
        self, url: str, headers: dict[str, str] | None = None, **kwargs
    ) -> Response:
        return self.request("GET", url, headers=headers, **kwargs)

    def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        data=None,
        **kwargs,
    ) -> Response:
        return self.request("POST", url, headers=headers, data=data, **kwargs)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class AsyncSession:
    """
    Async session that persists cookies per host across requests.

    Args:
        auto_referer: Automatically set Referer header based on previous request URL (default: True)
        **client_kwargs: Arguments passed to the underlying AsyncClient
    """

    def __init__(self, auto_referer: bool = True, **client_kwargs) -> None:
        self.client = AsyncClient(**client_kwargs)
        self.cookies = CookieJar()
        self.auto_referer = auto_referer
        self._last_url: str | None = None

    async def request(
        self, method: str, url: str, headers: dict[str, str] | None = None, **kwargs
    ) -> Response:
        hdrs = dict(headers or {})
        from .utils import parse_url

        _, host, _, _ = parse_url(url)
        cookie_header = self.cookies.cookie_header(host)
        if cookie_header and "Cookie" not in {k.title() for k in hdrs}:
            hdrs["Cookie"] = cookie_header

        # Auto-set Referer header from previous request
        if self.auto_referer and self._last_url is not None:
            if "Referer" not in {k.title() for k in hdrs}:
                hdrs["Referer"] = self._last_url

        resp = await self.client.request(method, url, headers=hdrs, **kwargs)
        # Capture Set-Cookie
        self.cookies.set_from_headers(resp.raw_headers, host)
        # Store current URL for next request's Referer
        self._last_url = url
        return resp

    async def get(
        self, url: str, headers: dict[str, str] | None = None, **kwargs
    ) -> Response:
        return await self.request("GET", url, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        data=None,
        **kwargs,
    ) -> Response:
        return await self.request("POST", url, headers=headers, data=data, **kwargs)

    async def close(self) -> None:
        await self.client.close()

    async def __aenter__(self) -> AsyncSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
