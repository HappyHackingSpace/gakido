#!/usr/bin/env python3
"""
Example: Using SOCKS5 proxy with gakido (sync and async).

Requires a running SOCKS5 proxy at localhost:1080.
You can start one with:
  ssh -D 1080 localhost
or use tools like Dante, ss-local, etc.
"""

import asyncio
from gakido import Client, AsyncClient

def sync_example():
    print("=== Sync SOCKS5 example ===")
    client = Client()
    try:
        # Use SOCKS5 proxy (client resolves hostname)
        resp = client.get("http://httpbin.org/ip", proxy="socks5://127.0.0.1:1080")
        print("Response via socks5://:", resp.json())

        # Use SOCKS5h proxy (proxy resolves hostname)
        resp = client.get("http://httpbin.org/ip", proxy="socks5h://127.0.0.1:1080")
        print("Response via socks5h://:", resp.json())
    except Exception as e:
        print("Sync error:", e)

async def async_example():
    print("\n=== Async SOCKS5 example ===")
    client = AsyncClient()
    try:
        # Use SOCKS5 proxy with optional username/password
        resp = await client.get("http://httpbin.org/ip", proxy="socks5://user:pass@127.0.0.1:1080")
        print("Response via socks5:// with auth:", resp.json())
    except Exception as e:
        print("Async error:", e)

if __name__ == "__main__":
    sync_example()
    asyncio.run(async_example())
