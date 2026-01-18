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
