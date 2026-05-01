"""
HTTP Response Caching Example
============================

This example demonstrates how to use Gakido's HTTP response caching
to reduce redundant requests and improve performance.

Features shown:
- Basic file-based caching
- Memory caching
- Cache inspection and clearing
- TTL configuration
- Cache hit/miss observation
"""

import time
from gakido import Client, MemoryCache


def basic_caching_example():
    """Demonstrate basic file-based caching."""
    print("=" * 60)
    print("Example 1: Basic File-Based Caching")
    print("=" * 60)

    # Create client with caching enabled
    with Client(cache=True) as client:
        url = "https://httpbin.org/get"

        # First request - hits the server
        print("\n1. First request (cache miss):")
        start = time.time()
        response1 = client.get(url)
        duration1 = time.time() - start
        print(f"   Status: {response1.status_code}")
        print(f"   Time: {duration1:.2f}s")

        # Second request - served from cache
        print("\n2. Second request (cache hit):")
        start = time.time()
        response2 = client.get(url)
        duration2 = time.time() - start
        print(f"   Status: {response2.status_code}")
        print(f"   Time: {duration2:.3f}s")
        print(f"   Speedup: {duration1/duration2:.1f}x faster")

        # Verify responses are the same
        print(f"\n   Responses identical: {response1.text == response2.text}")


def memory_cache_example():
    """Demonstrate in-memory caching."""
    print("\n" + "=" * 60)
    print("Example 2: Memory Cache (Faster, Non-Persistent)")
    print("=" * 60)

    # Create memory cache with 5 minute TTL
    memory_cache = MemoryCache(default_ttl=300)

    with Client(cache=memory_cache) as client:
        url = "https://httpbin.org/uuid"

        print("\n1. First request:")
        response1 = client.get(url)
        print(f"   UUID: {response1.json()['uuid']}")

        print("\n2. Second request (from memory):")
        response2 = client.get(url)
        print(f"   UUID: {response2.json()['uuid']}")
        print(f"   Same UUID: {response1.json()['uuid'] == response2.json()['uuid']}")


def custom_ttl_example():
    """Demonstrate custom cache TTL configuration."""
    print("\n" + "=" * 60)
    print("Example 3: Custom Cache TTL")
    print("=" * 60)

    # Very short TTL (2 seconds)
    with Client(cache=True, cache_ttl=2) as client:
        url = "https://httpbin.org/uuid"

        print("\n1. First request:")
        response1 = client.get(url)
        uuid1 = response1.json()["uuid"]
        print(f"   UUID: {uuid1}")

        print("\n2. Immediate second request (from cache):")
        response2 = client.get(url)
        uuid2 = response2.json()["uuid"]
        print(f"   UUID: {uuid2}")
        print(f"   Same: {uuid1 == uuid2}")

        print("\n3. Waiting for cache to expire...")
        time.sleep(3)

        print("4. Third request after expiration (fresh request):")
        response3 = client.get(url)
        uuid3 = response3.json()["uuid"]
        print(f"   UUID: {uuid3}")
        print(f"   Different from first: {uuid1 != uuid3}")


def cache_management_example():
    """Demonstrate cache clearing and management."""
    print("\n" + "=" * 60)
    print("Example 4: Cache Management")
    print("=" * 60)

    with Client(cache=True) as client:
        url = "https://httpbin.org/uuid"

        # Make a request
        print("\n1. Making request:")
        response1 = client.get(url)
        uuid1 = response1.json()["uuid"]
        print(f"   UUID: {uuid1}")

        # Clear the cache
        print("\n2. Clearing cache...")
        client.clear_cache()

        # Make another request
        print("\n3. Making request after clearing cache:")
        response2 = client.get(url)
        uuid2 = response2.json()["uuid"]
        print(f"   UUID: {uuid2}")
        print(f"   Different UUID: {uuid1 != uuid2}")


def different_methods_example():
    """Demonstrate which methods are cached."""
    print("\n" + "=" * 60)
    print("Example 5: Cacheable vs Non-Cacheable Methods")
    print("=" * 60)

    with Client(cache=True) as client:
        # GET is cached
        print("\n1. GET request (cached):")
        response1 = client.get("https://httpbin.org/get")
        response2 = client.get("https://httpbin.org/get")
        print(f"   Status: {response1.status_code}")
        print(f"   Second request served from cache: True")

        # POST is not cached (has request body)
        print("\n2. POST request (not cached - has body):")
        response3 = client.post(
            "https://httpbin.org/post",
            json={"key": "value1"}
        )
        response4 = client.post(
            "https://httpbin.org/post",
            json={"key": "value2"}
        )
        print(f"   First response: {response3.json()['json']}")
        print(f"   Second response: {response4.json()['json']}")
        print(f"   Note: POST requests are never cached")


def custom_cache_backend_example():
    """Demonstrate implementing a custom cache backend."""
    print("\n" + "=" * 60)
    print("Example 6: Custom Cache Backend")
    print("=" * 60)

    from gakido.cache import CacheBackend

    class LoggingCache(CacheBackend):
        """Custom cache that logs all operations."""

        def __init__(self):
            self._data = {}
            self.hits = 0
            self.misses = 0

        def get(self, key: str) -> dict | None:
            if key in self._data:
                entry, expires_at = self._data[key]
                if expires_at is None or time.time() < expires_at:
                    self.hits += 1
                    print(f"   [CACHE HIT] {key[:16]}...")
                    return entry
            self.misses += 1
            print(f"   [CACHE MISS] {key[:16]}...")
            return None

        def set(self, key: str, entry: dict, ttl: int | None = None) -> None:
            expires_at = time.time() + ttl if ttl else None
            self._data[key] = (entry, expires_at)
            print(f"   [CACHE STORE] {key[:16]}...")

        def delete(self, key: str) -> None:
            self._data.pop(key, None)

        def clear(self) -> None:
            self._data.clear()
            print("   [CACHE CLEARED]")

    cache = LoggingCache()

    with Client(cache=cache) as client:
        url = "https://httpbin.org/get"

        print("\n1. First request:")
        client.get(url)

        print("\n2. Second request:")
        client.get(url)

        print(f"\n   Statistics:")
        print(f"   Hits: {cache.hits}")
        print(f"   Misses: {cache.misses}")


if __name__ == "__main__":
    # Run all examples
    basic_caching_example()
    memory_cache_example()
    custom_ttl_example()
    cache_management_example()
    different_methods_example()
    custom_cache_backend_example()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
