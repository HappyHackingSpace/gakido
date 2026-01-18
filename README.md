## Gakido

High-performance CPython HTTP client focused on browser impersonation, anti-bot evasion, and speed.

### Features
- Browser profiles (Chrome/Firefox/Safari/Edge/Tor aliases)
- JA3/Akamai-style TLS overrides (`tls_configuration_options`, `ExtraFingerprints`)
- HTTP/1.1 and HTTP/2 (HTTP/1.1 forced by default; enable h2 via `force_http1=False`)
- Sync + async clients, connection pooling
- Multipart uploads
- Minimal WebSocket client
- Optional native HTTP fast-path (`gakido_core`, HTTP only)

### Install
```bash
uv pip install -e .
uv pip install -e .[dev]   # if you add a dev extra later
```
Build native fast-path in place:
```bash
uv run python setup.py build_ext --inplace
```

### Quick start (sync)
```python
from gakido import Client

c = Client(impersonate="chrome_120")  # force_http1 defaults to True
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
```python
from gakido import Client

c = Client(proxies=["http://127.0.0.1:8080"])
r = c.get("http://httpbin.org/ip")  # HTTP proxy only
print(r.text)
```

### Notes
- `force_http1=True` by default for compatibility; set `force_http1=False` to allow ALPN h2.
- `Accept-Encoding: identity` is sent by default to avoid compressed bodies; override if needed.
- Native core (`gakido_core`) is HTTP-only; HTTPS still uses the Python path.
