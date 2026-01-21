"""Retry with exponential backoff utilities."""

import time
import random
import asyncio
from collections.abc import Callable


class RetryError(Exception):
    """Raised when the maximum number of retries is exhausted."""
    pass


def _default_retryable_status_codes() -> set[int]:
    """Default HTTP status codes that are considered retryable."""
    return {408, 429, 500, 502, 503, 504, 507, 511}


def _default_retryable_exceptions() -> set[type[BaseException]]:
    """Default exception types that are considered retryable."""
    return {ConnectionError, TimeoutError, OSError}


def _calculate_delay(attempt: int, base: float, max_delay: float, jitter: bool) -> float:
    """Calculate exponential backoff delay with optional jitter."""
    delay = min(base * (2 ** attempt), max_delay)
    if jitter:
        delay *= (0.5 + random.random() * 0.5)  # 50-100% of delay
    return delay


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable_status_codes: set[int] | None = None,
    retryable_exceptions: set[type[BaseException]] | None = None,
) -> Callable:
    """
    Decorator for retry with exponential backoff.

    Args:
        max_attempts: Maximum number of total attempts (including first).
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        jitter: Whether to add random jitter.
        retryable_status_codes: HTTP status codes to retry on.
        retryable_exceptions: Exception types to retry on.

    Returns:
        Decorated function that retries on failure.
    """
    if retryable_status_codes is None:
        retryable_status_codes = _default_retryable_status_codes()
    if retryable_exceptions is None:
        retryable_exceptions = _default_retryable_exceptions()

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            attempt = 0
            last_exc = None

            while attempt < max_attempts:
                try:
                    result = func(*args, **kwargs)
                    # Check for retryable HTTP status codes
                    if hasattr(result, "status_code") and result.status_code in retryable_status_codes:
                        raise RetryError(f"Retryable status code: {result.status_code}")
                    return result
                except RetryError:
                    # Our own retry error for status codes
                    last_exc = RetryError("Retryable status code")
                except Exception as e:
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in retryable_exceptions):
                        raise  # Non-retryable, re-raise immediately
                    last_exc = e

                attempt += 1
                if attempt >= max_attempts:
                    break

                # Calculate delay and wait
                delay = _calculate_delay(attempt - 1, base_delay, max_delay, jitter)
                time.sleep(delay)

            raise RetryError(f"Max retries ({max_attempts}) exhausted") from last_exc

        return wrapper
    return decorator


def aretry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable_status_codes: set[int] | None = None,
    retryable_exceptions: set[type[BaseException]] | None = None,
) -> Callable:
    """
    Async decorator for retry with exponential backoff.
    """
    if retryable_status_codes is None:
        retryable_status_codes = _default_retryable_status_codes()
    if retryable_exceptions is None:
        retryable_exceptions = _default_retryable_exceptions()

    def decorator(func: Callable) -> Callable:
        async def awrapper(*args, **kwargs):
            attempt = 0
            last_exc = None

            while attempt < max_attempts:
                try:
                    result = await func(*args, **kwargs)
                    # Check for retryable HTTP status codes
                    if hasattr(result, "status_code") and result.status_code in retryable_status_codes:
                        raise RetryError(f"Retryable status code: {result.status_code}")
                    return result
                except RetryError:
                    # Our own retry error for status codes
                    last_exc = RetryError("Retryable status code")
                except Exception as e:
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in retryable_exceptions):
                        raise  # Non-retryable, re-raise immediately
                    last_exc = e

                attempt += 1
                if attempt >= max_attempts:
                    break

                # Calculate delay and wait
                delay = _calculate_delay(attempt - 1, base_delay, max_delay, jitter)
                await asyncio.sleep(delay)

            raise RetryError(f"Max retries ({max_attempts}) exhausted") from last_exc

        return awrapper
    return decorator
