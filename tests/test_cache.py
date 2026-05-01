"""Tests for HTTP response caching functionality."""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from gakido.cache import CacheBackend, CacheController, FileCache, MemoryCache
from gakido.models import Response


class TestMemoryCache:
    """Tests for the MemoryCache backend."""

    def test_basic_set_get(self):
        """Test basic set and get operations."""
        cache = MemoryCache()
        entry = {"status_code": 200, "body": "test"}

        cache.set("key1", entry)
        result = cache.get("key1")

        assert result == entry

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = MemoryCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_ttl_expiration(self):
        """Test that entries expire after TTL."""
        cache = MemoryCache(default_ttl=0.1)  # 100ms TTL
        entry = {"status_code": 200, "body": "test"}

        cache.set("key1", entry, ttl=0.1)
        assert cache.get("key1") == entry

        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_delete(self):
        """Test deleting a cached entry."""
        cache = MemoryCache()
        entry = {"status_code": 200, "body": "test"}

        cache.set("key1", entry)
        assert cache.get("key1") == entry

        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """Test clearing all cached entries."""
        cache = MemoryCache()
        cache.set("key1", {"data": 1})
        cache.set("key2", {"data": 2})

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_custom_ttl_per_entry(self):
        """Test setting different TTL for specific entries."""
        cache = MemoryCache(default_ttl=3600)

        cache.set("long", {"data": "long"}, ttl=3600)
        cache.set("short", {"data": "short"}, ttl=0.1)

        time.sleep(0.15)

        assert cache.get("long") == {"data": "long"}
        assert cache.get("short") is None


class TestFileCache:
    """Tests for the FileCache backend."""

    def test_basic_set_get(self, tmp_path):
        """Test basic set and get operations."""
        cache = FileCache(tmp_path)
        entry = {"status_code": 200, "body": "test"}

        cache.set("key1", entry)
        result = cache.get("key1")

        assert result == entry

    def test_get_nonexistent_key(self, tmp_path):
        """Test getting a key that doesn't exist."""
        cache = FileCache(tmp_path)
        result = cache.get("nonexistent")
        assert result is None

    def test_ttl_expiration(self, tmp_path):
        """Test that entries expire after TTL."""
        cache = FileCache(tmp_path, default_ttl=0.1)
        entry = {"status_code": 200, "body": "test"}

        cache.set("key1", entry, ttl=0.1)
        assert cache.get("key1") == entry

        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_persistence(self, tmp_path):
        """Test that cache persists across instances."""
        entry = {"status_code": 200, "body": "test"}

        cache1 = FileCache(tmp_path)
        cache1.set("key1", entry)

        cache2 = FileCache(tmp_path)
        result = cache2.get("key1")

        assert result == entry

    def test_delete(self, tmp_path):
        """Test deleting a cached entry."""
        cache = FileCache(tmp_path)
        entry = {"status_code": 200, "body": "test"}

        cache.set("key1", entry)
        assert cache.get("key1") == entry

        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self, tmp_path):
        """Test clearing all cached entries."""
        cache = FileCache(tmp_path)
        cache.set("key1", {"data": 1})
        cache.set("key2", {"data": 2})

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_expands_user_directory(self, tmp_path, monkeypatch):
        """Test that ~ is expanded to user home."""
        monkeypatch.setenv("HOME", str(tmp_path))
        cache = FileCache("~/.cache/gakido")

        assert cache._cache_dir == Path(tmp_path) / ".cache" / "gakido"
        assert cache._cache_dir.exists()


class TestCacheController:
    """Tests for the CacheController."""

    def test_make_cache_key_consistency(self):
        """Test that cache keys are generated consistently."""
        controller = CacheController(MemoryCache())

        key1 = controller._make_cache_key("GET", "https://example.com", {"Accept": "json"})
        key2 = controller._make_cache_key("GET", "https://example.com", {"Accept": "json"})

        assert key1 == key2

    def test_make_cache_key_different_methods(self):
        """Test that different methods produce different keys."""
        controller = CacheController(MemoryCache())

        key1 = controller._make_cache_key("GET", "https://example.com", None)
        key2 = controller._make_cache_key("POST", "https://example.com", None)

        assert key1 != key2

    def test_make_cache_key_different_urls(self):
        """Test that different URLs produce different keys."""
        controller = CacheController(MemoryCache())

        key1 = controller._make_cache_key("GET", "https://example.com/a", None)
        key2 = controller._make_cache_key("GET", "https://example.com/b", None)

        assert key1 != key2

    def test_parse_cache_control_simple(self):
        """Test parsing simple Cache-Control header."""
        controller = CacheController(MemoryCache())

        result = controller._parse_cache_control("max-age=3600")
        assert result == {"max-age": "3600"}

    def test_parse_cache_control_multiple(self):
        """Test parsing multiple Cache-Control directives."""
        controller = CacheController(MemoryCache())

        result = controller._parse_cache_control("max-age=3600, no-cache, must-revalidate")
        assert result == {"max-age": "3600", "no-cache": None, "must-revalidate": None}

    def test_parse_cache_control_empty(self):
        """Test parsing empty Cache-Control header."""
        controller = CacheController(MemoryCache())

        result = controller._parse_cache_control(None)
        assert result == {}

    def test_is_cacheable_get_request(self):
        """Test that GET requests with 200 status are cacheable."""
        controller = CacheController(MemoryCache())
        response = Mock(spec=Response)
        response.status_code = 200
        response.headers = {}

        assert controller._is_cacheable("GET", response) is True

    def test_is_cacheable_post_request(self):
        """Test that POST requests are not cacheable."""
        controller = CacheController(MemoryCache())
        response = Mock(spec=Response)
        response.status_code = 200
        response.headers = {}

        assert controller._is_cacheable("POST", response) is False

    def test_is_cacheable_no_store(self):
        """Test that no-store prevents caching."""
        controller = CacheController(MemoryCache())
        response = Mock(spec=Response)
        response.status_code = 200
        response.headers = {"cache-control": "no-store"}

        assert controller._is_cacheable("GET", response) is False

    def test_is_cacheable_404_status(self):
        """Test that 404 responses are cacheable."""
        controller = CacheController(MemoryCache())
        response = Mock(spec=Response)
        response.status_code = 404
        response.headers = {}

        assert controller._is_cacheable("GET", response) is True

    def test_get_ttl_from_max_age(self):
        """Test extracting TTL from max-age directive."""
        controller = CacheController(MemoryCache())
        response = Mock(spec=Response)
        response.headers = {"cache-control": "max-age=3600"}

        ttl = controller._get_ttl(response, default_ttl=7200)
        assert ttl == 3600

    def test_get_ttl_fallback(self):
        """Test fallback to default TTL."""
        controller = CacheController(MemoryCache())
        response = Mock(spec=Response)
        response.headers = {}

        ttl = controller._get_ttl(response, default_ttl=3600)
        assert ttl == 3600

    def test_cache_response_success(self):
        """Test caching a successful response."""
        backend = MemoryCache()
        controller = CacheController(backend)

        response = Mock(spec=Response)
        response.status_code = 200
        response.reason = "OK"
        response.http_version = "HTTP/1.1"
        response.raw_headers = [("Content-Type", "text/plain")]
        response.content = b"test body"
        response.headers = {}

        controller.cache_response("GET", "https://example.com", None, response, default_ttl=3600)

        # Verify it was cached
        cached = controller.get_cached_response("GET", "https://example.com", None)
        assert cached is not None
        assert cached.status_code == 200

    def test_cache_response_not_cacheable(self):
        """Test that non-cacheable responses are not stored."""
        backend = MemoryCache()
        controller = CacheController(backend)

        response = Mock(spec=Response)
        response.status_code = 200
        response.headers = {"cache-control": "no-store"}

        controller.cache_response("POST", "https://example.com", None, response)

        cached = controller.get_cached_response("POST", "https://example.com", None)
        assert cached is None

    def test_get_cached_response_hit(self):
        """Test retrieving a cached response (cache hit)."""
        backend = MemoryCache()
        controller = CacheController(backend)

        response = Mock(spec=Response)
        response.status_code = 200
        response.reason = "OK"
        response.http_version = "HTTP/1.1"
        response.raw_headers = [("Content-Type", "application/json")]
        response.content = json.dumps({"key": "value"}).encode()
        response.headers = {}

        controller.cache_response("GET", "https://example.com", None, response, default_ttl=3600)

        cached = controller.get_cached_response("GET", "https://example.com", None)
        assert cached is not None
        assert cached.status_code == 200
        assert cached.reason == "OK"

    def test_get_cached_response_miss(self):
        """Test retrieving a non-cached response (cache miss)."""
        controller = CacheController(MemoryCache())

        cached = controller.get_cached_response("GET", "https://example.com", None)
        assert cached is None

    def test_get_cached_response_expired(self):
        """Test that expired cached responses return None."""
        backend = MemoryCache()
        controller = CacheController(backend)

        response = Mock(spec=Response)
        response.status_code = 200
        response.reason = "OK"
        response.http_version = "HTTP/1.1"
        response.raw_headers = []
        response.content = b"test"
        response.headers = {}

        # Cache with very short TTL
        controller.cache_response("GET", "https://example.com", None, response, default_ttl=0.1)

        # Should be retrievable immediately
        assert controller.get_cached_response("GET", "https://example.com", None) is not None

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired now
        assert controller.get_cached_response("GET", "https://example.com", None) is None


class TestCacheBackendInterface:
    """Tests for the CacheBackend abstract interface."""

    def test_custom_backend_implementation(self):
        """Test implementing a custom cache backend."""

        class CustomCache(CacheBackend):
            def __init__(self):
                self._data = {}

            def get(self, key: str) -> dict | None:
                return self._data.get(key)

            def set(self, key: str, entry: dict, ttl: int | None = None) -> None:
                self._data[key] = entry

            def delete(self, key: str) -> None:
                self._data.pop(key, None)

            def clear(self) -> None:
                self._data.clear()

        cache = CustomCache()
        controller = CacheController(cache)

        response = Mock(spec=Response)
        response.status_code = 200
        response.reason = "OK"
        response.http_version = "HTTP/1.1"
        response.raw_headers = []
        response.content = b"test"
        response.headers = {}

        controller.cache_response("GET", "https://example.com", None, response, default_ttl=3600)

        cached = controller.get_cached_response("GET", "https://example.com", None)
        assert cached is not None
        assert cached.status_code == 200
