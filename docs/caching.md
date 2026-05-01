# HTTP Response Caching

Gakido includes built-in HTTP response caching to reduce redundant requests and improve performance. The cache supports standard HTTP caching mechanisms including `Cache-Control`, `ETag`, and `Last-Modified` headers.

## Quick Start

Enable caching with a single parameter:

```python
from gakido import Client
import time

# Enable file-based caching with default settings
with Client(cache=True) as client:
    url = "https://api.example.com/data"

    # First request - hits the server
    start = time.time()
    response1 = client.get(url)
    print(f"First request: {time.time() - start:.2f}s")

    # Second request - served from cache (much faster!)
    start = time.time()
    response2 = client.get(url)
    print(f"Second request: {time.time() - start:.3f}s")  # ~100x faster
```

## Cache Backends

### File-Based Cache (Default)

The default cache stores responses on disk, persisting across program restarts:

```python
from gakido import Client

# Default cache directory: ~/.cache/gakido
with Client(cache=True) as client:
    response = client.get("https://api.example.com/data")

# Custom cache directory
with Client(cache=True, cache_dir="/path/to/cache") as client:
    response = client.get("https://api.example.com/data")
```

### Memory Cache

For in-memory caching that clears when the program exits:

```python
from gakido import Client, MemoryCache

# Create a memory cache with 5 minute TTL
cache = MemoryCache(default_ttl=300)

with Client(cache=cache) as client:
    response = client.get("https://api.example.com/data")
```

### Custom Cache Backend

Implement your own cache backend by subclassing `CacheBackend`:

```python
from gakido import CacheBackend, Client

class RedisCache(CacheBackend):
    def __init__(self, redis_client):
        self._redis = redis_client

    def get(self, key: str) -> dict | None:
        data = self._redis.get(key)
        return json.loads(data) if data else None

    def set(self, key: str, entry: dict, ttl: int | None = None) -> None:
        self._redis.setex(key, ttl or 3600, json.dumps(entry))

    def delete(self, key: str) -> None:
        self._redis.delete(key)

    def clear(self) -> None:
        # Clear all gakido cache keys
        pass

# Use custom cache
with Client(cache=RedisCache(redis_client)) as client:
    response = client.get("https://api.example.com/data")
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cache` | `bool` or `CacheBackend` | `False` | Enable caching or provide custom backend |
| `cache_dir` | `str` | `~/.cache/gakido` | Directory for file-based cache |
| `cache_ttl` | `int` | `3600` | Default cache TTL in seconds (1 hour) |

## Cache TTL Behavior

The actual cache duration is determined by HTTP response headers in this priority:

1. **Cache-Control: max-age** - Uses the specified value in seconds
2. **Expires** - Calculates TTL from the HTTP date
3. **ETag / Last-Modified** - Uses 10% of default TTL for heuristic caching
4. **Default TTL** - Falls back to the configured `cache_ttl`

### Example: Respecting Server Cache Directives

```python
from gakido import Client

with Client(cache=True) as client:
    # If server returns: Cache-Control: max-age=300
    # This response will be cached for 5 minutes
    response = client.get("https://api.example.com/data")
```

## What Gets Cached

Only **GET** and **HEAD** requests without a request body are cached:

```python
from gakido import Client

with Client(cache=True) as client:
    # ✅ Cached
    response = client.get("https://api.example.com/data")

    # ✅ Cached
    response = client.request("HEAD", "https://api.example.com/data")

    # ❌ Not cached (has request body)
    response = client.post("https://api.example.com/data", json={"key": "value"})
```

## Managing the Cache

### Clear Cache

```python
from gakido import Client

with Client(cache=True) as client:
    # Make some requests
    response = client.get("https://api.example.com/data")

    # Clear all cached responses
    client.clear_cache()
```

### Manual Cache Invalidation

Using custom cache backend for fine-grained control:

```python
from gakido import Client, FileCache

cache = FileCache("~/.cache/gakido")

with Client(cache=cache) as client:
    response = client.get("https://api.example.com/data")

# Delete specific cached entry
cache.delete(cache_key)

# Clear all entries
cache.clear()
```

## Async Client Caching

The async client supports the same caching options:

```python
import asyncio
from gakido.aio import AsyncClient

async def main():
    async with AsyncClient(cache=True, cache_ttl=1800) as client:
        # First request hits the server
        response1 = await client.get("https://api.example.com/data")

        # Second request served from cache
        response2 = await client.get("https://api.example.com/data")

        # Clear cache
        client.clear_cache()

asyncio.run(main())
```

## Cache Key Generation

Cache keys are generated from:
- HTTP method (GET, HEAD)
- Full request URL
- Request headers (excluding hop-by-hop headers)

This ensures responses are correctly cached per unique request.

## Security Considerations

- File cache uses `0o600` permissions (user-only readable/writable)
- Cache directory uses `0o700` permissions
- Sensitive data in responses is stored in the cache - use appropriate cache locations

## Disabling Cache for Specific Requests

To bypass cache for a specific request, temporarily disable the client's cache:

```python
from gakido import Client

with Client(cache=True) as client:
    # Temporarily disable cache
    original_cache = client._cache
    client._cache = None

    # This request won't use cache
    response = client.get("https://api.example.com/data")

    # Restore cache
    client._cache = original_cache
```

## HTTP Cache Headers Reference

| Header | Effect on Caching |
|--------|-------------------|
| `Cache-Control: max-age=N` | Cache for N seconds |
| `Cache-Control: no-store` | Never cache |
| `Cache-Control: no-cache` | Revalidate before using cache |
| `Cache-Control: must-revalidate` | Strict freshness checking |
| `Expires: <http-date>` | Cache until the specified date |
| `ETag: <tag>` | Cache with validation support |
| `Last-Modified: <date>` | Cache with validation support |

## Complete Example: API Client with Caching

Here's a complete example showing how to build an efficient API client with caching:

```python
from gakido import Client, MemoryCache
import json

class CachedAPIClient:
    """Example API client with intelligent caching."""

    def __init__(self, base_url: str, cache_ttl: int = 300):
        # Use memory cache for API responses
        self.cache = MemoryCache(default_ttl=cache_ttl)
        self.client = Client(
            cache=self.cache,
            impersonate="chrome_120",
            max_retries=2
        )
        self.base_url = base_url

    def get_user(self, user_id: int) -> dict:
        """Get user data (cached for 5 minutes by default)."""
        url = f"{self.base_url}/users/{user_id}"
        response = self.client.get(url)
        return response.json()

    def get_users(self) -> list:
        """Get all users (cached)."""
        url = f"{self.base_url}/users"
        response = self.client.get(url)
        return response.json()

    def refresh_user(self, user_id: int) -> dict:
        """Force refresh user data (bypasses cache)."""
        # Clear cache for this specific user
        # Note: In production, you'd want more granular cache invalidation
        self.client.clear_cache()

        url = f"{self.base_url}/users/{user_id}"
        response = self.client.get(url)
        return response.json()

    def close(self):
        self.client.close()

# Usage
api = CachedAPIClient("https://jsonplaceholder.typicode.com")

# First call hits the server
user1 = api.get_user(1)

# Second call is instant (from cache)
user2 = api.get_user(1)

# Force refresh
fresh_user = api.refresh_user(1)

api.close()
```

## Advanced: Conditional Requests with ETag

Gakido's cache controller supports HTTP validators (`ETag`, `Last-Modified`). Here's how to extend it for conditional requests:

```python
from gakido import Client
from gakido.cache import CacheController, FileCache

class ConditionalCacheController(CacheController):
    """Extended cache controller with conditional request support."""

    def get_validator_headers(self, method: str, url: str, headers: dict | None) -> dict | None:
        """Get validator headers (If-None-Match, If-Modified-Since) for conditional request."""
        cache_key = self._make_cache_key(method, url, headers)
        entry = self._backend.get(cache_key)

        if not entry:
            return None

        validators = {}
        entry_headers = entry.get("headers", [])

        # Extract ETag
        for name, value in entry_headers:
            if name.lower() == "etag":
                validators["If-None-Match"] = value
            elif name.lower() == "last-modified":
                validators["If-Modified-Since"] = value

        return validators if validators else None

# Usage
controller = ConditionalCacheController(FileCache("~/.cache/gakido"))

# Create a client that uses our custom controller
# (This requires extending Client class for full integration)
```

## Troubleshooting

### Cache Not Working

If caching doesn't seem to work:

1. **Check request method**: Only GET and HEAD are cached
2. **Check status code**: Only 200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501 are cached
3. **Check Cache-Control**: `no-store` directive prevents caching
4. **Check for request body**: Requests with body are never cached

### Debug Cache Operations

```python
from gakido import Client, MemoryCache

class DebugCache(MemoryCache):
    """Memory cache that prints all operations."""

    def get(self, key: str) -> dict | None:
        result = super().get(key)
        status = "HIT" if result else "MISS"
        print(f"[CACHE {status}] {key[:20]}...")
        return result

    def set(self, key: str, entry: dict, ttl: int | None = None) -> None:
        print(f"[CACHE STORE] {key[:20]}...")
        super().set(key, entry, ttl)

with Client(cache=DebugCache()) as client:
    response = client.get("https://api.example.com/data")
```

## Performance Tips

1. **Use memory cache for short-lived scripts** - Faster than disk I/O
2. **Use file cache for long-running applications** - Persists across restarts
3. **Set appropriate TTL** - Balance freshness with performance
4. **Clear cache strategically** - After deployments or data updates
5. **Monitor cache hit rates** - Use custom backends to track hits/misses
6. **Cache directory permissions** - Ensure `~/.cache/gakido` is writable
