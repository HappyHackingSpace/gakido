#!/usr/bin/env python3
"""
Rate Limiting Examples

Demonstrates various rate limiting features in gakido.
"""

import asyncio
import time

from gakido import (
    Client,
    AsyncClient,
    RateLimitExceeded,
    TokenBucket,
    AsyncTokenBucket,
    SlidingWindowLimiter,
    PerHostRateLimiter,
    rate_limited,
    arate_limited,
)


def example_basic_rate_limiting():
    """Basic rate limiting with sync client."""
    print("\n=== Basic Rate Limiting ===")

    client = Client(
        rate_limit=5.0,  # 5 requests per second
        rate_limit_capacity=5.0,  # No burst beyond rate
    )

    start = time.time()
    for i in range(10):
        # In a real scenario, this would make actual requests
        # For demo, we just show the timing
        print(f"Request {i + 1} at t={time.time() - start:.2f}s")
        # Simulate the rate limiter being checked
        if client._rate_limiter:
            client._rate_limiter.acquire()

    print(f"Total time: {time.time() - start:.2f}s (expected ~2s for 10 requests at 5/s)")


def example_burst_capacity():
    """Demonstrate burst capacity."""
    print("\n=== Burst Capacity ===")

    # Allow burst of 10, then rate limit to 2/s
    bucket = TokenBucket(rate=2.0, capacity=10.0)

    start = time.time()
    for i in range(15):
        bucket.acquire()
        print(f"Request {i + 1} at t={time.time() - start:.2f}s")

    print(f"First 10 were instant (burst), then rate limited to 2/s")


def example_non_blocking():
    """Non-blocking rate limiting that raises exceptions."""
    print("\n=== Non-Blocking Mode ===")

    bucket = TokenBucket(rate=1.0, capacity=2.0, blocking=False)

    for i in range(5):
        try:
            bucket.acquire()
            print(f"Request {i + 1}: Success")
        except RateLimitExceeded as e:
            print(f"Request {i + 1}: Rate limited! Retry after {e.retry_after:.2f}s")


def example_sliding_window():
    """Sliding window rate limiter."""
    print("\n=== Sliding Window Limiter ===")

    # Max 3 requests per 1 second window
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=1.0)

    start = time.time()
    for i in range(6):
        limiter.acquire()
        print(f"Request {i + 1} at t={time.time() - start:.2f}s")

    print("First 3 instant, then waits for window to slide")


def example_per_host():
    """Per-host rate limiting."""
    print("\n=== Per-Host Rate Limiting ===")

    limiter = PerHostRateLimiter(rate=2.0, capacity=2.0, blocking=False)

    hosts = ["api.example.com", "api.other.com", "api.example.com", "api.other.com"]

    for host in hosts:
        try:
            limiter.acquire(host)
            print(f"Request to {host}: Success")
        except RateLimitExceeded:
            print(f"Request to {host}: Rate limited!")


def example_decorator():
    """Using the rate_limited decorator."""
    print("\n=== Rate Limited Decorator ===")

    @rate_limited(rate=3.0, capacity=3.0)
    def api_call(n: int) -> str:
        return f"Response {n}"

    start = time.time()
    for i in range(6):
        result = api_call(i + 1)
        print(f"{result} at t={time.time() - start:.2f}s")


async def example_async_rate_limiting():
    """Async rate limiting."""
    print("\n=== Async Rate Limiting ===")

    bucket = AsyncTokenBucket(rate=5.0, capacity=5.0)

    start = time.time()

    async def make_request(n: int):
        await bucket.acquire()
        print(f"Async request {n} at t={time.time() - start:.2f}s")

    # Run 10 concurrent requests - they'll be rate limited
    await asyncio.gather(*[make_request(i + 1) for i in range(10)])


async def example_async_client():
    """Async client with rate limiting."""
    print("\n=== Async Client Rate Limiting ===")

    client = AsyncClient(
        rate_limit=10.0,
        rate_limit_capacity=10.0,
        rate_limit_per_host=5.0,  # Per-host limit
    )

    print(f"Client configured with:")
    print(f"  - Global rate limit: 10 req/s")
    print(f"  - Per-host rate limit: 5 req/s")
    print(f"  - Rate limiter: {client._rate_limiter}")
    print(f"  - Per-host limiter: {client._per_host_limiter}")

    await client.close()


async def example_async_decorator():
    """Using the arate_limited decorator."""
    print("\n=== Async Rate Limited Decorator ===")

    @arate_limited(rate=3.0, capacity=3.0)
    async def async_api_call(n: int) -> str:
        return f"Async Response {n}"

    start = time.time()
    for i in range(6):
        result = await async_api_call(i + 1)
        print(f"{result} at t={time.time() - start:.2f}s")


def example_combined_retry_and_rate_limit():
    """Combining rate limiting with retry logic."""
    print("\n=== Combined Retry and Rate Limiting ===")

    client = Client(
        rate_limit=5.0,
        rate_limit_capacity=10.0,
        max_retries=3,
        retry_base_delay=0.5,
    )

    print("Client configured with both rate limiting and retry:")
    print(f"  - Rate limit: 5 req/s with burst of 10")
    print(f"  - Retries: 3 attempts with 0.5s base delay")
    print("Requests will be rate limited, and failures will be retried")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Gakido Rate Limiting Examples")
    print("=" * 60)

    # Sync examples
    example_basic_rate_limiting()
    example_burst_capacity()
    example_non_blocking()
    example_sliding_window()
    example_per_host()
    example_decorator()
    example_combined_retry_and_rate_limit()

    # Async examples
    asyncio.run(example_async_rate_limiting())
    asyncio.run(example_async_client())
    asyncio.run(example_async_decorator())

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
