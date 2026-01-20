# User Guide

## Sync client

```python
from gakido import Client

with Client(impersonate="chrome_120") as c:
    r = c.get("https://httpbin.org/get", headers={"Accept-Encoding": "identity"})
    print(r.status_code, r.json())
```

### POST / multipart upload

```python
files = {"file": ("test.txt", b"hello", "text/plain")}
data = {"foo": "bar"}
with Client() as c:
    r = c.post("https://httpbin.org/post", data=data, files=files)
    print(r.json())
```

## Async client

```python
import asyncio
from gakido.aio import AsyncClient

async def main():
    async with AsyncClient(impersonate="chrome_120") as c:
        r = await c.get("https://httpbin.org/get")
        print(r.status_code)

asyncio.run(main())
```

## Profiles & impersonation

```python
from gakido import Client

c = Client(impersonate="firefox_133")
r = c.get("https://tls.browserleaks.com/json")
print(r.json().get("ja3_hash"))
```

## TLS overrides (JA3/Akamai style)

```python
from gakido import Client, ExtraFingerprints

ja3_str = "771,4866-4867-4865-49196,0-11-10,29,0"
extra_fp = ExtraFingerprints(alpn=["http/1.1"])

with Client(
    tls_configuration_options={
        "ja3_str": ja3_str,
        "extra_fp": extra_fp,
    },
    ja3={"alpn": ["http/1.1"]},
) as c:
    r = c.get("https://tls.browserleaks.com/json", headers={"Accept-Encoding": "identity"})
    print(r.json())
```

## WebSocket

```python
from gakido.websocket import WebSocket

ws = WebSocket.connect("echo.websocket.events", 443, "/", headers=[], tls=True)
ws.send_text("hello")
opcode, payload = ws.recv()
print(payload.decode())
ws.close()
```

## HTTP/3 (QUIC)

HTTP/3 uses QUIC as the transport layer, providing improved performance for Cloudflare and CDN targets through 0-RTT connection establishment and multiplexed streams.

### Installation

```bash
pip install gakido[h3]
```

### Basic Usage

```python
import asyncio
from gakido import AsyncClient, is_http3_available

async def main():
    # Check if HTTP/3 is available
    if not is_http3_available():
        print("Install HTTP/3 support: pip install gakido[h3]")
        return

    async with AsyncClient(
        impersonate="chrome_120",
        http3=True,           # Enable HTTP/3
        http3_fallback=True,  # Fall back to H1/H2 if H3 fails
        force_http1=False,    # Allow H2 as fallback
    ) as client:
        response = await client.get("https://cloudflare.com/cdn-cgi/trace")
        print(f"HTTP/{response.http_version}: {response.status_code}")
        print(response.text)

asyncio.run(main())
```

### Force HTTP/3 for Specific Requests

```python
async with AsyncClient(http3=True) as client:
    # Use client default (HTTP/3 with fallback)
    r1 = await client.get("https://example.com")

    # Force HTTP/3 for this specific request (no fallback)
    r2 = await client.request("GET", "https://cloudflare.com", force_http3=True)
```

### HTTP/3 Benefits

- **0-RTT Connection**: Faster initial requests with QUIC's zero round-trip handshake
- **No Head-of-Line Blocking**: Multiplexed streams don't block each other
- **Connection Migration**: Survives network changes (WiFi to cellular)
- **Built-in Encryption**: TLS 1.3 integrated into the protocol
