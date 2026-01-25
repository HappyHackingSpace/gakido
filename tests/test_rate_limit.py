"""Tests for rate limiting functionality."""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from gakido import Client, AsyncClient
from gakido.rate_limit import (
    RateLimitExceeded,
    TokenBucket,
    AsyncTokenBucket,
    SlidingWindowLimiter,
    AsyncSlidingWindowLimiter,
    PerHostRateLimiter,
    AsyncPerHostRateLimiter,
    rate_limited,
    arate_limited,
)


class TestTokenBucket:
    """Tests for synchronous TokenBucket."""

    def test_basic_acquire(self):
        """Test basic token acquisition."""
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        # Should be able to acquire immediately
        bucket.acquire()
        bucket.acquire()

    def test_burst_capacity(self):
        """Test burst capacity allows multiple immediate requests."""
        bucket = TokenBucket(rate=1.0, capacity=5.0)
        start = time.monotonic()
        for _ in range(5):
            bucket.acquire()
        elapsed = time.monotonic() - start
        # All 5 should be immediate (within burst capacity)
        assert elapsed < 0.1

    def test_rate_limiting_blocks(self):
        """Test that rate limiting blocks when tokens exhausted."""
        bucket = TokenBucket(rate=10.0, capacity=1.0, blocking=True)
        bucket.acquire()  # Use the one token
        start = time.monotonic()
        bucket.acquire()  # Should block ~0.1s
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09  # Allow small timing variance

    def test_non_blocking_raises(self):
        """Test non-blocking mode raises RateLimitExceeded."""
        bucket = TokenBucket(rate=10.0, capacity=1.0, blocking=False)
        bucket.acquire()  # Use the one token
        with pytest.raises(RateLimitExceeded) as exc_info:
            bucket.acquire()
        assert exc_info.value.retry_after is not None
        assert exc_info.value.retry_after > 0

    def test_context_manager(self):
        """Test context manager usage."""
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        with bucket:
            pass  # Should acquire and release

    def test_token_refill(self):
        """Test tokens refill over time."""
        bucket = TokenBucket(rate=100.0, capacity=1.0)
        bucket.acquire()  # Use the token
        time.sleep(0.02)  # Wait for ~2 tokens to refill
        # Should be able to acquire again
        bucket.acquire()


class TestAsyncTokenBucket:
    """Tests for asynchronous AsyncTokenBucket."""

    @pytest.mark.asyncio
    async def test_basic_acquire(self):
        """Test basic async token acquisition."""
        bucket = AsyncTokenBucket(rate=10.0, capacity=10.0)
        await bucket.acquire()
        await bucket.acquire()

    @pytest.mark.asyncio
    async def test_burst_capacity(self):
        """Test burst capacity allows multiple immediate requests."""
        bucket = AsyncTokenBucket(rate=1.0, capacity=5.0)
        start = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiting_blocks(self):
        """Test that rate limiting blocks when tokens exhausted."""
        bucket = AsyncTokenBucket(rate=10.0, capacity=1.0, blocking=True)
        await bucket.acquire()
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09

    @pytest.mark.asyncio
    async def test_non_blocking_raises(self):
        """Test non-blocking mode raises RateLimitExceeded."""
        bucket = AsyncTokenBucket(rate=10.0, capacity=1.0, blocking=False)
        await bucket.acquire()
        with pytest.raises(RateLimitExceeded) as exc_info:
            await bucket.acquire()
        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager usage."""
        bucket = AsyncTokenBucket(rate=10.0, capacity=10.0)
        async with bucket:
            pass


class TestSlidingWindowLimiter:
    """Tests for synchronous SlidingWindowLimiter."""

    def test_basic_acquire(self):
        """Test basic request acquisition."""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1.0)
        for _ in range(10):
            limiter.acquire()

    def test_window_limit_blocks(self):
        """Test that exceeding window limit blocks."""
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=0.1, blocking=True)
        limiter.acquire()
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()  # Should block until window slides
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09

    def test_non_blocking_raises(self):
        """Test non-blocking mode raises RateLimitExceeded."""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=1.0, blocking=False)
        limiter.acquire()
        with pytest.raises(RateLimitExceeded) as exc_info:
            limiter.acquire()
        assert exc_info.value.retry_after > 0

    def test_context_manager(self):
        """Test context manager usage."""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1.0)
        with limiter:
            pass


class TestAsyncSlidingWindowLimiter:
    """Tests for asynchronous AsyncSlidingWindowLimiter."""

    @pytest.mark.asyncio
    async def test_basic_acquire(self):
        """Test basic async request acquisition."""
        limiter = AsyncSlidingWindowLimiter(max_requests=10, window_seconds=1.0)
        for _ in range(10):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_window_limit_blocks(self):
        """Test that exceeding window limit blocks."""
        limiter = AsyncSlidingWindowLimiter(max_requests=2, window_seconds=0.1, blocking=True)
        await limiter.acquire()
        await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09

    @pytest.mark.asyncio
    async def test_non_blocking_raises(self):
        """Test non-blocking mode raises RateLimitExceeded."""
        limiter = AsyncSlidingWindowLimiter(max_requests=1, window_seconds=1.0, blocking=False)
        await limiter.acquire()
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager usage."""
        limiter = AsyncSlidingWindowLimiter(max_requests=10, window_seconds=1.0)
        async with limiter:
            pass


class TestPerHostRateLimiter:
    """Tests for per-host rate limiting."""

    def test_separate_limits_per_host(self):
        """Test that different hosts have separate limits."""
        limiter = PerHostRateLimiter(rate=1.0, capacity=1.0, blocking=False)
        # Each host should have its own bucket
        limiter.acquire("host1.com")
        limiter.acquire("host2.com")
        limiter.acquire("host3.com")
        # But same host should be limited
        with pytest.raises(RateLimitExceeded):
            limiter.acquire("host1.com")

    def test_blocking_mode(self):
        """Test blocking mode waits for tokens."""
        limiter = PerHostRateLimiter(rate=10.0, capacity=1.0, blocking=True)
        limiter.acquire("example.com")
        start = time.monotonic()
        limiter.acquire("example.com")
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09


class TestAsyncPerHostRateLimiter:
    """Tests for async per-host rate limiting."""

    @pytest.mark.asyncio
    async def test_separate_limits_per_host(self):
        """Test that different hosts have separate limits."""
        limiter = AsyncPerHostRateLimiter(rate=1.0, capacity=1.0, blocking=False)
        await limiter.acquire("host1.com")
        await limiter.acquire("host2.com")
        await limiter.acquire("host3.com")
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire("host1.com")

    @pytest.mark.asyncio
    async def test_blocking_mode(self):
        """Test blocking mode waits for tokens."""
        limiter = AsyncPerHostRateLimiter(rate=10.0, capacity=1.0, blocking=True)
        await limiter.acquire("example.com")
        start = time.monotonic()
        await limiter.acquire("example.com")
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09


class TestRateLimitedDecorator:
    """Tests for rate_limited decorator."""

    def test_sync_decorator(self):
        """Test synchronous rate_limited decorator."""
        call_count = 0

        @rate_limited(rate=100.0, capacity=2.0)
        def my_func():
            nonlocal call_count
            call_count += 1
            return call_count

        # First two should be immediate (within capacity)
        assert my_func() == 1
        assert my_func() == 2

    def test_sync_decorator_non_blocking(self):
        """Test non-blocking decorator raises exception."""
        @rate_limited(rate=10.0, capacity=1.0, blocking=False)
        def my_func():
            return "ok"

        my_func()  # First call ok
        with pytest.raises(RateLimitExceeded):
            my_func()  # Second should fail


class TestAsyncRateLimitedDecorator:
    """Tests for arate_limited decorator."""

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        """Test asynchronous arate_limited decorator."""
        call_count = 0

        @arate_limited(rate=100.0, capacity=2.0)
        async def my_func():
            nonlocal call_count
            call_count += 1
            return call_count

        assert await my_func() == 1
        assert await my_func() == 2

    @pytest.mark.asyncio
    async def test_async_decorator_non_blocking(self):
        """Test non-blocking async decorator raises exception."""
        @arate_limited(rate=10.0, capacity=1.0, blocking=False)
        async def my_func():
            return "ok"

        await my_func()
        with pytest.raises(RateLimitExceeded):
            await my_func()


class TestClientRateLimiting:
    """Tests for rate limiting integration with Client."""

    def test_client_rate_limit_disabled_by_default(self):
        """Test that rate limiting is disabled by default."""
        client = Client()
        assert client._rate_limiter is None
        assert client._per_host_limiter is None

    def test_client_rate_limit_configuration(self):
        """Test rate limit configuration options."""
        client = Client(
            rate_limit=10.0,
            rate_limit_capacity=5.0,
            rate_limit_per_host=2.0,
            rate_limit_blocking=False,
        )
        assert client._rate_limiter is not None
        assert client._rate_limiter.rate == 10.0
        assert client._rate_limiter.capacity == 5.0
        assert client._rate_limiter.blocking is False
        assert client._per_host_limiter is not None
        assert client._per_host_limiter.rate == 2.0

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_client_rate_limiting_applied(self, mock_get_profile, mock_pool):
        """Test that rate limiting is applied to requests."""
        mock_get_profile.return_value = {
            "headers": {"default": [("User-Agent", "gakido")], "order": ["User-Agent"]},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(
            rate_limit=10.0,
            rate_limit_capacity=1.0,
            use_native=False,
        )

        # First request should be immediate
        client.get("http://example.com")

        # Second request should be delayed
        start = time.monotonic()
        client.get("http://example.com")
        elapsed = time.monotonic() - start

        assert elapsed >= 0.09

    @patch('gakido.client.ConnectionPool')
    @patch('gakido.client.get_profile')
    def test_client_rate_limit_non_blocking_raises(self, mock_get_profile, mock_pool):
        """Test non-blocking rate limit raises exception."""
        mock_get_profile.return_value = {
            "headers": {"default": [("User-Agent", "gakido")], "order": ["User-Agent"]},
            "tls": {},
        }
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_conn.request.return_value = mock_response
        mock_conn.closed = False
        mock_pool.return_value.acquire.return_value = mock_conn

        client = Client(
            rate_limit=10.0,
            rate_limit_capacity=1.0,
            rate_limit_blocking=False,
            use_native=False,
        )

        client.get("http://example.com")
        with pytest.raises(RateLimitExceeded):
            client.get("http://example.com")


class TestAsyncClientRateLimiting:
    """Tests for rate limiting integration with AsyncClient."""

    def test_async_client_rate_limit_disabled_by_default(self):
        """Test that rate limiting is disabled by default."""
        client = AsyncClient()
        assert client._rate_limiter is None
        assert client._per_host_limiter is None

    def test_async_client_rate_limit_configuration(self):
        """Test rate limit configuration options."""
        client = AsyncClient(
            rate_limit=10.0,
            rate_limit_capacity=5.0,
            rate_limit_per_host=2.0,
            rate_limit_blocking=False,
        )
        assert client._rate_limiter is not None
        assert client._rate_limiter.rate == 10.0
        assert client._rate_limiter.capacity == 5.0
        assert client._rate_limiter.blocking is False
        assert client._per_host_limiter is not None
        assert client._per_host_limiter.rate == 2.0

    @pytest.mark.asyncio
    @patch('gakido.aio.asyncio.open_connection')
    async def test_async_client_rate_limiting_applied(self, mock_open_conn):
        """Test that rate limiting is applied to async requests."""
        mock_reader = MagicMock()
        mock_reader.readline = AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"])
        mock_reader.read = AsyncMock(return_value=b"")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()

        mock_open_conn.return_value = (mock_reader, mock_writer)

        client = AsyncClient(
            rate_limit=10.0,
            rate_limit_capacity=1.0,
        )

        # First request should be immediate
        await client.get("http://example.com")

        # Reset mock for second call
        mock_reader.readline = AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"])
        mock_reader.read = AsyncMock(return_value=b"")

        # Second request should be delayed
        start = time.monotonic()
        await client.get("http://example.com")
        elapsed = time.monotonic() - start

        assert elapsed >= 0.09

    @pytest.mark.asyncio
    @patch('gakido.aio.asyncio.open_connection')
    async def test_async_client_rate_limit_non_blocking_raises(self, mock_open_conn):
        """Test non-blocking rate limit raises exception."""
        mock_reader = MagicMock()
        mock_reader.readline = AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"])
        mock_reader.read = AsyncMock(return_value=b"")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        mock_writer.writelines = MagicMock()

        mock_open_conn.return_value = (mock_reader, mock_writer)

        client = AsyncClient(
            rate_limit=10.0,
            rate_limit_capacity=1.0,
            rate_limit_blocking=False,
        )

        await client.get("http://example.com")
        with pytest.raises(RateLimitExceeded):
            await client.get("http://example.com")


class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_exception_message(self):
        """Test exception message format."""
        exc = RateLimitExceeded()
        assert "Rate limit exceeded" in str(exc)
        assert exc.retry_after is None

    def test_exception_with_retry_after(self):
        """Test exception with retry_after value."""
        exc = RateLimitExceeded(retry_after=1.5)
        assert "retry after 1.50s" in str(exc)
        assert exc.retry_after == 1.5
