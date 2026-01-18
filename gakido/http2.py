from __future__ import annotations

import ssl
from collections.abc import Iterable

import h2.connection
import h2.events

from .errors import ProtocolError
from .models import Response


class HTTP2Connection:
    """
    Minimal single-stream HTTP/2 client over an existing TLS socket.
    """

    def __init__(self, sock: ssl.SSLSocket):
        self.sock = sock
        self.conn = h2.connection.H2Connection()
        self.conn.initiate_connection()
        self._send(self.conn.data_to_send())

    def request(
        self,
        method: str,
        authority: str,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None = None,
    ) -> Response:
        stream_id = self.conn.get_next_available_stream_id()
        pseudo_headers = [
            (":method", method),
            (":authority", authority),
            (":scheme", "https"),
            (":path", path),
        ]
        request_headers = pseudo_headers + list(headers)
        self.conn.send_headers(stream_id, request_headers, end_stream=body is None)
        if body:
            self.conn.send_data(stream_id, body, end_stream=True)
        self._send(self.conn.data_to_send())

        resp_headers: list[tuple[str, str]] = []
        resp_body = bytearray()
        status = 0
        reason = ""

        while True:
            data = self.sock.recv(65536)
            if not data:
                # Graceful close; return what we have if anything was received.
                if status or resp_body or resp_headers:
                    return Response(
                        status or 0, reason or "", "2", resp_headers, bytes(resp_body)
                    )
                break
            events = self.conn.receive_data(data)
            self._send(self.conn.data_to_send())
            for event in events:
                if isinstance(event, h2.events.ResponseReceived):
                    status = int(event.headers[0][1]) if event.headers else 0
                    resp_headers.extend(
                        (
                            name.decode() if isinstance(name, bytes) else name,
                            value.decode() if isinstance(value, bytes) else value,
                        )
                        for name, value in event.headers
                        if not name.startswith(b":")
                    )
                elif isinstance(event, h2.events.DataReceived):
                    resp_body.extend(event.data)
                    self.conn.acknowledge_received_data(
                        event.flow_controlled_length, stream_id
                    )
                elif isinstance(event, h2.events.StreamEnded):
                    reason = "OK"
                    return Response(status, reason, "2", resp_headers, bytes(resp_body))
                elif isinstance(event, h2.events.StreamReset):
                    raise ProtocolError(f"Stream reset: {event.error_code}")
        raise ProtocolError("Connection closed before stream ended")

    def _send(self, data: bytes) -> None:
        if not data:
            return
        self.sock.sendall(data)
