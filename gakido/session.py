from __future__ import annotations


from .client import Client
from .cookies import CookieJar
from .models import Response


class Session:
    """
    Simple session that persists cookies per host across requests.
    """

    def __init__(self, **client_kwargs) -> None:
        self.client = Client(**client_kwargs)
        self.cookies = CookieJar()

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

        resp = self.client.request(method, url, headers=hdrs, **kwargs)
        # Capture Set-Cookie
        self.cookies.set_from_headers(resp.raw_headers, host)
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
