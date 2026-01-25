#!/usr/bin/env python3
"""
Example: Streaming large responses without loading entire body into memory.

This demonstrates how to use gakido's streaming API to efficiently handle
large downloads, chunked responses, and line-by-line processing.
"""
from __future__ import annotations

import asyncio
import sys

from gakido import Client, AsyncClient


def sync_streaming_bytes():
    """Stream a large file and process it chunk by chunk."""
    print("=== Sync Streaming (bytes) ===")

    client = Client()
    url = "https://httpbin.org/stream-bytes/50000"  # 50KB of random bytes

    with client.stream("GET", url) as response:
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(list(response.headers.items())[:3])}...")

        total_bytes = 0
        chunk_count = 0

        for chunk in response.iter_bytes(chunk_size=8192):
            total_bytes += len(chunk)
            chunk_count += 1
            # Process chunk here (e.g., write to file, hash, etc.)

        print(f"Received {total_bytes} bytes in {chunk_count} chunks")


def sync_streaming_lines():
    """Stream a response and process it line by line."""
    print("\n=== Sync Streaming (lines) ===")

    client = Client()
    url = "https://httpbin.org/stream/5"  # 5 JSON lines

    with client.stream("GET", url) as response:
        print(f"Status: {response.status_code}")

        for i, line in enumerate(response.iter_lines()):
            print(f"  Line {i}: {line[:60]}...")


def sync_download_to_file():
    """Stream download directly to a file without loading into memory."""
    print("\n=== Sync Download to File ===")

    import tempfile
    import os

    client = Client()
    url = "https://httpbin.org/bytes/100000"  # 100KB

    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = f.name

        with client.stream("GET", url) as response:
            for chunk in response.iter_bytes(chunk_size=16384):
                f.write(chunk)

        file_size = os.path.getsize(temp_path)
        print(f"Downloaded {file_size} bytes to {temp_path}")
        os.unlink(temp_path)


async def async_streaming_bytes():
    """Async stream a large file and process it chunk by chunk."""
    print("\n=== Async Streaming (bytes) ===")

    client = AsyncClient()
    url = "https://httpbin.org/stream-bytes/50000"

    async with await client.stream("GET", url) as response:
        print(f"Status: {response.status_code}")

        total_bytes = 0
        chunk_count = 0

        async for chunk in response.aiter_bytes(chunk_size=8192):
            total_bytes += len(chunk)
            chunk_count += 1

        print(f"Received {total_bytes} bytes in {chunk_count} chunks")


async def async_streaming_lines():
    """Async stream a response and process it line by line."""
    print("\n=== Async Streaming (lines) ===")

    client = AsyncClient()
    url = "https://httpbin.org/stream/5"

    async with await client.stream("GET", url) as response:
        print(f"Status: {response.status_code}")

        i = 0
        async for line in response.aiter_lines():
            print(f"  Line {i}: {line[:60]}...")
            i += 1


async def async_concurrent_streams():
    """Download multiple streams concurrently."""
    print("\n=== Async Concurrent Streams ===")

    async def download_stream(client: AsyncClient, url: str, name: str) -> int:
        total = 0
        async with await client.stream("GET", url) as response:
            async for chunk in response.aiter_bytes():
                total += len(chunk)
        return total

    client = AsyncClient()
    urls = [
        ("https://httpbin.org/bytes/100000", "stream1"),
        ("https://httpbin.org/bytes/200000", "stream2"),
        ("https://httpbin.org/bytes/300000", "stream3"),
    ]

    tasks = [download_stream(client, url, name) for url, name in urls]
    results = await asyncio.gather(*tasks)

    for (url, name), size in zip(urls, results):
        print(f"  {name}: {size} bytes")

    print(f"  Total: {sum(results)} bytes")


def main():
    """Run all streaming examples."""
    print("Gakido Streaming Examples")
    print("=" * 50)

    # Sync examples
    sync_streaming_bytes()
    sync_streaming_lines()
    sync_download_to_file()

    # Async examples
    asyncio.run(async_streaming_bytes())
    asyncio.run(async_streaming_lines())
    asyncio.run(async_concurrent_streams())

    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    main()
