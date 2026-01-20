class GakidoError(Exception):
    """Base error for Gakido."""


class ConnectionError(GakidoError):
    """Raised when a TCP/TLS connection fails."""


class TLSNegotiationError(ConnectionError):
    """Raised when TLS handshake does not meet expectations."""


class ProtocolError(GakidoError):
    """Raised when an HTTP protocol error occurs."""


class HTTPError(GakidoError):
    """Raised for HTTP-level issues."""


class HTTP3NotAvailableError(GakidoError):
    """Raised when HTTP/3 is requested but aioquic is not installed."""
