"""Rate limiting utilities for HTTP clients.

Provides token bucket and sliding window rate limiters for both sync and async usage.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import TypeVar, Awaitable

T = TypeVar("T")
R = TypeVar("R")


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and blocking is disabled."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after is not None:
            msg += f", retry after {retry_after:.2f}s"
        super().__init__(msg)


class TokenBucket:
    """
    Token bucket rate limiter for synchronous usage.

    Tokens are added at a constant rate up to a maximum capacity.
    Each request consumes one token. If no tokens are available,
    the request either blocks until a token is available or raises
    RateLimitExceeded.

    Args:
        rate: Number of tokens added per second
        capacity: Maximum number of tokens in the bucket
        blocking: If True, wait for tokens; if False, raise RateLimitExceeded
    """

    def __init__(
        self,
        rate: float,
        capacity: float | None = None,
        blocking: bool = True,
    ) -> None:
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self.blocking = blocking
        self._tokens = self.capacity
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_update = now

    def acquire(self, tokens: float = 1.0) -> None:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Raises:
            RateLimitExceeded: If blocking is False and not enough tokens
        """
        with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return

            if not self.blocking:
                wait_time = (tokens - self._tokens) / self.rate
                raise RateLimitExceeded(retry_after=wait_time)

            # Calculate wait time and sleep
            wait_time = (tokens - self._tokens) / self.rate

        # Sleep outside the lock
        time.sleep(wait_time)

        with self._lock:
            self._refill()
            self._tokens -= tokens

    def __enter__(self) -> TokenBucket:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class AsyncTokenBucket:
    """
    Token bucket rate limiter for asynchronous usage.

    Args:
        rate: Number of tokens added per second
        capacity: Maximum number of tokens in the bucket
        blocking: If True, wait for tokens; if False, raise RateLimitExceeded
    """

    def __init__(
        self,
        rate: float,
        capacity: float | None = None,
        blocking: bool = True,
    ) -> None:
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self.blocking = blocking
        self._tokens = self.capacity
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_update = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Raises:
            RateLimitExceeded: If blocking is False and not enough tokens
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return

            if not self.blocking:
                wait_time = (tokens - self._tokens) / self.rate
                raise RateLimitExceeded(retry_after=wait_time)

            # Calculate wait time
            wait_time = (tokens - self._tokens) / self.rate

        # Sleep outside the lock
        await asyncio.sleep(wait_time)

        async with self._lock:
            self._refill()
            self._tokens -= tokens

    async def __aenter__(self) -> AsyncTokenBucket:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class SlidingWindowLimiter:
    """
    Sliding window rate limiter for synchronous usage.

    Limits requests to a maximum count within a sliding time window.

    Args:
        max_requests: Maximum number of requests allowed in the window
        window_seconds: Size of the sliding window in seconds
        blocking: If True, wait until request is allowed; if False, raise RateLimitExceeded
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        blocking: bool = True,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.blocking = blocking
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def _cleanup(self, now: float) -> None:
        """Remove timestamps outside the window."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def acquire(self) -> None:
        """
        Acquire permission to make a request.

        Raises:
            RateLimitExceeded: If blocking is False and limit is reached
        """
        while True:
            with self._lock:
                now = time.monotonic()
                self._cleanup(now)

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return

                if not self.blocking:
                    # Calculate when the oldest request will expire
                    wait_time = self._timestamps[0] + self.window_seconds - now
                    raise RateLimitExceeded(retry_after=wait_time)

                # Calculate wait time
                wait_time = self._timestamps[0] + self.window_seconds - now

            # Sleep outside the lock
            time.sleep(max(0.001, wait_time))

    def __enter__(self) -> SlidingWindowLimiter:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class AsyncSlidingWindowLimiter:
    """
    Sliding window rate limiter for asynchronous usage.

    Args:
        max_requests: Maximum number of requests allowed in the window
        window_seconds: Size of the sliding window in seconds
        blocking: If True, wait until request is allowed; if False, raise RateLimitExceeded
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        blocking: bool = True,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.blocking = blocking
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _cleanup(self, now: float) -> None:
        """Remove timestamps outside the window."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.

        Raises:
            RateLimitExceeded: If blocking is False and limit is reached
        """
        while True:
            async with self._lock:
                now = time.monotonic()
                self._cleanup(now)

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return

                if not self.blocking:
                    wait_time = self._timestamps[0] + self.window_seconds - now
                    raise RateLimitExceeded(retry_after=wait_time)

                wait_time = self._timestamps[0] + self.window_seconds - now

            await asyncio.sleep(max(0.001, wait_time))

    async def __aenter__(self) -> AsyncSlidingWindowLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class PerHostRateLimiter:
    """
    Rate limiter that applies separate limits per host.

    Args:
        rate: Requests per second per host (for token bucket)
        capacity: Burst capacity per host (for token bucket)
        blocking: If True, wait for tokens; if False, raise RateLimitExceeded
    """

    def __init__(
        self,
        rate: float,
        capacity: float | None = None,
        blocking: bool = True,
    ) -> None:
        self.rate = rate
        self.capacity = capacity
        self.blocking = blocking
        self._limiters: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _get_limiter(self, host: str) -> TokenBucket:
        """Get or create a limiter for the given host."""
        with self._lock:
            if host not in self._limiters:
                self._limiters[host] = TokenBucket(
                    rate=self.rate,
                    capacity=self.capacity,
                    blocking=self.blocking,
                )
            return self._limiters[host]

    def acquire(self, host: str) -> None:
        """Acquire permission for a request to the given host."""
        limiter = self._get_limiter(host)
        limiter.acquire()


class AsyncPerHostRateLimiter:
    """
    Async rate limiter that applies separate limits per host.

    Args:
        rate: Requests per second per host
        capacity: Burst capacity per host
        blocking: If True, wait for tokens; if False, raise RateLimitExceeded
    """

    def __init__(
        self,
        rate: float,
        capacity: float | None = None,
        blocking: bool = True,
    ) -> None:
        self.rate = rate
        self.capacity = capacity
        self.blocking = blocking
        self._limiters: dict[str, AsyncTokenBucket] = {}
        self._lock = asyncio.Lock()

    async def _get_limiter(self, host: str) -> AsyncTokenBucket:
        """Get or create a limiter for the given host."""
        async with self._lock:
            if host not in self._limiters:
                self._limiters[host] = AsyncTokenBucket(
                    rate=self.rate,
                    capacity=self.capacity,
                    blocking=self.blocking,
                )
            return self._limiters[host]

    async def acquire(self, host: str) -> None:
        """Acquire permission for a request to the given host."""
        limiter = await self._get_limiter(host)
        await limiter.acquire()


def rate_limited(
    rate: float,
    capacity: float | None = None,
    blocking: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to apply rate limiting to a synchronous function.

    Args:
        rate: Requests per second
        capacity: Burst capacity (defaults to rate)
        blocking: If True, wait; if False, raise RateLimitExceeded

    Returns:
        Decorated function
    """
    limiter = TokenBucket(rate=rate, capacity=capacity, blocking=blocking)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            limiter.acquire()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def arate_limited(
    rate: float,
    capacity: float | None = None,
    blocking: bool = True,
) -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]:
    """
    Decorator to apply rate limiting to an async function.

    Args:
        rate: Requests per second
        capacity: Burst capacity (defaults to rate)
        blocking: If True, wait; if False, raise RateLimitExceeded

    Returns:
        Decorated async function
    """
    limiter = AsyncTokenBucket(rate=rate, capacity=capacity, blocking=blocking)

    def decorator(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
        async def wrapper(*args, **kwargs) -> R:
            await limiter.acquire()
            return await func(*args, **kwargs)
        return wrapper
    return decorator
