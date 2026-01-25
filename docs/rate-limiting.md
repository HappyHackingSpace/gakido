# Rate Limiting

gakido provides built-in rate limiting to control request throughput and avoid overwhelming servers or hitting API rate limits.

## Features

- **Token bucket algorithm** for smooth rate limiting with burst support
- **Sliding window limiter** for strict request count limits
- **Per-host rate limiting** to apply separate limits per domain
- **Blocking and non-blocking modes** - wait for capacity or raise exception
- **Works with both sync and async clients**
- **Zero overhead** when disabled (default)

## Basic Usage

### Sync Client

```python
from gakido import Client

client = Client(
    rate_limit=10.0,           # 10 requests per second globally
    rate_limit_capacity=20.0,  # Allow burst of 20 requests
    rate_limit_blocking=True,  # Wait when rate limited (default)
)

# Requests will be automatically rate limited
for i in range(100):
    response = client.get("http://api.example.com/data")
    print(f"Request {i}: {response.status_code}")
```

### Async Client

```python
import asyncio
from gakido import AsyncClient

async def main():
    client = AsyncClient(
        rate_limit=5.0,            # 5 requests per second
        rate_limit_capacity=10.0,  # Allow burst of 10 requests
    )

    async with client:
        tasks = [client.get("http://api.example.com/data") for _ in range(50)]
        responses = await asyncio.gather(*tasks)
        print(f"Completed {len(responses)} requests")

asyncio.run(main())
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rate_limit` | `float \| None` | `None` | Global rate limit (requests per second), None to disable |
| `rate_limit_capacity` | `float \| None` | `None` | Burst capacity (defaults to rate_limit) |
| `rate_limit_per_host` | `float \| None` | `None` | Per-host rate limit (requests per second) |
| `rate_limit_blocking` | `bool` | `True` | If True, wait when rate limited; if False, raise RateLimitExceeded |

## Per-Host Rate Limiting

Apply separate rate limits to each domain:

```python
from gakido import Client

client = Client(
    rate_limit_per_host=2.0,  # 2 requests per second per host
)

# Each host has its own rate limit
client.get("http://api1.example.com/data")  # Rate limited separately
client.get("http://api2.example.com/data")  # Rate limited separately
client.get("http://api1.example.com/other") # Shares limit with first request
```

## Non-Blocking Mode

Raise an exception instead of waiting when rate limited:

```python
from gakido import Client, RateLimitExceeded

client = Client(
    rate_limit=1.0,
    rate_limit_capacity=1.0,
    rate_limit_blocking=False,  # Don't wait, raise exception
)

try:
    client.get("http://example.com")  # First request OK
    client.get("http://example.com")  # Raises RateLimitExceeded
except RateLimitExceeded as e:
    print(f"Rate limited! Retry after {e.retry_after:.2f}s")
```

## Using Rate Limiters Directly

### Token Bucket

The token bucket algorithm allows bursts up to capacity, then limits to the specified rate:

```python
from gakido import TokenBucket, AsyncTokenBucket

# Sync
limiter = TokenBucket(rate=10.0, capacity=20.0)
limiter.acquire()  # Get a token (blocks if none available)

# With context manager
with limiter:
    # Make your request here
    pass

# Async
async_limiter = AsyncTokenBucket(rate=10.0, capacity=20.0)
await async_limiter.acquire()

async with async_limiter:
    # Make your async request here
    pass
```

### Sliding Window Limiter

Strictly limit requests within a time window:

```python
from gakido import SlidingWindowLimiter, AsyncSlidingWindowLimiter

# Allow max 100 requests per minute
limiter = SlidingWindowLimiter(max_requests=100, window_seconds=60.0)
limiter.acquire()

# Async version
async_limiter = AsyncSlidingWindowLimiter(max_requests=100, window_seconds=60.0)
await async_limiter.acquire()
```

### Per-Host Rate Limiter

```python
from gakido import PerHostRateLimiter, AsyncPerHostRateLimiter

# Sync
limiter = PerHostRateLimiter(rate=5.0, capacity=10.0)
limiter.acquire("api.example.com")
limiter.acquire("other.example.com")  # Separate limit

# Async
async_limiter = AsyncPerHostRateLimiter(rate=5.0, capacity=10.0)
await async_limiter.acquire("api.example.com")
```

## Decorators

Apply rate limiting to any function:

```python
from gakido import rate_limited, arate_limited

# Sync decorator
@rate_limited(rate=5.0, capacity=10.0)
def make_api_call():
    # Your code here
    pass

# Async decorator
@arate_limited(rate=5.0, capacity=10.0)
async def async_api_call():
    # Your async code here
    pass

# Non-blocking decorator
@rate_limited(rate=1.0, blocking=False)
def strict_api_call():
    # Raises RateLimitExceeded if rate exceeded
    pass
```

## Combining with Retry

Rate limiting works seamlessly with retry logic:

```python
from gakido import Client

client = Client(
    # Rate limiting
    rate_limit=10.0,
    rate_limit_capacity=20.0,
    # Retry on failures
    max_retries=3,
    retry_base_delay=1.0,
)

# Requests are rate limited, and failures are retried
response = client.get("http://api.example.com/data")
```

## Examples

### API with Strict Rate Limits

```python
from gakido import AsyncClient

# Twitter-like API: 300 requests per 15 minutes per endpoint
client = AsyncClient(
    rate_limit=0.33,           # ~20 requests per minute
    rate_limit_capacity=50.0,  # Allow some bursting
)
```

### Web Scraping with Politeness

```python
from gakido import Client

# Be polite to servers
client = Client(
    rate_limit_per_host=1.0,  # 1 request per second per host
    rate_limit_capacity=1.0,  # No bursting
)
```

### High-Throughput with Burst

```python
from gakido import AsyncClient

# High throughput API with burst allowance
client = AsyncClient(
    rate_limit=100.0,          # 100 requests per second sustained
    rate_limit_capacity=500.0, # Allow bursts of 500
)
```

## Best Practices

1. **Match API limits** - Set rate limits to match your API provider's limits
2. **Use per-host limiting** for web scraping to be polite to each server
3. **Allow reasonable bursts** - Set capacity higher than rate for better UX
4. **Use non-blocking mode** when you need to handle rate limits explicitly
5. **Combine with retry** - Use retry for transient failures, rate limiting for throughput control
6. **Monitor rate limit exceptions** - Track `RateLimitExceeded` to tune your limits
