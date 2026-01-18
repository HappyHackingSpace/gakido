# Gakido

High-performance CPython HTTP client with browser impersonation, HTTP/2, optional native fast-path, async support, and WebSockets.

## Quick start

```python
from gakido import Client

with Client(impersonate="chrome_120") as c:
    r = c.get("https://example.com")
    print(r.status_code, r.text[:200])
```

## Features

- Browser profiles (Chrome/Firefox/Safari/Edge/Tor aliases)
- JA3/Akamai-like overrides via `tls_configuration_options`
- HTTP/1.1 and HTTP/2 (ALPN) plus optional native HTTP fast-path
- Async client
- Multipart uploads
- Minimal WebSocket client
