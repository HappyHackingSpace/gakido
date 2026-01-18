# Gakido HTTP Client

Performance-first CPython HTTP client with browser impersonation profiles.

## Quick start

```python
from gakido import Client

client = Client(impersonate="chrome_120")
resp = client.get("https://example.com")
print(resp.status_code)
print(resp.text[:200])
```

## Profiles

- `chrome_120`
- `firefox_120`

Each profile defines TLS ciphers, ALPN order, HTTP/2 settings (reserved),
default header values, and deterministic header ordering.

## Notes

- HTTP/1.1 is implemented. HTTP/2 negotiation will raise until the transport is
  completed.
- Deterministic header order is maintained, and TLS parameters follow the
  selected impersonation profile.
- A CPython extension `_gakido_native` provides a fast-path for HTTP/1.1 over
  TCP (no TLS yet). If the extension is not built or the request is HTTPS, the
  pure-Python path is used.
- HTTP/2 is supported via ALPN+h2 framing (single-stream). HTTP/3 is not yet
  implemented. WebSockets are supported with a minimal RFC6455 client.
- Async support is available via `gakido.aio.AsyncClient`. Per-request proxy
  selection is supported; basic rotation helper in `gakido.proxy.ProxyRotator`.
