"""
HTTP/3 (QUIC) support for Gakido.

This module provides HTTP/3 connectivity using aioquic, primarily targeting
Cloudflare and other CDNs that support HTTP/3. HTTP/3 uses QUIC as the
transport layer instead of TCP, providing improved performance through:
- 0-RTT connection establishment
- Multiplexed streams without head-of-line blocking
- Connection migration

Requires the optional `h3` extra: pip install gakido[h3]
"""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from .errors import HTTP3NotAvailableError, ProtocolError
from .models import Response

# Lazy import for optional dependency
_aioquic_available: bool | None = None
if TYPE_CHECKING:
    pass


def is_http3_available() -> bool:
    """Check if HTTP/3 support is available (aioquic installed)."""
    global _aioquic_available
    if _aioquic_available is None:
        try:
            import aioquic  # noqa: F401

            _aioquic_available = True
        except ImportError:
            _aioquic_available = False
    return _aioquic_available


def _get_aioquic() -> dict[str, Any]:
    """Import and return aioquic modules, raising helpful error if unavailable."""
    if not is_http3_available():
        raise HTTP3NotAvailableError(
            "HTTP/3 support requires aioquic. Install with: pip install gakido[h3]"
        )

    from aioquic.asyncio import connect as quic_connect
    from aioquic.asyncio.protocol import QuicConnectionProtocol
    from aioquic.h3.connection import H3Connection
    from aioquic.h3.events import (
        DataReceived,
        HeadersReceived,
    )
    from aioquic.quic.configuration import QuicConfiguration

    return {
        "quic_connect": quic_connect,
        "QuicConnectionProtocol": QuicConnectionProtocol,
        "H3Connection": H3Connection,
        "QuicConfiguration": QuicConfiguration,
        "DataReceived": DataReceived,
        "HeadersReceived": HeadersReceived,
    }


class H3ResponseHandler:
    """Handler for HTTP/3 response events."""

    def __init__(self, stream_id: int):
        self.stream_id = stream_id
        self.status_code = 0
        self.headers: list[tuple[str, str]] = []
        self.body = bytearray()
        self.complete = False
        self._waiter: asyncio.Future | None = None

    def feed_event(self, event: Any, mods: dict[str, Any]) -> None:
        """Process an H3 event."""
        DataReceived = mods["DataReceived"]
        HeadersReceived = mods["HeadersReceived"]

        if isinstance(event, HeadersReceived) and event.stream_id == self.stream_id:
            for name, value in event.headers:
                name_str = name.decode() if isinstance(name, bytes) else name
                value_str = value.decode() if isinstance(value, bytes) else value
                if name_str == ":status":
                    self.status_code = int(value_str)
                elif not name_str.startswith(":"):
                    self.headers.append((name_str, value_str))
            if event.stream_ended:
                self._mark_complete()

        elif isinstance(event, DataReceived) and event.stream_id == self.stream_id:
            self.body.extend(event.data)
            if event.stream_ended:
                self._mark_complete()

    def _mark_complete(self) -> None:
        self.complete = True
        if self._waiter and not self._waiter.done():
            self._waiter.set_result(None)

    async def wait_complete(self, timeout: float) -> None:
        """Wait for response to complete."""
        if self.complete:
            return
        self._waiter = asyncio.get_event_loop().create_future()
        try:
            await asyncio.wait_for(self._waiter, timeout=timeout)
        except TimeoutError:
            raise ProtocolError("HTTP/3 response timeout")


class HTTP3Protocol:
    """
    Async HTTP/3 protocol handler using aioquic.

    This class manages a QUIC connection and provides HTTP/3 request/response
    functionality optimized for Cloudflare and CDN targets.
    """

    def __init__(
        self,
        host: str,
        port: int = 443,
        verify: bool = True,
        timeout: float = 10.0,
        profile: dict | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.verify = verify
        self.timeout = timeout
        self.profile = profile or {}

        self._h3: Any = None
        self._protocol: Any = None
        self._connected = False
        self._mods: dict[str, Any] = {}
        self._handlers: dict[int, H3ResponseHandler] = {}

    async def connect(self) -> None:
        """Establish QUIC connection and initialize HTTP/3."""
        self._mods = _get_aioquic()
        QuicConfiguration = self._mods["QuicConfiguration"]
        quic_connect = self._mods["quic_connect"]
        H3Connection = self._mods["H3Connection"]

        # Configure QUIC with browser-like settings
        config = QuicConfiguration(
            is_client=True,
            alpn_protocols=["h3"],
            verify_mode=ssl.CERT_REQUIRED if self.verify else ssl.CERT_NONE,
        )

        # Apply HTTP/3 profile settings if available
        h3_settings = self.profile.get("http3", {})

        # Set max stream data limits (browser-like values)
        if "max_stream_data" in h3_settings:
            config.max_stream_data = h3_settings["max_stream_data"]
        else:
            config.max_stream_data = 1048576  # 1MB, Chrome-like

        if "max_data" in h3_settings:
            config.max_data = h3_settings["max_data"]
        else:
            config.max_data = 10485760  # 10MB

        # Idle timeout
        if "idle_timeout" in h3_settings:
            config.idle_timeout = h3_settings["idle_timeout"]
        else:
            config.idle_timeout = 30.0

        try:
            async with asyncio.timeout(self.timeout):
                async with quic_connect(
                    self.host,
                    self.port,
                    configuration=config,
                ) as protocol:
                    self._protocol = protocol
                    self._h3 = H3Connection(protocol._quic)
                    self._connected = True
                    # Note: Connection stays open after context manager exits
                    # for connection reuse. Close explicitly with close().
        except TimeoutError as exc:
            raise ProtocolError(f"HTTP/3 connection timeout to {self.host}") from exc
        except Exception as exc:
            raise ProtocolError(f"HTTP/3 connection failed: {exc}") from exc

    async def request(
        self,
        method: str,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None = None,
    ) -> Response:
        """
        Send an HTTP/3 request and return the response.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            headers: Request headers as (name, value) tuples
            body: Optional request body

        Returns:
            Response object with status, headers, and body
        """
        if not self._connected or self._h3 is None or self._protocol is None:
            await self.connect()

        # Build HTTP/3 headers with pseudo-headers first
        h3_headers: list[tuple[bytes, bytes]] = [
            (b":method", method.encode()),
            (b":scheme", b"https"),
            (b":authority", self.host.encode()),
            (b":path", path.encode()),
        ]

        # Add regular headers
        for name, value in headers:
            # Skip pseudo-headers and connection-specific headers
            name_lower = name.lower()
            if name_lower in ("host", "connection", "transfer-encoding"):
                continue
            h3_headers.append((name.encode(), value.encode()))

        # Create a new stream and send headers
        stream_id = self._protocol._quic.get_next_available_stream_id()
        handler = H3ResponseHandler(stream_id)
        self._handlers[stream_id] = handler

        self._h3.send_headers(
            stream_id=stream_id,
            headers=h3_headers,
            end_stream=body is None,
        )

        # Send body if present
        if body:
            self._h3.send_data(
                stream_id=stream_id,
                data=body,
                end_stream=True,
            )

        # Transmit
        self._protocol.transmit()

        # Process incoming events with timeout
        try:
            async with asyncio.timeout(self.timeout):
                while not handler.complete:
                    # Wait for QUIC events
                    await asyncio.sleep(0.01)

                    # Process any H3 events
                    for event in self._h3.handle_events():
                        event_stream = getattr(event, "stream_id", None)
                        if event_stream in self._handlers:
                            self._handlers[event_stream].feed_event(event, self._mods)

                    self._protocol.transmit()

        except TimeoutError as exc:
            del self._handlers[stream_id]
            raise ProtocolError("HTTP/3 response timeout") from exc

        del self._handlers[stream_id]

        if handler.status_code:
            return Response(
                handler.status_code,
                "OK",
                "3",
                handler.headers,
                bytes(handler.body),
            )
        raise ProtocolError("HTTP/3 stream ended without response")

    async def close(self) -> None:
        """Close the QUIC connection."""
        if self._protocol:
            try:
                self._protocol.close()
            except Exception:
                pass
        self._connected = False
        self._h3 = None
        self._protocol = None
        self._handlers.clear()


async def http3_request(
    method: str,
    url: str,
    host: str,
    port: int,
    path: str,
    headers: Iterable[tuple[str, str]],
    body: bytes | None = None,
    verify: bool = True,
    timeout: float = 10.0,
    profile: dict | None = None,
) -> Response:
    """
    Convenience function for single HTTP/3 request.

    For multiple requests to the same host, use HTTP3Protocol directly
    to reuse the QUIC connection.
    """
    proto = HTTP3Protocol(
        host=host,
        port=port,
        verify=verify,
        timeout=timeout,
        profile=profile,
    )
    try:
        await proto.connect()
        return await proto.request(method, path, headers, body)
    finally:
        await proto.close()


def parse_alt_svc(header_value: str) -> dict[str, tuple[str, int]]:
    """
    Parse Alt-Svc header to discover HTTP/3 endpoints.

    Returns a dict mapping protocol to (host, port) tuples.
    Example: {"h3": ("example.com", 443), "h3-29": ("example.com", 443)}
    """
    services: dict[str, tuple[str, int]] = {}

    for entry in header_value.split(","):
        entry = entry.strip()
        if not entry or entry == "clear":
            continue

        # Parse: h3=":443" or h3="alt.example.com:8443"
        try:
            proto, rest = entry.split("=", 1)
            proto = proto.strip()

            # Remove quotes and parse host:port
            rest = rest.strip().strip('"')
            if rest.startswith(":"):
                # Same host, different port
                port = int(rest[1:].split(";")[0])
                services[proto] = ("", port)
            else:
                # Different host and port
                host_port = rest.split(";")[0]
                if ":" in host_port:
                    host, port_str = host_port.rsplit(":", 1)
                    services[proto] = (host, int(port_str))
                else:
                    services[proto] = (host_port, 443)
        except (ValueError, IndexError):
            continue

    return services
