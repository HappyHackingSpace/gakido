#!/usr/bin/env python3
"""
Example: Retry with exponential backoff.

This demonstrates how to use gakido's retry functionality for handling
transient failures like network errors or rate limiting.
"""

import asyncio
from gakido import Client, AsyncClient
from gakido.backoff import RetryError

def sync_retry_example():
    """Example of retry with sync client."""
    print("=== Sync retry example ===")

    # Client with retry configuration
    client = Client(
        max_retries=3,           # Up to 3 retry attempts
        retry_base_delay=0.5,    # Start with 0.5s delay
        retry_max_delay=10.0,    # Cap delay at 10s
        retry_jitter=True,       # Add random jitter
        use_native=False,        # Use Python path to avoid header format issues
    )

    try:
        # This will retry on connection errors or 5xx responses
        response = client.get("http://httpbin.org/status/500")
        print(f"Success: {response.status_code}")
    except RetryError as e:
        print(f"All retries exhausted: {e}")
    except Exception as e:
        print(f"Non-retryable error: {e}")

async def async_retry_example():
    """Example of retry with async client."""
    print("\n=== Async retry example ===")

    # Async client with retry
    client = AsyncClient(
        max_retries=2,
        retry_base_delay=1.0,
        retry_jitter=False,  # Predictable delays for demo
    )

    try:
        # This will retry on connection errors or rate limiting
        response = await client.get("http://httpbin.org/status/429")
        print(f"Success: {response.status_code}")
    except RetryError as e:
        print(f"All retries exhausted: {e}")
    except Exception as e:
        print(f"Non-retryable error: {e}")

def retry_decorator_example():
    """Example of using the retry decorator directly."""
    print("\n=== Retry decorator example ===")

    from gakido.backoff import retry_with_backoff

    call_count = 0

    @retry_with_backoff(max_attempts=3, base_delay=0.1, jitter=False)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Temporary failure")
        return f"Success after {call_count} attempts"

    try:
        result = flaky_function()
        print(f"Result: {result}")
    except RetryError as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    sync_retry_example()
    asyncio.run(async_retry_example())
    retry_decorator_example()
