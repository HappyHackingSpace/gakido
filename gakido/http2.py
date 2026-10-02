from __future__ import annotations

import ssl
from collections.abc import Iterable

import h2.config
import h2.connection
import h2.events
from h2.settings import SettingCodes, Settings

from .errors import ProtocolError
from .models import Response

# Map the string setting names used in browser profiles to h2's SettingCodes.
_SETTING_NAME_TO_CODE: dict[str, SettingCodes] = {
    "HEADER_TABLE_SIZE": SettingCodes.HEADER_TABLE_SIZE,
    "ENABLE_PUSH": SettingCodes.ENABLE_PUSH,
    "MAX_CONCURRENT_STREAMS": SettingCodes.MAX_CONCURRENT_STREAMS,
    "INITIAL_WINDOW_SIZE": SettingCodes.INITIAL_WINDOW_SIZE,
    "MAX_FRAME_SIZE": SettingCodes.MAX_FRAME_SIZE,
    "MAX_HEADER_LIST_SIZE": SettingCodes.MAX_HEADER_LIST_SIZE,
}

# Fallback pseudo-header order if the profile does not declare one.
_DEFAULT_PSEUDO_ORDER: tuple[str, ...] = (":method", ":authority", ":scheme", ":path")


def apply_profile_settings(conn: h2.connection.H2Connection, profile: dict) -> None:
    """
    Apply a browser profile's HTTP/2 SETTINGS onto an h2 connection.

    Must be called *before* ``initiate_connection()``. We replace the whole
    ``local_settings`` object with one built from ``initial_values`` because
    per-key assignment on the existing object only stages a *pending* change
    (sent in a later SETTINGS update) and leaves the initial SETTINGS frame at
    h2's defaults.
    """
    h2opts = (profile or {}).get("http2", {}) or {}
    initial_values: dict[SettingCodes, int] = {}
    for name, value in (h2opts.get("settings") or {}).items():
        code = _SETTING_NAME_TO_CODE.get(name)
        if code is not None:
            try:
                initial_values[code] = int(value)
            except (ValueError, TypeError):
                pass
    if initial_values:
        conn.local_settings = Settings(client=True, initial_values=initial_values)


def profile_window_increment(profile: dict) -> int | None:
    """Return the connection-level WINDOW_UPDATE increment, if the profile sets one."""
    increment = ((profile or {}).get("http2", {}) or {}).get("window_update_increment")
    if not increment:
        return None
    try:
        return int(increment)
    except (ValueError, TypeError):
        return None


def order_pseudo_headers(
    profile: dict, method: str, authority: str, path: str
) -> list[tuple[str, str]]:
    """Build the :pseudo headers in the profile's declared order."""
    order = tuple(
        ((profile or {}).get("http2", {}) or {}).get("pseudo_header_order")
        or _DEFAULT_PSEUDO_ORDER
    )
    pseudo_values = {
        ":method": method,
        ":authority": authority,
        ":scheme": "https",
        ":path": path,
    }
    ordered: list[tuple[str, str]] = []
    for name in order:
        if name in pseudo_values:
            ordered.append((name, pseudo_values[name]))
    for name, value in pseudo_values.items():
        if name not in order:
            ordered.append((name, value))
    return ordered


class HTTP2Connection:
    """
    Minimal HTTP/2 client over an existing TLS socket.

    The initial SETTINGS frame, the connection-level WINDOW_UPDATE, and the
    pseudo-header order are driven by the impersonated browser profile so the
    HTTP/2 ("Akamai") fingerprint matches the profile rather than h2's library
    defaults. A single instance is reused for multiple sequential streams, so
    the connection preface is sent exactly once.
    """

    def __init__(self, sock: ssl.SSLSocket, profile: dict | None = None):
        self.sock = sock
        self.profile = profile or {}

        config = h2.config.H2Configuration(client_side=True)
        self.conn = h2.connection.H2Connection(config=config)

        # Apply the browser's SETTINGS values *before* initiating the connection
        # so they ride in the initial SETTINGS frame (h2 builds that frame from
        # local_settings).
        apply_profile_settings(self.conn, self.profile)

        self.conn.initiate_connection()
        self._send(self.conn.data_to_send())

        # Real browsers immediately enlarge the connection-level flow-control
        # window with a WINDOW_UPDATE on stream 0 (e.g. Chrome sends 15663105).
        increment = profile_window_increment(self.profile)
        if increment:
            try:
                # stream_id=None targets the connection-level flow-control
                # window (WINDOW_UPDATE on stream 0).
                self.conn.increment_flow_control_window(increment)
                self._send(self.conn.data_to_send())
            except (ValueError, TypeError):
                pass

    def _build_request_headers(
        self,
        method: str,
        authority: str,
        path: str,
        headers: Iterable[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        """Order pseudo-headers per the profile, then append regular headers."""
        ordered = order_pseudo_headers(self.profile, method, authority, path)
        ordered.extend(headers)
        return ordered

    def request(
        self,
        method: str,
        authority: str,
        path: str,
        headers: Iterable[tuple[str, str]],
        body: bytes | None = None,
    ) -> Response:
        stream_id = self.conn.get_next_available_stream_id()
        request_headers = self._build_request_headers(
            method, authority, path, headers
        )
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
