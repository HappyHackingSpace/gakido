"""Cookie handling with persistence support for Gakido.

Provides CookieJar for in-memory cookie storage with optional
JSON file persistence across program restarts.
"""

from __future__ import annotations

import json
import os
import time
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from collections.abc import Iterable


class CookieJar:
    """
    Host-scoped cookie jar with optional file persistence.

    Stores cookies per host with metadata (expiration, path, secure flag).
    Supports JSON serialization for persistence across sessions.

    Args:
        cookie_file: Optional path to JSON file for persistence.
                    If provided, cookies are loaded on creation and saved on demand.
    """

    def __init__(self, cookie_file: str | Path | None = None) -> None:
        self.store: dict[str, dict[str, dict[str, Any]]] = {}
        self._cookie_file: Path | None = None

        if cookie_file:
            self._cookie_file = Path(cookie_file).expanduser()
            self.load_cookies()

    def set_from_headers(self, headers: Iterable[tuple[str, str]], host: str) -> None:
        """Parse Set-Cookie headers and store cookies."""
        for name, value in headers:
            if name.lower() != "set-cookie":
                continue

            cookie = SimpleCookie()
            cookie.load(value)

            for morsel in cookie.values():
                # Get path (default to "/" if not set or empty)
                path = morsel.get("path") or "/"

                cookie_data = {
                    "value": morsel.value,
                    "expires": None,
                    "path": path,
                    "secure": morsel.get("secure", False),
                    "httponly": morsel.get("httponly", False),
                    "samesite": morsel.get("samesite", None),
                    "timestamp": time.time(),
                }

                # Parse expiration
                expires = morsel.get("expires")
                max_age = morsel.get("max-age")

                if max_age:
                    try:
                        cookie_data["expires"] = time.time() + int(max_age)
                    except ValueError:
                        pass
                elif expires:
                    try:
                        # Parse HTTP-date format
                        from email.utils import parsedate_to_datetime
                        exp_dt = parsedate_to_datetime(expires)
                        cookie_data["expires"] = exp_dt.timestamp()
                    except (ValueError, TypeError):
                        pass

                # Determine cookie domain
                domain = morsel.get("domain")
                if domain:
                    # Domain cookie (applies to subdomains)
                    # Keep the leading dot to distinguish from host-only cookies
                    cookie_host = domain if domain.startswith(".") else f".{domain}"
                else:
                    # Host-only cookie
                    cookie_host = host

                self.store.setdefault(cookie_host, {})[morsel.key] = cookie_data

    def cookie_header(self, host: str) -> str | None:
        """Build Cookie header string for the given host."""
        cookies: list[tuple[str, str]] = []
        now = time.time()

        # Check exact host match
        if host in self.store:
            for name, data in list(self.store[host].items()):
                # Remove expired cookies
                if data.get("expires") and now > data["expires"]:
                    del self.store[host][name]
                    continue
                cookies.append((name, data["value"]))

        # Check domain cookies (e.g., .example.com matches sub.example.com)
        for domain in list(self.store.keys()):
            if domain.startswith(".") and host.endswith(domain):
                for name, data in list(self.store[domain].items()):
                    # Remove expired cookies
                    if data.get("expires") and now > data["expires"]:
                        del self.store[domain][name]
                        continue
                    # Check if cookie already added (host-only takes precedence)
                    if name not in [c[0] for c in cookies]:
                        cookies.append((name, data["value"]))

        # Clean up empty hosts
        for host_key in list(self.store.keys()):
            if not self.store[host_key]:
                del self.store[host_key]

        if not cookies:
            return None

        return "; ".join(f"{k}={v}" for k, v in cookies)

    def save_cookies(self, cookie_file: str | Path | None = None) -> None:
        """Save cookies to JSON file.

        Args:
            cookie_file: Path to save cookies. Uses the file from constructor
                        if not specified.
        """
        path = cookie_file or self._cookie_file
        if not path:
            raise ValueError("No cookie file specified")

        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Filter out expired cookies before saving
        now = time.time()
        data_to_save: dict[str, dict[str, dict[str, Any]]] = {}

        for host, cookies in self.store.items():
            valid_cookies = {}
            for name, data in cookies.items():
                if data.get("expires") is None or data["expires"] > now:
                    valid_cookies[name] = data
            if valid_cookies:
                data_to_save[host] = valid_cookies

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2)

        # Set restrictive permissions (user-only)
        os.chmod(path, 0o600)

    def load_cookies(self, cookie_file: str | Path | None = None) -> None:
        """Load cookies from JSON file.

        Args:
            cookie_file: Path to load cookies from. Uses the file from constructor
                        if not specified.
        """
        path = cookie_file or self._cookie_file
        if not path:
            return

        path = Path(path).expanduser()

        if not path.exists():
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            now = time.time()

            # Filter out expired cookies on load
            for host, cookies in data.items():
                valid_cookies = {}
                for name, cookie_data in cookies.items():
                    expires = cookie_data.get("expires")
                    if expires is None or expires > now:
                        valid_cookies[name] = cookie_data

                if valid_cookies:
                    self.store[host] = valid_cookies

        except (json.JSONDecodeError, OSError):
            # Fail silently - start with empty jar
            pass

    def clear_cookies(self) -> None:
        """Clear all cookies from memory and optionally the file."""
        self.store.clear()

        if self._cookie_file and self._cookie_file.exists():
            self._cookie_file.unlink(missing_ok=True)

    def get_cookies_for_host(self, host: str) -> dict[str, dict[str, Any]]:
        """Get all cookies for a specific host (including non-expired)."""
        result = {}
        now = time.time()

        # Direct host match
        if host in self.store:
            for name, data in self.store[host].items():
                if data.get("expires") is None or data["expires"] > now:
                    result[name] = data

        return result

    def __repr__(self) -> str:
        hosts = len(self.store)
        total = sum(len(cookies) for cookies in self.store.values())
        return f"<CookieJar hosts={hosts} cookies={total}>"
