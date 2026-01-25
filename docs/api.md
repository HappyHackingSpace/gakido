# API Reference (essentials)

## gakido.Client
- `Client(impersonate="chrome_120", ja3=None, tls_configuration_options=None, proxies=None, timeout=10.0, verify=True, use_native=True, force_http1=True, auto_decompress=True, max_retries=0, retry_base_delay=1.0, retry_max_delay=60.0, retry_jitter=True)`
- Methods: `get`, `post`, `request`, `close`, context manager.
- `files` supported on `post`/`request` for multipart.
- **proxies** (`list[str] | None`): List of proxy URLs to rotate through. Supports HTTP, SOCKS5, and SOCKS5H schemes. Example: `["http://proxy:8080", "socks5://user:pass@proxy:1080"]`. Default: `None`.
- **max_retries** (`int`): Maximum number of retry attempts (0 disables retry). Default: `0`.
- **retry_base_delay** (`float`): Initial delay in seconds for exponential backoff. Default: `1.0`.
- **retry_max_delay** (`float`): Maximum delay in seconds. Default: `60.0`.
- **retry_jitter** (`bool`): Whether to add random jitter to avoid thundering herd. Default: `True`.

## gakido.aio.AsyncClient
- `AsyncClient(impersonate="chrome_120", timeout=10.0, verify=True, proxy_pool=None, ja3=None, tls_configuration_options=None, force_http1=True, http3=False, http3_fallback=True, auto_decompress=True, max_retries=0, retry_base_delay=1.0, retry_max_delay=60.0, retry_jitter=True)`
- Async context manager; methods `get`, `post`, `request`, `close`.
- **proxy_pool** (`list[str] | None`): List of proxy URLs to rotate through. Supports HTTP, SOCKS5, and SOCKS5H schemes. Example: `["http://proxy:8080", "socks5://user:pass@proxy:1080"]`. Default: `None`.
- **max_retries** (`int`): Maximum number of retry attempts (0 disables retry). Default: `0`.
- **retry_base_delay** (`float`): Initial delay in seconds for exponential backoff. Default: `1.0`.
- **retry_max_delay** (`float`): Maximum delay in seconds. Default: `60.0`.
- **retry_jitter** (`bool`): Whether to add random jitter to avoid thundering herd. Default: `True`.

### Compression Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `auto_decompress` | `bool` | `True` | Automatically decompress gzip/deflate/br responses |

When `auto_decompress=True`:
- Uses the profile's `Accept-Encoding` header (e.g., `gzip, deflate, br` for Chrome)
- Automatically decompresses response bodies based on `Content-Encoding`
- Supports gzip, deflate, and brotli (br) encodings

When `auto_decompress=False`:
- Sends `Accept-Encoding: identity` (no compression)
- Returns raw, uncompressed response bodies

### HTTP/3 Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `http3` | `bool` | `False` | Enable HTTP/3 (QUIC) for compatible targets |
| `http3_fallback` | `bool` | `True` | Fall back to HTTP/1.1 or HTTP/2 if HTTP/3 fails |
| `force_http3` | `bool` | `None` | Per-request override (in `request()` method) |

## gakido.is_http3_available
- `is_http3_available() -> bool`
- Returns `True` if aioquic is installed and HTTP/3 support is available.

## Profiles

**96 browser profiles** available (24 base + 72 aliases). See [Browser Profiles](profiles.md) for complete list.

- `impersonate` accepts keys from `gakido.impersonation.PROFILES`
- Supported browsers: Chrome, Firefox, Safari, Edge, Opera, Brave, Vivaldi, Tor
- Profiles include HTTP/3 settings (`http3.max_stream_data`, `http3.max_data`, `http3.idle_timeout`)
- Chrome/Edge/Opera/Brave/Vivaldi profiles include `client_hints` (Sec-CH-UA headers) and `canvas_webgl` fingerprint data

## Client Hints & Fingerprints

```python
from gakido.impersonation import (
    get_client_hints_headers,        # Extract Sec-CH-UA headers from profile
    get_canvas_webgl_fingerprint,    # Get WebGL vendor/renderer from profile
    build_client_hints_for_platform, # Build custom client hints
    generate_sec_ch_ua,              # Generate Sec-CH-UA header value
    parse_accept_ch,                 # Parse Accept-CH response header
    WEBGL_RENDERERS,                 # Predefined WebGL renderer strings
)
```

See [Client Hints & Browser Fingerprints](client-hints.md) for full documentation.

## TLS overrides
- `ja3` dict: override ciphers/alpn/curves/sig_algs.
- `tls_configuration_options`: accepts `ja3_str`, `akamai_str`, `extra_fp` (`ExtraFingerprints`).

## WebSocket
- `gakido.websocket.WebSocket.connect(host, port, resource, headers, tls, timeout)`
- Methods: `send_text`, `send_bytes`, `recv`, `close`.

## Installation Extras
```bash
pip install gakido          # Core package
pip install gakido[h3]      # With HTTP/3 (QUIC) support
pip install gakido[dev]     # Development dependencies
```
