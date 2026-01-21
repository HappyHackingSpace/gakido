from __future__ import annotations

import time
import random
from collections.abc import Callable


class RetryError(Exception):
    """Raised when the maximum number of retries is exhausted."""
    pass


def default_retryable_status_codes() -> set[int]:
    """Default set of HTTP status codes that are considered retryable."""
    return {408, 429, 500, 502, 503, 504, 507, 511}


def default_retryable_exceptions() -> set[type[BaseException]]:
    """Default set of exceptions that are considered retryable."""
    return {
        ConnectionError,
        TimeoutError,
        OSError,
    }


class RetryState:
    """State for a single retry attempt."""
    def __init__(self, attempt: int, max_attempts: int):
        self.attempt = attempt
        self.max_attempts = max_attempts

    @property
    def is_last_attempt(self) -> bool:
        return self.attempt >= self.max_attempts

    def next(self) -> RetryState:
        """Return the next retry state."""
        return RetryState(self.attempt + 1, self.max_attempts)


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    Calculate exponential backoff delay with optional jitter.

    Args:
        attempt: Current attempt number (0-based).
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        exponential_base: Base for exponential backoff.
        jitter: Whether to add random jitter to avoid thundering herd.

    Returns:
        Delay in seconds.
    """
    delay = base_delay * (exponential_base ** attempt)
    delay = min(delay, max_delay)
    if jitter:
        delay *= (0.5 + random.random() * 0.5)  # 50% to 100% of full delay
    return delay


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_status_codes: set[int] | None = None,
    retryable_exceptions: set[type[BaseException]] | None = None,
    on_retry: Callable[[RetryState, Exception, float], None] | None = None,
) -> Callable:
    """
    Decorator to add retry-with-backoff to a function.

    Args:
        max_attempts: Maximum number of attempts (including initial attempt).
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        exponential_base: Base for exponential backoff.
        jitter: Whether to add random jitter.
        retryable_status_codes: HTTP status codes that should trigger retries.
        retryable_exceptions: Exception types that should trigger retries.
        on_retry: Callback called before each retry (state, exception, delay).

    Returns:
        Decorated function that retries on failure.
    """
    if retryable_status_codes is None:
        retryable_status_codes = default_retryable_status_codes()
    if retryable_exceptions is None:
        retryable_exceptions = default_retryable_exceptions()

    def decorator(func):
        def wrapper(*args, **kwargs):
            state = RetryState(attempt=0, max_attempts=max_attempts)
            last_exception = None

            while True:
                try:
                    result = func(*args, **kwargs)
                    # If result has a status_code attribute (like Response), check it
                    if hasattr(result, "status_code"):
                        if result.status_code in retryable_status_codes:
                            raise RetryError(f"Retryable status code: {result.status_code}")
                    return result
                except Exception as e:
                    # Filter by exception type
                    if not any(isinstance(e, exc_type) for exc_type in retryable_exceptions):
                        # Special case: our own RetryError for status codes
                        if type(e).__name__ == "RetryError":
                            pass  # treat as retryable
                        else:
                            raise  # non-retryable exception
                    last_exception = e

                    if state.attempt >= max_attempts - 1:
                        raise RetryError(f"Max retries ({max_attempts}) exhausted") from last_exception

                    # Calculate delay and sleep
                    delay = calculate_backoff_delay(
                        state.attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                        jitter=jitter,
                    )

                    if on_retry:
                        on_retry(state, e, delay)

                    time.sleep(delay)
                    state = state.next()

        return wrapper
    return decorator


def aretry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_status_codes: set[int] | None = None,
    retryable_exceptions: set[type[BaseException]] | None = None,
    on_retry: Callable[[RetryState, Exception, float], None] | None = None,
) -> Callable:
    """
    Async version of the retry decorator.
    """
    import asyncio

    if retryable_status_codes is None:
        retryable_status_codes = default_retryable_status_codes()
    if retryable_exceptions is None:
        retryable_exceptions = default_retryable_exceptions()

    def decorator(func):
        async def wrapper(*args, **kwargs):
            state = RetryState(attempt=0, max_attempts=max_attempts)
            last_exception = None

            while True:
                try:
                    result = await func(*args, **kwargs)
                    # If result has a status_code attribute (like Response), check it
                    if hasattr(result, "status_code"):
                        if result.status_code in retryable_status_codes:
                            raise RetryError(f"Retryable status code: {result.status_code}")
                    return result
                except Exception as e:
                    # Filter by exception type
                    if not any(isinstance(e, exc_type) for exc_type in retryable_exceptions):
                        # Special case: our own RetryError for status codes
                        if type(e).__name__ == "RetryError":
                            pass  # treat as retryable
                        else:
                            raise  # non-retryable exception
                    last_exception = e

                    if state.attempt >= max_attempts - 1:
                        raise RetryError(f"Max retries ({max_attempts}) exhausted") from last_exception

                    # Calculate delay and sleep
                    delay = calculate_backoff_delay(
                        state.attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                        jitter=jitter,
                    )

                    if on_retry:
                        on_retry(state, e, delay)

                    await asyncio.sleep(delay)
                    state = state.next()

        return wrapper
    return decorator
