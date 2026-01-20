#!/usr/bin/env python3
"""
Compression examples for Gakido.

Demonstrates automatic gzip/deflate/brotli decompression with
profile-based Accept-Encoding content negotiation.
"""

from gakido import Client, AsyncClient
import asyncio


def sync_examples():
    """Synchronous compression examples."""
    print("=" * 60)
    print("SYNC CLIENT COMPRESSION EXAMPLES")
    print("=" * 60)

    # Example 1: Default behavior - auto decompression enabled
    print("\n1. Default: Auto-decompression enabled (gzip, deflate, br)")
    print("-" * 50)
    with Client(impersonate="chrome_120") as c:
        # httpbin.org/gzip returns gzip-compressed JSON
        r = c.get("https://httpbin.org/gzip")
        print(f"   URL: https://httpbin.org/gzip")
        print(f"   Status: {r.status_code}")
        print(f"   Content-Encoding: {r.headers.get('content-encoding', 'none')}")
        print(f"   Response: {r.json()}")

    # Example 2: Brotli compression
    print("\n2. Brotli compression")
    print("-" * 50)
    with Client(impersonate="chrome_120") as c:
        # httpbin.org/brotli returns brotli-compressed JSON
        r = c.get("https://httpbin.org/brotli")
        print(f"   URL: https://httpbin.org/brotli")
        print(f"   Status: {r.status_code}")
        print(f"   Content-Encoding: {r.headers.get('content-encoding', 'none')}")
        print(f"   Response: {r.json()}")

    # Example 3: Deflate compression
    print("\n3. Deflate compression")
    print("-" * 50)
    with Client(impersonate="chrome_120") as c:
        r = c.get("https://httpbin.org/deflate")
        print(f"   URL: https://httpbin.org/deflate")
        print(f"   Status: {r.status_code}")
        print(f"   Content-Encoding: {r.headers.get('content-encoding', 'none')}")
        print(f"   Response: {r.json()}")

    # Example 4: Disable auto-decompression
    print("\n4. Disabled: auto_decompress=False")
    print("-" * 50)
    with Client(impersonate="chrome_120", auto_decompress=False) as c:
        r = c.get("https://httpbin.org/get")
        print(f"   URL: https://httpbin.org/get")
        print(f"   Status: {r.status_code}")
        print(f"   Accept-Encoding sent: identity (no compression requested)")
        print(f"   Content-Encoding: {r.headers.get('content-encoding', 'none')}")

    # Example 5: Custom Accept-Encoding header
    print("\n5. Custom Accept-Encoding header override")
    print("-" * 50)
    with Client(impersonate="chrome_120") as c:
        # Request only gzip
        r = c.get(
            "https://httpbin.org/gzip",
            headers={"Accept-Encoding": "gzip"}
        )
        print(f"   URL: https://httpbin.org/gzip")
        print(f"   Custom Accept-Encoding: gzip")
        print(f"   Status: {r.status_code}")
        print(f"   Response auto-decompressed: {r.json()}")

    # Example 6: Different browser profiles have different Accept-Encoding
    print("\n6. Profile-based Accept-Encoding")
    print("-" * 50)
    profiles = ["chrome_120", "firefox_133", "safari_170"]
    for profile in profiles:
        with Client(impersonate=profile) as c:
            r = c.get("https://httpbin.org/headers")
            headers_sent = r.json().get("headers", {})
            accept_enc = headers_sent.get("Accept-Encoding", "not sent")
            print(f"   {profile}: Accept-Encoding = {accept_enc}")


async def async_examples():
    """Asynchronous compression examples."""
    print("\n" + "=" * 60)
    print("ASYNC CLIENT COMPRESSION EXAMPLES")
    print("=" * 60)

    # Example 1: Async with auto-decompression
    print("\n1. Async: Auto-decompression enabled")
    print("-" * 50)
    async with AsyncClient(impersonate="chrome_120") as c:
        r = await c.get("https://httpbin.org/gzip")
        print(f"   URL: https://httpbin.org/gzip")
        print(f"   Status: {r.status_code}")
        print(f"   Response: {r.json()}")

    # Example 2: Async with compression disabled
    print("\n2. Async: Auto-decompression disabled")
    print("-" * 50)
    async with AsyncClient(impersonate="chrome_120", auto_decompress=False) as c:
        r = await c.get("https://httpbin.org/get")
        print(f"   URL: https://httpbin.org/get")
        print(f"   Status: {r.status_code}")
        print(f"   Accept-Encoding: identity")

    # Example 3: Concurrent requests with compression
    print("\n3. Async: Concurrent compressed requests")
    print("-" * 50)
    async with AsyncClient(impersonate="chrome_120") as c:
        urls = [
            "https://httpbin.org/gzip",
            "https://httpbin.org/brotli",
            "https://httpbin.org/deflate",
        ]
        tasks = [c.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)

        for url, r in zip(urls, responses):
            encoding = r.headers.get("content-encoding", "none")
            print(f"   {url.split('/')[-1]}: status={r.status_code}, encoding={encoding}")


def show_compression_info():
    """Show compression configuration info."""
    from gakido.compression import BROTLI_AVAILABLE, DEFAULT_ACCEPT_ENCODING

    print("=" * 60)
    print("COMPRESSION CONFIGURATION")
    print("=" * 60)
    print(f"\nBrotli available: {BROTLI_AVAILABLE}")
    print(f"Default Accept-Encoding: {DEFAULT_ACCEPT_ENCODING}")
    print("\nSupported encodings:")
    print("  - gzip: GNU zip compression")
    print("  - deflate: zlib/deflate compression")
    print("  - br: Brotli compression" + (" ✓" if BROTLI_AVAILABLE else " (not installed)"))


if __name__ == "__main__":
    show_compression_info()
    print()
    sync_examples()
    asyncio.run(async_examples())

    print("\n" + "=" * 60)
    print("All compression examples completed!")
    print("=" * 60)
