"""Tests for gakido.http2 module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import ssl

from gakido.http2 import HTTP2Connection
from gakido.models import Response
from gakido.errors import ProtocolError


class TestHTTP2ConnectionInit:
    """Tests for HTTP2Connection initialization."""

    @patch('gakido.http2.h2.connection.H2Connection')
    def test_init_initiates_connection(self, mock_h2_conn_class):
        """Test HTTP2Connection initiates h2 connection."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b"preface"
        mock_h2_conn_class.return_value = mock_h2_conn

        h2 = HTTP2Connection(mock_sock)

        mock_h2_conn.initiate_connection.assert_called_once()
        mock_sock.sendall.assert_called_once_with(b"preface")

    @patch('gakido.http2.h2.connection.H2Connection')
    def test_init_stores_socket(self, mock_h2_conn_class):
        """Test HTTP2Connection stores socket reference."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn_class.return_value = mock_h2_conn

        h2 = HTTP2Connection(mock_sock)

        assert h2.sock is mock_sock


class TestHTTP2ConnectionRequest:
    """Tests for HTTP2Connection.request method."""

    @patch('gakido.http2.h2.events')
    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_get(self, mock_h2_conn_class, mock_events):
        """Test HTTP2 GET request."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        # Mock response events
        mock_response_received = MagicMock()
        mock_response_received.headers = [(b":status", b"200")]
        mock_data_received = MagicMock()
        mock_data_received.data = b"response body"
        mock_data_received.flow_controlled_length = 13
        mock_stream_ended = MagicMock()

        # Configure isinstance checks
        mock_events.ResponseReceived = type(mock_response_received)
        mock_events.DataReceived = type(mock_data_received)
        mock_events.StreamEnded = type(mock_stream_ended)

        # First recv returns response data, second returns empty (connection close)
        mock_sock.recv.side_effect = [b"h2data", b""]
        mock_h2_conn.receive_data.return_value = [
            mock_response_received,
            mock_data_received,
            mock_stream_ended,
        ]

        h2 = HTTP2Connection(mock_sock)
        response = h2.request("GET", "example.com", "/path", [("accept", "*/*")])

        assert response.status_code == 200

    @patch('gakido.http2.h2.events')
    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_post_with_body(self, mock_h2_conn_class, mock_events):
        """Test HTTP2 POST request with body."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        # Mock response events
        mock_response_received = MagicMock()
        mock_response_received.headers = [(b":status", b"201")]
        mock_stream_ended = MagicMock()

        mock_events.ResponseReceived = type(mock_response_received)
        mock_events.DataReceived = MagicMock
        mock_events.StreamEnded = type(mock_stream_ended)
        mock_events.StreamReset = MagicMock

        mock_sock.recv.side_effect = [b"h2data", b""]
        mock_h2_conn.receive_data.return_value = [
            mock_response_received,
            mock_stream_ended,
        ]

        h2 = HTTP2Connection(mock_sock)
        response = h2.request(
            "POST",
            "example.com",
            "/submit",
            [("content-type", "application/json")],
            body=b'{"data": "value"}',
        )

        # Verify send_data was called with body
        mock_h2_conn.send_data.assert_called_once_with(1, b'{"data": "value"}', end_stream=True)

    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_stream_reset_raises(self, mock_h2_conn_class):
        """Test HTTP2 stream reset raises ProtocolError."""
        import h2.events

        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        # Create a real StreamReset event mock
        mock_stream_reset = MagicMock(spec=h2.events.StreamReset)
        mock_stream_reset.error_code = 2

        mock_sock.recv.side_effect = [b"h2data", b""]
        mock_h2_conn.receive_data.return_value = [mock_stream_reset]

        h2 = HTTP2Connection(mock_sock)

        with pytest.raises(ProtocolError, match="Stream reset"):
            h2.request("GET", "example.com", "/path", [])

    @patch('gakido.http2.h2.events')
    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_graceful_close_returns_partial(self, mock_h2_conn_class, mock_events):
        """Test graceful close returns partial response if data received."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        # Mock response received event
        mock_response_received = MagicMock()
        mock_response_received.headers = [(b":status", b"200")]

        mock_events.ResponseReceived = type(mock_response_received)
        mock_events.DataReceived = MagicMock
        mock_events.StreamEnded = MagicMock
        mock_events.StreamReset = MagicMock

        # Receive response then connection closes
        mock_sock.recv.side_effect = [b"h2data", b""]
        mock_h2_conn.receive_data.return_value = [mock_response_received]

        h2 = HTTP2Connection(mock_sock)
        response = h2.request("GET", "example.com", "/path", [])

        # Should return partial response
        assert response.status_code == 200

    @patch('gakido.http2.h2.events')
    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_connection_closed_without_response_raises(self, mock_h2_conn_class, mock_events):
        """Test connection close without any response raises ProtocolError."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        mock_events.ResponseReceived = MagicMock
        mock_events.DataReceived = MagicMock
        mock_events.StreamEnded = MagicMock
        mock_events.StreamReset = MagicMock

        # Immediately close connection
        mock_sock.recv.return_value = b""
        mock_h2_conn.receive_data.return_value = []

        h2 = HTTP2Connection(mock_sock)

        with pytest.raises(ProtocolError, match="Connection closed before stream ended"):
            h2.request("GET", "example.com", "/path", [])


class TestHTTP2ConnectionSend:
    """Tests for HTTP2Connection._send method."""

    @patch('gakido.http2.h2.connection.H2Connection')
    def test_send_empty_data_skipped(self, mock_h2_conn_class):
        """Test _send with empty data does nothing."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn_class.return_value = mock_h2_conn

        h2 = HTTP2Connection(mock_sock)
        mock_sock.reset_mock()

        h2._send(b"")

        mock_sock.sendall.assert_not_called()

    @patch('gakido.http2.h2.connection.H2Connection')
    def test_send_data(self, mock_h2_conn_class):
        """Test _send with data calls sendall."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn_class.return_value = mock_h2_conn

        h2 = HTTP2Connection(mock_sock)
        mock_sock.reset_mock()

        h2._send(b"data to send")

        mock_sock.sendall.assert_called_once_with(b"data to send")


class TestHTTP2ConnectionHeaders:
    """Tests for HTTP2Connection header handling."""

    @patch('gakido.http2.h2.events')
    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_filters_pseudo_headers(self, mock_h2_conn_class, mock_events):
        """Test response filters out pseudo-headers from headers list."""
        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        # Mock response with pseudo-headers and regular headers
        mock_response_received = MagicMock()
        mock_response_received.headers = [
            (b":status", b"200"),
            (b"content-type", b"text/html"),
            (b"content-length", b"100"),
        ]
        mock_stream_ended = MagicMock()

        mock_events.ResponseReceived = type(mock_response_received)
        mock_events.DataReceived = MagicMock
        mock_events.StreamEnded = type(mock_stream_ended)
        mock_events.StreamReset = MagicMock

        mock_sock.recv.side_effect = [b"h2data", b""]
        mock_h2_conn.receive_data.return_value = [
            mock_response_received,
            mock_stream_ended,
        ]

        h2 = HTTP2Connection(mock_sock)
        response = h2.request("GET", "example.com", "/", [])

        # Verify pseudo-headers are not in response headers
        header_names = [name for name, _ in response.raw_headers]
        assert ":status" not in header_names
        assert "content-type" in header_names

    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_handles_bytes_headers(self, mock_h2_conn_class):
        """Test response handles bytes headers correctly."""
        import h2.events

        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        # Mock response with bytes headers (standard h2 behavior)
        mock_response_received = MagicMock(spec=h2.events.ResponseReceived)
        mock_response_received.headers = [
            (b":status", b"200"),
            (b"content-type", b"text/html"),
        ]
        mock_stream_ended = MagicMock(spec=h2.events.StreamEnded)

        mock_sock.recv.side_effect = [b"h2data", b""]
        mock_h2_conn.receive_data.return_value = [
            mock_response_received,
            mock_stream_ended,
        ]

        h2 = HTTP2Connection(mock_sock)
        response = h2.request("GET", "example.com", "/", [])

        assert response.status_code == 200


class TestHTTP2ConnectionFlowControl:
    """Tests for HTTP2Connection flow control."""

    @patch('gakido.http2.h2.connection.H2Connection')
    def test_request_acknowledges_received_data(self, mock_h2_conn_class):
        """Test request acknowledges received data for flow control."""
        import h2.events

        mock_sock = MagicMock()
        mock_h2_conn = MagicMock()
        mock_h2_conn.data_to_send.return_value = b""
        mock_h2_conn.get_next_available_stream_id.return_value = 1
        mock_h2_conn_class.return_value = mock_h2_conn

        # Mock data received event
        mock_data_received = MagicMock(spec=h2.events.DataReceived)
        mock_data_received.data = b"response body"
        mock_data_received.flow_controlled_length = 13
        mock_stream_ended = MagicMock(spec=h2.events.StreamEnded)

        mock_sock.recv.side_effect = [b"h2data", b""]
        mock_h2_conn.receive_data.return_value = [
            mock_data_received,
            mock_stream_ended,
        ]

        h2 = HTTP2Connection(mock_sock)
        h2.request("GET", "example.com", "/", [])

        mock_h2_conn.acknowledge_received_data.assert_called_with(13, 1)
