import asyncio
from gakido.aio import AsyncClient
from gakido.proxy import ProxyRotator


async def main() -> None:
    proxies = ProxyRotator(
        [
            "http://127.0.0.1:8080",
            "http://127.0.0.1:8888",
        ]
    )
    async with AsyncClient() as c:
        for i in range(3):
            proxy = proxies.next()
            # HTTPS over HTTP proxy (CONNECT) is not implemented; use HTTP target here.
            try:
                r = await c.get("http://httpbin.org/ip", proxy=proxy)
                print(f"req {i} via {proxy}: {r.status_code} {r.text.strip()}")
            except Exception as exc:
                print(f"req {i} via {proxy} failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
