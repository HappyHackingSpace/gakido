from __future__ import annotations

import urllib.parse

from .errors import CircularRedirectError, TooManyRedirectsError
from .models import Response

#: Status codes that trigger redirect following when a Location header is set.
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

#: Headers that must not leak to a different host on a cross-host redirect.
SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization"})


def is_redirect(response: Response) -> bool:
    """Return True when the response is a followable redirect."""
    return response.status_code in REDIRECT_STATUSES and bool(
        response.headers.get("location")
    )


def redirect_method(method: str, status_code: int) -> str:
    """
    Return the method to use for the next hop.

    Mirrors browser behavior: 303 always switches to GET (except HEAD),
    and 301/302 downgrade POST to GET; 307/308 preserve the method.
    """
    method = method.upper()
    if status_code == 303 and method != "HEAD":
        return "GET"
    if status_code in (301, 302) and method == "POST":
        return "GET"
    return method


def prepare_redirect(
    method: str, url: str, response: Response
) -> tuple[str, str, bool]:
    """
    Compute the next hop for a redirect response.

    Returns (next_method, next_url, keep_body). The Location header is
    resolved relative to the current URL, and the body is only kept when
    the method is preserved (e.g. 307/308).
    """
    location = response.headers.get("location", "")
    next_url = urllib.parse.urljoin(url, location)
    next_method = redirect_method(method, response.status_code)
    keep_body = next_method == method.upper()
    return next_method, next_url, keep_body


def strip_sensitive_headers(
    headers: dict[str, str] | None, old_url: str, new_url: str
) -> dict[str, str] | None:
    """Drop credential-bearing headers when a redirect changes host."""
    if headers is None:
        return None
    old_host = urllib.parse.urlsplit(old_url).hostname
    new_host = urllib.parse.urlsplit(new_url).hostname
    if old_host == new_host:
        return headers
    return {
        name: value
        for name, value in headers.items()
        if name.lower() not in SENSITIVE_HEADERS
    }


class RedirectTracker:
    """
    Tracks a redirect chain, enforcing a maximum number of hops and
    detecting circular redirects (revisiting a method/URL pair).
    """

    def __init__(self, method: str, url: str, max_redirects: int) -> None:
        self.max_redirects = max_redirects
        self.history: list[Response] = []
        self._seen: set[tuple[str, str]] = {(method.upper(), url)}

    def follow(self, method: str, url: str, response: Response) -> None:
        """
        Record one redirect hop.

        Raises:
            TooManyRedirectsError: when the chain exceeds max_redirects hops.
            CircularRedirectError: when the chain revisits a method/URL pair.
        """
        self.history.append(response)
        if len(self.history) > self.max_redirects:
            raise TooManyRedirectsError(
                f"Exceeded maximum of {self.max_redirects} redirects"
            )
        key = (method.upper(), url)
        if key in self._seen:
            raise CircularRedirectError(f"Circular redirect detected: {method} {url}")
        self._seen.add(key)
