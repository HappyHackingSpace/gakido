"""HTTP response caching implementation for Gakido.

Supports standard HTTP caching mechanisms including Cache-Control,
ETag, and Last-Modified headers.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gakido.models import Response


class CacheBackend(ABC):
    """Abstract base class for cache storage backends."""

    @abstractmethod
    def get(self, key: str) -> dict | None:
        """Retrieve a cached entry by key.

        Args:
            key: Cache key

        Returns:
            Cached entry dict or None if not found/expired
        """
        pass

    @abstractmethod
    def set(self, key: str, entry: dict, ttl: int | None = None) -> None:
        """Store an entry in the cache.

        Args:
            key: Cache key
            entry: Entry to cache
            ttl: Time to live in seconds (None for default)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a cached entry."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entries."""
        pass


class MemoryCache(CacheBackend):
    """In-memory cache backend with TTL support."""

    def __init__(self, default_ttl: int = 3600) -> None:
        self._cache: dict[str, tuple[dict, float | None]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> dict | None:
        if key not in self._cache:
            return None

        entry, expires_at = self._cache[key]

        # Check if expired
        if expires_at is not None and time.time() > expires_at:
            del self._cache[key]
            return None

        return entry

    def set(self, key: str, entry: dict, ttl: int | None = None) -> None:
        ttl = ttl or self._default_ttl
        expires_at = time.time() + ttl if ttl else None
        self._cache[key] = (entry, expires_at)

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()


class FileCache(CacheBackend):
    """File-based cache backend with TTL support."""

    def __init__(self, cache_dir: str | Path, default_ttl: int = 3600) -> None:
        self._cache_dir = Path(cache_dir).expanduser()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl

        # Ensure directory permissions (user-only)
        os.chmod(self._cache_dir, 0o700)

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        # Use hash to create safe filename
        filename = hashlib.sha256(key.encode()).hexdigest() + ".json"
        return self._cache_dir / filename

    def get(self, key: str) -> dict | None:
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)

            # Check if expired
            if data.get("expires_at") and time.time() > data["expires_at"]:
                cache_path.unlink(missing_ok=True)
                return None

            return data["entry"]
        except (json.JSONDecodeError, OSError):
            cache_path.unlink(missing_ok=True)
            return None

    def set(self, key: str, entry: dict, ttl: int | None = None) -> None:
        ttl = ttl or self._default_ttl
        expires_at = time.time() + ttl if ttl else None

        data = {
            "key": key,
            "entry": entry,
            "expires_at": expires_at,
            "cached_at": time.time(),
        }

        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.chmod(cache_path, 0o600)  # User-only permissions
        except OSError:
            pass  # Fail silently if we can't write cache

    def delete(self, key: str) -> None:
        cache_path = self._get_cache_path(key)
        cache_path.unlink(missing_ok=True)

    def clear(self) -> None:
        for cache_file in self._cache_dir.glob("*.json"):
            cache_file.unlink(missing_ok=True)


class CacheController:
    """HTTP cache controller implementing RFC 7234 caching logic."""

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend

    @staticmethod
    def _make_cache_key(method: str, url: str, headers: dict[str, str] | None) -> str:
        """Generate a cache key from request components."""
        # Normalize the key components
        key_parts = [method.upper(), url]

        # Include Vary headers in key (simplified - just include all request headers)
        if headers:
            # Sort headers for consistent key generation
            for name in sorted(headers.keys()):
                # Skip hop-by-hop headers
                if name.lower() not in (
                    "connection",
                    "keep-alive",
                    "proxy-authenticate",
                    "proxy-authorization",
                    "te",
                    "trailers",
                    "transfer-encoding",
                    "upgrade",
                ):
                    key_parts.append(f"{name}:{headers[name]}")

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    @staticmethod
    def _parse_cache_control(header_value: str | None) -> dict[str, str | None]:
        """Parse Cache-Control header value."""
        directives: dict[str, str | None] = {}
        if not header_value:
            return directives

        for directive in header_value.lower().split(","):
            directive = directive.strip()
            if "=" in directive:
                key, value = directive.split("=", 1)
                directives[key.strip()] = value.strip()
            else:
                directives[directive] = None

        return directives

    def _is_cacheable(self, method: str, response: Response) -> bool:
        """Determine if a response can be cached."""
        # Only cache GET and HEAD requests
        if method.upper() not in ("GET", "HEAD"):
            return False

        # Check response status code
        if response.status_code not in (
            200,
            203,
            204,
            206,
            300,
            301,
            404,
            405,
            410,
            414,
            501,
        ):
            return False

        headers = response.headers

        # Check Cache-Control: no-store
        cache_control = self._parse_cache_control(headers.get("cache-control"))
        if "no-store" in cache_control:
            return False

        # Check for explicit expiration or validator
        has_expiration = (
            "max-age" in cache_control
            or headers.get("expires") is not None
            or "s-maxage" in cache_control
        )
        has_validator = (
            headers.get("etag") is not None or headers.get("last-modified") is not None
        )

        # Cache if there's explicit expiration, validator, or it's a cacheable status without no-cache
        # Per RFC 7234, 200 responses are cacheable by default
        if has_expiration or has_validator:
            return True

        # Default: cache common GET/HEAD responses even without explicit headers
        # (heuristic freshness will be used)
        return response.status_code in (
            200,
            203,
            204,
            206,
            300,
            301,
            404,
            405,
            410,
            414,
        )

    def _get_ttl(self, response: Response, default_ttl: int = 3600) -> int:
        """Calculate TTL from response headers."""
        headers = response.headers
        cache_control = self._parse_cache_control(headers.get("cache-control"))

        # Check max-age
        max_age = cache_control.get("max-age")
        if max_age is not None:
            try:
                return int(max_age)
            except ValueError:
                pass

        # Check s-maxage (for shared caches)
        s_maxage = cache_control.get("s-maxage")
        if s_maxage is not None:
            try:
                return int(s_maxage)
            except ValueError:
                pass

        # Check Expires header
        if headers.get("expires"):
            try:
                # Parse HTTP-date format
                from email.utils import parsedate_to_datetime

                expires = parsedate_to_datetime(headers["expires"])
                now = time.time()
                ttl = int(expires.timestamp() - now)
                return max(0, ttl)
            except (ValueError, OverflowError):
                pass

        # Heuristic: if has validator but no expiration, cache for short period
        if headers.get("etag") or headers.get("last-modified"):
            # Default heuristic freshness lifetime
            return default_ttl // 10  # 10% of default TTL

        return default_ttl

    def get_cached_response(
        self, method: str, url: str, headers: dict[str, str] | None
    ) -> Response | None:
        """Retrieve a cached response if available and fresh."""
        cache_key = self._make_cache_key(method, url, headers)
        entry = self._backend.get(cache_key)

        if not entry:
            return None

        # Reconstruct response from cache
        from gakido.models import Response

        return Response(
            status_code=entry["status_code"],
            reason=entry["reason"],
            http_version=entry["http_version"],
            headers=entry["headers"],
            body=entry["body"].encode()
            if isinstance(entry["body"], str)
            else entry["body"],
        )

    def cache_response(
        self,
        method: str,
        url: str,
        request_headers: dict[str, str] | None,
        response: Response,
        default_ttl: int = 3600,
    ) -> None:
        """Store a response in the cache if cacheable."""
        if not self._is_cacheable(method, response):
            return

        cache_key = self._make_cache_key(method, url, request_headers)
        ttl = self._get_ttl(response, default_ttl)

        # Don't cache if TTL is 0
        if ttl <= 0:
            return

        entry = {
            "status_code": response.status_code,
            "reason": response.reason,
            "http_version": response.http_version,
            "headers": response.raw_headers,
            "body": response.content.decode("utf-8", errors="replace"),
            "url": url,
            "method": method,
        }

        self._backend.set(cache_key, entry, ttl)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._backend.clear()
