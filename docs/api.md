# API Reference (essentials)

## gakido.Client
- `Client(impersonate="chrome_120", ja3=None, tls_configuration_options=None, proxies=None, timeout=10.0, verify=True, use_native=True, force_http1=True)`
- Methods: `get`, `post`, `request`, `close`, context manager.
- `files` supported on `post`/`request` for multipart.

## gakido.aio.AsyncClient
- `AsyncClient(impersonate="chrome_120", timeout=10.0, verify=True, proxy_pool=None, ja3=None, tls_configuration_options=None, force_http1=True, http3=False, http3_fallback=True)`
- Async context manager; methods `get`, `post`, `request`, `close`.

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
- `impersonate` accepts keys from `gakido.impersonation.PROFILES` (Chrome/Firefox/Safari/Edge/Tor aliases).
- Profiles include HTTP/3 settings (`http3.max_stream_data`, `http3.max_data`, `http3.idle_timeout`).

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
