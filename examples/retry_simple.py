#!/usr/bin/env python3
"""
Simple retry example without external dependencies.
"""

import sys
import os

# Import backoff module directly
import gakido.backoff as backoff
from gakido.backoff import retry_with_backoff, aretry_with_backoff, RetryError
import asyncio
import time

def sync_retry_example():
    """Example of sync retry with exponential backoff."""
    print("=== Sync retry example ===")

    call_count = 0

    @retry_with_backoff(max_attempts=3, base_delay=0.1, jitter=False)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        print(f"  Attempt {call_count}...")
        if call_count < 3:
            raise ConnectionError("Temporary failure")
        return "Success!"

    try:
        start = time.time()
        result = flaky_function()
        elapsed = time.time() - start
        print(f"  Result: {result}")
        print(f"  Time elapsed: {elapsed:.2f}s")
    except RetryError as e:
        print(f"  Failed: {e}")

async def async_retry_example():
    """Example of async retry with exponential backoff."""
    print("\n=== Async retry example ===")

    call_count = 0

    @aretry_with_backoff(max_attempts=3, base_delay=0.1, jitter=False)
    async def async_flaky_function():
        nonlocal call_count
        call_count += 1
        print(f"  Attempt {call_count}...")
        if call_count < 3:
            raise ConnectionError("Temporary failure")
        return "Success!"

    try:
        start = time.time()
        result = await async_flaky_function()
        elapsed = time.time() - start
        print(f"  Result: {result}")
        print(f"  Time elapsed: {elapsed:.2f}s")
    except RetryError as e:
        print(f"  Failed: {e}")

def delay_calculation_example():
    """Example of delay calculation with jitter."""
    print("\n=== Delay calculation example ===")

    from gakido.backoff import _calculate_delay

    print("  Exponential backoff delays (no jitter):")
    for i in range(4):
        delay = _calculate_delay(i, base=0.1, max_delay=2.0, jitter=False)
        print(f"    Attempt {i}: {delay:.3f}s")

    print("\n  With jitter (50-100% of base delay):")
    for i in range(4):
        delay = _calculate_delay(i, base=0.1, max_delay=2.0, jitter=True)
        print(f"    Attempt {i}: {delay:.3f}s")

if __name__ == "__main__":
    sync_retry_example()
    asyncio.run(async_retry_example())
    delay_calculation_example()
    print("\n✓ Retry with exponential backoff examples completed!")
