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


class RedirectError(HTTPError):
    """Base error for redirect handling failures."""


class TooManyRedirectsError(RedirectError):
    """Raised when a redirect chain exceeds the configured maximum."""


class CircularRedirectError(RedirectError):
    """Raised when a redirect chain loops back to an already-visited URL."""


class HTTP3NotAvailableError(GakidoError):
    """Raised when HTTP/3 is requested but aioquic is not installed."""
