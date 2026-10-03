## Gakido

High-performance CPython HTTP client focused on browser impersonation, anti-bot evasion, and speed.

### Features
- Browser profiles (Chrome/Firefox/Safari/Edge/Tor aliases)
- **Native TLS backend (Go + uTLS)** for byte-accurate browser JA3/JA4 ClientHello and HTTP/2 fingerprints — the pure-Python `ssl` path cannot reproduce these
- JA3/Akamai-style TLS overrides (`tls_configuration_options`, `ExtraFingerprints`)
- HTTP/1.1, HTTP/2, and **HTTP/3 (QUIC)** support
- HTTP/3 optimized for Cloudflare and CDN targets
- **Automatic compression** (gzip, deflate, brotli) with profile-based Accept-Encoding
- Sync + async clients, connection pooling
- Multipart uploads
- Minimal WebSocket client
- **96 browser profiles** (24 base + 72 aliases) for Chrome, Firefox, Safari, Edge, Opera, Brave, Vivaldi, Tor
- [Antibot benchmark](docs/antibot-benchmark.md) for testing impersonation against detection systems

### Install

**pip:**
```bash
pip install gakido
pip install gakido[h3]     # with HTTP/3 support
pip install gakido[dev]    # development dependencies
```

**uv:**
```bash
uv add gakido
uv add gakido[h3]          # with HTTP/3 support
uv add gakido[dev]         # development dependencies
```

### Quick start (sync)
```python
from gakido import Client

c = Client(impersonate="chrome_120")  # force_http1 defaults to False (ALPN negotiates h2)
r = c.get("https://example.com")
print(r.status_code, r.text[:200])
```

### Async
```python
import asyncio
from gakido.aio import AsyncClient

async def main():
    async with AsyncClient(impersonate="chrome_120") as c:
        r = await c.get("https://httpbin.org/get")
        print(r.status_code)

asyncio.run(main())
```

### Multipart upload
```python
files = {"file": ("test.txt", b"hello", "text/plain")}
data = {"foo": "bar"}
with Client() as c:
    r = c.post("https://httpbin.org/post", data=data, files=files)
    print(r.json())
```

### TLS overrides (JA3-like)
```python
from gakido import Client, ExtraFingerprints

ja3_str = "771,4866-4867-4865-49196,0-11-10,29,0"
extra_fp = ExtraFingerprints(alpn=["http/1.1"])

c = Client(
    impersonate="chrome_120",
    tls_configuration_options={"ja3_str": ja3_str, "extra_fp": extra_fp},
)
r = c.get("https://tls.browserleaks.com/json")
print(r.json().get("ja3_hash"))
```

### Native TLS backend (browser-accurate JA3/JA4)

Python's stdlib `ssl` cannot reproduce a browser's TLS ClientHello, so on the
pure-Python path JA3/JA4 look like Python-OpenSSL and are easily flagged. The
optional native backend (Go + [uTLS](https://github.com/refraction-networking/utls),
via [tls-client](https://github.com/bogdanfinn/tls-client)) produces a
byte-accurate ClientHello **and** HTTP/2 fingerprint for the impersonated
profile.

The Linux (x86_64) and macOS (arm64/x86_64) wheels on PyPI ship the native
library prebuilt, so `pip install gakido` enables it automatically there. On
other platforms (e.g. Windows), or from the source distribution, build it once
yourself (requires Go):

```bash
make -C native build        # outputs gakido/_native/libgakido_tls.{dylib,so,dll}
```

Then it is used automatically:

```python
from gakido import Client

# tls_backend="auto" (default): native when built, else pure-Python fallback.
c = Client(impersonate="chrome_120")              # auto
c = Client(impersonate="chrome_120", tls_backend="native")   # require native
c = Client(impersonate="chrome_120", tls_backend="stdlib")   # force pure-Python

r = c.get("https://tls.peet.ws/api/all")
print(r.json()["tls"]["ja4"])                     # matches real Chrome
```

Same request, same `User-Agent` — only the TLS/HTTP2 fingerprint differs
(`tls.peet.ws`, `chrome_120`):

| Client | JA4 (TLS) | Looks like Chrome? |
| --- | --- | --- |
| `requests` / `httpx` | `t13d1812h1_…` | ✗ OpenSSL, HTTP/1.1 |
| gakido `tls_backend="stdlib"` | `t13d3112h2_…` | ✗ HTTP/2 ok, TLS still OpenSSL |
| **gakido (native)** | **`t13d1516h2_8daaf6152771_02713d6af862`** | ✓ identical to real Chrome 120 |

Full methodology and HTTP/2 (Akamai) results: [benchmark](docs/antibot-benchmark.md).

> Matching the fingerprint defeats TLS/HTTP-fingerprint–based blocking. It does
> **not** solve JavaScript challenges (Cloudflare managed challenge, Turnstile) —
> those need a real browser.

The backend is optional: when the library is neither bundled nor built,
`tls_backend="auto"` transparently falls back to the pure-Python path.

### WebSocket
```python
from gakido.websocket import WebSocket

ws = WebSocket.connect("echo.websocket.events", 443, "/", headers=[], tls=True)
ws.send_text("hello")
op, payload = ws.recv()
print(payload.decode(errors="ignore"))
ws.close()
```

### Proxies

gakido supports HTTP, SOCKS5, and SOCKS5H proxies for both sync and async clients.

```python
from gakido import Client, AsyncClient

# Sync client with HTTP or SOCKS5 proxy
c = Client()
r = c.get("http://httpbin.org/ip", proxy="http://127.0.0.1:8080")
r = c.get("http://httpbin.org/ip", proxy="socks5://127.0.0.1:1080")
r = c.get("http://httpbin.org/ip", proxy="socks5h://user:pass@127.0.0.1:1080")  # proxy resolves hostname
print(r.text)

# Async client with proxy pool
async_client = AsyncClient(proxy_pool=[
    "http://proxy1:8080",
    "socks5://proxy2:1080",
    "socks5h://user:pass@proxy3:1080",
])
r = await async_client.get("http://httpbin.org/ip")
print(r.text)
```

### Retry with Exponential Backoff

gakido supports configurable retry with exponential backoff for both sync and async clients.

```python
from gakido import Client, AsyncClient
import time

# Sync client with retry
client = Client(
    max_retries=3,           # Up to 3 retry attempts (4 total attempts)
    retry_base_delay=0.5,    # Start with 0.5s delay
    retry_max_delay=30.0,    # Cap delay at 30s
    retry_jitter=True,       # Add random jitter to avoid thundering herd
)
try:
    resp = client.get("http://flaky.example.com")
except Exception as e:
    print(f"Failed after retries: {e}")

# Async client with retry
async_client = AsyncClient(
    max_retries=2,
    retry_base_delay=1.0,
    retry_jitter=False,  # Predictable delays for testing
)
resp = await async_client.get("http://api.example.com")

# Retryable status codes (by default): 408, 429, 500, 502, 503, 504, 507, 511
# Retryable exceptions (by default): ConnectionError, TimeoutError, OSError

See [Retry Documentation](docs/retry.md) for detailed information about retry options and best practices.
```

### HTTP/3 (QUIC) for Cloudflare/CDN
```python
import asyncio
from gakido import AsyncClient, is_http3_available

async def main():
    print(f"HTTP/3 available: {is_http3_available()}")

    async with AsyncClient(
        impersonate="chrome_120",
        http3=True,           # Enable HTTP/3
        http3_fallback=True,  # Fall back to H1/H2 if H3 fails
    ) as c:
        r = await c.get("https://cloudflare.com/cdn-cgi/trace")
        print(f"HTTP/{r.http_version}: {r.status_code}")

asyncio.run(main())
```

### Notes
- `force_http1=False` by default, so ALPN negotiates HTTP/2 like a real browser; set `force_http1=True` to restrict to HTTP/1.1. The HTTP/2 SETTINGS, connection-level WINDOW_UPDATE and pseudo-header order are driven by the impersonated profile to match the browser's "Akamai" fingerprint.
- `http3=True` enables HTTP/3 (QUIC) for compatible targets (requires `pip install gakido[h3]`).
- `auto_decompress=True` by default: uses profile's Accept-Encoding (gzip, deflate, br) and auto-decompresses responses.
- Set `auto_decompress=False` to disable compression and receive raw responses.
- The native TLS backend (`tls_backend="auto"`) handles HTTPS; plaintext `http://` uses the pure-Python connection path.
