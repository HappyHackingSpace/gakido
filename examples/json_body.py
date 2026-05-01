"""
Example: Auto-serialize JSON request body (like httpx/requests)

The `json=` parameter automatically:
- Serializes the object to JSON
- Sets Content-Type: application/json
"""

import asyncio
from gakido import Client, AsyncClient


def sync_example():
    """Synchronous JSON POST example."""
    with Client() as client:
        # Using json= parameter (auto-serializes and sets Content-Type)
        response = client.post(
            "https://httpbin.org/post",
            json={"name": "gakido", "version": "1.0", "features": ["fast", "simple"]},
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        # Also works with request() method
        response = client.request(
            "PUT",
            "https://httpbin.org/put",
            json={"action": "update", "id": 123},
        )
        print(f"\nPUT Status: {response.status_code}")


async def async_example():
    """Asynchronous JSON POST example."""
    async with AsyncClient() as client:
        # Using json= parameter
        response = await client.post(
            "https://httpbin.org/post",
            json={"async": True, "data": [1, 2, 3]},
        )
        print(f"\nAsync Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")


if __name__ == "__main__":
    print("=== Sync Example ===")
    sync_example()

    print("\n=== Async Example ===")
    asyncio.run(async_example())
