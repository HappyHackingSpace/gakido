# API Reference (essentials)

## gakido.Client
- `Client(impersonate="chrome_120", ja3=None, tls_configuration_options=None, proxies=None, timeout=10.0, verify=True, use_native=True)`
- Methods: `get`, `post`, `request`, `close`, context manager.
- `files` supported on `post`/`request` for multipart.

## gakido.aio.AsyncClient
- Same parameters as `Client`.
- Async context manager; methods `get`, `post`, `request`.

## Profiles
- `impersonate` accepts keys from `gakido.impersonation.PROFILES` (Chrome/Firefox/Safari/Edge/Tor aliases).

## TLS overrides
- `ja3` dict: override ciphers/alpn/curves/sig_algs.
- `tls_configuration_options`: accepts `ja3_str`, `akamai_str`, `extra_fp` (`ExtraFingerprints`).

## WebSocket
- `gakido.websocket.WebSocket.connect(host, port, resource, headers, tls, timeout)`
- Methods: `send_text`, `send_bytes`, `recv`, `close`.
