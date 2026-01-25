# Retry with Exponential Backoff

gakido provides built-in retry functionality with exponential backoff for handling transient failures like network errors or server issues.

## Features

- **Exponential backoff** with configurable base delay and maximum delay
- **Jitter** to prevent thundering herd when many clients retry simultaneously
- **Configurable retry conditions** - retry on specific HTTP status codes and exception types
- **Zero overhead** when disabled (default)
- **Works with both sync and async clients**

## Basic Usage

### Sync Client

```python
from gakido import Client

client = Client(
    max_retries=3,           # Up to 3 retry attempts (4 total attempts)
    retry_base_delay=0.5,    # Start with 0.5s delay
    retry_max_delay=30.0,    # Cap delay at 30s
    retry_jitter=True,       # Add random jitter
)

try:
    response = client.get("http://flaky.example.com")
    print(f"Success: {response.status_code}")
except Exception as e:
    print(f"Failed after retries: {e}")
```

### Async Client

```python
from gakido import AsyncClient

async_client = AsyncClient(
    max_retries=2,
    retry_base_delay=1.0,
    retry_jitter=False,  # Predictable delays for testing
)

try:
    response = await async_client.get("http://api.example.com")
    print(f"Success: {response.status_code}")
except Exception as e:
    print(f"Failed after retries: {e}")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_retries` | `int` | `0` | Maximum number of retry attempts (0 = disabled) |
| `retry_base_delay` | `float` | `1.0` | Initial delay in seconds for exponential backoff |
| `retry_max_delay` | `float` | `60.0` | Maximum delay in seconds |
| `retry_jitter` | `bool` | `True` | Whether to add random jitter to avoid thundering herd |

## Retry Conditions

### Default Retryable Status Codes

The following HTTP status codes trigger retries by default:
- `408` - Request Timeout
- `429` - Too Many Requests
- `500` - Internal Server Error
- `502` - Bad Gateway
- `503` - Service Unavailable
- `504` - Gateway Timeout
- `507` - Insufficient Storage
- `511` - Network Authentication Required

### Default Retryable Exceptions

The following exception types trigger retries by default:
- `ConnectionError` - Network connection failures
- `TimeoutError` - Request timeout
- `OSError` - Operating system level errors

## Using Retry Decorators Directly

You can also use the retry decorators directly on your own functions:

```python
from gakido.backoff import retry_with_backoff, aretry_with_backoff

# Sync decorator
@retry_with_backoff(max_attempts=3, base_delay=0.1, jitter=False)
def flaky_operation():
    # Your code here that might fail
    pass

# Async decorator
@aretry_with_backoff(max_attempts=3, base_delay=0.1, jitter=False)
async def async_flaky_operation():
    # Your async code here that might fail
    pass
```

## Delay Calculation

The delay between retries follows exponential backoff:

```
delay = min(base_delay * (2 ^ attempt), max_delay)
```

With jitter enabled (default), the delay is reduced to 50-100% of the calculated value to prevent synchronized retries across multiple clients.

## Examples

### Handling Rate Limiting

```python
client = Client(
    max_retries=5,
    retry_base_delay=2.0,  # Start with 2s delay for rate limits
    retry_jitter=True,
)

# Will retry on 429 Too Many Requests
response = client.get("https://api.example.com/data")
```

### Quick Retries for Unstable Networks

```python
client = Client(
    max_retries=2,
    retry_base_delay=0.1,  # Quick retries
    retry_max_delay=1.0,
    retry_jitter=False,    # Predictable for debugging
)
```

### Disabling Retry

```python
# Retry is disabled by default
client = Client()  # max_retries=0

# Or explicitly disable
client = Client(max_retries=0)
```

## Best Practices

1. **Use jitter** in production to prevent thundering herd
2. **Set reasonable max delays** to avoid excessive wait times
3. **Monitor retry metrics** to identify systemic issues
4. **Handle non-retryable errors** appropriately (e.g., 404, 401)
5. **Test retry logic** with controlled failures
