import asyncio
import click
from gakido.aio import AsyncClient


async def main() -> None:
    files = {"file": ("hello.txt", b"hello async", "text/plain")}
    data = {"foo": "bar"}

    # Async client upload
    async with AsyncClient(impersonate="chrome_120") as c:
        r = await c.post("https://httpbin.org/post", data=data, files=files)
        click.secho(f"AsyncClient upload status: {r.status_code}", fg="green")

    async with AsyncClient() as s:
        r1 = await s.post(
            "https://httpbin.org/post",
            data={"a": "1"},
            files={"f": ("a.txt", b"a", "text/plain")})
        r2 = await s.post(
            "https://httpbin.org/post",
            data={"b": "2"},
            files={"f": ("b.txt", b"b", "text/plain")})
        print("Session-like reuse statuses:", r1.status_code, r2.status_code)


if __name__ == "__main__":
    asyncio.run(main())
