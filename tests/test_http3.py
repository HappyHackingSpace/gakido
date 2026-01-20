"""Tests for gakido.http3 module."""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from gakido.http3 import (
    is_http3_available,
    parse_alt_svc,
    HTTP3Protocol,
    H3ResponseHandler,
    _get_aioquic,
)
from gakido.errors import HTTP3NotAvailableError, ProtocolError


class TestIsHttp3Available:
    """Tests for is_http3_available function."""

    def test_returns_boolean(self):
        """Test function returns a boolean."""
        result = is_http3_available()
        assert isinstance(result, bool)

    def test_consistent_results(self):
        """Test function returns consistent results."""
        result1 = is_http3_available()
        result2 = is_http3_available()
        assert result1 == result2


class TestParseAltSvc:
    """Tests for parse_alt_svc function."""

    def test_parse_simple_h3(self):
        """Test parsing simple h3 Alt-Svc."""
        result = parse_alt_svc('h3=":443"')
        assert "h3" in result
        assert result["h3"] == ("", 443)

    def test_parse_h3_with_host(self):
        """Test parsing h3 with different host."""
        result = parse_alt_svc('h3="alt.example.com:443"')
        assert result["h3"] == ("alt.example.com", 443)

    def test_parse_multiple_protocols(self):
        """Test parsing multiple protocols."""
        result = parse_alt_svc('h3=":443", h3-29=":443", h2=":443"')
        assert "h3" in result
        assert "h3-29" in result
        assert "h2" in result

    def test_parse_with_params(self):
        """Test parsing with parameters (max-age, etc)."""
        result = parse_alt_svc('h3=":443"; ma=86400')
        assert result["h3"] == ("", 443)

    def test_parse_clear(self):
        """Test parsing 'clear' directive."""
        result = parse_alt_svc("clear")
        assert result == {}

    def test_parse_empty(self):
        """Test parsing empty string."""
        result = parse_alt_svc("")
        assert result == {}

    def test_parse_custom_port(self):
        """Test parsing with custom port."""
        result = parse_alt_svc('h3=":8443"')
        assert result["h3"] == ("", 8443)

    def test_parse_host_without_port(self):
        """Test parsing host without explicit port."""
        result = parse_alt_svc('h3="alt.example.com"')
        assert result["h3"] == ("alt.example.com", 443)

    def test_parse_invalid_format_ignored(self):
        """Test invalid format entries are ignored."""
        result = parse_alt_svc('invalid, h3=":443"')
        assert "h3" in result
        assert "invalid" not in result

    def test_parse_whitespace_handling(self):
        """Test whitespace is handled correctly."""
        result = parse_alt_svc('  h3=":443"  ,  h3-29=":443"  ')
        assert "h3" in result
        assert "h3-29" in result

    def test_parse_cloudflare_style(self):
        """Test parsing Cloudflare-style Alt-Svc header."""
        header = 'h3=":443"; ma=86400, h3-29=":443"; ma=86400'
        result = parse_alt_svc(header)
        assert result["h3"] == ("", 443)
        assert result["h3-29"] == ("", 443)

    def test_parse_no_closing_quote(self):
        """Test parsing when closing quote is missing."""
        result = parse_alt_svc('h3=":443')
        assert result["h3"] == ("", 443)

    def test_parse_value_error_ignored(self):
        """Test ValueError during parsing is ignored."""
        result = parse_alt_svc('h3=":notaport", h3-29=":443"')
        # h3 should be skipped due to ValueError, h3-29 should work
        assert "h3-29" in result

    def test_parse_index_error_ignored(self):
        """Test IndexError during parsing is ignored."""
        result = parse_alt_svc('=, h3=":443"')
        assert "h3" in result


class TestHttp3Module:
    """Tests for HTTP3 module imports and errors."""

    def test_http3_not_available_error_message(self):
        """Test HTTP3NotAvailableError has helpful message."""
        error = HTTP3NotAvailableError("test message")
        assert "test message" in str(error)

    @pytest.mark.skipif(
        is_http3_available(),
        reason="aioquic is installed"
    )
    def test_get_aioquic_raises_when_unavailable(self):
        """Test _get_aioquic raises when aioquic not installed."""
        with pytest.raises(HTTP3NotAvailableError, match="aioquic"):
            _get_aioquic()

    @pytest.mark.skipif(
        not is_http3_available(),
        reason="aioquic not installed"
    )
    def test_get_aioquic_returns_modules_when_available(self):
        """Test _get_aioquic returns modules when aioquic installed."""
        mods = _get_aioquic()
        assert "quic_connect" in mods
        assert "QuicConfiguration" in mods
        assert "H3Connection" in mods


class TestH3ResponseHandler:
    """Tests for H3ResponseHandler class."""

    def test_init(self):
        """Test H3ResponseHandler initialization."""
        handler = H3ResponseHandler(stream_id=1)

        assert handler.stream_id == 1
        assert handler.status_code == 0
        assert handler.headers == []
        assert handler.body == bytearray()
        assert handler.complete is False
        assert handler._waiter is None

    def test_feed_event_headers_received(self):
        """Test feeding HeadersReceived event."""
        handler = H3ResponseHandler(stream_id=1)

        mock_event = MagicMock()
        mock_event.stream_id = 1
        mock_event.headers = [
            (b":status", b"200"),
            (b"content-type", b"text/html"),
        ]
        mock_event.stream_ended = False

        mods = {
            "DataReceived": MagicMock,
            "HeadersReceived": type(mock_event),
        }

        handler.feed_event(mock_event, mods)

        assert handler.status_code == 200
        assert ("content-type", "text/html") in handler.headers

    def test_feed_event_headers_with_stream_ended(self):
        """Test feeding HeadersReceived event with stream_ended=True."""
        handler = H3ResponseHandler(stream_id=1)

        mock_event = MagicMock()
        mock_event.stream_id = 1
        mock_event.headers = [(b":status", b"200")]
        mock_event.stream_ended = True

        mods = {
            "DataReceived": MagicMock,
            "HeadersReceived": type(mock_event),
        }

        handler.feed_event(mock_event, mods)

        assert handler.complete is True

    def test_feed_event_data_received(self):
        """Test feeding DataReceived event."""
        handler = H3ResponseHandler(stream_id=1)

        # Create a class for DataReceived that isinstance can check
        class MockDataReceived:
            def __init__(self):
                self.stream_id = 1
                self.data = b"response body"
                self.stream_ended = False

        mock_event = MockDataReceived()

        mods = {
            "DataReceived": MockDataReceived,
            "HeadersReceived": MagicMock,
        }

        handler.feed_event(mock_event, mods)

        assert bytes(handler.body) == b"response body"
        assert handler.complete is False

    def test_feed_event_data_with_stream_ended(self):
        """Test feeding DataReceived event with stream_ended=True."""
        handler = H3ResponseHandler(stream_id=1)

        mock_event = MagicMock()
        mock_event.stream_id = 1
        mock_event.data = b"body"
        mock_event.stream_ended = True

        mods = {
            "DataReceived": type(mock_event),
            "HeadersReceived": MagicMock,
        }

        handler.feed_event(mock_event, mods)

        assert handler.complete is True

    def test_feed_event_wrong_stream_id_ignored(self):
        """Test feeding event with wrong stream_id is ignored."""
        handler = H3ResponseHandler(stream_id=1)

        mock_event = MagicMock()
        mock_event.stream_id = 999  # Wrong stream ID
        mock_event.data = b"data"
        mock_event.stream_ended = False

        mods = {
            "DataReceived": type(mock_event),
            "HeadersReceived": MagicMock,
        }

        handler.feed_event(mock_event, mods)

        assert bytes(handler.body) == b""

    def test_feed_event_string_headers(self):
        """Test feeding HeadersReceived event with string headers."""
        handler = H3ResponseHandler(stream_id=1)

        mock_event = MagicMock()
        mock_event.stream_id = 1
        mock_event.headers = [
            (":status", "200"),  # String headers
            ("content-type", "text/html"),
        ]
        mock_event.stream_ended = False

        mods = {
            "DataReceived": MagicMock,
            "HeadersReceived": type(mock_event),
        }

        handler.feed_event(mock_event, mods)

        assert handler.status_code == 200

    def test_feed_event_filters_pseudo_headers(self):
        """Test pseudo-headers (starting with :) are filtered."""
        handler = H3ResponseHandler(stream_id=1)

        mock_event = MagicMock()
        mock_event.stream_id = 1
        mock_event.headers = [
            (b":status", b"200"),
            (b":other", b"value"),
            (b"content-type", b"text/html"),
        ]
        mock_event.stream_ended = False

        mods = {
            "DataReceived": MagicMock,
            "HeadersReceived": type(mock_event),
        }

        handler.feed_event(mock_event, mods)

        header_names = [name for name, _ in handler.headers]
        assert ":status" not in header_names
        assert ":other" not in header_names
        assert "content-type" in header_names

    @pytest.mark.asyncio
    async def test_wait_complete_already_complete(self):
        """Test wait_complete returns immediately if already complete."""
        handler = H3ResponseHandler(stream_id=1)
        handler.complete = True

        # Should return immediately without waiting
        await handler.wait_complete(timeout=1.0)

    @pytest.mark.asyncio
    async def test_wait_complete_timeout(self):
        """Test wait_complete raises on timeout."""
        handler = H3ResponseHandler(stream_id=1)

        with pytest.raises(ProtocolError, match="HTTP/3 response timeout"):
            await handler.wait_complete(timeout=0.01)

    def test_mark_complete_sets_waiter(self):
        """Test _mark_complete sets waiter result."""
        import asyncio
        handler = H3ResponseHandler(stream_id=1)
        handler._waiter = asyncio.get_event_loop().create_future()

        handler._mark_complete()

        assert handler.complete is True
        assert handler._waiter.done()


class TestHTTP3Protocol:
    """Tests for HTTP3Protocol class."""

    def test_init(self):
        """Test HTTP3Protocol initialization."""
        proto = HTTP3Protocol(
            host="example.com",
            port=443,
            verify=True,
            timeout=30.0,
            profile={"http3": {"max_stream_data": 1048576}},
        )

        assert proto.host == "example.com"
        assert proto.port == 443
        assert proto.verify is True
        assert proto.timeout == 30.0
        assert proto._connected is False

    def test_init_default_values(self):
        """Test HTTP3Protocol default values."""
        proto = HTTP3Protocol(host="example.com")

        assert proto.port == 443
        assert proto.verify is True
        assert proto.timeout == 10.0
        assert proto.profile == {}

    @pytest.mark.asyncio
    async def test_close(self):
        """Test HTTP3Protocol close."""
        proto = HTTP3Protocol(host="example.com")
        proto._connected = True
        proto._protocol = MagicMock()
        proto._h3 = MagicMock()
        proto._handlers = {1: MagicMock()}

        await proto.close()

        assert proto._connected is False
        assert proto._h3 is None
        assert proto._protocol is None
        assert len(proto._handlers) == 0

    @pytest.mark.asyncio
    async def test_close_with_protocol_error(self):
        """Test close handles protocol close error gracefully."""
        proto = HTTP3Protocol(host="example.com")
        proto._connected = True
        proto._protocol = MagicMock()
        proto._protocol.close.side_effect = Exception("close error")

        await proto.close()  # Should not raise

        assert proto._connected is False

    @pytest.mark.skipif(
        not is_http3_available(),
        reason="aioquic not installed"
    )
    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Test connect raises on timeout."""
        proto = HTTP3Protocol(
            host="nonexistent.example.com",
            port=443,
            timeout=0.01,
        )

        with pytest.raises(ProtocolError, match="HTTP/3 connection"):
            await proto.connect()

    @pytest.mark.skipif(
        is_http3_available(),
        reason="aioquic is installed"
    )
    @pytest.mark.asyncio
    async def test_connect_without_aioquic(self):
        """Test connect raises when aioquic not installed."""
        proto = HTTP3Protocol(host="example.com")

        with pytest.raises(HTTP3NotAvailableError):
            await proto.connect()


class TestHTTP3Request:
    """Tests for http3_request function."""

    @pytest.mark.skipif(
        is_http3_available(),
        reason="aioquic is installed - test for unavailable case"
    )
    @pytest.mark.asyncio
    async def test_http3_request_without_aioquic(self):
        """Test http3_request raises when aioquic not installed."""
        from gakido.http3 import http3_request

        with pytest.raises(HTTP3NotAvailableError):
            await http3_request(
                method="GET",
                url="https://example.com",
                host="example.com",
                port=443,
                path="/",
                headers=[],
            )


class TestHTTP3ProtocolRequest:
    """Tests for HTTP3Protocol.request method."""

    @pytest.mark.asyncio
    async def test_request_reconnects_if_disconnected(self):
        """Test request calls connect if not connected."""
        proto = HTTP3Protocol(host="example.com")
        proto._connected = False
        proto.connect = AsyncMock(side_effect=ProtocolError("connection failed"))

        with pytest.raises(ProtocolError, match="connection failed"):
            await proto.request("GET", "/", [])
