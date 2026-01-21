import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock

from gakido import Client, AsyncClient
from gakido.backoff import RetryError, _calculate_delay, _default_retryable_status_codes


def test_calculate_backoff_delay():
    """Test exponential backoff calculation."""
    # No jitter
    delay = _calculate_delay(0, base=1.0, max_delay=60.0, jitter=False)
    assert delay == 1.0

    delay = _calculate_delay(1, base=1.0, max_delay=60.0, jitter=False)
    assert delay == 2.0

    delay = _calculate_delay(2, base=1.0, max_delay=60.0, jitter=False)
    assert delay == 4.0

    # Max delay cap
    delay = _calculate_delay(10, base=1.0, max_delay=5.0, jitter=False)
    assert delay == 5.0

    # With jitter (should be between 50% and 100% of full delay)
    delay = _calculate_delay(2, base=1.0, max_delay=60.0, jitter=True)
    assert 2.0 <= delay <= 4.0


def test_default_retryable_status_codes():
    """Test default retryable status codes."""
    codes = _default_retryable_status_codes()
    assert 408 in codes  # Request Timeout
    assert 429 in codes  # Too Many Requests
    assert 500 in codes  # Internal Server Error
    assert 502 in codes  # Bad Gateway
    assert 503 in codes  # Service Unavailable
    assert 200 not in codes  # OK should not be retryable
    assert 404 not in codes  # Not Found should not be retryable


def test_client_retry_disabled_by_default():
    """Test that retry is disabled by default."""
    client = Client()
    assert client.max_retries == 0


def test_client_retry_configuration():
    """Test retry configuration options."""
    client = Client(
        max_retries=3,
        retry_base_delay=0.5,
        retry_max_delay=30.0,
        retry_jitter=False,
    )
    assert client.max_retries == 3
    assert client.retry_base_delay == 0.5
    assert client.retry_max_delay == 30.0
    assert client.retry_jitter is False


@patch('gakido.client.ConnectionPool')
@patch('gakido.client.get_profile')
def test_client_retry_on_exception(mock_get_profile, mock_pool):
    """Test that client retries on retryable exceptions."""
    mock_get_profile.return_value = {
        "headers": {"default": [("User-Agent", "gakido")], "order": ["User-Agent"]},
        "tls": {},
    }

    # Mock connection that fails twice then succeeds
    mock_conn = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_conn.request.side_effect = [
        ConnectionError("First failure"),
        ConnectionError("Second failure"),
        mock_response,
    ]
    mock_conn.closed = False
    mock_pool.return_value.acquire.return_value = mock_conn

    client = Client(max_retries=3, retry_base_delay=0.01, retry_jitter=False, use_native=False)
    start = time.time()
    response = client.get("http://example.com")
    elapsed = time.time() - start

    # Should have retried twice (initial + 2 retries)
    assert mock_conn.request.call_count == 3
    # Should have delayed between retries (base_delay * 2^attempt)
    assert elapsed >= 0.01 + 0.02  # 0.01s + 0.02s
    assert response == mock_response


@patch('gakido.client.ConnectionPool')
@patch('gakido.client.get_profile')
def test_client_retry_exhausted(mock_get_profile, mock_pool):
    """Test that client raises RetryError when max retries exhausted."""
    mock_get_profile.return_value = {
        "headers": {"default": [("User-Agent", "gakido")], "order": ["User-Agent"]},
        "tls": {},
    }

    mock_conn = MagicMock()
    mock_conn.request.side_effect = ConnectionError("Always fails")
    mock_conn.closed = False
    mock_pool.return_value.acquire.return_value = mock_conn

    client = Client(max_retries=2, retry_base_delay=0.01, retry_jitter=False, use_native=False)

    with pytest.raises(RetryError):
        client.get("http://example.com")

    # Should have attempted initial + 2 retries = 3 total attempts, but max_attempts=3 means 3 attempts total
    assert mock_conn.request.call_count == 3


@patch('gakido.client.ConnectionPool')
@patch('gakido.client.get_profile')
def test_client_retry_on_status_code(mock_get_profile, mock_pool):
    """Test that client retries on retryable status codes."""
    mock_get_profile.return_value = {
        "headers": {"default": [("User-Agent", "gakido")], "order": ["User-Agent"]},
        "tls": {},
    }

    # Mock responses: 503 twice, then 200
    mock_responses = [
        MagicMock(status_code=503),
        MagicMock(status_code=503),
        MagicMock(status_code=200),
    ]
    mock_conn = MagicMock()
    mock_conn.request.side_effect = mock_responses
    mock_conn.closed = False
    mock_pool.return_value.acquire.return_value = mock_conn

    client = Client(max_retries=3, retry_base_delay=0.01, retry_jitter=False, use_native=False)
    response = client.get("http://example.com")

    # Should have retried twice
    assert mock_conn.request.call_count == 3
    assert response.status_code == 200


@patch('gakido.client.ConnectionPool')
@patch('gakido.client.get_profile')
def test_client_no_retry_on_non_retryable_status(mock_get_profile, mock_pool):
    """Test that client does not retry on non-retryable status codes."""
    mock_get_profile.return_value = {
        "headers": {"default": [("User-Agent", "gakido")], "order": ["User-Agent"]},
        "tls": {},
    }

    mock_response = MagicMock(status_code=404)
    mock_conn = MagicMock()
    mock_conn.request.return_value = mock_response
    mock_conn.closed = False
    mock_pool.return_value.acquire.return_value = mock_conn

    client = Client(max_retries=3, use_native=False)
    response = client.get("http://example.com")

    # Should not have retried
    assert mock_conn.request.call_count == 1
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_async_client_retry_configuration():
    """Test async client retry configuration."""
    client = AsyncClient(
        max_retries=2,
        retry_base_delay=0.1,
        retry_max_delay=20.0,
        retry_jitter=True,
    )
    assert client.max_retries == 2
    assert client.retry_base_delay == 0.1
    assert client.retry_max_delay == 20.0
    assert client.retry_jitter is True


@pytest.mark.asyncio
@patch('gakido.aio.asyncio.open_connection')
async def test_async_client_retry_on_exception(mock_open_conn):
    """Test that async client retries on retryable exceptions."""
    import asyncio

    # Mock connection that fails twice then succeeds
    mock_reader = MagicMock()
    mock_reader.readline = AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"])
    mock_reader.read = AsyncMock(return_value=b"")
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.drain = AsyncMock()
    mock_writer.writelines = MagicMock()

    mock_open_conn.side_effect = [
        ConnectionError("First failure"),
        ConnectionError("Second failure"),
        (mock_reader, mock_writer),
    ]

    client = AsyncClient(max_retries=3, retry_base_delay=0.01, retry_jitter=False)
    start = time.time()
    response = await client.get("http://example.com")
    elapsed = time.time() - start

    # Should have retried twice
    assert mock_open_conn.call_count == 3
    assert elapsed >= 0.01 + 0.02  # base_delay * 2^attempt
    assert response.status_code == 200


@pytest.mark.asyncio
@patch('gakido.aio.asyncio.open_connection')
async def test_async_client_retry_exhausted(mock_open_conn):
    """Test that async client raises RetryError when max retries exhausted."""
    mock_open_conn.side_effect = ConnectionError("Always fails")

    client = AsyncClient(max_retries=2, retry_base_delay=0.01, retry_jitter=False)

    with pytest.raises(RetryError, match="Max retries"):
        await client.get("http://example.com")

    # Should have attempted initial + 2 retries
    assert mock_open_conn.call_count == 3
