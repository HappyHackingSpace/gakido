#!/usr/bin/env python3
"""
Simple test to verify retry functionality works.
"""

from gakido import Client
from gakido.backoff import RetryError, retry_with_backoff

def test_retry_decorator():
    """Test the retry decorator directly."""
    call_count = 0

    @retry_with_backoff(max_attempts=3, base_delay=0.01, jitter=False)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Temporary failure")
        return "success"

    result = flaky_function()
    assert result == "success"
    assert call_count == 3
    print("✓ Retry decorator works correctly")

def test_client_retry():
    """Test client retry configuration."""
    client = Client(
        max_retries=2,
        retry_base_delay=0.1,
        retry_max_delay=1.0,
        retry_jitter=False,
    )

    assert client.max_retries == 2
    assert client.retry_base_delay == 0.1
    assert client.retry_max_delay == 1.0
    assert client.retry_jitter is False
    print("✓ Client retry configuration works")

if __name__ == "__main__":
    test_retry_decorator()
    test_client_retry()
    print("\nAll tests passed!")
