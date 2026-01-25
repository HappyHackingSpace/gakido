"""
Async WebSocket echo example using the AsyncWebSocket client.
"""

import asyncio

from gakido import AsyncWebSocket


async def main() -> None:
    """Connect to echo server and send/receive messages."""
    host = "ws.postman-echo.com"

    async with await AsyncWebSocket.connect(
        host=host,
        port=443,
        resource="/raw",
        headers=[("Origin", f"https://{host}")],
        tls=True,
        timeout=10.0,
    ) as ws:
        # Send text message
        await ws.send_text("hello async websocket")

        # Receive response
        opcode, payload = await ws.recv()
        print(f"Received: opcode={opcode}, payload={payload.decode()}")

        # Send binary message
        await ws.send_bytes(b"binary data")

        # Receive binary response
        opcode, payload = await ws.recv()
        print(f"Received: opcode={opcode}, payload={payload}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"WebSocket error: {exc}")
