#!/usr/bin/env python3
"""
HTTP/3 (QUIC) example for Cloudflare and CDN targets.

This example demonstrates how to use gakido's HTTP/3 support for improved
performance when connecting to Cloudflare-protected sites and other CDNs
that support HTTP/3.

Requirements:
    pip install gakido[h3]

HTTP/3 Benefits:
- 0-RTT connection establishment (faster initial requests)
- No head-of-line blocking (multiplexed streams)
- Connection migration (survives network changes)
- Built-in encryption with TLS 1.3
"""
import asyncio

from gakido import AsyncClient, is_http3_available


async def main():
    # Check if HTTP/3 is available
    if not is_http3_available():
        print("HTTP/3 not available. Install with: pip install gakido[h3]")
        print("Falling back to HTTP/1.1 or HTTP/2...")

    # Create client with HTTP/3 enabled
    # - http3=True enables HTTP/3 for compatible targets
    # - http3_fallback=True automatically falls back to HTTP/1.1/2 if H3 fails
    # - force_http1=False allows HTTP/2 as an alternative
    async with AsyncClient(
        impersonate="chrome_120",
        http3=True,
        http3_fallback=True,
        force_http1=False,
        timeout=15.0,
    ) as client:
        # Test against Cloudflare's HTTP/3 test endpoint
        print("Testing HTTP/3 connection to Cloudflare...")
        try:
            response = await client.get("https://cloudflare.com/cdn-cgi/trace")
            print(f"Status: {response.status_code}")
            print(f"HTTP Version: {response.http_version}")
            print(f"Body preview:\n{response.text[:500]}")

            # Check if we actually used HTTP/3
            if response.http_version == "3":
                print("\n✓ Successfully connected via HTTP/3 (QUIC)!")
            else:
                print(f"\n→ Connected via HTTP/{response.http_version}")
        except Exception as e:
            print(f"Request failed: {e}")

        # Example: Force HTTP/3 for a specific request
        print("\n--- Forcing HTTP/3 for specific request ---")
        try:
            response = await client.request(
                "GET",
                "https://www.cloudflare.com/",
                force_http3=True,  # Force H3 for this request only
            )
            print(f"Status: {response.status_code}, HTTP/{response.http_version}")
        except Exception as e:
            print(f"HTTP/3 request failed (expected if not supported): {e}")

if __name__ == "__main__":
    asyncio.run(main())
