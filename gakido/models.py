from __future__ import annotations

import json
from collections.abc import Iterable


class Response:
    """
    Lightweight HTTP response that preserves header order while
    exposing convenient helpers.
    """

    def __init__(
        self,
        status_code: int,
        reason: str,
        http_version: str,
        headers: Iterable[tuple[str, str]],
        body: bytes,
    ) -> None:
        self.status_code = status_code
        self.reason = reason
        self.http_version = http_version
        self.raw_headers: list[tuple[str, str]] = list(headers)
        self._body = body

    @property
    def headers(self) -> dict[str, str]:
        # Last-write wins while keeping access case-insensitive for callers.
        out: dict[str, str] = {}
        for name, value in self.raw_headers:
            out[name.lower()] = value
        return out

    @property
    def content(self) -> bytes:
        return self._body

    @property
    def text(self) -> str:
        encoding = "utf-8"
        ctype = self.headers.get("content-type")
        if ctype and "charset=" in ctype:
            encoding = ctype.split("charset=")[-1].split(";")[0].strip() or encoding
        try:
            return self._body.decode(encoding, errors="replace")
        except LookupError:
            return self._body.decode("utf-8", errors="replace")

    def json(self) -> object:
        return json.loads(self.text)

    def __repr__(self) -> str:
        return f"<Response [{self.status_code}] {len(self._body)} bytes>"
