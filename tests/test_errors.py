"""Tests for gakido.errors module."""

import pytest
from gakido.errors import (
    GakidoError,
    ConnectionError,
    TLSNegotiationError,
    ProtocolError,
    HTTPError,
    HTTP3NotAvailableError,
)


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_gakido_error_is_exception(self):
        """Test GakidoError inherits from Exception."""
        assert issubclass(GakidoError, Exception)

    def test_connection_error_inherits_gakido_error(self):
        """Test ConnectionError inherits from GakidoError."""
        assert issubclass(ConnectionError, GakidoError)

    def test_tls_negotiation_error_inherits_connection_error(self):
        """Test TLSNegotiationError inherits from ConnectionError."""
        assert issubclass(TLSNegotiationError, ConnectionError)
        assert issubclass(TLSNegotiationError, GakidoError)

    def test_protocol_error_inherits_gakido_error(self):
        """Test ProtocolError inherits from GakidoError."""
        assert issubclass(ProtocolError, GakidoError)

    def test_http_error_inherits_gakido_error(self):
        """Test HTTPError inherits from GakidoError."""
        assert issubclass(HTTPError, GakidoError)

    def test_http3_not_available_error_inherits_gakido_error(self):
        """Test HTTP3NotAvailableError inherits from GakidoError."""
        assert issubclass(HTTP3NotAvailableError, GakidoError)


class TestErrorInstantiation:
    """Tests for error instantiation."""

    def test_gakido_error_with_message(self):
        """Test GakidoError can be raised with message."""
        with pytest.raises(GakidoError, match="test message"):
            raise GakidoError("test message")

    def test_connection_error_with_message(self):
        """Test ConnectionError can be raised with message."""
        with pytest.raises(ConnectionError, match="connection failed"):
            raise ConnectionError("connection failed")

    def test_tls_negotiation_error_with_message(self):
        """Test TLSNegotiationError can be raised with message."""
        with pytest.raises(TLSNegotiationError, match="TLS handshake"):
            raise TLSNegotiationError("TLS handshake failed")

    def test_protocol_error_with_message(self):
        """Test ProtocolError can be raised with message."""
        with pytest.raises(ProtocolError, match="invalid response"):
            raise ProtocolError("invalid response")

    def test_http_error_with_message(self):
        """Test HTTPError can be raised with message."""
        with pytest.raises(HTTPError, match="404 Not Found"):
            raise HTTPError("404 Not Found")

    def test_http3_not_available_error_with_message(self):
        """Test HTTP3NotAvailableError can be raised with message."""
        with pytest.raises(HTTP3NotAvailableError, match="aioquic"):
            raise HTTP3NotAvailableError("aioquic not installed")


class TestErrorCatching:
    """Tests for catching errors at different hierarchy levels."""

    def test_catch_tls_error_as_connection_error(self):
        """Test TLSNegotiationError can be caught as ConnectionError."""
        try:
            raise TLSNegotiationError("TLS failed")
        except ConnectionError as e:
            assert "TLS failed" in str(e)

    def test_catch_connection_error_as_gakido_error(self):
        """Test ConnectionError can be caught as GakidoError."""
        try:
            raise ConnectionError("connection failed")
        except GakidoError as e:
            assert "connection failed" in str(e)

    def test_catch_all_as_gakido_error(self):
        """Test all custom errors can be caught as GakidoError."""
        errors = [
            ConnectionError("conn"),
            TLSNegotiationError("tls"),
            ProtocolError("proto"),
            HTTPError("http"),
            HTTP3NotAvailableError("h3"),
        ]
        for error in errors:
            try:
                raise error
            except GakidoError:
                pass  # Should catch all
