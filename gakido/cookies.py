from http.cookies import SimpleCookie
from collections.abc import Iterable


class CookieJar:
    """
    Minimal host-scoped cookie jar. Stores cookies per host and returns a
    Cookie header string for that host.
    """

    def __init__(self) -> None:
        self.store: dict[str, dict[str, str]] = {}

    def set_from_headers(self, headers: Iterable[tuple[str, str]], host: str) -> None:
        for name, value in headers:
            if name.lower() != "set-cookie":
                continue
            cookie = SimpleCookie()
            cookie.load(value)
            for morsel in cookie.values():
                self.store.setdefault(host, {})[morsel.key] = morsel.value

    def cookie_header(self, host: str) -> str | None:
        jar = self.store.get(host)
        if not jar:
            return None
        return "; ".join(f"{k}={v}" for k, v in jar.items())

    def __repr__(self) -> str:
        return f"<Cookies {self.store}>"
